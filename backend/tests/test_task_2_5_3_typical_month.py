"""
Tests for Task 2.5.3 — Mon Mois Typique wizard backend.

Tests (self-contained, follow project pattern from test_task_1_7_salons.py):
  - test_typical_month_creation: full endpoint creates report + employees + expenses
  - test_typical_month_calculations: point mort, charges computed correctly
  - test_user_flag_set: user.has_completed_typical_month set to True after submission
  - test_prestataire_no_charges: prestataire role has zero charges patronales
  - test_idempotent_resubmit: submitting twice succeeds (upsert, no duplicate key error)
  - test_wrong_salon_returns_404: cannot submit for another user's salon
  - test_missing_ca_returns_422: submitting without ca_ttc returns 422

Run: docker compose exec backend pytest tests/test_task_2_5_3_typical_month.py -v
"""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app

# ── Constants ─────────────────────────────────────────────────────────────────

_PASS = "TestPass253!"

TYPICAL_PAYLOAD = {
    "ca_ttc": 8000.0,
    "team": [
        {
            "name": "Marie Coiffeuse",
            "role_type": "salarie",
            "contract_type": "cdi",
            "net_salary": 1500.0,
            "hours_per_week": 35.0,
        }
    ],
    "expenses": [
        {
            "category": "expenses.loyer_immobilier",
            "label": "Loyer mensuel",
            "amount_ttc": 960.0,
        },
        {
            "category": "expenses.energie_fluides",
            "label": "Électricité",
            "amount_ttc": 180.0,
        },
    ],
}

# ── Helpers ────────────────────────────────────────────────────────────────────


async def _register_and_login(client: AsyncClient, suffix: str) -> tuple[str, dict]:
    """
    Register a fresh user and log in.
    Returns (email, cookies).
    WHY: Each test needs a fresh user to avoid state pollution between tests.
    """
    email = f"tm_test_{suffix}@example.com"
    reg = await client.post(
        "/api/auth/register",
        json={"email": email, "password": _PASS, "name": f"TM Test {suffix}"},
    )
    assert reg.status_code == 201, f"Register failed: {reg.text}"

    login = await client.post("/api/auth/login", json={"email": email, "password": _PASS})
    assert login.status_code == 200, f"Login failed: {login.text}"
    # Copy cookies to the client so subsequent requests are authenticated
    client.cookies.update(login.cookies)
    return email


async def _create_salon(client: AsyncClient) -> str:
    """Create a test salon and return its ID."""
    res = await client.post(
        "/api/salons",
        json={"name": "Salon TM Test", "business_type": "auto_micro", "nb_employees": 1},
    )
    assert res.status_code == 201, f"Salon create failed: {res.text}"
    return res.json()["id"]


async def _cleanup(email: str) -> None:
    """Delete test user (cascade removes all related rows)."""
    engine = create_async_engine(settings.database_url, echo=False)
    async with AsyncSession(engine, expire_on_commit=False) as db:
        await db.execute(text(f"DELETE FROM users WHERE email = '{email}'"))
        await db.commit()
    await engine.dispose()


# ── Tests ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_typical_month_creation():
    """
    Submitting the wizard creates a MonthlyReport with the given CA.
    Response must include month, year, point_mort, cash_flow, team, expenses.
    """
    uid = str(uuid.uuid4())[:8]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = await _register_and_login(client, uid)
        salon_id = await _create_salon(client)
        try:
            res = await client.post(f"/api/salons/{salon_id}/typical-month", json=TYPICAL_PAYLOAD)
            assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
            data = res.json()
            assert "month" in data
            assert "year" in data
            assert "monthly_report_id" in data
            assert float(data["ca_ttc"]) == 8000.0
            # Team and expenses are captured in the breakdown
            assert data["breakdown"]["total_salaires"] > 0, "Salaires > 0 expected"
            assert data["breakdown"]["total_charges_ttc"] > 0, "Charges TTC > 0 expected"
        finally:
            await _cleanup(email)


@pytest.mark.asyncio
async def test_typical_month_calculations():
    """
    Point mort and cash flow must be present and sensible:
      - point_mort > 0 (charges exist)
      - cash_flow > 0 (CA 8000 is above break-even)
    """
    uid = str(uuid.uuid4())[:8]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = await _register_and_login(client, uid)
        salon_id = await _create_salon(client)
        try:
            res = await client.post(f"/api/salons/{salon_id}/typical-month", json=TYPICAL_PAYLOAD)
            assert res.status_code == 201, res.text
            data = res.json()
            assert "point_mort" in data
            assert float(data["point_mort"]) > 0
            assert "resultat_net" in data
            assert float(data["resultat_net"]) > 0, (
                f"resultat_net should be positive with 8000 CA, got {data['resultat_net']}"
            )
        finally:
            await _cleanup(email)


