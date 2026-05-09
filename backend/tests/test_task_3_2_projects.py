"""
TASK-3.2: Project Model & P&L Computation API tests.

Tests cover:
- P&L computation: 80k/8k/2.5k/30% → net 3 850€, yield 4.81%
- P&L with 0 income → negative gross, tax = 0
- P&L with 0 purchase cost → yield = null
- Create investment project with P&L
- Create event project
- List projects (filter by type)
- Update project
- Soft delete
- Ownership enforcement

Uses the live migrated dev DB.
Run: docker compose exec backend pytest tests/test_task_3_2_projects.py -v
"""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app
from app.models.project import Project
from app.calculations.project_pnl import compute_pnl
from decimal import Decimal


async def _register_and_get_cookies(client, suffix: str) -> tuple:
    r = await client.post(
        "/api/auth/register",
        json={
            "email": f"test.proj{suffix}@example.com",
            "password": "TestPass123!",
            "name": f"Proj User{suffix}",
        },
    )
    assert r.status_code == 201, f"Registration failed: {r.text}"
    return uuid.UUID(r.json()["user"]["id"]), r.cookies


async def _cleanup(db, user_ids):
    for uid in user_ids:
        await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
    await db.commit()


ZERO_VALUES = ("0", "0.00")


# ── P&L Computation Unit Tests ────────────────────────────────────────────────


def test_pnl_standard_case():
    """P&L: 80k purchase, 8k income, 2.5k expenses, 30% tax."""
    pnl = compute_pnl(
        annual_income=Decimal("8000"),
        annual_expenses=Decimal("2500"),
        tax_rate=Decimal("0.300"),
        purchase_cost=Decimal("80000"),
    )
    # Numeric check
    assert pnl.gross_annual == Decimal("5500.00")
    assert pnl.tax_amount == Decimal("1650.00")
    assert pnl.net_annual == Decimal("3850.00")
    assert pnl.monthly_net == Decimal("320.83")

    # Yield: 3850 / 80000 = 0.048125
    assert pnl.yield_pct is not None
    assert abs(pnl.yield_pct - Decimal("0.048125")) < Decimal("0.0001")


def test_pnl_zero_income_negative_gross():
    """P&L: 0 income, 2500 expenses → negative gross, tax = 0."""
    pnl = compute_pnl(
        annual_income=Decimal("0"),
        annual_expenses=Decimal("2500"),
        tax_rate=Decimal("0.300"),
        purchase_cost=Decimal("80000"),
    )
    assert pnl.gross_annual == Decimal("-2500.00")
    assert pnl.tax_amount == Decimal("0")
    assert pnl.net_annual == Decimal("-2500.00")
    assert pnl.yield_pct is not None
    assert pnl.yield_pct < Decimal("0")


def test_pnl_negative_net():
    """P&L: expenses > income → negative net, tax = 0."""
    pnl = compute_pnl(
        annual_income=Decimal("2000"),
        annual_expenses=Decimal("3000"),
        tax_rate=Decimal("0.300"),
        purchase_cost=Decimal("80000"),
    )
    assert pnl.gross_annual == Decimal("-1000.00")
    assert pnl.tax_amount == Decimal("0")
    assert pnl.net_annual == Decimal("-1000.00")


def test_pnl_zero_purchase_cost():
    """P&L with 0 purchase cost → yield is None."""
    pnl = compute_pnl(
        annual_income=Decimal("8000"),
        annual_expenses=Decimal("2500"),
        tax_rate=Decimal("0.300"),
        purchase_cost=Decimal("0"),
    )
    assert pnl.yield_pct is None
    assert pnl.net_annual == Decimal("3850.00")


def test_pnl_no_tax():
    """P&L with 0% tax rate."""
    pnl = compute_pnl(
        annual_income=Decimal("10000"),
        annual_expenses=Decimal("2000"),
        tax_rate=Decimal("0"),
        purchase_cost=Decimal("50000"),
    )
    assert pnl.tax_amount == Decimal("0")
    assert pnl.net_annual == Decimal("8000.00")


