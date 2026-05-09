"""
Stripe webhook endpoint (Sprint 2.13 + TASK-2.16.4 + TASK-2.16.8).

Receives Stripe webhook events and routes them to the correct handler based
on `metadata.kind`. Per-submission kinds (payslip, dossier, contrat) go to
`stripe_per_submission.handle_payment_succeeded`. Subscription checkouts
(kind="subscription") go to the subscription handler.

TASK-2.16.8 additions:
  - checkout.session.completed + kind=subscription → records trial_started event
  - invoice.paid + billing_reason=subscription_cycle → records converted_to_paid event
  - customer.subscription.deleted → records churned event

Unknown kinds are logged and silently accepted.

Security:
  - Signature verification via STRIPE_WEBHOOK_SECRET (skipped in dev when unset).
  - Raw request bytes are read before Pydantic parses anything.
  - Always returns 200 (even for ignored events) so Stripe doesn't retry.

Setup for local dev:
  stripe listen --forward-to localhost:47002/api/stripe/webhook
  (copies the webhook secret to stdout -- put it in STRIPE_WEBHOOK_SECRET)
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.services.stripe_per_submission import (
    VALID_KINDS,
    handle_payment_succeeded,
    verify_webhook_signature,
)
from app.services.subscription_metrics import record_subscription_event
from app.services.noly_subscription import (
    COMPTA_SKU_KEYS,
    get_primary_salon_for_user,
    update_subscription_status,
    upsert_noly_subscription,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stripe", tags=["stripe-webhooks"])


@router.post(
    "/webhook",
    summary="Point d'entree Stripe webhooks",
    include_in_schema=False,  # Hidden from OpenAPI -- not for frontend consumption
)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Receive and route Stripe webhook events.

    Verification -> Parse -> Route -> Respond.

    Always returns HTTP 200 with a status dict. Stripe will retry any non-2xx
    response, so we return 200 even for events we ignore or cannot parse.
    We log errors instead of raising HTTP exceptions (to prevent Stripe retries).

    Event routing:
      - payment_intent.succeeded + kind in {payslip, dossier, contrat}
          -> stripe_per_submission.handle_payment_succeeded
      - checkout.session.completed + kind == "subscription"
          -> subscription checkout handler (records trial_started)
      - invoice.paid + billing_reason in {subscription_cycle, subscription_update}
          -> records converted_to_paid (first paid charge after trial)
      - customer.subscription.deleted
          -> records churned event
      - All other events / kinds
          -> logged and accepted as 200 {"status": "ignored"}

    Args:
        request: Raw FastAPI Request (we need the raw body for signature verify).
        db:      Async DB session for webhook handlers.

    Returns:
        JSON dict with "status" key.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    # Signature verification
    try:
        event = verify_webhook_signature(payload, sig_header)
    except stripe.error.SignatureVerificationError as exc:
        logger.warning("Stripe webhook signature verification failed: %s", exc)
        # Return 400 on signature failure -- Stripe should NOT retry a forged event.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stripe signature invalide.",
        )
    except Exception as exc:
        logger.error("Error parsing Stripe webhook payload: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload Stripe invalide.",
        )

    event_type: str = event.get("type", "")
    intent = event.data.object if hasattr(event, "data") else {}
    metadata = getattr(intent, "metadata", {}) or {}
    kind = metadata.get("kind", "") if hasattr(metadata, "get") else ""
    stripe_event_id = event.get("id")

    logger.info(
        "Received Stripe webhook event=%s type=%s kind=%r",
        stripe_event_id,
        event_type,
        kind,
    )

    # ── Route: payment_intent.succeeded (per-submission: payslip, dossier, contrat) ──
    if event_type == "payment_intent.succeeded":
        if kind in VALID_KINDS:
            try:
                result = await handle_payment_succeeded(event, db)
                return {"status": "processed", "result": result}
            except Exception as exc:
                # Log but don't re-raise -- we must return 200 to Stripe
                logger.exception(
                    "Error handling payment_intent.succeeded event=%s kind=%s: %s",
                    event.get("id"),
                    kind,
                    exc,
                )
                return {"status": "error_logged", "event_id": event.get("id")}
        else:
            logger.info(
                "payment_intent.succeeded with unknown kind=%r -- not a per-submission event.",
                kind,
            )
            return {"status": "ignored", "reason": f"unknown_kind:{kind}"}

    # ── Route: payment_intent.payment_failed ──────────────────────────────────
    if event_type == "payment_intent.payment_failed":
        intent_id = getattr(intent, "id", "unknown")
        failure_msg = getattr(intent, "last_payment_error", {})
        if hasattr(failure_msg, "get"):
            failure_msg = failure_msg.get("message", "unknown")
        logger.warning(
            "Payment failed for intent=%s kind=%r failure=%s",
            intent_id,
            kind,
            failure_msg,
        )
        return {"status": "payment_failed_logged", "intent_id": intent_id}

    # ── Route: checkout.session.completed for subscription (TASK-2.16.4 + 2.16.8) ──
    if event_type == "checkout.session.completed" and kind == "subscription":
        try:
            result = await _handle_subscription_checkout_completed(event, db)
            return {"status": "subscription_activated", "metrics": result}
        except Exception as exc:
            logger.exception(
                "Error handling checkout.session.completed subscription event=%s: %s",
                stripe_event_id,
                exc,
            )
            return {"status": "error_logged", "event_id": stripe_event_id}

    # ── Route: invoice.paid → converted_to_paid (TASK-2.16.8) ────────────────
    # billing_reason=subscription_cycle fires on the first real charge after trial.
    # We also catch subscription_update (plan upgrades) as a conversion signal.
    if event_type == "invoice.paid":
        try:
            await _handle_invoice_paid(event, db, stripe_event_id)
        except Exception as exc:
            logger.exception(
                "Error handling invoice.paid event=%s: %s", stripe_event_id, exc
            )
        return {"status": "invoice_paid_processed"}

    # ── Route: customer.subscription.updated → update noly_subscriptions (TASK-3.11) ─
    if event_type == "customer.subscription.updated":
        try:
            await _handle_subscription_updated(event, db, stripe_event_id)
        except Exception as exc:
            logger.exception(
                "Error handling customer.subscription.updated event=%s: %s",
                stripe_event_id,
                exc,
            )
        return {"status": "subscription_updated_processed"}

    # ── Route: invoice.payment_failed → past_due (TASK-3.11) ─────────────────
    if event_type == "invoice.payment_failed":
        try:
            await _handle_invoice_payment_failed(event, db, stripe_event_id)
        except Exception as exc:
            logger.exception(
                "Error handling invoice.payment_failed event=%s: %s",
                stripe_event_id,
                exc,
            )
        return {"status": "invoice_payment_failed_processed"}

    # ── Route: customer.subscription.deleted → churned (TASK-2.16.8) ─────────
    if event_type == "customer.subscription.deleted":
        try:
            await _handle_subscription_deleted(event, db, stripe_event_id)
        except Exception as exc:
            logger.exception(
                "Error handling customer.subscription.deleted event=%s: %s",
                stripe_event_id,
                exc,
            )
        return {"status": "subscription_deleted_processed"}

    # Default: accept and ignore
    logger.debug("Ignoring Stripe event type=%s", event_type)
    return {"status": "ignored", "event_type": event_type}


# ---------------------------------------------------------------------------
# Private handlers
# ---------------------------------------------------------------------------


async def _handle_subscription_checkout_completed(
    event: dict,
    db: AsyncSession,
) -> dict:
    """
    Handle Stripe `checkout.session.completed` for subscription checkouts.

    Records a 'trial_started' subscription event (TASK-2.16.8) and logs
    the activation for audit purposes.

    The session metadata carries:
      - user_id:          UUID of the Atlas user who subscribed
      - logical_sku_key:  The product key (e.g. "ccpilot_monthly_2026_05")
      - kind:             "subscription"

    Args:
        event: The verified Stripe event object.
        db:    Async DB session.

    Returns:
        Dict with action result from record_subscription_event.
    """
    session_obj = event.data.object
    session_id = getattr(session_obj, "id", "unknown")
    stripe_subscription_id = getattr(session_obj, "subscription", None)
    stripe_customer_id = getattr(session_obj, "customer", None)
    metadata = getattr(session_obj, "metadata", {}) or {}
    user_id_str = metadata.get("user_id") if hasattr(metadata, "get") else None
    logical_sku_key = metadata.get("logical_sku_key") if hasattr(metadata, "get") else None
    customer_email = getattr(session_obj, "customer_email", None)

    # Parse event.created timestamp (Unix epoch)
    occurred_at = datetime.fromtimestamp(event.get("created", 0), tz=UTC)

    user_id: uuid.UUID | None = None
    if user_id_str:
        try:
            user_id = uuid.UUID(user_id_str)
        except ValueError:
            logger.warning(
                "checkout.session.completed: invalid user_id=%r in metadata", user_id_str
            )

    logger.info(
        "Subscription checkout completed: session=%s user_id=%s sku=%s stripe_sub=%s email=%s",
        session_id,
        user_id,
        logical_sku_key,
        stripe_subscription_id,
        customer_email,
    )

    # Record trial_started event for TASK-2.16.8 metrics
    result = await record_subscription_event(
        db,
        event_type="trial_started",
        stripe_event_id=event.get("id"),
        stripe_subscription_id=stripe_subscription_id,
        stripe_customer_id=stripe_customer_id,
        logical_sku_key=logical_sku_key,
        user_id=user_id,
        occurred_at=occurred_at,
        notes=f"checkout session {session_id}",
    )

    # ── TASK-3.11: Noly Compta provisioning for compta SKUs ──────────────────
    # When the user subscribes to a plan that includes accounting, provision
    # their account on Noly and upsert the noly_subscriptions row.
    if logical_sku_key and logical_sku_key in COMPTA_SKU_KEYS and user_id:
        try:
            await _provision_noly_on_checkout(
                db=db,
                user_id=str(user_id),
                logical_sku_key=logical_sku_key,
                stripe_subscription_id=stripe_subscription_id,
                stripe_customer_id=stripe_customer_id,
            )
        except Exception as exc:
            # Non-fatal: log and continue. Metrics are already recorded.
            # The user can still access Noly via the access endpoint which
            # will retry magic-link on their email.
            logger.error(
                "Noly provisioning failed for user=%s sku=%s: %s — "
                "noly_subscriptions row may be missing; will retry on next access.",
                user_id, logical_sku_key, exc, exc_info=True,
            )

    return result


async def _handle_invoice_paid(
    event: dict,
    db: AsyncSession,
    stripe_event_id: str | None,
) -> None:
    """
    Handle Stripe `invoice.paid` to record trial → paid conversions.

    Only acts on billing_reason values that indicate a paid subscription
    cycle (not the free trial). This captures the first real charge.

    Args:
        event:          The verified Stripe event object.
        db:             Async DB session.
        stripe_event_id: The evt_xxx ID for idempotency.
    """
    invoice_obj = event.data.object
    billing_reason = getattr(invoice_obj, "billing_reason", "") or ""
    stripe_subscription_id = getattr(invoice_obj, "subscription", None)
    stripe_customer_id = getattr(invoice_obj, "customer", None)

    # billing_reason=subscription_cycle = regular renewal / first paid charge
    # billing_reason=subscription_update = plan change that triggered an invoice
    # We skip 'subscription_create' which is the initial invoice (often $0 trial)
    if billing_reason not in ("subscription_cycle", "subscription_update"):
        logger.debug(
            "invoice.paid skipped: billing_reason=%r not a conversion signal", billing_reason
        )
        return

    occurred_at = datetime.fromtimestamp(event.get("created", 0), tz=UTC)

    # We can't easily resolve logical_sku_key from an invoice without a Stripe
    # API call (the price ID is on the invoice line item). For now we record the
    # event without sku — the churn/conversion query falls back to sub_id matching.
    # TODO (future): expand invoice line items to extract the Price ID and map it.
    await record_subscription_event(
        db,
        event_type="converted_to_paid",
        stripe_event_id=stripe_event_id,
        stripe_subscription_id=stripe_subscription_id,
        stripe_customer_id=stripe_customer_id,
        logical_sku_key=None,  # resolved via sub_id match in metrics query
        user_id=None,          # resolved via customer_id in metrics query if needed
        occurred_at=occurred_at,
        notes=f"billing_reason={billing_reason}",
    )
    logger.info(
        "invoice.paid converted_to_paid recorded: sub=%s customer=%s reason=%s",
        stripe_subscription_id,
        stripe_customer_id,
        billing_reason,
    )


async def _handle_subscription_deleted(
    event: dict,
    db: AsyncSession,
    stripe_event_id: str | None,
) -> None:
    """
    Handle Stripe `customer.subscription.deleted` to record churn events.

    Args:
        event:          The verified Stripe event object.
        db:             Async DB session.
        stripe_event_id: The evt_xxx ID for idempotency.
    """
    sub_obj = event.data.object
    stripe_subscription_id = getattr(sub_obj, "id", None)
    stripe_customer_id = getattr(sub_obj, "customer", None)
    cancel_at = getattr(sub_obj, "canceled_at", None)
    cancel_reason = getattr(sub_obj, "cancellation_details", None)
    if hasattr(cancel_reason, "get"):
        cancel_reason = cancel_reason.get("reason", "unknown")

    occurred_at = datetime.fromtimestamp(event.get("created", 0), tz=UTC)

    await record_subscription_event(
        db,
        event_type="churned",
        stripe_event_id=stripe_event_id,
        stripe_subscription_id=stripe_subscription_id,
        stripe_customer_id=stripe_customer_id,
        logical_sku_key=None,  # not available on deletion event directly
        user_id=None,
        occurred_at=occurred_at,
        notes=f"cancel_reason={cancel_reason}",
    )
    logger.info(
        "customer.subscription.deleted churned recorded: sub=%s customer=%s reason=%s",
        stripe_subscription_id,
        stripe_customer_id,
        cancel_reason,
    )
    # Also mark the noly_subscriptions row as cancelled
    if stripe_subscription_id:
        await update_subscription_status(
            db,
            stripe_subscription_id=stripe_subscription_id,
            new_status="cancelled",
        )


async def _handle_subscription_updated(
    event: dict,
    db: AsyncSession,
    stripe_event_id: str | None,
) -> None:
    """
    Handle Stripe `customer.subscription.updated` to keep noly_subscriptions in sync.

    Stripe fires this event whenever a subscription changes:
      - trialing → active (trial ended, first charge taken)
      - active → past_due (payment failed)
      - past_due → active (payment recovered)
      - any → cancelled (initiated by customer or admin)

    We map Stripe's subscription status directly to our noly_subscriptions.status.

    Args:
        event:           The verified Stripe event object.
        db:              Async DB session.
        stripe_event_id: The evt_xxx ID for logging.
    """
    sub_obj = event.data.object
    stripe_subscription_id = getattr(sub_obj, "id", None)
    stripe_status = getattr(sub_obj, "status", None)  # e.g. "active", "past_due"
    trial_end_ts = getattr(sub_obj, "trial_end", None)
    period_end_ts = getattr(sub_obj, "current_period_end", None)

    if not stripe_subscription_id or not stripe_status:
        logger.warning(
            "_handle_subscription_updated: missing sub_id or status in event=%s",
            stripe_event_id,
        )
        return

    trial_ends_at = (
        datetime.fromtimestamp(trial_end_ts, tz=UTC) if trial_end_ts else None
    )
    current_period_end = (
        datetime.fromtimestamp(period_end_ts, tz=UTC) if period_end_ts else None
    )

    updated = await update_subscription_status(
        db,
        stripe_subscription_id=stripe_subscription_id,
        new_status=stripe_status,
        current_period_end=current_period_end,
        trial_ends_at=trial_ends_at,
    )
    if not updated:
        logger.info(
            "_handle_subscription_updated: no noly_subscriptions row for sub=%s "
            "(non-compta plan or not yet provisioned) — skipping.",
            stripe_subscription_id,
        )


async def _handle_invoice_payment_failed(
    event: dict,
    db: AsyncSession,
    stripe_event_id: str | None,
) -> None:
    """
    Handle Stripe `invoice.payment_failed` to mark subscription as past_due.

    Stripe fires this when an invoice charge fails. The subscription status is
    typically already set to 'past_due' by Stripe, but we also get a
    customer.subscription.updated event. We handle both to be resilient.

    Args:
        event:           The verified Stripe event object.
        db:              Async DB session.
        stripe_event_id: The evt_xxx ID for logging.
    """
    invoice_obj = event.data.object
    stripe_subscription_id = getattr(invoice_obj, "subscription", None)

    if not stripe_subscription_id:
        return

    await update_subscription_status(
        db,
        stripe_subscription_id=stripe_subscription_id,
        new_status="past_due",
    )
    logger.info(
        "_handle_invoice_payment_failed: set past_due for sub=%s event=%s",
        stripe_subscription_id, stripe_event_id,
    )


async def _provision_noly_on_checkout(
    db: AsyncSession,
    user_id: str,
    logical_sku_key: str,
    stripe_subscription_id: str | None,
    stripe_customer_id: str | None,
) -> None:
    """
    Provision a Noly Compta account and create noly_subscriptions row after checkout.

    Called from _handle_subscription_checkout_completed when the purchased plan
    includes accounting (COMPTA_SKU_KEYS). Handles the full flow:
      1. Look up the User + primary Salon from the DB.
      2. Call noly_api.provision_user() to create their Noly account.
         - If Noly returns 422 (email already exists), we skip provisioning
           gracefully — the user already has a Noly account (e.g. migrated from
           Bubble). We still create the noly_subscriptions row.
      3. Upsert noly_subscriptions with status='trialing' + Noly IDs.

    Args:
        db:                     Async DB session.
        user_id:                UUID string of the user from webhook metadata.
        logical_sku_key:        The product SKU (determines BIC vs BIC+ / tax_type).
        stripe_subscription_id: Stripe subscription ID from checkout session.
        stripe_customer_id:     Stripe customer ID from checkout session.
    """
    from sqlalchemy import select  # local import to keep top of file clean

    from app.services.noly_api import (
        BUSINESS_TYPE_TO_NOLY_BASE,
        NOLY_VAT_QUARTERLY,
        SKU_TO_NOLY_TAX_TYPE,
        probe_noly_user_exists,
        provision_user,
    )

    # Step 1: load User + Salon
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        logger.error(
            "_provision_noly_on_checkout: user not found user_id=%s", user_id
        )
        return

    salon = await get_primary_salon_for_user(db, user_id)
    if not salon:
        logger.error(
            "_provision_noly_on_checkout: no salon for user_id=%s", user_id
        )
        return

    # Step 2: probe Noly to check if this email already has an account,
    # then provision if not. This prevents double-registration for users
    # who were on Bubble, had a paused subscription, or re-subscribed.
    noly_user_id: str | None = None
    noly_company_id: str | None = None
    noly_pre_existing: bool | None = None

    # Probe first — discards the magic link URL, but gives us the Noly user ID
    # and avoids a confusing 422 from provision_user if the email already exists.
    already_exists, probed_noly_user_id = await probe_noly_user_exists(user.email)

    if already_exists:
        # User already has a Noly account in our white-label — skip provisioning.
        noly_user_id = probed_noly_user_id
        noly_pre_existing = True
        logger.info(
            "_provision_noly_on_checkout: email=%s already in Noly white-label "
            "(noly_user_id=%s) — skipping provision_user call.",
            user.email, noly_user_id,
        )
    else:
        # User not found in Noly — provision fresh account.
        noly_pre_existing = False

        # Split full name into firstname/lastname (best-effort)
        parts = (user.name or "").split(" ", 1)
        firstname = parts[0] if parts else None
        lastname = parts[1] if len(parts) > 1 else None

        # Map business_type to Noly base_type
        biz_type_raw = (getattr(salon, "business_type", None) or "").lower()
        noly_base_type = BUSINESS_TYPE_TO_NOLY_BASE.get(biz_type_raw)
        noly_tax_type = SKU_TO_NOLY_TAX_TYPE.get(logical_sku_key)

        # Employee count: count active employees for this salon
        from app.models.salon import Employee  # noqa: PLC0415
        emp_result = await db.execute(
            select(Employee).where(
                Employee.salon_id == salon.id,
                Employee.is_active == True,  # noqa: E712
            )
        )
        employees = emp_result.scalars().all()
        employees_count = len(employees) if employees else None

        try:
            prov = await provision_user(
                email=user.email,
                company_name=salon.name,
                firstname=firstname,
                lastname=lastname,
                employees_count=employees_count,
                base_type=noly_base_type,
                vat_type=NOLY_VAT_QUARTERLY,
                tax_type=noly_tax_type,
                send_credentials_email=True,
            )
            noly_user_id = prov.noly_user_id
            noly_company_id = prov.noly_company_id
            logger.info(
                "_provision_noly_on_checkout: provisioned user=%s noly_user=%s noly_co=%s",
                user_id, noly_user_id, noly_company_id,
            )
        except ValueError as exc:
            # Unexpected 422 after probe returned False — e.g. race condition or
            # probe failure that fell through as safe. Log prominently but don't
            # crash; noly_user_id stays None and magic-link lookup by email still works.
            logger.error(
                "_provision_noly_on_checkout: unexpected Noly 422 for user=%s "
                "after probe said not-found: %s — no Noly IDs stored.",
                user_id, exc,
            )

    # Step 3: upsert noly_subscriptions with trialing status
    await upsert_noly_subscription(
        db,
        salon_id=str(salon.id),
        stripe_subscription_id=stripe_subscription_id,
        stripe_customer_id=stripe_customer_id,
        status="trialing",
        logical_sku_key=logical_sku_key,
        current_period_end=None,   # populated later by subscription.updated event
        trial_ends_at=None,        # populated later by subscription.updated event
        noly_user_id=noly_user_id,
        noly_company_id=noly_company_id,
        noly_pre_existing=noly_pre_existing,
    )
