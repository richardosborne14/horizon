"""
Task 2.10: Services CRUD + Pricing endpoint API integration tests.

Run ONLY inside Docker (requires asyncpg + all deps):
  docker compose exec backend pytest tests/test_task_2_10_services_api.py -v

Pattern: self-contained (no shared fixtures) — each test creates its own
user/salon via API and cleans up in a finally block. Same pattern as
test_task_2_1_employees.py.
"""

import uuid
import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app
from app.services.auth import hash_password


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_engine():
    """Fresh async engine per test — avoids asyncpg connection state pollution."""
    return create_async_engine(settings.DATABASE_URL, echo=False)


async def _cleanup(db: AsyncSession, user_ids: list) -> None:
    """Delete test data — cascade handles salons, employees, services."""
    for uid in user_ids:
        await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
    await db.commit()


async def _create_user_and_salon(c: AsyncClient, engine, suffix: str) -> tuple[dict, dict, str]:
    """
    Helper: create a test user directly in DB, log in, create a salon.

    Returns (headers, salon_dict, user_id).
    """
    email = f"test_svc_{suffix}_{uuid.uuid4().hex[:8]}@test.com"
    uid = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, email, full_name, hashed_password, is_active, onboarding_completed) "
                "VALUES (:id, :email, 'Test', :pw, true, true)"
            ),
            {"id": uid, "email": email, "pw": hash_password("Password123!")},
        )
    login_r = await c.post("/api/auth/login", json={"email": email, "password": "Password123!"})
    token = login_r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    salon_r = await c.post("/api/salons", json={"name": "Salon Test Prix"}, headers=headers)
    return headers, salon_r.json(), uid


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_services_list_seeds_defaults():
    """First GET /api/salons/{id}/services seeds 5 default services."""
    engine = _make_engine()
    user_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            headers, salon, user_id = await _create_user_and_salon(c, engine, "seed")
            resp = await c.get(f"/api/salons/{salon['id']}/services", headers=headers)
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 5
            names = [s["name"] for s in data]
            assert "Forfait coupe femme" in names
            assert "Forfait Homme" in names
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, [user_id] if user_id else [])
        await engine.dispose()


@pytest.mark.asyncio
async def test_services_create_and_update():
    """POST creates a service; PUT updates prix_vente_ttc."""
    engine = _make_engine()
    user_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            headers, salon, user_id = await _create_user_and_salon(c, engine, "crud")
            salon_id = salon["id"]

            cr = await c.post(
                f"/api/salons/{salon_id}/services",
                json={"name": "Balayage", "type": "carte", "duration_minutes": 90, "addon_minutes": 0},
                headers=headers,
            )
            assert cr.status_code == 201
            svc = cr.json()
            assert svc["name"] == "Balayage"
            assert svc["type"] == "carte"
            assert svc["is_active"] is True

            ur = await c.put(
                f"/api/salons/{salon_id}/services/{svc['id']}",
                json={"prix_vente_ttc": "75.00"},
                headers=headers,
            )
            assert ur.status_code == 200
            assert ur.json()["prix_vente_ttc"] == "75.00"
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, [user_id] if user_id else [])
        await engine.dispose()


@pytest.mark.asyncio
async def test_services_deactivate():
    """DELETE soft-deactivates; visible with include_inactive=true, hidden otherwise."""
    engine = _make_engine()
    user_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            headers, salon, user_id = await _create_user_and_salon(c, engine, "del")
            salon_id = salon["id"]

            # Seed defaults, deactivate first
            list_r = await c.get(f"/api/salons/{salon_id}/services", headers=headers)
            svc_id = list_r.json()[0]["id"]

            del_r = await c.delete(f"/api/salons/{salon_id}/services/{svc_id}", headers=headers)
            assert del_r.status_code == 204

            # Not in normal list
            list_r2 = await c.get(f"/api/salons/{salon_id}/services", headers=headers)
            assert svc_id not in [s["id"] for s in list_r2.json()]

            # Visible with include_inactive=true
            list_r3 = await c.get(
                f"/api/salons/{salon_id}/services?include_inactive=true", headers=headers
            )
            assert svc_id in [s["id"] for s in list_r3.json()]
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, [user_id] if user_id else [])
        await engine.dispose()


@pytest.mark.asyncio
async def test_pricing_endpoint_with_employee():
    """POST /api/calculations/pricing with employee returns valid seuil for all services."""
    engine = _make_engine()
    user_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            headers, salon, user_id = await _create_user_and_salon(c, engine, "pricing")
            salon_id = salon["id"]

            # Add employee (35h CDI, taux_occupation default 0.65)
            await c.post(
                f"/api/salons/{salon_id}/employees",
                json={
                    "full_name": "Jackie Test",
                    "role_type": "salarie",
                    "contract_type": "CDI",
                    "hours_per_week": "35",
                    "salary_brut": "2000",
                },
                headers=headers,
            )

            # Seed services
            await c.get(f"/api/salons/{salon_id}/services", headers=headers)

            resp = await c.post(
                "/api/calculations/pricing",
                json={"salon_id": salon_id, "cout_annuel_total": "120000", "save_to_services": True},
                headers=headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["has_employees"] is True
            assert Decimal(data["cout_reel_minute"]) > Decimal("0")
            assert Decimal(data["cout_total_minute"]) > Decimal("0")
            assert data["saved_to_db"] is True
            assert len(data["services"]) == 5
            for svc in data["services"]:
                assert Decimal(svc["seuil_rentabilite"]) > Decimal("0")
                assert Decimal(svc["prix_recommande"]) > Decimal("0")
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, [user_id] if user_id else [])
        await engine.dispose()


@pytest.mark.asyncio
async def test_pricing_endpoint_no_employees():
    """Pricing returns has_employees=False when salon has no employees."""
    engine = _make_engine()
    user_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            headers, salon, user_id = await _create_user_and_salon(c, engine, "noempls")
            salon_id = salon["id"]

            resp = await c.post(
                "/api/calculations/pricing",
                json={"salon_id": salon_id, "cout_annuel_total": "120000"},
                headers=headers,
            )
            assert resp.status_code == 200
            assert resp.json()["has_employees"] is False
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, [user_id] if user_id else [])
        await engine.dispose()


@pytest.mark.asyncio
async def test_pricing_requires_auth():
    """Pricing endpoint returns 401 without authentication."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            "/api/calculations/pricing",
            json={"salon_id": "00000000-0000-0000-0000-000000000000", "cout_annuel_total": "120000"},
        )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_services_other_user_returns_404():
    """GET services for another user's salon returns 404."""
    engine = _make_engine()
    user1_id = user2_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            # User 1 creates salon
            headers1, salon1, user1_id = await _create_user_and_salon(c, engine, "u1")

            # User 2 tries to access user 1's salon services
            headers2, _, user2_id = await _create_user_and_salon(c, engine, "u2")
            resp = await c.get(f"/api/salons/{salon1['id']}/services", headers=headers2)
            assert resp.status_code == 404
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, [uid for uid in [user1_id, user2_id] if uid])
        await engine.dispose()
