"""
Tests for Task 2.8 (Annual Summary) and Task 2.9 (Duplicate Month).

Follows the self-contained async pattern used throughout Sprint 2:
  - httpx.AsyncClient + ASGITransport
  - Cookie-based auth (no shared fixtures)
  - Each test creates its own user and cleans up

2.8 — GET /api/salons/:id/annual-summary/:year
  - Returns 12-month breakdown even if no data exists
  - Correctly aggregates CA, expenses, salaries, cash flow
  - Category totals include pct_ca percentages
  - has_data=False for months without reports

2.9 — POST /api/salons/:id/monthly-reports/:rid/duplicate
  - Duplicates report to target months
  - Copies expenses (CA, category, amount)
  - Returns created/skipped/errors counts
  - Skips existing months when overwrite=False
  - Overwrites existing months when overwrite=True
  - 422 when target includes source month
  - 422 when target_months is empty or out of range
  - 401 without auth, 403/404 for wrong user

Run:
    docker compose exec backend pytest tests/test_task_2_8_9_annual_duplicate.py -v
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app
from app.services.auth import hash_password


# ── Shared helpers ────────────────────────────────────────────────────────────


async def _make_engine():
    """Create a fresh async engine connected to the test DB."""
    return create_async_engine(settings.database_url, echo=False)


async def _create_user(db: AsyncSession, email: str, name: str = "Test User") -> str:
    """Insert a test user directly into the DB and return its UUID string."""
    from app.models.user import User
    user = User(
        email=email,
        password_hash=hash_password("TestPass123!"),
        name=name,
    )
    db.add(user)
    await db.flush()
    uid = str(user.id)
    await db.commit()
    return uid


async def _cleanup(db: AsyncSession, user_ids: list) -> None:
    """Delete test users — cascade handles all related data."""
    for uid in user_ids:
        await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
    await db.commit()


async def _login(client: AsyncClient, email: str) -> object:
    """Log in and return the response cookies."""
    resp = await client.post(
        "/api/auth/login", json={"email": email, "password": "TestPass123!"}
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.cookies


async def _create_salon(client: AsyncClient, cookies) -> str:
    """Create a salon and return its ID."""
    resp = await client.post(
        "/api/salons",
        json={"name": "Salon Test 2.8-2.9", "business_type": "sarl"},
        cookies=cookies,
    )
    assert resp.status_code == 201, f"Create salon failed: {resp.text}"
    return resp.json()["id"]


async def _create_report(
    client: AsyncClient, cookies, salon_id: str, year: int, month: int, ca: str = "5000.00"
) -> str:
    """Create a monthly report and return its ID."""
    resp = await client.post(
        f"/api/salons/{salon_id}/monthly-reports",
        json={"year": year, "month": month, "ca_realise_ttc": ca, "subventions": "0"},
        cookies=cookies,
    )
    assert resp.status_code == 201, f"Create report failed: {resp.text}"
    return resp.json()["id"]


async def _get_first_category_id(client: AsyncClient, cookies) -> str:
    """Fetch the first expense category ID available."""
    resp = await client.get("/api/static-data/expense-categories", cookies=cookies)
    assert resp.status_code == 200
    cats = resp.json()
    assert len(cats) > 0, "No expense categories found"
    return cats[0]["id"]


async def _add_expense(
    client: AsyncClient, cookies, salon_id: str, report_id: str, cat_id: str, amount: str = "200.00"
) -> None:
    """Add an expense to a monthly report."""
    resp = await client.post(
        f"/api/salons/{salon_id}/monthly-reports/{report_id}/expenses",
        json={"category_id": cat_id, "amount_ttc": amount, "notes": "Test"},
        cookies=cookies,
    )
    assert resp.status_code == 201, f"Add expense failed: {resp.text}"


# ── Task 2.8: Annual Summary ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_annual_summary_empty_year():
    """Annual summary for a year with no reports returns 12 months, all has_data=False."""
    email = f"test28a-{uuid.uuid4().hex[:8]}@test.com"
    engine = await _make_engine()
    user_ids = []
    async with AsyncSession(engine) as db:
        uid = await _create_user(db, email)
        user_ids.append(uid)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            cookies = await _login(c, email)
            salon_id = await _create_salon(c, cookies)

            resp = await c.get(f"/api/salons/{salon_id}/annual-summary/2025", cookies=cookies)
            assert resp.status_code == 200
            data = resp.json()
            assert data["year"] == 2025
            assert data["salon_id"] == salon_id
            assert len(data["months"]) == 12
            assert all(not m["has_data"] for m in data["months"])
            assert data["months_with_data"] == 0
            assert Decimal(data["total_ca"]) == Decimal("0")
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_annual_summary_months_ordered():
    """Month breakdown is always ordered Jan (1) → Dec (12)."""
    email = f"test28b-{uuid.uuid4().hex[:8]}@test.com"
    engine = await _make_engine()
    user_ids = []
    async with AsyncSession(engine) as db:
        uid = await _create_user(db, email)
        user_ids.append(uid)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            cookies = await _login(c, email)
            salon_id = await _create_salon(c, cookies)

            resp = await c.get(f"/api/salons/{salon_id}/annual-summary/2025", cookies=cookies)
            assert resp.status_code == 200
            months = resp.json()["months"]
            assert [m["month"] for m in months] == list(range(1, 13))
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_annual_summary_with_one_report():
    """Annual summary reflects a single report's data correctly."""
    email = f"test28c-{uuid.uuid4().hex[:8]}@test.com"
    engine = await _make_engine()
    user_ids = []
    async with AsyncSession(engine) as db:
        uid = await _create_user(db, email)
        user_ids.append(uid)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            cookies = await _login(c, email)
            salon_id = await _create_salon(c, cookies)
            cat_id = await _get_first_category_id(c, cookies)
            report_id = await _create_report(c, cookies, salon_id, 2025, 3, ca="8000.00")
            await _add_expense(c, cookies, salon_id, report_id, cat_id, amount="1200.00")

            resp = await c.get(f"/api/salons/{salon_id}/annual-summary/2025", cookies=cookies)
            assert resp.status_code == 200
            data = resp.json()

            assert data["months_with_data"] == 1
            assert Decimal(data["total_ca"]) == Decimal("8000.00")

            # March = index 2
            march = data["months"][2]
            assert march["month"] == 3
            assert march["has_data"] is True
            assert Decimal(march["ca_realise_ttc"]) == Decimal("8000.00")
            assert Decimal(march["expense_total_ttc"]) == Decimal("1200.00")
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_annual_summary_multi_month_aggregation():
    """Total CA and expenses aggregate correctly across multiple months."""
    email = f"test28d-{uuid.uuid4().hex[:8]}@test.com"
    engine = await _make_engine()
    user_ids = []
    async with AsyncSession(engine) as db:
        uid = await _create_user(db, email)
        user_ids.append(uid)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            cookies = await _login(c, email)
            salon_id = await _create_salon(c, cookies)
            cat_id = await _get_first_category_id(c, cookies)

            for m in [1, 2, 3]:
                rid = await _create_report(c, cookies, salon_id, 2025, m, ca="5000.00")
                await _add_expense(c, cookies, salon_id, rid, cat_id, amount="500.00")

            resp = await c.get(f"/api/salons/{salon_id}/annual-summary/2025", cookies=cookies)
            assert resp.status_code == 200
            data = resp.json()

            assert data["months_with_data"] == 3
            assert Decimal(data["total_ca"]) == Decimal("15000.00")
            assert Decimal(data["total_expenses"]) == Decimal("1500.00")
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_annual_summary_category_totals():
    """Category totals section lists per-category aggregated expense amounts."""
    email = f"test28e-{uuid.uuid4().hex[:8]}@test.com"
    engine = await _make_engine()
    user_ids = []
    async with AsyncSession(engine) as db:
        uid = await _create_user(db, email)
        user_ids.append(uid)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            cookies = await _login(c, email)
            salon_id = await _create_salon(c, cookies)
            cat_id = await _get_first_category_id(c, cookies)

            for m in [1, 2]:
                rid = await _create_report(c, cookies, salon_id, 2025, m, ca="10000.00")
                await _add_expense(c, cookies, salon_id, rid, cat_id, amount="1000.00")

            resp = await c.get(f"/api/salons/{salon_id}/annual-summary/2025", cookies=cookies)
            assert resp.status_code == 200
            cat_totals = resp.json()["category_totals"]
            assert len(cat_totals) > 0

            our_cat = next((c2 for c2 in cat_totals if c2["category_id"] == cat_id), None)
            assert our_cat is not None
            assert Decimal(our_cat["total_ttc"]) == Decimal("2000.00")
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_annual_summary_category_pct_ca():
    """Category pct_ca is expense/total_ca — sanity check 10% ratio."""
    email = f"test28f-{uuid.uuid4().hex[:8]}@test.com"
    engine = await _make_engine()
    user_ids = []
    async with AsyncSession(engine) as db:
        uid = await _create_user(db, email)
        user_ids.append(uid)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            cookies = await _login(c, email)
            salon_id = await _create_salon(c, cookies)
            cat_id = await _get_first_category_id(c, cookies)
            rid = await _create_report(c, cookies, salon_id, 2025, 1, ca="10000.00")
            await _add_expense(c, cookies, salon_id, rid, cat_id, amount="1000.00")

            resp = await c.get(f"/api/salons/{salon_id}/annual-summary/2025", cookies=cookies)
            cat_totals = resp.json()["category_totals"]
            our_cat = next((c2 for c2 in cat_totals if c2["category_id"] == cat_id), None)
            assert our_cat is not None
            pct = Decimal(our_cat["pct_ca"])
            # 1000 / 10000 = 0.10
            assert abs(pct - Decimal("0.1")) < Decimal("0.001")
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_annual_summary_requires_auth():
    """Annual summary endpoint returns 401 without authentication."""
    email = f"test28g-{uuid.uuid4().hex[:8]}@test.com"
    engine = await _make_engine()
    user_ids = []
    async with AsyncSession(engine) as db:
        uid = await _create_user(db, email)
        user_ids.append(uid)
    try:
        salon_id = None
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            cookies = await _login(c, email)
            salon_id = await _create_salon(c, cookies)

        # WHY new client: AsyncClient stores Set-Cookie from login response in its
        # internal cookie jar. Subsequent requests from the same client would still
        # be authenticated even without explicitly passing cookies=. A fresh client
        # has no cookies → correctly gets 401.
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c2:
            resp = await c2.get(f"/api/salons/{salon_id}/annual-summary/2025")
            assert resp.status_code == 401
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_annual_summary_wrong_user_forbidden():
    """Cannot access another user's salon annual summary."""
    email1 = f"test28h1-{uuid.uuid4().hex[:8]}@test.com"
    email2 = f"test28h2-{uuid.uuid4().hex[:8]}@test.com"
    engine = await _make_engine()
    user_ids = []
    async with AsyncSession(engine) as db:
        uid1 = await _create_user(db, email1)
        uid2 = await _create_user(db, email2)
        user_ids.extend([uid1, uid2])
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            cookies1 = await _login(c, email1)
            cookies2 = await _login(c, email2)
            salon_id = await _create_salon(c, cookies1)

            resp = await c.get(
                f"/api/salons/{salon_id}/annual-summary/2025", cookies=cookies2
            )
            assert resp.status_code in (403, 404)
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


