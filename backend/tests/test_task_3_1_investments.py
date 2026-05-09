"""
TASK-3.1: Investment Vehicles & Allocation Model API tests.

Tests cover:
- GET /api/investments/vehicles — public, returns 7 vehicle specs
- GET /api/investments — upsert: creates missing rows, returns 7 allocations
- PUT /api/investments/{vehicle_key} — update single allocation
- PUT /api/investments — batch update
- Validation: negative values rejected
- Validation: invalid vehicle_key rejected
- Ceiling warning: balance > ceiling returns warning
- Ownership enforcement

Uses the live migrated dev DB.
Run: docker compose exec backend pytest tests/test_task_3_1_investments.py -v
"""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app
from app.models.investment import InvestmentAllocation


async def _register_and_get_cookies(client, suffix: str) -> tuple:
    """Register a user, return (user_id, cookies)."""
    r = await client.post(
        "/api/auth/register",
        json={
            "email": f"test.invest{suffix}@example.com",
            "password": "TestPass123!",
            "name": f"Invest User{suffix}",
        },
    )
    assert r.status_code == 201, f"Registration failed: {r.text}"
    return uuid.UUID(r.json()["user"]["id"]), r.cookies


async def _cleanup(db, user_ids):
    """Clean up test users (cascade removes allocations)."""
    for uid in user_ids:
        await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
    await db.commit()


# Helper: Decimal("0") serializes as "0" (not "0.00") in JSON
ZERO_VALUES = ("0", "0.00")


