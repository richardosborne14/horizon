"""
Sprint 7 — TASK-7.5 Income Source Model & API tests.

Tests:
- CRUD (create, list, get, update, soft-delete)
- Earner filter (?earner=user|spouse)
- Summary aggregation (monthly, annual, one_time handling)
- Auto-creation from existing monthly_gross_ca
- sync_profile_ca updates profile correctly
- Confidence filtering in summary
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app


# ── Helpers ────────────────────────────────────────────────────────────────────


async def _register_and_get_cookies(client: AsyncClient, suffix: str = ""):
    """Register a user and return cookies for auth."""
    email = f"test.income.{uuid.uuid4().hex[:6]}{suffix}@example.com"
    r = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "TestPass123!",
            "name": "Income Test User",
        },
    )
    assert r.status_code == 201, f"Register failed: {r.text}"
    user_id = uuid.UUID(r.json()["user"]["id"])
    return r.cookies, user_id, email


async def _set_profile_ca(cookies, monthly_ca: Decimal):
    """Set the user's monthly_gross_ca on their profile."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # First GET to create the profile
        await client.get("/api/profile", cookies=cookies)
        # Then PUT to set CA
        res = await client.put(
            "/api/profile",
            json={"monthly_gross_ca": str(monthly_ca)},
            cookies=cookies,
        )
        assert res.status_code == 200, f"Profile PUT failed: {res.text}"


# ── CRUD Tests ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_and_list_income_sources():
    """POST and GET /api/income-sources."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            cookies, user_id, _ = await _register_and_get_cookies(client, ".c1")

            async with AsyncSession(engine, expire_on_commit=False) as db:
                user_ids.append(user_id)

            # Ensure profile exists (no CA set)
            r = await client.get("/api/profile", cookies=cookies)
            assert r.status_code == 200

            # Create an income source
            res = await client.post(
                "/api/income-sources",
                json={
                    "label": "Client Alpha",
                    "source_type": "client",
                    "amount": "5000.00",
                    "frequency": "monthly",
                    "confidence": "high",
                    "earner": "user",
                    "is_ae_revenue": True,
                },
                cookies=cookies,
            )
            assert res.status_code == 201, f"Expected 201: {res.text}"
            data = res.json()
            assert data["label"] == "Client Alpha"
            assert Decimal(data["amount"]) == Decimal("5000.00")
            assert data["earner"] == "user"
            assert data["frequency"] == "monthly"
            assert data["confidence"] == "high"
            assert data["source_type"] == "client"
            assert data["is_ae_revenue"] is True

            # List all sources
            res2 = await client.get("/api/income-sources", cookies=cookies)
            assert res2.status_code == 200
            sources = res2.json()
            assert len(sources) == 1
            assert sources[0]["label"] == "Client Alpha"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_update_income_source():
    """PUT /api/income-sources/{id} — partial update."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            cookies, user_id, _ = await _register_and_get_cookies(client, ".c2")
            user_ids.append(user_id)

            await client.get("/api/profile", cookies=cookies)

            # Create
            res = await client.post(
                "/api/income-sources",
                json={
                    "label": "Client Beta",
                    "amount": "3000.00",
                    "frequency": "monthly",
                },
                cookies=cookies,
            )
            source_id = res.json()["id"]

            # Update amount and confidence
            res2 = await client.put(
                f"/api/income-sources/{source_id}",
                json={
                    "amount": "4000.00",
                    "confidence": "medium",
                },
                cookies=cookies,
            )
            assert res2.status_code == 200, f"Expected 200: {res2.text}"
            updated = res2.json()
            assert Decimal(updated["amount"]) == Decimal("4000.00")
            assert updated["confidence"] == "medium"
            assert updated["label"] == "Client Beta"  # unchanged

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_delete_income_source():
    """DELETE /api/income-sources/{id} — soft delete."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            cookies, user_id, _ = await _register_and_get_cookies(client, ".c3")
            user_ids.append(user_id)

            await client.get("/api/profile", cookies=cookies)

            res = await client.post(
                "/api/income-sources",
                json={"label": "To delete", "amount": "100.00", "frequency": "monthly"},
                cookies=cookies,
            )
            source_id = res.json()["id"]

            # Delete
            res2 = await client.delete(
                f"/api/income-sources/{source_id}", cookies=cookies
            )
            assert res2.status_code == 204

            # List should be empty
            res3 = await client.get("/api/income-sources", cookies=cookies)
            assert res3.status_code == 200
            assert len(res3.json()) == 0

            # GET by ID should 404
            res4 = await client.get(
                f"/api/income-sources/{source_id}", cookies=cookies
            )
            assert res4.status_code == 404

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_get_by_id():
    """GET /api/income-sources/{id}."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            cookies, user_id, _ = await _register_and_get_cookies(client, ".c4")
            user_ids.append(user_id)

            await client.get("/api/profile", cookies=cookies)

            res = await client.post(
                "/api/income-sources",
                json={
                    "label": "Gamma",
                    "amount": "2500.50",
                    "frequency": "monthly",
                    "source_type": "product",
                },
                cookies=cookies,
            )
            source_id = res.json()["id"]

            res2 = await client.get(
                f"/api/income-sources/{source_id}", cookies=cookies
            )
            assert res2.status_code == 200
            assert res2.json()["id"] == source_id
            assert res2.json()["label"] == "Gamma"

            # Non-existent ID returns 404
            fake_id = str(uuid.uuid4())
            res3 = await client.get(
                f"/api/income-sources/{fake_id}", cookies=cookies
            )
            assert res3.status_code == 404

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


