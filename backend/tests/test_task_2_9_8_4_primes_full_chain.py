"""
Tests for Task 2.9.8.4 — Primes Full Chain:
  - GET /api/salons/{id}/employees/{id}/prime-target-options
  - POST /api/salons/{id}/employees/{id}/prime-preview

These endpoints power the 3-source target card and the live bonus simulation panel
on the primes calculator page.
"""

import uuid
from decimal import Decimal

import pytest
from starlette.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app
from app.services.auth import hash_password


# ── Shared fixtures ────────────────────────────────────────────────────────────

_TEST_EMAIL = "test_primes_chain_2984@example.com"
_TEST_PASSWORD = "TestPassword123!"


def _create_user_and_login(client: TestClient) -> tuple[str, dict]:
    """
    Create test user if needed, log in, return (user_email, cookies_dict).
    Returns auth cookies dict ready for TestClient use.
    """
    import asyncio

    engine = create_async_engine(settings.database_url, echo=False)

    async def _ensure_user():
        async with AsyncSession(engine, expire_on_commit=False) as db:
            from app.models.user import User
            from sqlalchemy import select
            result = await db.execute(select(User).where(User.email == _TEST_EMAIL))
            if not result.scalar_one_or_none():
                user = User(
                    email=_TEST_EMAIL,
                    password_hash=hash_password(_TEST_PASSWORD),
                    name="Primes Chain Test",
                )
                db.add(user)
                await db.commit()
        await engine.dispose()

    asyncio.get_event_loop().run_until_complete(_ensure_user())
    resp = client.post("/api/auth/login", json={"email": _TEST_EMAIL, "password": _TEST_PASSWORD})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.cookies


@pytest.fixture(scope="module")
def client():
    """Synchronous TestClient against the FastAPI app."""
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture(scope="module")
def auth_cookies(client):
    """Log in once per module and return cookies."""
    return _create_user_and_login(client)


@pytest.fixture(scope="module")
def auth_headers():
    """Return empty dict — project uses cookie auth, not header auth."""
    return {}


@pytest.fixture(scope="module")
def test_salon(client, auth_cookies):
    """Create a test salon for this module's tests."""
    resp = client.post(
        "/api/salons",
        json={"name": "Salon Primes Chain Test", "business_type": "sarl"},
        cookies=auth_cookies,
    )
    assert resp.status_code == 201, f"Salon creation failed: {resp.text}"
    return resp.json()


@pytest.fixture(scope="module")
def test_employee(client, auth_cookies, test_salon):
    """Create a test employee (salarié) with a salary for computing target."""
    resp = client.post(
        f"/api/salons/{test_salon['id']}/employees",
        json={
            "name": "Julie TestPrimes",
            "role_type": "salarie",
            "contract_type": "cdi",
            "hours_per_week": 35,
            "salary_brut": 2500.0,
            "cotisations_patronales": 1125.0,
            "taux_occupation": 0.65,
        },
        cookies=auth_cookies,
    )
    assert resp.status_code == 201, f"Employee creation failed: {resp.text}"
    return resp.json()


@pytest.fixture
def db_session():
    """Provides a sync-compatible db session stub — only used for direct DB inserts in tests."""
    import asyncio
    engine = create_async_engine(settings.database_url, echo=False)

    class SyncDB:
        """Thin wrapper that runs async SQLAlchemy calls synchronously."""
        def add(self, obj):
            self._pending = getattr(self, '_pending', [])
            self._pending.append(obj)

        def commit_with(self, obj):
            async def _go():
                async with AsyncSession(engine, expire_on_commit=False) as s:
                    s.add(obj)
                    await s.commit()
                    await s.refresh(obj)
            asyncio.get_event_loop().run_until_complete(_go())

    return SyncDB()


# Override client fixture for individual tests that need per-test cookies
@pytest.fixture
def auth_client(client, auth_cookies):
    """Returns a partially-configured client that sends auth cookies automatically."""
    class CookieClient:
        def get(self, url, **kwargs):
            kwargs.setdefault('cookies', auth_cookies)
            return client.get(url, **kwargs)
        def post(self, url, **kwargs):
            kwargs.setdefault('cookies', auth_cookies)
            return client.post(url, **kwargs)
    return CookieClient()