# ── Task 2.9: Duplicate Month ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_duplicate_to_empty_months():
    """Duplicating a report to months with no data creates new reports."""
    email = f"test29a-{uuid.uuid4().hex[:8]}@test.com"
    engine = await _make_engine()
    user_ids = []
    async with AsyncSession(engine) as db:
        uid = await _create_user(db, email)
        user_ids.append(uid)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            cookies = await _login(c, email)
            salon_id = await _create_salon(c, cookies)
            cat_id = await _get_first_category_id(c, cookies)
            rid = await _create_report(c, cookies, salon_id, 2025, 1, ca="6000.00")
            await _add_expense(c, cookies, salon_id, rid, cat_id, amount="300.00")

            resp = await c.post(
                f"/api/salons/{salon_id}/monthly-reports/{rid}/duplicate",
                json={"target_months": [2, 3], "overwrite": False},
                cookies=cookies,
            )
            assert resp.status_code == 200
            result = resp.json()
            assert result["created"] == 2
            assert result["skipped"] == 0
            assert result["errors"] == 0
            assert set(result["created_months"]) == {2, 3}
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_duplicate_copies_ca():
    """Duplicated report inherits CA from the source month."""
    email = f"test29b-{uuid.uuid4().hex[:8]}@test.com"
    engine = await _make_engine()
    user_ids = []
    async with AsyncSession(engine) as db:
        uid = await _create_user(db, email)
        user_ids.append(uid)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            cookies = await _login(c, email)
            salon_id = await _create_salon(c, cookies)
            rid = await _create_report(c, cookies, salon_id, 2025, 1, ca="7500.00")

            await c.post(
                f"/api/salons/{salon_id}/monthly-reports/{rid}/duplicate",
                json={"target_months": [4], "overwrite": False},
                cookies=cookies,
            )

            # Check April report
            summary_resp = await c.get(
                f"/api/salons/{salon_id}/monthly-reports?year=2025", cookies=cookies
            )
            reports = summary_resp.json()
            april = next((r for r in reports if r["month"] == 4), None)
            assert april is not None
            assert Decimal(april["ca_realise_ttc"]) == Decimal("7500.00")
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_duplicate_copies_expenses():
    """Duplicated report gets copies of all expenses from the source."""
    email = f"test29c-{uuid.uuid4().hex[:8]}@test.com"
    engine = await _make_engine()
    user_ids = []
    async with AsyncSession(engine) as db:
        uid = await _create_user(db, email)
        user_ids.append(uid)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            cookies = await _login(c, email)
            salon_id = await _create_salon(c, cookies)
            cat_id = await _get_first_category_id(c, cookies)
            rid = await _create_report(c, cookies, salon_id, 2025, 1, ca="5000.00")
            await _add_expense(c, cookies, salon_id, rid, cat_id, amount="400.00")
            await _add_expense(c, cookies, salon_id, rid, cat_id, amount="600.00")

            await c.post(
                f"/api/salons/{salon_id}/monthly-reports/{rid}/duplicate",
                json={"target_months": [6], "overwrite": False},
                cookies=cookies,
            )

            summary_resp = await c.get(
                f"/api/salons/{salon_id}/monthly-reports?year=2025", cookies=cookies
            )
            june_summary = next((r for r in summary_resp.json() if r["month"] == 6), None)
            assert june_summary is not None
            assert june_summary["expense_count"] == 2
            assert Decimal(june_summary["expense_total_ttc"]) == Decimal("1000.00")
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_duplicate_skips_existing_without_overwrite():
    """When overwrite=False, existing months are skipped (not overwritten)."""
    email = f"test29d-{uuid.uuid4().hex[:8]}@test.com"
    engine = await _make_engine()
    user_ids = []
    async with AsyncSession(engine) as db:
        uid = await _create_user(db, email)
        user_ids.append(uid)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            cookies = await _login(c, email)
            salon_id = await _create_salon(c, cookies)
            source_rid = await _create_report(c, cookies, salon_id, 2025, 1, ca="5000.00")
            # Pre-create February with different CA
            await _create_report(c, cookies, salon_id, 2025, 2, ca="9999.00")

            resp = await c.post(
                f"/api/salons/{salon_id}/monthly-reports/{source_rid}/duplicate",
                json={"target_months": [2, 3], "overwrite": False},
                cookies=cookies,
            )
            assert resp.status_code == 200
            result = resp.json()
            assert result["created"] == 1    # March created
            assert result["skipped"] == 1    # February skipped
            assert 2 in result["skipped_months"]
            assert 3 in result["created_months"]

            # Verify February unchanged
            summary_resp = await c.get(
                f"/api/salons/{salon_id}/monthly-reports?year=2025", cookies=cookies
            )
            feb = next(r for r in summary_resp.json() if r["month"] == 2)
            assert Decimal(feb["ca_realise_ttc"]) == Decimal("9999.00")
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_duplicate_overwrites_when_flag_true():
    """When overwrite=True, existing months are replaced with source data."""
    email = f"test29e-{uuid.uuid4().hex[:8]}@test.com"
    engine = await _make_engine()
    user_ids = []
    async with AsyncSession(engine) as db:
        uid = await _create_user(db, email)
        user_ids.append(uid)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            cookies = await _login(c, email)
            salon_id = await _create_salon(c, cookies)
            source_rid = await _create_report(c, cookies, salon_id, 2025, 1, ca="5000.00")
            await _create_report(c, cookies, salon_id, 2025, 2, ca="9999.00")

            resp = await c.post(
                f"/api/salons/{salon_id}/monthly-reports/{source_rid}/duplicate",
                json={"target_months": [2], "overwrite": True},
                cookies=cookies,
            )
            assert resp.status_code == 200
            result = resp.json()
            assert result["created"] == 1
            assert result["skipped"] == 0

            # February now has source CA
            summary_resp = await c.get(
                f"/api/salons/{salon_id}/monthly-reports?year=2025", cookies=cookies
            )
            feb = next(r for r in summary_resp.json() if r["month"] == 2)
            assert Decimal(feb["ca_realise_ttc"]) == Decimal("5000.00")
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_duplicate_cannot_target_source_month():
    """Targeting the source month itself returns a 422 validation error."""
    email = f"test29f-{uuid.uuid4().hex[:8]}@test.com"
    engine = await _make_engine()
    user_ids = []
    async with AsyncSession(engine) as db:
        uid = await _create_user(db, email)
        user_ids.append(uid)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            cookies = await _login(c, email)
            salon_id = await _create_salon(c, cookies)
            rid = await _create_report(c, cookies, salon_id, 2025, 1)

            resp = await c.post(
                f"/api/salons/{salon_id}/monthly-reports/{rid}/duplicate",
                json={"target_months": [1], "overwrite": False},
                cookies=cookies,
            )
            assert resp.status_code == 422
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_duplicate_requires_auth():
    """Duplicate endpoint returns 401 without authentication."""
    email = f"test29g-{uuid.uuid4().hex[:8]}@test.com"
    engine = await _make_engine()
    user_ids = []
    async with AsyncSession(engine) as db:
        uid = await _create_user(db, email)
        user_ids.append(uid)
    try:
        salon_id = None
        rid = None
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            cookies = await _login(c, email)
            salon_id = await _create_salon(c, cookies)
            rid = await _create_report(c, cookies, salon_id, 2025, 1)

        # WHY new client: same reason as test_annual_summary_requires_auth —
        # the login Set-Cookie is stored in c's cookie jar. A fresh client has
        # no cookies and will correctly receive 401.
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c2:
            resp = await c2.post(
                f"/api/salons/{salon_id}/monthly-reports/{rid}/duplicate",
                json={"target_months": [2], "overwrite": False},
            )
            assert resp.status_code == 401
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_duplicate_wrong_user_forbidden():
    """Cannot duplicate another user's report."""
    email1 = f"test29h1-{uuid.uuid4().hex[:8]}@test.com"
    email2 = f"test29h2-{uuid.uuid4().hex[:8]}@test.com"
    engine = await _make_engine()
    user_ids = []
    async with AsyncSession(engine) as db:
        uid1 = await _create_user(db, email1)
        uid2 = await _create_user(db, email2)
        user_ids.extend([uid1, uid2])
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            cookies1 = await _login(c, email1)
            cookies2 = await _login(c, email2)
            salon_id = await _create_salon(c, cookies1)
            rid = await _create_report(c, cookies1, salon_id, 2025, 1)

            resp = await c.post(
                f"/api/salons/{salon_id}/monthly-reports/{rid}/duplicate",
                json={"target_months": [2], "overwrite": False},
                cookies=cookies2,
            )
            assert resp.status_code in (403, 404)
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_duplicate_invalid_target_months():
    """Target months outside 1-12 return 422."""
    email = f"test29i-{uuid.uuid4().hex[:8]}@test.com"
    engine = await _make_engine()
    user_ids = []
    async with AsyncSession(engine) as db:
        uid = await _create_user(db, email)
        user_ids.append(uid)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            cookies = await _login(c, email)
            salon_id = await _create_salon(c, cookies)
            rid = await _create_report(c, cookies, salon_id, 2025, 1)

            resp = await c.post(
                f"/api/salons/{salon_id}/monthly-reports/{rid}/duplicate",
                json={"target_months": [0, 13], "overwrite": False},
                cookies=cookies,
            )
            assert resp.status_code == 422
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_duplicate_empty_target_months():
    """Empty target_months list returns 422."""
    email = f"test29j-{uuid.uuid4().hex[:8]}@test.com"
    engine = await _make_engine()
    user_ids = []
    async with AsyncSession(engine) as db:
        uid = await _create_user(db, email)
        user_ids.append(uid)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            cookies = await _login(c, email)
            salon_id = await _create_salon(c, cookies)
            rid = await _create_report(c, cookies, salon_id, 2025, 1)

            resp = await c.post(
                f"/api/salons/{salon_id}/monthly-reports/{rid}/duplicate",
                json={"target_months": [], "overwrite": False},
                cookies=cookies,
            )
            assert resp.status_code == 422
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_duplicate_is_flagged():
    """Duplicated reports have is_duplicate=True in their full data."""
    email = f"test29k-{uuid.uuid4().hex[:8]}@test.com"
    engine = await _make_engine()
    user_ids = []
    async with AsyncSession(engine) as db:
        uid = await _create_user(db, email)
        user_ids.append(uid)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            cookies = await _login(c, email)
            salon_id = await _create_salon(c, cookies)
            rid = await _create_report(c, cookies, salon_id, 2025, 1)

            await c.post(
                f"/api/salons/{salon_id}/monthly-reports/{rid}/duplicate",
                json={"target_months": [5], "overwrite": False},
                cookies=cookies,
            )

            summary_resp = await c.get(
                f"/api/salons/{salon_id}/monthly-reports?year=2025", cookies=cookies
            )
            may_summary = next((r for r in summary_resp.json() if r["month"] == 5), None)
            assert may_summary is not None

            full_resp = await c.get(
                f"/api/salons/{salon_id}/monthly-reports/{may_summary['id']}/full",
                cookies=cookies,
            )
            assert full_resp.status_code == 200
            assert full_resp.json()["report"]["is_duplicate"] is True
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()
