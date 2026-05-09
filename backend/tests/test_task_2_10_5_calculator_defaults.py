"""
Tests for Task 2.10.5 — Calculator Defaults API.

Verifies that GET /api/salons/{id}/calculator-defaults/{calc_key} returns
the correct defaults for seuil_salaire, volume_clients, and cout_minute
calculators, sourced from salon_config and employee data.
"""
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app
from app.services.auth import hash_password


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_engine():
    """Fresh async engine per test — avoids asyncpg connection state pollution."""
    return create_async_engine(settings.database_url, echo=False)


async def _cleanup(db: AsyncSession, user_ids: list) -> None:
    """Delete test data — cascade handles salons, employees, services."""
    for uid in user_ids:
        await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
    await db.commit()


async def _create_user_and_salon(c: AsyncClient, engine, suffix: str) -> tuple[dict, dict, str]:
    """
    Create a test user in DB, log in (sets httpOnly session cookie on c),
    then create a salon.

    WHY empty headers: auth uses httpOnly session cookie set by /api/auth/login.
    The AsyncClient stores and replays cookies automatically, so subsequent
    requests need no explicit Authorization header.

    Returns ({}, salon_dict, user_id).
    """
    email = f"test_cd_{suffix}_{uuid.uuid4().hex[:8]}@test.com"
    uid = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, email, name, password_hash, onboarding_completed) "
                "VALUES (:id, :email, 'Test User', :pw, true)"
            ),
            {"id": uid, "email": email, "pw": hash_password("Password123!")},
        )
    login_r = await c.post("/api/auth/login", json={"email": email, "password": "Password123!"})
    assert login_r.status_code == 200, f"Login failed: {login_r.text}"
    # Cookie is now stored in c.cookies — no headers needed
    salon_r = await c.post(
        "/api/salons",
        json={"name": "Salon Defaults Test", "business_type": "salon_coiffure"},
    )
    assert salon_r.status_code in (200, 201), f"Salon create failed: {salon_r.text}"
    return {}, salon_r.json(), uid


# ── Seuil Salaire defaults ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_seuil_salaire_no_employees_returns_eric_defaults():
    """
    With no employees, seuil_salaire returns Eric's defaults and a warning.
    Margin fields (taux_produits, taux_charges_fixes, etc.) come from Eric defaults.
    """
    engine = _make_engine()
    user_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            headers, salon, user_id = await _create_user_and_salon(c, engine, "ss_noem")
            resp = await c.get(
                f"/api/salons/{salon['id']}/calculator-defaults/seuil_salaire",
                headers=headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "fields" in data
            assert "warnings" in data
            fields = data["fields"]
            # Eric defaults always present (source is either eric_default or salon_config.*)
            assert fields["taux_produits"]["value"] == pytest.approx(0.10)
            assert fields["taux_produits"]["source"] in ("eric_default", "salon_config.taux_produits")
            assert fields["taux_charges_fixes"]["value"] == pytest.approx(0.25)
            assert fields["pct_securite"]["value"] == pytest.approx(0.05)
            assert fields["pct_benefice"]["value"] == pytest.approx(0.10)
            assert fields["jours_semaine"]["value"] == pytest.approx(5.0)
            assert fields["semaines_an"]["value"] == pytest.approx(45.6)
            # No employee data — salary fields null with warning
            assert fields["salaire_brut"]["value"] is None
            assert len(data["warnings"]) > 0
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, [user_id] if user_id else [])
        await engine.dispose()


@pytest.mark.asyncio
async def test_seuil_salaire_with_employee_fills_employee_fields():
    """
    When an employee exists, seuil_salaire returns their salary and hours.
    Source should be 'employee_profile'.
    """
    engine = _make_engine()
    user_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            headers, salon, user_id = await _create_user_and_salon(c, engine, "ss_emp")
            salon_id = salon["id"]
            # Create an employee
            emp_r = await c.post(
                f"/api/salons/{salon_id}/employees",
                json={
                    "name": "Jacqueline Test",
                    "role_type": "salarie",
                    "contract_type": "cdi",
                    "hours_per_week": 35,
                    "weeks_per_year": 45.6,
                    "salary_brut": 2000.0,
                    "cotisations_patronales": 800.0,
                    "taux_occupation": 0.65,
                },
                headers=headers,
            )
            assert emp_r.status_code in (200, 201), emp_r.text

            resp = await c.get(
                f"/api/salons/{salon_id}/calculator-defaults/seuil_salaire",
                headers=headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            fields = data["fields"]
            assert fields["salaire_brut"]["value"] == pytest.approx(2000.0)
            assert fields["salaire_brut"]["source"] == "employee.salary_brut"
            assert fields["cotisations_patronales"]["value"] == pytest.approx(800.0)
            assert fields["heures_semaine"]["value"] == pytest.approx(35.0)
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, [user_id] if user_id else [])
        await engine.dispose()


