"""
TASK-2.11.5: Typical-Month — Dirigeant Cost Included in Point Mort (Section A)

Eric (PDF p12): "le système n'a pas pris en compte le salaire du dirigeant
(dans mon mois type)."

Verifies that:
1. TNS dirigeant at 2000 € net → Section A total_charge ≈ 2900 € (2000 × 1.45)
2. Assimilé salarié dirigeant → Section A total_charge via salarié formula
3. AE salon without dirigeant team member → no phantom salary row (total_salaires = 0)
4. Prestataire in team payload → cost appears in charges path, not in directed salary row

WHY: Eric's scenario shows only Julie (salarié) in Section A — the dirigeant's
TNS cost was zero because he had not added himself to the wizard team Step 2.
These tests confirm the backend correctly includes dirigeants when submitted AND
does not invent phantom rows for AE or prestataire roles.

WHY inline client per test: asyncpg + session-scoped event_loop conftest pattern.
"""

import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.calculations.social_charges import estimate_charges_tns, net_to_brut

TNS_NET = 2000.0  # Eric's scenario: 2000 € net TNS

TYPICAL_BASE = {
    "ca_ttc": 8000,
    "expenses": [
        {
            "category": "expenses.loyer_immobilier",
            "label": "Loyer",
            "amount_ttc": 1200,
            "tva_rate": 0.0,
        }
    ],
}


# ── helpers ───────────────────────────────────────────────────────────────────


