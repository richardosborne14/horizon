"""
Task 2.3: RecurringExpense CRUD API tests.

Tests cover:
- Create recurring expense
- List expenses (only active, only current user)
- Get single expense (ownership enforcement)
- Update expense (partial)
- Soft delete (hidden from list, row preserved)
- Validation: to_year >= from_year, non-negative amount
- Ownership enforcement

Uses the live migrated dev DB.
Run: docker compose exec backend pytest tests/test_recurring_expenses.py -v
"""

import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app
from app.models.recurring_expense import RecurringExpense


async def _register_and_get_cookies(client, suffix: str) -> tuple:
    """Register a user, return (user_id, cookies)."""
    r = await client.post(
        "/api/auth/register",
        json={
            "email": f"test.recurring{suffix}@example.com",
            "password": "TestPass123!",
            "name": f"Recurring User{suffix}",
        },
    )
    assert r.status_code == 201, f"Registration failed: {r.text}"
    return uuid.UUID(r.json()["user"]["id"]), r.cookies


async def _cleanup(db, user_ids):
    for uid in user_ids:
        await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
    await db.commit()


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_recurring_expense():
    """POST /api/recurring-expenses creates an expense and returns it."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_create")
            user_ids.append(uid)

            res = await client.post(
                "/api/recurring-expenses",
                json={
                    "label": "Vacances d'été",
                    "annual_amount": 3000,
                    "from_year": 2026,
                    "to_year": 2055,
                    "category": "loisirs",
                },
                cookies=cookies,
            )
            assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
            data = res.json()

            assert data["label"] == "Vacances d'été"
            assert data["annual_amount"] == "3000.00"
            assert data["from_year"] == 2026
            assert data["to_year"] == 2055
            assert data["category"] == "loisirs"
            assert data["is_active"] is True
            assert "id" in data
            assert "user_id" in data

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_list_expenses():
    """GET /api/recurring-expenses lists only the user's active expenses."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_list")
            user_ids.append(uid)

            # Create two expenses
            await client.post(
                "/api/recurring-expenses",
                json={
                    "label": "Prêt auto",
                    "annual_amount": 3600,
                    "from_year": 2026,
                    "to_year": 2030,
                },
                cookies=cookies,
            )
            await client.post(
                "/api/recurring-expenses",
                json={
                    "label": "Sport enfant",
                    "annual_amount": 500,
                    "from_year": 2026,
                    "to_year": 2034,
                },
                cookies=cookies,
            )

            list_res = await client.get("/api/recurring-expenses", cookies=cookies)
            assert list_res.status_code == 200
            data = list_res.json()
            assert data["total"] == 2
            labels = [e["label"] for e in data["expenses"]]
            assert "Prêt auto" in labels
            assert "Sport enfant" in labels

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_update_recurring_expense():
    """PUT updates only provided fields."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_update")
            user_ids.append(uid)

            create_res = await client.post(
                "/api/recurring-expenses",
                json={
                    "label": "Original Label",
                    "annual_amount": 1000,
                    "from_year": 2026,
                    "to_year": 2030,
                },
                cookies=cookies,
            )
            assert create_res.status_code == 201
            expense_id = create_res.json()["id"]

            update_res = await client.put(
                f"/api/recurring-expenses/{expense_id}",
                json={"label": "Updated Label"},
                cookies=cookies,
            )
            assert update_res.status_code == 200
            updated = update_res.json()
            assert updated["label"] == "Updated Label"
            assert updated["annual_amount"] == "1000.00"  # unchanged
            assert updated["from_year"] == 2026  # unchanged

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_soft_delete():
    """DELETE soft-deletes (is_active=false), row preserved."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []
    expense_id = None

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_softdel")
            user_ids.append(uid)

            create_res = await client.post(
                "/api/recurring-expenses",
                json={
                    "label": "To Delete",
                    "annual_amount": 500,
                    "from_year": 2026,
                    "to_year": 2028,
                },
                cookies=cookies,
            )
            assert create_res.status_code == 201
            expense_id = uuid.UUID(create_res.json()["id"])

            del_res = await client.delete(
                f"/api/recurring-expenses/{expense_id}", cookies=cookies
            )
            assert del_res.status_code == 204

            # List should be empty
            list_res = await client.get("/api/recurring-expenses", cookies=cookies)
            assert list_res.status_code == 200
            assert list_res.json()["total"] == 0

            # Get should 404
            get_res = await client.get(
                f"/api/recurring-expenses/{expense_id}", cookies=cookies
            )
            assert get_res.status_code == 404

        # DB row still exists
        async with AsyncSession(engine, expire_on_commit=False) as db:
            result = await db.execute(
                select(RecurringExpense).where(RecurringExpense.id == expense_id)
            )
            expense = result.scalar_one_or_none()
            assert expense is not None
            assert expense.is_active is False

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_ownership_enforcement():
    """User A cannot access User B's expenses."""
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
                "/api/recurring-expenses",
                json={
                    "label": "A's Expense",
                    "annual_amount": 1000,
                    "from_year": 2026,
                    "to_year": 2030,
                },
                cookies=cookies_a,
            )
            assert create_res.status_code == 201
            expense_id = create_res.json()["id"]

            # B cannot read A's expense
            get_res = await client.get(
                f"/api/recurring-expenses/{expense_id}", cookies=cookies_b
            )
            assert get_res.status_code == 404

            # B cannot update A's expense
            put_res = await client.put(
                f"/api/recurring-expenses/{expense_id}",
                json={"label": "Stolen"},
                cookies=cookies_b,
            )
            assert put_res.status_code == 404

            # B cannot delete A's expense
            del_res = await client.delete(
                f"/api/recurring-expenses/{expense_id}", cookies=cookies_b
            )
            assert del_res.status_code == 404

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_validation_year_range():
    """to_year must be >= from_year."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_year_range")
            user_ids.append(uid)

            res = await client.post(
                "/api/recurring-expenses",
                json={
                    "label": "Bad Range",
                    "annual_amount": 100,
                    "from_year": 2030,
                    "to_year": 2026,
                },
                cookies=cookies,
            )
            assert res.status_code == 422, f"Expected 422 for bad year range, got {res.status_code}"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_validation_negative_amount():
    """annual_amount must be >= 0."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            uid, cookies = await _register_and_get_cookies(client, "_neg_amount")
            user_ids.append(uid)

            res = await client.post(
                "/api/recurring-expenses",
                json={
                    "label": "Negative",
                    "annual_amount": -100,
                    "from_year": 2026,
                    "to_year": 2030,
                },
                cookies=cookies,
            )
            assert res.status_code == 422, f"Expected 422 for negative amount, got {res.status_code}"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()