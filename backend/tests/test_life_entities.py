"""
Task 2.1: LifeEntity CRUD API tests.

Tests cover:
- Create life entity (kid, pet, car, tech)
- List life entities (filtered by type, only active, only current user)
- Get single entity by ID (ownership enforcement)
- Update entity (partial update, cost_events modification)
- Soft delete (entity hidden from list, row preserved)
- Ownership enforcement (user A cannot access user B's entities)
- current_age computation
- Cost event validation

Uses the live migrated dev DB (not create_all — see LEARNINGS.md).
Fresh async engine per test to avoid asyncpg connection state issues.

Run: docker compose exec backend pytest tests/test_life_entities.py -v
"""

import uuid
from datetime import date
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app
from app.models.life_entity import LifeEntity
from app.models.user import User
from app.services.auth import hash_password


# ── DB helpers ────────────────────────────────────────────────────────────────


async def _teardown_engine(engine):
    """Dispose of the engine after a test."""
    await engine.dispose()


async def _create_test_user(db: AsyncSession, suffix: str = "") -> User:
    """Create a throwaway user for testing. Returns the flushed (uncommitted) user."""
    user = User(
        email=f"test.life{suffix}@example.com",
        password_hash=hash_password("TestPass123!"),
        name=f"Test Life User{suffix}",
    )
    db.add(user)
    await db.flush()
    return user


async def _cleanup(db: AsyncSession, user_ids: list[uuid.UUID]) -> None:
    """Delete all test data for the given user IDs. Cascade handles entities, sessions."""
    for uid in user_ids:
        await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
    await db.commit()


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client():
    """HTTPX async client hitting the FastAPI app directly."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ── Helper ────────────────────────────────────────────────────────────────────


async def _register_and_get_cookies(client, suffix: str) -> tuple:
    """Register a user, return (user_id, cookies)."""
    r = await client.post(
        "/api/auth/register",
        json={
            "email": f"test.life{suffix}@example.com",
            "password": "TestPass123!",
            "name": f"Life User{suffix}",
        },
    )
    assert r.status_code == 201, f"Registration failed: {r.text}"
    return uuid.UUID(r.json()["user"]["id"]), r.cookies


# ── Tests: Create ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_kid_entity():
    """POST /api/life-entities with entity_type=kid should create and return the entity with current_age."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_create_kid")
            user_ids.append(uid)

            # Kid born 2020-06-15 (age ~5 as of 2026-05-08 → age 5)
            res = await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "kid",
                    "name": "Emma",
                    "reference_date": "2020-06-15",
                    "metadata": {},
                    "cost_events": [],
                },
                cookies=cookies,
            )
            assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
            data = res.json()

            assert data["entity_type"] == "kid"
            assert data["name"] == "Emma"
            assert data["reference_date"] == "2020-06-15"
            assert data["current_age"] >= 5, f"Expected age >= 5, got {data['current_age']}"
            assert data["is_active"] is True
            assert data["metadata"] == {}
            # Empty cost_events are now auto-populated with canned defaults (TASK-2.2)
            assert len(data["cost_events"]) == 13, (
                f"Empty cost_events should be auto-populated, got {len(data['cost_events'])}"
            )
            assert all(e["source"] == "default" for e in data["cost_events"])
            assert "id" in data
            assert "user_id" in data

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await _teardown_engine(engine)


@pytest.mark.asyncio
async def test_create_car_entity_with_metadata():
    """POST /api/life-entities with entity_type=car and metadata should store metadata correctly."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_create_car")
            user_ids.append(uid)

            res = await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "car",
                    "name": "Ma Clio",
                    "reference_date": "2022-01-15",
                    "metadata": {
                        "fuel_type": "petrol",
                        "replace_cycle": 8,
                        "replace_cost": 18000,
                    },
                    "cost_events": [],
                },
                cookies=cookies,
            )
            assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
            data = res.json()

            assert data["entity_type"] == "car"
            assert data["name"] == "Ma Clio"
            assert data["metadata"]["fuel_type"] == "petrol"
            assert data["metadata"]["replace_cycle"] == 8
            assert data["metadata"]["replace_cost"] == 18000
            # Age since 2022-01-15 — should be ~4 years
            assert data["current_age"] >= 4, f"Expected age >= 4, got {data['current_age']}"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await _teardown_engine(engine)


@pytest.mark.asyncio
async def test_create_entity_with_cost_events_stores_them():
    """POST with provided cost_events should store them (not use defaults)."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_with_events")
            user_ids.append(uid)

            res = await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "pet",
                    "name": "Rex",
                    "reference_date": "2024-06-01",
                    "metadata": {"pet_type": "dog"},
                    "cost_events": [
                        {
                            "id": "abc12345",
                            "label": "Nourriture",
                            "from_age": 0,
                            "to_age": 15,
                            "amount": 600,
                            "frequency": "annual",
                            "source": "user",
                            "is_active": True,
                        }
                    ],
                },
                cookies=cookies,
            )
            assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
            data = res.json()

            assert len(data["cost_events"]) == 1
            assert data["cost_events"][0]["id"] == "abc12345"
            assert data["cost_events"][0]["label"] == "Nourriture"
            assert data["cost_events"][0]["amount"] == "600.00"  # Decimal serialized as string
            assert data["cost_events"][0]["frequency"] == "annual"
            assert data["cost_events"][0]["source"] == "user"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await _teardown_engine(engine)


