"""
Tests for TASK-2.11.1 — Salon contact fields (contact_email, contact_phone).

Verifies that:
  1. POST /api/salons accepts and persists contact_email + contact_phone
  2. PUT /api/salons/:id updates the fields
  3. Fields default to null when omitted on creation
  4. Max-length constraints are enforced by Pydantic (422 on oversized values)

WHY no shared fixture: asyncpg + session-scoped event_loop in conftest causes
"Future attached to different loop" errors when async generator fixtures span
loop teardown. Pattern matches test_task_1_7_salons.py — inline client per test.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app

SMOKE_EMAIL = "smoketest@comcoi.fr"
SMOKE_PASS = "Password123!"


# ── Helpers ────────────────────────────────────────────────────────────────────


async def _make_authed_client() -> AsyncClient:
    """
    Return a new AsyncClient pre-authenticated as the smoke-test user.
    Caller is responsible for closing it (use with 'async with' via _authed).
    """
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    login = await client.post(
        "/api/auth/login",
        json={"email": SMOKE_EMAIL, "password": SMOKE_PASS},
    )
    assert login.status_code == 200, f"Smoke-test login failed: {login.text}"
    client.cookies.update(login.cookies)
    return client


async def _create_salon(client: AsyncClient, **extra) -> dict:
    """Create a throwaway salon and return its JSON."""
    payload = {"name": "Contact Field Test", "business_type": "auto_micro", **extra}
    res = await client.post("/api/salons", json=payload)
    assert res.status_code == 201, f"Create salon failed: {res.text}"
    return res.json()


async def _delete_salon(client: AsyncClient, salon_id: str) -> None:
    """Soft-delete the salon to keep the DB tidy."""
    await client.delete(f"/api/salons/{salon_id}")


# ── Tests ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_salon_with_contact_fields():
    """POST /api/salons — contact_email and contact_phone are stored and returned."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        login = await client.post(
            "/api/auth/login",
            json={"email": SMOKE_EMAIL, "password": SMOKE_PASS},
        )
        assert login.status_code == 200
        client.cookies.update(login.cookies)

        salon = await _create_salon(
            client,
            name="Contact Test Create",
            contact_email="owner@monsalon.fr",
            contact_phone="06 12 34 56 78",
        )
        try:
            assert salon["contact_email"] == "owner@monsalon.fr"
            assert salon["contact_phone"] == "06 12 34 56 78"
        finally:
            await _delete_salon(client, salon["id"])


@pytest.mark.asyncio
async def test_create_salon_contact_fields_default_null():
    """Fields default to null when omitted on creation."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        login = await client.post(
            "/api/auth/login",
            json={"email": SMOKE_EMAIL, "password": SMOKE_PASS},
        )
        assert login.status_code == 200
        client.cookies.update(login.cookies)

        salon = await _create_salon(client, name="Contact Default Null")
        try:
            assert salon["contact_email"] is None
            assert salon["contact_phone"] is None
        finally:
            await _delete_salon(client, salon["id"])


@pytest.mark.asyncio
async def test_update_salon_contact_fields():
    """PUT /api/salons/:id — contact fields can be set and independently cleared."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        login = await client.post(
            "/api/auth/login",
            json={"email": SMOKE_EMAIL, "password": SMOKE_PASS},
        )
        assert login.status_code == 200
        client.cookies.update(login.cookies)

        salon = await _create_salon(client, name="Contact Update Test")
        salon_id = salon["id"]
        try:
            # Set both fields
            updated = await client.put(
                f"/api/salons/{salon_id}",
                json={"contact_email": "new@salon.fr", "contact_phone": "01 23 45 67 89"},
            )
            assert updated.status_code == 200, updated.text
            body = updated.json()
            assert body["contact_email"] == "new@salon.fr"
            assert body["contact_phone"] == "01 23 45 67 89"

            # Update only contact_email — phone must survive unchanged
            # WHY: SalonUpdate uses exclude_none=True; sending null is a no-op.
            # Clearing a field requires an empty string, not null.
            partial = await client.put(
                f"/api/salons/{salon_id}",
                json={"contact_email": "updated@salon.fr"},
            )
            assert partial.status_code == 200, partial.text
            assert partial.json()["contact_email"] == "updated@salon.fr"
            assert partial.json()["contact_phone"] == "01 23 45 67 89"
        finally:
            await _delete_salon(client, salon_id)


@pytest.mark.asyncio
async def test_create_salon_contact_email_too_long():
    """contact_email longer than 255 chars → 422 Unprocessable Entity."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        login = await client.post(
            "/api/auth/login",
            json={"email": SMOKE_EMAIL, "password": SMOKE_PASS},
        )
        assert login.status_code == 200
        client.cookies.update(login.cookies)

        res = await client.post(
            "/api/salons",
            json={
                "name": "Too Long Email",
                "business_type": "auto_micro",
                "contact_email": "a" * 256 + "@example.com",
            },
        )
        assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_salon_contact_phone_too_long():
    """contact_phone longer than 50 chars → 422 Unprocessable Entity."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        login = await client.post(
            "/api/auth/login",
            json={"email": SMOKE_EMAIL, "password": SMOKE_PASS},
        )
        assert login.status_code == 200
        client.cookies.update(login.cookies)

        res = await client.post(
            "/api/salons",
            json={
                "name": "Too Long Phone",
                "business_type": "auto_micro",
                "contact_phone": "0" * 51,
            },
        )
        assert res.status_code == 422
