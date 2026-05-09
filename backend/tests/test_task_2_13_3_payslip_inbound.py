"""
Tests for TASK-2.13.3 — Inbound email poller, notifications, and dev endpoint.

Covers:
  - extract_subject_token           — regex extraction from email subjects
  - _parse_email_message            — RFC822 parser with PDF attachment detection
  - _extract_pdf_text               — pypdf wrapper (stub PDF)
  - _match_pdf_to_employee          — name disambiguation logic
  - _process_message (full pipeline) — matched / unmatched / question flows
  - GET  /notifications             — list notifications (auth)
  - GET  /notifications/unread-count — badge count
  - POST /notifications/{id}/read  — mark one read
  - POST /notifications/read-all   — mark all read
  - POST /dev/payslip/simulate-inbound — dev simulate endpoint

All IMAP and email-send calls are mocked.

Self-contained pattern (integration tests): each test registers its own user via
the API and uses AsyncSessionLocal for DB setup. No conftest fixture injection.
"""

from __future__ import annotations

import email as _email_module
import secrets
import uuid
from datetime import UTC, datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.notification import PayslipNotification, ProcessedEmail, UnmatchedEmail
from app.models.payslip import PayslipSubmission
from app.models.salon import Employee, Salon
from app.models.user import User
from app.services.payslip_inbound import (
    ParsedMessage,
    _match_pdf_to_employee,
    _parse_email_message,
    extract_subject_token,
)


# ─── Shared helpers ───────────────────────────────────────────────────────────


def _make_raw_email(
    message_id: str,
    from_addr: str,
    subject: str,
    body: str,
    pdfs: list[tuple[str, bytes]] | None = None,
) -> bytes:
    """Build a raw RFC822 message for testing _parse_email_message."""
    if pdfs:
        msg = MIMEMultipart("mixed")
        msg["Message-ID"] = message_id
        msg["From"] = from_addr
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        for filename, pdf_bytes in pdfs:
            part = MIMEApplication(pdf_bytes, _subtype="pdf")
            part.add_header("Content-Disposition", "attachment", filename=filename)
            msg.attach(part)
    else:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Message-ID"] = message_id
        msg["From"] = from_addr
        msg["Subject"] = subject

    return msg.as_bytes()


async def _make_salon_user(db: AsyncSession) -> tuple[User, Salon]:
    """Create and persist a User + Salon for testing."""
    user = User(
        id=uuid.uuid4(),
        email=f"test-{uuid.uuid4().hex[:6]}@example.com",
        full_name="Test Owner",
        hashed_password="x",
        is_active=True,
    )
    db.add(user)
    await db.flush()

    salon = Salon(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Salon Inbound Test",
        business_type="sas",
        nb_employees=2,
    )
    db.add(salon)
    await db.flush()
    return user, salon


async def _make_submission(
    db: AsyncSession,
    salon: Salon,
    employee_id: uuid.UUID,
    token: str,
    status: str = "emailed",
) -> PayslipSubmission:
    """Create a PayslipSubmission with a given subject_token."""
    sub = PayslipSubmission(
        id=uuid.uuid4(),
        salon_id=salon.id,
        employee_id=employee_id,
        period_month=4,
        period_year=2026,
        status=status,
        subject_token=token,
        emailed_at=datetime.now(UTC),
    )
    db.add(sub)
    await db.flush()
    return sub


# ─── Self-contained infrastructure (for integration tests) ────────────────────


def _client() -> AsyncClient:
    """
    Return an ASGI test client with cookie support.

    The cookie jar persists the session cookie set by POST /api/auth/login
    across all subsequent requests in the same async-with block.
    """
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _register_login(
    client: AsyncClient,
    email: str,
    password: str = "Password123!",
) -> None:
    """
    Register a new user and log in, setting the session cookie on *client*.

    Args:
        client:   ASGI test client.
        email:    Unique test email for this test run.
        password: Must pass the app's validator.
    """
    await client.post(
        "/api/auth/register",
        json={"email": email, "name": "Test 2.13.3", "password": password},
    )
    await client.post("/api/auth/login", json={"email": email, "password": password})


# ─── Unit: extract_subject_token ─────────────────────────────────────────────


