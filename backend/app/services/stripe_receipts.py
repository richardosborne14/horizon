"""
Stripe receipt URL service (TASK-2.13.5).

Stripe receipt_url values are permanent (no expiry), so the primary path is:
  1. Submission has stripe_receipt_url already → use it directly.
  2. Submission has no receipt_url (pre-2.13.5 submissions) → fetch from Stripe,
     persist to DB, then redirect.

In-process cache (TTL = 1h):
  Maps stripe_payment_intent_id → receipt_url to avoid repeated Stripe API calls
  when the user hits the receipt endpoint multiple times in the same session.
  Single backend instance — this is pragmatically fine for our scale.
  If we ever scale to multiple pods, swap for Redis (document as Sprint-3+).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any

import stripe
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.stripe_per_submission import _init_stripe

logger = logging.getLogger(__name__)

# ── In-process cache ──────────────────────────────────────────────────────────
# Dict maps stripe_payment_intent_id → (receipt_url, expires_at)
_receipt_cache: dict[str, tuple[str, datetime]] = {}
_CACHE_TTL = timedelta(hours=1)


def _cache_get(intent_id: str) -> str | None:
    """
    Retrieve a cached receipt URL for a given PaymentIntent ID.

    Returns None if not cached or if the cached entry has expired.

    Args:
        intent_id: Stripe PaymentIntent ID.

    Returns:
        Cached receipt URL or None.
    """
    entry = _receipt_cache.get(intent_id)
    if entry is None:
        return None
    url, expires_at = entry
    if datetime.now(UTC) > expires_at:
        del _receipt_cache[intent_id]
        return None
    return url


def _cache_set(intent_id: str, url: str) -> None:
    """
    Cache a receipt URL for a given PaymentIntent ID with a 1-hour TTL.

    Args:
        intent_id: Stripe PaymentIntent ID.
        url:       Stripe receipt URL.
    """
    _receipt_cache[intent_id] = (url, datetime.now(UTC) + _CACHE_TTL)


# ── Stripe fetch helper ───────────────────────────────────────────────────────


async def _fetch_receipt_url_from_stripe(intent_id: str) -> str | None:
    """
    Retrieve the receipt URL for a PaymentIntent from the Stripe API.

    Expands the latest_charge to access charge.receipt_url.
    Runs in a thread pool executor (Stripe SDK is sync).

    Args:
        intent_id: Stripe PaymentIntent ID.

    Returns:
        Receipt URL string, or None if unavailable.
    """
    _init_stripe()
    loop = asyncio.get_event_loop()
    try:
        pi: Any = await loop.run_in_executor(
            None,
            partial(stripe.PaymentIntent.retrieve, intent_id, expand=["latest_charge"]),
        )
        charge = getattr(pi, "latest_charge", None)
        if charge:
            return getattr(charge, "receipt_url", None)
    except Exception as exc:
        logger.warning("stripe_receipts: failed to fetch PI %s from Stripe: %s", intent_id, exc)
    return None


# ── Public API ────────────────────────────────────────────────────────────────


async def get_receipt_url(
    submission_or_contrat: Any,
    db: AsyncSession,
) -> str | None:
    """
    Get the Stripe receipt URL for a submission or contrat request.

    Strategy:
      1. If the row already has stripe_receipt_url → return it directly.
      2. If the row has a stripe_payment_intent_id:
         a. Check the in-process cache.
         b. If not cached, fetch from Stripe API, cache + persist to DB.
      3. If no payment_intent_id → return None (draft/unconfirmed state).

    Args:
        submission_or_contrat: PayslipSubmission or ContratRequest ORM instance.
        db:                    Async DB session (used to persist newly fetched URL).

    Returns:
        Receipt URL string or None.
    """
    # Step 1: already persisted
    if submission_or_contrat.stripe_receipt_url:
        return submission_or_contrat.stripe_receipt_url

    intent_id = submission_or_contrat.stripe_payment_intent_id
    if not intent_id:
        return None

    # Step 2a: check cache
    cached = _cache_get(intent_id)
    if cached:
        # Persist opportunistically so future requests don't hit the cache/Stripe
        try:
            submission_or_contrat.stripe_receipt_url = cached
            await db.commit()
        except Exception as exc:
            logger.debug("stripe_receipts: opportunistic persist failed (non-fatal): %s", exc)
        return cached

    # Step 2b: fetch from Stripe
    url = await _fetch_receipt_url_from_stripe(intent_id)
    if url:
        _cache_set(intent_id, url)
        # Persist to DB for future requests
        try:
            submission_or_contrat.stripe_receipt_url = url
            await db.commit()
            logger.info(
                "stripe_receipts: persisted receipt_url for intent=%s row=%s",
                intent_id,
                getattr(submission_or_contrat, "id", "?"),
            )
        except Exception as exc:
            logger.warning(
                "stripe_receipts: failed to persist receipt_url for intent=%s: %s",
                intent_id,
                exc,
            )

    return url
