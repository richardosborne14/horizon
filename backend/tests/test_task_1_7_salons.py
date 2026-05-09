"""
Task 1.7: Salon CRUD API tests.

Tests cover:
- Create salon (including auto-creation of SalonConfig and PayslipWallet)
- List salons (only non-deleted, only for current user)
- Get salon by ID (ownership enforcement)
- Update salon (partial update)
- Soft delete (salon hidden from list, data preserved)
- Ownership enforcement (user A cannot access user B's salons)

Uses the live migrated dev DB (not create_all — see LEARNINGS.md).
Fresh async engine per test to avoid asyncpg connection state issues.

Run: docker compose exec backend pytest tests/test_task_1_7_salons.py -v
"""

import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app
from app.models.salon import Salon, SalonConfig
from app.models.subscription import PayslipWallet
from app.models.user import User
from app.services.auth import hash_password

# ── DB helpers ────────────────────────────────────────────────────────────────

# WHY fresh engine per test: asyncpg connection state pollution between tests.
# See LEARNINGS.md: "TASK 1.2 — asyncpg + pytest: use fresh engine per test"


async def _teardown_engine(engine):
    """Dispose of the engine after a test."""
    await engine.dispose()


async def _create_test_user(db: AsyncSession, suffix: str = "") -> User:
    """Create a throwaway user for testing. Returns the flushed (uncommitted) user."""
    user = User(
        email=f"test.salon{suffix}@example.com",
        password_hash=hash_password("TestPass123!"),
        name=f"Test Salon User{suffix}",
    )
    db.add(user)
    await db.flush()
    return user


async def _cleanup(db: AsyncSession, user_ids: list[uuid.UUID]) -> None:
    """
    Delete all test data for the given user IDs.
    Cascade handles salons, configs, wallets, sessions.
    """
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


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_salon_auto_creates_config_and_wallet():
    """
    Creating a salon via the API must:
    1. Create the Salon row
    2. Auto-create a SalonConfig row (Eric's defaults)
    3. Auto-create a PayslipWallet row (0 cents)
    """
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            user = await _create_test_user(db, "_autocreate")
            user_ids.append(user.id)
            await db.commit()

        # Log in to get a session cookie
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            login_res = await client.post(
                "/api/auth/login",
                json={"email": "test.salon_autocreate@example.com", "password": "TestPass123!"},
            )
            assert login_res.status_code == 200
            cookies = login_res.cookies

            # Create a salon
            res = await client.post(
                "/api/salons",
                json={
                    "name": "Salon Test Autocreate",
                    "business_type": "auto_micro",
                    "nb_employees": 0,
                },
                cookies=cookies,
            )
            assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
            salon_data = res.json()
            salon_id = uuid.UUID(salon_data["id"])

        # Verify SalonConfig and PayslipWallet were auto-created
        async with AsyncSession(engine, expire_on_commit=False) as db:
            config_result = await db.execute(
                select(SalonConfig).where(SalonConfig.salon_id == salon_id)
            )
            config = config_result.scalar_one_or_none()
            assert config is not None, "SalonConfig was NOT auto-created"
            assert float(config.semaines_ouverture_an) == 45.6, (
                "SalonConfig should default to 45.6 weeks (Eric's benchmark)"
            )

            wallet_result = await db.execute(
                select(PayslipWallet).where(PayslipWallet.salon_id == salon_id)
            )
            wallet = wallet_result.scalar_one_or_none()
            assert wallet is not None, "PayslipWallet was NOT auto-created"
            assert wallet.balance_cents == 0, "New wallet should start at 0 cents"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await _teardown_engine(engine)


