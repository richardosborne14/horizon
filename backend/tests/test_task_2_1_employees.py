"""
Task 2.1: Employee CRUD API tests.

Follows the same self-contained pattern as test_task_1_7_salons.py:
  - Fresh async engine per test (avoids asyncpg connection state pollution)
  - Test users and salons created via API/DB inline, cleaned up in finally
  - No shared fixtures (except conftest event_loop)

Run: docker compose exec backend pytest tests/test_task_2_1_employees.py -v

Key assertions:
  - cout_total_mensuel computed correctly for salarié (brut + patronales)
  - cout_total_mensuel = salary_brut only for dirigeant (no patronales)
  - weeks_per_year=45.6 and taux_occupation=0.65 default (Eric's benchmarks)
  - Soft deactivate sets is_active=False, row preserved (historical data safe)
  - Unauthenticated requests return 401
  - Other user's salon employees return 404 (not 403)
"""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app
from app.models.salon import Employee
from app.services.auth import hash_password


# ── Shared helpers ────────────────────────────────────────────────────────────


async def _cleanup(db: AsyncSession, user_ids: list) -> None:
    """Delete all test data for user_ids — cascade handles salons, employees, sessions."""
    for uid in user_ids:
        await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
    await db.commit()


async def _login_and_create_salon(client: AsyncClient, email: str, password: str) -> tuple:
    """
    Log in and create a test salon. Returns (cookies, salon_id).

    Args:
        client: AsyncClient for the test app.
        email: Test user email.
        password: Test user password.

    Returns:
        Tuple of (cookies dict, salon_id string).
    """
    login = await client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert login.status_code == 200, f"Login failed: {login.text}"
    cookies = login.cookies

    salon = await client.post(
        "/api/salons",
        json={"name": "Salon Test Employés", "business_type": "auto_micro"},
        cookies=cookies,
    )
    assert salon.status_code == 201, f"Salon creation failed: {salon.text}"
    return cookies, salon.json()["id"]


VALID_BODY = {
    "name": "Julie Martin",
    "role_type": "salarie",
    "contract_type": "cdi",
    "hours_per_week": 35,
    "salary_brut": 1800.00,
    "cotisations_patronales": 720.00,
}


# ── Test: unauthenticated returns 401 ────────────────────────────────────────


