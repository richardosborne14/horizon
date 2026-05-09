"""
TASK-2.9.7 — Regression tests: Cash flow consistency across all three views.

Bug reported by Eric:
    Modifying figures in the month view showed -580€ cash flow,
    but returning to the year grid still showed 5211€ — the old value
    using the simplified formula (CA − expenses only, no salaries).

Root cause:
    list_monthly_reports used `(CA + subv) − expenses_TTC` (no salaries).
    get_monthly_report_full and get_annual_summary both used compute_full_point_mort
    (salaries + expenses + emprunt + URSSAF).

Fix (TASK-2.9.7):
    list_monthly_reports now uses compute_full_point_mort — same as the other two.

These tests verify that all three endpoints return IDENTICAL cash_flow values
for the same month, and that the cash_flow figure correctly includes salaries.

Pattern: self-contained tests (each creates its own user/salon/data), matching
the pattern of test_task_2_2_monthly_reports.py.
"""

import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app
from app.services.auth import hash_password


pytestmark = pytest.mark.asyncio


# ── Shared helpers ─────────────────────────────────────────────────────────────


async def _setup_user_salon(email: str, password: str, client: AsyncClient) -> tuple:
    """
    Create a test user in DB, log in, create a salon.

    Returns (engine, user_ids, cookies, salon_id) for cleanup and use.
    Caller MUST dispose engine and delete user_ids in a finally block.
    """
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async with AsyncSession(engine, expire_on_commit=False) as db:
        from app.models.user import User
        user = User(
            email=email,
            password_hash=hash_password(password),
            name="Test CashFlow User",
        )
        db.add(user)
        await db.flush()
        user_ids.append(user.id)
        await db.commit()

    login = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, f"Login failed: {login.text}"
    cookies = login.cookies

    salon_resp = await client.post(
        "/api/salons",
        json={"name": "Salon CashFlow Test", "business_type": "sarl"},
        cookies=cookies,
    )
    assert salon_resp.status_code == 201, f"Salon creation failed: {salon_resp.text}"
    salon_id = salon_resp.json()["id"]

    return engine, user_ids, cookies, salon_id


async def _cleanup(engine, user_ids: list) -> None:
    """Delete test users (cascade removes salons, reports, expenses)."""
    async with AsyncSession(engine, expire_on_commit=False) as db:
        for uid in user_ids:
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()
    await engine.dispose()


async def _get_first_category_id(client: AsyncClient) -> str:
    """Return the first available expense category ID."""
    resp = await client.get("/api/static-data/expense-categories")
    assert resp.status_code == 200
    cats = resp.json()
    assert len(cats) > 0, "No expense categories found — seed missing?"
    return cats[0]["id"]


@pytest.fixture
def client():
    """HTTPX async client hitting the FastAPI app directly."""
    import asyncio
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ── Tests ──────────────────────────────────────────────────────────────────────