# ── Tests: List & Filter ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_entities_filters_by_type():
    """GET /api/life-entities?type=kid should only return kid entities."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_list_filter")
            user_ids.append(uid)

            # Create a kid and a car
            await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "kid",
                    "name": "Emma",
                    "reference_date": "2020-06-15",
                    "metadata": {},
                },
                cookies=cookies,
            )
            await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "car",
                    "name": "Clio",
                    "reference_date": "2022-01-01",
                    "metadata": {"fuel_type": "petrol"},
                },
                cookies=cookies,
            )

            # List all
            all_res = await client.get("/api/life-entities", cookies=cookies)
            assert all_res.status_code == 200
            all_data = all_res.json()
            assert all_data["total"] == 2

            # Filter by kid
            kid_res = await client.get("/api/life-entities?type=kid", cookies=cookies)
            assert kid_res.status_code == 200
            kid_data = kid_res.json()
            assert kid_data["total"] == 1
            assert kid_data["entities"][0]["name"] == "Emma"

            # Filter by car
            car_res = await client.get("/api/life-entities?type=car", cookies=cookies)
            assert car_res.status_code == 200
            car_data = car_res.json()
            assert car_data["total"] == 1
            assert car_data["entities"][0]["name"] == "Clio"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await _teardown_engine(engine)


@pytest.mark.asyncio
async def test_list_entities_excludes_soft_deleted():
    """Soft-deleted entities must NOT appear in the list."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_list_softdel")
            user_ids.append(uid)

            # Create two entities
            r1 = await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "kid",
                    "name": "Active Kid",
                    "reference_date": "2020-01-01",
                },
                cookies=cookies,
            )
            assert r1.status_code == 201
            kid_id = r1.json()["id"]

            await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "pet",
                    "name": "Active Pet",
                    "reference_date": "2023-01-01",
                    "metadata": {"pet_type": "cat"},
                },
                cookies=cookies,
            )

            # Soft-delete the kid
            del_res = await client.delete(f"/api/life-entities/{kid_id}", cookies=cookies)
            assert del_res.status_code == 204

            # List should only show the pet
            list_res = await client.get("/api/life-entities", cookies=cookies)
            assert list_res.status_code == 200
            data = list_res.json()
            assert data["total"] == 1
            assert data["entities"][0]["name"] == "Active Pet"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await _teardown_engine(engine)


# ── Tests: Get Single ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_entity_by_id():
    """GET /api/life-entities/:id should return the entity with computed current_age."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_get_by_id")
            user_ids.append(uid)

            create_res = await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "tech",
                    "name": "MacBook Pro",
                    "reference_date": "2024-01-01",
                    "metadata": {"replace_cycle": 4, "replace_cost": 2500},
                },
                cookies=cookies,
            )
            assert create_res.status_code == 201
            entity_id = create_res.json()["id"]

            get_res = await client.get(f"/api/life-entities/{entity_id}", cookies=cookies)
            assert get_res.status_code == 200
            data = get_res.json()

            assert data["name"] == "MacBook Pro"
            assert data["entity_type"] == "tech"
            assert data["metadata"]["replace_cycle"] == 4
            # Age since 2024-01-01 → ~2 years
            assert data["current_age"] >= 2

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await _teardown_engine(engine)


# ── Tests: Update ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_entity_partial():
    """PUT /api/life-entities/:id should update only provided fields."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_update_partial")
            user_ids.append(uid)

            create_res = await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "kid",
                    "name": "Lucas",
                    "reference_date": "2018-05-01",
                    "metadata": {},
                },
                cookies=cookies,
            )
            assert create_res.status_code == 201
            entity_id = create_res.json()["id"]

            # Update only the name
            update_res = await client.put(
                f"/api/life-entities/{entity_id}",
                json={"name": "Lucas Updated"},
                cookies=cookies,
            )
            assert update_res.status_code == 200
            updated = update_res.json()
            assert updated["name"] == "Lucas Updated"
            assert updated["entity_type"] == "kid"  # unchanged
            assert updated["reference_date"] == "2018-05-01"  # unchanged

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await _teardown_engine(engine)