# ─────────────────────────────────────────────────────────────────────────────
# Target Options Endpoint Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPrimeTargetOptions:
    """Tests for GET /api/salons/{id}/employees/{id}/prime-target-options."""

    def test_returns_three_sources(self, client, auth_headers, test_salon, test_employee):
        """Always returns exactly 3 source options."""
        resp = client.get(
            f"/api/salons/{test_salon['id']}/employees/{test_employee['id']}/prime-target-options",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["employee_id"] == str(test_employee["id"])
        assert "employee_name" in data
        options = data["options"]
        assert len(options) == 3

    def test_manual_always_available(self, client, auth_headers, test_salon, test_employee):
        """Manual source is always available with no pre-filled value."""
        resp = client.get(
            f"/api/salons/{test_salon['id']}/employees/{test_employee['id']}/prime-target-options",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        options = {o["source"]: o for o in resp.json()["options"]}
        manual = options["manual"]
        assert manual["available"] is True
        assert manual["value"] is None

    def test_seuil_salaire_unavailable_when_no_history(
        self, client, auth_headers, test_salon, test_employee
    ):
        """seuil_salaire source is unavailable when no calculation history exists."""
        resp = client.get(
            f"/api/salons/{test_salon['id']}/employees/{test_employee['id']}/prime-target-options",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        options = {o["source"]: o for o in resp.json()["options"]}
        seuil = options["seuil_salaire"]
        assert seuil["available"] is False
        assert seuil["value"] is None

    def test_pilotage_avg_unavailable_when_insufficient_data(
        self, client, auth_headers, test_salon, test_employee
    ):
        """pilotage_avg unavailable when fewer than 3 months have CA > 0."""
        resp = client.get(
            f"/api/salons/{test_salon['id']}/employees/{test_employee['id']}/prime-target-options",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        options = {o["source"]: o for o in resp.json()["options"]}
        pilotage = options["pilotage_avg"]
        assert pilotage["available"] is False
        assert pilotage["value"] is None

    def test_seuil_salaire_available_with_history(
        self, client, auth_headers, test_salon, test_employee
    ):
        """seuil_salaire source provides value when calculation history exists."""
        import asyncio
        from app.models.financial import CalculationHistory
        from app.models.user import User
        from sqlalchemy import select

        salon_uuid = uuid.UUID(test_salon["id"])

        async def _seed():
            """Insert a seuil_salaire history row for the test salon."""
            engine = create_async_engine(settings.database_url, echo=False)
            async with AsyncSession(engine, expire_on_commit=False) as db:
                # Get the test user (owner of test_salon)
                result = await db.execute(
                    select(User).where(User.email == _TEST_EMAIL)
                )
                user = result.scalar_one_or_none()
                if user is None:
                    await engine.dispose()
                    return None
                entry = CalculationHistory(
                    salon_id=salon_uuid,
                    user_id=user.id,
                    calculator_type="seuil_salaire",
                    inputs={"test": True},
                    outputs={"objectif_mois_ht": 8500.0, "objectif_jour_ttc": 350.0},
                )
                db.add(entry)
                await db.commit()
            await engine.dispose()

        asyncio.get_event_loop().run_until_complete(_seed())

        resp = client.get(
            f"/api/salons/{test_salon['id']}/employees/{test_employee['id']}/prime-target-options",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        options = {o["source"]: o for o in resp.json()["options"]}
        seuil = options["seuil_salaire"]
        assert seuil["available"] is True
        assert seuil["value"] is not None
        assert seuil["value"] > 0
        assert seuil["ref"] is not None

    def test_requires_authentication(self, test_salon, test_employee):
        """Endpoint requires authentication — uses a cookie-free fresh client."""
        # WHY fresh client: module-scoped client has cookies from login setup.
        # A bare request without cookies must get 401.
        with TestClient(app, raise_server_exceptions=True) as fresh:
            resp = fresh.get(
                f"/api/salons/{test_salon['id']}/employees/{test_employee['id']}/prime-target-options",
            )
        assert resp.status_code == 401

    def test_rejects_wrong_salon(
        self, client, auth_headers, test_employee
    ):
        """Returns 404 for an employee not in the requested salon."""
        wrong_salon = str(uuid.uuid4())
        resp = client.get(
            f"/api/salons/{wrong_salon}/employees/{test_employee['id']}/prime-target-options",
            headers=auth_headers,
        )
        assert resp.status_code in (403, 404)


# ─────────────────────────────────────────────────────────────────────────────
# Preview Endpoint Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPrimePreview:
    """Tests for POST /api/salons/{id}/employees/{id}/prime-preview."""

    def test_below_target_returns_zero_bonus(
        self, client, auth_headers, test_salon, test_employee
    ):
        """When actual < target, bonus is 0 and slices list is empty."""
        resp = client.post(
            f"/api/salons/{test_salon['id']}/employees/{test_employee['id']}/prime-preview",
            headers=auth_headers,
            json={
                "target": 10000.0,
                "actual": 8000.0,
                "source_target_origin": "manual",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["excess"] == 0.0
        assert data["total_bonus"] == 0.0
        assert data["slices"] == []

    def test_at_target_returns_zero_bonus(
        self, client, auth_headers, test_salon, test_employee
    ):
        """Exactly at target → zero bonus."""
        resp = client.post(
            f"/api/salons/{test_salon['id']}/employees/{test_employee['id']}/prime-preview",
            headers=auth_headers,
            json={
                "target": 10000.0,
                "actual": 10000.0,
                "source_target_origin": "manual",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["excess"] == 0.0
        assert data["total_bonus"] == 0.0

    def test_above_target_returns_slices(
        self, client, auth_headers, test_salon, test_employee
    ):
        """When actual > target, breakdown contains at least one slice with bonus > 0."""
        resp = client.post(
            f"/api/salons/{test_salon['id']}/employees/{test_employee['id']}/prime-preview",
            headers=auth_headers,
            json={
                "target": 10000.0,
                "actual": 11000.0,  # 1000 excess → falls in first Eric band (0-600 at 10%)
                "source_target_origin": "manual",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["excess"] == 1000.0
        assert data["total_bonus"] > 0
        assert len(data["slices"]) >= 1
        # Each slice must have the required fields
        for s in data["slices"]:
            assert "from_amount" in s
            assert "to_amount" in s
            assert "rate" in s
            assert "slice_amount" in s
            assert "bonus" in s
            assert s["bonus"] >= 0

    def test_slice_math_is_correct(
        self, client, auth_headers, test_salon, test_employee
    ):
        """Verify bonus = slice_amount × rate for each slice, and slices sum to total_bonus."""
        resp = client.post(
            f"/api/salons/{test_salon['id']}/employees/{test_employee['id']}/prime-preview",
            headers=auth_headers,
            json={
                "target": 10000.0,
                "actual": 11500.0,  # 1500 excess → crosses first Eric band boundary at 600
                "source_target_origin": "manual",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        for s in data["slices"]:
            expected_bonus = round(s["slice_amount"] * s["rate"], 2)
            assert abs(s["bonus"] - expected_bonus) < 0.01, (
                f"Slice math wrong: {s['slice_amount']} × {s['rate']} ≠ {s['bonus']}"
            )
        total_from_slices = round(sum(s["bonus"] for s in data["slices"]), 2)
        assert abs(total_from_slices - data["total_bonus"]) < 0.01

    def test_response_includes_provenance_fields(
        self, client, auth_headers, test_salon, test_employee
    ):
        """Response includes source_target_origin and source_target_ref."""
        resp = client.post(
            f"/api/salons/{test_salon['id']}/employees/{test_employee['id']}/prime-preview",
            headers=auth_headers,
            json={
                "target": 10000.0,
                "actual": 11000.0,
                "source_target_origin": "seuil_salaire",
                "source_target_ref": str(uuid.uuid4()),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_target_origin"] == "seuil_salaire"
        assert data["source_target_ref"] is not None

    def test_requires_authentication(self, test_salon, test_employee):
        """Endpoint requires authentication — uses a cookie-free fresh client."""
        # WHY fresh client: same reason as target-options auth test.
        with TestClient(app, raise_server_exceptions=True) as fresh:
            resp = fresh.post(
                f"/api/salons/{test_salon['id']}/employees/{test_employee['id']}/prime-preview",
                json={"target": 10000.0, "actual": 11000.0},
            )
        assert resp.status_code == 401

    def test_large_excess_exhausts_all_bands(
        self, client, auth_headers, test_salon, test_employee
    ):
        """Very large excess activates the unbounded last band (to_amount=None)."""
        resp = client.post(
            f"/api/salons/{test_salon['id']}/employees/{test_employee['id']}/prime-preview",
            headers=auth_headers,
            json={
                "target": 10000.0,
                "actual": 20000.0,  # 10,000 excess — way beyond Eric's 2700 boundary
                "source_target_origin": "manual",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["excess"] == 10000.0
        assert data["total_bonus"] > 0
        # The last slice should have to_amount=null (unbounded)
        last_slice = data["slices"][-1]
        assert last_slice["to_amount"] is None
