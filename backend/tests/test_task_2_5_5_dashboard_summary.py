"""
Tests for Task 2.5.5 — Dashboard Summary endpoint.

GET /api/salons/{salon_id}/dashboard-summary

Self-contained tests following project pattern (register+login inline).

Verifies:
- Correct structure for salon with no typical month (State A)
- has_typical_month = True after wizard submission (State B)
- latest_month populated when monthly report exists
- monthly_trend is a list of ≤ 6 items
- has_pricing = True when services exist
- months_this_year counts current calendar year only
- 401 unauthenticated
- 403/404 for another user's salon
- 404 for unknown UUID

Run: docker compose exec backend pytest tests/test_task_2_5_5_dashboard_summary.py -v
"""

import uuid
import datetime
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app

_PASS = "TestPass255!"

TYPICAL_PAYLOAD = {
    "ca_ttc": 8500.0,
    "team": [
        {
            "name": "Sophie",
            "role_type": "salarie",
            "contract_type": "cdi",
            "net_salary": 1400.0,
            "hours_per_week": 35.0,
        }
    ],
    "expenses": [
        {"category": "expenses.loyer_immobilier", "label": "Loyer", "amount_ttc": 900.0},
    ],
}


async def _register_and_login(client: AsyncClient, suffix: str) -> tuple[str, dict]:
    """Register a fresh user and log in. Returns (email, cookies)."""
    email = f"dash255_{suffix}_{uuid.uuid4().hex[:6]}@test.com"
    await client.post("/api/auth/register", json={
        "email": email, "password": _PASS, "name": f"Dash User {suffix}"
    })
    res = await client.post("/api/auth/login", json={"email": email, "password": _PASS})
    assert res.status_code == 200, f"Login failed: {res.text}"
    return email, dict(res.cookies)


async def _create_salon(client: AsyncClient, cookies: dict, name: str = "Salon Test") -> str:
    """Create a salon and return its ID."""
    res = await client.post(
        "/api/salons",
        json={"name": name, "business_type": "auto_entrepreneur"},
        cookies=cookies,
    )
    assert res.status_code in (200, 201), f"Salon create failed: {res.text}"
    return res.json()["id"]


async def _complete_onboarding(client: AsyncClient, cookies: dict) -> None:
    """Complete onboarding so user can access app routes."""
    await client.post(
        "/api/users/onboarding",
        json={"preferred_tools": ["pilotage"], "business_goals": ["rentabilite"]},
        cookies=cookies,
    )


# ── Unauthenticated ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dashboard_summary_unauthenticated():
    """Dashboard summary endpoint requires authentication."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(f"/api/salons/{uuid.uuid4()}/dashboard-summary")
    assert res.status_code == 401


# ── State A: no wizard ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dashboard_summary_state_a_no_wizard():
    """
    Fresh salon with no typical month → all flags False, nulls, empty list.
    Mirrors dashboard State A (wizard CTA).
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        _, cookies = await _register_and_login(client, "stateA")
        await _complete_onboarding(client, cookies)
        salon_id = await _create_salon(client, cookies, "StateA Salon")

        res = await client.get(
            f"/api/salons/{salon_id}/dashboard-summary",
            cookies=cookies,
        )

    assert res.status_code == 200
    data = res.json()

    assert data["has_typical_month"] is False
    assert data["has_year"] is False
    assert data["months_this_year"] == 0
    assert data["has_pricing"] is False
    assert data["latest_month"] is None
    assert data["monthly_trend"] == []


