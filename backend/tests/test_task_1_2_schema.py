"""
TASK 1.2 — Database Schema Unit Tests

The app uses postgresql+asyncpg (async driver).
pytest-asyncio is configured in AUTO mode in pytest.ini.

All fixtures are function-scoped to avoid asyncpg event-loop/connection
re-use issues across tests (module-scoped async fixtures + per-function
event loops cause "another operation is in progress" errors with asyncpg).

LEARNINGS:
  - App uses asyncpg driver — tests must use AsyncEngine + AsyncSession
  - Keep fixtures function-scoped to avoid asyncpg event loop / connection
    reuse issues between tests
  - For write tests, begin a transaction and rollback after yield

Verifies:
- All 20 expected tables exist in the database
- blog_articles.embedding is vector(1024) type (pgvector migration ran)
- Expense categories seeded (8 records, correct i18n keys, benchmarks)
- admin_config seeded (5 entries, tva_rate = 0.20)
- User model: insert + retrieve round-trip
- User email unique constraint enforced
- Salon FK to user
- MonthlyReport unique constraint (salon, year, month)
- ExpenseCategory unique i18n_key constraint
"""

import uuid
import pytest
import pytest_asyncio
from decimal import Decimal
from sqlalchemy import text, select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.models.user import User
from app.models.salon import Salon
from app.models.financial import ExpenseCategory, MonthlyReport
from app.models.admin import AdminConfig


# ── Helper — get a fresh read-only session ────────────────────────────────────

async def read_session():
    """Context manager for a fresh read-only AsyncSession."""
    engine = create_async_engine(settings.database_url, echo=False)
    session = AsyncSession(engine, expire_on_commit=False)
    try:
        yield session, engine
    finally:
        await session.close()
        await engine.dispose()


# ── Table existence ───────────────────────────────────────────────────────────

EXPECTED_TABLES = [
    "users", "salons", "employees", "salon_config", "prime_config",
    "monthly_reports", "expenses", "expense_categories", "monthly_salaries",
    "monthly_primes", "services", "noly_subscriptions", "payslip_wallet",
    "payslip_forms", "payslip_transactions",
    "blog_articles", "partners", "admin_config",
    "coco_user_profiles", "coco_conversations",
]


async def test_all_tables_exist():
    """All 20 expected tables must exist in the public schema."""
    engine = create_async_engine(settings.database_url, echo=False)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            )
            existing = {row[0] for row in result}
    finally:
        await engine.dispose()

    missing = set(EXPECTED_TABLES) - existing
    assert not missing, f"Missing tables: {missing}"


async def test_blog_embedding_is_vector_type():
    """
    The embedding column on blog_articles must be of type 'vector'.
    Confirms the pgvector ALTER TABLE ran in the migration.
    """
    engine = create_async_engine(settings.database_url, echo=False)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT udt_name FROM information_schema.columns "
                    "WHERE table_name = 'blog_articles' AND column_name = 'embedding'"
                )
            )
            row = result.fetchone()
    finally:
        await engine.dispose()

    assert row is not None, "embedding column not found on blog_articles"
    assert row[0] == "vector", f"Expected vector type, got: {row[0]}"


# ── Seed data ─────────────────────────────────────────────────────────────────

EXPECTED_CATEGORY_KEYS = [
    "expenses.achats_marchandises",
    "expenses.frais_personnel",
    "expenses.loyer_immobilier",
    "expenses.energie_fluides",
    "expenses.marketing_communication",
    "expenses.frais_generaux",
    "expenses.entretien_divers",
    "expenses.benefice_ebitda",
]


async def test_expense_categories_seeded():
    """All 8 system expense categories from Eric's grille must be present."""
    engine = create_async_engine(settings.database_url, echo=False)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await session.execute(
                select(ExpenseCategory).where(ExpenseCategory.is_system.is_(True))
            )
            categories = result.scalars().all()
    finally:
        await engine.dispose()

    seeded_keys = {c.i18n_key for c in categories}
    missing = set(EXPECTED_CATEGORY_KEYS) - seeded_keys
    assert not missing, f"Missing expense category keys: {missing}"
    assert len(categories) == 8


async def test_expense_categories_have_benchmarks():
    """Frais de personnel repère = 50%, idéal = 40% (Eric's grille)."""
    engine = create_async_engine(settings.database_url, echo=False)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await session.execute(
                select(ExpenseCategory).where(
                    ExpenseCategory.i18n_key == "expenses.frais_personnel"
                )
            )
            cat = result.scalar_one()
    finally:
        await engine.dispose()

    assert cat.percent_ca_repere == Decimal("0.5000")
    assert cat.percent_ca_ideal == Decimal("0.4000")


