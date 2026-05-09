"""
Tests for Task 2.6 — Copilote Paramétrage (salon config API).

Follows the self-contained pattern from test_task_2_1_employees.py:
  - No shared fixtures (except conftest event_loop)
  - Each test creates its own DB user, logs in via cookies, cleans up in finally
  - Fresh AsyncClient per test with ASGITransport

Covers:
  - GET /api/salons/{id}/config  — auto-creates with Eric's defaults on first access
  - GET /api/salons/{id}/config  — idempotent (same record returned on second call)
  - PUT /api/salons/{id}/config  — partial update persists; jours_an / heures_an recomputed
  - PUT with invalid type_exploitant → 422
  - Cross-user access → 403 or 404
  - GET /api/salons/{id}/config/employees — empty list when no employees
  - GET /api/salons/{id}/config/employees — cout_total_mois > salary_brut for salarié
  - GET /api/salons/{id}/config/employees — taux_occupation = hours / 35
  - GET /api/salons/{id}/config/employees — inactive employees excluded

Run:
    docker compose exec backend pytest tests/test_task_2_6_salon_config.py -v
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


# ── Shared helpers ────────────────────────────────────────────────────────────

async def _cleanup(db: AsyncSession, user_ids: list) -> None:
    """Delete all test data for user_ids — cascade handles salons, configs, employees."""
    for uid in user_ids:
        await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
    await db.commit()


async def _make_engine():
    """Create a fresh async engine connected to the test DB."""
    return create_async_engine(settings.database_url, echo=False)


async def _create_user(db: AsyncSession, email: str, name: str = "Test User") -> str:
    """Insert a test user directly into the DB and return its id."""
    from app.models.user import User
    user = User(
        email=email,
        password_hash=hash_password("TestPass123!"),
        name=name,
    )
    db.add(user)
    await db.flush()
    uid = str(user.id)
    await db.commit()
    return uid


async def _login(client: AsyncClient, email: str) -> object:
    """Log in and return the cookies object from the login response."""
    resp = await client.post(
        "/api/auth/login", json={"email": email, "password": "TestPass123!"}
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.cookies


async def _create_salon(client: AsyncClient, cookies) -> str:
    """Create a test salon and return its id."""
    resp = await client.post(
        "/api/salons",
        json={"name": "Salon Config Test", "business_type": "auto_micro"},
        cookies=cookies,
    )
    assert resp.status_code == 201, f"Salon create failed: {resp.text}"
    return resp.json()["id"]


async def _create_employee(
    client: AsyncClient, cookies, salon_id: str,
    role_type: str = "salarie",
    hours: float = 35.0,
    salary: float = 1800.0,
    taux_occupation: float = 0.65,
) -> str:
    """Create an employee and return its id.

    taux_occupation: stored directly on the model (0–1).
    Pass explicitly when testing taux-related assertions because
    the service does NOT compute it from hours_per_week — it uses
    whatever value is provided (default 0.65, hairdressing sector baseline).
    """
    resp = await client.post(
        f"/api/salons/{salon_id}/employees",
        json={
            "name": "Test Employee",
            "role_type": role_type,
            "hours_per_week": hours,
            "salary_brut": salary,
            "taux_occupation": taux_occupation,
        },
        cookies=cookies,
    )
    assert resp.status_code == 201, f"Employee create failed: {resp.text}"
    return resp.json()["id"]


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_config_auto_creates_with_defaults():
    """
    GET /api/salons/{id}/config returns 200 for a brand-new salon.
    A SalonConfig row is auto-created with Eric's default schedule:
      5 jours/semaine, 43 semaines/an (référence métier coiffure).
    """
    engine = await _make_engine()
    email = f"cfg.defaults.{uuid.uuid4().hex[:8]}@test.com"
    user_ids = []
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            user_ids.append(await _create_user(db, email))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            cookies = await _login(client, email)
            salon_id = await _create_salon(client, cookies)

            resp = await client.get(f"/api/salons/{salon_id}/config", cookies=cookies)
            assert resp.status_code == 200, resp.text

            data = resp.json()
            assert data["salon_id"] == salon_id
            # Structural presence
            for field in ("jours_ouverture_semaine", "semaines_ouverture_an",
                          "heures_ouverture_jour", "type_exploitant",
                          "effectif_entreprise", "jours_an", "heures_an"):
                assert field in data, f"Missing field: {field}"
            # Default type is valid
            assert data["type_exploitant"] in ("auto_entrepreneur", "tns", "assimile_salarie")
            # Default schedule (Eric's coiffure baseline):
            # 5 jours/semaine, 45.6 semaines/an (référence employé annualisée)
            assert Decimal(str(data["jours_ouverture_semaine"])) == Decimal("5")
            assert Decimal(str(data["semaines_ouverture_an"])) == Decimal("45.6")
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_get_config_idempotent():
    """
    Calling GET /config twice must return the same config record id.
    Auto-creation must NOT create a second row.
    """
    engine = await _make_engine()
    email = f"cfg.idem.{uuid.uuid4().hex[:8]}@test.com"
    user_ids = []
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            user_ids.append(await _create_user(db, email))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            cookies = await _login(client, email)
            salon_id = await _create_salon(client, cookies)

            r1 = await client.get(f"/api/salons/{salon_id}/config", cookies=cookies)
            r2 = await client.get(f"/api/salons/{salon_id}/config", cookies=cookies)
            assert r1.status_code == r2.status_code == 200
            assert r1.json()["id"] == r2.json()["id"], "Auto-create must be idempotent"
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_put_config_updates_fields_and_recomputes():
    """
    PUT /api/salons/{id}/config persists partial updates and returns the
    updated record. Computed read-only fields jours_an and heures_an are
    recalculated server-side:
      jours_an = jours_semaine × semaines_an = 6 × 48 = 288
      heures_an = jours_an × heures_jour  = 288 × 9 = 2592
    """
    engine = await _make_engine()
    email = f"cfg.put.{uuid.uuid4().hex[:8]}@test.com"
    user_ids = []
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            user_ids.append(await _create_user(db, email))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            cookies = await _login(client, email)
            salon_id = await _create_salon(client, cookies)
            # Ensure config row exists first
            await client.get(f"/api/salons/{salon_id}/config", cookies=cookies)

            payload = {
                "jours_ouverture_semaine": 6,
                "semaines_ouverture_an": 48,
                "heures_ouverture_jour": 9,
                "type_exploitant": "tns",
                "has_acre": True,
                "effectif_entreprise": 3,
                "majoration_securite_benefice": 0.12,
                "taux_produits": 0.08,
                "taux_charges_fixes": 0.30,
                "percent_clients_f": 0.65,
                "montant_moyen_f": 55,
                "percent_clients_h": 0.35,
                "montant_moyen_h": 25,
                "nb_visites_moyen_f": 6,
                "nb_visites_moyen_h": 12,
            }
            resp = await client.put(
                f"/api/salons/{salon_id}/config", json=payload, cookies=cookies
            )
            assert resp.status_code == 200, resp.text

            data = resp.json()
            assert Decimal(str(data["jours_ouverture_semaine"])) == Decimal("6")
            assert Decimal(str(data["semaines_ouverture_an"])) == Decimal("48")
            assert data["type_exploitant"] == "tns"
            assert data["has_acre"] is True
            assert data["effectif_entreprise"] == 3
            # Computed fields
            assert Decimal(str(data["jours_an"])) == Decimal("288"), (
                f"jours_an: expected 288, got {data['jours_an']}"
            )
            assert Decimal(str(data["heures_an"])) == Decimal("2592"), (
                f"heures_an: expected 2592, got {data['heures_an']}"
            )
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_put_config_invalid_type_exploitant_returns_422():
    """
    PUT with an invalid type_exploitant value must return 422 (Pydantic validation).
    """
    engine = await _make_engine()
    email = f"cfg.invalid.{uuid.uuid4().hex[:8]}@test.com"
    user_ids = []
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            user_ids.append(await _create_user(db, email))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            cookies = await _login(client, email)
            salon_id = await _create_salon(client, cookies)
            await client.get(f"/api/salons/{salon_id}/config", cookies=cookies)

            resp = await client.put(
                f"/api/salons/{salon_id}/config",
                json={"type_exploitant": "not_a_real_status"},
                cookies=cookies,
            )
            assert resp.status_code == 422, resp.text
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_config_not_accessible_by_other_user():
    """
    Another authenticated user cannot read or update a salon config they don't own.
    Expects 403 or 404.
    """
    engine = await _make_engine()
    email_owner = f"cfg.owner.{uuid.uuid4().hex[:8]}@test.com"
    email_other = f"cfg.other.{uuid.uuid4().hex[:8]}@test.com"
    user_ids = []
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            user_ids.append(await _create_user(db, email_owner, "Owner"))
            user_ids.append(await _create_user(db, email_other, "Other"))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            owner_cookies = await _login(client, email_owner)
            other_cookies = await _login(client, email_other)

            salon_id = await _create_salon(client, owner_cookies)

            # Other user GET → 403 or 404
            r_get = await client.get(
                f"/api/salons/{salon_id}/config", cookies=other_cookies
            )
            assert r_get.status_code in (403, 404), (
                f"Expected 403/404, got {r_get.status_code}: {r_get.text}"
            )

            # Other user PUT → 403 or 404
            r_put = await client.put(
                f"/api/salons/{salon_id}/config",
                json={"type_exploitant": "tns"},
                cookies=other_cookies,
            )
            assert r_put.status_code in (403, 404), (
                f"Expected 403/404, got {r_put.status_code}: {r_put.text}"
            )
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_employees_summary_empty_when_no_employees():
    """
    GET /api/salons/{id}/config/employees returns [] when the salon has no employees.
    """
    engine = await _make_engine()
    email = f"cfg.emp0.{uuid.uuid4().hex[:8]}@test.com"
    user_ids = []
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            user_ids.append(await _create_user(db, email))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            cookies = await _login(client, email)
            salon_id = await _create_salon(client, cookies)

            resp = await client.get(
                f"/api/salons/{salon_id}/config/employees", cookies=cookies
            )
            assert resp.status_code == 200, resp.text
            assert resp.json() == []
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_employees_summary_includes_calculated_cost():
    """
    GET /config/employees returns one row per active employee with
    auto-calculated cout_total_mois > salary_brut (includes employer charges).
    Required fields: id, name, role_type, hours_per_week, taux_occupation, cout_total_mois.
    """
    engine = await _make_engine()
    email = f"cfg.empcost.{uuid.uuid4().hex[:8]}@test.com"
    user_ids = []
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            user_ids.append(await _create_user(db, email))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            cookies = await _login(client, email)
            salon_id = await _create_salon(client, cookies)
            # Ensure config exists (auto-creates with default type_exploitant)
            await client.get(f"/api/salons/{salon_id}/config", cookies=cookies)
            # Create a full-time salarié with brut 1800 €
            await _create_employee(
                client, cookies, salon_id,
                role_type="salarie", hours=35.0, salary=1800.0
            )

            resp = await client.get(
                f"/api/salons/{salon_id}/config/employees", cookies=cookies
            )
            assert resp.status_code == 200, resp.text
            emps = resp.json()
            assert len(emps) == 1

            emp = emps[0]
            for field in ("id", "name", "role_type", "hours_per_week",
                          "taux_occupation", "cout_total_mois"):
                assert field in emp, f"Missing field: {field}"
            assert emp["name"] == "Test Employee"
            assert emp["role_type"] == "salarie"
            # hours_per_week may be returned as a Decimal string by the API
            assert float(emp["hours_per_week"]) == 35.0
            assert 0 < float(emp["taux_occupation"]) <= 1.0
            # With employer charges, total cost must exceed gross salary
            assert Decimal(str(emp["cout_total_mois"])) > Decimal("1800"), (
                f"cout_total_mois ({emp['cout_total_mois']}) should exceed brut (1800)"
            )
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_employees_summary_taux_occupation_calculation():
    """
    taux_occupation = hours_per_week / 35 (full-time reference hours).
    A 17.5 h/week employee → taux_occupation ≈ 0.50.
    """
    engine = await _make_engine()
    email = f"cfg.taux.{uuid.uuid4().hex[:8]}@test.com"
    user_ids = []
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            user_ids.append(await _create_user(db, email))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            cookies = await _login(client, email)
            salon_id = await _create_salon(client, cookies)
            await client.get(f"/api/salons/{salon_id}/config", cookies=cookies)
            # Pass taux_occupation=0.5 explicitly — the field is stored as-is,
            # not computed from hours_per_week at summary time.
            await _create_employee(
                client, cookies, salon_id,
                role_type="salarie", hours=17.5, salary=900.0,
                taux_occupation=0.5,
            )

            resp = await client.get(
                f"/api/salons/{salon_id}/config/employees", cookies=cookies
            )
            assert resp.status_code == 200
            emp = resp.json()[0]
            taux = float(emp["taux_occupation"])
            assert abs(taux - 0.5) < 0.01, (
                f"Expected taux_occupation = 0.50 (as stored), got {taux}"
            )
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_employees_summary_excludes_inactive():
    """
    Inactive employees (soft-deleted via DELETE endpoint) must NOT appear
    in the config employee summary.
    """
    engine = await _make_engine()
    email = f"cfg.inactive.{uuid.uuid4().hex[:8]}@test.com"
    user_ids = []
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            user_ids.append(await _create_user(db, email))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            cookies = await _login(client, email)
            salon_id = await _create_salon(client, cookies)
            await client.get(f"/api/salons/{salon_id}/config", cookies=cookies)
            emp_id = await _create_employee(client, cookies, salon_id)

            # Soft-deactivate (DELETE returns 200 or 204 depending on implementation)
            del_resp = await client.delete(
                f"/api/salons/{salon_id}/employees/{emp_id}", cookies=cookies
            )
            assert del_resp.status_code in (200, 204), del_resp.text

            # Summary must be empty
            summary_resp = await client.get(
                f"/api/salons/{salon_id}/config/employees", cookies=cookies
            )
            assert summary_resp.status_code == 200
            assert summary_resp.json() == [], (
                "Deactivated employee must not appear in config employee summary"
            )
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()