@pytest.mark.asyncio
async def test_update_cost_events():
    """PUT should replace the entire cost_events array."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_update_events")
            user_ids.append(uid)

            create_res = await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "kid",
                    "name": "Emma",
                    "reference_date": "2020-06-15",
                    "metadata": {},
                },
                cookies=cookies,
            )
            assert create_res.status_code == 201
            entity_id = create_res.json()["id"]

            # Update cost_events with two events
            update_res = await client.put(
                f"/api/life-entities/{entity_id}",
                json={
                    "cost_events": [
                        {
                            "id": "evt00001",
                            "label": "Crèche",
                            "from_age": 0,
                            "to_age": 3,
                            "amount": 500,
                            "frequency": "monthly",
                            "source": "user",
                            "is_active": True,
                        },
                        {
                            "id": "evt00002",
                            "label": "Cantine",
                            "from_age": 3,
                            "to_age": 11,
                            "amount": 150,
                            "frequency": "monthly",
                            "source": "user",
                            "is_active": True,
                        },
                    ],
                },
                cookies=cookies,
            )
            assert update_res.status_code == 200
            updated = update_res.json()
            assert len(updated["cost_events"]) == 2
            assert updated["cost_events"][0]["label"] == "Crèche"
            assert updated["cost_events"][1]["label"] == "Cantine"
            assert updated["cost_events"][0]["amount"] == "500.00"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await _teardown_engine(engine)


# ── Tests: Delete ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_soft_delete():
    """DELETE /api/life-entities/:id should soft-delete (set is_active=false) not hard-delete."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []
    entity_id = None

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_delete_soft")
            user_ids.append(uid)

            create_res = await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "pet",
                    "name": "Médor",
                    "reference_date": "2021-03-15",
                    "metadata": {"pet_type": "dog"},
                },
                cookies=cookies,
            )
            assert create_res.status_code == 201
            entity_id = uuid.UUID(create_res.json()["id"])

            # Delete (soft)
            del_res = await client.delete(f"/api/life-entities/{entity_id}", cookies=cookies)
            assert del_res.status_code == 204

            # API list should NOT include it
            list_res = await client.get("/api/life-entities", cookies=cookies)
            assert list_res.status_code == 200
            data = list_res.json()
            assert data["total"] == 0

            # API get by ID should 404
            get_res = await client.get(f"/api/life-entities/{entity_id}", cookies=cookies)
            assert get_res.status_code == 404

        # DB row must still exist (is_active=false, not hard-deleted)
        async with AsyncSession(engine, expire_on_commit=False) as db:
            result = await db.execute(
                select(LifeEntity).where(LifeEntity.id == entity_id)
            )
            entity = result.scalar_one_or_none()
            assert entity is not None, "Row must still exist in DB (soft delete preserves data)"
            assert entity.is_active is False, "is_active must be False after soft delete"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await _teardown_engine(engine)


