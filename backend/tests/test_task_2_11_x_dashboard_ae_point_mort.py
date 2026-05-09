"""
Tests — Task 2.11.x: Dashboard must use compute_full_point_mort for AE users.

Previously the dashboard endpoint used a naïve formula:
  point_mort = salaires + charges_ht
  cash_flow  = ca_ttc / 1.2 - point_mort   ← wrong for AE (no TVA)

This missed two mandatory costs for auto-entrepreneurs:
  1. URSSAF cotisations (21.2% of CA brut for bic_services)
  2. Minimum vital / cout_vie_perso

Test matrix:
  1. AE with URSSAF + minimum vital: point_mort and cash_flow match pilotage detail
  2. AE with URSSAF only (no cout_vie_perso): no crash, correct URSSAF applied
  3. Non-AE SARL: point_mort unchanged (salaires + charges only, no URSSAF)
  4. Dashboard cash_flow_ytd alert also uses correct formula
"""
from __future__ import annotations

import contextlib
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient, ASGITransport

# Use the FastAPI app directly (same pattern as all other backend tests)
# WHY: Tests run inside the Docker container — localhost:47002 is the HOST port
# and not reachable from within the container. ASGITransport hits the app in-process.
from app.main import app

SMOKE_EMAIL = "smoketest@comcoi.fr"
SMOKE_PASS = "Password123!"


# ── Helpers ────────────────────────────────────────────────────────────────────

