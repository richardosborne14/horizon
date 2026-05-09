"""
Task 2.2: Monthly Report CRUD + Expense Entry tests.

Tests follow the same self-contained pattern as test_task_2_1_employees.py.

Key assertions:
  - Unauthenticated → 401
  - Create monthly report → 201
  - Duplicate month → 409 Conflict
  - Add expense: amount_ht and tva_amount auto-calculated correctly
      amount_ht  = amount_ttc / 1.20   (e.g. 120 TTC → 100 HT)
      tva_amount = amount_ttc - amount_ht   (e.g. 120 TTC → 20 TVA)
  - Update CA recalculates cash_flow in response
  - Delete report cascades expenses
  - Totals computed correctly: expense_total_ttc, tva_encaissee, tva_a_payer
  - Other user's salon returns 404

Run: docker compose exec backend pytest tests/test_task_2_2_monthly_reports.py -v
"""

import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app
from app.services.auth import hash_password


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _cleanup(db: AsyncSession, user_ids: list) -> None:
    """Delete all test data for user_ids — cascade handles salons, reports, expenses."""
    for uid in user_ids:
        await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
    await db.commit()


async def _setup_user_and_salon(client: AsyncClient, email: str, password: str) -> tuple:
    """
    Create a user in DB, log in, create a salon.

    Returns (engine, user_id, cookies, salon_id).
    Caller must dispose engine and cleanup user_ids in finally block.
    """
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async with AsyncSession(engine, expire_on_commit=False) as db:
        from app.models.user import User
        user = User(
            email=email,
            password_hash=hash_password(password),
            name="Test User",
        )
        db.add(user)
        await db.flush()
        user_ids.append(user.id)
        await db.commit()

    login = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, f"Login failed: {login.text}"
    cookies = login.cookies

    salon = await client.post(
        "/api/salons",
        json={"name": "Test Salon Rapports", "business_type": "auto_micro"},
        cookies=cookies,
    )
    assert salon.status_code == 201, f"Salon failed: {salon.text}"

    return engine, user_ids, cookies, salon.json()["id"]


async def _get_first_category_id(client: AsyncClient) -> str:
    """Return the first expense category ID from the static-data endpoint."""
    resp = await client.get("/api/static-data/expense-categories")
    assert resp.status_code == 200, f"Categories failed: {resp.text}"
    categories = resp.json()
    assert len(categories) > 0, "No expense categories seeded — run the seed script"
    return categories[0]["id"]


# ── Test: unauthenticated → 401 ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_monthly_reports_unauthenticated_returns_401():
    """All monthly report endpoints require authentication."""
    import uuid
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        fake_id = uuid.uuid4()
        resp = await client.get(f"/api/salons/{fake_id}/monthly-reports?year=2026")
        assert resp.status_code == 401


# ── Test: create monthly report → 201 ────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_monthly_report():
    """Create a monthly report and verify response structure."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        engine, user_ids, cookies, salon_id = await _setup_user_and_salon(
            client, "test.mr.create@example.com", "TestPass123!"
        )
        try:
            resp = await client.post(
                f"/api/salons/{salon_id}/monthly-reports",
                json={"year": 2026, "month": 1, "ca_realise_ttc": "8500.00", "subventions": "0"},
                cookies=cookies,
            )
            assert resp.status_code == 201, resp.text
            data = resp.json()
            assert data["year"] == 2026
            assert data["month"] == 1
            assert float(data["ca_realise_ttc"]) == 8500.00
            assert data["expenses"] == []
            # Totals should be zero with no expenses
            assert float(data["totals"]["expense_total_ttc"]) == 0.0
            assert data["salon_id"] == salon_id
        finally:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                await _cleanup(db, user_ids)
            await engine.dispose()


# ── Test: duplicate month → 409 ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_duplicate_month_returns_409():
    """Creating a second report for the same month returns 409 Conflict."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        engine, user_ids, cookies, salon_id = await _setup_user_and_salon(
            client, "test.mr.duplicate@example.com", "TestPass123!"
        )
        try:
            payload = {"year": 2026, "month": 3}
            first = await client.post(
                f"/api/salons/{salon_id}/monthly-reports", json=payload, cookies=cookies
            )
            assert first.status_code == 201, first.text

            second = await client.post(
                f"/api/salons/{salon_id}/monthly-reports", json=payload, cookies=cookies
            )
            assert second.status_code == 409, (
                f"Expected 409 for duplicate month, got {second.status_code}: {second.text}"
            )
        finally:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                await _cleanup(db, user_ids)
            await engine.dispose()


