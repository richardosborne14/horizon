"""
Tests for Task 2.5.6 — Year Pre-Population from Typical Month Template.

POST /api/salons/{salon_id}/years/{year}/generate-from-template

Self-contained pattern (no conftest fixtures). Each test creates its own
user → salon → template via the actual FastAPI app (ASGITransport).

Scenarios:
  - 400 if salon has no template
  - Creates 12 months when year is empty
  - Skips existing months (idempotent: second call → months_created=0)
  - 404 for non-existent salon
"""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app

# ── Constants ──────────────────────────────────────────────────────────────────

_PASS = "TestPass256!"
YEAR = 2099  # Far-future year to avoid clashes with real data

TYPICAL_PAYLOAD = {
    "ca_ttc": 15000.0,
    "team": [
        {
            "name": "Alice Template",
            "role_type": "employe",
            "contract_type": "cdi",
            "net_salary": 1600.0,
            "hours_per_week": 35.0,
        }
    ],
    "expenses": [
        {
            "category": "expenses.loyer_immobilier",
            "label": "Loyer",
            "amount_ttc": 1200.0,
        }
    ],
}

# ── Helpers ────────────────────────────────────────────────────────────────────


async def _register_and_login(client: AsyncClient, suffix: str) -> str:
    """Register a fresh user, log in, and return the email."""
    email = f"ypop_{suffix}@example.com"
    reg = await client.post(
        "/api/auth/register",
        json={"email": email, "password": _PASS, "name": f"YPop Test {suffix}"},
    )
    assert reg.status_code == 201, f"Register failed: {reg.text}"

    login = await client.post("/api/auth/login", json={"email": email, "password": _PASS})
    assert login.status_code == 200, f"Login failed: {login.text}"
    client.cookies.update(login.cookies)
    return email


async def _create_salon(client: AsyncClient) -> str:
    """Create a test salon and return its ID."""
    res = await client.post(
        "/api/salons",
        json={"name": "Salon YPop Test", "business_type": "auto_micro", "nb_employees": 1},
    )
    assert res.status_code == 201, f"Salon create failed: {res.text}"
    return res.json()["id"]


async def _setup_template(client: AsyncClient, salon_id: str) -> None:
    """Run the Mon Mois Typique wizard to create a template in salon_config."""
    resp = await client.post(
        f"/api/salons/{salon_id}/typical-month",
        json=TYPICAL_PAYLOAD,
    )
    assert resp.status_code in (200, 201), f"Wizard failed: {resp.text}"


async def _cleanup(email: str) -> None:
    """Delete the test user (cascade removes all related data)."""
    engine = create_async_engine(settings.database_url, echo=False)
    async with AsyncSession(engine, expire_on_commit=False) as db:
        await db.execute(text(f"DELETE FROM users WHERE email = '{email}'"))
        await db.commit()
    await engine.dispose()


def _gen_url(salon_id: str) -> str:
    return f"/api/salons/{salon_id}/years/{YEAR}/generate-from-template"


# ── Tests ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_returns_400_when_no_template() -> None:
    """
    If the salon has no typical_month_template, the endpoint returns 400.
    We cannot pre-populate months without a template to copy from.
    """
    uid = str(uuid.uuid4())[:8]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = await _register_and_login(client, uid)
        salon_id = await _create_salon(client)
        try:
            resp = await client.post(_gen_url(salon_id))
            assert resp.status_code == 400
            assert "mois typique" in resp.json()["detail"].lower()
        finally:
            await _cleanup(email)


@pytest.mark.asyncio
async def test_generate_creates_12_months() -> None:
    """
    After setting up the template, generating a year should create 12 months.
    Each month must have a unique month number (1-12) and a valid UUID.
    """
    uid = str(uuid.uuid4())[:8]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = await _register_and_login(client, uid)
        salon_id = await _create_salon(client)
        try:
            await _setup_template(client, salon_id)

            resp = await client.post(_gen_url(salon_id))
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

            data = resp.json()
            assert data["year"] == YEAR
            assert data["months_created"] == 12
            assert len(data["reports"]) == 12

            # All 12 months represented exactly once
            months = {r["month"] for r in data["reports"]}
            assert months == set(range(1, 13))

            # Each report has a valid non-empty id
            for r in data["reports"]:
                assert r["id"], "Report id must not be empty"
        finally:
            await _cleanup(email)


@pytest.mark.asyncio
async def test_generate_skips_existing_months() -> None:
    """
    Running generate a second time when all months exist returns months_created=0.
    This tests the idempotency guarantee (never overwrite existing data).
    """
    uid = str(uuid.uuid4())[:8]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = await _register_and_login(client, uid)
        salon_id = await _create_salon(client)
        try:
            await _setup_template(client, salon_id)

            # First call: creates all 12 months
            resp1 = await client.post(_gen_url(salon_id))
            assert resp1.status_code == 200
            assert resp1.json()["months_created"] == 12

            # Second call: all months already exist — nothing created
            resp2 = await client.post(_gen_url(salon_id))
            assert resp2.status_code == 200
            data2 = resp2.json()
            assert data2["months_created"] == 0
            assert data2["reports"] == []
        finally:
            await _cleanup(email)


@pytest.mark.asyncio
async def test_generate_returns_404_for_nonexistent_salon() -> None:
    """
    Requesting year generation for a non-existent salon returns 404.
    We never reveal whether a foreign salon exists.
    """
    uid = str(uuid.uuid4())[:8]
    fake_salon_id = "00000000-0000-0000-0000-000000000000"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register_and_login(client, uid)
        try:
            resp = await client.post(
                f"/api/salons/{fake_salon_id}/years/{YEAR}/generate-from-template"
            )
            assert resp.status_code == 404
        finally:
            await _cleanup(f"ypop_{uid}@example.com")