@contextlib.asynccontextmanager
async def _client():
    """Create a test client using ASGI transport (no real HTTP, in-process)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _login(client: AsyncClient, email: str = SMOKE_EMAIL, password: str = SMOKE_PASS) -> None:
    """Log in and store session cookie in client."""
    resp = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"


async def _register_login(client: AsyncClient, email: str) -> None:
    """Register a fresh user and log in. Used for isolated test salons."""
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "TestPass123!", "name": "Test User"},
    )
    assert resp.status_code in (200, 201, 409), resp.text
    resp = await client.post("/api/auth/login", json={"email": email, "password": "TestPass123!"})
    assert resp.status_code == 200, resp.text


async def _create_salon(client: AsyncClient, name: str, business_type: str) -> str:
    """Create a salon and return its ID."""
    resp = await client.post(
        "/api/salons",
        json={"name": name, "business_type": business_type},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _put_config(client: AsyncClient, salon_id: str, payload: dict) -> dict:
    """PUT /api/salons/{salon_id}/config and return updated config."""
    resp = await client.put(f"/api/salons/{salon_id}/config", json=payload)
    assert resp.status_code == 200, f"Config update failed: {resp.text}"
    return resp.json()


async def _get_first_category_id(client: AsyncClient) -> str:
    """Fetch the first available expense category ID from the static-data endpoint."""
    resp = await client.get("/api/static-data/expense-categories")
    assert resp.status_code == 200, f"Failed to fetch categories: {resp.text}"
    categories = resp.json()
    assert categories, "No expense categories returned"
    return str(categories[0]["id"])


async def _post_report(client: AsyncClient, salon_id: str, year: int, month: int,
                        ca_ttc: float, expense_amount_ttc: float | None = None) -> str:
    """
    Create a MonthlyReport, optionally adding a single expense row.

    Uses the first available expense category to satisfy the required category_id field.

    Args:
        client: Authenticated HTTP test client.
        salon_id: Target salon UUID.
        year, month: Reporting period.
        ca_ttc: Gross CA for the month (TTC).
        expense_amount_ttc: If provided, create one expense row with this TTC amount
                            at 0% TVA (so amount_ht == amount_ttc, useful for AE tests).

    Returns:
        Report UUID string.
    """
    resp = await client.post(
        f"/api/salons/{salon_id}/monthly-reports",
        json={"year": year, "month": month, "ca_realise_ttc": ca_ttc},
    )
    assert resp.status_code in (200, 201), f"Report creation failed: {resp.text}"
    report_id = resp.json()["id"]

    if expense_amount_ttc is not None:
        category_id = await _get_first_category_id(client)
        er = await client.post(
            f"/api/salons/{salon_id}/monthly-reports/{report_id}/expenses",
            json={"category_id": category_id, "amount_ttc": str(expense_amount_ttc), "tva_rate": "0"},
        )
        assert er.status_code in (200, 201), f"Expense creation failed: {er.text}"

    return report_id


async def _get_dashboard(client: AsyncClient, salon_id: str) -> dict:
    """GET /api/salons/{salon_id}/dashboard-summary."""
    resp = await client.get(f"/api/salons/{salon_id}/dashboard-summary")
    assert resp.status_code == 200, f"Dashboard failed: {resp.text}"
    return resp.json()


async def _get_report_id(client: AsyncClient, salon_id: str, year: int, month: int) -> str:
    """Get the MonthlyReport ID for a given year/month by listing reports."""
    resp = await client.get(f"/api/salons/{salon_id}/monthly-reports")
    assert resp.status_code == 200, f"Failed to list reports: {resp.text}"
    for r in resp.json():
        if r["year"] == year and r["month"] == month:
            return str(r["id"])
    raise AssertionError(f"No report found for {year}-{month}")


async def _get_monthly_full(client: AsyncClient, salon_id: str, year: int, month: int) -> dict:
    """GET /api/salons/{salon_id}/monthly-reports/{report_id}/full."""
    report_id = await _get_report_id(client, salon_id, year, month)
    resp = await client.get(f"/api/salons/{salon_id}/monthly-reports/{report_id}/full")
    assert resp.status_code == 200, f"Monthly full failed: {resp.text}"
    return resp.json()


# ── Tests ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ae_dashboard_includes_urssaf() -> None:
    """
    AE salon: dashboard point_mort must include URSSAF (21.2% of CA).

    Setup: CA=4000, expenses=1000 HT, ae_activity_type=bic_services, no cout_vie_perso.
    Expected: point_mort ≈ 1000 + 848 = 1848, cash_flow ≈ 4000 - 1848 = 2152.
    (Not 4000/1.2 - 1000 = 2333 which was the old buggy value.)
    """
    email = f"ae_urssaf_{uuid.uuid4().hex[:8]}@test.comcoi.fr"
    async with _client() as c:
        await _register_login(c, email)
        salon_id = await _create_salon(c, "Salon AE URSSAF", "auto_micro")
        await _put_config(c, salon_id, {
            "ae_activity_type": "bic_services",
            # No cout_vie_perso_mensuel — testing URSSAF only
        })

        today_year, today_month = 2026, 4  # Use a known month
        await _post_report(
            c, salon_id, today_year, today_month, 4000.0,
            expense_amount_ttc=1000.0,  # 0% TVA: amount_ht == amount_ttc
        )

        # Get dashboard
        dash = await _get_dashboard(c, salon_id)
        lm = dash["latest_month"]

        # Point mort must include URSSAF: 1000 + 848 = 1848
        expected_urssaf = 4000 * 0.212  # = 848
        expected_point_mort = 1000 + expected_urssaf  # = 1848

        assert abs(lm["point_mort"] - expected_point_mort) < 1.0, (
            f"Dashboard point_mort={lm['point_mort']:.2f} should be ~{expected_point_mort:.2f} "
            f"(expenses 1000 + URSSAF {expected_urssaf:.2f})"
        )
        # cash_flow = 4000 - 1848 = 2152 (not 2333 from old /1.2 formula)
        expected_cf = 4000 - expected_point_mort
        assert abs(lm["resultat_net"] - expected_cf) < 1.0, (
            f"Dashboard resultat_net={lm['resultat_net']:.2f} should be ~{expected_cf:.2f}"
        )


@pytest.mark.asyncio
async def test_ae_dashboard_includes_minimum_vital() -> None:
    """
    AE salon with cout_vie_perso=2000: dashboard must include both URSSAF and min vital.

    CA=4000, expenses=1000, ae=bic_services, cout_vie_perso=2000.
    Expected point_mort = 1000 + 848 + 2000 = 3848, cash_flow = 4000 - 3848 = 152.
    (This is the exact scenario reported by the user as showing the wrong value.)
    """
    email = f"ae_minvital_{uuid.uuid4().hex[:8]}@test.comcoi.fr"
    async with _client() as c:
        await _register_login(c, email)
        salon_id = await _create_salon(c, "Salon AE Min Vital", "auto_micro")
        await _put_config(c, salon_id, {
            "ae_activity_type": "bic_services",
            "cout_vie_perso_mensuel": 2000,
        })

        await _post_report(c, salon_id, 2026, 4, 4000.0, expense_amount_ttc=1000.0)

        dash = await _get_dashboard(c, salon_id)
        lm = dash["latest_month"]

        expected_urssaf = 4000 * 0.212  # = 848
        expected_point_mort = 1000 + expected_urssaf + 2000  # = 3848
        expected_cf = 4000 - expected_point_mort  # = 152

        assert abs(lm["point_mort"] - expected_point_mort) < 1.0, (
            f"Dashboard point_mort={lm['point_mort']:.2f} should be ~{expected_point_mort:.2f} "
            f"(expenses 1000 + URSSAF {expected_urssaf:.2f} + min_vital 2000)"
        )
        assert abs(lm["resultat_net"] - expected_cf) < 1.0, (
            f"Dashboard resultat_net={lm['resultat_net']:.2f} should be ~{expected_cf:.2f}"
        )


@pytest.mark.asyncio
async def test_ae_dashboard_matches_pilotage_detail() -> None:
    """
    Dashboard latest_month values must equal pilotage monthly-full values for the same month.

    This is the core consistency check: both views must use compute_full_point_mort.
    CA=4000, expenses=1000, ae=bic_services, cout_vie_perso=2000.
    """
    email = f"ae_consistency_{uuid.uuid4().hex[:8]}@test.comcoi.fr"
    async with _client() as c:
        await _register_login(c, email)
        salon_id = await _create_salon(c, "Salon AE Consistency", "auto_micro")
        await _put_config(c, salon_id, {
            "ae_activity_type": "bic_services",
            "cout_vie_perso_mensuel": 2000,
        })

        await _post_report(c, salon_id, 2026, 4, 4000.0, expense_amount_ttc=1000.0)

        dash = await _get_dashboard(c, salon_id)
        lm = dash["latest_month"]

        # Compare with pilotage detail
        full = await _get_monthly_full(c, salon_id, 2026, 4)
        pilotage_pm = full.get("point_mort", {})

        # pilotage uses point_mort_dirigeant_inclus (may come back as str from Decimal serialisation)
        pilotage_point_mort_raw = pilotage_pm.get("point_mort_dirigeant_inclus", None)
        if pilotage_point_mort_raw is not None:
            pilotage_point_mort = float(pilotage_point_mort_raw)
            assert abs(lm["point_mort"] - pilotage_point_mort) < 0.01, (
                f"Dashboard point_mort={lm['point_mort']:.2f} must equal "
                f"pilotage point_mort_dirigeant_inclus={pilotage_point_mort:.2f}"
            )


@pytest.mark.asyncio
async def test_non_ae_dashboard_unchanged() -> None:
    """
    Non-AE (SARL) salon: dashboard must NOT add URSSAF or min vital.

    point_mort = salaires + charges_ht (same as before the fix).
    CA=5000 TTC, expenses=2000 HT. Expected point_mort ≈ 2000.
    Cash_flow ≈ 5000/1.2 - 2000 = 2166.67. Not AE: no URSSAF deduction.
    """
    email = f"sarl_unchanged_{uuid.uuid4().hex[:8]}@test.comcoi.fr"
    async with _client() as c:
        await _register_login(c, email)
        salon_id = await _create_salon(c, "Salon SARL", "sarl")

        # amount_ttc=2400 at 20% TVA → amount_ht = 2000
        await _post_report(c, salon_id, 2026, 4, 5000.0, expense_amount_ttc=2400.0)
        # For the SARL test we need 20% TVA; update the expense TVA rate after creation
        # Actually: the expense endpoint defaulting tva_rate depends on config.
        # Simpler: use no expenses and just verify no URSSAF is added.

        dash = await _get_dashboard(c, salon_id)
        lm = dash["latest_month"]

        # For SARL with 0% TVA expense of 2400: point_mort = 2400 (no URSSAF, no min vital)
        expected_point_mort = 2400.0
        # WHY ca/1.2: TASK-2.15.1 fixed compute_full_point_mort to use ca_ht (TTC/1.2).
        # SARL cash_flow = 5000/1.2 - 2400 = 4166.67 - 2400 = 1766.67
        expected_cf = round(5000 / 1.2 - expected_point_mort, 2)  # 1766.67

        assert abs(lm["point_mort"] - expected_point_mort) < 1.0, (
            f"SARL point_mort={lm['point_mort']:.2f} should be ~{expected_point_mort:.2f} "
            f"(no URSSAF for SARL)"
        )
        # Key assertion: for SARL, no URSSAF is subtracted from CA (not 5000 * 0.212 = 1060 extra)
        expected_cf_with_urssaf = round(5000 - expected_point_mort - 5000 * 0.212, 2)
        assert lm["resultat_net"] > expected_cf_with_urssaf, (
            f"SARL resultat_net={lm['resultat_net']:.2f} must be above {expected_cf_with_urssaf:.2f} "
            f"(URSSAF must NOT be deducted for SARL)"
        )
        assert abs(lm["resultat_net"] - expected_cf) < 1.0, (
            f"SARL resultat_net={lm['resultat_net']:.2f} should be ~{expected_cf:.2f}"
        )


@pytest.mark.asyncio
async def test_ae_ytd_alert_includes_urssaf() -> None:
    """
    YTD cash-flow alert (cash_flow_ytd) must include URSSAF for AE salons.

    Old formula: cash_flow_ytd = ca/1.2 - salaires - charges
    New formula: cash_flow_ytd = ca - (salaires + charges + urssaf + cout_vie_perso)

    With CA=4000, expenses=1000, ae=bic_services:
    old: 3333 - 1000 = 2333
    new: 4000 - 1848 = 2152

    We assert new value (includes URSSAF) is materially lower than old.
    """
    email = f"ae_ytd_{uuid.uuid4().hex[:8]}@test.comcoi.fr"
    async with _client() as c:
        await _register_login(c, email)
        salon_id = await _create_salon(c, "Salon AE YTD Alert", "auto_micro")
        await _put_config(c, salon_id, {"ae_activity_type": "bic_services"})

        await _post_report(c, salon_id, 2026, 4, 4000.0, expense_amount_ttc=1000.0)

        dash = await _get_dashboard(c, salon_id)
        alert = dash["cash_flow_alert"]
        ytd_cf = alert["cash_flow_ytd"]

        # New (correct) value: 4000 - 1848 = 2152
        # Old (buggy) value: 3333 - 1000 = 2333
        # The URSSAF of 848 is the key difference.
        assert ytd_cf < 2333, (
            f"cash_flow_ytd={ytd_cf:.2f} should be less than 2333 "
            f"(URSSAF 848 must be deducted for AE)"
        )
        assert abs(ytd_cf - 2152) < 5, (
            f"cash_flow_ytd={ytd_cf:.2f} should be ~2152 (4000 CA - 1000 expenses - 848 URSSAF)"
        )
