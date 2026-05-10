"""
Sprint 6 — TASK-6.3 Loan & Mortgage Lifecycle tests.

Tests:
- Loan CRUD (create, list, get, update, soft-delete)
- End date resolution from remaining_months
- Loan summary with termination timeline
- Projection engine: loans NOT inflation-adjusted
- Projection engine: loans drop to zero after end_date
- Backwards compatibility: no loans → no loan_expenses
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app


@pytest.mark.asyncio
async def test_create_and_list_loans():
    """POST and GET /api/loans."""
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
                    "email": f"test.loans.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "Loan Test User",
                },
            )
            assert r.status_code == 201
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            # Create a mortgage
            res = await client.post(
                "/api/loans",
                json={
                    "label": "Crédit immobilier",
                    "loan_type": "mortgage",
                    "monthly_payment": 500,
                    "start_date": "2022-01-15",
                    "remaining_months": 144,
                    "insurance_monthly": 30,
                },
                cookies=cookies,
            )
            assert res.status_code == 201, f"Expected 201: {res.text}"
            data = res.json()
            assert data["label"] == "Crédit immobilier"
            assert data["loan_type"] == "mortgage"
            assert Decimal(data["monthly_payment"]) == Decimal("500")
            assert data["end_date"] is not None  # computed from remaining_months
            assert Decimal(data["insurance_monthly"]) == Decimal("30")

            # Create an auto loan with explicit end_date
            res2 = await client.post(
                "/api/loans",
                json={
                    "label": "Prêt auto",
                    "loan_type": "auto",
                    "monthly_payment": 90,
                    "start_date": "2024-06-01",
                    "end_date": "2028-06-01",
                },
                cookies=cookies,
            )
            assert res2.status_code == 201

            # List loans
            res3 = await client.get("/api/loans", cookies=cookies)
            assert res3.status_code == 200
            loans = res3.json()
            assert len(loans) == 2

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_loan_end_date_from_remaining_months():
    """End date should be computed correctly from remaining_months."""
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
                    "email": f"test.loans.end.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "End Date User",
                },
            )
            assert r.status_code == 201
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            # 120 months from 2022-03-01 → 2032-03-01
            res = await client.post(
                "/api/loans",
                json={
                    "label": "Test Loan",
                    "loan_type": "consumer",
                    "monthly_payment": 100,
                    "start_date": "2022-03-01",
                    "remaining_months": 120,
                },
                cookies=cookies,
            )
            assert res.status_code == 201
            data = res.json()
            assert "2032-03-01" in data["end_date"], (
                f"Expected end_date ~2032-03-01, got {data['end_date']}"
            )

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_loan_soft_delete_and_filters():
    """Soft-deleted loans should not appear in list or get."""
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
                    "email": f"test.loans.del.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "Delete User",
                },
            )
            assert r.status_code == 201
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            res = await client.post(
                "/api/loans",
                json={
                    "label": "To Delete",
                    "loan_type": "other",
                    "monthly_payment": 50,
                    "start_date": "2025-01-01",
                },
                cookies=cookies,
            )
            loan_id = res.json()["id"]

            # Soft delete
            res2 = await client.delete(f"/api/loans/{loan_id}", cookies=cookies)
            assert res2.status_code == 204

            # Should not appear in list
            res3 = await client.get("/api/loans", cookies=cookies)
            loans = res3.json()
            assert len(loans) == 0

            # Should 404 on GET
            res4 = await client.get(f"/api/loans/{loan_id}", cookies=cookies)
            assert res4.status_code == 404

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_loan_summary_timeline():
    """Summary endpoint should return a timeline of loan terminations."""
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
                    "email": f"test.loans.sum.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "Summary User",
                },
            )
            assert r.status_code == 201
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            # Mortgage that ends in 3 years
            await client.post(
                "/api/loans",
                json={
                    "label": "Crédit immo",
                    "loan_type": "mortgage",
                    "monthly_payment": 500,
                    "start_date": "2022-01-01",
                    "end_date": f"{date.today().year + 3}-12-31",
                },
                cookies=cookies,
            )

            res = await client.get("/api/loans/summary", cookies=cookies)
            assert res.status_code == 200
            summary = res.json()
            assert Decimal(summary["total_monthly"]) == Decimal("500")
            assert len(summary["loans"]) == 1

            # Timeline should show decreasing total
            timeline = summary["timeline"]
            assert len(timeline) >= 1
            current_year_entries = [t for t in timeline if t["year"] == date.today().year]
            assert len(current_year_entries) > 0, f"Timeline should include current year: {timeline}"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


def test_loan_expenses_in_projection_engine():
    """Loans in the projection engine should be fixed nominal and terminate on end_date."""
    from app.calculations.projection import ProjectionInput, project_timeline

    inp = ProjectionInput(
        current_age=40,
        target_age=70,
        current_year=2026,
        post_retirement_years=0,
        monthly_gross=Decimal("5000"),
        monthly_expenses_total=Decimal("3000"),
        scale="moderate",
        loans=[
            {
                "label": "Crédit immo",
                "monthly_payment": Decimal("500"),
                "start_date": date(2022, 1, 1),
                "end_date": date(2035, 12, 31),
                "insurance_monthly": Decimal("30"),
            },
        ],
    )

    timeline = project_timeline(inp)

    # Year 1 (2026): loan should be active
    y2026 = timeline[1]
    assert y2026.loan_expenses > 0, "Loan should be active in 2026"

    # Year 10 (2036): loan should have ended
    y2036 = timeline[10]
    assert y2036.loan_expenses == 0, f"Loan should end in 2036, got {y2036.loan_expenses}"


def test_loan_not_inflation_adjusted():
    """Loan payments should stay the same nominal amount year over year."""
    from app.calculations.projection import ProjectionInput, project_timeline

    inp = ProjectionInput(
        current_age=40,
        target_age=70,
        current_year=2026,
        post_retirement_years=0,
        monthly_gross=Decimal("5000"),
        monthly_expenses_total=Decimal("3000"),
        scale="moderate",  # 3% inflation
        loans=[
            {
                "label": "Loan",
                "monthly_payment": Decimal("500"),
                "start_date": date(2026, 1, 1),
                "end_date": date(2040, 12, 31),
            },
        ],
    )

    timeline = project_timeline(inp)

    # Year 1 and year 5 should have same loan expense (fixed nominal)
    y1 = timeline[0]  # 2026
    y5 = timeline[4]  # 2030

    assert y1.loan_expenses == y5.loan_expenses, (
        f"Loan NOT inflation-adjusted: year1={y1.loan_expenses}, year5={y5.loan_expenses}"
    )


def test_no_loans_backwards_compatible():
    """No loans in input → loan_expenses is zero."""
    from app.calculations.projection import ProjectionInput, project_timeline

    inp = ProjectionInput(
        current_age=40,
        target_age=70,
        current_year=2026,
        post_retirement_years=0,
        monthly_gross=Decimal("5000"),
        monthly_expenses_total=Decimal("3000"),
        scale="moderate",
        loans=[],
    )

    timeline = project_timeline(inp)
    for entry in timeline:
        assert entry.loan_expenses == 0, "No loans should mean zero loan expenses"


def test_multiple_loans_aggregated():
    """Multiple loans should have their expenses summed."""
    from app.calculations.projection import ProjectionInput, project_timeline

    inp = ProjectionInput(
        current_age=40,
        target_age=70,
        current_year=2026,
        post_retirement_years=0,
        monthly_gross=Decimal("5000"),
        monthly_expenses_total=Decimal("3000"),
        scale="moderate",
        loans=[
            {
                "label": "Mortgage",
                "monthly_payment": Decimal("500"),
                "start_date": date(2022, 1, 1),
                "end_date": date(2035, 12, 31),
            },
            {
                "label": "Prêt auto",
                "monthly_payment": Decimal("90"),
                "start_date": date(2024, 6, 1),
                "end_date": date(2028, 6, 1),
            },
        ],
    )

    timeline = project_timeline(inp)

    # 2026: both active → 590€ × 12 = 7080
    y2026 = timeline[0]
    expected = (Decimal("500") + Decimal("90")) * Decimal("12")
    assert y2026.loan_expenses == expected, (
        f"Expected {expected}, got {y2026.loan_expenses}"
    )

    # 2029: auto ended, only mortgage → 500€ × 12 = 6000
    y2029 = timeline[3]
    expected_2029 = Decimal("500") * Decimal("12")
    assert y2029.loan_expenses == expected_2029, (
        f"Expected {expected_2029}, got {y2029.loan_expenses}"
    )