# ── Test: add expense — HT and TVA auto-calculated ────────────────────────────


@pytest.mark.asyncio
async def test_expense_ht_tva_auto_calculated():
    """
    Adding an expense with amount_ttc=120 to an auto_micro (AE) salon must
    auto-calculate using tva_rate=0 (AE guard):
        amount_ht  = 120.00  (HT = TTC for AE — no deductible TVA)
        tva_amount = 0.00

    AE guard added in Task 2.8.3: auto-entrepreneurs cannot deduct purchase TVA.
    Verified against 06-social-charges-reference.md AE rules.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        engine, user_ids, cookies, salon_id = await _setup_user_and_salon(
            client, "test.mr.tva@example.com", "TestPass123!"
        )
        try:
            category_id = await _get_first_category_id(client)

            # Create the report
            report_resp = await client.post(
                f"/api/salons/{salon_id}/monthly-reports",
                json={"year": 2026, "month": 4},
                cookies=cookies,
            )
            assert report_resp.status_code == 201, report_resp.text
            report_id = report_resp.json()["id"]

            # Add expense with TTC = 120.00
            exp_resp = await client.post(
                f"/api/salons/{salon_id}/monthly-reports/{report_id}/expenses",
                json={"category_id": category_id, "amount_ttc": "120.00"},
                cookies=cookies,
            )
            assert exp_resp.status_code == 201, exp_resp.text
            data = exp_resp.json()

            # AE guard (Task 2.8.3): tva_rate forced to 0 for auto_micro — HT = TTC
            assert abs(float(data["amount_ht"]) - 120.0) < 0.01, (
                f"Expected amount_ht=120 (AE, no TVA deduction), got {data['amount_ht']}"
            )
            # AE: no deductible TVA on purchases
            assert abs(float(data["tva_amount"]) - 0.0) < 0.01, (
                f"Expected tva_amount=0 (AE), got {data['tva_amount']}"
            )
            assert float(data["amount_ttc"]) == 120.0
        finally:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                await _cleanup(db, user_ids)
            await engine.dispose()


# ── Test: report totals computed correctly ────────────────────────────────────


@pytest.mark.asyncio
async def test_report_totals_computed_correctly():
    """
    With CA=10000 and one expense of 600 TTC (auto_micro / AE salon):
        expense_total_ttc = 600
        expense_total_ht  = 600        (AE guard: HT = TTC, tva_rate=0)
        tva_payee_achats  = 0          (AE cannot deduct purchase TVA)
        tva_encaissee     = 10000 - (10000/1.20) = 1666.666... (CA-side still computed)
        tva_a_payer       = 1666.67 - 0 = 1666.67 approx
        cash_flow         = (10000 + 0) - 600 = 9400

    AE guard added Task 2.8.3. Formulas from 05-calculation-reference.md Section 6.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        engine, user_ids, cookies, salon_id = await _setup_user_and_salon(
            client, "test.mr.totals@example.com", "TestPass123!"
        )
        try:
            category_id = await _get_first_category_id(client)

            # Create report with CA = 10000
            report_resp = await client.post(
                f"/api/salons/{salon_id}/monthly-reports",
                json={"year": 2026, "month": 5, "ca_realise_ttc": "10000.00"},
                cookies=cookies,
            )
            assert report_resp.status_code == 201
            report_id = report_resp.json()["id"]

            # Add single expense: 600 TTC
            await client.post(
                f"/api/salons/{salon_id}/monthly-reports/{report_id}/expenses",
                json={"category_id": category_id, "amount_ttc": "600.00"},
                cookies=cookies,
            )

            # Fetch the full report
            full = await client.get(
                f"/api/salons/{salon_id}/monthly-reports/{report_id}", cookies=cookies
            )
            assert full.status_code == 200, full.text
            t = full.json()["totals"]

            assert abs(float(t["expense_total_ttc"]) - 600.0) < 0.01
            # AE guard: tva_rate=0 → HT = TTC
            assert abs(float(t["expense_total_ht"]) - 600.0) < 0.01
            # AE: no deductible purchase TVA
            assert abs(float(t["tva_payee_achats"]) - 0.0) < 0.01
            # tva_encaissee = 10000 * (1 - 1/1.20) = 10000 * 0.16667 = 1666.67
            assert abs(float(t["tva_encaissee"]) - 1666.67) < 0.10
            # tva_a_payer = 1666.67 - 0 = 1666.67 (AE has no deductible purchase TVA)
            assert abs(float(t["tva_a_payer"]) - 1666.67) < 0.10
            # cash_flow = 10000 - 600 = 9400
            assert abs(float(t["cash_flow"]) - 9400.0) < 0.01
        finally:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                await _cleanup(db, user_ids)
            await engine.dispose()