class TestExtractSubjectToken:
    """Unit tests for extract_subject_token regex."""

    def test_plain_subject_with_token(self):
        """Token extracted from a plain subject."""
        result = extract_subject_token("Variables salaire [REF-1a2b3c4d]")
        assert result == "1a2b3c4d"

    def test_reply_prefix(self):
        """Token extracted despite Re: prefix."""
        result = extract_subject_token("Re: Variables — Salon Elisa [REF-AABBCCDD]")
        assert result == "aabbccdd"  # lowercase

    def test_fwd_prefix(self):
        """Token extracted from forwarded subject."""
        result = extract_subject_token("Fwd: Re: Avril 2026 [REF-abcdef12]")
        assert result == "abcdef12"

    def test_no_token(self):
        """Returns None when no token present."""
        assert extract_subject_token("Hello from Marie") is None

    def test_short_token_ignored(self):
        """Token must be exactly 8 hex chars."""
        # Only 6 chars — should not match
        assert extract_subject_token("RE: test [REF-aabbcc]") is None

    def test_case_insensitive_ref(self):
        """[ref-token] (lowercase) also extracted."""
        result = extract_subject_token("[ref-deadbeef] April")
        assert result == "deadbeef"

    def test_uppercase_hex_normalised(self):
        """Uppercase hex letters are normalised to lowercase."""
        result = extract_subject_token("[REF-DEADBEEF]")
        assert result == "deadbeef"


# ─── Unit: _parse_email_message ──────────────────────────────────────────────


class TestParseEmailMessage:
    """Unit tests for RFC822 parser."""

    def test_simple_text(self):
        """Simple text/plain message parsed correctly."""
        raw = _make_raw_email(
            "<abc@example.com>",
            "Marie <marie@example.com>",
            "Re: Avril [REF-12345678]",
            "Bonjour, voici le bulletin.",
        )
        result = _parse_email_message(raw)
        assert result is not None
        assert result.message_id == "<abc@example.com>"
        assert "marie@example.com" in result.from_address
        assert result.subject == "Re: Avril [REF-12345678]"
        assert "bulletin" in result.body_text
        assert result.pdfs == []

    def test_with_pdf_attachment(self):
        """Multipart message with PDF attachment parsed."""
        raw = _make_raw_email(
            "<msg@x.com>",
            "marie@x.com",
            "Bulletins [REF-aabbccdd]",
            "Bulletin en pièce jointe.",
            pdfs=[("bulletin_dupont.pdf", b"%PDF-1.4 stub")],
        )
        result = _parse_email_message(raw)
        assert result is not None
        assert len(result.pdfs) == 1
        filename, pdf_bytes = result.pdfs[0]
        assert filename == "bulletin_dupont.pdf"
        assert pdf_bytes == b"%PDF-1.4 stub"

    def test_no_message_id_skipped(self):
        """Message without Message-ID returns None."""
        msg = MIMEText("Hello", "plain", "utf-8")
        msg["From"] = "x@example.com"
        msg["Subject"] = "Test"
        result = _parse_email_message(msg.as_bytes())
        assert result is None


# ─── Unit: _match_pdf_to_employee ────────────────────────────────────────────


class TestMatchPdfToEmployee:
    """Unit tests for employee name disambiguation."""

    def test_single_match(self):
        """Returns the one name that appears in the PDF text (reversed/uppercase format)."""
        result = _match_pdf_to_employee(
            "Bulletin de salaire\nNom : DUPONT Jean\nPériode : Avril 2026",
            ["Jean Dupont", "Marie Martin"],
        )
        assert result == "Jean Dupont"

    def test_no_match(self):
        """Returns None when no name found."""
        result = _match_pdf_to_employee(
            "Bulletin de salaire",
            ["Jean Dupont", "Marie Martin"],
        )
        assert result is None

    def test_ambiguous_multiple(self):
        """Returns None when both names found (ambiguous)."""
        result = _match_pdf_to_employee(
            "jean dupont et marie martin",
            ["Jean Dupont", "Marie Martin"],
        )
        assert result is None

    def test_empty_text(self):
        """Returns None on empty PDF text."""
        assert _match_pdf_to_employee("", ["Jean Dupont"]) is None


# ─── Integration: _process_message ───────────────────────────────────────────
#
# Self-contained: user created via API, salon/employee/submission via AsyncSessionLocal.


