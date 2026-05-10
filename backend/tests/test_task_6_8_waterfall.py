"""
Sprint 6 — TASK-6.8 Disposable Income Waterfall tests.

Tests:
- Waterfall endpoint returns correct structure
- Monthly amounts sum correctly (gross - charges - expenses + additions ≈ disposable)
- Surplus shows emerald status, deficit shows deficit note
- Requires auth and profile
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app


@pytest.mark.asyncio
async def test_waterfall_requires_auth():
    """GET /api/profile/waterfall returns 403 without auth."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/api/profile/waterfall")
        assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_waterfall_smoke():
    """GET /api/profile/waterfall returns valid waterfall for configured user."""
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
            # Register user
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": f"test.wfall.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "Waterfall Test",
                },
            )
            assert r.status_code == 201
            uid = r.json()["user"]["id"]
            user_ids.append(uuid.UUID(uid))
            cookies = r.cookies

            # Set profile with known values
            profile_res = await client.put(
                "/api/profile",
                json={
                    "birth_date": "1986-06-15",
                    "monthly_gross_ca": 5600,
                    "target_retirement_age": 65,
                    "ae_activity_type": "bnc_non_reglementee",
                    "monthly_expenses": {
                        "loyer": 800,
                        "alimentation": 600,
                        "transport": 200,
                        "energie": 150,
                        "internet": 50,
                        "assurance": 100,
                        "sante": 80,
                        "loisirs": 150,
                        "abonnements": 40,
                        "impots": 50,
                        "credit": 590,
                        "divers": 100,
                    },
                    "growth_preset": "moderate",
                },
                cookies=cookies,
            )
            assert profile_res.status_code == 200

            # Add savings
            await client.put(
                "/api/investments/allocations",
                json={
                    "allocations": [
                        {
                            "vehicle_key": "livret_a",
                            "existing_balance": 5000,
                            "monthly_contribution": 500,
                        },
                        {
                            "vehicle_key": "av_euro",
                            "existing_balance": 3000,
                            "monthly_contribution": 250,
                        },
                    ]
                },
                cookies=cookies,
            )

            # Call waterfall
            r = await client.get(
                "/api/profile/waterfall",
                cookies=cookies,
            )
            assert r.status_code == 200, f"Waterfall failed: {r.text}"

            data = r.json()

            # Check structure
            assert "year" in data
            assert "age" in data
            assert "status" in data
            assert data["status"] in ("surplus", "deficit", "breakeven")

            monthly = data["monthly"]
            assert "gross_ca" in monthly
            assert "charges" in monthly
            assert "net_after_charges" in monthly
            assert "disposable" in monthly
            assert "savings_planned" in monthly
            assert "monthly_surplus_deficit" in monthly

            # Verify monthly arithmetic: net_after_charges - expenses + additions ≈ disposable
            gross_m = Decimal(monthly["gross_ca"])
            charges_m = Decimal(monthly["charges"])
            cfe_m = Decimal(monthly["cfe_monthly"])
            net_m = Decimal(monthly["net_after_charges"])

            assert abs(net_m - (gross_m - charges_m - cfe_m)) < Decimal("0.02")

            # Disposable = net - expenses + income additions
            # Expenses = base + loans + kids + pets + cars + tech + recurring
            total_exp_m = (
                Decimal(monthly["base_expenses"])
                + Decimal(monthly["loan_payments"])
                + Decimal(monthly["kid_costs"])
                + Decimal(monthly["pet_costs"])
                + Decimal(monthly["car_costs"])
                + Decimal(monthly["tech_costs"])
                + Decimal(monthly["recurring_costs"])
            )
            additions_m = Decimal(monthly["caf_income"]) + Decimal(monthly["tax_credits"])
            expected_disp = net_m - total_exp_m + additions_m
            actual_disp = Decimal(monthly["disposable"])
            assert abs(actual_disp - expected_disp) < Decimal("0.02")

            # Surplus/deficit = disposable - savings
            savings_m = Decimal(monthly["savings_planned"])
            expected_sd = actual_disp - savings_m
            actual_sd = Decimal(monthly["monthly_surplus_deficit"])
            assert abs(actual_sd - expected_sd) < Decimal("0.02")

            # Annual should also check out
            annual = data["annual"]
            assert Decimal(annual["gross_ca"]) > 0
            assert Decimal(annual["charges"]) > 0

            # If deficit, should have note
            if data["status"] == "deficit":
                assert len(data["deficit_note"]) > 0
            elif data["status"] == "breakeven":
                assert "équilibre" in data["deficit_note"].lower()

    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_waterfall_no_profile():
    """Waterfall returns 404 when no profile exists."""
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
                    "email": f"test.wfall.nop.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "No Profile WF",
                },
            )
            assert r.status_code == 201
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            r = await client.get(
                "/api/profile/waterfall",
                cookies=cookies,
            )
            assert r.status_code == 404

    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()