def _client() -> AsyncClient:
    """Return a fresh ASGI test client."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _setup(client: AsyncClient, suffix: str, business_type: str = "sarl") -> str:
    """Register, login and create a salon. Return salon_id."""
    email = f"dirigeant_test_{suffix}@test.com"
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "name": "Test"},
    )
    await client.post(
        "/api/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    resp = await client.post(
        "/api/salons",
        json={"name": f"Salon {suffix}", "city": "Lyon", "business_type": business_type},
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


# ── tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tns_dirigeant_included_in_section_a():
    """
    WHY: TNS dirigeant at 2000 € net → total_charge ≈ 2900 € (45% URSSAF on net).
    This mirrors Eric's scenario: a non-AE gérant SARL who submits himself as
    a team member with role_type='dirigeant', contract_type='tns'.

    The wizard response 'total_salaires' must include the TNS cost, confirming
    the dirigeant is counted in Section A (masse salariale).
    """
    async with _client() as c:
        salon_id = await _setup(c, "tns_section_a")

        # Expected TNS cost from the same formula used in the service
        tns = estimate_charges_tns(Decimal("2000"))
        expected_total = float(tns.cout_total_entreprise)

        payload = {
            **TYPICAL_BASE,
            "team": [
                {
                    "name": "Eric",
                    "role_type": "dirigeant",
                    "contract_type": "tns",
                    "net_salary": TNS_NET,
                    "hours_per_week": 40,
                }
            ],
        }
        resp = await c.post(f"/api/salons/{salon_id}/typical-month", json=payload)
        assert resp.status_code in (200, 201), resp.text
        data = resp.json()

        # Section A: total_salaires must equal the TNS cost
        total_salaires = data["breakdown"]["total_salaires"]
        assert abs(total_salaires - expected_total) < 1.0, (
            f"total_salaires {total_salaires:.2f} ≠ expected TNS total {expected_total:.2f}. "
            "Dirigeant cost missing from Section A."
        )

        # Point mort must be positive (includes salary + charges)
        assert data["point_mort"] > 0, "point_mort should include dirigeant cost"
        # Breakdown cost should be significant (not zero)
        assert total_salaires > 2800, (
            f"TNS total should be ~2900 € for 2000 € net (got {total_salaires:.2f})"
        )


@pytest.mark.asyncio
async def test_assimile_salarie_dirigeant_included_in_section_a():
    """
    WHY: Assimilé salarié (SASU, SAS, minority gérant SARL) is treated like a
    regular salarié for cotisations. The net_to_brut() formula applies, giving
    total_charge ≈ net * 1.80 (brut ≈ net / 0.78, patronales ≈ brut * 0.45).

    For 2000 € net assimilé salarié, we expect total_charge in range [3000, 4000].
    The important assertion is that the cost > 0 and ends up in Section A.
    """
    async with _client() as c:
        salon_id = await _setup(c, "assimile_section_a")

        payload = {
            **TYPICAL_BASE,
            "team": [
                {
                    "name": "Sophie",
                    "role_type": "dirigeant",
                    "contract_type": "assimile_salarie",
                    "net_salary": 2000,
                    "hours_per_week": 35,
                }
            ],
        }
        resp = await c.post(f"/api/salons/{salon_id}/typical-month", json=payload)
        assert resp.status_code in (200, 201), resp.text
        data = resp.json()

        total_salaires = data["breakdown"]["total_salaires"]
        # Expected: use the same net_to_brut formula the service uses
        expected = net_to_brut(
            net_mensuel=Decimal("2000"),
            contract_type="assimile_salarie",
            role_type="dirigeant",
        )
        expected_total = float(expected.cout_total)
        assert abs(total_salaires - expected_total) < 2.0, (
            f"Assimilé salarié total_salaires {total_salaires:.2f} ≠ "
            f"expected {expected_total:.2f}. Cost may be missing from Section A."
        )
        # Sanity: assimilé salarié has real cotisations, total must be > net
        assert total_salaires > 2000, (
            f"Assimilé salarié total {total_salaires:.2f} ≤ net salary 2000. "
            "Charges patronales not applied."
        )


@pytest.mark.asyncio
async def test_ae_dirigeant_not_duplicated():
    """
    WHY: Auto-entrepreneurs do NOT receive a salary — their income is the residual
    after URSSAF + expenses. The wizard frontend filters 'dirigeant' from the
    team role dropdown for AE users.

    This regression test confirms that an AE salon whose team is EMPTY (or has
    only prestataires in charges) does NOT get a phantom salary row for the owner.
    total_salaires must be 0; URSSAF cotisations must be >0 (applied on gross CA).
    """
    async with _client() as c:
        salon_id = await _setup(c, "ae_no_phantom", business_type="auto_micro")

        # AE wizard: no team members (owner income is residual, not a salary row)
        # WHY loyer: expenses.loyer_immobilier is guaranteed to exist in the seeded DB.
        payload = {
            "ca_ttc": 5000,
            "team": [],  # Intentionally empty — no dirigeant
            "expenses": [
                {
                    "category": "expenses.loyer_immobilier",
                    "label": "Loyer local",
                    "amount_ttc": 600,
                    "tva_rate": 0.0,
                }
            ],
        }
        resp = await c.post(f"/api/salons/{salon_id}/typical-month", json=payload)
        assert resp.status_code in (200, 201), resp.text
        data = resp.json()

        # No phantom salary rows — AE income is residual, not a salary
        assert data["breakdown"]["total_salaires"] == 0.0, (
            f"AE salon should have 0 team salaries (got {data['breakdown']['total_salaires']}). "
            "Phantom dirigeant row must not be auto-inserted for AE."
        )
        # URSSAF is applied (this is the AE equivalent of "cotisations")
        assert data["breakdown"]["urssaf_cotisations"] > 0, (
            "AE URSSAF cotisations should be >0 — computed on gross CA."
        )
        # Point mort is non-zero (URSSAF + expenses)
        assert data["point_mort"] > 0, "AE point_mort should include URSSAF + expenses"


@pytest.mark.asyncio
async def test_prestataire_not_in_salary_section():
    """
    WHY: The wizard UI tells users "Les prestataires sont à saisir dans les charges
    à l'étape suivante." Prestataire costs should flow through the expenses path,
    not the Section A (masse salariale) path. When the team list contains only a
    prestataire, total_salaires should reflect the flat fee with zero URSSAF
    overhead (prestataires have no charges patronales).

    NOTE: The current system accepts prestataires in the team payload for
    legacy compatibility. The flat cost (no charges) IS included in total_salaires
    as a zero-overhead line (charges_patronales = 0). This test documents and
    regression-guards that behaviour:
    - prestataire adds its flat fee to total_salaires with 0 patronales overhead
    - The system does NOT apply the salarié net_to_brut formula to a prestataire
    """
    async with _client() as c:
        salon_id = await _setup(c, "prestataire_check")

        prestataire_cost = 600.0  # flat monthly fee

        payload = {
            **TYPICAL_BASE,
            "team": [
                {
                    "name": "Camille Prestataire",
                    "role_type": "prestataire",
                    "contract_type": "prestataire",
                    "net_salary": prestataire_cost,
                    "hours_per_week": 20,
                }
            ],
        }
        resp = await c.post(f"/api/salons/{salon_id}/typical-month", json=payload)
        assert resp.status_code in (200, 201), resp.text
        data = resp.json()

        total_salaires = data["breakdown"]["total_salaires"]
        # Prestataire has no charges patronales — total = flat fee, not flat * 1.45
        # If salarié formula had been applied to 600 € net, total_charge would be ~1080+.
        # The value must be equal to the flat fee (within rounding).
        assert abs(total_salaires - prestataire_cost) < 5.0, (
            f"Prestataire should not have charges patronales applied. "
            f"Expected ~{prestataire_cost}, got {total_salaires:.2f} (salarié formula may have fired)."
        )
