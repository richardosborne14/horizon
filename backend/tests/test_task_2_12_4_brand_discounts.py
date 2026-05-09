"""
Tests for TASK-2.12.4: Per-brand product discount configuration.

Covers:
  1. Per-brand pct applied correctly (L'Oréal 12%, Wella 8%) — unit test
  2. Missing brand falls back to PRODUCTS_DEFAULT_DISCOUNT_PCT (10%) — unit test
  3. Two brands with independent pcts — unit test
  4. already_customer flag sets is_paid_customer=True — unit test
  5. Admin GET /api/admin/config — returns all known keys
  6. Admin PATCH /api/admin/config/{key} — persists updated JSONB
  7. Non-admin gets 403 on both endpoints
  8. 404 on PATCH for non-existent key
  9. Unauthenticated gets 401 or 403

Test patterns:
  - LEARNINGS #27: every test is self-contained (register → login → test)
  - LEARNINGS #26: run inside Docker (from app.* imports work correctly)
  - Unit tests mock the DB to inject controlled admin_cfg and brand rows
"""

import uuid
import pytest
from decimal import Decimal
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from sqlalchemy import select

from app.main import app
from app.services.savings_engine import (
    _channel_produits,
    AC_PRODUCTS_BY_BRAND,
    AC_PRODUCTS_DEFAULT_DISCOUNT,
    AC_PRODUCTS_MIN_SPEND,
)

# ── Config key under test ─────────────────────────────────────────────────────

BRAND_DISCOUNTS_KEY = "PRODUCTS_DISCOUNT_PCT_BY_BRAND"


# ── Test helpers ──────────────────────────────────────────────────────────────


def _make_brand_row(brand: str, total_ht: float) -> MagicMock:
    """
    Return a MagicMock that mimics a SQLAlchemy BrandPurchase aggregate row.

    Args:
        brand:    Brand key string (e.g. 'loreal', 'wella').
        total_ht: Total HT spend for this brand over 12 months.

    Returns:
        MagicMock with .brand and .total_ht attributes.
    """
    row = MagicMock()
    row.brand = brand
    row.total_ht = total_ht
    return row


def _mock_db_with_rows(rows: list) -> AsyncMock:
    """
    Return an AsyncMock DB session whose execute() returns the given rows.

    Args:
        rows: List of MagicMock aggregate rows to return from .all().

    Returns:
        AsyncMock mimicking an SQLAlchemy async session.
    """
    execute_result = MagicMock()
    execute_result.all.return_value = rows

    db = AsyncMock()
    db.execute.return_value = execute_result
    return db


