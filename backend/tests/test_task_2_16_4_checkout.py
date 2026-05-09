"""
Tests for TASK-2.16.4 — Stripe Checkout session creation for subscriptions.

Covers:
  1. _detect_legacy_conflict — pure function, no DB
  2. POST /api/billing/create-checkout-session:
       - Valid SKU, authenticated + Stripe mocked → 200 checkout_url + session_id
       - Unknown SKU → 422
       - Legacy plan conflict → 409
       - Stripe Price ID not configured → 503
       - Stripe API error → 502
       - Unauthenticated → 401
  3. Webhook: checkout.session.completed (kind=subscription) → 200 subscription_activated
  4. Webhook: checkout.session.completed (other kind) → 200 ignored

Note: pytest-mock is NOT available in this project — use unittest.mock.patch directly.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import stripe
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.dependencies import get_current_user
from app.routers.billing import _detect_legacy_conflict


# ── Self-contained client helpers (project pattern — see test_task_2_13_2) ───


def _api_client() -> AsyncClient:
    """Return a fresh unauthenticated ASGI test client."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _register_login(client: AsyncClient, email: str) -> None:
    """Register + log in, setting the session cookie on the client."""
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "name": "Test Billing"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"


# ── 1. _detect_legacy_conflict pure-function tests ────────────────────────────


def _mock_user(legacy_plan: str | None) -> MagicMock:
    """Build a minimal User-like object for conflict detection tests."""
    u = MagicMock()
    u.legacy_pricing_plan = legacy_plan
    return u


def test_no_legacy_no_conflict():
    """Standard new user (no legacy plan) should never conflict."""
    assert _detect_legacy_conflict(_mock_user(None), "ccpilot_monthly_2026_05") is None


def test_legacy_same_family_conflicts():
    """Legacy CCPilot user requesting CCPilot solo → conflict."""
    result = _detect_legacy_conflict(_mock_user("legacy_99_yearly"), "ccpilot_monthly_2026_05")
    assert result is not None
    assert "99" in result


def test_legacy_different_family_no_conflict():
    """Legacy BIC compta user requesting CCPilot solo → no conflict."""
    assert _detect_legacy_conflict(_mock_user("legacy_bic_63_monthly"), "ccpilot_monthly_2026_05") is None


def test_legacy_bic_plus_conflicts_with_bic_plus_pack():
    """Legacy BIC+ user trying to buy BIC+ pack → conflict."""
    result = _detect_legacy_conflict(
        _mock_user("legacy_bic_plus_93_monthly"),
        "pack_bic_plus_ccpilot_monthly_2026_05",
    )
    assert result is not None


def test_legacy_bic_plus_ok_for_bic_pack():
    """Legacy BIC+ (93) trying BIC pack — different family → no conflict."""
    assert _detect_legacy_conflict(
        _mock_user("legacy_bic_plus_93_monthly"),
        "pack_bic_ccpilot_monthly_2026_05",
    ) is None


def test_unknown_sku_returns_none():
    """Unknown SKU key → no conflict (graceful fallback)."""
    assert _detect_legacy_conflict(_mock_user("legacy_99_yearly"), "totally_unknown_sku_2099") is None


# ── 2. POST /api/billing/create-checkout-session ──────────────────────────────


@pytest.mark.asyncio
async def test_create_checkout_session_valid():
    """Valid SKU + authenticated user + Stripe mocked → 200 with checkout_url."""
    fake_url = "https://checkout.stripe.com/c/pay/cs_test_fake"
    fake_session_id = "cs_test_fake_session_001"

    mock_session = MagicMock()
    mock_session.url = fake_url
    mock_session.id = fake_session_id

    email = f"billing_valid_{uuid4().hex[:8]}@test.fr"

    with (
        patch("app.routers.billing._stripe_call", new=AsyncMock(return_value=mock_session)),
        patch("app.routers.billing.get_price_id", return_value="price_test_ccpilot"),
        patch(
            "app.routers.billing.get_catalogue_entry",
            return_value={"trial_days": 14, "label": "CCPilot", "ht_eur": "32.00"},
        ),
    ):
        async with _api_client() as client:
            await _register_login(client, email)
            resp = await client.post(
                "/api/billing/create-checkout-session",
                json={"logical_sku_key": "ccpilot_monthly_2026_05"},
            )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["checkout_url"] == fake_url
    assert data["session_id"] == fake_session_id