# ── Test: update CA recalculates totals ───────────────────────────────────────


@pytest.mark.asyncio
async def test_update_ca_reflected_in_totals():
    """Updating ca_realise_ttc changes the totals on subsequent GET."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        engine, user_ids, cookies, salon_id = await _setup_user_and_salon(
            client, "test.mr.update@example.com", "TestPass123!"
        )
        try:
            report_resp = await client.post(
                f"/api/salons/{salon_id}/monthly-reports",
                json={"year": 2026, "month": 6, "ca_realise_ttc": "5000.00"},
                cookies=cookies,
            )
            assert report_resp.status_code == 201
            report_id = report_resp.json()["id"]

            update = await client.put(
                f"/api/salons/{salon_id}/monthly-reports/{report_id}",
                json={"ca_realise_ttc": "7500.00"},
                cookies=cookies,
            )
            assert update.status_code == 200, update.text
            assert float(update.json()["ca_realise_ttc"]) == 7500.00
            # tva_encaissee should now be based on 7500
            tva_enc = float(update.json()["totals"]["tva_encaissee"])
            expected = 7500 * (1 - 1 / 1.2)
            assert abs(tva_enc - expected) < 0.01, f"Expected {expected:.2f}, got {tva_enc}"
        finally:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                await _cleanup(db, user_ids)
            await engine.dispose()


# ── Test: delete report cascades expenses ─────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_report_cascades_expenses():
    """Deleting a report also deletes all its expenses (cascade)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        engine, user_ids, cookies, salon_id = await _setup_user_and_salon(
            client, "test.mr.delete@example.com", "TestPass123!"
        )
        try:
            category_id = await _get_first_category_id(client)

            report_resp = await client.post(
                f"/api/salons/{salon_id}/monthly-reports",
                json={"year": 2026, "month": 7},
                cookies=cookies,
            )
            report_id = report_resp.json()["id"]

            await client.post(
                f"/api/salons/{salon_id}/monthly-reports/{report_id}/expenses",
                json={"category_id": category_id, "amount_ttc": "200.00"},
                cookies=cookies,
            )

            delete = await client.delete(
                f"/api/salons/{salon_id}/monthly-reports/{report_id}", cookies=cookies
            )
            assert delete.status_code == 204

            # Report no longer exists
            get = await client.get(
                f"/api/salons/{salon_id}/monthly-reports/{report_id}", cookies=cookies
            )
            assert get.status_code == 404
        finally:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                await _cleanup(db, user_ids)
            await engine.dispose()