# ── Earner Filter Tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_earner_filter():
    """GET /api/income-sources?earner=user and ?earner=spouse."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            cookies, user_id, _ = await _register_and_get_cookies(client, ".c5")
            user_ids.append(user_id)

            await client.get("/api/profile", cookies=cookies)

            # Create user source
            await client.post(
                "/api/income-sources",
                json={
                    "label": "My Client",
                    "amount": "5000.00",
                    "frequency": "monthly",
                    "earner": "user",
                },
                cookies=cookies,
            )

            # Create spouse source
            await client.post(
                "/api/income-sources",
                json={
                    "label": "Spouse Job",
                    "amount": "3000.00",
                    "frequency": "monthly",
                    "earner": "spouse",
                    "is_ae_revenue": False,
                },
                cookies=cookies,
            )

            # Filter user only
            res_user = await client.get(
                "/api/income-sources?earner=user", cookies=cookies
            )
            assert res_user.status_code == 200
            user_sources = res_user.json()
            assert len(user_sources) == 1
            assert user_sources[0]["label"] == "My Client"

            # Filter spouse only
            res_spouse = await client.get(
                "/api/income-sources?earner=spouse", cookies=cookies
            )
            assert res_spouse.status_code == 200
            spouse_sources = res_spouse.json()
            assert len(spouse_sources) == 1
            assert spouse_sources[0]["label"] == "Spouse Job"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


# ── Summary Tests ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_summary_aggregation():
    """GET /api/income-sources/summary — correct aggregation."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            cookies, user_id, _ = await _register_and_get_cookies(client, ".c6")
            user_ids.append(user_id)

            await client.get("/api/profile", cookies=cookies)

            # Create: user with 3 monthly sources (5000 + 2000 + 1500 = 8500)
            await client.post(
                "/api/income-sources",
                json={"label": "Client A", "amount": "5000.00", "frequency": "monthly", "confidence": "high", "earner": "user"},
                cookies=cookies,
            )
            await client.post(
                "/api/income-sources",
                json={"label": "Client B", "amount": "2000.00", "frequency": "monthly", "confidence": "high", "earner": "user"},
                cookies=cookies,
            )
            await client.post(
                "/api/income-sources",
                json={"label": "Prospect X", "amount": "1500.00", "frequency": "monthly", "confidence": "low", "earner": "user"},
                cookies=cookies,
            )

            # Create: spouse with 1 monthly source
            await client.post(
                "/api/income-sources",
                json={"label": "Spouse CDI", "amount": "2800.00", "frequency": "monthly", "confidence": "high", "earner": "spouse", "is_ae_revenue": False},
                cookies=cookies,
            )

            # Get summary
            res = await client.get("/api/income-sources/summary", cookies=cookies)
            assert res.status_code == 200, f"Expected 200: {res.text}"
            summary = res.json()

            # User
            assert Decimal(summary["user"]["current_monthly_total"]) == Decimal("8500.00")
            assert summary["user"]["sources_count"] == 3
            assert Decimal(summary["user"]["guaranteed_monthly"]) == Decimal("7000.00")
            assert Decimal(summary["user"]["speculative_monthly"]) == Decimal("1500.00")

            # Spouse
            assert summary["spouse"] is not None
            assert Decimal(summary["spouse"]["current_monthly_total"]) == Decimal("2800.00")
            assert summary["spouse"]["sources_count"] == 1

            # Household
            assert Decimal(summary["household_monthly_total"]) == Decimal("11300.00")

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_summary_annual_source_divided_by_12():
    """Annual sources should be divided by 12 in monthly totals."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            cookies, user_id, _ = await _register_and_get_cookies(client, ".c7")
            user_ids.append(user_id)

            await client.get("/api/profile", cookies=cookies)

            # Monthly: 3000
            await client.post(
                "/api/income-sources",
                json={"label": "Monthly Client", "amount": "3000.00", "frequency": "monthly", "earner": "user"},
                cookies=cookies,
            )
            # Annual: 36000 → 3000/month
            await client.post(
                "/api/income-sources",
                json={"label": "Annual Contract", "amount": "36000.00", "frequency": "annual", "earner": "user"},
                cookies=cookies,
            )
            # One-time: excluded from monthly
            await client.post(
                "/api/income-sources",
                json={"label": "Asset Sale", "amount": "50000.00", "frequency": "one_time", "earner": "user"},
                cookies=cookies,
            )

            res = await client.get("/api/income-sources/summary", cookies=cookies)
            summary = res.json()

            # 3000 + (36000/12) = 3000 + 3000 = 6000
            assert Decimal(summary["user"]["current_monthly_total"]) == Decimal("6000.00")
            assert summary["user"]["sources_count"] == 3  # monthly + annual + one_time count

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_summary_ending_within_12_months():
    """Sources ending within 12 months should be flagged."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            cookies, user_id, _ = await _register_and_get_cookies(client, ".c8")
            user_ids.append(user_id)

            await client.get("/api/profile", cookies=cookies)

            today = date.today()
            ends_soon = today + timedelta(days=200)  # within 12 months
            ends_late = today + timedelta(days=730)  # 2 years out

            await client.post(
                "/api/income-sources",
                json={
                    "label": "Ending Soon",
                    "amount": "2000.00",
                    "frequency": "monthly",
                    "end_date": ends_soon.isoformat(),
                    "earner": "user",
                },
                cookies=cookies,
            )
            await client.post(
                "/api/income-sources",
                json={
                    "label": "Long Term",
                    "amount": "3000.00",
                    "frequency": "monthly",
                    "end_date": ends_late.isoformat(),
                    "earner": "user",
                },
                cookies=cookies,
            )

            res = await client.get("/api/income-sources/summary", cookies=cookies)
            summary = res.json()

            ending_soon = summary["user"]["ending_within_12_months"]
            assert len(ending_soon) == 1
            assert ending_soon[0]["label"] == "Ending Soon"
            assert ending_soon[0]["ends"] == ends_soon.isoformat()

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