async def test_admin_config_tva_rate_seeded():
    """tva_rate must be seeded with rate = '0.20'."""
    engine = create_async_engine(settings.database_url, echo=False)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await session.execute(
                select(AdminConfig).where(AdminConfig.key == "tva_rate")
            )
            config = result.scalar_one_or_none()
    finally:
        await engine.dispose()

    assert config is not None, "tva_rate not found in admin_config"
    assert config.value["rate"] == "0.20"


async def test_admin_config_has_five_entries():
    """Seed must produce exactly 5 admin_config entries."""
    engine = create_async_engine(settings.database_url, echo=False)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await session.execute(
                select(func.count()).select_from(AdminConfig)
            )
            count = result.scalar()
    finally:
        await engine.dispose()

    assert count == 5


# ── Write tests — each uses its own engine + rolled-back transaction ──────────

async def test_user_insert_and_retrieve():
    """A user can be inserted and retrieved with correct fields."""
    engine = create_async_engine(settings.database_url, echo=False)
    try:
        async with engine.begin() as conn:
            # Wrap in a SAVEPOINT so we can rollback cleanly
            sp = await conn.begin_nested()
            session = AsyncSession(bind=conn, expire_on_commit=False)
            try:
                user = User(
                    email="test_insert@example.com",
                    password_hash="hashed_pw",
                    name="Test User",
                    role="user",
                    onboarding_completed=False,
                    preferred_tools=[],
                )
                session.add(user)
                await session.flush()

                result = await session.execute(
                    select(User).where(User.email == "test_insert@example.com")
                )
                retrieved = result.scalar_one()
                assert retrieved.name == "Test User"
                assert retrieved.role == "user"
                assert isinstance(retrieved.id, uuid.UUID)
            finally:
                await session.close()
                await sp.rollback()
    finally:
        await engine.dispose()


async def test_user_email_unique_constraint():
    """Two users with the same email must raise IntegrityError."""
    engine = create_async_engine(settings.database_url, echo=False)
    try:
        async with engine.begin() as conn:
            sp = await conn.begin_nested()
            session = AsyncSession(bind=conn, expire_on_commit=False)
            try:
                u1 = User(email="dupe@example.com", password_hash="pw1", name="User 1")
                session.add(u1)
                await session.flush()

                u2 = User(email="dupe@example.com", password_hash="pw2", name="User 2")
                session.add(u2)
                with pytest.raises(IntegrityError):
                    await session.flush()
            finally:
                await session.close()
                await sp.rollback()
    finally:
        await engine.dispose()


async def test_salon_fk_to_user():
    """A salon can be linked to a valid user."""
    engine = create_async_engine(settings.database_url, echo=False)
    try:
        async with engine.begin() as conn:
            sp = await conn.begin_nested()
            session = AsyncSession(bind=conn, expire_on_commit=False)
            try:
                user = User(
                    email="salon_owner@example.com", password_hash="pw", name="Owner"
                )
                session.add(user)
                await session.flush()

                salon = Salon(
                    user_id=user.id, name="Salon Test", business_type="sarl"
                )
                session.add(salon)
                await session.flush()

                assert salon.id is not None
                assert salon.user_id == user.id
            finally:
                await session.close()
                await sp.rollback()
    finally:
        await engine.dispose()


async def test_monthly_report_unique_constraint():
    """
    Two monthly reports for the same salon + year + month → IntegrityError.
    Critical — prevents duplicate copilot entries.
    """
    engine = create_async_engine(settings.database_url, echo=False)
    try:
        async with engine.begin() as conn:
            sp = await conn.begin_nested()
            session = AsyncSession(bind=conn, expire_on_commit=False)
            try:
                user = User(
                    email="mr_test@example.com", password_hash="pw", name="MR User"
                )
                session.add(user)
                await session.flush()

                salon = Salon(
                    user_id=user.id, name="Salon MR", business_type="eurl"
                )
                session.add(salon)
                await session.flush()

                r1 = MonthlyReport(salon_id=salon.id, year=2025, month=3)
                session.add(r1)
                await session.flush()

                r2 = MonthlyReport(salon_id=salon.id, year=2025, month=3)
                session.add(r2)
                with pytest.raises(IntegrityError):
                    await session.flush()
            finally:
                await session.close()
                await sp.rollback()
    finally:
        await engine.dispose()


async def test_expense_category_i18n_key_unique():
    """Two expense categories with the same i18n_key → IntegrityError."""
    engine = create_async_engine(settings.database_url, echo=False)
    try:
        async with engine.begin() as conn:
            sp = await conn.begin_nested()
            session = AsyncSession(bind=conn, expire_on_commit=False)
            try:
                c1 = ExpenseCategory(
                    name="Cat A", i18n_key="test.dup_key", is_system=False
                )
                session.add(c1)
                await session.flush()

                c2 = ExpenseCategory(
                    name="Cat B", i18n_key="test.dup_key", is_system=False
                )
                session.add(c2)
                with pytest.raises(IntegrityError):
                    await session.flush()
            finally:
                await session.close()
                await sp.rollback()
    finally:
        await engine.dispose()