@pytest.mark.asyncio
async def test_employees_unauthenticated_returns_401():
    """All employee endpoints require authentication."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        fake_id = uuid.uuid4()
        resp = await client.get(f"/api/salons/{fake_id}/employees")
        assert resp.status_code == 401


# ── Test: create salarié — cout_total_mensuel = brut + patronales ─────────────


@pytest.mark.asyncio
async def test_create_salarie_employee():
    """
    Create a salarié employee and verify:
      - 201 response
      - cout_total_mensuel = salary_brut + cotisations_patronales
      - is_active = True
    """
    engine = create_async_engine(settings.database_url, echo=False)
    email = "test.emp.salarie@example.com"
    user_ids = []

    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            from app.models.user import User
            user = User(
                email=email,
                password_hash=hash_password("TestPass123!"),
                name="Test Salarié",
            )
            db.add(user)
            await db.flush()
            user_ids.append(user.id)
            await db.commit()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            cookies, salon_id = await _login_and_create_salon(client, email, "TestPass123!")

            resp = await client.post(
                f"/api/salons/{salon_id}/employees",
                json=VALID_BODY,
                cookies=cookies,
            )
            assert resp.status_code == 201, resp.text
            data = resp.json()
            assert data["name"] == "Julie Martin"
            assert data["role_type"] == "salarie"
            assert data["contract_type"] == "cdi"
            assert float(data["salary_brut"]) == 1800.00
            assert float(data["cotisations_patronales"]) == 720.00
            assert data["is_active"] is True
            # cout_total_mensuel = 1800 + 720 = 2520 (employer total cost)
            assert float(data["cout_total_mensuel"]) == 2520.00, (
                f"Expected 2520.00, got {data['cout_total_mensuel']}"
            )
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


# ── Test: dirigeant — no patronales, cout_total = salary_brut only ────────────


@pytest.mark.asyncio
async def test_create_dirigeant_employee():
    """
    Dirigeant (salon owner / travailleur indépendant):
      - cotisations_patronales should be None (they declare to URSSAF directly)
      - cout_total_mensuel = salary_brut only (×1.45 applied at point mort level)
    """
    engine = create_async_engine(settings.database_url, echo=False)
    email = "test.emp.dirigeant@example.com"
    user_ids = []

    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            from app.models.user import User
            user = User(
                email=email,
                password_hash=hash_password("TestPass123!"),
                name="Test Dirigeant",
            )
            db.add(user)
            await db.flush()
            user_ids.append(user.id)
            await db.commit()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            cookies, salon_id = await _login_and_create_salon(client, email, "TestPass123!")

            resp = await client.post(
                f"/api/salons/{salon_id}/employees",
                json={
                    "name": "Marie Dupont",
                    "role_type": "dirigeant",
                    "hours_per_week": 40,
                    "salary_brut": 2500.00,
                    # no cotisations_patronales — dirigeant handles URSSAF directly
                },
                cookies=cookies,
            )
            assert resp.status_code == 201, resp.text
            data = resp.json()
            assert data["role_type"] == "dirigeant"
            assert data["cotisations_patronales"] is None
            # cout_total_mensuel = salary_brut only for dirigeant
            assert float(data["cout_total_mensuel"]) == 2500.00, (
                f"Expected 2500.00, got {data['cout_total_mensuel']}"
            )
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


# ── Test: defaults weeks_per_year=45.6 taux_occupation=0.65 ─────────────────


@pytest.mark.asyncio
async def test_employee_defaults():
    """
    When weeks_per_year and taux_occupation are not provided:
      - weeks_per_year defaults to 45.6 (Eric's Excel benchmark)
      - taux_occupation defaults to 0.65 (65% productivity rate)
    """
    engine = create_async_engine(settings.database_url, echo=False)
    email = "test.emp.defaults@example.com"
    user_ids = []

    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            from app.models.user import User
            user = User(
                email=email,
                password_hash=hash_password("TestPass123!"),
                name="Test Defaults",
            )
            db.add(user)
            await db.flush()
            user_ids.append(user.id)
            await db.commit()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            cookies, salon_id = await _login_and_create_salon(client, email, "TestPass123!")

            resp = await client.post(
                f"/api/salons/{salon_id}/employees",
                json={"name": "Test Défauts", "role_type": "salarie", "hours_per_week": 35},
                cookies=cookies,
            )
            assert resp.status_code == 201, resp.text
            data = resp.json()
            assert float(data["weeks_per_year"]) == 45.6, (
                f"Expected 45.6 (Eric's benchmark), got {data['weeks_per_year']}"
            )
            assert float(data["taux_occupation"]) == 0.65, (
                f"Expected 0.65 (65% productivity), got {data['taux_occupation']}"
            )
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


# ── Test: soft deactivate — row preserved with is_active=False ───────────────


@pytest.mark.asyncio
async def test_soft_deactivate_preserves_row():
    """
    DELETE /employees/{id} must soft-deactivate (is_active=False) NOT hard-delete.

    WHY: Historical monthly_salaries and payslip_forms reference this employee.
    Hard-deleting would cascade-delete all that financial history.
    """
    engine = create_async_engine(settings.database_url, echo=False)
    email = "test.emp.deactivate@example.com"
    user_ids = []
    emp_uuid = None

    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            from app.models.user import User
            user = User(
                email=email,
                password_hash=hash_password("TestPass123!"),
                name="Test Deactivate",
            )
            db.add(user)
            await db.flush()
            user_ids.append(user.id)
            await db.commit()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            cookies, salon_id = await _login_and_create_salon(client, email, "TestPass123!")

            create = await client.post(
                f"/api/salons/{salon_id}/employees", json=VALID_BODY, cookies=cookies
            )
            assert create.status_code == 201, create.text
            emp_id = create.json()["id"]
            emp_uuid = uuid.UUID(emp_id)

            delete = await client.delete(
                f"/api/salons/{salon_id}/employees/{emp_id}", cookies=cookies
            )
            assert delete.status_code == 204

            # Verify row stays in DB with is_active=False
            async with AsyncSession(engine, expire_on_commit=False) as db:
                result = await db.execute(
                    select(Employee).where(Employee.id == emp_uuid)
                )
                emp = result.scalar_one_or_none()
                assert emp is not None, "Employee row must NOT be hard-deleted"
                assert emp.is_active is False, "is_active must be False after deactivation"

            # Verify it's hidden from the default list (active only)
            list_resp = await client.get(
                f"/api/salons/{salon_id}/employees", cookies=cookies
            )
            assert list_resp.status_code == 200
            names = [e["name"] for e in list_resp.json()]
            assert "Julie Martin" not in names, "Deactivated employee must not appear in default list"

            # Verify it appears with include_inactive=true
            incl_resp = await client.get(
                f"/api/salons/{salon_id}/employees?include_inactive=true", cookies=cookies
            )
            assert incl_resp.status_code == 200
            names_incl = [e["name"] for e in incl_resp.json()]
            assert "Julie Martin" in names_incl, "Deactivated employee must appear with include_inactive=true"
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


# ── Test: partial update ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_partial_update_employee():
    """PUT with one field only changes that field. cout_total_mensuel recomputes."""
    engine = create_async_engine(settings.database_url, echo=False)
    email = "test.emp.update@example.com"
    user_ids = []

    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            from app.models.user import User
            user = User(
                email=email,
                password_hash=hash_password("TestPass123!"),
                name="Test Update",
            )
            db.add(user)
            await db.flush()
            user_ids.append(user.id)
            await db.commit()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            cookies, salon_id = await _login_and_create_salon(client, email, "TestPass123!")

            create = await client.post(
                f"/api/salons/{salon_id}/employees", json=VALID_BODY, cookies=cookies
            )
            assert create.status_code == 201
            emp_id = create.json()["id"]

            # Update only salary_brut
            update = await client.put(
                f"/api/salons/{salon_id}/employees/{emp_id}",
                json={"salary_brut": 2000.00},
                cookies=cookies,
            )
            assert update.status_code == 200, update.text
            data = update.json()
            assert float(data["salary_brut"]) == 2000.00
            assert data["name"] == "Julie Martin", "name must be unchanged"
            assert data["role_type"] == "salarie", "role_type must be unchanged"
            # cout_total_mensuel = 2000 + 720 = 2720
            assert float(data["cout_total_mensuel"]) == 2720.00, (
                f"Expected 2720.00, got {data['cout_total_mensuel']}"
            )
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


# ── Test: other user's salon returns 404 ─────────────────────────────────────


@pytest.mark.asyncio
async def test_other_users_salon_employees_returns_404():
    """
    User A must receive 404 when accessing User B's salon employees.
    WHY 404 not 403: We don't reveal whether the salon exists at all.
    """
    engine = create_async_engine(settings.database_url, echo=False)
    email_a = "test.emp.user_a@example.com"
    email_b = "test.emp.user_b@example.com"
    user_ids = []

    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            from app.models.user import User
            for email, name in [(email_a, "User A"), (email_b, "User B")]:
                u = User(
                    email=email,
                    password_hash=hash_password("TestPass123!"),
                    name=name,
                )
                db.add(u)
                await db.flush()
                user_ids.append(u.id)
            await db.commit()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # User B creates a salon
            cookies_b, salon_id_b = await _login_and_create_salon(client, email_b, "TestPass123!")

            # User A logs in
            login_a = await client.post(
                "/api/auth/login", json={"email": email_a, "password": "TestPass123!"}
            )
            cookies_a = login_a.cookies

            # User A tries to access User B's salon employees — must be 404
            resp = await client.get(
                f"/api/salons/{salon_id_b}/employees", cookies=cookies_a
            )
            assert resp.status_code == 404, (
                f"Expected 404 (not 403) — must not reveal foreign salon existence. Got {resp.status_code}"
            )
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


# ── Test: validation — hours_per_week must be > 0 ─────────────────────────────


@pytest.mark.asyncio
async def test_hours_per_week_must_be_positive():
    """hours_per_week = 0 must return 422 Unprocessable Entity."""
    engine = create_async_engine(settings.database_url, echo=False)
    email = "test.emp.valid.hours@example.com"
    user_ids = []

    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            from app.models.user import User
            user = User(
                email=email,
                password_hash=hash_password("TestPass123!"),
                name="Test Validation Hours",
            )
            db.add(user)
            await db.flush()
            user_ids.append(user.id)
            await db.commit()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            cookies, salon_id = await _login_and_create_salon(client, email, "TestPass123!")

            resp = await client.post(
                f"/api/salons/{salon_id}/employees",
                json={**VALID_BODY, "hours_per_week": 0},
                cookies=cookies,
            )
            assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


# ── Test: validation — taux_occupation must be 0–1 ───────────────────────────


@pytest.mark.asyncio
async def test_taux_occupation_must_be_zero_to_one():
    """taux_occupation > 1 must return 422 Unprocessable Entity."""
    engine = create_async_engine(settings.database_url, echo=False)
    email = "test.emp.valid.taux@example.com"
    user_ids = []

    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            from app.models.user import User
            user = User(
                email=email,
                password_hash=hash_password("TestPass123!"),
                name="Test Validation Taux",
            )
            db.add(user)
            await db.flush()
            user_ids.append(user.id)
            await db.commit()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            cookies, salon_id = await _login_and_create_salon(client, email, "TestPass123!")

            resp = await client.post(
                f"/api/salons/{salon_id}/employees",
                json={**VALID_BODY, "taux_occupation": 1.5},
                cookies=cookies,
            )
            assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


# ── Test: cout_total_mensuel is None when no salary set ──────────────────────


@pytest.mark.asyncio
async def test_cout_total_mensuel_none_when_no_salary():
    """cout_total_mensuel must be None when salary_brut is not provided."""
    engine = create_async_engine(settings.database_url, echo=False)
    email = "test.emp.nosalary@example.com"
    user_ids = []

    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            from app.models.user import User
            user = User(
                email=email,
                password_hash=hash_password("TestPass123!"),
                name="Test No Salary",
            )
            db.add(user)
            await db.flush()
            user_ids.append(user.id)
            await db.commit()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            cookies, salon_id = await _login_and_create_salon(client, email, "TestPass123!")

            resp = await client.post(
                f"/api/salons/{salon_id}/employees",
                json={"name": "Sans salaire", "role_type": "salarie", "hours_per_week": 35},
                cookies=cookies,
            )
            assert resp.status_code == 201, resp.text
            assert resp.json()["cout_total_mensuel"] is None
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()
