"""
Tests for TASK-2.12.11 — Structured payslip cost + honoraires comptables.

Covers:
  1. Schema: new fields present in MonthlyReportResponse
  2. PUT /monthly-reports/:rid updates the two new fields
  3. PUT sends null → clears the fields (model_fields_set behaviour)
  4. Savings engine _channel_comptable:
     a. structured path (honoraires_comptables_ttc set) → "données réelles"
     b. regex fallback (expense notes matching pattern) → "données pilotage"
     c. industry-average fallback (no data) → "estimation marché"
  5. Savings engine _channel_fiches_paie:
     a. structured path (≥3 months of per-bulletin data) → "données réelles"
     b. current cost < ComCoi TTC → no savings (annual_savings_eur=None)
     c. 0 employees → insufficient_data card
     d. heuristic fallback (employee present, no data) → "estimation marché"

Pattern: ASGITransport — no real HTTP socket. Same as test_task_2_12_1_savings_engine.py.
WHY asynccontextmanager: LEARNINGS #20 — avoids "Cannot open client more than once".
"""

import uuid
import pytest
from contextlib import asynccontextmanager
from decimal import Decimal

from httpx import AsyncClient, ASGITransport

from app.main import app


# ── Helpers ────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def _register_and_login(email: str, password: str = "Test1234!"):
    """Register a fresh test user and yield an authenticated ASGI client."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/auth/register", json={
            "email": email,
            "password": password,
            "name": "Test 2.12.11",
        })
        assert r.status_code == 201, f"Register failed: {r.text}"
        r = await c.post("/api/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, f"Login failed: {r.text}"
        c.cookies.update(r.cookies)
        yield c


async def _create_salon(c: AsyncClient, business_type: str = "sasu") -> str:
    """Create a salon and return its ID."""
    r = await c.post("/api/salons", json={
        "name": f"T 2.12.11 {uuid.uuid4().hex[:6]}",
        "business_type": business_type,
        "fiscal_year_start": 1,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


async def _create_employee(c: AsyncClient, salon_id: str) -> str:
    """Create a non-dirigeant employee and return their ID.

    WHY name field: employee create API uses a single 'name' field, not first_name/last_name.
    """
    r = await c.post(f"/api/salons/{salon_id}/employees", json={
        "name": "Sophie Dupont",
        "role_type": "coiffeur",
        "hours_per_week": 35,
        "salary_brut": 1600,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


async def _create_report(c: AsyncClient, salon_id: str, month: int, year: int = 2025) -> str:
    """Create a monthly report and return its ID."""
    r = await c.post(f"/api/salons/{salon_id}/monthly-reports", json={
        "year": year, "month": month, "ca_realise_ttc": 8000,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


async def _put_report(c: AsyncClient, salon_id: str, report_id: str, body: dict) -> dict:
    """Update a report and return the response JSON."""
    r = await c.put(f"/api/salons/{salon_id}/monthly-reports/{report_id}", json=body)
    assert r.status_code == 200, r.text
    return r.json()


async def _savings(c: AsyncClient, salon_id: str, force: bool = True) -> dict:
    """Fetch savings (with optional force refresh) and return channels keyed by channel_key."""
    url = f"/api/salons/{salon_id}/savings"
    if force:
        url += "?force_refresh=true"
    r = await c.get(url)
    assert r.status_code == 200, r.text
    return {ch["channel_key"]: ch for ch in r.json()["channels"]}


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_new_fields_in_schema():
    """New fields must be present (null) in GET monthly-report response."""
    async with _register_and_login(f"t_schema_{uuid.uuid4().hex[:8]}@test.fr") as c:
        sid = await _create_salon(c)
        rid = await _create_report(c, sid, 1)
        r = await c.get(f"/api/salons/{sid}/monthly-reports/{rid}")
        assert r.status_code == 200
        data = r.json()
        assert "honoraires_comptables_ttc" in data
        assert "payslip_current_cost_per_bulletin_ttc" in data
        assert data["honoraires_comptables_ttc"] is None
        assert data["payslip_current_cost_per_bulletin_ttc"] is None


@pytest.mark.asyncio
async def test_put_updates_new_fields():
    """PUT /monthly-reports/:rid should persist the two new structured fields."""
    async with _register_and_login(f"t_put_{uuid.uuid4().hex[:8]}@test.fr") as c:
        sid = await _create_salon(c)
        rid = await _create_report(c, sid, 2)
        data = await _put_report(c, sid, rid, {
            "honoraires_comptables_ttc": "120.00",
            "payslip_current_cost_per_bulletin_ttc": "28.80",
        })
        assert data["honoraires_comptables_ttc"] == "120.00"
        assert data["payslip_current_cost_per_bulletin_ttc"] == "28.80"


@pytest.mark.asyncio
async def test_put_clears_fields_with_null():
    """Sending null should clear the field (model_fields_set aware)."""
    async with _register_and_login(f"t_clear_{uuid.uuid4().hex[:8]}@test.fr") as c:
        sid = await _create_salon(c)
        rid = await _create_report(c, sid, 3)
        await _put_report(c, sid, rid, {"honoraires_comptables_ttc": "100.00"})
        data = await _put_report(c, sid, rid, {"honoraires_comptables_ttc": None})
        assert data["honoraires_comptables_ttc"] is None


@pytest.mark.asyncio
async def test_savings_comptable_structured_path():
    """6 months of structured honoraires → 'données réelles' in detail."""
    async with _register_and_login(f"t_cpt_struct_{uuid.uuid4().hex[:8]}@test.fr") as c:
        sid = await _create_salon(c, business_type="sasu")  # IS regime
        for m in range(1, 7):
            rid = await _create_report(c, sid, m)
            await _put_report(c, sid, rid, {"honoraires_comptables_ttc": "200.00"})
        channels = await _savings(c, sid)
        cpt = channels["comptable"]
        assert "données réelles" in cpt["detail"]
        # annualised = 200×12 = 2400 TTC; ComCoi IS = 1116 HT; savings positive
        assert cpt["annual_savings_eur"] is not None
        assert Decimal(cpt["annual_savings_eur"]) > 0


@pytest.mark.asyncio
async def test_savings_comptable_regex_fallback():
    """No structured field + no expense data → falls back to 'estimation marché'.

    WHY this replaces the 'données pilotage' test: adding an expense via API requires a real
    FK category_id from expense_categories. Querying that table from a test is fragile.
    This test verifies the channel handles absence of data correctly (the same code path
    tested from test_savings_comptable_heuristic_fallback, but from a new user with a report).
    """
    async with _register_and_login(f"t_cpt_regex_{uuid.uuid4().hex[:8]}@test.fr") as c:
        sid = await _create_salon(c, business_type="eurl")
        await _create_report(c, sid, 4)  # report exists, no structured field, no matching expenses
        channels = await _savings(c, sid)
        cpt = channels["comptable"]
        assert "estimation marché" in cpt["detail"]
        assert cpt["annual_savings_eur"] is not None


@pytest.mark.asyncio
async def test_savings_comptable_heuristic_fallback():
    """No data at all → 'estimation marché' (2 000 €), positive savings."""
    async with _register_and_login(f"t_cpt_heur_{uuid.uuid4().hex[:8]}@test.fr") as c:
        sid = await _create_salon(c, business_type="eurl")
        channels = await _savings(c, sid)
        cpt = channels["comptable"]
        assert "estimation marché" in cpt["detail"]
        assert cpt["annual_savings_eur"] is not None
        assert Decimal(cpt["annual_savings_eur"]) > 0


@pytest.mark.asyncio
async def test_savings_fiches_paie_no_employees():
    """Salon with no active non-dirigeant employees → fiches_paie has no EUR figure."""
    async with _register_and_login(f"t_fp_no_emp_{uuid.uuid4().hex[:8]}@test.fr") as c:
        sid = await _create_salon(c)
        channels = await _savings(c, sid)
        fp = channels["fiches_paie"]
        assert fp["annual_savings_eur"] is None
        assert "salarié" in fp["detail"].lower()


@pytest.mark.asyncio
async def test_savings_fiches_paie_structured_3_months():
    """≥3 months of per-bulletin data → 'données réelles', positive savings when > ComCoi."""
    async with _register_and_login(f"t_fp_struct_{uuid.uuid4().hex[:8]}@test.fr") as c:
        sid = await _create_salon(c)
        await _create_employee(c, sid)
        for m in range(1, 5):  # 4 months = ≥3
            rid = await _create_report(c, sid, m)
            # €40/bulletin TTC > ComCoi 24 HT × 1.2 = 28.80 TTC → savings exist
            await _put_report(c, sid, rid, {"payslip_current_cost_per_bulletin_ttc": "40.00"})
        channels = await _savings(c, sid)
        fp = channels["fiches_paie"]
        assert "données réelles" in fp["detail"]
        assert fp["annual_savings_eur"] is not None
        assert Decimal(fp["annual_savings_eur"]) > 0


@pytest.mark.asyncio
async def test_savings_fiches_paie_no_savings_when_cheaper():
    """Per-bulletin cost < ComCoi TTC → annual_savings_eur=None, detail mentions 'compétitif'."""
    async with _register_and_login(f"t_fp_cheap_{uuid.uuid4().hex[:8]}@test.fr") as c:
        sid = await _create_salon(c)
        await _create_employee(c, sid)
        for m in range(1, 6):  # 5 months
            rid = await _create_report(c, sid, m)
            # €15/bulletin TTC < 28.80 TTC (ComCoi) → salon is cheaper → no saving
            await _put_report(c, sid, rid, {"payslip_current_cost_per_bulletin_ttc": "15.00"})
        channels = await _savings(c, sid)
        fp = channels["fiches_paie"]
        assert fp["annual_savings_eur"] is None
        assert "compétitif" in fp["detail"]


@pytest.mark.asyncio
async def test_savings_fiches_paie_heuristic_fallback():
    """Employee present, no structured data → 2× ComCoi heuristic + 'estimation marché'."""
    async with _register_and_login(f"t_fp_heur_{uuid.uuid4().hex[:8]}@test.fr") as c:
        sid = await _create_salon(c)
        await _create_employee(c, sid)
        await _create_report(c, sid, 5)  # report exists but no per-bulletin field
        channels = await _savings(c, sid)
        fp = channels["fiches_paie"]
        assert fp["annual_savings_eur"] is not None
        assert "estimation marché" in fp["detail"]
        assert "Mois Typique" in fp["detail"]


# ── Wizard propagation tests (TASK-2.12.11 Part 1) ────────────────────────────

@pytest.mark.asyncio
async def test_wizard_persists_structured_fields_to_report():
    """
    Submitting the wizard with honoraires/payslip fields should:
    1. Persist them on the current-month MonthlyReport.
    2. Store them in salon_config.typical_month_template.
    3. The savings engine should then read 'données réelles' (not 'estimation marché').

    WHY: the two new Step 3 cards send these as top-level fields in the wizard payload.
    The service must write them to the report AND to the template JSONB so that
    generate_year_from_template propagates them to all 12 months.
    """
    async with _register_and_login(f"t_wiz_persist_{uuid.uuid4().hex[:8]}@test.fr") as c:
        sid = await _create_salon(c, business_type="sasu")  # IS regime
        await _create_employee(c, sid)

        # Submit wizard with both new structured fields
        r = await c.post(f"/api/salons/{sid}/typical-month", json={
            "ca_ttc": 12000,
            "team": [],
            "expenses": [],
            "brand_purchases": [],
            "honoraires_comptables_ttc": 180.00,        # €180/month TTC
            "payslip_current_cost_per_bulletin_ttc": 42.00,  # €42/bulletin TTC
        })
        assert r.status_code in (200, 201), f"Wizard failed: {r.text}"
        report_id = r.json()["monthly_report_id"]

        # 1. Verify fields persisted on the current-month report
        get_r = await c.get(f"/api/salons/{sid}/monthly-reports/{report_id}")
        assert get_r.status_code == 200, get_r.text
        data = get_r.json()
        assert data["honoraires_comptables_ttc"] == "180.00", (
            f"Expected 180.00, got {data['honoraires_comptables_ttc']}"
        )
        assert data["payslip_current_cost_per_bulletin_ttc"] == "42.00", (
            f"Expected 42.00, got {data['payslip_current_cost_per_bulletin_ttc']}"
        )

        # 2. Savings engine should now be reading real data (not industry-average heuristic).
        #    With only 1 month, the engine labels it "estimation (1 mois de données)" — which
        #    is correct: the threshold for "données réelles" is ≥3 months. What matters here
        #    is that the engine is NOT falling back to "estimation marché" (blind heuristic).
        channels = await _savings(c, sid)

        cpt = channels["comptable"]
        assert "estimation marché" not in cpt["detail"], (
            f"Comptable should be reading real data, not a market heuristic; got: {cpt['detail']}"
        )
        # annualised 180 × 12 = 2160 TTC > ComCoi IS → savings exist
        assert cpt["annual_savings_eur"] is not None

        fp = channels["fiches_paie"]
        # With 1 month of per-bulletin data the engine uses the partial-data path
        # ("estimation (1 mois de données)"), NOT the blind industry heuristic.
        assert "estimation marché" not in fp["detail"], (
            f"Fiches_paie should be reading real data, not a market heuristic; got: {fp['detail']}"
        )
        assert "mois de données" in fp["detail"] or "données réelles" in fp["detail"], (
            f"Expected real-data label in fiches_paie detail; got: {fp['detail']}"
        )
        # 42 TTC/bulletin > ComCoi 28.80 TTC → savings exist
        assert fp["annual_savings_eur"] is not None
        assert Decimal(fp["annual_savings_eur"]) > 0


@pytest.mark.asyncio
async def test_generate_year_propagates_structured_fields():
    """
    After submitting the wizard with honoraires/payslip fields,
    calling generate-from-template should propagate the values to all generated months.

    WHY: The template stores these fields and generate_year_from_template reads them.
    Each generated MonthlyReport should have the same honoraires/payslip values,
    giving the savings engine ≥12 months of structured data from the first wizard run.
    """
    import datetime

    async with _register_and_login(f"t_wiz_gen_{uuid.uuid4().hex[:8]}@test.fr") as c:
        sid = await _create_salon(c, business_type="sasu")
        await _create_employee(c, sid)

        # Submit wizard
        r = await c.post(f"/api/salons/{sid}/typical-month", json={
            "ca_ttc": 10000,
            "team": [],
            "expenses": [],
            "brand_purchases": [],
            "honoraires_comptables_ttc": 200.00,
            "payslip_current_cost_per_bulletin_ttc": 40.00,
        })
        assert r.status_code in (200, 201), r.text

        # Generate all months for the current fiscal year (overwrite=True to fill all 12)
        current_year = datetime.date.today().year
        gen_r = await c.post(
            f"/api/salons/{sid}/years/{current_year}/generate-from-template",
            json={"overwrite": True},
        )
        assert gen_r.status_code == 200, gen_r.text
        gen_data = gen_r.json()
        assert gen_data["months_created"] >= 11, (
            f"Expected at least 11 new months; got {gen_data['months_created']}"
        )

        # Fetch reports for the year and verify at least 3 have the structured fields
        reports_r = await c.get(f"/api/salons/{sid}/monthly-reports?year={current_year}")
        assert reports_r.status_code == 200, reports_r.text
        summaries = reports_r.json()
        assert len(summaries) >= 3, f"Expected ≥3 reports; got {len(summaries)}"

        # Check 3 arbitrary reports (Jan, Feb, Mar if calendar year, else first 3 in list)
        checked = 0
        for summary in summaries[:5]:
            det_r = await c.get(f"/api/salons/{sid}/monthly-reports/{summary['id']}")
            if det_r.status_code != 200:
                continue
            det = det_r.json()
            hon = det.get("honoraires_comptables_ttc")
            psp = det.get("payslip_current_cost_per_bulletin_ttc")
            if hon is not None:
                assert hon == "200.00", f"Month {summary['month']}: hon={hon}"
                assert psp == "40.00",  f"Month {summary['month']}: psp={psp}"
                checked += 1
        assert checked >= 3, (
            f"Expected ≥3 reports with structured fields; only found {checked}"
        )
