"""
Tests for TASK-2.11.6 — Dirigeant as Employee with contract_type.

Verifies:
1. TNS dirigeant: cost is auto-computed and greater than net salary
2. Assimilé salarié dirigeant: cost uses RGDU formula, different from TNS
3. TNS vs assimilé produce different costs for same salary_brut
4. AE salon: no auto-created dirigeant employee after migration 025
5. contract_type='assimile_salarie' is persisted and returned correctly

WHY async httpx pattern: matches project convention (test_task_2_11_1_salon_contact.py).
asyncpg + session-scoped event_loop in conftest prohibits async generator fixtures.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app

SMOKE_EMAIL = "smoketest@comcoi.fr"
SMOKE_PASS = "Password123!"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _authed_client() -> AsyncClient:
    """Return a new AsyncClient pre-authenticated as the smoke-test user."""
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    login = await client.post(
        "/api/auth/login",
        json={"email": SMOKE_EMAIL, "password": SMOKE_PASS},
    )
    assert login.status_code == 200, f"Smoke-test login failed: {login.text}"
    client.cookies.update(login.cookies)
    return client


async def _create_salon(client: AsyncClient, business_type: str = "sarl") -> str:
    """Create a throwaway salon and return its ID."""
    res = await client.post(
        "/api/salons",
        json={"name": f"Test 2.11.6 {business_type}", "business_type": business_type},
    )
    assert res.status_code == 201, f"Create salon failed: {res.text}"
    return res.json()["id"]


async def _create_employee(client: AsyncClient, salon_id: str, **kwargs) -> dict:
    """Create an employee and return its JSON."""
    payload = {
        "name": "Test Employee",
        "role_type": "dirigeant",
        "hours_per_week": 35,
        "weeks_per_year": 45.6,
        "taux_occupation": 0.65,
        **kwargs,
    }
    res = await client.post(f"/api/salons/{salon_id}/employees", json=payload)
    assert res.status_code == 201, f"Create employee failed: {res.text}"
    return res.json()


async def _delete_salon(client: AsyncClient, salon_id: str) -> None:
    """Clean up — soft-delete the test salon."""
    await client.delete(f"/api/salons/{salon_id}")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers for config/employees (computed costs)
# ─────────────────────────────────────────────────────────────────────────────

async def _get_employee_summary(client: AsyncClient, salon_id: str, emp_id: str) -> dict | None:
    """
    Fetch the employee cost summaries via GET /config/employees — this
    endpoint uses _calc_employee_cost (with effectif + contract_type routing).

    WHY this endpoint (not POST response): cout_total_mensuel is stored in
    the DB on write but computed using the full charge formula only via the
    salon_config endpoint, which calls _calc_employee_cost.
    """
    res = await client.get(f"/api/salons/{salon_id}/config/employees")
    assert res.status_code == 200, f"Config employees failed: {res.text}"
    summaries = res.json()
    return next((s for s in summaries if s["id"] == emp_id), None)


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: TNS dirigeant cost is auto-computed via config endpoint
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_tns_dirigeant_cost_auto_computed():
    """
    A TNS dirigeant with salary_brut=2000 should have cout_total_mois
    greater than 2000 (TNS charges applied) as returned by the config/employees
    endpoint which uses _calc_employee_cost.

    WHY config/employees, not POST response: The POST response returns the raw
    DB value. The config/employees endpoint recalculates via _calc_employee_cost
    which applies the correct formula per role_type and contract_type.

    TNS formula: total = net / (1 - rate) where rate=0.45 → total ≈ net × 1.818.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post("/api/auth/login", json={"email": SMOKE_EMAIL, "password": SMOKE_PASS})
        assert login.status_code == 200
        client.cookies.update(login.cookies)

        salon_id = await _create_salon(client, "sarl")
        try:
            emp = await _create_employee(
                client, salon_id,
                name="Dirigeant TNS 2.11.6",
                role_type="dirigeant",
                contract_type="tns",
                salary_brut=2000.0,
            )
            summary = await _get_employee_summary(client, salon_id, emp["id"])
            assert summary is not None, "Employee summary not found in config/employees"

            cost = float(summary.get("cout_total_mois") or 0)
            assert cost > 2000.0, (
                f"TNS cost (from config/employees) must exceed net salary 2000. Got {cost}"
            )
            assert cost < 6000.0, f"TNS cost seems unrealistically high: {cost}"
        finally:
            await _delete_salon(client, salon_id)


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Assimilé salarié cost uses RGDU-style formula
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_assimile_salarie_cost_auto_computed():
    """
    An assimilé salarié dirigeant with salary_brut=3000 should have
    cout_total_mois > 3000 (employer charges on top of brut), as computed
    by _calc_employee_cost via the config/employees endpoint.

    WHY: assimilé salarié = RGDU formula, same as a regular salarié.
    Employer charges add approximately 40-50% on top of brut.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post("/api/auth/login", json={"email": SMOKE_EMAIL, "password": SMOKE_PASS})
        assert login.status_code == 200
        client.cookies.update(login.cookies)

        salon_id = await _create_salon(client, "sasu")
        try:
            emp = await _create_employee(
                client, salon_id,
                name="Dirigeant Assimilé 2.11.6",
                role_type="dirigeant",
                contract_type="assimile_salarie",
                salary_brut=3000.0,
            )
            summary = await _get_employee_summary(client, salon_id, emp["id"])
            assert summary is not None, "Employee summary not found in config/employees"

            cost = float(summary.get("cout_total_mois") or 0)
            assert cost > 3000.0, (
                f"Assimilé cost (from config/employees) must exceed brut 3000. Got {cost}"
            )
            assert cost < 7500.0, f"Assimilé cost seems too high: {cost}"
        finally:
            await _delete_salon(client, salon_id)


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: TNS vs assimilé produce DIFFERENT costs
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_tns_and_assimile_produce_different_costs():
    """
    For the same salary_brut=2500, TNS and assimilé salarié should produce
    different cout_total_mois values via the config/employees endpoint.

    WHY: This is the regression test for TASK-2.11.6's routing logic.
    If both contract_type values route to the same formula, costs would be
    equal and this test fails — alerting us to the bug.

    TNS: net / (1-0.45) ≈ net × 1.818
    Assimilé: brut + RGDU employer charges (~40-50%) → brut × ~1.45
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post("/api/auth/login", json={"email": SMOKE_EMAIL, "password": SMOKE_PASS})
        assert login.status_code == 200
        client.cookies.update(login.cookies)

        salon_id = await _create_salon(client, "sarl")
        try:
            emp_tns = await _create_employee(
                client, salon_id,
                name="Dirigeant TNS Comp",
                role_type="dirigeant",
                contract_type="tns",
                salary_brut=2500.0,
            )
            emp_assimile = await _create_employee(
                client, salon_id,
                name="Dirigeant Assimilé Comp",
                role_type="dirigeant",
                contract_type="assimile_salarie",
                salary_brut=2500.0,
            )

            summary_tns = await _get_employee_summary(client, salon_id, emp_tns["id"])
            summary_assimile = await _get_employee_summary(client, salon_id, emp_assimile["id"])

            assert summary_tns is not None, "TNS employee not found in config/employees"
            assert summary_assimile is not None, "Assimilé employee not found in config/employees"

            cost_tns = float(summary_tns.get("cout_total_mois") or 0)
            cost_assimile = float(summary_assimile.get("cout_total_mois") or 0)

            assert cost_tns != cost_assimile, (
                f"TNS ({cost_tns}€) and assimilé ({cost_assimile}€) must produce "
                f"different total costs for the same salary_brut=2500."
            )
        finally:
            await _delete_salon(client, salon_id)


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: AE salon — no auto-created dirigeant employee after migration 025
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_ae_salon_has_no_auto_dirigeant():
    """
    A fresh AE salon's employee list must not contain any 'dirigeant' rows.

    WHY (TASK-2.11.6): Migration 025 explicitly skips AE salons because AE
    remuneration is tracked via cout_vie_perso_mensuel (Task 2.11.16),
    NOT as an employee record. Creating a dirigeant for AE would double-count.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post("/api/auth/login", json={"email": SMOKE_EMAIL, "password": SMOKE_PASS})
        assert login.status_code == 200
        client.cookies.update(login.cookies)

        salon_id = await _create_salon(client, "auto_micro")
        try:
            res = await client.get(f"/api/salons/{salon_id}/employees")
            assert res.status_code == 200, res.text
            employees = res.json()

            dirigeants = [e for e in employees if e.get("role_type") == "dirigeant"]
            assert len(dirigeants) == 0, (
                f"Fresh AE salon must have no auto-created dirigeant. Found: {dirigeants}"
            )
        finally:
            await _delete_salon(client, salon_id)


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: contract_type='assimile_salarie' persisted and returned correctly
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_assimile_contract_type_persisted():
    """
    Verify that contract_type='assimile_salarie' is stored and returned
    by the API without being stripped or reset to 'tns'.

    WHY: The Employee model previously had no contract_type — this was added
    in TASK-2.11.6. Persistence confirms the column is correctly mapped.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post("/api/auth/login", json={"email": SMOKE_EMAIL, "password": SMOKE_PASS})
        assert login.status_code == 200
        client.cookies.update(login.cookies)

        salon_id = await _create_salon(client, "sasu")
        try:
            emp = await _create_employee(
                client, salon_id,
                name="Assimilé Persist Test",
                role_type="dirigeant",
                contract_type="assimile_salarie",
                salary_brut=3500.0,
            )
            emp_id = emp["id"]

            # Re-fetch via list endpoint (single-employee GET may not exist)
            list_res = await client.get(f"/api/salons/{salon_id}/employees")
            assert list_res.status_code == 200
            fetched = next((e for e in list_res.json() if e["id"] == emp_id), None)
            assert fetched is not None, "Employee not found after creation"
            assert fetched.get("contract_type") == "assimile_salarie", (
                f"Expected contract_type='assimile_salarie', got: {fetched.get('contract_type')}"
            )
        finally:
            await _delete_salon(client, salon_id)
