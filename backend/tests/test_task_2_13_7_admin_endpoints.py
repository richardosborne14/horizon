"""
Tests for TASK-2.13.7 — Admin oversight endpoints.

Coverage:
  - Auth blocking: non-admin → 403 on every endpoint
  - GET /admin/payslip/submissions — pagination + filter
  - GET /admin/payslip/contrats — filter by status
  - GET /admin/payslip/metrics — response shape + values
  - POST /admin/payslip/submissions/{id}/upload-pdf — success + audit log
  - POST /admin/payslip/contrats/{id}/upload-pdf — success + audit log
  - POST /admin/payslip/submissions/{id}/retry-email — 422 when not error
  - POST /admin/payslip/submissions/{id}/retry-email — 500 when SMTP unavail
  - PATCH /admin/payslip/dossiers/{id}/status — audit log written
  - 404 on upload-pdf for unknown submission/contrat

Auth pattern: cookie-based sessions (not Bearer tokens).
The HTTPX AsyncClient's cookie jar automatically carries the session cookie
set by POST /api/auth/login across subsequent requests in the same context.
Making a user admin via direct DB update takes effect immediately for the
next request (is_admin is read from the DB on every request).

All DB-direct row creation uses AsyncSessionLocal() — these can nest within
the same `async with _client()` context since they use a separate connection.
"""

from __future__ import annotations

import io
import uuid
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.user import User


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _make_admin(email: str) -> None:
    """
    Set role='admin' for a user identified by email.

    get_admin_user checks `user.role == 'admin'`, not a separate is_admin flag.
    Change takes effect immediately for subsequent API requests because
    get_current_user reads role from the DB on every request.

    Args:
        email: Email address of the user to promote to admin role.
    """
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(User).where(User.email == email).values(role="admin")
        )
        await db.commit()


def _client() -> AsyncClient:
    """
    Return an ASGI test client with cookie support.

    The client's cookie jar persists the session cookie set by
    POST /api/auth/login across all subsequent requests in the same context.
    """
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _fake_pdf() -> bytes:
    """
    Minimal valid PDF bytes for upload tests.

    Stub mode (no S3 creds in CI) skips the actual upload, so the content
    only needs to pass the filename check.
    """
    return (
        b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\nxref\n0 1\n"
        b"0000000000 65535 f\ntrailer<<>>\nstartxref\n9\n%%EOF"
    )


async def _register_login(
    client: AsyncClient,
    email: str,
    password: str = "Password123!",
    name: str = "Test User",
) -> None:
    """
    Register a new user and login (sets session cookie on the client).

    Args:
        client:   ASGI test client (cookie jar updated in place).
        email:    Unique test email.
        password: Password (default passes the validator).
        name:     Display name.
    """
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "name": name},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, f"login failed: {resp.text}"


async def _create_salon(client: AsyncClient) -> dict[str, Any]:
    """
    POST /api/salons and return the response dict.

    Args:
        client: Logged-in ASGI test client.

    Returns:
        Salon JSON dict.
    """
    resp = await client.post(
        "/api/salons",
        json={
            "name": f"Salon {uuid.uuid4().hex[:6]}",
            "business_type": "sarl",
            "fiscal_year_start": 1,
        },
    )
    assert resp.status_code in (200, 201), f"create salon: {resp.text}"
    return resp.json()


async def _create_employee(client: AsyncClient, salon_id: str) -> dict[str, Any]:
    """
    POST an employee and return the response dict.

    Args:
        client:    Logged-in ASGI test client.
        salon_id:  UUID string of the target salon.

    Returns:
        Employee JSON dict.
    """
    resp = await client.post(
        f"/api/salons/{salon_id}/employees",
        json={
            "name": f"Emp {uuid.uuid4().hex[:4]}",
            "contract_type": "cdi",
            "role_type": "salarie",
            "salary_brut": "2200.00",
            "taux_occupation": 1.0,
            "hours_per_week": 35,
        },
    )
    assert resp.status_code in (200, 201), f"create employee: {resp.text}"
    return resp.json()


