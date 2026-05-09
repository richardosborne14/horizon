"""
Tests for AE solo dirigeant pricing mode.

Bug: AE salons have no auto-created Employee record (TASK-2.11.6 migration 025
intentionally skips them). Without an employee, compute_pricing() returns
has_employees=False and the /prix page shows a dead-end warning.

Fix: When the frontend supplies three solo_dirigeant_* fields AND the salon
is auto_micro with no DB employees, the pricing endpoint synthesises a virtual
EmployeePricingData and runs the normal cost-per-minute calculation.

Tests:
1. Pure unit test: compute_pricing() with one synthetic dirigeant reproduces
   Eric's reference numbers (10h/day × 4d/wk × 40wks × 40% = 38,400 min,
   37,500€ / 38,400min = 0.9766€/min).

2. Integration test: POST /api/calculations/pricing with solo_dirigeant_*
   fields on an auto_micro salon with no employees → is_solo_dirigeant=True,
   has_employees=True, correct cout_reel_minute.

3. Back-compat: auto_micro salon with no employees but NO solo fields supplied
   → has_employees=False (unchanged behaviour).

4. Non-AE salon with no employees + solo fields → still has_employees=False
   (solo mode only activates for auto_micro).
"""

from decimal import Decimal

import pytest
from httpx import AsyncClient, ASGITransport

from app.calculations.pricing import compute_pricing, EmployeePricingData
from app.main import app

SMOKE_EMAIL = "smoketest@comcoi.fr"
SMOKE_PASS = "Password123!"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _authed_client() -> AsyncClient:
    """Return a new authenticated AsyncClient as the smoke-test user."""
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    login = await client.post(
        "/api/auth/login",
        json={"email": SMOKE_EMAIL, "password": SMOKE_PASS},
    )
    assert login.status_code == 200, f"Login failed: {login.text}"
    client.cookies.update(login.cookies)
    return client


async def _create_ae_salon(client: AsyncClient) -> str:
    """Create a throwaway auto_micro salon; return its ID."""
    res = await client.post(
        "/api/salons",
        json={"name": "Test AE Solo Pricing", "business_type": "auto_micro"},
    )
    assert res.status_code == 201, f"Salon create failed: {res.text}"
    return res.json()["id"]


async def _create_sarl_salon(client: AsyncClient) -> str:
    """Create a throwaway SARL salon; return its ID."""
    res = await client.post(
        "/api/salons",
        json={"name": "Test SARL Solo Pricing", "business_type": "sarl"},
    )
    assert res.status_code == 201, f"Salon create failed: {res.text}"
    return res.json()["id"]


async def _delete_salon(client: AsyncClient, salon_id: str) -> None:
    """Soft-delete the test salon to keep DB clean."""
    await client.delete(f"/api/salons/{salon_id}")


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Unit test — Eric's reference numbers
# ─────────────────────────────────────────────────────────────────────────────

