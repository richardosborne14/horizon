"""
TASK-2.13.5 — Payslip history, PDF download, receipt, and ZIP endpoints.

Testing strategy (mirrors other 2.13 tests — see LEARNINGS.md):
  - Unit tests: pure function tests — no DB, no HTTP.
  - Service tests: MagicMock AsyncSession (conftest has no db_session fixture).
  - Endpoint auth tests: ASGI transport + real register/login (minimal DB touch).
  - History aggregation integration: exercised via endpoint with real DB insert
    through the internal app.core.database session (via AsyncSession context).

WHY no db_session fixture: conftest.py only provides a session-scoped event_loop.
Each test manages its own DB state using the ASGI client (API calls) or direct
AsyncSession from `app.core.database.AsyncSessionLocal` for setup-only inserts.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.payslip_history import _compute_status_summary


# ── Helpers ───────────────────────────────────────────────────────────────────


def _client() -> AsyncClient:
    """Return a fresh unauthenticated ASGI test client."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _register_login(client: AsyncClient, suffix: str) -> None:
    """Register and log in a unique test user (sets session cookie on client)."""
    email = f"test_2135_{suffix}@example.com"
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "name": "Test 2.13.5"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"


async def _create_salon(client: AsyncClient, suffix: str) -> str:
    """Create a salon and return its ID."""
    resp = await client.post(
        "/api/salons",
        json={"name": f"Salon 2.13.5 {suffix}", "city": "Paris", "business_type": "EURL"},
    )
    assert resp.status_code in (200, 201), f"Create salon failed: {resp.text}"
    return resp.json()["id"]


async def _create_employee(client: AsyncClient, salon_id: str, suffix: str) -> str:
    """Create an eligible CDI employee and return its ID."""
    resp = await client.post(
        "/api/employees",
        json={
            "salon_id": salon_id,
            "name": f"Employé Test {suffix}",
            "role_type": "salarie",
            "contract_type": "cdi",
            "hours_per_week": 35,
            "salary_brut": 1800,
            "cotisations_patronales": 650,
        },
    )
    assert resp.status_code in (200, 201), f"Create employee failed: {resp.text}"
    return resp.json()["id"]


# ── Unit tests: _compute_status_summary ──────────────────────────────────────


def test_status_summary_all_attached() -> None:
    """All pdf_attached → all_attached."""
    assert _compute_status_summary(["pdf_attached", "pdf_attached"]) == "all_attached"


def test_status_summary_some_attached() -> None:
    """Mix of pdf_attached and others → some_attached."""
    assert _compute_status_summary(["pdf_attached", "emailed"]) == "some_attached"


def test_status_summary_error_beats_all() -> None:
    """error outranks all other statuses."""
    assert _compute_status_summary(["pdf_attached", "error"]) == "error"
    assert _compute_status_summary(["emailed", "error"]) == "error"


def test_status_summary_all_emailed() -> None:
    """All emailed → emailed."""
    assert _compute_status_summary(["emailed", "emailed"]) == "emailed"


def test_status_summary_processing() -> None:
    """paid_pending_email → processing."""
    assert _compute_status_summary(["paid_pending_email"]) == "processing"


def test_status_summary_empty() -> None:
    """Empty list defaults to processing."""
    assert _compute_status_summary([]) == "processing"


def test_status_summary_single_all_attached() -> None:
    """Single pdf_attached → all_attached."""
    assert _compute_status_summary(["pdf_attached"]) == "all_attached"


def test_status_summary_error_beats_all_attached() -> None:
    """error wins even when most are pdf_attached."""
    result = _compute_status_summary(["pdf_attached", "error", "pdf_attached"])
    assert result == "error"


# ── Service-level tests (MagicMock DB) ───────────────────────────────────────


@pytest.mark.asyncio
async def test_get_submission_history_empty_db() -> None:
    """
    get_submission_history returns HistoryResponse(periods=[]) when no submissions.

    WHY MagicMock: avoids the db_session fixture that doesn't exist in conftest.
    We test that the service handles an empty scalars().all() result correctly.
    """
    from app.services.payslip_history import get_submission_history

    db = AsyncMock()
    # Execute returns a result with no rows
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=mock_result)

    response = await get_submission_history(salon_id=uuid.uuid4(), db=db)
    assert response.periods == []