async def _insert_dossier(salon_id: str) -> None:
    """
    Insert a PayslipDossier directly into the DB (status='paid').

    Args:
        salon_id: UUID string of the salon.
    """
    from datetime import UTC, datetime
    from app.models.payslip import PayslipDossier

    async with AsyncSessionLocal() as db:
        dossier = PayslipDossier(
            salon_id=uuid.UUID(salon_id),
            status="paid",
            paid_at=datetime.now(UTC),
            stripe_payment_intent_id=f"pi_test_{uuid.uuid4().hex[:8]}",
        )
        db.add(dossier)
        await db.commit()


async def _insert_submission(
    salon_id: str,
    employee_id: str,
    status: str = "error",
    period_month: int = 4,
    period_year: int = 2026,
) -> str:
    """
    Insert a PayslipSubmission directly into the DB.

    Note: there is a unique constraint on (salon_id, employee_id, period_month, period_year).
    Use distinct period_month values when inserting multiple rows for the same employee.

    Args:
        salon_id:      Salon UUID string.
        employee_id:   Employee UUID string.
        status:        Initial status (default 'error').
        period_month:  Payroll month (1–12, default 4). Vary to avoid unique constraint.
        period_year:   Payroll year (default 2026).

    Returns:
        UUID string of the created submission.
    """
    from app.models.payslip import PayslipSubmission

    sub_id = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        sub = PayslipSubmission(
            id=sub_id,
            salon_id=uuid.UUID(salon_id),
            employee_id=uuid.UUID(employee_id),
            period_month=period_month,
            period_year=period_year,
            status=status,
            stripe_payment_intent_id=f"pi_test_{uuid.uuid4().hex[:8]}",
            subject_token=uuid.uuid4().hex[:8],
        )
        db.add(sub)
        await db.commit()
    return str(sub_id)


async def _insert_contrat(salon_id: str, requester_user_id: str) -> str:
    """
    Insert a ContratRequest directly into the DB.

    Args:
        salon_id:           Salon UUID string.
        requester_user_id:  Requesting user UUID string.

    Returns:
        UUID string of the created contrat.
    """
    from app.models.payslip import ContratRequest

    contrat_id = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        contrat = ContratRequest(
            id=contrat_id,
            salon_id=uuid.UUID(salon_id),
            requester_user_id=uuid.UUID(requester_user_id),
            employee_data={"nom": "Dupont", "prenom": "Marie"},
            status="emailed",
            stripe_payment_intent_id=f"pi_test_{uuid.uuid4().hex[:8]}",
        )
        db.add(contrat)
        await db.commit()
    return str(contrat_id)


async def _get_user_id(email: str) -> str:
    """
    Return the UUID string of a user by email.

    Args:
        email: User email.

    Returns:
        UUID string.
    """
    from sqlalchemy import select
    from app.models.user import User as UserModel

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(UserModel).where(UserModel.email == email))
        user = result.scalar_one()
        return str(user.id)


# ── Auth blocking ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_submissions_requires_admin() -> None:
    """Non-admin user gets 403 on GET /admin/payslip/submissions."""
    email = f"nonadmin_{uuid.uuid4().hex[:6]}@example.com"
    async with _client() as client:
        await _register_login(client, email)
        resp = await client.get("/api/admin/payslip/submissions")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_contrats_requires_admin() -> None:
    """Non-admin user gets 403 on GET /admin/payslip/contrats."""
    email = f"nonadmin_{uuid.uuid4().hex[:6]}@example.com"
    async with _client() as client:
        await _register_login(client, email)
        resp = await client.get("/api/admin/payslip/contrats")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_metrics_requires_admin() -> None:
    """Non-admin user gets 403 on GET /admin/payslip/metrics."""
    email = f"nonadmin_{uuid.uuid4().hex[:6]}@example.com"
    async with _client() as client:
        await _register_login(client, email)
        resp = await client.get("/api/admin/payslip/metrics")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_upload_pdf_requires_admin() -> None:
    """Non-admin gets 403 on POST /admin/payslip/submissions/{id}/upload-pdf."""
    email = f"nonadmin_{uuid.uuid4().hex[:6]}@example.com"
    fake_id = str(uuid.uuid4())
    async with _client() as client:
        await _register_login(client, email)
        resp = await client.post(
            f"/api/admin/payslip/submissions/{fake_id}/upload-pdf",
            files={"file": ("test.pdf", io.BytesIO(_fake_pdf()), "application/pdf")},
        )
    assert resp.status_code == 403