def test_ae_solo_reference_numbers():
    """
    Verify compute_pricing() reproduces Eric's domicile AE example exactly.

    Eric's example (from client feedback):
      Présence : 10 h/jour × 4 jours × 40 semaines = 1 600 h/an
      Taux de productivité = 40 %
      Heures productives = 1 600 × 0.40 = 640 h = 38 400 min
      Coût total (revenu 1 500 € net inclus) = 37 500 €
      Coût réel minute = 37 500 / 38 400 = 0.9765625 ≈ 0.976563 €/min

    The synthetic employee uses:
      hours_per_week = 4 jours × 10 h = 40 h
      weeks_per_year = 40
      taux_occupation = 0.40
    """
    employees = [
        EmployeePricingData(
            employee_id="solo-ae-test",
            name="Dirigeant (AE)",
            role_type="dirigeant",
            hours_per_week=Decimal("40"),
            weeks_per_year=Decimal("40"),
            taux_occupation=Decimal("0.40"),
            contract_subtype=None,
        )
    ]

    result = compute_pricing(
        employees=employees,
        cout_total_fonctionnement=Decimal("37500"),
        services=[],
        majoration_securite_benefice=Decimal("0.10"),
        source_couts="manual",
    )

    assert result.has_employees is True
    # Total minutes: 40h × 40wks × 60 × 0.40 = 38,400
    expected_minutes = Decimal("38400.00")
    assert result.total_minutes_reelles == expected_minutes, (
        f"Expected {expected_minutes} real minutes, got {result.total_minutes_reelles}"
    )
    # cout_reel_minute = 37500 / 38400 ≈ 0.976563
    expected_crm = Decimal("37500") / Decimal("38400")
    # Rounded to 6dp
    from decimal import ROUND_HALF_UP
    expected_crm_r = expected_crm.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    assert result.cout_reel_minute == expected_crm_r, (
        f"Expected cout_reel_minute={expected_crm_r}, got {result.cout_reel_minute}"
    )
    # taux_moyen_occupation = 0.40 (single employee)
    assert result.taux_moyen_occupation == Decimal("0.4000"), (
        f"Expected taux_moyen_occupation=0.4000, got {result.taux_moyen_occupation}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Integration — POST /pricing with solo fields on AE salon
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_pricing_solo_dirigeant_ae_integration():
    """
    POST /api/calculations/pricing with solo_dirigeant_* fields on an AE salon
    with no employees should return is_solo_dirigeant=True, has_employees=True,
    and a non-zero cout_reel_minute matching Eric's reference.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post(
            "/api/auth/login", json={"email": SMOKE_EMAIL, "password": SMOKE_PASS}
        )
        assert login.status_code == 200
        client.cookies.update(login.cookies)

        salon_id = await _create_ae_salon(client)
        try:
            # Verify no employees on this fresh AE salon
            emp_res = await client.get(f"/api/salons/{salon_id}/employees")
            assert emp_res.status_code == 200
            assert len(emp_res.json()) == 0, "Fresh AE salon should have no employees"

            # Run pricing with solo dirigeant fields — Eric's reference numbers
            res = await client.post(
                "/api/calculations/pricing",
                json={
                    "salon_id": salon_id,
                    "cout_annuel_total": 37500,
                    "solo_dirigeant_hours_per_week": 40,
                    "solo_dirigeant_weeks_per_year": 40,
                    "solo_dirigeant_taux_occupation": 0.40,
                    "majoration_securite_benefice": 0.10,
                    "save_to_services": False,
                },
            )
            assert res.status_code == 200, f"Pricing failed: {res.text}"
            data = res.json()

            assert data["is_solo_dirigeant"] is True, "Expected is_solo_dirigeant=True"
            assert data["has_employees"] is True, "Expected has_employees=True after solo injection"
            assert len(data["employees"]) == 1
            assert data["employees"][0]["name"] == "Dirigeant (AE)"

            # Verify minutes
            assert float(data["total_minutes_reelles"]) == pytest.approx(38400.0, rel=1e-3)

            # Verify cout_reel_minute ≈ 0.9766
            crm = float(data["cout_reel_minute"])
            assert crm == pytest.approx(37500 / 38400, rel=1e-4), (
                f"Expected ~0.9766, got {crm}"
            )

        finally:
            await _delete_salon(client, salon_id)


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: Back-compat — AE with no employees, no solo fields → has_employees=False
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_pricing_ae_no_employees_no_solo_fields_unchanged():
    """
    Existing behaviour: AE salon + no employees + no solo_dirigeant_* fields
    → has_employees=False, is_solo_dirigeant=False.

    This ensures we haven't broken the existing warning flow.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post(
            "/api/auth/login", json={"email": SMOKE_EMAIL, "password": SMOKE_PASS}
        )
        assert login.status_code == 200
        client.cookies.update(login.cookies)

        salon_id = await _create_ae_salon(client)
        try:
            res = await client.post(
                "/api/calculations/pricing",
                json={
                    "salon_id": salon_id,
                    "cout_annuel_total": 37500,
                    # No solo_dirigeant_* fields
                    "save_to_services": False,
                },
            )
            assert res.status_code == 200, f"Pricing failed: {res.text}"
            data = res.json()

            assert data["has_employees"] is False, "Should be False without solo fields"
            assert data["is_solo_dirigeant"] is False
            assert float(data["cout_reel_minute"]) == 0.0

        finally:
            await _delete_salon(client, salon_id)


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: Solo fields on non-AE salon without employees → still has_employees=False
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_pricing_non_ae_with_solo_fields_ignored():
    """
    A SARL salon with no employees that sends solo_dirigeant_* fields should NOT
    trigger solo mode. is_solo_dirigeant stays False and has_employees stays False.

    WHY: solo mode is AE-only by design — non-AE owners must add a dirigeant
    Employee record via Paramétrage → Équipe (where the TNS cost formula applies).
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post(
            "/api/auth/login", json={"email": SMOKE_EMAIL, "password": SMOKE_PASS}
        )
        assert login.status_code == 200
        client.cookies.update(login.cookies)

        salon_id = await _create_sarl_salon(client)
        try:
            res = await client.post(
                "/api/calculations/pricing",
                json={
                    "salon_id": salon_id,
                    "cout_annuel_total": 37500,
                    "solo_dirigeant_hours_per_week": 40,
                    "solo_dirigeant_weeks_per_year": 40,
                    "solo_dirigeant_taux_occupation": 0.40,
                    "save_to_services": False,
                },
            )
            assert res.status_code == 200, f"Pricing failed: {res.text}"
            data = res.json()

            assert data["has_employees"] is False, (
                "Non-AE salon should not trigger solo mode — must use Employee records"
            )
            assert data["is_solo_dirigeant"] is False

        finally:
            await _delete_salon(client, salon_id)