@pytest.mark.asyncio
async def test_seuil_salaire_salon_config_margins_override_eric():
    """
    When salon_config has custom margin fields, they override Eric defaults.
    Source should be 'salon_config'.
    """
    engine = _make_engine()
    user_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            headers, salon, user_id = await _create_user_and_salon(c, engine, "ss_cfg")
            salon_id = salon["id"]
            # Set custom margins in salon config
            await c.put(
                f"/api/salons/{salon_id}/config",
                json={"taux_produits": 0.15, "taux_charges_fixes": 0.30},
                headers=headers,
            )
            resp = await c.get(
                f"/api/salons/{salon_id}/calculator-defaults/seuil_salaire",
                headers=headers,
            )
            assert resp.status_code == 200
            fields = resp.json()["fields"]
            assert fields["taux_produits"]["value"] == pytest.approx(0.15)
            assert fields["taux_produits"]["source"] == "salon_config.taux_produits"
            assert fields["taux_charges_fixes"]["value"] == pytest.approx(0.30)
            assert fields["taux_charges_fixes"]["source"] == "salon_config.taux_charges_fixes"
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, [user_id] if user_id else [])
        await engine.dispose()


# ── Cout Minute defaults ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cout_minute_returns_eric_default_majoration():
    """
    cout_minute defaults return majoration=0.10 (Eric default) when not set in salon_config.
    """
    engine = _make_engine()
    user_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            headers, salon, user_id = await _create_user_and_salon(c, engine, "cm_def")
            resp = await c.get(
                f"/api/salons/{salon['id']}/calculator-defaults/cout_minute",
                headers=headers,
            )
            assert resp.status_code == 200
            fields = resp.json()["fields"]
            # Service always returns salon_config.majoration_securite_benefice since
            # get_or_create_config seeds the column with the Eric default (0.10)
            assert fields["majoration"]["value"] == pytest.approx(0.10)
            assert fields["majoration"]["source"] == "salon_config.majoration_securite_benefice"
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, [user_id] if user_id else [])
        await engine.dispose()


@pytest.mark.asyncio
async def test_cout_minute_custom_majoration_from_salon_config():
    """
    If salon_config.majoration_securite_benefice is set, cout_minute reflects it.
    """
    engine = _make_engine()
    user_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            headers, salon, user_id = await _create_user_and_salon(c, engine, "cm_cfg")
            salon_id = salon["id"]
            await c.put(
                f"/api/salons/{salon_id}/config",
                json={"majoration_securite_benefice": 0.15},
                headers=headers,
            )
            resp = await c.get(
                f"/api/salons/{salon_id}/calculator-defaults/cout_minute",
                headers=headers,
            )
            assert resp.status_code == 200
            fields = resp.json()["fields"]
            assert fields["majoration"]["value"] == pytest.approx(0.15)
            assert fields["majoration"]["source"] == "salon_config.majoration_securite_benefice"
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, [user_id] if user_id else [])
        await engine.dispose()


# ── Error cases ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unknown_calc_key_returns_404():
    """Unknown calculator key → 404."""
    engine = _make_engine()
    user_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            headers, salon, user_id = await _create_user_and_salon(c, engine, "err_404")
            resp = await c.get(
                f"/api/salons/{salon['id']}/calculator-defaults/unknown_calculator",
                headers=headers,
            )
            assert resp.status_code == 404
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, [user_id] if user_id else [])
        await engine.dispose()


@pytest.mark.asyncio
async def test_unauthenticated_returns_401():
    """No session cookie → 401. Use a fresh client with no cookies."""
    engine = _make_engine()
    user_id = None
    salon_id = None
    try:
        # First, create a salon with a logged-in client to get a valid salon ID
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c_auth:
            _, salon, user_id = await _create_user_and_salon(c_auth, engine, "err_401")
            salon_id = salon["id"]
        # Now use a FRESH client with no cookies — this should be unauthenticated
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c_anon:
            resp = await c_anon.get(
                f"/api/salons/{salon_id}/calculator-defaults/seuil_salaire"
            )
            assert resp.status_code == 401
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, [user_id] if user_id else [])
        await engine.dispose()


@pytest.mark.asyncio
async def test_other_users_salon_returns_404():
    """
    User 2 tries to access User 1's salon defaults → 404.
    Uses separate clients so each user has their own cookie session.
    """
    engine = _make_engine()
    user_ids = []
    try:
        salon1_id = None
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c1:
            _, salon1, uid1 = await _create_user_and_salon(c1, engine, "err_own1")
            salon1_id = salon1["id"]
            user_ids.append(uid1)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c2:
            _, _salon2, uid2 = await _create_user_and_salon(c2, engine, "err_own2")
            user_ids.append(uid2)
            # User 2 (c2's cookie) tries to access user 1's salon
            resp = await c2.get(
                f"/api/salons/{salon1_id}/calculator-defaults/seuil_salaire"
            )
            assert resp.status_code == 404
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()