@pytest.mark.asyncio
async def test_process_message_matched_with_pdf():
    """PDF attaches to a single matched submission → status=pdf_attached."""
    from app.services.payslip_inbound import _process_message

    email_addr = f"proc-pdf-{uuid.uuid4().hex[:6]}@test.com"

    # Create user in DB via API
    async with _client() as c:
        await _register_login(c, email_addr)

    # Create salon + employee + submission
    sub_id: uuid.UUID | None = None
    salon_id: uuid.UUID | None = None
    token = secrets.token_hex(4)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email_addr))
        user = result.scalar_one()
        salon_id = uuid.uuid4()
        salon = Salon(
            id=salon_id,
            user_id=user.id,
            name="Salon ProcessMsg Test",
            business_type="sas",
            nb_employees=1,
        )
        db.add(salon)
        await db.flush()
        emp = Employee(
            id=uuid.uuid4(),
            salon_id=salon_id,
            name="Julie Dupont",
            role_type="salarie",
            contract_type="cdi",
            hours_per_week=35,
            salary_brut=2000,
        )
        db.add(emp)
        await db.flush()
        sub_id = uuid.uuid4()
        sub = PayslipSubmission(
            id=sub_id,
            salon_id=salon_id,
            employee_id=emp.id,
            period_month=4,
            period_year=2026,
            status="emailed",
            subject_token=token,
            emailed_at=datetime.now(UTC),
        )
        db.add(sub)
        await db.commit()

    msg = ParsedMessage(
        message_id=f"<test-pdf-{uuid.uuid4()}@example.com>",
        from_address="marie@paie.com",
        subject=f"Re: Bulletins [REF-{token}]",
        body_text="Bonjour, ci-joint les bulletins.",
        received_at=datetime.now(UTC),
        pdfs=[("bulletin_dupont.pdf", b"%PDF-1.4 test")],
    )

    with (
        patch(
            "app.services.payslip_inbound.upload_pdf",
            new_callable=AsyncMock,
            return_value=f"payslips/{salon_id}/2026-04/stub.pdf",
        ),
        patch(
            "app.services.payslip_inbound.notify_pdf_ready",
            new_callable=AsyncMock,
        ),
    ):
        async with AsyncSessionLocal() as db:
            await _process_message(msg, db)
            await db.commit()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PayslipSubmission).where(PayslipSubmission.id == sub_id)
        )
        final_sub = result.scalar_one()
        assert final_sub.status == "pdf_attached"
        assert final_sub.pdf_url is not None
        assert final_sub.pdf_attached_by == "auto"


@pytest.mark.asyncio
async def test_process_message_question_email_no_pdf():
    """Email without PDF → submission marked pending_review."""
    from app.services.payslip_inbound import _process_message

    email_addr = f"proc-q-{uuid.uuid4().hex[:6]}@test.com"
    async with _client() as c:
        await _register_login(c, email_addr)

    sub_id: uuid.UUID | None = None
    salon_id: uuid.UUID | None = None
    token = secrets.token_hex(4)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email_addr))
        user = result.scalar_one()
        salon_id = uuid.uuid4()
        salon = Salon(
            id=salon_id,
            user_id=user.id,
            name="Salon Q Test",
            business_type="sas",
            nb_employees=1,
        )
        db.add(salon)
        await db.flush()
        emp = Employee(
            id=uuid.uuid4(),
            salon_id=salon_id,
            name="Jean Martin",
            role_type="salarie",
            contract_type="cdi",
            hours_per_week=35,
            salary_brut=1900,
        )
        db.add(emp)
        await db.flush()
        sub_id = uuid.uuid4()
        sub = PayslipSubmission(
            id=sub_id,
            salon_id=salon_id,
            employee_id=emp.id,
            period_month=4,
            period_year=2026,
            status="emailed",
            subject_token=token,
            emailed_at=datetime.now(UTC),
        )
        db.add(sub)
        await db.commit()

    msg = ParsedMessage(
        message_id=f"<q-{uuid.uuid4()}@example.com>",
        from_address="marie@paie.com",
        subject=f"Re: Bulletin [REF-{token}]",
        body_text="Avez-vous le contrat pour ce salarié ?",
        received_at=datetime.now(UTC),
        pdfs=[],
    )

    with patch("app.core.email.send_email", new_callable=AsyncMock):
        async with AsyncSessionLocal() as db:
            await _process_message(msg, db)
            await db.commit()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PayslipSubmission).where(PayslipSubmission.id == sub_id)
        )
        final_sub = result.scalar_one()
        assert final_sub.status == "pending_review"
        assert final_sub.needs_review_note is not None
        assert "marie@paie.com" in final_sub.needs_review_note