# ── Submissions list ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_submissions_list_shape() -> None:
    """Admin can call submissions list and get pagination metadata."""
    email = f"admin_{uuid.uuid4().hex[:6]}@example.com"
    async with _client() as client:
        await _register_login(client, email)
        await _make_admin(email)

        resp = await client.get(
            "/api/admin/payslip/submissions",
            params={"limit": 10, "offset": 0},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "has_more" in data
    assert isinstance(data["total"], int)
    assert isinstance(data["has_more"], bool)


@pytest.mark.asyncio
async def test_admin_submissions_list_filter_by_status() -> None:
    """Submissions list: filtering by status returns only matching rows."""
    email = f"admin_{uuid.uuid4().hex[:6]}@example.com"
    async with _client() as client:
        await _register_login(client, email)
        await _make_admin(email)
        salon = await _create_salon(client)
        salon_id = salon["id"]
        emp = await _create_employee(client, salon_id)
        emp_id = emp["id"]

        # Insert two submissions with different statuses (different months — unique constraint)
        await _insert_submission(salon_id, emp_id, status="error", period_month=4)
        await _insert_submission(salon_id, emp_id, status="pdf_attached", period_month=5)

        resp = await client.get(
            "/api/admin/payslip/submissions",
            params={"status": "error", "salon_id": salon_id},
        )
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["status"] == "error"


@pytest.mark.asyncio
async def test_admin_submissions_list_pagination() -> None:
    """limit=1 returns exactly 1 item and has_more=True when total > 1."""
    email = f"admin_{uuid.uuid4().hex[:6]}@example.com"
    async with _client() as client:
        await _register_login(client, email)
        await _make_admin(email)
        salon = await _create_salon(client)
        salon_id = salon["id"]
        emp = await _create_employee(client, salon_id)
        emp_id = emp["id"]

        for month in (4, 5, 6):
            await _insert_submission(salon_id, emp_id, status="emailed", period_month=month)

        resp = await client.get(
            "/api/admin/payslip/submissions",
            params={"salon_id": salon_id, "limit": 1, "offset": 0},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["total"] >= 3
    assert data["has_more"] is True


@pytest.mark.asyncio
async def test_admin_submissions_item_has_days_since_paid() -> None:
    """Submissions items include days_since_paid as a non-negative integer."""
    email = f"admin_{uuid.uuid4().hex[:6]}@example.com"
    async with _client() as client:
        await _register_login(client, email)
        await _make_admin(email)
        salon = await _create_salon(client)
        salon_id = salon["id"]
        emp = await _create_employee(client, salon_id)
        emp_id = emp["id"]

        await _insert_submission(salon_id, emp_id, status="error")

        resp = await client.get(
            "/api/admin/payslip/submissions",
            params={"salon_id": salon_id, "status": "error"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) >= 1
    for item in data["items"]:
        assert "days_since_paid" in item
        assert isinstance(item["days_since_paid"], int)
        assert item["days_since_paid"] >= 0


# ── Contrats list ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_contrats_list_shape() -> None:
    """Admin contrats list returns items + total with correct shape."""
    email = f"admin_{uuid.uuid4().hex[:6]}@example.com"
    async with _client() as client:
        await _register_login(client, email)
        await _make_admin(email)
        salon = await _create_salon(client)
        salon_id = salon["id"]

        user_id = await _get_user_id(email)
        contrat_id = await _insert_contrat(salon_id, user_id)

        resp = await client.get(
            "/api/admin/payslip/contrats",
            params={"salon_id": salon_id},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    assert any(item["id"] == contrat_id for item in data["items"])


# ── Metrics ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_metrics_response_shape() -> None:
    """Metrics returns current_month, previous_month and unmatched_email_count."""
    email = f"admin_{uuid.uuid4().hex[:6]}@example.com"
    async with _client() as client:
        await _register_login(client, email)
        await _make_admin(email)

        resp = await client.get("/api/admin/payslip/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "current_month" in data
    assert "previous_month" in data
    assert "unmatched_email_count" in data

    cur = data["current_month"]
    assert "bulletins_emitted" in cur
    assert "revenue_ttc_eur" in cur
    assert "error_count" in cur
    assert "avg_processing_minutes" in cur

    from datetime import UTC, datetime
    now = datetime.now(UTC)
    assert cur["year"] == now.year
    assert cur["month"] == now.month


# ── PDF upload — submission ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_upload_submission_pdf_success() -> None:
    """Manual upload sets status=pdf_attached, writes audit log."""
    email = f"admin_{uuid.uuid4().hex[:6]}@example.com"
    async with _client() as client:
        await _register_login(client, email)
        await _make_admin(email)
        salon = await _create_salon(client)
        salon_id = salon["id"]
        emp = await _create_employee(client, salon_id)
        emp_id = emp["id"]

        sub_id = await _insert_submission(salon_id, emp_id, status="pending_review")

        resp = await client.post(
            f"/api/admin/payslip/submissions/{sub_id}/upload-pdf",
            files={"file": ("bulletin.pdf", io.BytesIO(_fake_pdf()), "application/pdf")},
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "pdf_url" in data
    assert data["pdf_url"]

    # Verify DB state
    from sqlalchemy import select
    from app.models.payslip import PayslipSubmission
    from app.models.notification import AdminAuditLog

    async with AsyncSessionLocal() as db:
        sub_row = (
            await db.execute(
                select(PayslipSubmission).where(
                    PayslipSubmission.id == uuid.UUID(sub_id)
                )
            )
        ).scalar_one()
        assert sub_row.status == "pdf_attached"
        assert sub_row.pdf_url is not None
        assert sub_row.pdf_attached_by is not None and "admin:" in sub_row.pdf_attached_by

        audit_rows = (
            await db.execute(
                select(AdminAuditLog).where(
                    AdminAuditLog.target_id == sub_id,
                    AdminAuditLog.action == "upload_pdf_submission",
                )
            )
        ).scalars().all()
        assert len(audit_rows) >= 1


@pytest.mark.asyncio
async def test_admin_upload_submission_pdf_not_found() -> None:
    """Upload to unknown submission UUID → 404."""
    email = f"admin_{uuid.uuid4().hex[:6]}@example.com"
    fake_id = str(uuid.uuid4())
    async with _client() as client:
        await _register_login(client, email)
        await _make_admin(email)
        resp = await client.post(
            f"/api/admin/payslip/submissions/{fake_id}/upload-pdf",
            files={"file": ("x.pdf", io.BytesIO(_fake_pdf()), "application/pdf")},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_upload_submission_pdf_rejects_non_pdf() -> None:
    """Upload with non-PDF filename → 422."""
    email = f"admin_{uuid.uuid4().hex[:6]}@example.com"
    async with _client() as client:
        await _register_login(client, email)
        await _make_admin(email)
        salon = await _create_salon(client)
        salon_id = salon["id"]
        emp = await _create_employee(client, salon_id)
        emp_id = emp["id"]

        sub_id = await _insert_submission(salon_id, emp_id, status="pending_review")

        resp = await client.post(
            f"/api/admin/payslip/submissions/{sub_id}/upload-pdf",
            files={"file": ("bulletin.docx", io.BytesIO(b"not a pdf"), "application/msword")},
        )
    assert resp.status_code == 422


# ── PDF upload — contrat ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_upload_contrat_pdf_success() -> None:
    """Manual contrat upload sets pdf_url, status=pdf_attached, audit log."""
    email = f"admin_{uuid.uuid4().hex[:6]}@example.com"
    async with _client() as client:
        await _register_login(client, email)
        await _make_admin(email)
        salon = await _create_salon(client)
        salon_id = salon["id"]

        user_id = await _get_user_id(email)
        contrat_id = await _insert_contrat(salon_id, user_id)

        resp = await client.post(
            f"/api/admin/payslip/contrats/{contrat_id}/upload-pdf",
            files={"file": ("contrat.pdf", io.BytesIO(_fake_pdf()), "application/pdf")},
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "pdf_url" in data

    from sqlalchemy import select
    from app.models.payslip import ContratRequest
    from app.models.notification import AdminAuditLog

    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(
                select(ContratRequest).where(
                    ContratRequest.id == uuid.UUID(contrat_id)
                )
            )
        ).scalar_one()
        assert row.status == "pdf_attached"
        assert row.pdf_url is not None

        audit_rows = (
            await db.execute(
                select(AdminAuditLog).where(
                    AdminAuditLog.target_id == contrat_id,
                    AdminAuditLog.action == "upload_pdf_contrat",
                )
            )
        ).scalars().all()
        assert len(audit_rows) >= 1


@pytest.mark.asyncio
async def test_admin_upload_contrat_pdf_not_found() -> None:
    """Upload to unknown contrat UUID → 404."""
    email = f"admin_{uuid.uuid4().hex[:6]}@example.com"
    fake_id = str(uuid.uuid4())
    async with _client() as client:
        await _register_login(client, email)
        await _make_admin(email)
        resp = await client.post(
            f"/api/admin/payslip/contrats/{fake_id}/upload-pdf",
            files={"file": ("c.pdf", io.BytesIO(_fake_pdf()), "application/pdf")},
        )
    assert resp.status_code == 404


# ── Email retry ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_retry_email_not_found() -> None:
    """Retry on unknown submission UUID → 404."""
    email = f"admin_{uuid.uuid4().hex[:6]}@example.com"
    fake_id = str(uuid.uuid4())
    async with _client() as client:
        await _register_login(client, email)
        await _make_admin(email)
        resp = await client.post(
            f"/api/admin/payslip/submissions/{fake_id}/retry-email"
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_retry_email_rejects_non_error_status() -> None:
    """Retry returns 422 when submission.status != 'error'."""
    email = f"admin_{uuid.uuid4().hex[:6]}@example.com"
    async with _client() as client:
        await _register_login(client, email)
        await _make_admin(email)
        salon = await _create_salon(client)
        salon_id = salon["id"]
        emp = await _create_employee(client, salon_id)
        emp_id = emp["id"]

        sub_id = await _insert_submission(salon_id, emp_id, status="emailed")

        resp = await client.post(
            f"/api/admin/payslip/submissions/{sub_id}/retry-email"
        )
    assert resp.status_code == 422
    assert "error" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_retry_email_smtp_unavail_returns_500_but_audit_committed() -> None:
    """
    Retry on error submission → 500 when SMTP unavail.
    Audit log must be committed even after the 500 (committed before raise).
    """
    email = f"admin_{uuid.uuid4().hex[:6]}@example.com"
    async with _client() as client:
        await _register_login(client, email)
        await _make_admin(email)
        salon = await _create_salon(client)
        salon_id = salon["id"]
        emp = await _create_employee(client, salon_id)
        emp_id = emp["id"]

        sub_id = await _insert_submission(salon_id, emp_id, status="error")

        resp = await client.post(
            f"/api/admin/payslip/submissions/{sub_id}/retry-email"
        )

    # No SMTP in test env → send_variables_email returns False → 500
    assert resp.status_code == 500

    # Audit log committed before the 500 raise
    from sqlalchemy import select
    from app.models.notification import AdminAuditLog

    async with AsyncSessionLocal() as db:
        audit_rows = (
            await db.execute(
                select(AdminAuditLog).where(
                    AdminAuditLog.target_id == sub_id,
                    AdminAuditLog.action == "retry_email",
                )
            )
        ).scalars().all()
        assert len(audit_rows) >= 1


# ── Dossier status → audit log ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_dossier_status_mutation_writes_audit_log() -> None:
    """PATCH /dossiers/{salon_id}/status commits an audit_log row."""
    email = f"admin_{uuid.uuid4().hex[:6]}@example.com"
    async with _client() as client:
        await _register_login(client, email)
        await _make_admin(email)
        salon = await _create_salon(client)
        salon_id = salon["id"]

        await _insert_dossier(salon_id)

        resp = await client.patch(
            f"/api/admin/payslip/dossiers/{salon_id}/status",
            json={"status": "suspended", "notes": "Test suspension"},
        )
    assert resp.status_code == 200

    from sqlalchemy import select
    from app.models.notification import AdminAuditLog

    async with AsyncSessionLocal() as db:
        audit_rows = (
            await db.execute(
                select(AdminAuditLog).where(
                    AdminAuditLog.target_id == salon_id,
                    AdminAuditLog.action == "update_dossier_status",
                )
            )
        ).scalars().all()
        assert len(audit_rows) >= 1
        assert audit_rows[0].payload["prev_status"] == "paid"
        assert audit_rows[0].payload["new_status"] == "suspended"