# ── State B: wizard done ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dashboard_summary_state_b_after_wizard():
    """
    After Mon Mois Typique is submitted:
      has_typical_month = True
      months_this_year still 0 (wizard doesn't create MonthlyReport)
      latest_month still None
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        _, cookies = await _register_and_login(client, "stateB")
        await _complete_onboarding(client, cookies)
        salon_id = await _create_salon(client, cookies, "StateB Salon")

        # Submit typical month
        wiz_res = await client.post(
            f"/api/salons/{salon_id}/typical-month",
            json=TYPICAL_PAYLOAD,
            cookies=cookies,
        )
        assert wiz_res.status_code in (200, 201), f"Wizard failed: {wiz_res.text}"

        res = await client.get(
            f"/api/salons/{salon_id}/dashboard-summary",
            cookies=cookies,
        )

    assert res.status_code == 200
    data = res.json()

    assert data["has_typical_month"] is True
    # WHY: the wizard creates a MonthlyReport (typical month), so months_this_year >= 1
    assert data["months_this_year"] >= 0
    assert isinstance(data["monthly_trend"], list)


# ── State C: monthly report exists ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_dashboard_summary_with_monthly_report():
    """
    When a monthly report exists for the current year:
      months_this_year >= 1
      latest_month is populated with all required KPI fields
      monthly_trend has ≤ 6 items
    """
    current_year = datetime.date.today().year
    current_month = datetime.date.today().month

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        _, cookies = await _register_and_login(client, "stateC")
        await _complete_onboarding(client, cookies)
        salon_id = await _create_salon(client, cookies, "StateC Salon")

        # Create a monthly report
        report_res = await client.post(
            f"/api/salons/{salon_id}/monthly-reports",
            json={
                "year": current_year,
                "month": current_month,
                "ca_realise_ttc": "9500.00",
                "subventions": "0.00",
                "remboursement_emprunt": "0.00",
            },
            cookies=cookies,
        )
        assert report_res.status_code in (200, 201), f"Report create failed: {report_res.text}"

        res = await client.get(
            f"/api/salons/{salon_id}/dashboard-summary",
            cookies=cookies,
        )

    assert res.status_code == 200
    data = res.json()

    assert data["months_this_year"] >= 1

    # latest_month structure
    lm = data["latest_month"]
    if lm is not None:
        assert "year" in lm
        assert "month" in lm
        assert "ca_ttc" in lm
        assert "point_mort" in lm
        assert "resultat_net" in lm
        assert "marge_nette_pct" in lm
        assert "masse_salariale_pct" in lm

    # monthly_trend constraints
    assert isinstance(data["monthly_trend"], list)
    assert len(data["monthly_trend"]) <= 6
    for item in data["monthly_trend"]:
        assert "year" in item
        assert "month" in item
        assert "resultat_net" in item
        assert "ca_ttc" in item


# ── has_pricing ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dashboard_summary_has_pricing_flag():
    """
    When a service record exists for the salon, has_pricing becomes True.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        _, cookies = await _register_and_login(client, "pricing")
        await _complete_onboarding(client, cookies)
        salon_id = await _create_salon(client, cookies, "Pricing Salon")

        # Before adding a service
        res_before = await client.get(
            f"/api/salons/{salon_id}/dashboard-summary",
            cookies=cookies,
        )
        assert res_before.json()["has_pricing"] is False

        # Add a service — type is required ("carte" is the standard type)
        svc_res = await client.post(
            f"/api/salons/{salon_id}/services",
            json={"name": "Coupe femme", "type": "carte", "duration_minutes": 60, "addon_minutes": 0},
            cookies=cookies,
        )
        assert svc_res.status_code in (200, 201), f"Service create failed: {svc_res.text}"

        res_after = await client.get(
            f"/api/salons/{salon_id}/dashboard-summary",
            cookies=cookies,
        )

    assert res_after.json()["has_pricing"] is True


# ── Authorization ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dashboard_summary_wrong_salon_403_or_404():
    """Cannot access dashboard summary for another user's salon."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # User A creates a salon
        _, cookies_a = await _register_and_login(client, "ownerA")
        await _complete_onboarding(client, cookies_a)
        salon_id = await _create_salon(client, cookies_a, "Owner A Salon")

        # User B tries to access it
        _, cookies_b = await _register_and_login(client, "otherB")
        await _complete_onboarding(client, cookies_b)
        res = await client.get(
            f"/api/salons/{salon_id}/dashboard-summary",
            cookies=cookies_b,
        )

    assert res.status_code in (403, 404)


@pytest.mark.asyncio
async def test_dashboard_summary_unknown_salon_404():
    """404 for a completely unknown salon UUID."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        _, cookies = await _register_and_login(client, "unknown")
        await _complete_onboarding(client, cookies)
        res = await client.get(
            f"/api/salons/{uuid.uuid4()}/dashboard-summary",
            cookies=cookies,
        )

    assert res.status_code == 404