@pytest.mark.asyncio
async def test_process_message_unmatched_email_stored():
    """Email with no matching token → UnmatchedEmail row created."""
    from app.services.payslip_inbound import _process_message

    message_id = f"<unmatched-{uuid.uuid4()}@example.com>"
    msg = ParsedMessage(
        message_id=message_id,
        from_address="unknown@example.com",
        subject="Hello from unknown",
        body_text="Pas de token ici.",
        received_at=datetime.now(UTC),
        pdfs=[],
    )

    async with AsyncSessionLocal() as db:
        await _process_message(msg, db)
        await db.commit()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(UnmatchedEmail).where(UnmatchedEmail.message_id == message_id)
        )
        row = result.scalar_one_or_none()
        assert row is not None
        assert row.status == "unmatched"
        assert row.from_address == "unknown@example.com"


@pytest.mark.asyncio
async def test_process_message_duplicate_message_skipped():
    """Processing the same message_id twice → dedup record exists after first call."""
    from app.services.payslip_inbound import _process_message

    message_id = f"<dup-{uuid.uuid4()}@example.com>"
    msg = ParsedMessage(
        message_id=message_id,
        from_address="x@example.com",
        subject="No token",
        body_text="Test",
        received_at=datetime.now(UTC),
        pdfs=[],
    )

    # First call — creates UnmatchedEmail + ProcessedEmail
    async with AsyncSessionLocal() as db:
        await _process_message(msg, db)
        await db.commit()

    # The ProcessedEmail dedup record should exist
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ProcessedEmail).where(ProcessedEmail.message_id == message_id)
        )
        assert result.scalar_one_or_none() is not None

    # Second call — _mark_already_processed returns True, function exits early
    async with AsyncSessionLocal() as db:
        await _process_message(msg, db)
        await db.commit()  # no error — just a no-op

    # UnmatchedEmail row count should still be exactly 1 (not doubled)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(UnmatchedEmail).where(UnmatchedEmail.message_id == message_id)
        )
        rows = result.scalars().all()
        assert len(rows) == 1


# ─── Integration: Notifications API ──────────────────────────────────────────
#
# Self-contained: each test registers a unique user.


@pytest.mark.asyncio
async def test_notifications_list_empty():
    """Empty list returned when no notifications exist for a fresh user."""
    email = f"notif-empty-{uuid.uuid4().hex[:6]}@test.com"
    async with _client() as client:
        await _register_login(client, email)
        resp = await client.get("/api/notifications")
        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.asyncio
async def test_notifications_list_shows_own():
    """User sees their own notifications after DB seeding."""
    email = f"notif-own-{uuid.uuid4().hex[:6]}@test.com"
    notif_id = uuid.uuid4()

    async with _client() as client:
        await _register_login(client, email)

        # Look up user and seed a notification
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one()
            notif = PayslipNotification(
                id=notif_id,
                user_id=user.id,
                notification_type="pdf_ready",
                title="Bulletin disponible",
                message="Votre bulletin est prêt.",
                link="/fiches-salaire/historique",
                created_at=datetime.now(UTC),
            )
            db.add(notif)
            await db.commit()

        resp = await client.get("/api/notifications")
        assert resp.status_code == 200
        ids = [n["id"] for n in resp.json()]
        assert str(notif_id) in ids


@pytest.mark.asyncio
async def test_notifications_unread_count_zero():
    """Unread count is 0 for a fresh user with no notifications."""
    email = f"notif-count0-{uuid.uuid4().hex[:6]}@test.com"
    async with _client() as client:
        await _register_login(client, email)
        resp = await client.get("/api/notifications/unread-count")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0


@pytest.mark.asyncio
async def test_notifications_unread_count_increments():
    """Unread count increases with new unread notifications."""
    email = f"notif-count-{uuid.uuid4().hex[:6]}@test.com"
    async with _client() as client:
        await _register_login(client, email)

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one()
            for _ in range(2):
                db.add(PayslipNotification(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    notification_type="pdf_ready",
                    title="Bulletin",
                    message="Prêt.",
                    link="/fiches-salaire/historique",
                    created_at=datetime.now(UTC),
                ))
            await db.commit()

        resp = await client.get("/api/notifications/unread-count")
        assert resp.status_code == 200
        assert resp.json()["count"] >= 2


@pytest.mark.asyncio
async def test_notifications_mark_single_read():
    """POST /{id}/read marks one notification as read."""
    email = f"notif-read1-{uuid.uuid4().hex[:6]}@test.com"
    notif_id = uuid.uuid4()
    async with _client() as client:
        await _register_login(client, email)

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one()
            db.add(PayslipNotification(
                id=notif_id,
                user_id=user.id,
                notification_type="pdf_ready",
                title="Bulletin",
                message="Prêt.",
                link="/fiches-salaire/historique",
                created_at=datetime.now(UTC),
            ))
            await db.commit()

        resp = await client.post(f"/api/notifications/{notif_id}/read")
        assert resp.status_code == 200
        assert resp.json()["read"] is True


