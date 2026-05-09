"""
TASK-2.12.7 — Pilotage Bilan / Add-employee inline tests.

Tests:
  1. Savings API returns a 'comptable' channel (required for bilan page honoraires row).
  2. Annual summary months_with_data reflects created reports correctly.
  3. Add-employee inline flow: create employee → verify in employee list → /full endpoint ok.

Auth pattern: register → login → cookies (session-based, NOT Bearer token).
WHY asynccontextmanager: httpx AsyncClient state must be OPENED before requests.
"""

import uuid
import pytest
from contextlib import asynccontextmanager
from httpx import AsyncClient, ASGITransport

from app.main import app


@asynccontextmanager
async def fresh_user_client():
    """
    Register a fresh user and yield an authenticated ASGI client (cookie-based).

    WHY: Auth is session/cookie-based (same as savings engine test pattern).
    Register does NOT return a token — must login separately to get cookies.
    """
    suffix = uuid.uuid4().hex[:8]
    email = f"test2127_{suffix}@test.com"
    password = "Test1234!"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/auth/register",
            json={"email": email, "password": password, "name": "Test 2127"},
        )
        assert r.status_code == 201, f"Register failed: {r.text}"

        r = await client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        assert r.status_code == 200, f"Login failed: {r.text}"
        client.cookies.update(r.cookies)

        yield client


