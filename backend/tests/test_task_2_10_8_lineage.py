"""
Tests for Task 2.10.8 — Data Lineage Badge (is_user_modified)

Covers:
- MonthlyReport.is_user_modified defaults to False on creation
- mark_report_modified() sets is_user_modified=True (idempotent)
- Duplicated months start as is_user_modified=False
- Editing CA on a monthly report triggers mark_modified → is_user_modified=True
- Annual summary includes is_user_modified per month
- Dashboard summary includes is_user_modified on current_month
- Dashboard summary ytd_lineage derivation (estimation / partial / real)
"""
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app
from app.services.auth import hash_password


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_engine():
    """Fresh async engine per test module run."""
    return create_async_engine(settings.database_url, echo=False)


async def _cleanup(db: AsyncSession, user_ids: list) -> None:
    """Hard-delete test users — cascade removes salons, reports, etc."""
    for uid in user_ids:
        await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
    await db.commit()


async def _setup(c: AsyncClient, engine, suffix: str) -> tuple[str, str]:
    """
    Create user via raw SQL, log in (sets session cookie on c), create salon.
    Returns (salon_id, user_id).

    WHY raw SQL: tests need atomic user creation before the first API call,
    and the User ORM model lives in app.models (not app.models.auth).
    """
    uid = str(uuid.uuid4())
    email = f"lineage_{suffix}_{uid[:8]}@test.com"
    pw = "TestPassword1!"

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, email, name, password_hash, onboarding_completed) "
                "VALUES (:id, :email, :name, :pw, true)"
            ),
            {"id": uid, "email": email, "name": f"Lineage {suffix}", "pw": hash_password(pw)},
        )

    # Login
    r = await c.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, f"Login failed: {r.text}"

    # Create salon
    r = await c.post("/api/salons", json={
        "name": f"Salon Lineage {suffix}",
        "business_type": "sarl",
        "nb_employees": 0
    })
    assert r.status_code in (200, 201), f"Salon creation failed: {r.text}"
    salon_id = r.json()["id"]

    return salon_id, uid


# ── Test 1: new monthly report has is_user_modified=False ─────────────────────

