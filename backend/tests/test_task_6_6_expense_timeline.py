"""
Sprint 6 — TASK-6.6 Expense Evolution Timeline tests.

Tests:
  - Expense timeline structure (all fields present)
  - Total expenses are positive
  - First year delta is 0.00
  - Loan termination events detected
  - Scale validation (422 on bad scale)
  - Different scales produce different results
  - Kid independence events detected
  - No duplicate events
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.main import app


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_email() -> str:
    """Generate a unique email so each test user is isolated."""
    return f"t66_{uuid.uuid4().hex[:8]}@test.com"


def _make_password() -> str:
    return "Test1234!"


async def _register_and_get_headers(client: AsyncClient) -> tuple[dict, str]:
    """Register a unique user and return (auth_headers, user_id)."""
    email = _make_email()
    password = _make_password()

    resp = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
            "name": "Test User",
        },
    )
    assert resp.status_code in (201, 200), f"Register failed: {resp.text}"

    # Extract session cookie
    cookies = resp.cookies
    cookie_header = "; ".join(
        f"{name}={value}" for name, value in cookies.items()
    )
    return {"Cookie": cookie_header}, email


async def _get_user_id(engine, email: str) -> str:
    """Get the UUID for a user by email."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": email},
        )
        row = result.fetchone()
        return str(row[0])


async def _seed_profile(engine, user_id: str) -> None:
    """Directly insert a profile with required fields for projection."""
    async with engine.connect() as conn:
        # Check if profile exists
        result = await conn.execute(
            text("SELECT id FROM user_profiles WHERE user_id = :uid"),
            {"uid": user_id},
        )
        if result.fetchone() is None:
            await conn.execute(
                text(
                    """INSERT INTO user_profiles (id, user_id, birth_date,
                       target_retirement_age, monthly_gross_ca, monthly_expenses,
                       ae_activity_type)
                       VALUES (gen_random_uuid(), :uid, :bd, 67, :ca,
                               :expenses, 'bnc_non_reglementee')"""
                ),
                {
                    "uid": user_id,
                    "bd": date(1985, 6, 15),
                    "ca": "5000",
                    "expenses": '{"logement": "1200", "alimentation": "800"}',
                },
            )
        await conn.commit()


async def _get_expense_timeline(
    client: AsyncClient, headers: dict, scale: str = "moderate"
) -> dict:
    """Hit the expense timeline endpoint and return JSON."""
    resp = await client.get(
        f"/api/projection/expense-timeline?scale={scale}", headers=headers
    )
    assert resp.status_code == 200, (
        f"Expected 200, got {resp.status_code}: {resp.text}"
    )
    return resp.json()


# ── Tests ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_expense_timeline_structure():
    """Basic smoke test: timeline has correct structure for a user with profile."""
    engine = create_async_engine(settings.database_url, echo=False)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        headers, email = await _register_and_get_headers(client)
        user_id = await _get_user_id(engine, email)
        await _seed_profile(engine, user_id)

        data = await _get_expense_timeline(client, headers)

        assert "timeline" in data
        assert "key_events" in data
        assert len(data["timeline"]) > 0

        first_year = data["timeline"][0]
        assert "year" in first_year
        assert "age" in first_year
        assert "base_expenses_monthly" in first_year
        assert "loan_payments_monthly" in first_year
        assert "kid_expenses_monthly" in first_year
        assert "pet_expenses_monthly" in first_year
        assert "car_expenses_monthly" in first_year
        assert "tech_expenses_monthly" in first_year
        assert "recurring_monthly" in first_year
        assert "project_expenses_monthly" in first_year
        assert "total_monthly" in first_year
        assert "events" in first_year
        assert "delta_vs_previous" in first_year

    await engine.dispose()


@pytest.mark.asyncio
async def test_expense_timeline_total_positive():
    """Total monthly expenses should be positive for a configured user."""
    engine = create_async_engine(settings.database_url, echo=False)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        headers, email = await _register_and_get_headers(client)
        user_id = await _get_user_id(engine, email)
        await _seed_profile(engine, user_id)

        data = await _get_expense_timeline(client, headers)

        for entry in data["timeline"]:
            total = Decimal(entry["total_monthly"])
            assert total >= 0, (
                f"Year {entry['year']}: total_monthly is negative ({total})"
            )

    await engine.dispose()


@pytest.mark.asyncio
async def test_delta_vs_previous_first_year_zero():
    """The first year's delta_vs_previous should be 0.00 (no prior year)."""
    engine = create_async_engine(settings.database_url, echo=False)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        headers, email = await _register_and_get_headers(client)
        user_id = await _get_user_id(engine, email)
        await _seed_profile(engine, user_id)

        data = await _get_expense_timeline(client, headers)

        first = data["timeline"][0]
        assert first["delta_vs_previous"] in ("0", "0.00"), (
            f"Expected 0/0.00, got {first['delta_vs_previous']}"
        )

    await engine.dispose()