@asynccontextmanager
async def _admin_client():
    """
    Register a fresh admin user, upgrade their role to 'admin' via DB, login.

    WHY direct DB write: There is no /api/admin/promote endpoint. Admin role is
    assigned by the operator (in production: manually). Tests simulate this by
    writing directly to the DB via AsyncSessionLocal.

    Yields:
        Authenticated httpx.AsyncClient with admin session cookie.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.user import User as UserModel

    email = f"admin-2124-{uuid.uuid4().hex[:8]}@test.comcoi.fr"
    password = "AdminTest1234!"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/auth/register", json={
            "email": email,
            "password": password,
            "name": "Admin Test 2124",
        })
        assert r.status_code == 201, f"Register failed: {r.text}"

        # Promote to admin directly in DB — no API endpoint for this.
        # WHY by email not by id: the register endpoint does not return 'id'
        # in its response body, but email is unique and known at registration time.
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(UserModel).where(UserModel.email == email))
            user = result.scalar_one_or_none()
            assert user is not None, f"User {email!r} not found in DB after register"
            user.role = "admin"
            await db.commit()

        r = await client.post("/api/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, f"Login after promotion failed: {r.text}"
        client.cookies.update(r.cookies)
        yield client


@asynccontextmanager
async def _regular_client():
    """
    Register a fresh regular user and login.

    Yields:
        Authenticated httpx.AsyncClient with user (non-admin) session cookie.
    """
    email = f"user-2124-{uuid.uuid4().hex[:8]}@test.comcoi.fr"
    password = "UserTest1234!"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/auth/register", json={
            "email": email,
            "password": password,
            "name": "User Test 2124",
        })
        assert r.status_code == 201, f"Register failed: {r.text}"
        r = await client.post("/api/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, f"Login failed: {r.text}"
        client.cookies.update(r.cookies)
        yield client


# ── Unit tests: savings engine per-brand discount logic ───────────────────────


class TestPerBrandDiscountCalculation:
    """
    Unit tests for _channel_produits — the per-brand savings channel calculator.

    All DB I/O is mocked so these tests run in-process without a DB connection.
    """

    @pytest.mark.asyncio
    async def test_specific_brand_pct_overrides_default(self):
        """
        L'Oréal configured at 12% in by_brand map → savings = spend × 0.12.

        Verifies that the per-brand override takes priority over the default 10%.
        """
        db = _mock_db_with_rows([_make_brand_row("loreal", 12000)])

        admin_cfg = {
            AC_PRODUCTS_MIN_SPEND: 3000,
            AC_PRODUCTS_DEFAULT_DISCOUNT: 0.10,
            AC_PRODUCTS_BY_BRAND: {"loreal": 0.12},
        }

        channels = await _channel_produits(
            salon_id="unit-test-salon",
            admin_cfg=admin_cfg,
            paid_channels=set(),
            db=db,
        )

        assert len(channels) == 1, "Expected exactly one brand channel row"
        ch = channels[0]
        assert ch.channel_key == "produits:loreal"
        expected = (Decimal("12000") * Decimal("0.12")).quantize(Decimal("0.01"))
        assert ch.annual_savings_eur == expected, (
            f"Expected savings {expected}, got {ch.annual_savings_eur}"
        )

    @pytest.mark.asyncio
    async def test_missing_brand_falls_back_to_default_10pct(self):
        """
        Wella not in by_brand map → uses PRODUCTS_DEFAULT_DISCOUNT_PCT (10%).

        The fallback ensures any unlisted brand still gets a savings estimate.
        """
        db = _mock_db_with_rows([_make_brand_row("wella", 8000)])

        admin_cfg = {
            AC_PRODUCTS_MIN_SPEND: 3000,
            AC_PRODUCTS_DEFAULT_DISCOUNT: 0.10,
            AC_PRODUCTS_BY_BRAND: {},  # no wella override → falls back to default
        }

        channels = await _channel_produits(
            salon_id="unit-test-salon",
            admin_cfg=admin_cfg,
            paid_channels=set(),
            db=db,
        )

        assert len(channels) == 1
        ch = channels[0]
        assert ch.channel_key == "produits:wella"
        expected = (Decimal("8000") * Decimal("0.10")).quantize(Decimal("0.01"))
        assert ch.annual_savings_eur == expected

    @pytest.mark.asyncio
    async def test_two_brands_with_different_pcts(self):
        """
        L'Oréal 12% + Wella 8% → two independent channel rows with correct savings.

        Each brand's savings is computed independently. Total should equal
        loreal_savings + wella_savings.
        """
        db = _mock_db_with_rows([
            _make_brand_row("loreal", 12000),
            _make_brand_row("wella", 6000),
        ])

        admin_cfg = {
            AC_PRODUCTS_MIN_SPEND: 3000,
            AC_PRODUCTS_DEFAULT_DISCOUNT: 0.10,
            AC_PRODUCTS_BY_BRAND: {"loreal": 0.12, "wella": 0.08},
        }

        channels = await _channel_produits(
            salon_id="unit-test-salon",
            admin_cfg=admin_cfg,
            paid_channels=set(),
            db=db,
        )

        assert len(channels) == 2, "Expected one channel row per qualifying brand"

        loreal_ch = next((c for c in channels if c.channel_key == "produits:loreal"), None)
        wella_ch = next((c for c in channels if c.channel_key == "produits:wella"), None)

        assert loreal_ch is not None, "No L'Oréal channel in result"
        assert wella_ch is not None, "No Wella channel in result"

        assert loreal_ch.annual_savings_eur == (
            Decimal("12000") * Decimal("0.12")
        ).quantize(Decimal("0.01"))
        assert wella_ch.annual_savings_eur == (
            Decimal("6000") * Decimal("0.08")
        ).quantize(Decimal("0.01"))

    @pytest.mark.asyncio
    async def test_already_customer_flag_marks_channel(self):
        """
        When paid_customer_flags contains 'produits:loreal', the channel has
        is_paid_customer=True. Savings are still computed (the UI shows
        'already customer' state rather than suppressing the number).
        """
        db = _mock_db_with_rows([_make_brand_row("loreal", 12000)])

        admin_cfg = {
            AC_PRODUCTS_MIN_SPEND: 3000,
            AC_PRODUCTS_DEFAULT_DISCOUNT: 0.10,
            AC_PRODUCTS_BY_BRAND: {"loreal": 0.12},
        }
        paid_channels = {"produits:loreal"}

        channels = await _channel_produits(
            salon_id="unit-test-salon",
            admin_cfg=admin_cfg,
            paid_channels=paid_channels,
            db=db,
        )

        assert len(channels) == 1
        ch = channels[0]
        assert ch.is_paid_customer is True, "Expected is_paid_customer=True for flagged brand"

    @pytest.mark.asyncio
    async def test_brand_below_min_spend_excluded(self):
        """
        Brand with spend below PRODUCTS_SAVINGS_MIN_SPEND_EUR is not shown as
        a per-brand channel — returns the fallback 'produits' row instead.
        """
        db = _mock_db_with_rows([_make_brand_row("loreal", 1000)])  # below 3000 threshold

        admin_cfg = {
            AC_PRODUCTS_MIN_SPEND: 3000,
            AC_PRODUCTS_DEFAULT_DISCOUNT: 0.10,
            AC_PRODUCTS_BY_BRAND: {},
        }

        channels = await _channel_produits(
            salon_id="unit-test-salon",
            admin_cfg=admin_cfg,
            paid_channels=set(),
            db=db,
        )

        # Below threshold → fallback aggregated row
        assert len(channels) == 1
        ch = channels[0]
        assert ch.channel_key == "produits", (
            f"Expected fallback 'produits' channel, got '{ch.channel_key}'"
        )
        # Fallback row has no savings figure
        assert ch.annual_savings_eur is None


# ── Integration tests: admin_config API ──────────────────────────────────────


class TestAdminConfigAPI:
    """
    Integration tests for GET/PATCH /api/admin/config.

    Each test registers a fresh admin or regular user (self-contained per
    LEARNINGS #27). Admin promotion is done via direct DB write (no promote API).
    """

    @pytest.mark.asyncio
    async def test_admin_can_list_all_config_keys(self):
        """GET /api/admin/config returns a list containing seeded config keys."""
        async with _admin_client() as client:
            r = await client.get("/api/admin/config")
            assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
            data = r.json()
            assert isinstance(data, list), "Expected a list of config rows"
            keys = {item["key"] for item in data}
            assert "PRODUCTS_DEFAULT_DISCOUNT_PCT" in keys
            assert "PRODUCTS_DISCOUNT_PCT_BY_BRAND" in keys
            assert "COMCOI_PAYSLIP_UNIT_PRICE_HT_EUR" in keys

    @pytest.mark.asyncio
    async def test_admin_can_update_brand_discounts(self):
        """
        PATCH /api/admin/config/PRODUCTS_DISCOUNT_PCT_BY_BRAND persists new JSONB.

        Also verifies that GET reflects the change immediately after PATCH,
        and cleans up by resetting to empty dict.
        """
        new_discounts = {"loreal": 0.12, "wella": 0.08}

        async with _admin_client() as client:
            # Read current value first
            r_before = await client.get("/api/admin/config")
            assert r_before.status_code == 200
            before_val = next(
                (item["value"] for item in r_before.json() if item["key"] == BRAND_DISCOUNTS_KEY),
                None,
            )

            # Apply update
            r = await client.patch(
                f"/api/admin/config/{BRAND_DISCOUNTS_KEY}",
                json={"value": new_discounts},
            )
            assert r.status_code == 200, f"PATCH failed: {r.text}"
            data = r.json()
            assert data["key"] == BRAND_DISCOUNTS_KEY
            assert data["value"] == new_discounts

            # Verify GET reflects the change
            r2 = await client.get("/api/admin/config")
            assert r2.status_code == 200
            found = next(
                (item for item in r2.json() if item["key"] == BRAND_DISCOUNTS_KEY),
                None,
            )
            assert found is not None
            assert found["value"] == new_discounts

            # Cleanup: restore original value (so other tests aren't affected)
            await client.patch(
                f"/api/admin/config/{BRAND_DISCOUNTS_KEY}",
                json={"value": before_val or {}},
            )

    @pytest.mark.asyncio
    async def test_patch_nonexistent_key_returns_404(self):
        """
        PATCH on a key that was never seeded returns 404.
        Prevents admin UI from silently creating orphan keys.
        """
        async with _admin_client() as client:
            r = await client.patch(
                "/api/admin/config/NONEXISTENT_KEY_XYZ_2124",
                json={"value": 42},
            )
            assert r.status_code == 404, f"Expected 404, got {r.status_code}"

    @pytest.mark.asyncio
    async def test_non_admin_gets_403_on_list(self):
        """Regular user cannot list admin config — 403."""
        async with _regular_client() as client:
            r = await client.get("/api/admin/config")
            assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_non_admin_gets_403_on_patch(self):
        """Regular user cannot update admin config — 403."""
        async with _regular_client() as client:
            r = await client.patch(
                f"/api/admin/config/{BRAND_DISCOUNTS_KEY}",
                json={"value": {"loreal": 0.99}},
            )
            assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_gets_401_or_403(self):
        """No session cookie → cannot access admin config."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get("/api/admin/config")
            assert r.status_code in (401, 403), (
                f"Expected 401 or 403 for unauthenticated request, got {r.status_code}"
            )
