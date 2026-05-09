"""
Stripe subscription SKU map for the 2026-05 pricing restructure.

Single source of truth: logical product key → Stripe Price ID.
Price IDs live in environment variables so each env (dev/staging/prod) can
reference its own Stripe account objects.

Usage pattern (TASK-2.16.4, checkout flow):
    from app.services.stripe_subscriptions import get_price_id
    price_id = get_price_id("ccpilot_monthly_2026_05")

See also:
    backend/scripts/stripe_seed_2026_05.py — creates the objects in Stripe
    TASK-2.16.1 — documents the product/price matrix
"""

from __future__ import annotations

from typing import Literal

from app.core.config import settings

# ---------------------------------------------------------------------------
# Product catalogue — human-readable metadata for each SKU.
# Amounts are in cents (EUR, HT / excluding TVA).
# ---------------------------------------------------------------------------

_CATALOGUE: dict[str, dict] = {
    "ccpilot_monthly_2026_05": {
        "name": "CCPilot Mensuel",
        "description": "Outils de pilotage Communauté Coiffure (mensuel)",
        "amount_ht_cents": 3200,       # 32,00 € HT
        "trial_days": 14,
        "metadata_kind": "ccpilot_monthly",
        "metadata_version": "2026-05",
    },
    "pack_bic_ccpilot_monthly_2026_05": {
        "name": "Pack BIC + CCPilot Mensuel",
        "description": "Compta BIC + outils de pilotage (mensuel)",
        "amount_ht_cents": 8900,       # 89,00 € HT
        "trial_days": 14,
        "metadata_kind": "pack_bic_ccpilot_monthly",
        "metadata_version": "2026-05",
    },
    "pack_bic_plus_ccpilot_monthly_2026_05": {
        "name": "Pack BIC+ + CCPilot Mensuel",
        "description": "Compta BIC+ + outils de pilotage (mensuel)",
        "amount_ht_cents": 11900,      # 119,00 € HT
        "trial_days": 14,
        "metadata_kind": "pack_bic_plus_ccpilot_monthly",
        "metadata_version": "2026-05",
    },
    # BIC+ standalone — 99 € HT/mois confirmed by Eric 2026-04-29.
    "pack_bic_plus_monthly_v2_2026_05": {
        "name": "Pack BIC+ Mensuel v2",
        "description": "Compta BIC+ engagement (mensuel) — version 2026-05",
        "amount_ht_cents": 9900,   # 99,00 € HT — confirmed 2026-04-29
        "trial_days": 14,
        "metadata_kind": "pack_bic_plus_monthly_v2",
        "metadata_version": "2026-05",
    },
}

# All valid logical keys
VALID_KEYS = frozenset(_CATALOGUE.keys())

# ---------------------------------------------------------------------------
# Price ID map — reads from environment.
# Price IDs are populated by running stripe_seed_2026_05.py in each env.
# ---------------------------------------------------------------------------

def _price_id_map() -> dict[str, str]:
    """
    Build the logical-key → Stripe Price ID mapping from environment variables.

    Returns an empty string for keys whose env var is not yet set (dev / before
    the seed script has been run).

    Returns:
        Mapping from logical key to Stripe Price ID string.
    """
    return {
        "ccpilot_monthly_2026_05": settings.stripe_price_ccpilot_monthly,
        "pack_bic_ccpilot_monthly_2026_05": settings.stripe_price_pack_bic_ccpilot_monthly,
        "pack_bic_plus_ccpilot_monthly_2026_05": settings.stripe_price_pack_bic_plus_ccpilot_monthly,
        "pack_bic_plus_monthly_v2_2026_05": settings.stripe_price_pack_bic_plus_monthly_v2,
    }


def get_price_id(key: str) -> str:
    """
    Return the Stripe Price ID for a given logical product key.

    Args:
        key: One of the logical keys defined in VALID_KEYS.

    Returns:
        Stripe Price ID string (e.g. "price_1Abc123…").

    Raises:
        ValueError: If the key is unknown.
        RuntimeError: If the env var for this key has not been set yet
            (i.e. the seed script has not been run or the env var is missing).
    """
    if key not in VALID_KEYS:
        raise ValueError(
            f"Unknown subscription product key {key!r}. "
            f"Valid keys: {sorted(VALID_KEYS)}"
        )
    price_map = _price_id_map()
    price_id = price_map.get(key, "")
    if not price_id:
        raise RuntimeError(
            f"Stripe Price ID for {key!r} is not configured. "
            f"Run stripe_seed_2026_05.py and set the corresponding "
            f"STRIPE_PRICE_* environment variable."
        )
    return price_id


def get_catalogue_entry(key: str) -> dict:
    """
    Return the product catalogue metadata for a given logical key.

    Args:
        key: One of the logical keys defined in VALID_KEYS.

    Returns:
        Dict with name, description, amount_ht_cents, trial_days, etc.

    Raises:
        ValueError: If the key is unknown.
    """
    if key not in VALID_KEYS:
        raise ValueError(
            f"Unknown subscription product key {key!r}. "
            f"Valid keys: {sorted(VALID_KEYS)}"
        )
    return _CATALOGUE[key].copy()