@pytest.mark.asyncio
async def test_list_salons_only_returns_own_active():
    """
    GET /api/salons must only return salons belonging to the current user,
    and must NOT return soft-deleted salons.
    """
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Register two users
            r1 = await client.post(
                "/api/auth/register",
                json={
                    "email": "test.salon_list1@example.com",
                    "password": "TestPass123!",
                    "name": "List User One",
                },
            )
            assert r1.status_code == 201
            r2 = await client.post(
                "/api/auth/register",
                json={
                    "email": "test.salon_list2@example.com",
                    "password": "TestPass123!",
                    "name": "List User Two",
                },
            )
            assert r2.status_code == 201

            user_ids.append(uuid.UUID(r1.json()["user"]["id"]))
            user_ids.append(uuid.UUID(r2.json()["user"]["id"]))

            cookies1 = r1.cookies
            cookies2 = r2.cookies

            # User 1 creates 2 salons
            await client.post(
                "/api/salons",
                json={"name": "User1 Salon A", "business_type": "eurl"},
                cookies=cookies1,
            )
            res_b = await client.post(
                "/api/salons",
                json={"name": "User1 Salon B", "business_type": "sarl"},
                cookies=cookies1,
            )
            salon_b_id = res_b.json()["id"]

            # User 2 creates 1 salon
            await client.post(
                "/api/salons",
                json={"name": "User2 Salon X", "business_type": "sasu"},
                cookies=cookies2,
            )

            # User 1 soft-deletes Salon B
            del_res = await client.delete(f"/api/salons/{salon_b_id}", cookies=cookies1)
            assert del_res.status_code == 204

            # User 1 list — should see only Salon A (not B, not User2's X)
            list_res = await client.get("/api/salons", cookies=cookies1)
            assert list_res.status_code == 200
            salons = list_res.json()
            names = [s["name"] for s in salons]
            assert "User1 Salon A" in names, "User1 Salon A should be in the list"
            assert "User1 Salon B" not in names, "Deleted Salon B should NOT be in the list"
            assert "User2 Salon X" not in names, "Other user's salon should NOT appear"
            assert len(salons) == 1, f"User1 should have exactly 1 active salon, got {len(salons)}"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await _teardown_engine(engine)


@pytest.mark.asyncio
async def test_update_salon_partial():
    """
    PUT /api/salons/:id should update only the provided fields.
    Non-provided fields remain unchanged.
    """
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": "test.salon_update@example.com",
                    "password": "TestPass123!",
                    "name": "Update User",
                },
            )
            assert r.status_code == 201
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            # Create
            create_res = await client.post(
                "/api/salons",
                json={
                    "name": "Original Name",
                    "business_type": "auto_micro",
                    "ville": "Paris",
                },
                cookies=cookies,
            )
            assert create_res.status_code == 201
            salon_id = create_res.json()["id"]

            # Update only the name
            update_res = await client.put(
                f"/api/salons/{salon_id}",
                json={"name": "Updated Name"},
                cookies=cookies,
            )
            assert update_res.status_code == 200
            updated = update_res.json()
            assert updated["name"] == "Updated Name", "Name should be updated"
            assert updated["business_type"] == "auto_micro", (
                "business_type should NOT change (not in update payload)"
            )
            assert updated["ville"] == "Paris", "ville should NOT change (not in update payload)"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await _teardown_engine(engine)


@pytest.mark.asyncio
async def test_soft_delete_preserves_db_row():
    """
    DELETE /api/salons/:id should soft-delete (set deleted_at), not hard-delete.
    The row must still exist in the database after deletion.
    The salon must NOT appear in the API list.
    """
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []
    salon_id = None

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": "test.salon_softdel@example.com",
                    "password": "TestPass123!",
                    "name": "SoftDel User",
                },
            )
            assert r.status_code == 201
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            create_res = await client.post(
                "/api/salons",
                json={"name": "To Be Deleted", "business_type": "eurl"},
                cookies=cookies,
            )
            assert create_res.status_code == 201
            salon_id = uuid.UUID(create_res.json()["id"])

            # Delete (soft)
            del_res = await client.delete(f"/api/salons/{salon_id}", cookies=cookies)
            assert del_res.status_code == 204

            # API list should be empty
            list_res = await client.get("/api/salons", cookies=cookies)
            assert list_res.status_code == 200
            assert len(list_res.json()) == 0, "Soft-deleted salon should not appear in list"

            # API get by ID should 404
            get_res = await client.get(f"/api/salons/{salon_id}", cookies=cookies)
            assert get_res.status_code == 404, "Soft-deleted salon should return 404 on get"

        # DB row must still exist (deleted_at set, not hard-deleted)
        async with AsyncSession(engine, expire_on_commit=False) as db:
            result = await db.execute(
                select(Salon).where(Salon.id == salon_id)
            )
            salon = result.scalar_one_or_none()
            assert salon is not None, "Row must still exist in DB (soft delete preserves data)"
            assert salon.deleted_at is not None, "deleted_at must be set after soft delete"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await _teardown_engine(engine)


