"""
Regression test: TASK-2.15.1 — Cash-flow consistency between wizard step-4
preview (resultat_net) and pilotage/bilan after generate_year_from_template.

Root cause fixed: compute_full_point_mort was using TTC amounts for total_B
(expenses) and CA, while the wizard correctly uses HT amounts throughout.
For a non-AE business the gap was exactly TVA_nette per month, causing
pilotage/bilan to show falsely higher cash flow than the wizard preview.

Fix: compute_full_point_mort now uses:
  - total_B = SUM(expense.amount_ht)   ← was SUM(expense.amount_ttc)
  - cash_flow = ca_ht - point_mort     ← was ca_ttc - point_mort

For AE salons: amount_ht == amount_ttc (no TVA), so the fix is a no-op.

Test scenario (non-AE, TNS dirigeant):
  CA TTC = 10 000 €, expenses TTC = 1 200 € (20% TVA → HT = 1 000 €),
  dirigeant net = 2 000 € (total_charge = 2 900 € via TNS ×1.45)

  Wizard:
    ca_ht        = 10 000 / 1.2  = 8 333.33
    point_mort   = 2 900 + 1 000 = 3 900.00
    resultat_net = 8 333.33 - 3 900 = 4 433.33

  Before fix (compute_full, TTC basis):
    total_B (TTC) = 1 200 → point_mort = 4 100 → cash_flow = 10 000 - 4 100 = 5 900  ✗

  After fix (compute_full, HT basis):
    total_B (HT)  = 1 000 → point_mort = 3 900 → cash_flow = 8 333.33 - 3 900 = 4 433.33  ✓
"""

import uuid
import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport

from app.main import app


