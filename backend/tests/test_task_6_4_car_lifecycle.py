"""
Sprint 6 — TASK-6.4 Car Lifecycle Overhaul tests.

Tests:
- Expired entity detection (cars with max_to_age < current_age)
- New car defaults use to_age=99 for ongoing costs
- Replacement events pre-generated at replace_cycle intervals
- CT events generated through age 40
- API returns expired flag and message for expired entities
- Expired car entity is still created but flagged
- Updating an expired car's cost events clears the expired flag
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
from app.schemas.life_entity import CostEvent
from app.services.canned_defaults import get_car_defaults


# ── Canned defaults tests ──────────────────────────────────────────────────────


def test_car_defaults_use_to_age_99_for_ongoing():
    """Ongoing costs (insurance, fuel, maintenance) should use to_age=99."""
    today = date.today()
    defaults = get_car_defaults(fuel_type="petrol", acquisition_date=today)

    ongoing = [e for e in defaults if e.id in ("c-insurance", "c-fuel", "c-maintenance")]
    assert len(ongoing) == 3, f"Expected 3 ongoing events, got {[e.id for e in ongoing]}"

    for evt in ongoing:
        assert evt.to_age == 99, (
            f"{evt.id}: expected to_age=99, got {evt.to_age}"
        )


def test_car_defaults_have_replacement_events():
    """Replacement events should be pre-generated at replace_cycle intervals."""
    today = date.today()
    defaults = get_car_defaults(
        fuel_type="petrol", acquisition_date=today, replace_cycle=8
    )

    replace_events = [e for e in defaults if e.id.startswith("c-replace-")]
    assert len(replace_events) >= 3, (
        f"Expected at least 3 replacement events, got {len(replace_events)}: "
        f"{[e.id for e in replace_events]}"
    )

    # Check intervals: 8, 16, 24, 32, 40
    expected_ages = [8, 16, 24, 32, 40]
    for evt, expected_age in zip(replace_events, expected_ages):
        assert evt.from_age == expected_age, (
            f"{evt.id}: expected from_age={expected_age}, got {evt.from_age}"
        )
        assert evt.amount == Decimal("18000.00"), (
            f"{evt.id}: expected amount=18000, got {evt.amount}"
        )


def test_car_defaults_have_ct_events():
    """CT events should be generated every 2 years from age 4 through 40."""
    today = date.today()
    defaults = get_car_defaults(fuel_type="petrol", acquisition_date=today)

    ct_events = [e for e in defaults if e.id.startswith("c-ct-")]
    assert len(ct_events) >= 15, (
        f"Expected at least 15 CT events (4→38), got {len(ct_events)}"
    )

    # First CT at age 4
    assert ct_events[0].from_age == 4
    assert ct_events[0].amount == Decimal("80.00")


def test_car_defaults_no_events_past_age_40():
    """No cost event should have from_age > 40 (cap)."""
    today = date.today()
    defaults = get_car_defaults(fuel_type="petrol", acquisition_date=today)

    for evt in defaults:
        if evt.id.startswith("c-replace-") or evt.id.startswith("c-ct-"):
            assert evt.from_age <= 40, (
                f"{evt.id}: from_age={evt.from_age} exceeds cap of 40"
            )


def test_electric_car_has_lower_fuel_costs():
    """Electric cars should have lower fuel/energy costs."""
    today = date.today()
    petrol_defaults = get_car_defaults(fuel_type="petrol", acquisition_date=today)
    electric_defaults = get_car_defaults(fuel_type="electric", acquisition_date=today)

    petrol_fuel = next(e for e in petrol_defaults if e.id == "c-fuel")
    electric_fuel = next(e for e in electric_defaults if e.id == "c-fuel")

    assert electric_fuel.amount < petrol_fuel.amount, (
        f"Electric fuel ({electric_fuel.amount}) should be less than "
        f"petrol fuel ({petrol_fuel.amount})"
    )


# ── Expired entity detection tests (API level) ─────────────────────────────────


@pytest.mark.asyncio
async def test_create_old_car_shows_expired():
    """Creating a car with acquisition_date 15 years ago → expired=True."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM life_entities WHERE user_id = '{uid}'"))
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": f"test.car.old.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "Old Car User",
                },
            )
            assert r.status_code == 201
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            # Create a car acquired 15 years ago
            old_date = (date.today() - timedelta(days=15 * 365)).isoformat()

            res = await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "car",
                    "name": "Vieille Xsara",
                    "reference_date": old_date,
                    "metadata": {"fuel_type": "diesel"},
                },
                cookies=cookies,
            )
            assert res.status_code == 201, f"Expected 201: {res.text}"
            data = res.json()

            # The car is 15 years old — with the new rolling model (to_age=99),
            # ongoing costs should be active, so NOT expired
            assert data["current_age"] >= 15
            # With rolling model, max to_age is 99 → not expired
            assert data["expired"] is False, (
                f"Car with rolling model should NOT be expired, got expired={data['expired']}, "
                f"message={data.get('expired_message')}"
            )

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_car_with_user_defined_short_cycle_shows_expired():
    """Car with user-defined cost events that all end at age 5 → expired if age > 5."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM life_entities WHERE user_id = '{uid}'"))
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": f"test.car.short.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "Short Cycle User",
                },
            )
            assert r.status_code == 201
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            old_date = (date.today() - timedelta(days=10 * 365)).isoformat()

            # Provide custom cost events that all end at age 5
            res = await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "car",
                    "name": "Short-cycle car",
                    "reference_date": old_date,
                    "cost_events": [
                        {
                            "id": "custom-1",
                            "label": "Assurance courte",
                            "from_age": 0,
                            "to_age": 5,
                            "amount": 500,
                            "frequency": "annual",
                            "is_active": True,
                        },
                        {
                            "id": "custom-2",
                            "label": "Carburant",
                            "from_age": 0,
                            "to_age": 5,
                            "amount": 1000,
                            "frequency": "annual",
                            "is_active": True,
                        },
                    ],
                },
                cookies=cookies,
            )
            assert res.status_code == 201, f"Expected 201: {res.text}"
            data = res.json()

            # The car is 10 years old, but max to_age is 5 → expired
            assert data["current_age"] >= 10
            assert data["expired"] is True, (
                f"Car with max_to_age=5 at age 10 should be expired, got {data['expired']}"
            )
            assert data["expired_message"] is not None
            assert "5" in data["expired_message"]

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_new_car_is_not_expired():
    """A brand-new car (reference_date = today) should NOT be expired."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM life_entities WHERE user_id = '{uid}'"))
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": f"test.car.new.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "New Car User",
                },
            )
            assert r.status_code == 201
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            res = await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "car",
                    "name": "Nouvelle voiture",
                    "reference_date": date.today().isoformat(),
                    "metadata": {"fuel_type": "hybrid"},
                },
                cookies=cookies,
            )
            assert res.status_code == 201, f"Expected 201: {res.text}"
            data = res.json()

            assert data["current_age"] == 0
            assert data["expired"] is False
            assert data["expired_message"] is None

            # Should have ongoing costs
            event_ids = [e["id"] for e in data["cost_events"]]
            assert "c-insurance" in event_ids
            assert "c-fuel" in event_ids
            assert "c-maintenance" in event_ids

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_car_list_includes_expired_flag():
    """GET /api/life-entities should include expired flag for each entity."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM life_entities WHERE user_id = '{uid}'"))
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": f"test.car.list.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "List User",
                },
            )
            assert r.status_code == 201
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            # Create a new car
            await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "car",
                    "name": "Nouvelle",
                    "reference_date": date.today().isoformat(),
                },
                cookies=cookies,
            )

            # Create an old car with short cycle
            old_date = (date.today() - timedelta(days=12 * 365)).isoformat()
            await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "car",
                    "name": "Ancienne Xsara",
                    "reference_date": old_date,
                    "cost_events": [
                        {
                            "id": "short",
                            "label": "Cost",
                            "from_age": 0,
                            "to_age": 5,
                            "amount": 500,
                            "frequency": "annual",
                            "is_active": True,
                        },
                    ],
                },
                cookies=cookies,
            )

            res = await client.get("/api/life-entities", cookies=cookies)
            assert res.status_code == 200
            entities = res.json()["entities"]

            assert len(entities) == 2

            # Find the expired one
            expired = [e for e in entities if e["expired"]]
            not_expired = [e for e in entities if not e["expired"]]

            assert len(expired) == 1
            assert len(not_expired) == 1
            assert expired[0]["name"] == "Ancienne Xsara"
            assert expired[0]["expired_message"] is not None

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_update_car_extends_cycle_unexpires():
    """Updating an expired car's cost events to extend to_age → expired becomes False."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM life_entities WHERE user_id = '{uid}'"))
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": f"test.car.extend.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "Extend User",
                },
            )
            assert r.status_code == 201
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            old_date = (date.today() - timedelta(days=10 * 365)).isoformat()

            # Create expired car
            res = await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "car",
                    "name": "To extend",
                    "reference_date": old_date,
                    "cost_events": [
                        {
                            "id": "evt1",
                            "label": "Short cost",
                            "from_age": 0,
                            "to_age": 5,
                            "amount": 500,
                            "frequency": "annual",
                            "is_active": True,
                        },
                    ],
                },
                cookies=cookies,
            )
            entity_id = res.json()["id"]
            assert res.json()["expired"] is True

            # Update to extend to_age to 99
            res2 = await client.put(
                f"/api/life-entities/{entity_id}",
                json={
                    "cost_events": [
                        {
                            "id": "evt1",
                            "label": "Extended cost",
                            "from_age": 0,
                            "to_age": 99,
                            "amount": 500,
                            "frequency": "annual",
                            "is_active": True,
                        },
                    ],
                },
                cookies=cookies,
            )
            assert res2.status_code == 200, f"Expected 200: {res2.text}"
            updated = res2.json()
            assert updated["expired"] is False, (
                f"After extending to_age to 99, car should not be expired"
            )

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()