@pytest.mark.asyncio
async def test_ownership_enforcement():
    """
    User A must NOT be able to read, update, or delete User B's salons.
    All such requests should return 404 (not 403 — we don't reveal existence).
    """
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Register User A
            ra = await client.post(
                "/api/auth/register",
                json={
                    "email": "test.salon_owner_a@example.com",
                    "password": "TestPass123!",
                    "name": "Owner A",
                },
            )
            assert ra.status_code == 201
            user_ids.append(uuid.UUID(ra.json()["user"]["id"]))
            cookies_a = ra.cookies

            # Register User B
            rb = await client.post(
                "/api/auth/register",
                json={
                    "email": "test.salon_owner_b@example.com",
                    "password": "TestPass123!",
                    "name": "Owner B",
                },
            )
            assert rb.status_code == 201
            user_ids.append(uuid.UUID(rb.json()["user"]["id"]))
            cookies_b = rb.cookies

            # User A creates a salon
            create_res = await client.post(
                "/api/salons",
                json={"name": "A's Private Salon", "business_type": "sarl"},
                cookies=cookies_a,
            )
            assert create_res.status_code == 201
            salon_id = create_res.json()["id"]

            # User B tries to GET User A's salon → 404
            get_res = await client.get(f"/api/salons/{salon_id}", cookies=cookies_b)
            assert get_res.status_code == 404, "User B should not be able to read User A's salon"

            # User B tries to UPDATE User A's salon → 404
            update_res = await client.put(
                f"/api/salons/{salon_id}",
                json={"name": "Stolen"},
                cookies=cookies_b,
            )
            assert update_res.status_code == 404, "User B should not be able to update User A's salon"

            # User B tries to DELETE User A's salon → 404
            del_res = await client.delete(f"/api/salons/{salon_id}", cookies=cookies_b)
            assert del_res.status_code == 404, "User B should not be able to delete User A's salon"

            # User A's salon is still intact
            get_a_res = await client.get(f"/api/salons/{salon_id}", cookies=cookies_a)
            assert get_a_res.status_code == 200
            assert get_a_res.json()["name"] == "A's Private Salon"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await _teardown_engine(engine)


@pytest.mark.asyncio
async def test_create_salon_validation():
    """
    POST /api/salons with missing required fields should return 422.
    """
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": "test.salon_validation@example.com",
                    "password": "TestPass123!",
                    "name": "Validation User",
                },
            )
            assert r.status_code == 201
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            # Missing name → 422
            res_no_name = await client.post(
                "/api/salons",
                json={"business_type": "eurl"},
                cookies=cookies,
            )
            assert res_no_name.status_code == 422, "Missing name should return 422"

            # Missing business_type → 422
            res_no_type = await client.post(
                "/api/salons",
                json={"name": "Unnamed Salon"},
                cookies=cookies,
            )
            assert res_no_type.status_code == 422, "Missing business_type should return 422"

            # Unauthenticated → 401 — must use a FRESH client (no cookies)
            # WHY separate client: the shared `client` stores the session cookie
            # from the register call above. An unauthenticated request needs a
            # cookieless client to actually have no session.
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as anon_client:
                res_unauth = await anon_client.post(
                    "/api/salons",
                    json={"name": "Anonymous Salon", "business_type": "eurl"},
                )
                assert res_unauth.status_code == 401, "Unauthenticated request should return 401"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await _teardown_engine(engine)
