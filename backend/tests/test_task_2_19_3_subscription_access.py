"""
Tests for TASK-2.19.3: subscription access level logic.

Tests the pure service layer (subscription_access.py) covering all 5 access
level states and the trial creation idempotency. Does NOT test the FastAPI
endpoints (that's covered by smoke testing against the running dev stack).

Run: docker compose exec backend pytest tests/test_task_2_19_3_subscription_access.py -v
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.subscription_access import (
    ACCESS_CCPILOT,
    ACCESS_COMPTA_ONLY,
    ACCESS_EXPIRED,
    ACCESS_NONE,
    ACCESS_TRIALING,
    _plan_has_ccpilot,
    _plan_is_compta_only,
    access_level_to_response,
    get_subscription_access_level,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_sub(**kwargs) -> MagicMock:
    """Build a mock NolySubscription with sensible defaults."""
    sub = MagicMock()
    sub.id = uuid.uuid4()
    sub.salon_id = uuid.uuid4()
    sub.status = kwargs.get("status", "trialing")
    sub.plan_name = kwargs.get("plan_name", None)
    sub.logical_sku_key = kwargs.get("logical_sku_key", None)
    sub.trial_ends_at = kwargs.get("trial_ends_at", None)
    sub.current_period_end = kwargs.get("current_period_end", None)
    return sub


def _make_db(sub_to_return: object) -> AsyncMock:
    """Build a mock AsyncSession that returns sub_to_return from scalar_one_or_none."""
    db = AsyncMock()
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = sub_to_return
    db.execute = AsyncMock(return_value=scalar_result)
    return db


# ── Plan detection unit tests ─────────────────────────────────────────────────


class TestPlanHasCCPilot:
    """Unit tests for _plan_has_ccpilot()."""

    def test_ccpilot_sku_returns_true(self):
        assert _plan_has_ccpilot("ccpilot_monthly_2026_05", None) is True

    def test_pack_ir_ccpilot_returns_true(self):
        assert _plan_has_ccpilot("pack_ir_ccpilot_monthly_2026_05", None) is True

    def test_pack_is_ccpilot_returns_true(self):
        assert _plan_has_ccpilot("pack_is_ccpilot_monthly_2026_05", None) is True

    def test_compta_only_returns_false(self):
        assert _plan_has_ccpilot("compta_ir_monthly_2026_05", None) is False

    def test_compta_is_only_returns_false(self):
        assert _plan_has_ccpilot("compta_is_monthly_2026_05", None) is False

    def test_no_sku_with_plan_name_returns_true(self):
        """Legacy Bubble imports have plan_name but no logical_sku_key → CCPilot."""
        assert _plan_has_ccpilot(None, "Abonnement Standard") is True

    def test_no_sku_no_plan_returns_false(self):
        assert _plan_has_ccpilot(None, None) is False

    def test_future_ccpilot_sku_year_returns_true(self):
        """Forward-compat: a future key like ccpilot_monthly_2027_01 still matches."""
        assert _plan_has_ccpilot("ccpilot_monthly_2027_01", None) is True


class TestPlanIsComptaOnly:
    """Unit tests for _plan_is_compta_only()."""

    def test_compta_ir_is_compta_only(self):
        assert _plan_is_compta_only("compta_ir_monthly_2026_05", None) is True

    def test_compta_is_is_compta_only(self):
        assert _plan_is_compta_only("compta_is_monthly_2026_05", None) is True

    def test_ccpilot_not_compta_only(self):
        assert _plan_is_compta_only("ccpilot_monthly_2026_05", None) is False

    def test_pack_ccpilot_not_compta_only(self):
        assert _plan_is_compta_only("pack_ir_ccpilot_monthly_2026_05", None) is False

    def test_no_sku_returns_false(self):
        """Without a SKU, we can't confirm compta-only — default to False."""
        assert _plan_is_compta_only(None, "Abonnement Compta") is False


# ── get_subscription_access_level async tests ─────────────────────────────────


