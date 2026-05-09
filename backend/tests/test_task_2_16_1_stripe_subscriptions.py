"""
Tests for TASK-2.16.1 — Stripe subscription SKU map and seed script.

Coverage:
  - get_price_id() resolves from env when configured
  - get_price_id() raises RuntimeError when env var not set
  - get_price_id() raises ValueError for unknown keys
  - get_catalogue_entry() returns correct metadata
  - VALID_KEYS contains the expected 4 keys
  - seed script: dry-run makes no Stripe calls
  - seed script: second run (idempotent) creates no duplicates

All Stripe API calls are mocked — no real Stripe credentials needed.
"""

from __future__ import annotations

import sys
from io import StringIO
from unittest.mock import MagicMock, patch, call

import pytest

from app.services.stripe_subscriptions import (
    VALID_KEYS,
    get_catalogue_entry,
    get_price_id,
)


# ── get_price_id ─────────────────────────────────────────────────────────────


def test_price_id_resolves_when_env_var_set():
    """
    get_price_id() returns the configured Price ID when the env var is populated.
    """
    with patch(
        "app.services.stripe_subscriptions._price_id_map",
        return_value={
            "ccpilot_monthly_2026_05": "price_test_ccpilot_abc123",
            "pack_bic_ccpilot_monthly_2026_05": "price_test_bic_def456",
            "pack_bic_plus_ccpilot_monthly_2026_05": "price_test_bic_plus_ghi789",
            "pack_bic_plus_monthly_v2_2026_05": "price_test_bic_plus_v2_jkl012",
        },
    ):
        assert get_price_id("ccpilot_monthly_2026_05") == "price_test_ccpilot_abc123"
        assert get_price_id("pack_bic_ccpilot_monthly_2026_05") == "price_test_bic_def456"
        assert get_price_id("pack_bic_plus_ccpilot_monthly_2026_05") == "price_test_bic_plus_ghi789"


def test_price_id_raises_runtime_error_when_not_configured():
    """
    get_price_id() raises RuntimeError when the env var is empty (seed not run yet).
    """
    with patch(
        "app.services.stripe_subscriptions._price_id_map",
        return_value={
            "ccpilot_monthly_2026_05": "",
            "pack_bic_ccpilot_monthly_2026_05": "",
            "pack_bic_plus_ccpilot_monthly_2026_05": "",
            "pack_bic_plus_monthly_v2_2026_05": "",
        },
    ):
        with pytest.raises(RuntimeError, match="not configured"):
            get_price_id("ccpilot_monthly_2026_05")


def test_price_id_raises_value_error_for_unknown_key():
    """
    get_price_id() raises ValueError for an unrecognised logical key.
    """
    with pytest.raises(ValueError, match="Unknown subscription product key"):
        get_price_id("not_a_real_product_2026_05")


# ── VALID_KEYS ────────────────────────────────────────────────────────────────


def test_valid_keys_contains_expected_products():
    """
    VALID_KEYS contains exactly the 4 expected logical keys.
    """
    expected = {
        "ccpilot_monthly_2026_05",
        "pack_bic_ccpilot_monthly_2026_05",
        "pack_bic_plus_ccpilot_monthly_2026_05",
        "pack_bic_plus_monthly_v2_2026_05",
    }
    assert VALID_KEYS == expected


# ── get_catalogue_entry ───────────────────────────────────────────────────────


def test_catalogue_entry_ccpilot_monthly():
    """
    CCPilot monthly entry has correct amount (32 € = 3200 cents) and 14-day trial.
    """
    entry = get_catalogue_entry("ccpilot_monthly_2026_05")
    assert entry["amount_ht_cents"] == 3200
    assert entry["trial_days"] == 14
    assert entry["metadata_version"] == "2026-05"
    assert entry["metadata_kind"] == "ccpilot_monthly"


def test_catalogue_entry_pack_bic_ccpilot():
    """
    Pack BIC + CCPilot entry has amount 89 € = 8900 cents.
    """
    entry = get_catalogue_entry("pack_bic_ccpilot_monthly_2026_05")
    assert entry["amount_ht_cents"] == 8900