# ── Public Route Tests ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_vehicles_public():
    """GET /api/investments/vehicles returns 7 vehicle specs without auth."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.get("/api/investments/vehicles")

    assert res.status_code == 200
    data = res.json()

    # All 7 vehicles present
    expected_keys = {
        "livret_a", "ldds", "av_euro", "av_uc", "pea", "scpi", "per"
    }
    assert set(data.keys()) == expected_keys

    # Check one vehicle's spec in detail
    livret_a = data["livret_a"]
    assert livret_a["label"] == "Livret A"
    assert livret_a["rate"] == "0.025"
    assert livret_a["tax_free"] is True
    assert livret_a["tax_rate"] in ZERO_VALUES
    assert livret_a["ceiling"] == "22950.00"
    assert livret_a["risk"] == "Aucun"
    assert livret_a["color"] == "#22d3ee"
    assert livret_a["liquidity"] == "Immédiate"

    # PER has tax_deductible
    per = data["per"]
    assert per["tax_deductible"] is True

    # Livret A does NOT have tax_deductible
    assert livret_a["tax_deductible"] is False


# ── Auth Route Tests ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_allocations_upsert():
    """GET /api/investments creates missing rows and returns 7 allocations."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_upsert")
            user_ids.append(uid)

            res = await client.get("/api/investments", cookies=cookies)
            assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
            data = res.json()

            # 7 allocations
            assert len(data["allocations"]) == 7
            assert data["total_existing"] in ZERO_VALUES
            assert data["total_monthly"] in ZERO_VALUES
            assert data["total_annual"] in ZERO_VALUES

            # All 7 vehicle keys present
            keys = [a["vehicle_key"] for a in data["allocations"]]
            expected_order = [
                "livret_a", "ldds", "av_euro", "av_uc", "pea", "scpi", "per"
            ]
            assert keys == expected_order

            # Each allocation has zero balance, zero contribution, and a spec
            for alloc in data["allocations"]:
                assert alloc["existing_balance"] in ZERO_VALUES
                assert alloc["monthly_contribution"] in ZERO_VALUES
                assert "spec" in alloc
                assert alloc["spec"]["key"] == alloc["vehicle_key"]

        # Verify 7 rows exist in DB
        async with AsyncSession(engine, expire_on_commit=False) as db:
            result = await db.execute(
                select(InvestmentAllocation).where(
                    InvestmentAllocation.user_id == uid
                )
            )
            rows = result.scalars().all()
            assert len(rows) == 7

        # Second GET — should be idempotent, still 7 rows
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            res2 = await client.get("/api/investments", cookies=cookies)
            assert res2.status_code == 200
            assert len(res2.json()["allocations"]) == 7

        async with AsyncSession(engine, expire_on_commit=False) as db:
            result = await db.execute(
                select(InvestmentAllocation).where(
                    InvestmentAllocation.user_id == uid
                )
            )
            rows2 = result.scalars().all()
            assert len(rows2) == 7

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_update_single_allocation():
    """PUT /api/investments/{vehicle_key} updates one allocation."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_single")
            user_ids.append(uid)

            # First, ensure rows exist
            await client.get("/api/investments", cookies=cookies)

            # Update Livret A
            res = await client.put(
                "/api/investments/livret_a",
                json={
                    "existing_balance": 5000,
                    "monthly_contribution": 200,
                },
                cookies=cookies,
            )
            assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
            data = res.json()

            assert data["vehicle_key"] == "livret_a"
            assert data["existing_balance"] == "5000.00"
            assert data["monthly_contribution"] == "200.00"
            assert data["spec"]["label"] == "Livret A"

            # Update PEA as well
            res2 = await client.put(
                "/api/investments/pea",
                json={
                    "existing_balance": 15000,
                    "monthly_contribution": 300,
                },
                cookies=cookies,
            )
            assert res2.status_code == 200
            data2 = res2.json()
            assert data2["vehicle_key"] == "pea"
            assert data2["existing_balance"] == "15000.00"
            assert data2["monthly_contribution"] == "300.00"

            # List should show updated totals
            list_res = await client.get("/api/investments", cookies=cookies)
            assert list_res.status_code == 200
            list_data = list_res.json()
            assert list_data["total_existing"] == "20000.00"  # 5000 + 15000
            assert list_data["total_monthly"] == "500.00"  # 200 + 300
            assert list_data["total_annual"] == "6000.00"  # 500 * 12

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_update_batch_allocations():
    """PUT /api/investments (batch) updates multiple allocations at once."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_batch")
            user_ids.append(uid)

            # Ensure rows exist
            await client.get("/api/investments", cookies=cookies)

            # Batch update 3 vehicles
            res = await client.put(
                "/api/investments",
                json={
                    "allocations": [
                        {
                            "vehicle_key": "livret_a",
                            "existing_balance": 10000,
                            "monthly_contribution": 150,
                        },
                        {
                            "vehicle_key": "ldds",
                            "existing_balance": 3000,
                            "monthly_contribution": 50,
                        },
                        {
                            "vehicle_key": "pea",
                            "existing_balance": 20000,
                            "monthly_contribution": 500,
                        },
                    ]
                },
                cookies=cookies,
            )
            assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
            data = res.json()

            assert len(data["allocations"]) == 7
            assert data["total_existing"] == "33000.00"
            assert data["total_monthly"] == "700.00"
            assert data["total_annual"] == "8400.00"

            # Verify individual values
            allocs_by_key = {
                a["vehicle_key"]: a for a in data["allocations"]
            }
            assert allocs_by_key["livret_a"]["existing_balance"] == "10000.00"
            assert allocs_by_key["livret_a"]["monthly_contribution"] == "150.00"
            assert allocs_by_key["ldds"]["existing_balance"] == "3000.00"
            assert allocs_by_key["ldds"]["monthly_contribution"] == "50.00"
            assert allocs_by_key["av_euro"]["existing_balance"] in ZERO_VALUES  # unchanged

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_ceiling_warning():
    """Balance > ceiling returns a warning field."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_ceiling")
            user_ids.append(uid)

            await client.get("/api/investments", cookies=cookies)

            # Set Livret A above its 22950 ceiling
            res = await client.put(
                "/api/investments/livret_a",
                json={
                    "existing_balance": 25000,
                    "monthly_contribution": 0,
                },
                cookies=cookies,
            )
            assert res.status_code == 200
            data = res.json()
            assert data["warning"] is not None
            assert "22950" in data["warning"]
            assert "25000" in data["warning"] or "25000.00" in data["warning"]

            # Set Livret A within ceiling — no warning
            res2 = await client.put(
                "/api/investments/livret_a",
                json={
                    "existing_balance": 20000,
                    "monthly_contribution": 0,
                },
                cookies=cookies,
            )
            assert res2.status_code == 200
            data2 = res2.json()
            assert data2["warning"] is None

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_invalid_vehicle_key():
    """PUT with invalid vehicle_key returns 404."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_badkey")
            user_ids.append(uid)

            res = await client.put(
                "/api/investments/bitcoin",
                json={
                    "existing_balance": 1000,
                    "monthly_contribution": 100,
                },
                cookies=cookies,
            )
            assert res.status_code == 404

            # Batch with invalid key should fail validation
            res2 = await client.put(
                "/api/investments",
                json={
                    "allocations": [
                        {
                            "vehicle_key": "livret_a",
                            "existing_balance": 1000,
                            "monthly_contribution": 0,
                        },
                        {
                            "vehicle_key": "invalid_vehicle",
                            "existing_balance": 0,
                            "monthly_contribution": 0,
                        },
                    ]
                },
                cookies=cookies,
            )
            assert res2.status_code == 422

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_values_rejected():
    """Validation rejects negative balance and contribution."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_neg")
            user_ids.append(uid)

            # Single update with negative balance
            res = await client.put(
                "/api/investments/livret_a",
                json={
                    "existing_balance": -100,
                    "monthly_contribution": 200,
                },
                cookies=cookies,
            )
            assert res.status_code == 422

            # Single update with negative contribution
            res2 = await client.put(
                "/api/investments/livret_a",
                json={
                    "existing_balance": 1000,
                    "monthly_contribution": -50,
                },
                cookies=cookies,
            )
            assert res2.status_code == 422

            # Batch update with negative value
            res3 = await client.put(
                "/api/investments",
                json={
                    "allocations": [
                        {
                            "vehicle_key": "livret_a",
                            "existing_balance": -500,
                            "monthly_contribution": 0,
                        }
                    ]
                },
                cookies=cookies,
            )
            assert res3.status_code == 422

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_ownership_enforcement():
    """User A cannot access User B's allocations."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid_a, cookies_a = await _register_and_get_cookies(client, "_owner_a")
            uid_b, cookies_b = await _register_and_get_cookies(client, "_owner_b")
            user_ids.extend([uid_a, uid_b])

            # User A sets a balance
            await client.get("/api/investments", cookies=cookies_a)
            await client.put(
                "/api/investments/livret_a",
                json={"existing_balance": 5000, "monthly_contribution": 200},
                cookies=cookies_a,
            )

            # User B gets only their own allocations (all zero)
            res_b = await client.get("/api/investments", cookies=cookies_b)
            assert res_b.status_code == 200
            data_b = res_b.json()
            assert data_b["total_existing"] in ZERO_VALUES

            # User B cannot see user A's Livret A through the API
            # (The single-vehicle endpoint always returns B's own allocation)
            res_b_livret = await client.get("/api/investments", cookies=cookies_b)
            assert res_b_livret.status_code == 200
            for alloc in res_b_livret.json()["allocations"]:
                if alloc["vehicle_key"] == "livret_a":
                    assert alloc["existing_balance"] in ZERO_VALUES

            # User A still sees 5000
            res_a = await client.get("/api/investments", cookies=cookies_a)
            assert res_a.status_code == 200
            assert res_a.json()["total_existing"] == "5000.00"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()