# ── CRUD API Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_investment_project():
    """POST /api/projects/investment creates project with P&L."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_invest")
            user_ids.append(uid)

            res = await client.post(
                "/api/projects/investment",
                json={
                    "label": "Gîte Provence",
                    "start_year": 2035,
                    "purchase_cost": 80000,
                    "annual_income": 8000,
                    "annual_expenses": 2500,
                    "tax_rate": 0.30,
                },
                cookies=cookies,
            )
            assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
            data = res.json()

            assert data["project_type"] == "invest"
            assert data["label"] == "Gîte Provence"
            assert data["start_year"] == 2035
            assert data["purchase_cost"] == "80000.00"
            assert data["annual_income"] == "8000.00"
            assert data["annual_expenses"] == "2500.00"
            assert data["tax_rate"] == "0.300"

            # Check P&L
            pnl = data["pnl"]
            assert pnl is not None
            assert pnl["gross_annual"] == "5500.00"
            assert pnl["tax_amount"] == "1650.00"
            assert pnl["net_annual"] == "3850.00"
            assert pnl["yield_pct"] is not None

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_event_project():
    """POST /api/projects/event creates a life event."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_event")
            user_ids.append(uid)

            res = await client.post(
                "/api/projects/event",
                json={
                    "label": "Tour du monde",
                    "event_year": 2030,
                    "event_cost": 20000,
                },
                cookies=cookies,
            )
            assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
            data = res.json()

            assert data["project_type"] == "event"
            assert data["label"] == "Tour du monde"
            assert data["event_year"] == 2030
            assert data["event_cost"] == "20000.00"

            # Events should have no P&L
            assert data["pnl"] is None

            # Investment fields should be null
            assert data["start_year"] is None
            assert data["purchase_cost"] is None

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_list_projects_filter():
    """GET /api/projects?type=invest filters correctly."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_filter")
            user_ids.append(uid)

            # Create one investment and one event
            await client.post(
                "/api/projects/investment",
                json={
                    "label": "Rental",
                    "start_year": 2035,
                    "purchase_cost": 100000,
                    "annual_income": 10000,
                    "annual_expenses": 3000,
                    "tax_rate": 0.30,
                },
                cookies=cookies,
            )
            await client.post(
                "/api/projects/event",
                json={
                    "label": "Wedding",
                    "event_year": 2028,
                    "event_cost": 15000,
                },
                cookies=cookies,
            )

            # List all
            all_res = await client.get("/api/projects", cookies=cookies)
            assert all_res.status_code == 200
            assert all_res.json()["total"] == 2

            # Filter by invest
            invest_res = await client.get(
                "/api/projects?type=invest", cookies=cookies
            )
            assert invest_res.status_code == 200
            assert invest_res.json()["total"] == 1
            assert invest_res.json()["projects"][0]["label"] == "Rental"

            # Filter by event
            event_res = await client.get(
                "/api/projects?type=event", cookies=cookies
            )
            assert event_res.status_code == 200
            assert event_res.json()["total"] == 1
            assert event_res.json()["projects"][0]["label"] == "Wedding"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_update_project():
    """PUT /api/projects/{id} updates fields."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_update")
            user_ids.append(uid)

            create_res = await client.post(
                "/api/projects/investment",
                json={
                    "label": "Original",
                    "start_year": 2035,
                    "purchase_cost": 80000,
                    "annual_income": 8000,
                    "annual_expenses": 2500,
                    "tax_rate": 0.30,
                },
                cookies=cookies,
            )
            proj_id = create_res.json()["id"]

            update_res = await client.put(
                f"/api/projects/{proj_id}",
                json={"label": "Updated Gîte", "annual_income": 10000},
                cookies=cookies,
            )
            assert update_res.status_code == 200
            updated = update_res.json()
            assert updated["label"] == "Updated Gîte"
            assert updated["annual_income"] == "10000.00"
            assert updated["annual_expenses"] == "2500.00"  # unchanged

            # P&L should reflect new income
            pnl = updated["pnl"]
            assert pnl is not None
            # gross = 10000 - 2500 = 7500, tax = 2250, net = 5250
            assert pnl["gross_annual"] == "7500.00"
            assert pnl["net_annual"] == "5250.00"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_soft_delete_project():
    """DELETE /api/projects/{id} soft-deletes."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_softdel")
            user_ids.append(uid)

            create_res = await client.post(
                "/api/projects/event",
                json={
                    "label": "To Delete",
                    "event_year": 2030,
                    "event_cost": 5000,
                },
                cookies=cookies,
            )
            proj_id = uuid.UUID(create_res.json()["id"])

            del_res = await client.delete(
                f"/api/projects/{proj_id}", cookies=cookies
            )
            assert del_res.status_code == 204

            # List should be empty
            list_res = await client.get("/api/projects", cookies=cookies)
            assert list_res.json()["total"] == 0

            # Get should 404
            get_res = await client.get(
                f"/api/projects/{proj_id}", cookies=cookies
            )
            assert get_res.status_code == 404

        # DB row still exists, is_active=False
        async with AsyncSession(engine, expire_on_commit=False) as db:
            result = await db.execute(
                select(Project).where(Project.id == proj_id)
            )
            proj = result.scalar_one_or_none()
            assert proj is not None
            assert proj.is_active is False

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_ownership_enforcement():
    """User A cannot access User B's projects."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid_a, cookies_a = await _register_and_get_cookies(client, "_owner_a")
            uid_b, cookies_b = await _register_and_get_cookies(client, "_owner_b")
            user_ids.extend([uid_a, uid_b])

            create_res = await client.post(
                "/api/projects/event",
                json={
                    "label": "A's Event",
                    "event_year": 2030,
                    "event_cost": 10000,
                },
                cookies=cookies_a,
            )
            assert create_res.status_code == 201
            proj_id = create_res.json()["id"]

            # B cannot read A's project
            get_res = await client.get(
                f"/api/projects/{proj_id}", cookies=cookies_b
            )
            assert get_res.status_code == 404

            # B cannot update A's project
            put_res = await client.put(
                f"/api/projects/{proj_id}",
                json={"label": "Stolen"},
                cookies=cookies_b,
            )
            assert put_res.status_code == 404

            # B cannot delete A's project
            del_res = await client.delete(
                f"/api/projects/{proj_id}", cookies=cookies_b
            )
            assert del_res.status_code == 404

            # B's list is empty
            list_res = await client.get("/api/projects", cookies=cookies_b)
            assert list_res.json()["total"] == 0

            # A's list still has it
            list_res_a = await client.get("/api/projects", cookies=cookies_a)
            assert list_res_a.json()["total"] == 1

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()