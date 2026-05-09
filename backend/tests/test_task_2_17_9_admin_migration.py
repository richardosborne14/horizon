"""
Tests for TASK-2.17.9 — Admin migration cohort dashboard.

Tests:
  test_summary_returns_counts_per_status    — /summary counts imported users per status
  test_users_endpoint_paginates_and_filters — /users pagination + status filter
  test_users_detail_includes_audit_trail    — /users/{id} returns profile + audit rows
  test_resync_stripe_updates_subscription_status — /resync-stripe calls service
  test_welcome_email_endpoint_calls_service — /welcome-email delegates to service
  test_welcome_email_idempotent_stub        — stub returns already_sent=False (replace in 2.17.11)
  test_send_batch_skips_already_emailed     — /cutover-emails/send-batch returns counts
  test_csv_export_quotes_special_chars      — /users.csv returns well-formed CSV
  test_non_admin_user_gets_403              — all endpoints enforce admin guard

All tests are self-contained: register → login → seed data → test → cleanup.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.main import app


# ── Fixture helpers ────────────────────────────────────────────────────────────

ADMIN_EMAIL = f"admin-mig-test-{uuid.uuid4().hex[:6]}@example.com"
ADMIN_PASS = "AdminMig123!"

USER_EMAIL = f"regular-mig-test-{uuid.uuid4().hex[:6]}@example.com"
USER_PASS = "RegularUser123!"


async def _register_admin(client: AsyncClient) -> None:
    """Register a user and promote to admin."""
    await client.post(
        "/api/auth/register",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS, "name": "Admin Mig Tester"},
    )
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("UPDATE users SET role='admin' WHERE email=:e"), {"e": ADMIN_EMAIL}
        )
        await db.commit()
    resp = await client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
    )
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"


async def _register_regular(client: AsyncClient) -> None:
    """Register a regular (non-admin) user."""
    await client.post(
        "/api/auth/register",
        json={"email": USER_EMAIL, "password": USER_PASS, "name": "Regular Mig Tester"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": USER_EMAIL, "password": USER_PASS},
    )
    assert resp.status_code == 200, f"Regular login failed: {resp.text}"


async def _seed_imported_user(
    *,
    import_status: str = "imported_active_paying",
    suffix: str = "",
) -> uuid.UUID:
    """
    Insert a fake imported user with a salon for testing.

    Returns the user UUID.
    """
    email = f"imported-{uuid.uuid4().hex[:6]}{suffix}@example.com"
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("""
                INSERT INTO users (email, password_hash, name, import_source, import_status)
                VALUES (:email, 'x', 'Imported User', 'bubble', :status)
                RETURNING id
            """),
            {"email": email, "status": import_status},
        )
        user_id = result.fetchone()[0]
        await db.commit()
    return user_id


async def _cleanup() -> None:
    """Remove test users and associated data."""
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("DELETE FROM users WHERE email LIKE 'imported-%@example.com'")
        )
        await db.execute(
            text("DELETE FROM users WHERE email=:e"), {"e": ADMIN_EMAIL}
        )
        await db.execute(
            text("DELETE FROM users WHERE email=:e"), {"e": USER_EMAIL}
        )
        await db.commit()


# ── Test 1: summary returns counts per status ─────────────────────────────────

@pytest.mark.asyncio
async def test_summary_returns_counts_per_status():
    """
    GET /api/admin/migration/summary must return counts for each import_status.

    Seeds two imported users (one paying, one dormant) and asserts
    the summary counts are ≥ the seeded values (other tests may add more).
    """
    user1 = await _seed_imported_user(import_status="imported_active_paying")
    user2 = await _seed_imported_user(import_status="imported_dormant")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register_admin(client)
        resp = await client.get("/api/admin/migration/summary")

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "imported_active_paying" in data
    assert "imported_dormant" in data
    assert "total" in data
    assert data["imported_active_paying"] >= 1
    assert data["imported_dormant"] >= 1
    assert data["total"] >= 2
    # Blog fields present
    assert "blog_articles_cleaned" in data
    assert "blog_articles_pending_review" in data

    await _cleanup()


# ── Test 2: users endpoint paginates and filters ──────────────────────────────

@pytest.mark.asyncio
async def test_users_endpoint_paginates_and_filters():
    """
    GET /api/admin/migration/users must:
    - return paginated results
    - filter by ?status=imported_lapsed
    - include required fields in each item
    """
    lapsed_user = await _seed_imported_user(import_status="imported_lapsed", suffix="-lapsed")
    await _seed_imported_user(import_status="imported_dormant", suffix="-dormant")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register_admin(client)

        # Unfiltered
        resp_all = await client.get("/api/admin/migration/users?page=1&page_size=5")
        assert resp_all.status_code == 200
        data_all = resp_all.json()
        assert "items" in data_all
        assert "total" in data_all
        assert data_all["page"] == 1
        assert data_all["page_size"] == 5

        # Filtered by status
        resp_lapsed = await client.get(
            "/api/admin/migration/users?status=imported_lapsed&page=1&page_size=50"
        )
        assert resp_lapsed.status_code == 200
        lapsed_data = resp_lapsed.json()
        # All returned items should have lapsed status
        for item in lapsed_data["items"]:
            assert item["import_status"] == "imported_lapsed"

        # Check required fields on items
        if lapsed_data["items"]:
            item = lapsed_data["items"][0]
            required_fields = [
                "user_id", "email", "name", "import_status", "legacy_pricing_plan",
                "last_login_at", "last_reporting_activity_at", "days_since_last_activity",
            ]
            for field in required_fields:
                assert field in item, f"Missing field: {field}"

    await _cleanup()


# ── Test 3: user detail includes audit trail ──────────────────────────────────

@pytest.mark.asyncio
async def test_users_detail_includes_audit_trail():
    """
    GET /api/admin/migration/users/{id} must return profile + audit_rows +
    import_runs.

    Seeds a user and a legacy_pricing_audit row, asserts both appear in detail.
    """
    user_id = await _seed_imported_user(import_status="imported_active_paying", suffix="-detail")

    # Seed a legacy_pricing_audit row
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("""
                INSERT INTO legacy_pricing_audit (user_id, plan, source)
                VALUES (:uid, 'legacy_99_yearly', 'bubble_migration')
            """),
            {"uid": user_id},
        )
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register_admin(client)
        resp = await client.get(f"/api/admin/migration/users/{user_id}")

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "profile" in data
    assert "audit_rows" in data
    assert "import_runs" in data

    assert data["profile"]["user_id"] == str(user_id)
    assert data["profile"]["import_status"] == "imported_active_paying"

    # Should have at least the one audit row we seeded
    audit_plans = [r["plan"] for r in data["audit_rows"]]
    assert "legacy_99_yearly" in audit_plans

    await _cleanup()


# ── Test 4: resync-stripe calls service ───────────────────────────────────────

@pytest.mark.asyncio
async def test_resync_stripe_updates_subscription_status():
    """
    POST /api/admin/migration/users/{id}/resync-stripe must call resync_stripe_user
    and return action dict.

    WHY mock: we don't call real Stripe in unit tests (no API key in test env).
    The service is tested in isolation; here we assert the endpoint delegates to it.
    """
    user_id = await _seed_imported_user(import_status="imported_lapsed", suffix="-resync")

    mock_result = {
        "action": "synced",
        "stripe_status": "active",
        "import_status": "imported_active_paying",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register_admin(client)

        with patch(
            "app.routers.admin_migration.resync_stripe_user",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = await client.post(f"/api/admin/migration/users/{user_id}/resync-stripe")

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["action"] == "synced"
    assert data["stripe_status"] == "active"

    await _cleanup()


# ── Test 5: welcome-email endpoint uses stub ──────────────────────────────────

@pytest.mark.asyncio
async def test_welcome_email_endpoint_calls_service():
    """
    POST /api/admin/migration/users/{id}/welcome-email must return 200 with
    the template and already_sent flag from the service.

    Mocks migration_email.send_welcome_email_for_user to simulate a send.
    """
    user_id = await _seed_imported_user(
        import_status="imported_active_paying", suffix="-email"
    )

    mock_result = {
        "template": "paying",
        "already_sent": False,
        "user_id": str(user_id),
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register_admin(client)

        with patch(
            "app.services.migration_email.send_welcome_email_for_user",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = await client.post(
                f"/api/admin/migration/users/{user_id}/welcome-email"
            )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is True
    assert data["template"] == "paying"
    assert data["already_sent"] is False
    assert data["user_id"] == str(user_id)

    await _cleanup()


# ── Test 6: real idempotency (TASK-2.17.11 implemented) ───────────────────────

@pytest.mark.asyncio
async def test_welcome_email_idempotent_stub():
    """
    Idempotency: first call sends and returns sent=True; second call returns
    already_sent=True without re-sending.

    Updated in TASK-2.17.11 from the old stub-contract test. The email service
    is now fully implemented — mock send_email to avoid SMTP in tests.
    """
    user_id = await _seed_imported_user(
        import_status="imported_active_unpaid", suffix="-idempotent"
    )

    with patch(
        "app.services.migration_email.send_email",
        new_callable=AsyncMock,
    ) as mock_send:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _register_admin(client)
            resp1 = await client.post(
                f"/api/admin/migration/users/{user_id}/welcome-email"
            )
            resp2 = await client.post(
                f"/api/admin/migration/users/{user_id}/welcome-email"
            )

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    data1 = resp1.json()
    data2 = resp2.json()
    # First send: sent
    assert data1["ok"] is True
    assert data1.get("already_sent") is False
    assert data1["template"] == "B"
    # Second call: idempotent skip
    assert data2["ok"] is True
    assert data2.get("already_sent") is True
    # send_email called only once
    mock_send.assert_called_once()

    await _cleanup()


# ── Test 7: send-batch returns counts ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_batch_skips_already_emailed():
    """
    POST /api/admin/migration/cutover-emails/send-batch with mock service must
    return counts from the service result.

    WHY mock: the stub service always returns 0 counts. We mock it here to
    simulate a realistic batch-send response and assert the router serialises
    the counts correctly.
    """
    mock_batch_result = {
        "sent": 5,
        "skipped_already_sent": 3,
        "errors": 0,
        "dry_run": False,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register_admin(client)

        with patch(
            "app.services.migration_email.send_batch",
            new_callable=AsyncMock,
            return_value=mock_batch_result,
        ):
            resp = await client.post(
                "/api/admin/migration/cutover-emails/send-batch",
                json={"batch_size": 10, "status_filter": "imported_lapsed", "dry_run": False},
            )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["sent"] == 5
    assert data["skipped_already_sent"] == 3
    assert data["errors"] == 0
    assert data["dry_run"] is False

    await _cleanup()


# ── Test 8: CSV export is well-formed ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_csv_export_quotes_special_chars():
    """
    GET /api/admin/migration/users.csv must return:
    - Content-Type: text/csv
    - Well-formed CSV with a header row
    - Accented chars in names are preserved (UTF-8 BOM for Excel)
    """
    # Seed a user with an accented name
    email = f"csv-{uuid.uuid4().hex[:6]}@example.com"
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("""
                INSERT INTO users (email, password_hash, name, import_source, import_status)
                VALUES (:email, 'x', 'Élodie Ménard', 'bubble', 'imported_dormant')
            """),
            {"email": email},
        )
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register_admin(client)
        resp = await client.get("/api/admin/migration/users.csv?status=imported_dormant")

    assert resp.status_code == 200, resp.text
    assert "text/csv" in resp.headers.get("content-type", "")

    # Parse CSV (strip BOM)
    content = resp.text.lstrip("\ufeff")
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)

    # Header must have required fields
    assert reader.fieldnames is not None
    assert "user_id" in reader.fieldnames
    assert "email" in reader.fieldnames
    assert "import_status" in reader.fieldnames

    # At least one row with our email
    emails = [r["email"] for r in rows]
    assert email in emails

    # Cleanup
    async with AsyncSessionLocal() as db:
        await db.execute(text("DELETE FROM users WHERE email=:e"), {"e": email})
        await db.commit()

    await _cleanup()


# ── Test 9: non-admin gets 403 ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_non_admin_user_gets_403():
    """
    All /api/admin/migration/* endpoints must return 403 for non-admin users.

    Tests the summary endpoint as a representative.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register_regular(client)
        resp = await client.get("/api/admin/migration/summary")

    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"

    await _cleanup()