def test_catalogue_entry_pack_bic_plus_ccpilot():
    """
    Pack BIC+ + CCPilot entry has amount 119 € = 11900 cents.
    """
    entry = get_catalogue_entry("pack_bic_plus_ccpilot_monthly_2026_05")
    assert entry["amount_ht_cents"] == 11900


def test_catalogue_entry_bic_plus_v2():
    """
    Pack BIC+ v2 standalone entry has amount 99 € = 9900 cents (confirmed Eric 2026-04-29).
    """
    entry = get_catalogue_entry("pack_bic_plus_monthly_v2_2026_05")
    assert entry["amount_ht_cents"] == 9900


def test_catalogue_entry_raises_for_unknown_key():
    """
    get_catalogue_entry() raises ValueError for an unknown key.
    """
    with pytest.raises(ValueError, match="Unknown subscription product key"):
        get_catalogue_entry("ghost_product_2026_05")


def test_catalogue_entry_returns_copy():
    """
    get_catalogue_entry() returns a copy so mutation doesn't affect the module dict.
    """
    entry = get_catalogue_entry("ccpilot_monthly_2026_05")
    entry["amount_ht_cents"] = 9999
    # Fetch again — original value unchanged
    fresh = get_catalogue_entry("ccpilot_monthly_2026_05")
    assert fresh["amount_ht_cents"] == 3200


# ── seed script ───────────────────────────────────────────────────────────────


def test_seed_script_dry_run_does_not_call_stripe(capsys):
    """
    --dry-run flag outputs the plan to stdout without importing or calling stripe.
    """
    # Import the private function directly
    from scripts.stripe_seed_2026_05 import _run_seed  # type: ignore[import]

    # No stripe module should be imported/called in dry-run mode
    with patch.dict("sys.modules", {"stripe": None}):
        _run_seed(dry_run=True)

    captured = capsys.readouterr()
    assert "DRY RUN" in captured.out
    assert "CCPilot Mensuel" in captured.out
    assert "32.00 € HT" in captured.out
    assert "14-day" in captured.out.lower() or "14" in captured.out


def test_seed_script_is_idempotent():
    """
    Calling _run_seed twice with the same Stripe state creates no duplicates.
    On the second call, all Products and Prices already exist — no creates called.
    """
    from scripts.stripe_seed_2026_05 import _run_seed  # type: ignore[import]

    # Build a fake stripe module
    fake_stripe = MagicMock()

    # Simulate existing product and price on second call
    fake_product = MagicMock()
    fake_product.__getitem__ = lambda self, k: "prod_existing_123" if k == "id" else None
    fake_product.get = lambda k, d=None: {"kind": "ccpilot_monthly", "version": "2026-05"}.get(k, d)

    fake_price_obj = MagicMock()
    fake_price_obj.get = lambda k, d=None: {
        "unit_amount": 3200,
        "currency": "eur",
    }.get(k, d)
    fake_price_obj.__getitem__ = lambda self, k: "price_existing_456" if k == "id" else None

    # Product.list returns one existing product
    fake_product_list = MagicMock()
    fake_product_list.auto_paging_iter.return_value = iter([fake_product])
    fake_stripe.Product.list.return_value = fake_product_list

    # Price.list returns one existing price
    fake_price_list = MagicMock()
    fake_price_list.data = [fake_price_obj]
    fake_stripe.Price.list.return_value = fake_price_list

    with patch.dict("sys.modules", {"stripe": fake_stripe}):
        with patch("os.environ.get", return_value="sk_test_fake"):
            with patch(
                "scripts.stripe_seed_2026_05._find_existing_product",
                return_value="prod_existing_123",
            ):
                with patch(
                    "scripts.stripe_seed_2026_05._find_existing_price",
                    return_value="price_existing_456",
                ):
                    _run_seed(dry_run=False)

    # No new products or prices created on second run
    fake_stripe.Product.create.assert_not_called()
    fake_stripe.Price.create.assert_not_called()