@pytest.mark.asyncio
async def test_create_checkout_session_unknown_sku():
    """Unknown SKU key → 422."""
    email = f"billing_sku_{uuid4().hex[:8]}@test.fr"
    async with _api_client() as client:
        await _register_login(client, email)
        resp = await client.post(
            "/api/billing/create-checkout-session",
            json={"logical_sku_key": "not_a_real_sku_2099"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_checkout_session_legacy_conflict():
    """
    Legacy plan conflict → 409 with human-readable detail.

    FastAPI resolves get_current_user via Depends(), so we override via
    app.dependency_overrides (the correct approach for FastAPI integration tests).
    """
    mock_legacy_user = MagicMock()
    mock_legacy_user.id = uuid4()
    mock_legacy_user.email = "legacy_conflict@test.fr"
    mock_legacy_user.legacy_pricing_plan = "legacy_99_yearly"

    # dependency_overrides must be a callable (sync or async)
    async def _override_user():
        return mock_legacy_user

    app.dependency_overrides[get_current_user] = _override_user
    try:
        async with _api_client() as client:
            resp = await client.post(
                "/api/billing/create-checkout-session",
                json={"logical_sku_key": "ccpilot_monthly_2026_05"},
            )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "forfait" in detail.lower() or "préservé" in detail.lower()


@pytest.mark.asyncio
async def test_create_checkout_session_price_id_not_configured():
    """Stripe Price ID env var not set → 503."""
    email = f"billing_503_{uuid4().hex[:8]}@test.fr"

    with patch(
        "app.routers.billing.get_price_id",
        side_effect=RuntimeError("STRIPE_PRICE_CCPILOT_MONTHLY not set"),
    ):
        async with _api_client() as client:
            await _register_login(client, email)
            resp = await client.post(
                "/api/billing/create-checkout-session",
                json={"logical_sku_key": "ccpilot_monthly_2026_05"},
            )
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_create_checkout_session_stripe_api_error():
    """Stripe API error → 502."""
    email = f"billing_502_{uuid4().hex[:8]}@test.fr"

    with (
        patch("app.routers.billing.get_price_id", return_value="price_test_ccpilot"),
        patch(
            "app.routers.billing.get_catalogue_entry",
            return_value={"trial_days": 14, "label": "CCPilot", "ht_eur": "32.00"},
        ),
        patch(
            "app.routers.billing._stripe_call",
            new=AsyncMock(side_effect=stripe.error.StripeError("Stripe unavailable")),
        ),
    ):
        async with _api_client() as client:
            await _register_login(client, email)
            resp = await client.post(
                "/api/billing/create-checkout-session",
                json={"logical_sku_key": "ccpilot_monthly_2026_05"},
            )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_create_checkout_session_unauthenticated():
    """No session cookie → 401."""
    async with _api_client() as client:
        resp = await client.post(
            "/api/billing/create-checkout-session",
            json={"logical_sku_key": "ccpilot_monthly_2026_05"},
        )
    assert resp.status_code == 401


# ── 3. Webhook — checkout.session.completed for subscription ──────────────────


def _build_stripe_event_mock(kind: str) -> MagicMock:
    """
    Build a MagicMock that mimics a Stripe Event object.

    The webhook handler uses BOTH dict-style access (event.get("type")) AND
    attribute access (event.data.object.metadata). A plain SimpleNamespace only
    supports attributes, so we use MagicMock and wire .get() manually.
    """
    metadata = {
        "kind": kind,
        "user_id": "00000000-0000-0000-0000-000000000099",
        "logical_sku_key": "ccpilot_monthly_2026_05",
    }
    top_level = {"type": "checkout.session.completed", "id": f"evt_test_{kind}"}

    event = MagicMock()
    # Dict-style .get("type", "") — used by the webhook router
    event.get.side_effect = lambda key, default="": top_level.get(key, default)
    # Attribute-style event.data.object
    event.data.object.id = "cs_test_fake"
    event.data.object.subscription = "sub_test_001"
    event.data.object.customer_email = "test@example.fr"
    # metadata.get("kind", "") — also dict-style
    event.data.object.metadata.get.side_effect = lambda key, default="": metadata.get(key, default)
    # Support getattr(intent, "metadata", {}) — MagicMock handles this
    return event


def _build_sub_event_dict(kind: str = "subscription") -> dict:
    """Build a plain dict for the raw webhook payload body."""
    return {
        "id": f"evt_test_{kind}",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_fake",
                "subscription": "sub_test_001",
                "customer_email": "test@example.fr",
                "metadata": {
                    "kind": kind,
                    "user_id": "00000000-0000-0000-0000-000000000099",
                    "logical_sku_key": "ccpilot_monthly_2026_05",
                },
            }
        },
    }


@pytest.mark.asyncio
async def test_webhook_subscription_checkout_completed():
    """
    checkout.session.completed + kind=subscription →
    200 {"status": "subscription_activated"}.
    """
    payload = json.dumps(_build_sub_event_dict("subscription")).encode()
    mock_event = _build_stripe_event_mock("subscription")

    with patch(
        "app.routers.stripe_webhooks.verify_webhook_signature",
        return_value=mock_event,
    ):
        async with _api_client() as client:
            resp = await client.post(
                "/api/stripe/webhook",
                content=payload,
                headers={"Content-Type": "application/json"},
            )

    assert resp.status_code == 200
    assert resp.json()["status"] == "subscription_activated"


@pytest.mark.asyncio
async def test_webhook_non_subscription_checkout_ignored():
    """
    checkout.session.completed + kind != 'subscription' →
    200 {"status": "ignored"} (falls through to default ignore branch).
    """
    payload = json.dumps(_build_sub_event_dict("payslip")).encode()
    mock_event = _build_stripe_event_mock("payslip")

    with patch(
        "app.routers.stripe_webhooks.verify_webhook_signature",
        return_value=mock_event,
    ):
        async with _api_client() as client:
            resp = await client.post(
                "/api/stripe/webhook",
                content=payload,
                headers={"Content-Type": "application/json"},
            )

    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"