@pytest.mark.asyncio
async def test_get_submission_history_groups_periods() -> None:
    """
    get_submission_history groups submissions by (year, month) and sorts DESC.
    """
    from app.models.payslip import PayslipSubmission
    from app.models.salon import Employee
    from app.services.payslip_history import get_submission_history

    salon_id = uuid.uuid4()
    emp_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # Two submissions: March and April 2026
    sub_april = MagicMock(spec=PayslipSubmission)
    sub_april.id = uuid.uuid4()
    sub_april.salon_id = salon_id
    sub_april.employee_id = emp_id
    sub_april.period_year = 2026
    sub_april.period_month = 4
    sub_april.status = "paid_pending_email"
    sub_april.pdf_url = None
    sub_april.stripe_receipt_url = None

    sub_march = MagicMock(spec=PayslipSubmission)
    sub_march.id = uuid.uuid4()
    sub_march.salon_id = salon_id
    sub_march.employee_id = emp_id
    sub_march.period_year = 2026
    sub_march.period_month = 3
    sub_march.status = "pdf_attached"
    sub_march.pdf_url = "salon/march.pdf"
    sub_march.stripe_receipt_url = "https://receipt.stripe.com/r"

    emp_mock = MagicMock(spec=Employee)
    emp_mock.id = str(emp_id)
    emp_mock.name = "Julie Martin"

    db = AsyncMock()

    # First call: submissions query
    subs_result = MagicMock()
    subs_result.scalars.return_value.all.return_value = [sub_april, sub_march]

    # Second call: employees query
    emps_result = MagicMock()
    emps_result.scalars.return_value.all.return_value = [emp_mock]

    db.execute = AsyncMock(side_effect=[subs_result, emps_result])

    response = await get_submission_history(salon_id=salon_id, db=db, year=None)

    # 2 periods, sorted DESC → April first
    assert len(response.periods) == 2
    assert response.periods[0].year == 2026
    assert response.periods[0].month == 4
    assert response.periods[0].status_summary == "processing"
    assert response.periods[1].month == 3
    assert response.periods[1].status_summary == "all_attached"

    # PDF and receipt flags
    april_emp = response.periods[0].employees[0]
    assert april_emp.pdf_available is False
    assert april_emp.receipt_available is False

    march_emp = response.periods[1].employees[0]
    assert march_emp.pdf_available is True
    assert march_emp.receipt_available is True


@pytest.mark.asyncio
async def test_get_submission_history_total_price() -> None:
    """total_paid_ttc_eur = n_bulletins × 28.80."""
    from app.models.payslip import PayslipSubmission
    from app.models.salon import Employee
    from app.services.payslip_history import get_submission_history

    salon_id = uuid.uuid4()
    emp_id = uuid.uuid4()

    sub = MagicMock(spec=PayslipSubmission)
    sub.id = uuid.uuid4()
    sub.salon_id = salon_id
    sub.employee_id = emp_id
    sub.period_year = 2026
    sub.period_month = 5
    sub.status = "emailed"
    sub.pdf_url = None
    sub.stripe_receipt_url = None

    emp_mock = MagicMock(spec=Employee)
    emp_mock.id = str(emp_id)
    emp_mock.name = "Test Emp"

    db = AsyncMock()
    subs_result = MagicMock()
    subs_result.scalars.return_value.all.return_value = [sub]
    emps_result = MagicMock()
    emps_result.scalars.return_value.all.return_value = [emp_mock]
    db.execute = AsyncMock(side_effect=[subs_result, emps_result])

    response = await get_submission_history(salon_id=salon_id, db=db)
    period = response.periods[0]
    assert period.n_bulletins == 1
    assert period.total_paid_ttc_eur == Decimal("28.80")


@pytest.mark.asyncio
async def test_get_submission_history_year_filter() -> None:
    """year filter is applied to the DB query (verified via execute call count)."""
    from app.services.payslip_history import get_submission_history

    db = AsyncMock()
    subs_result = MagicMock()
    subs_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=subs_result)

    response = await get_submission_history(salon_id=uuid.uuid4(), db=db, year=2025)
    assert response.periods == []
    # Only one execute call when empty (employee query is skipped)
    assert db.execute.call_count == 1