@pytest.mark.asyncio
async def test_expense_timeline_with_loans():
    """When a loan is configured, its termination should appear in key_events."""
    engine = create_async_engine(settings.database_url, echo=False)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        headers, email = await _register_and_get_headers(client)
        user_id = await _get_user_id(engine, email)
        await _seed_profile(engine, user_id)

        # Create a loan ending in 2 years
        today = date.today()
        end_date = date(today.year + 2, 12, 31)

        resp = await client.post(
            "/api/loans",
            json={
                "label": "Credit immobilier test",
                "loan_type": "mortgage",
                "monthly_payment": 500,
                "start_date": today.isoformat(),
                "end_date": end_date.isoformat(),
                "insurance_monthly": 15,
            },
            headers=headers,
        )
        assert resp.status_code in (201, 200), f"Loan create failed: {resp.text}"
        loan_id = resp.json().get("id")

        data = await _get_expense_timeline(client, headers)

        # Check that loan expenses appear
        loan_positive_years = [
            e for e in data["timeline"]
            if Decimal(e["loan_payments_monthly"]) > 0
        ]
        assert len(loan_positive_years) > 0, "No years with loan payments found"

        # Check key events for loan termination
        loan_events = [
            e for e in data["key_events"] if e["category"] == "loan_end"
        ]
        assert len(loan_events) > 0, (
            f"Expected loan_end event, got key_events: {data['key_events']}"
        )

        # Cleanup
        if loan_id:
            await client.delete(f"/api/loans/{loan_id}", headers=headers)

    await engine.dispose()


@pytest.mark.asyncio
async def test_scale_validation_rejects_bad_scale():
    """Invalid scale parameter should return 422."""
    engine = create_async_engine(settings.database_url, echo=False)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        headers, email = await _register_and_get_headers(client)
        user_id = await _get_user_id(engine, email)
        await _seed_profile(engine, user_id)

        resp = await client.get(
            "/api/projection/expense-timeline?scale=nonsense",
            headers=headers,
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"

    await engine.dispose()


@pytest.mark.asyncio
async def test_scale_pessimistic_differs_from_optimistic():
    """Pessimistic and optimistic scales should produce different totals."""
    engine = create_async_engine(settings.database_url, echo=False)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        headers, email = await _register_and_get_headers(client)
        user_id = await _get_user_id(engine, email)
        await _seed_profile(engine, user_id)

        data_pess = await _get_expense_timeline(client, headers, scale="pessimistic")
        data_opt = await _get_expense_timeline(client, headers, scale="optimistic")

        assert len(data_pess["timeline"]) > 0
        assert len(data_opt["timeline"]) > 0

        # Later years should differ due to different inflation rates
        total_pess = Decimal(data_pess["timeline"][-1]["total_monthly"])
        total_opt = Decimal(data_opt["timeline"][-1]["total_monthly"])
        assert total_pess != total_opt, (
            f"Expected different totals: pessim={total_pess}, optim={total_opt}"
        )

    await engine.dispose()


@pytest.mark.asyncio
async def test_expense_timeline_with_kids():
    """Kid cost events should generate independence key_events."""
    engine = create_async_engine(settings.database_url, echo=False)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        headers, email = await _register_and_get_headers(client)
        user_id = await _get_user_id(engine, email)
        await _seed_profile(engine, user_id)

        # Create a kid entity that will "leave home" within projection period
        today = date.today()
        kid_birth = date(today.year - 10, 1, 1)  # 10-year-old kid

        resp = await client.post(
            "/api/life-entities",
            json={
                "entity_type": "kid",
                "name": "Enfant Test",
                "reference_date": kid_birth.isoformat(),
                "cost_events": [
                    {
                        "label": "Cantine",
                        "from_age": 6,
                        "to_age": 18,
                        "amount": 150,
                        "frequency": "monthly",
                    },
                    {
                        "label": "Activites",
                        "from_age": 6,
                        "to_age": 18,
                        "amount": 100,
                        "frequency": "monthly",
                    },
                    {
                        "label": "Premiere voiture",
                        "from_age": 18,
                        "to_age": 18,
                        "amount": 5000,
                        "frequency": "once",
                    },
                ],
            },
            headers=headers,
        )
        assert resp.status_code in (201, 200), (
            f"Life entity create failed: {resp.text}"
        )
        entity_id = resp.json().get("id")

        data = await _get_expense_timeline(client, headers)

        # Check key events for kid independence
        kid_events = [
            e for e in data["key_events"] if e["category"] == "kid_independence"
        ]
        assert len(kid_events) > 0, (
            f"Expected kid_independence event, got: {data['key_events']}"
        )
        assert "Enfant Test" in kid_events[0]["event"]

        # Cleanup
        if entity_id:
            await client.delete(f"/api/life-entities/{entity_id}", headers=headers)

    await engine.dispose()


@pytest.mark.asyncio
async def test_expense_timeline_events_not_duplicated():
    """Key events should not contain duplicate entries."""
    engine = create_async_engine(settings.database_url, echo=False)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        headers, email = await _register_and_get_headers(client)
        user_id = await _get_user_id(engine, email)
        await _seed_profile(engine, user_id)

        data = await _get_expense_timeline(client, headers)

        # Check for duplicates by year + event combo
        seen = set()
        for event in data["key_events"]:
            key = (event["year"], event["event"])
            assert key not in seen, f"Duplicate event: {key}"
            seen.add(key)

    await engine.dispose()