# ── Test: update expense recalculates HT/TVA ─────────────────────────────────


@pytest.mark.asyncio
async def test_update_expense_recalculates_ht_tva():
    """
    Updating amount_ttc from 240 to 360 on AE salon — AE guard keeps tva_rate=0:
        amount_ht  = 360.00  (HT = TTC for AE)
        tva_amount = 0.00    (AE has no deductible purchase TVA)
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        engine, user_ids, cookies, salon_id = await _setup_user_and_salon(
            client, "test.mr.expupdate@example.com", "TestPass123!"
        )
        try:
            category_id = await _get_first_category_id(client)

            report_resp = await client.post(
                f"/api/salons/{salon_id}/monthly-reports",
                json={"year": 2026, "month": 8},
                cookies=cookies,
            )
            report_id = report_resp.json()["id"]

            create_exp = await client.post(
                f"/api/salons/{salon_id}/monthly-reports/{report_id}/expenses",
                json={"category_id": category_id, "amount_ttc": "240.00"},
                cookies=cookies,
            )
            expense_id = create_exp.json()["id"]

            update_exp = await client.put(
                f"/api/salons/{salon_id}/monthly-reports/{report_id}/expenses/{expense_id}",
                json={"amount_ttc": "360.00"},
                cookies=cookies,
            )
            assert update_exp.status_code == 200, update_exp.text
            data = update_exp.json()
            # AE guard: tva_rate=0, so HT = TTC = 360
            assert abs(float(data["amount_ht"]) - 360.0) < 0.01, (
                f"Expected 360 HT (AE: HT=TTC), got {data['amount_ht']}"
            )
            # AE: no deductible purchase TVA
            assert abs(float(data["tva_amount"]) - 0.0) < 0.01, (
                f"Expected 0 TVA (AE), got {data['tva_amount']}"
            )
        finally:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                await _cleanup(db, user_ids)
            await engine.dispose()


# ── Test: other user's salon → 404 ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_other_users_salon_returns_404():
    """User A cannot access User B's salon reports — must return 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        engine_a = create_async_engine(settings.database_url, echo=False)
        engine_b = create_async_engine(settings.database_url, echo=False)
        user_ids = []
        try:
            async with AsyncSession(engine_a, expire_on_commit=False) as db:
                from app.models.user import User
                for email, name in [
                    ("test.mr.usera@example.com", "User A"),
                    ("test.mr.userb@example.com", "User B"),
                ]:
                    u = User(email=email, password_hash=hash_password("TestPass123!"), name=name)
                    db.add(u)
                    await db.flush()
                    user_ids.append(u.id)
                await db.commit()

            # User B creates a salon
            login_b = await client.post(
                "/api/auth/login",
                json={"email": "test.mr.userb@example.com", "password": "TestPass123!"},
            )
            cookies_b = login_b.cookies
            salon_b = await client.post(
                "/api/salons",
                json={"name": "Salon User B", "business_type": "auto_micro"},
                cookies=cookies_b,
            )
            salon_id_b = salon_b.json()["id"]

            # User A logs in and tries to access User B's reports
            login_a = await client.post(
                "/api/auth/login",
                json={"email": "test.mr.usera@example.com", "password": "TestPass123!"},
            )
            cookies_a = login_a.cookies

            resp = await client.get(
                f"/api/salons/{salon_id_b}/monthly-reports?year=2026", cookies=cookies_a
            )
            assert resp.status_code == 404, (
                f"Expected 404, got {resp.status_code}: {resp.text}"
            )
        finally:
            async with AsyncSession(engine_a, expire_on_commit=False) as db:
                await _cleanup(db, user_ids)
            await engine_a.dispose()
            await engine_b.dispose()
