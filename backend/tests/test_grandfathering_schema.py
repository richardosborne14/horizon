"""
Tests for TASK-2.16.2 — Grandfathering schema and service.

Covers:
  - mark_user_legacy sets the flag and writes an audit row
  - Idempotency: same plan called twice → one audit row, not two
  - Plan change: updating to a different plan writes a new audit row
  - is_legacy pure-function helper
  - GET /api/users/me serialises the legacy_pricing_plan field

Uses ASGITransport(app=app) — codebase standard in-process test pattern.
Self-contained: each test creates its own user and cleans up after itself.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.config import settings
from app.models.user import User
from app.models.legacy_pricing import LegacyPricingAudit
from app.services.grandfathering import mark_user_legacy, is_legacy, get_legacy_audit_trail


# ── Helpers ───────────────────────────────────────────────────────────────────


def _api_client() -> AsyncClient:
    """Return a fresh ASGI test client (unauthenticated)."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _register_login(client: AsyncClient, email: str) -> None:
    """Register and log in a user (sets session cookie on client)."""
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "name": "Test Grandfathering"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"


async def _make_db_session():
    """Create a direct async DB session for assertions/cleanup."""
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


async def _delete_user(email: str) -> None:
    """Delete test user by email (cascade removes all related rows)."""
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            await db.delete(user)
            await db.commit()
    await engine.dispose()


async def _get_user(email: str) -> User | None:
    """Fetch user by email via direct DB query."""
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()
    await engine.dispose()


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mark_user_legacy_sets_flag_and_audit():
    """
    After calling mark_user_legacy, the user row has the plan set
    and a LegacyPricingAudit row exists.
    """
    email = "test_2_16_2_a@comcoi-test.fr"
    await _delete_user(email)

    async with _api_client() as client:
        await _register_login(client, email)

    # Direct DB work — call the service as the migration/backfill scripts would
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            assert user is not None
            assert user.legacy_pricing_plan is None  # starts NULL

            ret = await mark_user_legacy(
                db,
                user.id,
                plan="legacy_99_yearly",
                source="manual_admin",
                stripe_subscription_id="sub_test_abc123",
                notes="Unit test fixture",
            )
            await db.commit()

            assert ret["action"] == "created"
            assert ret["plan"] == "legacy_99_yearly"

            # Reload to confirm column was persisted
            await db.refresh(user)
            assert user.legacy_pricing_plan == "legacy_99_yearly"

            # Audit row must exist
            audit_rows = await get_legacy_audit_trail(db, user.id)
            assert len(audit_rows) == 1
            row = audit_rows[0]
            assert row.plan == "legacy_99_yearly"
            assert row.source == "manual_admin"
            assert row.stripe_subscription_id == "sub_test_abc123"
            assert row.notes == "Unit test fixture"
    finally:
        await engine.dispose()
        await _delete_user(email)


@pytest.mark.asyncio
async def test_mark_user_legacy_is_idempotent_for_same_input():
    """
    Calling mark_user_legacy twice with the same plan → no-op on second call,
    only ONE audit row is written (not two).
    """
    email = "test_2_16_2_b@comcoi-test.fr"
    await _delete_user(email)

    async with _api_client() as client:
        await _register_login(client, email)

    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one()

            r1 = await mark_user_legacy(db, user.id, "legacy_bic_63_monthly", "bubble_migration")
            await db.commit()
            assert r1["action"] == "created"

            r2 = await mark_user_legacy(db, user.id, "legacy_bic_63_monthly", "bubble_migration")
            await db.commit()
            assert r2["action"] == "noop"

            # Only one audit row
            audit_rows = await get_legacy_audit_trail(db, user.id)
            assert len(audit_rows) == 1
    finally:
        await engine.dispose()
        await _delete_user(email)


@pytest.mark.asyncio
async def test_mark_user_legacy_writes_new_audit_when_plan_changes():
    """
    Changing the plan (admin correction) writes a second audit row
    but leaves the first one in place for history.
    """
    email = "test_2_16_2_c@comcoi-test.fr"
    await _delete_user(email)

    async with _api_client() as client:
        await _register_login(client, email)

    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one()

            r1 = await mark_user_legacy(db, user.id, "legacy_bic_63_monthly", "bubble_migration")
            await db.commit()
            assert r1["action"] == "created"

            r2 = await mark_user_legacy(
                db, user.id, "legacy_bic_plus_93_monthly", "manual_admin",
                notes="Admin correction",
            )
            await db.commit()
            assert r2["action"] == "updated"

            # Two audit rows — original + correction
            audit_rows = await get_legacy_audit_trail(db, user.id)
            assert len(audit_rows) == 2
            assert audit_rows[0].source == "bubble_migration"
            assert audit_rows[0].plan == "legacy_bic_63_monthly"
            assert audit_rows[1].source == "manual_admin"
            assert audit_rows[1].plan == "legacy_bic_plus_93_monthly"

            # Column reflects the LATEST plan
            await db.refresh(user)
            assert user.legacy_pricing_plan == "legacy_bic_plus_93_monthly"
    finally:
        await engine.dispose()
        await _delete_user(email)


@pytest.mark.asyncio
async def test_is_legacy_helper():
    """
    is_legacy() returns True if legacy_pricing_plan is set, False if NULL.
    Pure function — no DB calls.
    """
    user_null = User()
    user_null.legacy_pricing_plan = None
    assert is_legacy(user_null) is False

    user_flagged = User()
    user_flagged.legacy_pricing_plan = "legacy_99_yearly"
    assert is_legacy(user_flagged) is True


@pytest.mark.asyncio
async def test_mark_user_legacy_rejects_invalid_plan():
    """mark_user_legacy raises ValueError for an unknown plan string."""
    email = "test_2_16_2_d@comcoi-test.fr"
    await _delete_user(email)

    async with _api_client() as client:
        await _register_login(client, email)

    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one()

            with pytest.raises(ValueError, match="Unknown legacy plan"):
                await mark_user_legacy(db, user.id, "not_a_real_plan", "manual_admin")
    finally:
        await engine.dispose()
        await _delete_user(email)


@pytest.mark.asyncio
async def test_user_me_serialises_legacy_flag():
    """
    GET /api/users/me returns the legacy_pricing_plan field.
    For a standard user it is null; for a flagged user it is the plan string.
    """
    email = "test_2_16_2_e@comcoi-test.fr"
    await _delete_user(email)

    try:
        # ── Part 1: standard user → field present and null ─────────────────
        async with _api_client() as client:
            await _register_login(client, email)
            me_resp = await client.get("/api/users/me")
            assert me_resp.status_code == 200
            data = me_resp.json()
            assert "legacy_pricing_plan" in data
            assert data["legacy_pricing_plan"] is None

        # ── Part 2: flag the user, re-login, check the field ───────────────
        engine = create_async_engine(settings.database_url, echo=False)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one()
            await mark_user_legacy(db, user.id, "legacy_99_yearly", "cutover_backfill")
            await db.commit()
        await engine.dispose()

        async with _api_client() as client:
            await _register_login(client, email)
            me_resp = await client.get("/api/users/me")
            assert me_resp.status_code == 200
            data = me_resp.json()
            assert data["legacy_pricing_plan"] == "legacy_99_yearly"

    finally:
        await _delete_user(email)