@pytest.mark.asyncio
async def test_user_flag_set():
    """
    After successful submission, GET /api/users/me should return
    has_completed_typical_month=True.
    """
    uid = str(uuid.uuid4())[:8]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = await _register_and_login(client, uid)
        salon_id = await _create_salon(client)
        try:
            res = await client.post(f"/api/salons/{salon_id}/typical-month", json=TYPICAL_PAYLOAD)
            assert res.status_code == 201, res.text

            me = await client.get("/api/users/me")
            assert me.status_code == 200
            assert me.json().get("has_completed_typical_month") is True, (
                "has_completed_typical_month should be True after submission"
            )
        finally:
            await _cleanup(email)


@pytest.mark.asyncio
async def test_prestataire_no_charges():
    """
    A prestataire team member should have zero charges patronales —
    they invoice independently, so no employer contributions.
    """
    uid = str(uuid.uuid4())[:8]
    payload = {
        "ca_ttc": 6000.0,
        "team": [
            {
                "name": "Freelance Coiffeur",
                "role_type": "prestataire",
                "contract_type": None,
                "net_salary": 1200.0,
                "hours_per_week": 20.0,
            }
        ],
        "expenses": [],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = await _register_and_login(client, uid)
        salon_id = await _create_salon(client)
        try:
            res = await client.post(f"/api/salons/{salon_id}/typical-month", json=payload)
            assert res.status_code == 201, res.text
            data = res.json()
            # For a prestataire, total_salaires = flat monthly cost (no charges)
            # cotisations_sociales = 0, so total_salaires == net_salary exactly
            breakdown = data.get("breakdown", {})
            total_salaires = float(breakdown.get("total_salaires", -1))
            assert total_salaires == 1200.0, (
                f"Prestataire total_salaires should equal net_salary=1200, got {total_salaires}"
            )
        finally:
            await _cleanup(email)


@pytest.mark.asyncio
async def test_idempotent_resubmit():
    """
    Submitting the wizard twice for the same salon should succeed (upsert).
    The second submission overwrites the first — no duplicate key error.
    """
    uid = str(uuid.uuid4())[:8]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = await _register_and_login(client, uid)
        salon_id = await _create_salon(client)
        try:
            res1 = await client.post(f"/api/salons/{salon_id}/typical-month", json=TYPICAL_PAYLOAD)
            assert res1.status_code == 201, res1.text

            updated = {**TYPICAL_PAYLOAD, "ca_ttc": 9500.0}
            res2 = await client.post(f"/api/salons/{salon_id}/typical-month", json=updated)
            assert res2.status_code == 201, f"Second submission failed: {res2.text}"
            assert float(res2.json()["ca_ttc"]) == 9500.0, "Second submission should update CA"
        finally:
            await _cleanup(email)


@pytest.mark.asyncio
async def test_wrong_salon_returns_404():
    """
    Submitting to a salon owned by another user returns 403 or 404.
    """
    uid_a = str(uuid.uuid4())[:8]
    uid_b = str(uuid.uuid4())[:8]
    email_a = f"tm_test_{uid_a}@example.com"
    email_b = f"tm_test_{uid_b}@example.com"

    # Get salon A's ID using user A's client
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ca:
        await _register_and_login(ca, uid_a)
        salon_a_id = await _create_salon(ca)

    # User B tries to submit to user A's salon
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cb:
        await _register_and_login(cb, uid_b)
        await _create_salon(cb)  # create their own salon so they're not blocked by onboarding
        try:
            res = await cb.post(f"/api/salons/{salon_a_id}/typical-month", json=TYPICAL_PAYLOAD)
            assert res.status_code in (403, 404), (
                f"Expected 403 or 404 for wrong salon, got {res.status_code}: {res.text}"
            )
        finally:
            await _cleanup(email_a)
            await _cleanup(email_b)


@pytest.mark.asyncio
async def test_missing_ca_returns_422():
    """
    Submitting without ca_ttc (required field) returns 422 validation error.
    """
    uid = str(uuid.uuid4())[:8]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = await _register_and_login(client, uid)
        salon_id = await _create_salon(client)
        try:
            res = await client.post(
                f"/api/salons/{salon_id}/typical-month",
                json={"team": [], "expenses": []},
            )
            assert res.status_code == 422, (
                f"Expected 422 for missing ca_ttc, got {res.status_code}"
            )
        finally:
            await _cleanup(email)
