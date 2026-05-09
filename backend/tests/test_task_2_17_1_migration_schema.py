"""
TASK-2.17.1 — Bubble import metadata schema tests.

Follows the codebase's self-contained test pattern: each test creates its own
async DB session using create_async_engine / async_sessionmaker (no shared
db_session fixture — see test_grandfathering_schema.py for the same approach).

Tests:
    T1. Column existence: check information_schema.columns for every new field.
    T2. UNIQUE partial index: duplicate non-null bubble_user_id raises IntegrityError.
    T3. NULL bubble_user_id values don't trigger the partial unique index.
    T4. Run lifecycle: start → inserted → updated → skipped → error → cursor → finish.
    T5. error_log errored counter increments correctly.
    T6. BubbleImportRun.__repr__ smoke test.
"""

import uuid
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import settings
from app.services.bubble_import import (
    finish_run,
    record_error,
    record_inserted,
    record_skipped,
    record_updated,
    set_cursor,
    start_run,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_factory():
    """Return a fresh (engine, session_factory) pair for this test."""
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


async def _col_exists(db, table: str, column: str) -> bool:
    """Return True if column exists in table per information_schema."""
    result = await db.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.fetchone() is not None


# ── T1: column existence ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_users_bubble_columns_exist():
    """users table has all six new bubble migration columns."""
    _, factory = _make_factory()
    async with factory() as db:
        for col in [
            "bubble_user_id",
            "import_source",
            "import_status",
            "import_completion_step",
            "last_paid_at",
            "welcome_email_sent_at",
        ]:
            assert await _col_exists(db, "users", col), f"users.{col} missing"


@pytest.mark.asyncio
async def test_salons_bubble_columns_exist():
    """salons table has bubble_salon_id + bubble_establishment_type."""
    _, factory = _make_factory()
    async with factory() as db:
        assert await _col_exists(db, "salons", "bubble_salon_id")
        assert await _col_exists(db, "salons", "bubble_establishment_type")


@pytest.mark.asyncio
async def test_employees_bubble_column_exists():
    _, factory = _make_factory()
    async with factory() as db:
        assert await _col_exists(db, "employees", "bubble_employee_id")


@pytest.mark.asyncio
async def test_services_bubble_column_exists():
    _, factory = _make_factory()
    async with factory() as db:
        assert await _col_exists(db, "services", "bubble_service_id")


@pytest.mark.asyncio
async def test_monthly_reports_bubble_column_exists():
    _, factory = _make_factory()
    async with factory() as db:
        assert await _col_exists(db, "monthly_reports", "bubble_month_id")


@pytest.mark.asyncio
async def test_expenses_bubble_column_exists():
    _, factory = _make_factory()
    async with factory() as db:
        assert await _col_exists(db, "expenses", "bubble_item_id")


@pytest.mark.asyncio
async def test_monthly_salaries_bubble_column_exists():
    _, factory = _make_factory()
    async with factory() as db:
        assert await _col_exists(db, "monthly_salaries", "bubble_item_id")


@pytest.mark.asyncio
async def test_noly_subscriptions_bubble_columns_exist():
    _, factory = _make_factory()
    async with factory() as db:
        assert await _col_exists(db, "noly_subscriptions", "bubble_abonnement_id")
        assert await _col_exists(db, "noly_subscriptions", "stripe_price_id")


@pytest.mark.asyncio
async def test_blog_articles_bubble_columns_exist():
    """blog_articles has all five new columns."""
    _, factory = _make_factory()
    async with factory() as db:
        for col in [
            "bubble_blog_id",
            "body_html_cleaned",
            "enhancement_status",
            "enhancement_diff",
            "published_version",
        ]:
            assert await _col_exists(db, "blog_articles", col), f"blog_articles.{col} missing"


@pytest.mark.asyncio
async def test_bubble_import_runs_table_and_columns_exist():
    """bubble_import_runs table exists with all required columns."""
    _, factory = _make_factory()
    async with factory() as db:
        for col in [
            "id", "script_name", "started_at", "finished_at", "dry_run",
            "inserted", "updated", "skipped", "errored",
            "last_cursor", "error_log", "triggered_by", "notes",
        ]:
            assert await _col_exists(db, "bubble_import_runs", col), (
                f"bubble_import_runs.{col} missing"
            )


# ── T2: partial unique index on bubble_user_id ───────────────────────────────

@pytest.mark.asyncio
async def test_bubble_user_id_unique_index():
    """Inserting duplicate non-null bubble_user_id raises IntegrityError."""
    unique_bubble_id = f"test-bubble-uid-{uuid.uuid4().hex[:8]}"
    email_a = f"bubble-a-{uuid.uuid4().hex[:8]}@test.com"
    email_b = f"bubble-b-{uuid.uuid4().hex[:8]}@test.com"

    _, factory = _make_factory()
    async with factory() as db:
        # Insert first user with this bubble_user_id
        await db.execute(
            text(
                "INSERT INTO users (email, password_hash, name, bubble_user_id) "
                "VALUES (:e, 'x', 'User A', :bid)"
            ),
            {"e": email_a, "bid": unique_bubble_id},
        )
        await db.commit()

        # Attempt duplicate — must raise
        with pytest.raises(IntegrityError):
            await db.execute(
                text(
                    "INSERT INTO users (email, password_hash, name, bubble_user_id) "
                    "VALUES (:e, 'x', 'User B', :bid)"
                ),
                {"e": email_b, "bid": unique_bubble_id},
            )
            await db.flush()

    # Cleanup
    _, factory = _make_factory()
    async with factory() as db:
        await db.execute(text("DELETE FROM users WHERE email = :e"), {"e": email_a})
        await db.commit()


@pytest.mark.asyncio
async def test_bubble_user_id_null_not_unique():
    """Multiple users with NULL bubble_user_id do NOT violate the partial index."""
    email_a = f"null-bubble-a-{uuid.uuid4().hex[:8]}@test.com"
    email_b = f"null-bubble-b-{uuid.uuid4().hex[:8]}@test.com"

    _, factory = _make_factory()
    async with factory() as db:
        await db.execute(
            text("INSERT INTO users (email, password_hash, name) VALUES (:a, 'x', 'A'), (:b, 'x', 'B')"),
            {"a": email_a, "b": email_b},
        )
        await db.commit()  # should not raise

    # Cleanup
    _, factory = _make_factory()
    async with factory() as db:
        await db.execute(
            text("DELETE FROM users WHERE email IN (:a, :b)"),
            {"a": email_a, "b": email_b},
        )
        await db.commit()


# ── T3: run lifecycle ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_lifecycle():
    """Full lifecycle: start → counters → cursor → finish."""
    _, factory = _make_factory()
    async with factory() as db:
        run = await start_run(db, "test_script_lifecycle", dry_run=False)
        assert run.id is not None
        assert run.finished_at is None
        assert run.inserted == 0

        await record_inserted(run, db, 3)
        assert run.inserted == 3

        await record_updated(run, db)
        assert run.updated == 1

        await record_skipped(run, db, 2)
        assert run.skipped == 2

        await set_cursor(run, db, 100)
        assert run.last_cursor == 100

        await finish_run(run, db)
        assert run.finished_at is not None


# ── T4: error counter ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_error_log_increments_counter():
    """record_error increments errored counter."""
    _, factory = _make_factory()
    async with factory() as db:
        run = await start_run(db, "test_errors_counter", dry_run=True)
        await record_error(run, db, bubble_id="bubble-aaa", reason="not found")
        await record_error(run, db, bubble_id="bubble-bbb", reason="schema mismatch")
        assert run.errored == 2
        await finish_run(run, db)


# ── T5: repr smoke test ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bubble_import_run_repr():
    """BubbleImportRun.__repr__ contains script name and class name."""
    _, factory = _make_factory()
    async with factory() as db:
        run = await start_run(db, "repr_smoke_test")
        r = repr(run)
        assert "repr_smoke_test" in r
        assert "BubbleImportRun" in r
        await finish_run(run, db)
