"""
Sprint 7 — TASK-7.4 Spouse/Partner Data Model & API tests.

Tests:
- Create spouse (success, duplicate returns 409)
- Get spouse (exists, 404 when none)
- Update spouse (partial update)
- Delete spouse
- CC estimate returns 4 options with reasonable values
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


# ── Helpers ────────────────────────────────────────────────────────────────────


async def _register_and_get_cookies(client: AsyncClient, suffix: str = ""):
    """Register a user and return cookies for auth."""
    email = f"test.spouse.{uuid.uuid4().hex[:6]}{suffix}@example.com"
    r = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "TestPass123!",
            "name": "Spouse Test User",
        },
    )
    assert r.status_code == 201, f"Register failed: {r.text}"
    user_id = uuid.UUID(r.json()["user"]["id"])
    return r.cookies, user_id, email


# ── CRUD Tests ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_spouse():
    """POST /api/spouse — create a spouse."""
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
            cookies, user_id, _ = await _register_and_get_cookies(client, ".s1")
            user_ids.append(user_id)

            res = await client.post(
                "/api/spouse",
                json={
                    "first_name": "Marie",
                    "birth_date": "1990-05-15",
                    "relationship_type": "married",
                    "status": "cdi",
                    "monthly_gross_income": "3500.00",
                },
                cookies=cookies,
            )
            assert res.status_code == 201, f"Expected 201: {res.text}"
            data = res.json()
            assert data["first_name"] == "Marie"
            assert data["relationship_type"] == "married"
            assert data["status"] == "cdi"
            assert Decimal(data["monthly_gross_income"]) == Decimal("3500.00")
            assert data["birth_date"] == "1990-05-15"
            # current_age should be computed
            assert data["current_age"] is not None
            assert isinstance(data["current_age"], int)

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_spouse_duplicate_fails():
    """POST /api/spouse — second POST returns 409."""
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
            cookies, user_id, _ = await _register_and_get_cookies(client, ".s2")
            user_ids.append(user_id)

            # First create succeeds
            res1 = await client.post(
                "/api/spouse",
                json={"first_name": "Marie", "relationship_type": "married", "status": "cdi"},
                cookies=cookies,
            )
            assert res1.status_code == 201

            # Second create returns 409
            res2 = await client.post(
                "/api/spouse",
                json={"first_name": "Anne", "relationship_type": "pacsed", "status": "ae"},
                cookies=cookies,
            )
            assert res2.status_code == 409

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_get_spouse():
    """GET /api/spouse — get existing spouse."""
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
            cookies, user_id, _ = await _register_and_get_cookies(client, ".s3")
            user_ids.append(user_id)

            await client.post(
                "/api/spouse",
                json={"first_name": "Marie", "relationship_type": "married", "status": "cdi"},
                cookies=cookies,
            )

            res = await client.get("/api/spouse", cookies=cookies)
            assert res.status_code == 200
            assert res.json()["first_name"] == "Marie"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_get_spouse_404():
    """GET /api/spouse — 404 when no spouse."""
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
            cookies, user_id, _ = await _register_and_get_cookies(client, ".s4")
            user_ids.append(user_id)

            res = await client.get("/api/spouse", cookies=cookies)
            assert res.status_code == 404

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_update_spouse():
    """PUT /api/spouse — partial update."""
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
            cookies, user_id, _ = await _register_and_get_cookies(client, ".s5")
            user_ids.append(user_id)

            await client.post(
                "/api/spouse",
                json={"first_name": "Marie", "relationship_type": "married", "status": "cdi", "monthly_gross_income": "3500.00"},
                cookies=cookies,
            )

            # Partial update: change status and income
            res = await client.put(
                "/api/spouse",
                json={"status": "ae", "monthly_gross_income": "4200.00"},
                cookies=cookies,
            )
            assert res.status_code == 200
            updated = res.json()
            assert updated["status"] == "ae"
            assert Decimal(updated["monthly_gross_income"]) == Decimal("4200.00")
            assert updated["first_name"] == "Marie"  # unchanged
            assert updated["relationship_type"] == "married"  # unchanged

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_delete_spouse():
    """DELETE /api/spouse — delete spouse."""
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
            cookies, user_id, _ = await _register_and_get_cookies(client, ".s6")
            user_ids.append(user_id)

            await client.post(
                "/api/spouse",
                json={"first_name": "Marie", "relationship_type": "married", "status": "cdi"},
                cookies=cookies,
            )

            # Delete
            res = await client.delete("/api/spouse", cookies=cookies)
            assert res.status_code == 204

            # Now GET should 404
            res2 = await client.get("/api/spouse", cookies=cookies)
            assert res2.status_code == 404

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


# ── CC Estimate Tests ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cc_estimate():
    """GET /api/spouse/cc-estimate — returns 4 options with reasonable values."""
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
            cookies, user_id, _ = await _register_and_get_cookies(client, ".s7")
            user_ids.append(user_id)

            # Set profile CA so revenu-based options are non-zero
            await client.get("/api/profile", cookies=cookies)
            await client.put(
                "/api/profile",
                json={"monthly_gross_ca": "5000.00"},
                cookies=cookies,
            )

            res = await client.get("/api/spouse/cc-estimate", cookies=cookies)
            assert res.status_code == 200, f"Expected 200: {res.text}"
            data = res.json()

            # Check all 4 options are present
            for option in ["tiers_plafond", "moitie_plafond", "tiers_revenu", "moitie_revenu"]:
                assert option in data
                est = data[option]
                assert "base_annuelle" in est
                assert "cotisation_annuelle" in est
                assert "cotisation_mensuelle" in est
                # All amounts should be positive strings
                assert Decimal(est["base_annuelle"]) > 0
                assert Decimal(est["cotisation_annuelle"]) > 0
                assert Decimal(est["cotisation_mensuelle"]) > 0

            # Tiers plafond = 46368 / 3 = 15456
            assert Decimal(data["tiers_plafond"]["base_annuelle"]) == Decimal("15456.00")
            # Cotisation = 15456 * 0.28 = 4327.68
            assert Decimal(data["tiers_plafond"]["cotisation_annuelle"]) == Decimal("4327.68")
            # Mensuelle = 4327.68 / 12 = 360.64
            assert Decimal(data["tiers_plafond"]["cotisation_mensuelle"]) == Decimal("360.64")

            # Moitié plafond = 46368 / 2 = 23184
            assert Decimal(data["moitie_plafond"]["base_annuelle"]) == Decimal("23184.00")

            # Tiers revenu = (5000 * 12) / 3 = 20000
            assert Decimal(data["tiers_revenu"]["base_annuelle"]) == Decimal("20000.00")
            # Cotisation = 20000 * 0.28 = 5600
            assert Decimal(data["tiers_revenu"]["cotisation_annuelle"]) == Decimal("5600.00")

            # Moitié revenu = (5000 * 12) / 2 = 30000
            assert Decimal(data["moitie_revenu"]["base_annuelle"]) == Decimal("30000.00")

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_cc_estimate_no_profile():
    """GET /api/spouse/cc-estimate — works even without a spouse."""
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
            cookies, user_id, _ = await _register_and_get_cookies(client, ".s8")
            user_ids.append(user_id)

            # No profile set, no spouse — still works
            res = await client.get("/api/spouse/cc-estimate", cookies=cookies)
            assert res.status_code == 200
            data = res.json()

            # Revenue-based options should be zero since CA is null
            assert Decimal(data["tiers_revenu"]["base_annuelle"]) == Decimal("0.00")
            assert Decimal(data["moitie_revenu"]["base_annuelle"]) == Decimal("0.00")

            # Plafond-based options should still have values
            assert Decimal(data["tiers_plafond"]["base_annuelle"]) > 0
            assert Decimal(data["moitie_plafond"]["base_annuelle"]) > 0

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()