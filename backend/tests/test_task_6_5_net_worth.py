"""
Sprint 6 — TASK-6.5 Net Worth Snapshot tests.

Tests:
- CRUD (GET, PUT upsert)
- GET returns default zeros when no snapshot exists
- PUT creates new snapshot, subsequent PUT updates it
- Summary endpoint aggregates investments + loans + net worth fields
- Buffer adequacy includes extra cash from net worth snapshot
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app


@pytest.mark.asyncio
async def test_get_net_worth_empty():
    """GET /api/net-worth without any snapshot → returns default zeros."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM net_worth_snapshots WHERE user_id = '{uid}'"))
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": f"test.nw.empty.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "NW Empty",
                },
            )
            assert r.status_code == 201
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            res = await client.get("/api/net-worth", cookies=cookies)
            assert res.status_code == 200
            data = res.json()

            # Should return zeros — no snapshot created yet
            assert Decimal(data["cash_current_accounts"]) == Decimal("0")
            assert Decimal(data["cash_savings_other"]) == Decimal("0")
            assert Decimal(data["property_primary_value"]) == Decimal("0")
            assert Decimal(data["business_value"]) == Decimal("0")
            assert Decimal(data["other_debts"]) == Decimal("0")

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_put_and_get_net_worth():
    """PUT /api/net-worth creates snapshot, GET returns it."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM net_worth_snapshots WHERE user_id = '{uid}'"))
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": f"test.nw.put.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "NW Put User",
                },
            )
            assert r.status_code == 201
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            # Create snapshot
            res = await client.put(
                "/api/net-worth",
                json={
                    "cash_current_accounts": 5000,
                    "cash_savings_other": 10000,
                    "property_primary_value": 200000,
                    "business_value": 15000,
                    "vehicle_value": 5000,
                    "other_debts": 3000,
                    "other_debts_label": "Prêt familial",
                    "snapshot_date": "2026-05-09",
                },
                cookies=cookies,
            )
            assert res.status_code == 200, f"Expected 200: {res.text}"
            data = res.json()
            assert str(data["cash_current_accounts"]) in ("5000", "5000.00")
            assert str(data["property_primary_value"]) in ("200000", "200000.00")
            assert data["other_debts_label"] == "Prêt familial"
            assert data["snapshot_date"] == "2026-05-09"

            snapshot_id = data["id"]

            # GET should return the same data
            res2 = await client.get("/api/net-worth", cookies=cookies)
            assert res2.status_code == 200
            data2 = res2.json()
            assert data2["id"] == snapshot_id

            # Update snapshot (second PUT should update, not create)
            res3 = await client.put(
                "/api/net-worth",
                json={
                    "cash_current_accounts": 7000,
                    "cash_savings_other": 10000,
                    "property_primary_value": 210000,
                    "snapshot_date": "2026-06-15",
                },
                cookies=cookies,
            )
            assert res3.status_code == 200
            data3 = res3.json()
            # Same ID — upsert
            assert data3["id"] == snapshot_id
            assert str(data3["cash_current_accounts"]) in ("7000", "7000.00")
            assert str(data3["property_primary_value"]) in ("210000", "210000.00")

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_net_worth_summary_empty():
    """Summary endpoint without any data → all zeros."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM net_worth_snapshots WHERE user_id = '{uid}'"))
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": f"test.nw.summary.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "Summary Empty",
                },
            )
            assert r.status_code == 201
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            res = await client.get("/api/net-worth/summary", cookies=cookies)
            assert res.status_code == 200
            summary = res.json()

            assert Decimal(str(summary["total_assets"])) == Decimal("0")
            assert Decimal(str(summary["total_debts"])) == Decimal("0")
            assert Decimal(str(summary["net_worth"])) == Decimal("0")
            assert summary["assets_breakdown"]["liquidites"] == 0
            assert summary["assets_breakdown"]["placements"] == 0
            assert summary["debts_breakdown"]["credits_restants"] == 0

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_net_worth_summary_with_data():
    """Summary endpoint aggregates net worth + investments + loans."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM investment_allocations WHERE user_id = '{uid}'"))
            await db.execute(text(f"DELETE FROM loans WHERE user_id = '{uid}'"))
            await db.execute(text(f"DELETE FROM net_worth_snapshots WHERE user_id = '{uid}'"))
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": f"test.nw.full.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "Full NW User",
                },
            )
            assert r.status_code == 201
            uid = r.json()["user"]["id"]
            user_ids.append(uuid.UUID(uid))
            cookies = r.cookies

            # Create net worth snapshot
            await client.put(
                "/api/net-worth",
                json={
                    "cash_current_accounts": 5000,
                    "cash_savings_other": 10000,
                    "property_primary_value": 200000,
                    "business_value": 15000,
                    "snapshot_date": "2026-05-09",
                },
                cookies=cookies,
            )

            # Create a loan with remaining balance
            await client.post(
                "/api/loans",
                json={
                    "label": "Crédit immobilier",
                    "loan_type": "mortgage",
                    "monthly_payment": 500,
                    "start_date": "2022-01-01",
                    "end_date": "2035-12-31",
                    "remaining_balance": 85000,
                },
                cookies=cookies,
            )

            # The summary should include the loan
            res = await client.get("/api/net-worth/summary", cookies=cookies)
            assert res.status_code == 200
            summary = res.json()

            # Assets: 5000 + 10000 + 200000 + 15000 = 230000
            assert Decimal(str(summary["cash_total"])) == Decimal("15000")
            assert Decimal(str(summary["property_total"])) == Decimal("200000")
            assert Decimal(str(summary["business_value"])) == Decimal("15000")
            assert Decimal(str(summary["total_assets"])) == Decimal("230000")

            # Debts: 85000 from loan
            assert Decimal(str(summary["loans_total_remaining"])) == Decimal("85000")
            assert Decimal(str(summary["total_debts"])) == Decimal("85000")

            # Net worth: 230000 - 85000 = 145000
            assert Decimal(str(summary["net_worth"])) == Decimal("145000")

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


def test_buffer_adequacy_with_extra_liquid():
    """Buffer adequacy should include extra_liquid from net worth snapshot."""
    from app.calculations.readiness import _compute_buffer_adequacy
    from app.calculations.projection import YearProjection

    allocations = [
        {"vehicle_key": "livret_a", "balance": Decimal("2000"), "monthly": Decimal("0")},
    ]

    y0 = YearProjection(
        year=2026,
        age=40,
        is_retirement=False,
        gross_annual=Decimal("67200"),
        net_annual=Decimal("47000"),
        total_outgoing=Decimal("36000"),
        total_income=Decimal("47000"),
        year_invested=Decimal("6000"),
        passive_monthly=Decimal("0"),
        total_wealth=Decimal("2000"),
        loan_expenses=Decimal("0"),
        project_income=Decimal("0"),
        pension_annual=Decimal("0"),
    )
    timeline = [y0]

    # Without extra_liquid: 2000€ / 3000€ = 0.67 months → score 0
    score_no_extra = _compute_buffer_adequacy(allocations, timeline)
    assert score_no_extra == 0  # < 1 month

    # With 10,000€ extra (cash in current accounts): 12000€ / 3000€ = 4 months
    extra = Decimal("10000")
    score_with_extra = _compute_buffer_adequacy(allocations, timeline, extra_liquid=extra)
    # 4 months out of 6 → (4/6) * 100 ≈ 66
    assert score_with_extra > 50
    assert score_with_extra == 66


def test_buffer_adequacy_with_full_extra_liquid():
    """With enough extra liquid, buffer adequacy reaches 100."""
    from app.calculations.readiness import _compute_buffer_adequacy
    from app.calculations.projection import YearProjection

    allocations = [
        {"vehicle_key": "livret_a", "balance": Decimal("5000"), "monthly": Decimal("0")},
    ]

    y0 = YearProjection(
        year=2026,
        age=40,
        is_retirement=False,
        gross_annual=Decimal("67200"),
        net_annual=Decimal("47000"),
        total_outgoing=Decimal("36000"),
        total_income=Decimal("47000"),
        year_invested=Decimal("6000"),
        passive_monthly=Decimal("0"),
        total_wealth=Decimal("5000"),
        loan_expenses=Decimal("0"),
        project_income=Decimal("0"),
        pension_annual=Decimal("0"),
    )
    timeline = [y0]

    # Without extra: 5000€ / 3000€ = 1.67 months → 27
    score_no_extra = _compute_buffer_adequacy(allocations, timeline)
    assert score_no_extra == 27

    # With 13,000€ extra: 18000€ / 3000€ = 6 months → 100
    extra = Decimal("13000")
    score_with_extra = _compute_buffer_adequacy(allocations, timeline, extra_liquid=extra)
    assert score_with_extra == 100