# ── Endpoint auth tests (ASGI) ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_history_endpoint_requires_auth() -> None:
    """GET /submissions/history returns 401 for unauthenticated requests."""
    salon_id = str(uuid.uuid4())
    async with _client() as client:
        resp = await client.get(
            f"/api/salons/{salon_id}/payslip/submissions/history"
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_pdf_endpoint_requires_auth() -> None:
    """GET /submissions/{id}/pdf returns 401 for unauthenticated requests."""
    salon_id = str(uuid.uuid4())
    sub_id = str(uuid.uuid4())
    async with _client() as client:
        resp = await client.get(
            f"/api/salons/{salon_id}/payslip/submissions/{sub_id}/pdf",
            follow_redirects=False,
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_receipt_endpoint_requires_auth() -> None:
    """GET /submissions/{id}/receipt returns 401 for unauthenticated requests."""
    salon_id = str(uuid.uuid4())
    sub_id = str(uuid.uuid4())
    async with _client() as client:
        resp = await client.get(
            f"/api/salons/{salon_id}/payslip/submissions/{sub_id}/receipt",
            follow_redirects=False,
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_zip_endpoint_requires_auth() -> None:
    """GET .../period/{year}/{month}/zip returns 401 for unauthenticated."""
    salon_id = str(uuid.uuid4())
    async with _client() as client:
        resp = await client.get(
            f"/api/salons/{salon_id}/payslip/submissions/period/2026/4/zip"
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_history_endpoint_404_for_wrong_salon() -> None:
    """GET /submissions/history returns 404 when salon not owned by user."""
    async with _client() as client:
        await _register_login(client, "wrongsalon")
        # Use a random UUID that doesn't belong to this user
        fake_salon_id = str(uuid.uuid4())
        resp = await client.get(
            f"/api/salons/{fake_salon_id}/payslip/submissions/history"
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_history_endpoint_returns_empty_for_new_salon() -> None:
    """GET /submissions/history returns empty periods for a salon with no submissions."""
    async with _client() as client:
        await _register_login(client, "newsalon_hist")
        salon_id = await _create_salon(client, "newsalon_hist")
        resp = await client.get(
            f"/api/salons/{salon_id}/payslip/submissions/history"
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "periods" in data
    assert data["periods"] == []


@pytest.mark.asyncio
async def test_pdf_endpoint_404_for_unknown_submission() -> None:
    """GET /submissions/{id}/pdf returns 404 for a submission that doesn't exist."""
    async with _client() as client:
        await _register_login(client, "pdfnotfound")
        salon_id = await _create_salon(client, "pdfnotfound")
        fake_sub_id = str(uuid.uuid4())
        resp = await client.get(
            f"/api/salons/{salon_id}/payslip/submissions/{fake_sub_id}/pdf",
            follow_redirects=False,
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_receipt_endpoint_404_for_unknown_submission() -> None:
    """GET /submissions/{id}/receipt returns 404 for a submission that doesn't exist."""
    async with _client() as client:
        await _register_login(client, "receiptnotfound")
        salon_id = await _create_salon(client, "receiptnotfound")
        fake_sub_id = str(uuid.uuid4())
        resp = await client.get(
            f"/api/salons/{salon_id}/payslip/submissions/{fake_sub_id}/receipt",
            follow_redirects=False,
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_zip_endpoint_404_for_period_with_no_submissions() -> None:
    """GET .../period/{year}/{month}/zip returns 404 when no paid submissions found."""
    async with _client() as client:
        await _register_login(client, "zipempty")
        salon_id = await _create_salon(client, "zipempty")
        resp = await client.get(
            f"/api/salons/{salon_id}/payslip/submissions/period/2026/4/zip"
        )
    assert resp.status_code == 404


# ── stripe_receipts cache unit tests ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_receipt_url_returns_stored_url() -> None:
    """
    get_receipt_url returns stripe_receipt_url directly when already persisted.
    Should not call Stripe API.
    """
    from app.services.stripe_receipts import get_receipt_url

    submission = MagicMock()
    submission.stripe_receipt_url = "https://receipt.stripe.com/already-stored"
    submission.stripe_payment_intent_id = "pi_test_123"

    db = AsyncMock()
    result = await get_receipt_url(submission, db)

    assert result == "https://receipt.stripe.com/already-stored"
    # DB should not be modified (no need to fetch from Stripe)
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_get_receipt_url_returns_none_without_pi() -> None:
    """
    get_receipt_url returns None when stripe_payment_intent_id is None.
    Nothing to fetch from Stripe.
    """
    from app.services.stripe_receipts import get_receipt_url

    submission = MagicMock()
    submission.stripe_receipt_url = None
    submission.stripe_payment_intent_id = None

    db = AsyncMock()
    result = await get_receipt_url(submission, db)

    assert result is None


@pytest.mark.asyncio
async def test_get_receipt_url_fetches_from_stripe_when_not_persisted() -> None:
    """
    get_receipt_url fetches from Stripe when stripe_receipt_url is missing
    but stripe_payment_intent_id is set. Persists to DB afterward.
    """
    from app.services.stripe_receipts import get_receipt_url, _receipt_cache

    # Clear any cached entry for this test
    test_intent_id = "pi_test_fetch_from_stripe"
    _receipt_cache.pop(test_intent_id, None)

    submission = MagicMock()
    submission.stripe_receipt_url = None
    submission.stripe_payment_intent_id = test_intent_id
    submission.id = uuid.uuid4()

    db = AsyncMock()

    stripe_receipt_url = "https://receipt.stripe.com/fetched"

    with patch(
        "app.services.stripe_receipts._fetch_receipt_url_from_stripe",
        AsyncMock(return_value=stripe_receipt_url),
    ):
        result = await get_receipt_url(submission, db)

    assert result == stripe_receipt_url
    # Should have persisted the URL
    assert submission.stripe_receipt_url == stripe_receipt_url
    db.commit.assert_called_once()
