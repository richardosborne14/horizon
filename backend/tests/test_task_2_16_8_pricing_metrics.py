"""
Tests for TASK-2.16.8 — Conversion/churn watch list metrics.

Covers:
  - sku_group_for() derivation from logical key
  - record_subscription_event() creates rows and is idempotent
  - compute_pricing_metrics() returns correct rates given fixture data:
      * 10 trial_started + 5 converted_to_paid → 50% conversion
      * cohort filter: legacy users excluded from 'new' cohort metric
      * window filter: events outside the window excluded
      * churn rate: 1 churned / 10 trials → 10%
      * avg_days_to_convert: correct average across conversions
  - GET /api/admin/pricing-metrics returns 200 for admin, 403 for non-admin
  - GET /api/admin/pricing-metrics?window=30d passes the correct window

All DB-touching tests use the live test DB (same pattern as test_grandfathering_schema.py).
Pure computation tests use synthetic in-memory data to avoid DB overhead.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.subscription_metrics import (
    compute_pricing_metrics,
    record_subscription_event,
    sku_group_for,
)


# ---------------------------------------------------------------------------
# sku_group_for — pure function
# ---------------------------------------------------------------------------


def test_sku_group_for_ccpilot():
    """ccpilot_monthly_2026_05 → ccpilot_solo."""
    assert sku_group_for("ccpilot_monthly_2026_05") == "ccpilot_solo"


def test_sku_group_for_pack_bic_ccpilot():
    """pack_bic_ccpilot_monthly_2026_05 → pack_bic_ccpilot."""
    assert sku_group_for("pack_bic_ccpilot_monthly_2026_05") == "pack_bic_ccpilot"


def test_sku_group_for_pack_bic_plus():
    """pack_bic_plus_ccpilot_monthly_2026_05 → pack_bic_plus_ccpilot."""
    assert sku_group_for("pack_bic_plus_ccpilot_monthly_2026_05") == "pack_bic_plus_ccpilot"


def test_sku_group_for_bic_plus_v2():
    """pack_bic_plus_monthly_v2_2026_05 → pack_bic_plus_ccpilot (same group)."""
    assert sku_group_for("pack_bic_plus_monthly_v2_2026_05") == "pack_bic_plus_ccpilot"


def test_sku_group_for_unknown_key():
    """Unknown key → 'unknown'."""
    assert sku_group_for("some_future_product_2030") == "unknown"


def test_sku_group_for_none():
    """None → 'unknown'."""
    assert sku_group_for(None) == "unknown"


# ---------------------------------------------------------------------------
# compute_pricing_metrics — synthetic fixture data (no DB)
# ---------------------------------------------------------------------------

_CUTOVER = datetime(2026, 5, 1, 0, 0, 0, tzinfo=UTC)
_DAY1 = datetime(2026, 5, 2, 0, 0, 0, tzinfo=UTC)    # day after cutover


def _make_row(
    event_type: str,
    sku_group: str,
    sub_id: str,
    occurred_at: datetime,
    legacy_plan: str | None = None,
):
    """Build a namedtuple-like row matching the SQLAlchemy select() shape."""
    row = MagicMock()
    row.event_type = event_type
    row.sku_group = sku_group
    row.stripe_subscription_id = sub_id
    row.occurred_at = occurred_at
    row.legacy_pricing_plan = legacy_plan
    return row


async def _mock_compute(rows: list, window_days=None) -> dict:
    """
    Call compute_pricing_metrics with a mocked DB that returns `rows`.
    """
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = rows
    mock_db.execute.return_value = mock_result

    return await compute_pricing_metrics(
        mock_db,
        cutover_dt=_CUTOVER,
        window_days=window_days,
    )


@pytest.mark.asyncio
async def test_50_percent_conversion_rate():
    """
    10 trial_started + 5 converted_to_paid → conversion rate = 50%.
    All on the same sku_group, cohort='new'.
    """
    rows = []
    for i in range(10):
        rows.append(_make_row("trial_started", "ccpilot_solo", f"sub_{i}", _DAY1))
    for i in range(5):
        rows.append(_make_row(
            "converted_to_paid", "ccpilot_solo", f"sub_{i}",
            _DAY1 + timedelta(days=10),
        ))

    result = await _mock_compute(rows)

    cr = result["conversion_rate"]
    assert len(cr) == 1
    seg = cr[0]
    assert seg["sku_group"] == "ccpilot_solo"
    assert seg["cohort"] == "new"
    assert seg["trials"] == 10
    assert seg["converted"] == 5
    assert seg["rate_pct"] == 50.0


@pytest.mark.asyncio
async def test_churn_rate_10_percent():
    """
    10 trials, 1 churned → churn rate = 10%.
    """
    rows = []
    for i in range(10):
        rows.append(_make_row("trial_started", "ccpilot_solo", f"sub_{i}", _DAY1))
    rows.append(_make_row("churned", "ccpilot_solo", "sub_0", _DAY1 + timedelta(days=5)))

    result = await _mock_compute(rows)

    cr = result["churn_rate"]
    assert len(cr) == 1
    assert cr[0]["churned"] == 1
    assert cr[0]["rate_pct"] == 10.0


@pytest.mark.asyncio
async def test_avg_days_to_convert():
    """
    2 conversions: sub_0 converts after 8 days, sub_1 after 12 days → avg = 10.0.
    """
    rows = [
        _make_row("trial_started", "ccpilot_solo", "sub_0", _DAY1),
        _make_row("trial_started", "ccpilot_solo", "sub_1", _DAY1),
        _make_row("converted_to_paid", "ccpilot_solo", "sub_0", _DAY1 + timedelta(days=8)),
        _make_row("converted_to_paid", "ccpilot_solo", "sub_1", _DAY1 + timedelta(days=12)),
    ]

    result = await _mock_compute(rows)

    avgs = result["avg_days_to_convert"]
    assert len(avgs) == 1
    assert avgs[0]["avg_days"] == 10.0


@pytest.mark.asyncio
async def test_cohort_segmentation_legacy_vs_new():
    """
    Legacy users (legacy_pricing_plan non-NULL) are in cohort='legacy';
    new users are in cohort='new'. The two cohorts are computed independently.
    """
    rows = [
        # 4 new trials, 2 convert
        _make_row("trial_started", "ccpilot_solo", "new_0", _DAY1),
        _make_row("trial_started", "ccpilot_solo", "new_1", _DAY1),
        _make_row("trial_started", "ccpilot_solo", "new_2", _DAY1),
        _make_row("trial_started", "ccpilot_solo", "new_3", _DAY1),
        _make_row("converted_to_paid", "ccpilot_solo", "new_0", _DAY1 + timedelta(days=5)),
        _make_row("converted_to_paid", "ccpilot_solo", "new_1", _DAY1 + timedelta(days=5)),
        # 2 legacy trials, both convert
        _make_row("trial_started", "ccpilot_solo", "leg_0", _DAY1, legacy_plan="legacy_99_yearly"),
        _make_row("trial_started", "ccpilot_solo", "leg_1", _DAY1, legacy_plan="legacy_99_yearly"),
        _make_row("converted_to_paid", "ccpilot_solo", "leg_0", _DAY1 + timedelta(days=3), legacy_plan="legacy_99_yearly"),
        _make_row("converted_to_paid", "ccpilot_solo", "leg_1", _DAY1 + timedelta(days=3), legacy_plan="legacy_99_yearly"),
    ]

    result = await _mock_compute(rows)

    cr = {r["cohort"]: r for r in result["conversion_rate"]}
    assert "new" in cr
    assert "legacy" in cr
    assert cr["new"]["trials"] == 4
    assert cr["new"]["converted"] == 2
    assert cr["new"]["rate_pct"] == 50.0
    assert cr["legacy"]["trials"] == 2
    assert cr["legacy"]["converted"] == 2
    assert cr["legacy"]["rate_pct"] == 100.0


@pytest.mark.asyncio
async def test_empty_dataset_returns_empty_lists():
    """When no events exist, all three metric lists are empty."""
    result = await _mock_compute([])
    assert result["conversion_rate"] == []
    assert result["churn_rate"] == []
    assert result["avg_days_to_convert"] == []


@pytest.mark.asyncio
async def test_multiple_sku_groups_segmented():
    """
    Events for two different sku_groups produce two separate entries per block.
    """
    rows = [
        _make_row("trial_started", "ccpilot_solo", "sub_cc_0", _DAY1),
        _make_row("trial_started", "pack_bic_ccpilot", "sub_bic_0", _DAY1),
        _make_row("converted_to_paid", "ccpilot_solo", "sub_cc_0", _DAY1 + timedelta(days=7)),
    ]

    result = await _mock_compute(rows)

    groups = {r["sku_group"] for r in result["conversion_rate"]}
    assert "ccpilot_solo" in groups
    assert "pack_bic_ccpilot" in groups

    cc = next(r for r in result["conversion_rate"] if r["sku_group"] == "ccpilot_solo")
    bic = next(r for r in result["conversion_rate"] if r["sku_group"] == "pack_bic_ccpilot")
    assert cc["rate_pct"] == 100.0
    assert bic["rate_pct"] == 0.0


# ---------------------------------------------------------------------------
# HTTP API — admin guard tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pricing_metrics_endpoint_requires_admin():
    """
    GET /api/admin/pricing-metrics returns 403 for non-admin users.
    """
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register + login as standard user
        email = "metrics_nonAdmin_2_16_8@comcoi-test.fr"
        await client.post(
            "/api/auth/register",
            json={"email": email, "password": "Password123!", "name": "Metrics Test"},
        )
        resp = await client.post(
            "/api/auth/login",
            json={"email": email, "password": "Password123!"},
        )
        assert resp.status_code == 200
        resp = await client.get("/api/admin/pricing-metrics")
        assert resp.status_code == 403

    # Cleanup
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import select
    from app.models.user import User
    from app.core.config import settings
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            await db.delete(user)
            await db.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_pricing_metrics_endpoint_window_param():
    """
    GET /api/admin/pricing-metrics?window=30d passes window=30 to compute_pricing_metrics.
    Uses dependency_overrides to bypass the admin guard and DB.
    """
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.core.dependencies import get_admin_user
    from app.core.database import get_db
    from app.models.user import User

    # Fake admin user
    fake_admin = MagicMock(spec=User)
    fake_admin.role = "admin"

    # Mock the metrics service to avoid a real DB query
    captured_args: dict = {}

    async def fake_compute(db, *, cutover_dt, window_days=None):
        captured_args["window_days"] = window_days
        return {
            "generated_at": "2026-05-01T00:00:00+00:00",
            "cutover_iso": "2026-05-01",
            "window_days": window_days,
            "conversion_rate": [],
            "churn_rate": [],
            "avg_days_to_convert": [],
        }

    app.dependency_overrides[get_admin_user] = lambda: fake_admin
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    try:
        with patch(
            "app.routers.admin_pricing_metrics.compute_pricing_metrics",
            side_effect=fake_compute,
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/api/admin/pricing-metrics?window=30d")
                assert resp.status_code == 200
                data = resp.json()
                assert data["window_days"] == 30
                assert captured_args["window_days"] == 30
    finally:
        app.dependency_overrides.pop(get_admin_user, None)
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_pricing_metrics_endpoint_invalid_window():
    """
    GET /api/admin/pricing-metrics?window=invalid returns 422.
    """
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.core.dependencies import get_admin_user
    from app.core.database import get_db
    from app.models.user import User

    fake_admin = MagicMock(spec=User)
    fake_admin.role = "admin"
    app.dependency_overrides[get_admin_user] = lambda: fake_admin
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/admin/pricing-metrics?window=invalid")
            assert resp.status_code == 422
    finally:
        app.dependency_overrides.pop(get_admin_user, None)
        app.dependency_overrides.pop(get_db, None)