async def create_salon(client: AsyncClient, name: str = "Salon Bilan Test") -> str:
    """Create a salon and return its ID."""
    r = await client.post(
        "/api/salons",
        json={"name": name, "business_type": "sarl"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ── Test classes ──────────────────────────────────────────────────────────────

class TestSavingsComptableChannel:
    """The savings API must return a 'comptable' channel so the bilan page renders the honoraires row."""

    @pytest.mark.asyncio
    async def test_savings_returns_comptable_channel(self):
        """GET /salons/{id}/savings → channels list includes 'comptable'."""
        async with fresh_user_client() as client:
            salon_id = await create_salon(client)
            r = await client.get(f"/api/salons/{salon_id}/savings")
            assert r.status_code == 200, r.text
            keys = [ch["channel_key"] for ch in r.json()["channels"]]
            assert "comptable" in keys, f"Expected 'comptable' in savings channels, got: {keys}"

    @pytest.mark.asyncio
    async def test_savings_total_is_numeric(self):
        """
        total_annual_savings_eur must be parseable as a number.
        WHY: NUMERIC(12,2) fields are serialised as strings by FastAPI/Pydantic (not float).
        We accept str (e.g. '884.00') and coerce to float for the numeric check.
        """
        async with fresh_user_client() as client:
            salon_id = await create_salon(client)
            r = await client.get(f"/api/salons/{salon_id}/savings")
            assert r.status_code == 200
            raw = r.json()["total_annual_savings_eur"]
            # NUMERIC(12,2) comes back as a string from the DB layer — must be castable to float
            assert raw is not None, "total_annual_savings_eur must not be null"
            assert float(raw) >= 0, f"Expected a non-negative numeric total, got: {raw!r}"

    @pytest.mark.asyncio
    async def test_savings_comptable_channel_has_required_fields(self):
        """
        Comptable channel must have channel_label, annual_savings_eur, current_cost_eur, comcoi_cost_eur.
        WHY: bilan page renders all four fields inline in the honoraires row.
        """
        async with fresh_user_client() as client:
            salon_id = await create_salon(client)
            r = await client.get(f"/api/salons/{salon_id}/savings")
            assert r.status_code == 200
            comptable = next(
                (ch for ch in r.json()["channels"] if ch["channel_key"] == "comptable"), None
            )
            assert comptable is not None, "comptable channel not found"
            for field in ("channel_label", "annual_savings_eur", "current_cost_eur", "comcoi_cost_eur"):
                assert field in comptable, f"Missing field in comptable channel: {field}"


class TestAnnualSummaryMonthsWithData:
    """months_with_data must accurately reflect created reports."""

    @pytest.mark.asyncio
    async def test_empty_year_has_zero_months_with_data(self):
        """Fresh salon, no reports → months_with_data == 0."""
        async with fresh_user_client() as client:
            salon_id = await create_salon(client)
            r = await client.get(f"/api/salons/{salon_id}/annual-summary/2099")
            assert r.status_code == 200
            assert r.json()["months_with_data"] == 0

    @pytest.mark.asyncio
    async def test_months_with_data_reflects_created_report(self):
        """After creating a report, months_with_data = 1 and that month has has_data=True."""
        async with fresh_user_client() as client:
            salon_id = await create_salon(client)

            # Create a report for March 2099
            r = await client.post(
                f"/api/salons/{salon_id}/monthly-reports",
                json={"year": 2099, "month": 3, "ca_realise_ttc": "5000", "subventions": "0"},
            )
            assert r.status_code == 201, r.text

            summary = await client.get(f"/api/salons/{salon_id}/annual-summary/2099")
            assert summary.status_code == 200
            data = summary.json()
            assert data["months_with_data"] == 1

            march = next((m for m in data["months"] if m["month"] == 3), None)
            assert march is not None
            assert march["has_data"] is True


class TestAddEmployeeInline:
    """
    Creating an employee via the API must appear in the employee list.
    The /full endpoint must always return salary_rows + salary_totals keys.
    WHY: the mois page's inline add-employee calls loadReport() post-creation
    and expects the SalaryGrid to receive a populated salaryData object.
    """

    @pytest.mark.asyncio
    async def test_create_employee_appears_in_list(self):
        """POST /salons/{id}/employees → GET employees returns the new employee."""
        async with fresh_user_client() as client:
            salon_id = await create_salon(client)

            before = await client.get(f"/api/salons/{salon_id}/employees")
            assert before.status_code == 200
            count_before = len(before.json())

            r = await client.post(
                f"/api/salons/{salon_id}/employees",
                json={
                    "name": "Julie Martin",
                    "role_type": "salarie",
                    "contract_type": "cdi",
                    "hours_per_week": 35,
                    "salary_brut": "2000.00",
                    "cotisations_patronales": "600.00",
                    "taux_occupation": "0.65",
                },
            )
            assert r.status_code == 201, r.text
            emp_id = r.json()["id"]

            after = await client.get(f"/api/salons/{salon_id}/employees")
            assert after.status_code == 200
            ids = [e["id"] for e in after.json()]
            assert emp_id in ids, "New employee not found in employee list after creation"
            assert len(after.json()) == count_before + 1

    @pytest.mark.asyncio
    async def test_monthly_full_has_salary_keys(self):
        """
        GET /monthly-reports/{id}/full must always include salary_rows + salary_totals.
        WHY: SalaryGrid component requires both keys (even if lists are empty).
        """
        async with fresh_user_client() as client:
            salon_id = await create_salon(client)

            # Create report
            rpt = await client.post(
                f"/api/salons/{salon_id}/monthly-reports",
                json={"year": 2098, "month": 6, "ca_realise_ttc": "4000", "subventions": "0"},
            )
            assert rpt.status_code == 201, rpt.text
            report_id = rpt.json()["id"]

            # Create an employee
            emp = await client.post(
                f"/api/salons/{salon_id}/employees",
                json={
                    "name": "Paul Dupont",
                    "role_type": "salarie",
                    "contract_type": "cdi",
                    "hours_per_week": 35,
                    "salary_brut": "1800.00",
                    "cotisations_patronales": "540.00",
                    "taux_occupation": "0.65",
                },
            )
            assert emp.status_code == 201, emp.text

            # /full must return salary_rows and salary_totals
            full = await client.get(
                f"/api/salons/{salon_id}/monthly-reports/{report_id}/full",
            )
            assert full.status_code == 200, full.text
            full_data = full.json()
            assert "salary_rows" in full_data, "full endpoint must include salary_rows key"
            assert "salary_totals" in full_data, "full endpoint must include salary_totals key"