# ── Auto-Migration Tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_auto_create_from_ca():
    """When no sources exist but profile has monthly_gross_ca, auto-create one."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            cookies, user_id, _ = await _register_and_get_cookies(client, ".c9")
            user_ids.append(user_id)

            # Set profile CA to 4200
            await _set_profile_ca(cookies, Decimal("4200.00"))

            # First GET — should auto-create from CA
            res = await client.get("/api/income-sources", cookies=cookies)
            assert res.status_code == 200
            sources = res.json()
            assert len(sources) == 1
            assert sources[0]["label"] == "Activité principale"
            assert Decimal(sources[0]["amount"]) == Decimal("4200.00")
            assert sources[0]["earner"] == "user"

            # Second GET — should NOT create a duplicate
            res2 = await client.get("/api/income-sources", cookies=cookies)
            assert res2.status_code == 200
            assert len(res2.json()) == 1

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_sync_profile_ca():
    """After creating/updating/deleting sources, profile.monthly_gross_ca is synced."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            cookies, user_id, _ = await _register_and_get_cookies(client, ".c10")
            user_ids.append(user_id)

            await client.get("/api/profile", cookies=cookies)

            # Create 2 monthly AE sources: 3000 + 2000 = 5000
            await client.post(
                "/api/income-sources",
                json={"label": "Client 1", "amount": "3000.00", "frequency": "monthly", "is_ae_revenue": True, "earner": "user"},
                cookies=cookies,
            )
            await client.post(
                "/api/income-sources",
                json={"label": "Client 2", "amount": "2000.00", "frequency": "monthly", "is_ae_revenue": True, "earner": "user"},
                cookies=cookies,
            )

            # Check profile CA
            res = await client.get("/api/profile", cookies=cookies)
            assert Decimal(res.json()["monthly_gross_ca"]) == Decimal("5000.00")

            # Add an annual AE source: 12000/year = 1000/month
            res2 = await client.post(
                "/api/income-sources",
                json={"label": "Annual Retainer", "amount": "12000.00", "frequency": "annual", "is_ae_revenue": True, "earner": "user"},
                cookies=cookies,
            )
            source_id = res2.json()["id"]

            # Now monthly CA should be: 3000 + 2000 + (12000/12) = 6000
            res3 = await client.get("/api/profile", cookies=cookies)
            assert Decimal(res3.json()["monthly_gross_ca"]) == Decimal("6000.00")

            # Delete one source
            await client.delete(
                f"/api/income-sources/{source_id}", cookies=cookies
            )

            # Back to 5000
            res4 = await client.get("/api/profile", cookies=cookies)
            assert Decimal(res4.json()["monthly_gross_ca"]) == Decimal("5000.00")

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_summary_no_spouse():
    """Summary should return null spouse when no spouse sources exist."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            cookies, user_id, _ = await _register_and_get_cookies(client, ".c11")
            user_ids.append(user_id)

            await client.get("/api/profile", cookies=cookies)

            # Only user source
            await client.post(
                "/api/income-sources",
                json={"label": "My CA", "amount": "4000.00", "frequency": "monthly", "earner": "user"},
                cookies=cookies,
            )

            res = await client.get("/api/income-sources/summary", cookies=cookies)
            summary = res.json()
            assert summary["spouse"] is None
            assert Decimal(summary["household_monthly_total"]) == Decimal("4000.00")

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()