def _api_client() -> AsyncClient:
    """Return a test client that exercises the full ASGI stack (no live server)."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _register_login(client: AsyncClient) -> None:
    """Register a fresh user and establish a session cookie on the client."""
    email = f"test_2_15_1_{uuid.uuid4().hex[:8]}@example.com"
    password = "TestPassword123!"
    r_reg = await client.post("/api/auth/register", json={"email": email, "password": password, "name": "Test 2.15.1"})
    assert r_reg.status_code in (200, 201), f"Register failed: {r_reg.text}"
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"Login failed: {r.text}"


async def _create_salon(client: AsyncClient, business_type: str = "sarl") -> str:
    """Create a salon and return its ID."""
    r = await client.post("/api/salons", json={
        "name": "Salon Test 2.15.1",
        "business_type": business_type,
    })
    assert r.status_code in (200, 201), f"Create salon failed: {r.text}"
    return r.json()["id"]


@pytest.mark.asyncio
async def test_wizard_cashflow_matches_pilotage_non_ae():
    """
    Non-AE (SARL TNS): wizard resultat_net must equal compute_full cash_flow
    after generate_year_from_template.

    This was broken before TASK-2.15.1 — pilotage showed ca_TTC-based cash flow
    (higher by TVA_nette) while wizard showed ca_HT-based resultat_net.
    """
    async with _api_client() as client:
        await _register_login(client)
        salon_id = await _create_salon(client, "sarl")

        # Fetch first expense category i18n key — wizard uses i18n_key, not UUID
        r = await client.get("/api/static-data/expense-categories")
        assert r.status_code == 200, f"expense-categories failed: {r.text}"
        cat_key = r.json()[0]["i18n_key"]

        # ── Submit wizard ──────────────────────────────────────────────────────
        # CA TTC = 10 000. TNS dirigeant net = 2 000 → total_charge = 2 900.
        # Expense: 1 200 TTC at 20% TVA → HT = 1 000.
        wizard_payload = {
            "ca_ttc": 10000.00,
            "team": [
                {
                    "name": "Patron",
                    "role_type": "dirigeant",
                    "contract_type": "tns",
                    "net_salary": 2000.00,
                    "hours_per_week": 35,
                    "included": True,
                    "is_scenario": False,
                }
            ],
            "expenses": [
                {
                    "category": cat_key,
                    "label": "Loyer test",
                    "amount_ttc": 1200.00,
                    "tva_rate": 0.20,
                }
            ],
            "brand_purchases": [],
        }
        r = await client.post(f"/api/salons/{salon_id}/typical-month", json=wizard_payload)
        assert r.status_code in (200, 201), f"Wizard failed: {r.text}"
        wizard = r.json()

        wizard_resultat_net = Decimal(str(wizard["resultat_net"]))
        wizard_point_mort = Decimal(str(wizard["point_mort"]))

        # Verify wizard produces the expected HT-basis numbers:
        #   ca_ht = 8333.33, expenses_ht = 1000, tns_total_charge = 2900
        #   point_mort = 3900, resultat_net = 4433.33
        assert abs(wizard_point_mort - Decimal("3900.00")) < Decimal("1.00"), (
            f"Wizard point_mort = {wizard_point_mort}, expected ~3900"
        )
        assert abs(wizard_resultat_net - Decimal("4433.33")) < Decimal("1.00"), (
            f"Wizard resultat_net = {wizard_resultat_net}, expected ~4433.33"
        )

        # ── Generate 12 months from template ──────────────────────────────────
        import datetime
        year = datetime.date.today().year
        r = await client.post(
            f"/api/salons/{salon_id}/years/{year}/generate-from-template",
            json={"overwrite": True},
        )
        assert r.status_code in (200, 201), f"generate-from-template failed: {r.text}"
        gen = r.json()
        assert gen["months_created"] > 0, "No months were generated"

        report_id = gen["reports"][0]["id"]

        # ── Check /full endpoint for one generated month ───────────────────────
        r = await client.get(f"/api/salons/{salon_id}/monthly-reports/{report_id}/full")
        assert r.status_code == 200, f"/full failed: {r.text}"
        pm = r.json()["point_mort"]

        full_cash_flow = Decimal(str(pm["cash_flow"]))
        full_point_mort = Decimal(str(pm["point_mort_dirigeant_inclus"]))

        assert abs(full_point_mort - wizard_point_mort) < Decimal("1.00"), (
            f"Point mort mismatch: wizard={wizard_point_mort}, pilotage={full_point_mort}"
        )
        assert abs(full_cash_flow - wizard_resultat_net) < Decimal("1.00"), (
            f"Cash flow mismatch (TASK-2.15.1 regression): "
            f"wizard={wizard_resultat_net}, pilotage={full_cash_flow}. "
            f"Gap={full_cash_flow - wizard_resultat_net:.2f} "
            f"(was ~TVA_nette={Decimal('10000') - Decimal('10000') / Decimal('1.2'):.2f} before fix)"
        )

        # ── Check annual summary ───────────────────────────────────────────────
        r = await client.get(
            f"/api/salons/{salon_id}/annual-summary/{year}",
        )
        assert r.status_code == 200, f"Annual summary failed: {r.text}"
        annual = r.json()

        months_with_data = annual["months_with_data"]
        total_cash_flow = Decimal(str(annual["total_cash_flow"]))
        expected_total = wizard_resultat_net * months_with_data

        assert abs(total_cash_flow - expected_total) < Decimal("2.00"), (
            f"Annual cash flow mismatch: expected {expected_total:.2f} "
            f"({months_with_data} × {wizard_resultat_net:.2f}), got {total_cash_flow:.2f}"
        )


@pytest.mark.asyncio
async def test_wizard_cashflow_matches_pilotage_ae():
    """
    AE (auto_micro): no TVA, so wizard and compute_full should already agree.
    The TASK-2.15.1 fix must be a no-op for AE salons. Confirm no regression.
    """
    async with _api_client() as client:
        await _register_login(client)
        salon_id = await _create_salon(client, "auto_micro")

        r = await client.get("/api/static-data/expense-categories")
        assert r.status_code == 200, f"AE expense-categories failed: {r.text}"
        cat_key = r.json()[0]["i18n_key"]

        wizard_payload = {
            "ca_ttc": 5000.00,
            "team": [],
            "expenses": [
                {
                    "category": cat_key,
                    "label": "Loyer AE",
                    "amount_ttc": 600.00,
                    "tva_rate": 0.0,
                }
            ],
            "brand_purchases": [],
        }
        r = await client.post(f"/api/salons/{salon_id}/typical-month", json=wizard_payload)
        assert r.status_code in (200, 201), f"AE wizard failed: {r.text}"
        wizard = r.json()

        import datetime
        year = datetime.date.today().year
        r = await client.post(
            f"/api/salons/{salon_id}/years/{year}/generate-from-template",
            json={"overwrite": True},
        )
        assert r.status_code in (200, 201), f"AE generate-from-template failed: {r.text}"
        gen = r.json()
        assert gen["months_created"] > 0

        report_id = gen["reports"][0]["id"]
        r = await client.get(f"/api/salons/{salon_id}/monthly-reports/{report_id}/full")
        assert r.status_code == 200
        pm = r.json()["point_mort"]

        full_cash_flow = Decimal(str(pm["cash_flow"]))
        wizard_resultat = Decimal(str(wizard["resultat_net"]))

        assert abs(full_cash_flow - wizard_resultat) < Decimal("1.00"), (
            f"AE cash flow mismatch (no TVA — should be 0 gap): "
            f"wizard={wizard_resultat}, full={full_cash_flow}"
        )