# ── Tests: Ownership ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ownership_enforcement():
    """User A must NOT be able to read, update, or delete User B's entities."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid_a, cookies_a = await _register_and_get_cookies(client, "_owner_a")
            uid_b, cookies_b = await _register_and_get_cookies(client, "_owner_b")
            user_ids.extend([uid_a, uid_b])

            # User A creates an entity
            create_res = await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "kid",
                    "name": "A's Kid",
                    "reference_date": "2020-01-01",
                },
                cookies=cookies_a,
            )
            assert create_res.status_code == 201
            entity_id = create_res.json()["id"]

            # User B tries to GET User A's entity → 404
            get_res = await client.get(f"/api/life-entities/{entity_id}", cookies=cookies_b)
            assert get_res.status_code == 404

            # User B tries to UPDATE User A's entity → 404
            update_res = await client.put(
                f"/api/life-entities/{entity_id}",
                json={"name": "Stolen"},
                cookies=cookies_b,
            )
            assert update_res.status_code == 404

            # User B tries to DELETE User A's entity → 404
            del_res = await client.delete(f"/api/life-entities/{entity_id}", cookies=cookies_b)
            assert del_res.status_code == 404

            # User A's entity is still intact
            get_a_res = await client.get(f"/api/life-entities/{entity_id}", cookies=cookies_a)
            assert get_a_res.status_code == 200
            assert get_a_res.json()["name"] == "A's Kid"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await _teardown_engine(engine)


# ── Tests: Validation ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_validation_missing_required_fields():
    """POST should return 422 for missing required fields."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_validation")
            user_ids.append(uid)

            # Missing name
            res = await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "kid",
                    "reference_date": "2020-01-01",
                },
                cookies=cookies,
            )
            assert res.status_code == 422, f"Missing name: expected 422, got {res.status_code}"

            # Missing reference_date
            res = await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "kid",
                    "name": "Emma",
                },
                cookies=cookies,
            )
            assert res.status_code == 422, f"Missing reference_date: expected 422, got {res.status_code}"

            # Invalid entity_type
            res = await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "boat",
                    "name": "Boaty",
                    "reference_date": "2020-01-01",
                },
                cookies=cookies,
            )
            assert res.status_code == 422, f"Invalid entity_type: expected 422, got {res.status_code}"

            # Unauthenticated → 401
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as anon_client:
                res_unauth = await anon_client.post(
                    "/api/life-entities",
                    json={
                        "entity_type": "kid",
                        "name": "Anonymous",
                        "reference_date": "2020-01-01",
                    },
                )
                assert res_unauth.status_code == 401, f"Unauthenticated: expected 401, got {res_unauth.status_code}"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await _teardown_engine(engine)


@pytest.mark.asyncio
async def test_cost_event_validation():
    """Cost events with negative amounts or invalid frequencies should be rejected."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_event_validation")
            user_ids.append(uid)

            # Negative amount
            res = await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "kid",
                    "name": "Emma",
                    "reference_date": "2020-01-01",
                    "cost_events": [
                        {
                            "id": "bad00001",
                            "label": "Bad Event",
                            "from_age": 0,
                            "to_age": 5,
                            "amount": -100,
                            "frequency": "monthly",
                        }
                    ],
                },
                cookies=cookies,
            )
            assert res.status_code == 422, f"Negative amount: expected 422, got {res.status_code}"

            # Invalid frequency
            res = await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "kid",
                    "name": "Emma",
                    "reference_date": "2020-01-01",
                    "cost_events": [
                        {
                            "id": "bad00002",
                            "label": "Bad Event",
                            "from_age": 0,
                            "to_age": 5,
                            "amount": 100,
                            "frequency": "weekly",  # not allowed
                        }
                    ],
                },
                cookies=cookies,
            )
            assert res.status_code == 422, f"Invalid frequency: expected 422, got {res.status_code}"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await _teardown_engine(engine)


# ── Tests: Age Computation ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_current_age_computation():
    """current_age should be computed as (today - reference_date).days // 365."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_age")
            user_ids.append(uid)

            # Kid born exactly 3 years ago
            today = date.today()
            kid_birth = date(today.year - 3, today.month, today.day)
            res = await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "kid",
                    "name": "Three Year Old",
                    "reference_date": kid_birth.isoformat(),
                },
                cookies=cookies,
            )
            assert res.status_code == 201
            data = res.json()
            # Should be exactly 3 or very close
            assert data["current_age"] == 3, (
                f"Kid born exactly 3 years ago should be age 3, got {data['current_age']}"
            )

            # Age updates with time — create entity born yesterday
            yesterday = date(today.year, today.month, today.day - 1) if today.day > 1 else date(today.year, today.month - 1, 28)
            res2 = await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "pet",
                    "name": "New Puppy",
                    "reference_date": yesterday.isoformat(),
                    "metadata": {"pet_type": "dog"},
                },
                cookies=cookies,
            )
            assert res2.status_code == 201
            data2 = res2.json()
            # Born yesterday → age 0
            assert data2["current_age"] == 0, (
                f"Pet born yesterday should be age 0, got {data2['current_age']}"
            )

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await _teardown_engine(engine)