"""
Stripe per-submission payment service (Sprint 2.13).

Implements the per-submission PaymentIntent model chosen by Richard (2026-04-24):
  - Each "Envoyer" or "Commander" click creates a Stripe PaymentIntent.
  - On webhook `payment_intent.succeeded`, we promote the DB rows and fire email.
  - No wallet, no top-ups, no subscription for payslips.

Architecture:
  - Stripe SDK is synchronous. We wrap calls with asyncio.get_event_loop().run_in_executor
    so they don't block the FastAPI event loop.
  - Webhook verification: skipped if STRIPE_WEBHOOK_SECRET is empty (dev mode).
    Set it via `stripe listen --forward-to localhost:47002/api/stripe/webhook`
    for local dev, or configure the Stripe Dashboard endpoint for production.
  - Idempotency: every webhook event ID is recorded in `stripe_events_processed`.
    Replaying the same event is a guaranteed no-op.

Pricing constants (locked — 24 × 1.20 = 28.80, never recomputed at runtime):
  Kind       | HT   | TTC    | Cents
  ---------- | ---- | ------ | -----
  payslip    | 24   | 28.80  | 2880
  dossier    | 85   | 102.00 | 10200
  contrat    | 50   | 60.00  | 6000
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from functools import partial
from typing import Any
from uuid import UUID

import stripe
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.payslip import (
    ContratRequest,
    PayslipDossier,
    PayslipSubmission,
    StripeEventProcessed,
)
from app.schemas.payslip import DisplayPrice

logger = logging.getLogger(__name__)

# ── Pricing table (locked — do NOT recompute dynamically) ─────────────────────

_PRICING: dict[str, dict[str, Any]] = {
    "payslip": {
        "ht_eur": Decimal("24.00"),
        "ttc_eur": Decimal("28.80"),
        "ttc_cents": 2880,
        "description": "Bulletin de salaire",
    },
    "dossier": {
        "ht_eur": Decimal("85.00"),
        "ttc_eur": Decimal("102.00"),
        "ttc_cents": 10200,
        "description": "Création dossier de paie",
    },
    "contrat": {
        "ht_eur": Decimal("50.00"),
        "ttc_eur": Decimal("60.00"),
        "ttc_cents": 6000,
        "description": "Contrat de travail",
    },
}

VALID_KINDS = frozenset(_PRICING.keys())

# Employee contract types eligible for payslip submissions.
# TNS and prestataire workers get their own payment flows outside this sprint.
ELIGIBLE_CONTRACT_TYPES = frozenset({"cdi", "cdd", "apprentissage", "assimile_salarie"})


# ── Stripe initialisation ─────────────────────────────────────────────────────


def _init_stripe() -> None:
    """
    Configure the Stripe SDK with the secret key from settings.

    Called lazily on first use. Logs a warning in dev if keys are not configured.
    """
    if not settings.stripe_secret_key:
        logger.warning(
            "STRIPE_SECRET_KEY is not set. Stripe calls will fail. "
            "Set it in .env for local dev."
        )
    stripe.api_key = settings.stripe_secret_key


# ── Helper: run Stripe (sync) call in thread pool ─────────────────────────────


async def _stripe_call(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """
    Run a synchronous Stripe SDK function in a thread pool executor.

    This prevents Stripe's blocking network calls from stalling the
    FastAPI async event loop.

    Args:
        fn:     The synchronous Stripe function (e.g. stripe.PaymentIntent.create).
        *args:  Positional args forwarded to fn.
        **kwargs: Keyword args forwarded to fn.

    Returns:
        The return value from fn.

    Raises:
        stripe.error.StripeError: Any Stripe API error is propagated as-is.
    """
    _init_stripe()
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(fn, *args, **kwargs))


# ── Promo code validation ─────────────────────────────────────────────────────


async def validate_promo_code(code: str) -> dict[str, Any]:
    """
    Validate a Stripe Promotion Code and return discount information.

    Calls the Stripe Promotion Codes API. No DB table required — codes are
    created and managed in the Stripe Dashboard by the admin.

    Args:
        code: Promotion code string entered by the user (case-insensitive in Stripe).

    Returns:
        Dict with:
          valid (bool): True if an active promo code was found.
          promo_label (str | None): Display string, e.g. "COMCOI20 — -20%".
          percent_off (float | None): Percentage discount if applicable.
          amount_off_cents (int | None): Fixed discount in euro-cents if applicable.
          error (str | None): Human-readable error message if invalid.
    """
    _init_stripe()
    try:
        promos = await _stripe_call(
            stripe.PromotionCode.list,
            code=code,
            active=True,
            limit=1,
        )
    except stripe.error.StripeError as exc:
        logger.warning("Stripe error validating promo code %r: %s", code, exc)
        return {
            "valid": False,
            "error": "Impossible de vérifier ce code promo.",
            "promo_label": None,
            "percent_off": None,
            "amount_off_cents": None,
        }

    if not promos.data:
        return {
            "valid": False,
            "error": "Code promo invalide ou expiré.",
            "promo_label": None,
            "percent_off": None,
            "amount_off_cents": None,
        }

    promo = promos.data[0]
    coupon = promo.coupon

    if coupon.percent_off is not None:
        label = f"{promo.code} — -{int(coupon.percent_off)}%"
        return {
            "valid": True,
            "promo_label": label,
            "percent_off": float(coupon.percent_off),
            "amount_off_cents": None,
            "error": None,
        }

    if coupon.amount_off is not None:
        label = f"{promo.code} — -{coupon.amount_off / 100:.2f} €"
        return {
            "valid": True,
            "promo_label": label,
            "percent_off": None,
            "amount_off_cents": coupon.amount_off,
            "error": None,
        }

    return {
        "valid": False,
        "error": "Code promo non pris en charge.",
        "promo_label": None,
        "percent_off": None,
        "amount_off_cents": None,
    }


def get_unit_ttc_cents(kind: str, quantity: int = 1) -> int:
    """
    Return the total TTC price in euro-cents for a given kind × quantity.

    Args:
        kind:     "payslip" | "dossier" | "contrat".
        quantity: Number of units (default 1).

    Returns:
        Total TTC amount in cents.

    Raises:
        ValueError: If kind is not in VALID_KINDS.
    """
    if kind not in VALID_KINDS:
        raise ValueError(f"Invalid kind: {kind!r}")
    return _PRICING[kind]["ttc_cents"] * quantity


# ── Display-price helper ──────────────────────────────────────────────────────


def build_display_price(kind: str, business_type: str | None) -> DisplayPrice:
    """
    Build the DisplayPrice object for an API response.

    Args:
        kind:           "payslip" | "dossier" | "contrat".
        business_type:  Salon's business_type (e.g. "auto_micro", "sarl").

    Returns:
        DisplayPrice with AE/non-AE framing.
    """
    pricing = _PRICING[kind]
    # AE = franchise en base TVA — no TVA framing. Show TTC only.
    framing = "ttc_primary" if business_type == "auto_micro" else "ht_primary"
    return DisplayPrice(
        ht_eur=pricing["ht_eur"],
        ttc_eur=pricing["ttc_eur"],
        framing=framing,
    )


# ── PaymentIntent creation ────────────────────────────────────────────────────


async def create_payment_intent(
    kind: str,
    salon_id: UUID,
    user_id: UUID,
    quantity: int = 1,
    submission_ids: list[UUID] | None = None,
    contrat_request_id: UUID | None = None,
    promo_code: str | None = None,
) -> stripe.PaymentIntent:
    """
    Create a Stripe PaymentIntent for a per-submission charge.

    Amount = unit_price_ttc_cents × quantity, minus any promo code discount.
    Metadata stored on the intent allows the webhook to route and act.

    Args:
        kind:               "payslip" | "dossier" | "contrat".
        salon_id:           The salon making the purchase.
        user_id:            The authenticated user placing the order.
        quantity:           Number of units (1 for dossier/contrat; N for payslips).
        submission_ids:     UUIDs of pre-created draft PayslipSubmission rows
                            (payslip kind only — used by webhook to locate rows).
        contrat_request_id: UUID of the pre-created ContratRequest row
                            (contrat kind only).
        promo_code:         Optional Stripe Promotion Code to apply.
                            Re-validated server-side for security.

    Returns:
        stripe.PaymentIntent object with .client_secret set.

    Raises:
        ValueError:               If kind is not in VALID_KINDS.
        stripe.error.StripeError: On Stripe API errors.
    """
    if kind not in VALID_KINDS:
        raise ValueError(f"Invalid payslip kind: {kind!r}. Must be one of {VALID_KINDS}")

    pricing = _PRICING[kind]
    amount_cents = pricing["ttc_cents"] * quantity

    # Build metadata that the webhook handler reads
    metadata: dict[str, str] = {
        "kind": kind,
        "salon_id": str(salon_id),
        "user_id": str(user_id),
        "quantity": str(quantity),
    }
    if submission_ids:
        # Encode as comma-separated string (Stripe metadata values are strings)
        metadata["submission_ids"] = ",".join(str(s) for s in submission_ids)
    if contrat_request_id:
        metadata["contrat_request_id"] = str(contrat_request_id)

    # Apply promo code discount (re-validated server-side — never trust the client amount)
    if promo_code:
        promo_result = await validate_promo_code(promo_code)
        if promo_result["valid"]:
            if promo_result["percent_off"] is not None:
                discount = int(amount_cents * promo_result["percent_off"] / 100)
            else:
                discount = promo_result["amount_off_cents"] or 0
            # Stripe minimum charge is 50 cents — enforce floor
            amount_cents = max(50, amount_cents - discount)
            metadata["promo_code"] = promo_code
            metadata["promo_label"] = promo_result["promo_label"] or ""
            logger.info(
                "Applied promo code %r (label=%r discount=%d cents) to intent for kind=%s salon=%s",
                promo_code,
                promo_result["promo_label"],
                discount,
                kind,
                salon_id,
            )

    intent = await _stripe_call(
        stripe.PaymentIntent.create,
        amount=amount_cents,
        currency="eur",
        metadata=metadata,
        description=f"{pricing['description']} — salon {salon_id}",
        # automatic_payment_methods lets Stripe handle the payment flow
        automatic_payment_methods={"enabled": True},
    )

    logger.info(
        "Created Stripe PaymentIntent %s for kind=%s salon=%s amount_cents=%s",
        intent.id,
        kind,
        salon_id,
        amount_cents,
    )
    return intent


# ── Webhook idempotency ───────────────────────────────────────────────────────


async def mark_event_processed(event_id: str, db: AsyncSession) -> bool:
    """
    Attempt to record a Stripe event ID as processed.

    Uses an INSERT that fails silently on PK conflict. If the row already
    exists (duplicate delivery), returns False — the caller should skip
    re-processing.

    Args:
        event_id: Stripe event ID (e.g. "evt_1ABC...").
        db:       Async DB session.

    Returns:
        True  if this is the first time we're processing this event.
        False if the event was already processed (idempotent replay).
    """
    record = StripeEventProcessed(
        event_id=event_id,
        processed_at=datetime.now(timezone.utc),
    )
    db.add(record)
    try:
        await db.flush()
        return True
    except IntegrityError:
        await db.rollback()
        logger.info("Stripe event %s already processed — skipping (idempotent replay)", event_id)
        return False


# ── Webhook handler ───────────────────────────────────────────────────────────


async def handle_payment_succeeded(
    event: stripe.Event,
    db: AsyncSession,
) -> dict[str, Any]:
    """
    Handle a Stripe `payment_intent.succeeded` event for per-submission kinds.

    Reads `metadata.kind` to determine which DB rows to update, then
    promotes their status and queues outbound email (stubs for 2.13.2/2.13.4/2.13.6).

    Args:
        event:  The verified Stripe Event object.
        db:     Async DB session.

    Returns:
        A dict with `processed` (bool) and `details` describing what changed.

    WHY we call handle_payment_succeeded from both the webhook route AND the
    /confirm endpoint: Stripe webhooks may arrive before or after the user
    returns to our return_url. Whichever fires first does the work; the second
    is a no-op via idempotency.
    """
    intent = event.data.object  # PaymentIntent
    intent_id: str = intent.id
    metadata: dict[str, str] = intent.get("metadata", {})
    kind = metadata.get("kind", "")

    if kind not in VALID_KINDS:
        logger.info(
            "Stripe event %s has unknown kind=%r — not a per-submission event, ignoring",
            event.id,
            kind,
        )
        return {"processed": False, "reason": f"unknown_kind:{kind}"}

    # Idempotency check
    already_processed = not await mark_event_processed(event.id, db)
    if already_processed:
        return {"processed": False, "reason": "already_processed"}

    salon_id_str = metadata.get("salon_id", "")

    if kind == "payslip":
        details = await _handle_payslip_succeeded(intent_id, metadata, db)
    elif kind == "dossier":
        details = await _handle_dossier_succeeded(intent_id, salon_id_str, db)
    elif kind == "contrat":
        details = await _handle_contrat_succeeded(intent_id, metadata, db)
    else:
        details = {"action": "none"}

    await db.commit()

    logger.info(
        "Handled payment_intent.succeeded event=%s kind=%s details=%s",
        event.id,
        kind,
        details,
    )
    return {"processed": True, "kind": kind, "details": details}


async def _handle_payslip_succeeded(
    intent_id: str,
    metadata: dict[str, str],
    db: AsyncSession,
) -> dict[str, Any]:
    """
    Promote draft PayslipSubmission rows to 'paid_pending_email'.

    Locates submissions by the comma-separated submission_ids in metadata,
    updates their status and stripe_payment_intent_id.

    Args:
        intent_id: Stripe PaymentIntent ID.
        metadata:  PaymentIntent metadata dict.
        db:        Async DB session.

    Returns:
        Dict with count of rows updated.
    """
    submission_ids_raw = metadata.get("submission_ids", "")
    if not submission_ids_raw:
        logger.warning("payslip payment_intent.succeeded has no submission_ids in metadata: %s", intent_id)
        return {"action": "no_submission_ids"}

    ids = [sid.strip() for sid in submission_ids_raw.split(",") if sid.strip()]
    result = await db.execute(
        select(PayslipSubmission).where(
            PayslipSubmission.id.in_(ids),
            PayslipSubmission.status == "draft",
        )
    )
    submissions = result.scalars().all()

    # Attempt to retrieve the Stripe receipt URL from the latest charge.
    # WHY: receipt_url on the charge is the Stripe-hosted, accounting-compliant
    # receipt. We persist it now so the history endpoint can serve it without
    # an extra Stripe API call per-request.
    receipt_url: str | None = None
    try:
        pi = await _stripe_call(
            stripe.PaymentIntent.retrieve,
            intent_id,
            expand=["latest_charge"],
        )
        charge = getattr(pi, "latest_charge", None)
        if charge:
            receipt_url = getattr(charge, "receipt_url", None)
    except Exception as exc:
        # Non-fatal — we can still serve the history page without the URL.
        logger.warning("Could not fetch receipt_url for intent %s: %s", intent_id, exc)

    updated = 0
    for sub in submissions:
        sub.status = "paid_pending_email"
        sub.stripe_payment_intent_id = intent_id
        if receipt_url:
            sub.stripe_receipt_url = receipt_url
        sub.updated_at = datetime.now(timezone.utc)
        updated += 1

    # Fire outbound email to Marie — idempotent (skips if already emailed)
    from app.services.payslip_email import send_variables_email  # noqa: PLC0415
    promoted_ids = [sub.id for sub in submissions]
    await send_variables_email(promoted_ids, db)

    logger.info("Promoted %d payslip submissions to paid_pending_email (intent=%s)", updated, intent_id)
    return {"action": "submissions_promoted", "count": updated, "receipt_url_stored": bool(receipt_url)}


async def _handle_dossier_succeeded(
    intent_id: str,
    salon_id_str: str,
    db: AsyncSession,
) -> dict[str, Any]:
    """
    Mark a salon's payslip dossier as 'paid'.

    Upserts the PayslipDossier row: creates it if it doesn't exist (race-safe),
    updates to 'paid' if it does.

    Args:
        intent_id:    Stripe PaymentIntent ID.
        salon_id_str: Salon UUID as string (from metadata).
        db:           Async DB session.

    Returns:
        Dict with action and new status.
    """
    if not salon_id_str:
        return {"action": "no_salon_id"}

    result = await db.execute(
        select(PayslipDossier).where(PayslipDossier.salon_id == salon_id_str)
    )
    dossier = result.scalar_one_or_none()

    # Generate a stable subject_token for inbound email matching (2.13.3).
    # Only set once — idempotent if webhook fires twice.
    token = secrets.token_hex(4)

    if dossier is None:
        dossier = PayslipDossier(
            salon_id=salon_id_str,
            status="paid",
            paid_at=datetime.now(timezone.utc),
            stripe_payment_intent_id=intent_id,
            subject_token=token,
            updated_at=datetime.now(timezone.utc),
        )
        db.add(dossier)
        action = "dossier_created_paid"
    else:
        dossier.status = "paid"
        dossier.paid_at = datetime.now(timezone.utc)
        dossier.stripe_payment_intent_id = intent_id
        # Only set token if not already set (idempotency)
        if not dossier.subject_token:
            dossier.subject_token = token
        dossier.updated_at = datetime.now(timezone.utc)
        action = "dossier_updated_paid"

    # Fire dossier creation email to Marie (TASK-2.13.4)
    from app.services.payslip_email import send_dossier_email  # noqa: PLC0415
    await send_dossier_email(salon_id_str, db)

    return {"action": action, "salon_id": salon_id_str}


async def _handle_contrat_succeeded(
    intent_id: str,
    metadata: dict[str, str],
    db: AsyncSession,
) -> dict[str, Any]:
    """
    Mark a ContratRequest as 'paid_pending_email'.

    Locates the ContratRequest by contrat_request_id from metadata.

    Args:
        intent_id: Stripe PaymentIntent ID.
        metadata:  PaymentIntent metadata dict.
        db:        Async DB session.

    Returns:
        Dict with action and contrat_request_id.
    """
    contrat_id = metadata.get("contrat_request_id", "")
    if not contrat_id:
        return {"action": "no_contrat_request_id"}

    result = await db.execute(
        select(ContratRequest).where(ContratRequest.id == contrat_id)
    )
    contrat = result.scalar_one_or_none()

    if contrat is None:
        logger.warning("ContratRequest %s not found for payment_intent %s", contrat_id, intent_id)
        return {"action": "contrat_not_found", "contrat_request_id": contrat_id}

    contrat.status = "paid_pending_email"
    contrat.stripe_payment_intent_id = intent_id

    # Attempt to retrieve and persist the Stripe receipt URL (same pattern as payslip).
    try:
        pi = await _stripe_call(
            stripe.PaymentIntent.retrieve,
            intent_id,
            expand=["latest_charge"],
        )
        charge = getattr(pi, "latest_charge", None)
        if charge:
            receipt_url = getattr(charge, "receipt_url", None)
            if receipt_url:
                contrat.stripe_receipt_url = receipt_url
    except Exception as exc:
        logger.warning("Could not fetch receipt_url for contrat intent %s: %s", intent_id, exc)

    # Fire contrat email to Marie (TASK-2.13.6). Idempotent in payslip_email.py.
    from app.services.payslip_email import send_contrat_email  # noqa: PLC0415
    await send_contrat_email(str(contrat.id), db)

    return {"action": "contrat_promoted_paid_pending_email", "contrat_request_id": contrat_id}


# ── Webhook signature verification ───────────────────────────────────────────


def verify_webhook_signature(payload: bytes, sig_header: str | None) -> stripe.Event:
    """
    Verify a Stripe webhook payload signature and parse the event.

    If STRIPE_WEBHOOK_SECRET is empty (dev mode without `stripe listen`),
    signature verification is skipped and the payload is parsed without
    verification — ONLY do this in development.

    Args:
        payload:    Raw request body bytes.
        sig_header: Value of the 'Stripe-Signature' header.

    Returns:
        Parsed stripe.Event object.

    Raises:
        stripe.error.SignatureVerificationError: If verification fails.
        ValueError: If payload cannot be parsed as a Stripe event.
    """
    _init_stripe()

    if not settings.stripe_webhook_secret:
        logger.warning(
            "STRIPE_WEBHOOK_SECRET not set — skipping signature verification. "
            "This is ONLY acceptable in development. Set the webhook secret for production."
        )
        # Parse without verification (dev only)
        return stripe.Event.construct_from(
            stripe.util.convert_to_stripe_object(
                stripe.util.json.loads(payload.decode("utf-8"))
            ),
            stripe.api_key,
        )

    return stripe.Webhook.construct_event(
        payload, sig_header, settings.stripe_webhook_secret
    )
