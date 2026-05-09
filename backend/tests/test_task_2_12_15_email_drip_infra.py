"""
Tests for TASK-2.12.15 — Email drip infrastructure.

Coverage:
  - Unsubscribed user excluded from cohort (find_candidates)
  - Imported user excluded from cohort
  - Idempotency: already-sent state blocks re-dispatch
  - Dry-run writes dispatch row but does NOT call SMTP
  - Unsubscribe token round-trip (sign → verify)
  - Unsubscribe endpoint stamps unsubscribed_at + idempotent
  - Unsubscribe endpoint rejects invalid tokens
  - Email-preferences toggle (enable/disable)
  - Unsubscribe does NOT affect transactional email (payslip) flow

Uses the codebase-standard self-contained pattern:
  register → login → test → delete user
No shared fixtures — each test is fully independent.
"""

from __future__ import annotations

import uuid
import pytest
import inspect

from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.config import settings
from app.models.user import User
from app.models.email_dispatch import EmailDispatch
from app.services.email_drip.unsubscribe_token import generate_token, verify_token
from app.services.email_drip.registry import register, get, _REGISTRY


# ── Helpers ───────────────────────────────────────────────────────────────────


def _client() -> AsyncClient:
    """Return a fresh ASGI test client (unauthenticated)."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _register_login(client: AsyncClient, email: str) -> None:
    """Register and log in a user via the API."""
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "name": "Drip Test User"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"


async def _get_user(email: str) -> User | None:
    """Fetch a user from DB by email."""
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
    await engine.dispose()
    return user


async def _delete_user(email: str) -> None:
    """Delete test user by email (cascade removes related rows)."""
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            await db.delete(user)
            await db.commit()
    await engine.dispose()


# ── Token tests (pure unit — no DB) ──────────────────────────────────────────


def test_unsubscribe_token_round_trip():
    """generate_token → verify_token must return the original (user_id, dispatch_id)."""
    user_id = uuid.uuid4()
    dispatch_id = uuid.uuid4()
    token = generate_token(user_id, dispatch_id)
    result_user, result_dispatch = verify_token(token)
    assert result_user == user_id
    assert result_dispatch == dispatch_id


def test_unsubscribe_token_tamper_detection():
    """A modified token must be rejected with ValueError."""
    user_id = uuid.uuid4()
    dispatch_id = uuid.uuid4()
    token = generate_token(user_id, dispatch_id)
    bad_token = token[:-3] + "XXX"
    with pytest.raises(ValueError):
        verify_token(bad_token)


def test_unsubscribe_token_malformed():
    """A random string must be rejected cleanly with ValueError."""
    with pytest.raises(ValueError):
        verify_token("not-a-valid-token-at-all")


# ── Registry tests (pure unit) ────────────────────────────────────────────────


def test_registry_register_and_retrieve():
    """A registered template must be retrievable via get()."""
    from app.services.email_drip.registry import RenderedEmail

    def fake_cohort(user):
        return True

    def fake_render(user, salon):
        return RenderedEmail(subject="S", html_body="H", text_body="T")

    register("_test_2_12_15", {"days_after_signup": 0}, fake_cohort, fake_render)
    tpl = get("_test_2_12_15")
    assert tpl is not None
    assert tpl.template_id == "_test_2_12_15"

    # Clean up to avoid polluting other tests
    _REGISTRY.pop("_test_2_12_15", None)


# ── find_candidates tests (DB) ────────────────────────────────────────────────


@pytest.mark.anyio
async def test_unsubscribed_user_excluded_from_cohort():
    """A user with unsubscribed_at set must not appear as a candidate."""
    from app.services.email_drip.dispatcher import find_candidates

    email = "drip_unsub_test@comcoi-test.fr"
    await _delete_user(email)

    async with _client() as client:
        await _register_login(client, email)

    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one()
            user.unsubscribed_at = datetime.now(timezone.utc)
            await db.commit()

            candidates = await find_candidates("welcome", lambda u: True, db)
            candidate_ids = [c.id for c in candidates]
            assert user.id not in candidate_ids
    finally:
        await _delete_user(email)
        await engine.dispose()


@pytest.mark.anyio
async def test_imported_user_excluded_from_cohort():
    """A user with import_status='imported_active_paying' must be excluded."""
    from app.services.email_drip.dispatcher import find_candidates

    email = "drip_imported_test@comcoi-test.fr"
    await _delete_user(email)

    async with _client() as client:
        await _register_login(client, email)

    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one()
            user.import_status = "imported_active_paying"
            await db.commit()

            candidates = await find_candidates("welcome", lambda u: True, db)
            candidate_ids = [c.id for c in candidates]
            assert user.id not in candidate_ids
    finally:
        await _delete_user(email)
        await engine.dispose()


@pytest.mark.anyio
async def test_idempotent_send_does_not_redispatch():
    """User already in email_drip_state['welcome'] must not be reselected."""
    from app.services.email_drip.dispatcher import find_candidates

    email = "drip_idem_test@comcoi-test.fr"
    await _delete_user(email)

    async with _client() as client:
        await _register_login(client, email)

    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one()
            user.email_drip_state = {"welcome": {"sent_at": "2026-05-05T09:00:00+00:00"}}
            await db.commit()

            candidates = await find_candidates("welcome", lambda u: True, db)
            candidate_ids = [c.id for c in candidates]
            assert user.id not in candidate_ids
    finally:
        await _delete_user(email)
        await engine.dispose()


# ── Dry-run dispatch test (DB) ────────────────────────────────────────────────


@pytest.mark.anyio
async def test_dry_run_writes_dispatch_row_but_does_not_send():
    """
    With dry_run=True:
      - An email_dispatches row with status='sent' must be created.
      - send_email must NOT be called.

    WHY mock find_candidates: cohort selection is already covered by 3 dedicated
    tests above. Here we only want to test the dry-run path of send_for_template
    (no SMTP, dispatch row written). Patching find_candidates avoids session
    identity-map complexity when reusing the same AsyncSession for setup + test.
    """
    from app.services.email_drip.dispatcher import send_for_template
    from app.services.email_drip.registry import RenderedEmail

    email = "drip_dryrun_test@comcoi-test.fr"
    await _delete_user(email)

    async with _client() as client:
        await _register_login(client, email)

    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            user = (await db.execute(
                select(User).where(User.email == email)
            )).scalar_one()
            user_id = user.id

            def simple_render(u, salon):
                return RenderedEmail(
                    subject="Test",
                    html_body="<p>Hello {{UNSUBSCRIBE_URL}}</p>",
                    text_body="Hello {{UNSUBSCRIBE_URL}}",
                )

            # Patch find_candidates to return only our test user so we can
            # test the dry-run path without session identity-map complexity.
            with (
                patch("app.services.email_drip.dispatcher.find_candidates", return_value=[user]),
                patch("app.services.email_drip.dispatcher.send_email") as mock_send,
            ):
                result = await send_for_template(
                    "_dryrun_2_12_15",
                    lambda u: True,  # cohort_fn not called when find_candidates is mocked
                    simple_render,
                    db,
                    dry_run=True,
                )

            mock_send.assert_not_called()
            assert result["sent"] == 1

            # Verify dispatch row was written
            dispatch = (await db.execute(
                select(EmailDispatch).where(
                    EmailDispatch.user_id == user_id,
                    EmailDispatch.template_id == "_dryrun_2_12_15",
                )
            )).scalar_one_or_none()
            assert dispatch is not None
            assert dispatch.status == "sent"
    finally:
        await _delete_user(email)
        await engine.dispose()


# ── Unsubscribe endpoint tests (HTTP) ─────────────────────────────────────────


@pytest.mark.anyio
async def test_unsubscribe_endpoint_stamps_user():
    """GET /api/unsubscribe?token=... must return success and stamp the user."""
    email = "drip_unsub_ep_test@comcoi-test.fr"
    await _delete_user(email)

    async with _client() as client:
        await _register_login(client, email)

    user = await _get_user(email)
    assert user is not None

    try:
        dispatch_id = uuid.uuid4()
        token = generate_token(user.id, dispatch_id)

        async with _client() as client:
            resp = await client.get(f"/api/unsubscribe?token={token}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

        # Verify unsubscribed_at was stamped
        updated_user = await _get_user(email)
        assert updated_user.unsubscribed_at is not None
    finally:
        await _delete_user(email)


@pytest.mark.anyio
async def test_unsubscribe_endpoint_idempotent():
    """Calling the endpoint twice must succeed both times (no error)."""
    email = "drip_unsub_idem_test@comcoi-test.fr"
    await _delete_user(email)

    async with _client() as client:
        await _register_login(client, email)

    user = await _get_user(email)
    assert user is not None

    try:
        dispatch_id = uuid.uuid4()
        token = generate_token(user.id, dispatch_id)

        async with _client() as client:
            r1 = await client.get(f"/api/unsubscribe?token={token}")
            r2 = await client.get(f"/api/unsubscribe?token={token}")

        assert r1.status_code == 200
        assert r2.status_code == 200
    finally:
        await _delete_user(email)


@pytest.mark.anyio
async def test_unsubscribe_endpoint_rejects_bad_token():
    """An invalid token must return 400."""
    async with _client() as client:
        resp = await client.get("/api/unsubscribe?token=this-is-totally-invalid")
    assert resp.status_code == 400


# ── Email-preferences toggle (HTTP) ──────────────────────────────────────────


@pytest.mark.anyio
async def test_email_preferences_disable():
    """PATCH /api/users/me/email-preferences {drip_emails_enabled: false} must unsubscribe."""
    email = "drip_prefs_disable@comcoi-test.fr"
    await _delete_user(email)
    try:
        async with _client() as client:
            await _register_login(client, email)
            resp = await client.patch(
                "/api/users/me/email-preferences",
                json={"drip_emails_enabled": False},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["drip_emails_enabled"] is False
    finally:
        await _delete_user(email)


@pytest.mark.anyio
async def test_email_preferences_enable_after_disable():
    """PATCH with drip_emails_enabled=true after disable must clear unsubscribed_at."""
    email = "drip_prefs_enable@comcoi-test.fr"
    await _delete_user(email)
    try:
        async with _client() as client:
            await _register_login(client, email)
            await client.patch(
                "/api/users/me/email-preferences",
                json={"drip_emails_enabled": False},
            )
            resp = await client.patch(
                "/api/users/me/email-preferences",
                json={"drip_emails_enabled": True},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["drip_emails_enabled"] is True
    finally:
        await _delete_user(email)


# ── Transactional email separation (design test) ──────────────────────────────


def test_unsubscribe_does_not_disable_payslip_notifications():
    """
    send_email (core/email.py) must NOT reference unsubscribed_at.

    WHY a design test: transactional emails (payslip-ready, password reset)
    must always send regardless of drip opt-out. The separation is enforced
    by convention — this test locks it in so it can't be accidentally broken.
    """
    import app.core.email as email_mod
    src = inspect.getsource(email_mod)
    assert "unsubscribed_at" not in src, (
        "app.core.email.send_email must never check unsubscribed_at — "
        "transactional emails must always send regardless of drip opt-out. "
        "Only the drip dispatcher checks unsubscribed_at."
    )