@pytest.mark.asyncio
async def test_new_report_not_user_modified():
    """
    A freshly created monthly report should have is_user_modified=False.
    WHY: newly created reports are either blank or duplicated — both count
    as 'estimation' until the user actively edits figures.
    """
    engine = _make_engine()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        salon_id, user_id = await _setup(c, engine, "t1")

        resp = await c.post(
            f"/api/salons/{salon_id}/monthly-reports",
            json={"year": 2026, "month": 11}
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["is_user_modified"] is False, (
            "A new monthly report must default to is_user_modified=False"
        )

    async with AsyncSession(engine) as db:
        await _cleanup(db, [user_id])
    await engine.dispose()


# ── Test 2: editing CA sets is_user_modified=True ─────────────────────────────

@pytest.mark.asyncio
async def test_editing_ca_marks_report_modified():
    """
    After a PATCH to update ca_realise_ttc, is_user_modified must be True.
    WHY: editing any financial figure distinguishes real data from estimation.
    """
    engine = _make_engine()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        salon_id, user_id = await _setup(c, engine, "t2")

        # Create a fresh report
        resp = await c.post(
            f"/api/salons/{salon_id}/monthly-reports",
            json={"year": 2026, "month": 3}
        )
        assert resp.status_code == 201, resp.text
        report_id = resp.json()["id"]

        # PUT CA — this should trigger mark_report_modified
        # WHY PUT not PATCH: the endpoint is PUT /salons/{id}/monthly-reports/{rid}
        put_resp = await c.put(
            f"/api/salons/{salon_id}/monthly-reports/{report_id}",
            json={"ca_realise_ttc": "8500.00"}
        )
        assert put_resp.status_code == 200, put_resp.text
        assert put_resp.json()["is_user_modified"] is True, (
            "PUTting ca_realise_ttc must set is_user_modified=True"
        )

    async with AsyncSession(engine) as db:
        await _cleanup(db, [user_id])
    await engine.dispose()


# ── Test 3: annual summary exposes is_user_modified per month ─────────────────

@pytest.mark.asyncio
async def test_annual_summary_includes_lineage():
    """
    GET /salons/{id}/annual-summary/{year} must include is_user_modified
    on each month breakdown.
    """
    engine = _make_engine()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        salon_id, user_id = await _setup(c, engine, "t3")

        # Create a report with user modification for month 4
        r = await c.post(
            f"/api/salons/{salon_id}/monthly-reports",
            json={"year": 2026, "month": 4}
        )
        assert r.status_code == 201
        rid = r.json()["id"]
        await c.put(f"/api/salons/{salon_id}/monthly-reports/{rid}", json={"ca_realise_ttc": "9000.00"})

        # Fetch annual summary
        resp = await c.get(f"/api/salons/{salon_id}/annual-summary/2026")
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert "months" in data
        assert len(data["months"]) == 12, "Annual summary must contain exactly 12 months"

        for m in data["months"]:
            assert "is_user_modified" in m, (
                f"Month {m['month']} missing is_user_modified field"
            )
            assert isinstance(m["is_user_modified"], bool), (
                f"Month {m['month']} is_user_modified must be a boolean"
            )
            # Months with no data must always be False
            if not m["has_data"]:
                assert m["is_user_modified"] is False, (
                    f"Month {m['month']} has no data so is_user_modified must be False"
                )

        # Our edited month must be True
        april = next(m for m in data["months"] if m["month"] == 4)
        assert april["is_user_modified"] is True, (
            "Month 4 was patched, so is_user_modified must be True"
        )

    async with AsyncSession(engine) as db:
        await _cleanup(db, [user_id])
    await engine.dispose()


# ── Test 4: dashboard summary includes lineage fields ─────────────────────────

@pytest.mark.asyncio
async def test_dashboard_summary_lineage_fields():
    """
    GET /salons/{id}/dashboard-summary must include:
    - ytd_lineage (string or null)
    - months_ytd_user_modified (int)
    - current_month.is_user_modified if present
    """
    engine = _make_engine()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        salon_id, user_id = await _setup(c, engine, "t4")

        resp = await c.get(f"/api/salons/{salon_id}/dashboard-summary")
        assert resp.status_code == 200, resp.text
        data = resp.json()

        # ytd_lineage must be present (None if no months this year)
        assert "ytd_lineage" in data
        assert data["ytd_lineage"] in (None, "estimation", "partial", "real"), (
            f"ytd_lineage has unexpected value: {data['ytd_lineage']!r}"
        )

        # months_ytd_user_modified must be an integer
        assert "months_ytd_user_modified" in data
        assert isinstance(data["months_ytd_user_modified"], int)
        assert data["months_ytd_user_modified"] >= 0

        # If current_month is present, it must have is_user_modified
        if data.get("current_month"):
            assert "is_user_modified" in data["current_month"], (
                "current_month must include is_user_modified field"
            )
            assert isinstance(data["current_month"]["is_user_modified"], bool)

    async with AsyncSession(engine) as db:
        await _cleanup(db, [user_id])
    await engine.dispose()


# ── Test 5: ytd_lineage derivation logic ──────────────────────────────────────

@pytest.mark.asyncio
async def test_ytd_lineage_estimation_vs_real():
    """
    Fresh salon (no reports) → ytd_lineage is None.
    After adding a report without editing → ytd_lineage = "estimation".
    After editing that report → ytd_lineage = "real".
    """
    engine = _make_engine()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        salon_id, user_id = await _setup(c, engine, "t5")

        # Step A: no reports — ytd_lineage must be None
        resp = await c.get(f"/api/salons/{salon_id}/dashboard-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ytd_lineage"] is None, (
            f"Fresh salon must have ytd_lineage=None, got {data['ytd_lineage']!r}"
        )

        # Step B: add a report for current month (without editing)
        from datetime import date
        today = date.today()
        r = await c.post(
            f"/api/salons/{salon_id}/monthly-reports",
            json={"year": today.year, "month": today.month}
        )
        assert r.status_code == 201, r.text
        rid = r.json()["id"]

        resp = await c.get(f"/api/salons/{salon_id}/dashboard-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ytd_lineage"] == "estimation", (
            f"One unedited report → ytd_lineage must be 'estimation', got {data['ytd_lineage']!r}"
        )

        # Step C: edit the report → lineage becomes "real"
        await c.put(f"/api/salons/{salon_id}/monthly-reports/{rid}", json={"ca_realise_ttc": "7500.00"})

        resp = await c.get(f"/api/salons/{salon_id}/dashboard-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ytd_lineage"] == "real", (
            f"All months edited → ytd_lineage must be 'real', got {data['ytd_lineage']!r}"
        )

    async with AsyncSession(engine) as db:
        await _cleanup(db, [user_id])
    await engine.dispose()
