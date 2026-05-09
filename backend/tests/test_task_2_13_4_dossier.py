"""
Tests for TASK-2.13.4 — Payslip dossier purchase flow.

Covers:
  - GET  /api/salons/{salon_id}/payslip/dossier          — dossier status
  - POST /api/salons/{salon_id}/payslip/dossier/intent   — creates Stripe PI
  - POST /api/salons/{salon_id}/payslip/dossier/confirm  — marks dossier paid + sends email

All Stripe calls are mocked — no network calls.

Self-contained pattern: each test registers its own user via the API and uses
AsyncSessionLocal for any DB setup. No conftest fixture injection.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.payslip import PayslipDossier
from app.models.salon import Salon
from app.models.user import User


# ─── Self-contained infrastructure ───────────────────────────────────────────


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
        email:    Unique test email for this test.
        password: Must pass the app's validator (≥8 chars, mixed case, digit).
    """
    await client.post(
        "/api/auth/register",
        json={"email": email, "name": "Test User 2.13.4", "password": password},
    )
    await client.post("/api/auth/login", json={"email": email, "password": password})


async def _make_salon_for_email(email: str) -> uuid.UUID:
    """
    Look up the registered user by email and create a Salon owned by them.

    Args:
        email: Email of the already-registered user (lowercase, as stored by the register endpoint).

    Returns:
        The created salon's UUID.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        salon = Salon(
            id=uuid.uuid4(),
            user_id=user.id,
            name=f"Salon Test 2.13.4 {uuid.uuid4().hex[:4]}",
            business_type="sas",
            nb_employees=2,
        )
        db.add(salon)
        await db.commit()
        return salon.id


async def _make_dossier(salon_id: uuid.UUID, status: str = "not_started") -> None:
    """
    Create a PayslipDossier for the given salon with the given status.

    Args:
        salon_id: UUID of the owning salon.
        status:   Dossier status string ("not_started", "paid", "active", etc.).
    """
    async with AsyncSessionLocal() as db:
        dossier = PayslipDossier(
            salon_id=salon_id,
            status=status,
        )
        db.add(dossier)
        await db.commit()


# ─── GET /api/salons/{salon_id}/payslip/dossier ───────────────────────────────


@pytest.mark.asyncio
async def test_dossier_status_no_dossier_returns_not_started():
    """If no dossier exists for the salon, status should be 'not_started'."""
    email = f"dossier-s1-{uuid.uuid4().hex[:6]}@test.com"
    async with _client() as client:
        await _register_login(client, email)
        salon_id = await _make_salon_for_email(email)
        resp = await client.get(f"/api/salons/{salon_id}/payslip/dossier")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "not_started"


@pytest.mark.asyncio
async def test_dossier_status_paid_dossier_returned():
    """A dossier with status='paid' should be returned correctly."""
    email = f"dossier-s2-{uuid.uuid4().hex[:6]}@test.com"
    async with _client() as client:
        await _register_login(client, email)
        salon_id = await _make_salon_for_email(email)
        await _make_dossier(salon_id, status="paid")
        resp = await client.get(f"/api/salons/{salon_id}/payslip/dossier")
        assert resp.status_code == 200
        assert resp.json()["status"] == "paid"


@pytest.mark.asyncio
async def test_dossier_status_active_dossier_returned():
    """A dossier with status='active' should be returned correctly."""
    email = f"dossier-s3-{uuid.uuid4().hex[:6]}@test.com"
    async with _client() as client:
        await _register_login(client, email)
        salon_id = await _make_salon_for_email(email)
        await _make_dossier(salon_id, status="active")
        resp = await client.get(f"/api/salons/{salon_id}/payslip/dossier")
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"


# ─── POST /api/salons/{salon_id}/payslip/dossier/intent ──────────────────────


@pytest.mark.asyncio
@patch("app.services.stripe_per_submission.stripe.PaymentIntent.create")
async def test_dossier_creates_payment_intent(mock_pi_create):
    """Creating a checkout should call Stripe and return a payment_intent_id."""
    mock_pi_create.return_value = MagicMock(
        id="pi_test_dossier_001",
        client_secret="pi_test_dossier_001_secret_abc",
        amount=10200,
        currency="eur",
    )
    email = f"dossier-c1-{uuid.uuid4().hex[:6]}@test.com"
    async with _client() as client:
        await _register_login(client, email)
        salon_id = await _make_salon_for_email(email)
        resp = await client.post(f"/api/salons/{salon_id}/payslip/dossier/intent")
        assert resp.status_code in (200, 201), f"Expected 2xx got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "payment_intent_id" in data
        mock_pi_create.assert_called_once()


@pytest.mark.asyncio
@patch("app.services.stripe_per_submission.stripe.PaymentIntent.create")
async def test_dossier_already_paid_rejected(mock_pi_create):
    """If a dossier already has status 'paid' or 'active', re-checkout should return 409."""
    mock_pi_create.return_value = MagicMock(
        id="pi_test_dup",
        client_secret="pi_test_dup_secret",
        amount=10200,
        currency="eur",
    )
    email = f"dossier-c2-{uuid.uuid4().hex[:6]}@test.com"
    async with _client() as client:
        await _register_login(client, email)
        salon_id = await _make_salon_for_email(email)
        await _make_dossier(salon_id, status="paid")
        resp = await client.post(f"/api/salons/{salon_id}/payslip/dossier/intent")
        assert resp.status_code == 409, f"Expected 409 got {resp.status_code}: {resp.text}"


# ─── POST /api/salons/{salon_id}/payslip/dossier/confirm ─────────────────────


@pytest.mark.asyncio
@patch("app.routers.payslip.stripe.PaymentIntent.retrieve")
@patch("app.services.payslip_email.send_dossier_email", new_callable=AsyncMock)
async def test_dossier_confirm_marks_paid_and_sends_email(mock_email, mock_pi_retrieve):
    """Confirming a succeeded PaymentIntent should set status=paid and trigger email."""
    mock_pi_retrieve.return_value = MagicMock(
        id="pi_test_confirm_001",
        status="succeeded",
        amount=10200,
        currency="eur",
        metadata={},
    )
    email = f"dossier-confirm1-{uuid.uuid4().hex[:6]}@test.com"
    async with _client() as client:
        await _register_login(client, email)
        salon_id = await _make_salon_for_email(email)
        resp = await client.post(
            f"/api/salons/{salon_id}/payslip/dossier/confirm",
            json={"payment_intent_id": "pi_test_confirm_001"},
        )
        assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("dossier_status") == "paid"
        mock_email.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.routers.payslip.stripe.PaymentIntent.retrieve")
async def test_dossier_confirm_failed_payment_returns_error(mock_pi_retrieve):
    """A PaymentIntent with status != 'succeeded' should return a 400."""
    mock_pi_retrieve.return_value = MagicMock(
        id="pi_test_failed_001",
        status="requires_payment_method",
        amount=10200,
        currency="eur",
        metadata={},
    )
    email = f"dossier-confirm2-{uuid.uuid4().hex[:6]}@test.com"
    async with _client() as client:
        await _register_login(client, email)
        salon_id = await _make_salon_for_email(email)
        resp = await client.post(
            f"/api/salons/{salon_id}/payslip/dossier/confirm",
            json={"payment_intent_id": "pi_test_failed_001"},
        )
        assert resp.status_code in (400, 402, 422), (
            f"Expected 4xx got {resp.status_code}: {resp.text}"
        )
