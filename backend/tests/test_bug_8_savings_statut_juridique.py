"""
Regression test for Bug 8 (2026-04-27): /api/salons/{id}/savings 500 when
salon has ≥3 monthly reports.

Root cause:
  `_channel_statut_juridique` referenced two attributes that don't exist on the
  `MonthlyReport` ORM:
    - `r.ca_ttc` → real column is `ca_realise_ttc`
    - aggregate "depenses_total_ttc" → no such column; expenses must be summed
      from the eager-loaded `expenses` relationship.

Hitting either path raised `AttributeError`, which the engine wrapped in a
generic 500 — every user with ≥3 months of pilotage data on a non-AE salon
saw an "erreur lors du calcul" toast on /mes-economies.

Acceptance:
  - GET /savings returns 200 for a SASU salon with 3 monthly reports + expenses.
  - The statut_juridique channel includes a `simulator_inputs` payload (the
    "what if I switched to EURL" widget data is what the user expected).
  - `total_annual_savings_eur` is a number (not null / not error).

This test must STAY GREEN — if it ever flips to 500 again, savings is broken
for every paying user with real pilotage data.

WHY a separate file: tagged `bug_8` to make it grep-able. Runs in <2s in
the existing pytest suite (no Stripe / no IMAP / pure DB).
"""

import uuid
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@asynccontextmanager
async def _register_and_login(email: str):
    """
    Register and authenticate a fresh test user.

    Args:
        email: Unique test email.

    Yields:
        Authenticated AsyncClient.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/auth/register",
            json={"email": email, "password": "Test1234!", "name": "Bug 8 Tester"},
        )
        assert r.status_code == 201, f"Register failed: {r.text}"
        r = await client.post(
            "/api/auth/login", json={"email": email, "password": "Test1234!"}
        )
        assert r.status_code == 200, f"Login failed: {r.text}"
        client.cookies.update(r.cookies)
        yield client


async def _create_salon(client: AsyncClient, business_type: str) -> str:
    """
    Create a salon of the given business type and return its UUID.

    Args:
        client:        Authenticated client.
        business_type: e.g. 'sasu', 'eurl', 'auto_micro'.

    Returns:
        Salon UUID string.
    """
    r = await client.post(
        "/api/salons",
        json={
            "name": f"Salon Bug8 {uuid.uuid4().hex[:6]}",
            "business_type": business_type,
        },
    )
    assert r.status_code == 201, f"Create salon failed: {r.text}"
    return r.json()["id"]


async def _create_report(
    client: AsyncClient,
    salon_id: str,
    year: int,
    month: int,
    ca_realise_ttc: float,
) -> str:
    """
    Create one monthly report and return its UUID.

    WHY ca_realise_ttc as keyword: the column name has been wrong before
    (Bug 8); pin it explicitly so a future rename surfaces here.

    Args:
        client:           Authenticated client.
        salon_id:         Salon UUID.
        year:             Calendar year of the report.
        month:            Calendar month (1-12).
        ca_realise_ttc:   Revenue TTC for the month.

    Returns:
        Report UUID string.
    """
    r = await client.post(
        f"/api/salons/{salon_id}/monthly-reports",
        json={"year": year, "month": month, "ca_realise_ttc": ca_realise_ttc},
    )
    assert r.status_code == 201, f"Report create failed: {r.text}"
    return r.json()["id"]


@pytest.mark.asyncio
async def test_savings_endpoint_does_not_500_with_three_months_of_data():
    """
    Reproduces Bug 8: SASU salon + 3 monthly reports + savings → must NOT 500.

    This is the regression guard for the `r.ca_realise_ttc` typo and the
    inline-sum-from-expenses fix in `_channel_statut_juridique`.
    """
    email = f"bug8_{uuid.uuid4().hex[:8]}@test.com"
    async with _register_and_login(email) as client:
        # SASU triggers the IS comptable tier AND populates statut_juridique
        # alternatives — exactly the path that hit the AttributeError.
        salon_id = await _create_salon(client, business_type="sasu")

        # 3 monthly reports = MIN_MONTHS threshold for the simulator.
        await _create_report(client, salon_id, 2026, 1, 12000)
        await _create_report(client, salon_id, 2026, 2, 11500)
        await _create_report(client, salon_id, 2026, 3, 13200)

        # The bug surfaces here — used to return 500.
        r = await client.get(f"/api/salons/{salon_id}/savings")
        assert r.status_code == 200, (
            f"Bug 8 regression: /savings returned {r.status_code}. "
            f"Body: {r.text}"
        )
        data = r.json()
        assert data["salon_id"] == salon_id
        # total must be present and numeric (not null) — None means a channel
        # silently failed and we don't want to ship that.
        assert data["total_annual_savings_eur"] is not None


@pytest.mark.asyncio
async def test_statut_juridique_channel_carries_simulator_inputs_for_sasu():
    """
    With ≥3 months of data, the statut_juridique channel must include a
    `simulator_inputs` payload — that's what powers the "passez en EURL"
    widget the user expected to see.

    Bug 8 also hid this widget (because the channel never returned at all).
    """
    email = f"bug8sim_{uuid.uuid4().hex[:8]}@test.com"
    async with _register_and_login(email) as client:
        salon_id = await _create_salon(client, business_type="sasu")
        await _create_report(client, salon_id, 2026, 1, 12000)
        await _create_report(client, salon_id, 2026, 2, 11500)
        await _create_report(client, salon_id, 2026, 3, 13200)

        r = await client.get(f"/api/salons/{salon_id}/savings")
        assert r.status_code == 200, r.text

        channels = {ch["channel_key"]: ch for ch in r.json()["channels"]}
        sj = channels.get("statut_juridique")
        assert sj is not None, "statut_juridique channel missing entirely"

        sim = sj.get("simulator_inputs")
        assert sim is not None, (
            "Bug 8 follow-up: simulator_inputs missing — the SASU→EURL "
            "comparison widget will not render on the frontend."
        )
        # Sanity: the payload must contain the current type and at least one
        # alternative for the simulator UI to be useful.
        assert sim["current_type"] == "sasu"
        assert isinstance(sim.get("alternatives"), list)
        assert len(sim["alternatives"]) >= 1, "No alternative business types returned"


@pytest.mark.asyncio
async def test_savings_under_three_months_shows_insufficient_data_not_500():
    """
    Below the 3-month threshold the channel should degrade gracefully —
    no simulator_inputs, no savings figure, but still a 200 with a friendly
    detail message. Bug 8 made this path 500 too.
    """
    email = f"bug8sub3_{uuid.uuid4().hex[:8]}@test.com"
    async with _register_and_login(email) as client:
        salon_id = await _create_salon(client, business_type="sasu")
        await _create_report(client, salon_id, 2026, 1, 12000)
        # Only 1 month — well under the MIN_MONTHS=3 threshold.

        r = await client.get(f"/api/salons/{salon_id}/savings")
        assert r.status_code == 200, r.text
        channels = {ch["channel_key"]: ch for ch in r.json()["channels"]}
        sj = channels["statut_juridique"]
        # Insufficient data → no savings figure, but no error
        assert sj["annual_savings_eur"] is None
        assert sj.get("detail"), "Expected a friendly 'add more months' detail"