class TestCashFlowConsistency:
    """
    TASK-2.9.7 — Verify all three views return the same cash flow.

    WHY the old formula produced wrong results:
        Simplified: cash_flow = (CA + subv) − expenses_TTC
        Full (correct): cash_flow = ca_ht − (salaries + expenses_ht + urssaf + emprunt)

        For a SARL with CA_TTC=10000, expenses_TTC=3000 (20% TVA), emprunt=500:
          Simplified:     10000 − 3000 = 7000€          ← WRONG (old bug, excluded emprunt)
          Old (TTC-based): 10000 − (0 + 3000 + 500) = 6500€  ← fixed emprunt, but still TTC
          New (HT-based):  8333.33 − (0 + 2500 + 500) = 5333.33€  ← TASK-2.15.1 fix
    """

    async def test_list_cash_flow_matches_full_view(self, client: AsyncClient):
        """
        The list endpoint's cash_flow must match the full endpoint's cash_flow.

        This test would have FAILED before TASK-2.9.7 when emprunt=500:
        Old list formula: 10000 − 3000 = 7000€
        Full formula:     10000 − (3000 + 500) = 6500€
        """
        async with client as c:
            engine, user_ids, cookies, salon_id = await _setup_user_salon(
                "cashflow_test1@example.com", "Password123!", c
            )
            try:
                cat_id = await _get_first_category_id(c)

                # Create report with emprunt so old vs new formula differs
                report_resp = await c.post(
                    f"/api/salons/{salon_id}/monthly-reports",
                    json={
                        "year": 2029,
                        "month": 7,
                        "ca_realise_ttc": "10000.00",
                        "subventions": "0",
                        "remboursement_emprunt": "500.00",
                    },
                    cookies=cookies,
                )
                assert report_resp.status_code == 201, report_resp.text
                report_id = report_resp.json()["id"]

                # Add an expense
                expense_resp = await c.post(
                    f"/api/salons/{salon_id}/monthly-reports/{report_id}/expenses",
                    json={"category_id": cat_id, "amount_ttc": "3000.00", "tva_rate": "0.200"},
                    cookies=cookies,
                )
                assert expense_resp.status_code == 201, expense_resp.text

                # ── Get cash flow from list endpoint ───────────────────────────
                list_resp = await c.get(
                    f"/api/salons/{salon_id}/monthly-reports?year=2029",
                    cookies=cookies,
                )
                assert list_resp.status_code == 200
                summaries = list_resp.json()
                july = next((s for s in summaries if s["month"] == 7), None)
                assert july is not None, "Month 7 not found in list response"
                list_cash_flow = Decimal(july["cash_flow"])

                # ── Get cash flow from full endpoint ───────────────────────────
                full_resp = await c.get(
                    f"/api/salons/{salon_id}/monthly-reports/{report_id}/full",
                    cookies=cookies,
                )
                assert full_resp.status_code == 200
                full_cash_flow = Decimal(full_resp.json()["point_mort"]["cash_flow"])

                # ── Get cash flow from annual summary ──────────────────────────
                annual_resp = await c.get(
                    f"/api/salons/{salon_id}/annual-summary/2029",
                    cookies=cookies,
                )
                assert annual_resp.status_code == 200
                annual_months = annual_resp.json()["months"]
                july_annual = next((m for m in annual_months if m["month"] == 7), None)
                assert july_annual is not None
                annual_cash_flow = Decimal(july_annual["cash_flow"])

                # ── Core assertion: all three must agree ───────────────────────
                assert list_cash_flow == full_cash_flow, (
                    f"TASK-2.9.7 REGRESSION: list({list_cash_flow}) != full({full_cash_flow}). "
                    "The old bug excluded emprunt+salaries from list view cash flow."
                )
                assert list_cash_flow == annual_cash_flow, (
                    f"TASK-2.9.7 REGRESSION: list({list_cash_flow}) != annual({annual_cash_flow})."
                )

                # Also assert emprunt is actually included (cash_flow < ca_ht − expenses_ht)
                # CA_TTC=10000, expenses_TTC=3000 (20%→HT=2500), emprunt=500
                # ca_ht=8333.33, CF = 8333.33 − (2500+500) = 5333.33 (TASK-2.15.1)
                assert list_cash_flow == Decimal("5333.33"), (
                    f"Expected 5333.33 (ca_ht−expenses_ht−emprunt), got {list_cash_flow}. "
                    "Emprunt not being included in point mort OR formula not HT-based."
                )

            finally:
                await _cleanup(engine, user_ids)

    async def test_list_summary_has_point_mort_field(self, client: AsyncClient):
        """
        MonthlyReportSummary must include point_mort field (added in TASK-2.9.7).
        cash_flow = ca_realise_ttc - point_mort must hold exactly.
        """
        async with client as c:
            engine, user_ids, cookies, salon_id = await _setup_user_salon(
                "cashflow_test2@example.com", "Password123!", c
            )
            try:
                cat_id = await _get_first_category_id(c)

                report_resp = await c.post(
                    f"/api/salons/{salon_id}/monthly-reports",
                    json={
                        "year": 2029,
                        "month": 8,
                        "ca_realise_ttc": "8000.00",
                        "subventions": "0",
                        "remboursement_emprunt": "200.00",
                    },
                    cookies=cookies,
                )
                assert report_resp.status_code == 201
                report_id = report_resp.json()["id"]

                await c.post(
                    f"/api/salons/{salon_id}/monthly-reports/{report_id}/expenses",
                    json={"category_id": cat_id, "amount_ttc": "2000.00", "tva_rate": "0.200"},
                    cookies=cookies,
                )

                list_resp = await c.get(
                    f"/api/salons/{salon_id}/monthly-reports?year=2029",
                    cookies=cookies,
                )
                assert list_resp.status_code == 200
                summaries = list_resp.json()
                aug = next((s for s in summaries if s["month"] == 8), None)
                assert aug is not None

                # Field must exist
                assert "point_mort" in aug, (
                    "MonthlyReportSummary missing 'point_mort' — schema not updated (TASK-2.9.7)"
                )

                # cash_flow = ca_ht − point_mort (TASK-2.15.1: HT basis)
                # ca_realise_ttc in list is TTC; point_mort and cash_flow use HT.
                ca_ttc = Decimal(aug["ca_realise_ttc"])
                pm = Decimal(aug["point_mort"])
                cf = Decimal(aug["cash_flow"])
                ca_ht = (ca_ttc / Decimal("1.2")).quantize(Decimal("0.01"))
                assert round(cf, 2) == round(ca_ht - pm, 2), (
                    f"cash_flow ({cf}) should equal ca_ht ({ca_ht}) − point_mort ({pm})"
                )

                # Also: list == full
                full_resp = await c.get(
                    f"/api/salons/{salon_id}/monthly-reports/{report_id}/full",
                    cookies=cookies,
                )
                assert full_resp.status_code == 200
                full_cf = Decimal(full_resp.json()["point_mort"]["cash_flow"])
                assert cf == full_cf, f"list CF ({cf}) != full CF ({full_cf})"

            finally:
                await _cleanup(engine, user_ids)

    async def test_all_three_endpoints_consistent_after_ca_update(self, client: AsyncClient):
        """
        After updating CA on a report, all three views must reflect the same
        new cash_flow value — this directly tests Eric's reported bug scenario.

        Eric's bug: modifying numbers on month view showed new cash_flow,
        but the year grid still showed the old value.
        """
        async with client as c:
            engine, user_ids, cookies, salon_id = await _setup_user_salon(
                "cashflow_test3@example.com", "Password123!", c
            )
            try:
                cat_id = await _get_first_category_id(c)

                # Create report with initial CA
                report_resp = await c.post(
                    f"/api/salons/{salon_id}/monthly-reports",
                    json={
                        "year": 2029,
                        "month": 4,  # April — Eric's month
                        "ca_realise_ttc": "15000.00",
                        "subventions": "0",
                        "remboursement_emprunt": "1000.00",
                    },
                    cookies=cookies,
                )
                assert report_resp.status_code == 201
                report_id = report_resp.json()["id"]

                # Add expense
                await c.post(
                    f"/api/salons/{salon_id}/monthly-reports/{report_id}/expenses",
                    json={"category_id": cat_id, "amount_ttc": "5000.00", "tva_rate": "0.200"},
                    cookies=cookies,
                )

                # Update CA — this is Eric's "modification"
                update_resp = await c.put(
                    f"/api/salons/{salon_id}/monthly-reports/{report_id}",
                    json={"ca_realise_ttc": "12000.00"},
                    cookies=cookies,
                )
                assert update_resp.status_code == 200

                # ── All three views after the update ───────────────────────────
                list_resp = await c.get(
                    f"/api/salons/{salon_id}/monthly-reports?year=2029",
                    cookies=cookies,
                )
                april = next((s for s in list_resp.json() if s["month"] == 4), None)
                assert april is not None
                list_cf = Decimal(april["cash_flow"])

                full_resp = await c.get(
                    f"/api/salons/{salon_id}/monthly-reports/{report_id}/full",
                    cookies=cookies,
                )
                full_cf = Decimal(full_resp.json()["point_mort"]["cash_flow"])

                annual_resp = await c.get(
                    f"/api/salons/{salon_id}/annual-summary/2029",
                    cookies=cookies,
                )
                april_annual = next(
                    (m for m in annual_resp.json()["months"] if m["month"] == 4), None
                )
                assert april_annual is not None
                annual_cf = Decimal(april_annual["cash_flow"])

                # ALL THREE must agree
                assert list_cf == full_cf, (
                    f"After CA update: list CF ({list_cf}) != full CF ({full_cf}). "
                    "This is exactly Eric's bug — year grid not reflecting changes."
                )
                assert list_cf == annual_cf, (
                    f"After CA update: list CF ({list_cf}) != annual CF ({annual_cf})."
                )

                # Expected (TASK-2.15.1 HT fix): CA_TTC=12000 → ca_ht=10000,
                # expenses_TTC=5000 (20%→HT=4166.67), emprunt=1000
                # point_mort = 4166.67 + 1000 = 5166.67, CF = 10000 − 5166.67 = 4833.33
                assert list_cf == Decimal("4833.33"), (
                    f"Expected 4833.33 (ca_ht−expenses_ht−emprunt), got {list_cf}. "
                    "Check point mort formula (TASK-2.15.1: HT basis)."
                )

            finally:
                await _cleanup(engine, user_ids)
