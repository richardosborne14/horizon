"""
Sprint 6 — TASK-6.1 Career History tests.

Tests:
- Career period CRUD (create, list, get, update, soft-delete)
- Pension regime auto-derivation from period_type
- Trimestre estimation per period type
- Overlap detection
- Career summary endpoint
"""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app


@pytest.mark.asyncio
async def test_create_and_list_career_periods():
    """POST and GET /api/career — basic CRUD with regime auto-detection."""
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
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": f"test.career.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "Career Test User",
                },
            )
            assert r.status_code == 201
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            # Create a CDI period (2012–2020, 40k€/year)
            res = await client.post(
                "/api/career",
                json={
                    "period_type": "cdi",
                    "start_date": "2012-09-01",
                    "end_date": "2020-03-15",
                    "employer_name": "Acme Corp",
                    "job_title": "Développeur",
                    "annual_gross": 40000,
                    "is_full_time": True,
                },
                cookies=cookies,
            )
            assert res.status_code == 201, f"Expected 201: {res.text}"
            data = res.json()
            assert data["period_type"] == "cdi"
            assert data["pension_regime"] == "general"
            assert data["employer_name"] == "Acme Corp"
            assert data["duration_years"] > 7.0
            assert data["trimestres_estimated"] >= 28  # ~7.5 years × 4

            # Create an AE period (ongoing, no end_date)
            res2 = await client.post(
                "/api/career",
                json={
                    "period_type": "ae",
                    "start_date": "2020-04-01",
                    "annual_gross": 67200,
                },
                cookies=cookies,
            )
            assert res2.status_code == 201
            data2 = res2.json()
            assert data2["period_type"] == "ae"
            assert data2["pension_regime"] == "ae"
            assert data2["end_date"] is None  # ongoing

            # Create a parental leave period
            res3 = await client.post(
                "/api/career",
                json={
                    "period_type": "parental_leave",
                    "start_date": "2014-06-01",
                    "end_date": "2014-12-31",
                },
                cookies=cookies,
            )
            assert res3.status_code == 201
            assert res3.json()["pension_regime"] == "general"

            # List all periods — should be 3, ordered by start_date
            res4 = await client.get("/api/career", cookies=cookies)
            assert res4.status_code == 200
            periods = res4.json()
            assert len(periods) == 3
            assert periods[0]["period_type"] == "cdi"  # earliest
            assert periods[1]["period_type"] == "parental_leave"
            assert periods[2]["period_type"] == "ae"  # latest

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_career_regime_auto_derivation():
    """Pension regime should be auto-derived from period_type."""
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
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": f"test.regime.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "Regime User",
                },
            )
            assert r.status_code == 201
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            test_cases = [
                ("cdi", "general"),
                ("cdd", "general"),
                ("sasu", "general"),
                ("ae", "ae"),
                ("eirl", "tns"),
                ("eurl", "tns"),
                ("unemployment", "general"),
                ("education", None),
                ("foreign", "foreign"),
            ]

            for period_type, expected_regime in test_cases:
                res = await client.post(
                    "/api/career",
                    json={
                        "period_type": period_type,
                        "start_date": "2000-01-01",
                        "end_date": "2000-12-31",
                    },
                    cookies=cookies,
                )
                assert res.status_code == 201, f"Failed for {period_type}: {res.text}"
                actual_regime = res.json()["pension_regime"]
                if expected_regime is None:
                    assert actual_regime is None, (
                        f"{period_type} should have no regime, got {actual_regime}"
                    )
                else:
                    assert actual_regime == expected_regime, (
                        f"{period_type} regime: expected {expected_regime}, got {actual_regime}"
                    )

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_career_soft_delete_and_filters():
    """Soft-deleted periods should not appear in list or get."""
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
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": f"test.career.del.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "Delete User",
                },
            )
            assert r.status_code == 201
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            res = await client.post(
                "/api/career",
                json={
                    "period_type": "cdi",
                    "start_date": "2010-01-01",
                    "end_date": "2015-12-31",
                },
                cookies=cookies,
            )
            period_id = res.json()["id"]

            # Soft delete
            res2 = await client.delete(f"/api/career/{period_id}", cookies=cookies)
            assert res2.status_code == 204

            # Should not appear in list
            res3 = await client.get("/api/career", cookies=cookies)
            assert len(res3.json()) == 0

            # Should 404 on GET
            res4 = await client.get(f"/api/career/{period_id}", cookies=cookies)
            assert res4.status_code == 404

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_career_overlap_detection():
    """Overlapping periods should be detected (warning only, not blocked)."""
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
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": f"test.overlap.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "Overlap User",
                },
            )
            assert r.status_code == 201
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            # Create CDI 2015–2020
            await client.post(
                "/api/career",
                json={
                    "period_type": "cdi",
                    "start_date": "2015-01-01",
                    "end_date": "2020-12-31",
                },
                cookies=cookies,
            )

            # Create AE 2018–2023 (overlaps with CDI for 2018–2020)
            res = await client.post(
                "/api/career",
                json={
                    "period_type": "ae",
                    "start_date": "2018-06-01",
                    "end_date": "2023-12-31",
                },
                cookies=cookies,
            )
            # The AE should show has_overlap=True and list the CDI's UUID
            ae_period = res.json()
            assert ae_period["has_overlap"] is True, (
                f"Expected overlap, got: {ae_period}"
            )
            assert len(ae_period["overlaps_with"]) >= 1

            # Create a non-overlapping period
            res3 = await client.get("/api/career", cookies=cookies)
            periods = res3.json()
            # CDI should also show overlap
            cdi = [p for p in periods if p["period_type"] == "cdi"][0]
            assert cdi["has_overlap"] is True

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_career_summary():
    """Summary endpoint should return trimestre count and timeline."""
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
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": f"test.summary.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "Summary User",
                },
            )
            assert r.status_code == 201
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            # 8-year CDI at 40k
            await client.post(
                "/api/career",
                json={
                    "period_type": "cdi",
                    "start_date": "2012-01-01",
                    "end_date": "2020-01-01",
                    "annual_gross": 40000,
                },
                cookies=cookies,
            )

            # Ongoing AE
            await client.post(
                "/api/career",
                json={
                    "period_type": "ae",
                    "start_date": "2020-03-01",
                    "annual_gross": 67200,
                },
                cookies=cookies,
            )

            res = await client.get("/api/career/summary", cookies=cookies)
            assert res.status_code == 200
            summary = res.json()
            assert summary["total_periods"] == 2
            assert summary["total_years_worked"] > 13  # 8 + 6+
            assert summary["total_trimestres_estimated"] >= 32  # 8×4 for CDI
            assert summary["trimestres_required"] == 172
            assert summary["pension_regimes"] == ["ae", "general"]
            assert summary["current_period"] is not None
            assert summary["current_period"]["type"] == "ae"

            # Timeline should have entries
            assert len(summary["timeline"]) > 0

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_career_update():
    """PUT /api/career/{id} should support partial update."""
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
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": f"test.update.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "Update User",
                },
            )
            assert r.status_code == 201
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            res = await client.post(
                "/api/career",
                json={
                    "period_type": "cdi",
                    "start_date": "2015-01-01",
                    "end_date": "2018-12-31",
                    "annual_gross": 30000,
                },
                cookies=cookies,
            )
            period_id = res.json()["id"]

            # Update salary
            res2 = await client.put(
                f"/api/career/{period_id}",
                json={"annual_gross": 35000, "job_title": "Senior Dev"},
                cookies=cookies,
            )
            assert res2.status_code == 200
            updated = res2.json()
            assert str(updated["annual_gross"]) in ("35000", "35000.00"), (
                f"Expected ~35000, got {updated['annual_gross']!r}"
            )
            assert updated["job_title"] == "Senior Dev"

            # Other fields unchanged
            assert updated["period_type"] == "cdi"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()