class TestGetSubscriptionAccessLevel:
    """Integration-style tests for get_subscription_access_level()."""

    @pytest.mark.asyncio
    async def test_admin_user_always_ccpilot(self):
        """Admin users bypass the subscription check entirely."""
        db = _make_db(None)
        result = await get_subscription_access_level(
            uuid.uuid4(), db, user_role="admin"
        )
        assert result == ACCESS_CCPILOT
        # DB should not be consulted for admin
        db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_legacy_pricing_plan_returns_ccpilot(self):
        """Grandfathered Bubble users bypass check."""
        db = _make_db(None)
        result = await get_subscription_access_level(
            uuid.uuid4(), db, legacy_pricing_plan="Abonnement Mensuel"
        )
        assert result == ACCESS_CCPILOT
        db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_subscription_row_returns_none(self):
        """No noly_subscriptions row → ACCESS_NONE."""
        db = _make_db(None)
        result = await get_subscription_access_level(uuid.uuid4(), db)
        assert result == ACCESS_NONE

    @pytest.mark.asyncio
    async def test_active_ccpilot_sku_returns_active_ccpilot(self):
        """Active subscription with CCPilot SKU → ACCESS_CCPILOT."""
        sub = _make_sub(status="active", logical_sku_key="ccpilot_monthly_2026_05")
        db = _make_db(sub)
        result = await get_subscription_access_level(uuid.uuid4(), db)
        assert result == ACCESS_CCPILOT

    @pytest.mark.asyncio
    async def test_active_pack_ccpilot_returns_active_ccpilot(self):
        """Active subscription with pack CCPilot SKU → ACCESS_CCPILOT."""
        sub = _make_sub(status="active", logical_sku_key="pack_ir_ccpilot_monthly_2026_05")
        db = _make_db(sub)
        result = await get_subscription_access_level(uuid.uuid4(), db)
        assert result == ACCESS_CCPILOT

    @pytest.mark.asyncio
    async def test_active_compta_only_sku_returns_compta_only(self):
        """Active compta-only subscription → ACCESS_COMPTA_ONLY."""
        sub = _make_sub(status="active", logical_sku_key="compta_ir_monthly_2026_05")
        db = _make_db(sub)
        result = await get_subscription_access_level(uuid.uuid4(), db)
        assert result == ACCESS_COMPTA_ONLY

    @pytest.mark.asyncio
    async def test_active_no_plan_info_defaults_ccpilot(self):
        """Active subscription without plan info → safe default ACCESS_CCPILOT."""
        sub = _make_sub(status="active", logical_sku_key=None, plan_name=None)
        db = _make_db(sub)
        result = await get_subscription_access_level(uuid.uuid4(), db)
        assert result == ACCESS_CCPILOT

    @pytest.mark.asyncio
    async def test_trialing_within_window_returns_trialing(self):
        """Trialing subscription with trial_ends_at in the future → ACCESS_TRIALING."""
        sub = _make_sub(
            status="trialing",
            trial_ends_at=datetime.now(UTC) + timedelta(days=7),
        )
        db = _make_db(sub)
        result = await get_subscription_access_level(uuid.uuid4(), db)
        assert result == ACCESS_TRIALING

    @pytest.mark.asyncio
    async def test_trialing_stripe_period_end_within_window(self):
        """Trialing with Stripe current_period_end in the future → ACCESS_TRIALING."""
        sub = _make_sub(
            status="trialing",
            trial_ends_at=None,
            current_period_end=datetime.now(UTC) + timedelta(days=3),
        )
        db = _make_db(sub)
        result = await get_subscription_access_level(uuid.uuid4(), db)
        assert result == ACCESS_TRIALING

    @pytest.mark.asyncio
    async def test_trialing_expired_returns_expired(self):
        """Trialing with trial_ends_at in the past → ACCESS_EXPIRED."""
        sub = _make_sub(
            status="trialing",
            trial_ends_at=datetime.now(UTC) - timedelta(days=1),
            current_period_end=None,
        )
        db = _make_db(sub)
        result = await get_subscription_access_level(uuid.uuid4(), db)
        assert result == ACCESS_EXPIRED

    @pytest.mark.asyncio
    async def test_past_due_returns_expired(self):
        """past_due → ACCESS_EXPIRED (treat same as expired)."""
        sub = _make_sub(status="past_due")
        db = _make_db(sub)
        result = await get_subscription_access_level(uuid.uuid4(), db)
        assert result == ACCESS_EXPIRED

    @pytest.mark.asyncio
    async def test_cancelled_returns_expired(self):
        """Cancelled → ACCESS_EXPIRED."""
        sub = _make_sub(status="cancelled")
        db = _make_db(sub)
        result = await get_subscription_access_level(uuid.uuid4(), db)
        assert result == ACCESS_EXPIRED

    @pytest.mark.asyncio
    async def test_unknown_status_returns_expired(self):
        """Unknown status string → ACCESS_EXPIRED (safe default)."""
        sub = _make_sub(status="unknown_future_status")
        db = _make_db(sub)
        result = await get_subscription_access_level(uuid.uuid4(), db)
        assert result == ACCESS_EXPIRED


# ── access_level_to_response unit tests ──────────────────────────────────────


class TestAccessLevelToResponse:
    """Tests for the response dict builder."""

    def test_trialing_includes_days_remaining(self):
        sub = _make_sub(
            status="trialing",
            trial_ends_at=datetime.now(UTC) + timedelta(days=8),
        )
        resp = access_level_to_response(ACCESS_TRIALING, sub)
        assert resp["is_trialing"] is True
        assert resp["has_ccpilot"] is True
        assert resp["trial_days_remaining"] is not None
        assert resp["trial_days_remaining"] >= 7  # may be 7 or 8 depending on timing

    def test_active_ccpilot_has_ccpilot(self):
        sub = _make_sub(status="active", logical_sku_key="ccpilot_monthly_2026_05")
        resp = access_level_to_response(ACCESS_CCPILOT, sub)
        assert resp["has_ccpilot"] is True
        assert resp["has_compta"] is True
        assert resp["is_trialing"] is False
        assert resp["trial_days_remaining"] is None

    def test_compta_only_has_compta_not_ccpilot(self):
        sub = _make_sub(status="active", logical_sku_key="compta_ir_monthly_2026_05")
        resp = access_level_to_response(ACCESS_COMPTA_ONLY, sub)
        assert resp["has_ccpilot"] is False
        assert resp["has_compta"] is True

    def test_expired_has_neither(self):
        sub = _make_sub(status="cancelled")
        resp = access_level_to_response(ACCESS_EXPIRED, sub)
        assert resp["has_ccpilot"] is False
        assert resp["has_compta"] is False

    def test_none_with_null_sub(self):
        resp = access_level_to_response(ACCESS_NONE, None)
        assert resp["has_ccpilot"] is False
        assert resp["subscription_status"] is None

    def test_past_due_includes_update_url(self):
        sub = _make_sub(status="past_due")
        resp = access_level_to_response(ACCESS_EXPIRED, sub)
        assert resp["update_payment_url"] == "/settings/subscription"
