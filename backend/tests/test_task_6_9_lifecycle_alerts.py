"""
Sprint 6 — TASK-6.9 Lifecycle Alerts tests.

Tests:
- Alerts generated for loans, kids, pets, retirement countdown
- Alerts endpoint returns valid structure
- Auth required
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app
from app.calculations.insights import generate_lifecycle_alerts, LifecycleAlert
from app.calculations.projection import ProjectionInput, project_timeline


# ── Unit tests ──────────────────────────────────────────────────────────────


def _minimal_input(**overrides) -> ProjectionInput:
    kwargs = dict(
        current_age=40,
        target_age=65,
        current_year=2026,
        monthly_gross=Decimal("5000"),
        growth_rate=Decimal("0.04"),
        ae_activity_type="bnc_non_reglementee",
        monthly_expenses_total=Decimal("3000"),
        scale="moderate",
        life_entities=[],
        recurring_expenses=[],
        allocations={
            "livret_a": {"balance": Decimal("5000"), "monthly": Decimal("500")},
        },
        projects=[],
        kids_birth_dates=[],
        loans=[],
    )
    kwargs.update(overrides)
    return ProjectionInput(**kwargs)


def test_loan_termination_alert():
    """A loan with an end_date within the projection generates a termination alert."""
    inp = _minimal_input(
        loans=[
            {
                "label": "Crédit immo",
                "monthly_payment": 500,
                "start_date": "2020-01-01",
                "end_date": "2035-01-01",
                "insurance_monthly": 0,
            }
        ]
    )
    timeline = project_timeline(inp)
    alerts = generate_lifecycle_alerts(
        timeline=timeline,
        summary={},
        loans=inp.loans,
        life_entities=inp.life_entities,
        allocations=[{"vehicle_key": "livret_a", "balance": 5000, "monthly": 500}],
        profile_data={"monthly_gross": 5000, "growth_rate": 0.04, "target_age": 65, "current_age": 40},
    )

    loan_alerts = [a for a in alerts if a.alert_type == "loan_end"]
    assert len(loan_alerts) >= 1
    assert loan_alerts[0].year == 2036  # end_year + 1
    assert loan_alerts[0].severity == "action"
    assert "Crédit immo" in loan_alerts[0].title


def test_loan_no_end_date_no_alert():
    """A loan without an end_date generates no termination alert."""
    inp = _minimal_input(
        loans=[
            {
                "label": "Prêt permanent",
                "monthly_payment": 100,
                "start_date": "2020-01-01",
                "end_date": None,
                "insurance_monthly": 0,
            }
        ]
    )
    timeline = project_timeline(inp)
    alerts = generate_lifecycle_alerts(
        timeline=timeline,
        summary={},
        loans=inp.loans,
        life_entities=inp.life_entities,
        allocations=[],
        profile_data={"monthly_gross": 5000, "growth_rate": 0.04, "target_age": 65, "current_age": 40},
    )

    loan_alerts = [a for a in alerts if a.alert_type == "loan_end"]
    assert len(loan_alerts) == 0


def test_kid_independence_alert():
    """A kid entity generates independence alerts."""
    today = date.today()
    birth = date(today.year - 10, 6, 1)  # 10 year old kid
    inp = _minimal_input(
        life_entities=[
            {
                "entity_type": "kid",
                "entity_name": "Saoirse",
                "entity_age_at_start": 10,
                "cost_events": [
                    {"label": "Cantine", "from_age": 10, "to_age": 22, "amount": 150, "frequency": "monthly", "is_active": True},
                ],
            }
        ]
    )
    timeline = project_timeline(inp)
    alerts = generate_lifecycle_alerts(
        timeline=timeline,
        summary={},
        loans=[],
        life_entities=inp.life_entities,
        allocations=[],
        profile_data={"monthly_gross": 5000, "growth_rate": 0.04, "target_age": 65, "current_age": 40},
    )

    kid_alerts = [a for a in alerts if a.alert_type == "kid_independence"]
    assert len(kid_alerts) >= 1
    assert "Saoirse" in kid_alerts[0].title


def test_retirement_countdown_alerts():
    """Retirement countdown generates alerts at 10, 5, 3, 1 years."""
    inp = _minimal_input(current_age=55, target_age=65)
    timeline = project_timeline(inp)
    alerts = generate_lifecycle_alerts(
        timeline=timeline,
        summary={},
        loans=[],
        life_entities=[],
        allocations=[],
        profile_data={"monthly_gross": 5000, "growth_rate": 0.04, "target_age": 65, "current_age": 55},
    )

    countdown_alerts = [a for a in alerts if a.alert_type == "retirement_countdown"]
    assert len(countdown_alerts) >= 1  # at least 1y and 3y should fire
    years = [a.year for a in countdown_alerts]
    assert 2035 in years or 2036 in years  # 10 years from now


def test_empty_input_no_alerts():
    """Empty inputs produce only expense_peak and retirement_countdown (base alerts)."""
    timeline = project_timeline(_minimal_input())
    alerts = generate_lifecycle_alerts(
        timeline=timeline, summary={}, loans=[], life_entities=[],
        allocations=[], profile_data={"monthly_gross": 5000, "growth_rate": 0.04, "target_age": 65, "current_age": 40}
    )
    # No loan, no kid, no pet, no car — only expense_peak and retirement countdown
    alert_types = {a.alert_type for a in alerts}
    assert "expense_peak" in alert_types or "retirement_countdown" in alert_types
    # Should not have entity-specific alerts
    assert "loan_end" not in alert_types
    assert "kid_independence" not in alert_types
    assert "pet_eol" not in alert_types
    assert "car_replacement" not in alert_types


# ── API integration tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_alerts_endpoint_requires_auth():
    """GET /api/projection/alerts returns 401/403 without auth."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/api/projection/alerts")
        assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_alerts_endpoint_smoke():
    """GET /api/projection/alerts returns valid alerts for a configured user."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": f"test.alerts.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "Alerts Test",
                },
            )
            assert r.status_code == 201
            uid = r.json()["user"]["id"]
            user_ids.append(uuid.UUID(uid))
            cookies = r.cookies

            await client.put(
                "/api/profile",
                json={
                    "birth_date": "1986-06-15",
                    "monthly_gross_ca": 5000,
                    "target_retirement_age": 65,
                    "ae_activity_type": "bnc_non_reglementee",
                    "monthly_expenses": {"loyer": 800, "alimentation": 500},
                    "growth_preset": "moderate",
                },
                cookies=cookies,
            )

            # Add a loan with an end date
            await client.post(
                "/api/loans",
                json={
                    "label": "Crédit test",
                    "loan_type": "mortgage",
                    "monthly_payment": 500,
                    "start_date": "2020-01-01",
                    "remaining_months": 120,
                },
                cookies=cookies,
            )

            # Add a kid
            await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "kid",
                    "name": "Enfant Test",
                    "reference_date": "2016-06-01",
                    "cost_events": [
                        {"label": "Cantine", "from_age": 10, "to_age": 22, "amount": 150, "frequency": "monthly", "is_active": True}
                    ],
                },
                cookies=cookies,
            )

            r = await client.get(
                "/api/projection/alerts?scale=moderate",
                cookies=cookies,
            )
            assert r.status_code == 200, f"Alerts failed: {r.text}"

            data = r.json()
            assert "alerts" in data
            assert "total" in data
            assert isinstance(data["alerts"], list)

            for alert in data["alerts"]:
                assert "id" in alert
                assert "alert_type" in alert
                assert "year" in alert
                assert "severity" in alert
                assert "title" in alert
                assert "description" in alert

    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()