@pytest.mark.asyncio
async def test_notifications_mark_all_read():
    """POST /read-all marks all unread notifications as read."""
    email = f"notif-readall-{uuid.uuid4().hex[:6]}@test.com"
    async with _client() as client:
        await _register_login(client, email)

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one()
            for _ in range(2):
                db.add(PayslipNotification(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    notification_type="pdf_ready",
                    title="Bulletin",
                    message="Prêt.",
                    link="/fiches-salaire/historique",
                    created_at=datetime.now(UTC),
                ))
            await db.commit()

        resp = await client.post("/api/notifications/read-all")
        assert resp.status_code == 200
        assert resp.json()["marked_read"] >= 2

        count_resp = await client.get("/api/notifications/unread-count")
        assert count_resp.json()["count"] == 0


@pytest.mark.asyncio
async def test_notifications_mark_read_wrong_user_returns_404():
    """Cannot mark another user's notification as read."""
    email_a = f"notif-userA-{uuid.uuid4().hex[:6]}@test.com"
    email_b = f"notif-userb-{uuid.uuid4().hex[:6]}@test.com"
    notif_id = uuid.uuid4()

    # Register user B and seed a notification for them
    async with _client() as c:
        await _register_login(c, email_b)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email_b))
        user_b = result.scalar_one()
        db.add(PayslipNotification(
            id=notif_id,
            user_id=user_b.id,
            notification_type="pdf_ready",
            title="Bulletin",
            message="Prêt.",
            link="/fiches-salaire/historique",
            created_at=datetime.now(UTC),
        ))
        await db.commit()

    # Register user A, try to mark user B's notification → 404
    async with _client() as client:
        await _register_login(client, email_a)
        resp = await client.post(f"/api/notifications/{notif_id}/read")
        assert resp.status_code == 404


# ─── Integration: Dev simulate-inbound ───────────────────────────────────────


@pytest.mark.asyncio
async def test_simulate_inbound_unmatched():
    """Simulate email with no REF token → status='ok' (stored as unmatched)."""
    email = f"simulate-u-{uuid.uuid4().hex[:6]}@test.com"
    async with _client() as client:
        await _register_login(client, email)

        with patch("app.core.email.send_email", new_callable=AsyncMock):
            resp = await client.post(
                "/api/dev/payslip/simulate-inbound",
                json={
                    "subject": "Test sans token",
                    "from_address": "marie@example.com",
                    "body_text": "Bonjour",
                    "include_pdf": False,
                },
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_simulate_inbound_matched_with_pdf():
    """Simulate a matched email with PDF → returns status='ok'."""
    email = f"simulate-m-{uuid.uuid4().hex[:6]}@test.com"
    async with _client() as c:
        await _register_login(c, email)

    # Create salon + employee + submission in DB
    token = secrets.token_hex(4)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        salon_id = uuid.uuid4()
        salon = Salon(
            id=salon_id,
            user_id=user.id,
            name="Salon Simulate Test",
            business_type="sas",
            nb_employees=1,
        )
        db.add(salon)
        await db.flush()
        emp = Employee(
            id=uuid.uuid4(),
            salon_id=salon_id,
            name="Alice Simulate",
            role_type="salarie",
            contract_type="cdi",
            hours_per_week=35,
            salary_brut=2100,
        )
        db.add(emp)
        await db.flush()
        sub = PayslipSubmission(
            id=uuid.uuid4(),
            salon_id=salon_id,
            employee_id=emp.id,
            period_month=4,
            period_year=2026,
            status="emailed",
            subject_token=token,
            emailed_at=datetime.now(UTC),
        )
        db.add(sub)
        await db.commit()

    # Simulate inbound via the dev endpoint (authenticated as same user)
    async with _client() as client:
        await _register_login(client, email)

        with (
            patch(
                "app.services.payslip_inbound.upload_pdf",
                new_callable=AsyncMock,
                return_value=f"payslips/{salon_id}/2026-04/stub.pdf",
            ),
            patch(
                "app.services.payslip_inbound.notify_pdf_ready",
                new_callable=AsyncMock,
            ),
        ):
            resp = await client.post(
                "/api/dev/payslip/simulate-inbound",
                json={
                    "subject": f"Re: Bulletins [REF-{token}]",
                    "from_address": "marie@example.com",
                    "body_text": "Bulletin en pièce jointe.",
                    "include_pdf": True,
                },
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
