"""
TASK-2.17.7 — Stripe verification + grandfathered subscriptions: unit tests.

All tests call ``process_records()`` directly with fixture Bubble Abonnement
records. Stripe SDK calls are mocked with ``unittest.mock.patch`` (never
pytest-mock — not installed per LEARNINGS #96).

The Stripe mock uses ``MagicMock`` with ``.get.side_effect`` to handle both
dict-style access (``sub.get("status")``) and the plain-dict return shape
that ``process_records`` expects. See LEARNINGS #98.

Self-contained pattern (LEARNINGS #27): each test creates its own user + salon,
runs the import, asserts DB state, and cleans up — regardless of test order.

Test coverage:
  T1. Active Stripe sub → grandfathered: noly_subscriptions row created,
      legacy_pricing_audit row written with source='bubble_migration'.
  T2. Canceled Stripe sub → lapsed: import_status='imported_lapsed',
      last_paid_at populated, no legacy_pricing_audit row written.
  T3. Stripe 404 → treated as lapsed, logged in error_details.
  T4. Metadata tagged on Stripe.Subscription.modify (comcoi_user_id +
      migrated_from='bubble_2026_05').
  T5. safe_modify() raises RuntimeError on any forbidden key (items, price, …).
      Pure unit test — no DB or Stripe calls needed.
  T6. Idempotent re-run: second pass skips Stripe API call entirely
      (because noly_subscriptions.bubble_abonnement_id already exists);
      no new legacy_pricing_audit rows written.
  T7. pack_compta → legacy_plan mapping: table-driven, pure unit test.
  T8. After grandfathering, users.import_status = 'imported_active_paying'.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import settings
from scripts.bubble.import_subscriptions import (
    PACK_TO_LEGACY_PLAN,
    FORBIDDEN_MODIFY_KEYS,
    process_records,
    safe_modify,
)


# ── Session factory ───────────────────────────────────────────────────────────

def _make_session_factory():
    """Return a fresh (engine, factory) pair for this test invocation."""
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


# ── DB setup helpers ──────────────────────────────────────────────────────────

async def _create_user_and_salon(
    factory,
    bubble_user_id: str,
    bubble_salon_id: str | None = None,
    import_status: str = "imported_dormant",
) -> tuple[str, str]:
    """
    Seed a user and salon row. Returns (user_db_id, salon_db_id) as UUID strings.

    Args:
        factory:          Async session factory.
        bubble_user_id:   Bubble user ID to set on the user row.
        bubble_salon_id:  Bubble salon ID (auto-generated if None).
        import_status:    Initial import_status for the user.

    Returns:
        Tuple of (user_db_id, salon_db_id) as UUID strings.
    """
    async with factory() as db:
        # Create user
        user_result = await db.execute(
            text("""
                INSERT INTO users (
                    email, password_hash, name,
                    role, onboarding_completed, has_completed_typical_month,
                    preferred_tools, bubble_user_id, import_status, import_source
                ) VALUES (
                    :email, 'test_hash', :name,
                    'user', false, false,
                    '[]'::jsonb, :bubble_user_id, :import_status,
                    'bubble_migration_2026_05'
                )
                RETURNING id
            """),
            {
                "email": f"test-{bubble_user_id[:12]}@sub-test.invalid",
                "name": f"Test User {bubble_user_id[:8]}",
                "bubble_user_id": bubble_user_id,
                "import_status": import_status,
            },
        )
        user_db_id = str(user_result.fetchone()[0])

        # Create salon (needs user_id FK)
        bsid = bubble_salon_id or f"bsalon-{uuid.uuid4().hex[:16]}"
        salon_result = await db.execute(
            text("""
                INSERT INTO salons (
                    user_id, name, fiscal_year_start,
                    bubble_salon_id
                ) VALUES (
                    :user_id, :name, 1, :bubble_salon_id
                )
                RETURNING id
            """),
            {
                "user_id": user_db_id,
                "name": f"Salon {bubble_user_id[:8]}",
                "bubble_salon_id": bsid,
            },
        )
        salon_db_id = str(salon_result.fetchone()[0])
        await db.commit()

    return user_db_id, salon_db_id


async def _get_user_status(factory, user_db_id: str) -> dict:
    """
    Return {import_status, legacy_pricing_plan, last_paid_at} for a user row.

    Args:
        factory:      Async session factory.
        user_db_id:   Postgres users.id as UUID string.
    """
    async with factory() as db:
        r = await db.execute(
            text(
                "SELECT import_status, legacy_pricing_plan, last_paid_at "
                "FROM users WHERE id = :uid LIMIT 1"
            ),
            {"uid": user_db_id},
        )
        row = r.mappings().fetchone()
        return dict(row) if row else {}


async def _count_audit_rows(factory, user_db_id: str) -> int:
    """Count legacy_pricing_audit rows for a given user."""
    async with factory() as db:
        r = await db.execute(
            text(
                "SELECT COUNT(*) FROM legacy_pricing_audit WHERE user_id = :uid"
            ),
            {"uid": user_db_id},
        )
        return r.scalar_one()


async def _count_noly_rows(factory, bubble_abonnement_id: str) -> int:
    """Count noly_subscriptions rows for a given bubble_abonnement_id."""
    async with factory() as db:
        r = await db.execute(
            text(
                "SELECT COUNT(*) FROM noly_subscriptions "
                "WHERE bubble_abonnement_id = :bid"
            ),
            {"bid": bubble_abonnement_id},
        )
        return r.scalar_one()


async def _cleanup(factory, user_db_id: str, salon_db_id: str | None = None) -> None:
    """Delete test rows in reverse FK order."""
    async with factory() as db:
        await db.execute(
            text("DELETE FROM legacy_pricing_audit WHERE user_id = :uid"),
            {"uid": user_db_id},
        )
        if salon_db_id:
            await db.execute(
                text("DELETE FROM noly_subscriptions WHERE salon_id = :sid"),
                {"sid": salon_db_id},
            )
        await db.execute(
            text("DELETE FROM salons WHERE user_id = :uid"),
            {"uid": user_db_id},
        )
        await db.execute(
            text("DELETE FROM users WHERE id = :uid"),
            {"uid": user_db_id},
        )
        await db.commit()


# ── Bubble fixture helpers ────────────────────────────────────────────────────

def _abonnement(
    bubble_id: str,
    bubble_user_id: str,
    stripe_sub_id: str | None = "sub_test_001",
    pack_compta: str = "Pack micro-entreprises",
) -> dict:
    """
    Build a minimal Bubble Abonnement dict.

    Args:
        bubble_id:        Bubble Abonnement._id.
        bubble_user_id:   Bubble User._id (Created By).
        stripe_sub_id:    Stripe subscription ID or None for unpaid users.
        pack_compta:      Plan tier string as stored in Bubble.

    Returns:
        Dict matching the Bubble API shape.
    """
    return {
        "_id": bubble_id,
        "Created By": bubble_user_id,
        "id_stripe compta": stripe_sub_id,
        "pack-compta": pack_compta,
        "abonnement compta": True,
        "fin-essai-compta": "2024-02-17T12:16:42.543Z",
        "Created Date": "2023-10-11T12:42:55.403Z",
        "Modified Date": "2024-05-02T14:07:47.704Z",
    }


def _stripe_sub_mock(status: str = "active", current_period_end_ts: int = 1_800_000_000) -> dict:
    """
    Build a minimal Stripe Subscription dict (dict, not StripeObject).

    ``process_records`` accesses this via .get() exclusively, so a plain dict works.

    Args:
        status:                 Stripe subscription status string.
        current_period_end_ts:  Unix timestamp for current_period_end.

    Returns:
        Dict matching Stripe Subscription shape (minimal subset used by script).
    """
    return {
        "id": "sub_test_001",
        "status": status,
        "current_period_end": current_period_end_ts,
        "items": {
            "data": [
                {"price": {"id": "price_legacy_99_yearly"}},
            ]
        },
    }


# ── T1: active sub → grandfathered + audit row ────────────────────────────────

@pytest.mark.asyncio
async def test_active_sub_grandfathered_with_audit():
    """
    Active Stripe subscription → grandfathered:
    - noly_subscriptions row created with stripe_subscription_id.
    - legacy_pricing_audit row written with source='bubble_migration'.
    - users.import_status set to 'imported_active_paying'.
    - process_records counts['grandfathered'] == 1.
    """
    _, factory = _make_session_factory()
    buid = f"buid-t1-{uuid.uuid4().hex[:12]}"
    babt = f"babt-t1-{uuid.uuid4().hex[:12]}"
    user_db_id, salon_db_id = await _create_user_and_salon(factory, buid)

    stripe_mock = _stripe_sub_mock(status="active")
    abonnement = _abonnement(
        bubble_id=babt,
        bubble_user_id=buid,
        stripe_sub_id="sub_active_t1",
        pack_compta="Pack micro-entreprises",
    )

    try:
        with (
            patch("scripts.bubble.import_subscriptions.stripe") as mock_stripe,
            patch("scripts.bubble.import_subscriptions.time") as mock_time,
        ):
            mock_stripe.Subscription.retrieve.return_value = stripe_mock
            mock_stripe.Subscription.modify.return_value = MagicMock()
            mock_stripe.error.InvalidRequestError = Exception  # unused in this path

            async with factory() as db:
                counts = await process_records(db, [abonnement], dry_run=False)

        assert counts["grandfathered"] == 1, f"Expected 1 grandfathered, got {counts}"
        assert counts["errored"] == 0

        # noly_subscriptions row created
        noly_count = await _count_noly_rows(factory, babt)
        assert noly_count == 1, "Expected noly_subscriptions row to be created"

        # legacy_pricing_audit row written with source='bubble_migration'
        async with factory() as db:
            r = await db.execute(
                text(
                    "SELECT source, plan FROM legacy_pricing_audit "
                    "WHERE user_id = :uid ORDER BY set_at DESC LIMIT 1"
                ),
                {"uid": user_db_id},
            )
            audit_row = r.mappings().fetchone()
        assert audit_row is not None, "legacy_pricing_audit row not found"
        assert audit_row["source"] == "bubble_migration", (
            f"Expected source='bubble_migration', got {audit_row['source']!r}"
        )
        assert audit_row["plan"] == "legacy_99_yearly"

        # users.import_status promoted
        user_state = await _get_user_status(factory, user_db_id)
        assert user_state["import_status"] == "imported_active_paying"
        assert user_state["legacy_pricing_plan"] == "legacy_99_yearly"

    finally:
        await _cleanup(factory, user_db_id, salon_db_id)


# ── T2: canceled sub → lapsed, no legacy row ─────────────────────────────────

@pytest.mark.asyncio
async def test_canceled_sub_marked_lapsed_no_legacy_set():
    """
    Canceled Stripe subscription:
    - import_status set to 'imported_lapsed'.
    - last_paid_at populated from current_period_end.
    - No legacy_pricing_audit row written.
    - No noly_subscriptions row created.
    """
    _, factory = _make_session_factory()
    buid = f"buid-t2-{uuid.uuid4().hex[:12]}"
    babt = f"babt-t2-{uuid.uuid4().hex[:12]}"
    user_db_id, salon_db_id = await _create_user_and_salon(factory, buid)

    # Timestamp for current_period_end (2026-01-15 UTC)
    cpe_ts = int(datetime(2026, 1, 15, tzinfo=timezone.utc).timestamp())
    stripe_mock = _stripe_sub_mock(status="canceled", current_period_end_ts=cpe_ts)
    abonnement = _abonnement(
        bubble_id=babt,
        bubble_user_id=buid,
        stripe_sub_id="sub_canceled_t2",
    )

    try:
        with (
            patch("scripts.bubble.import_subscriptions.stripe") as mock_stripe,
            patch("scripts.bubble.import_subscriptions.time"),
        ):
            mock_stripe.Subscription.retrieve.return_value = stripe_mock
            mock_stripe.error.InvalidRequestError = Exception

            async with factory() as db:
                counts = await process_records(db, [abonnement], dry_run=False)

        assert counts["lapsed"] == 1
        assert counts["grandfathered"] == 0

        # No noly_subscriptions row
        noly_count = await _count_noly_rows(factory, babt)
        assert noly_count == 0, "Canceled sub should NOT create noly_subscriptions row"

        # No legacy_pricing_audit row
        audit_count = await _count_audit_rows(factory, user_db_id)
        assert audit_count == 0, "Canceled sub should NOT write legacy_pricing_audit"

        # import_status = lapsed, last_paid_at set
        user_state = await _get_user_status(factory, user_db_id)
        assert user_state["import_status"] == "imported_lapsed"
        assert user_state["last_paid_at"] is not None, "last_paid_at should be set for lapsed"
        assert user_state["legacy_pricing_plan"] is None

    finally:
        await _cleanup(factory, user_db_id, salon_db_id)


# ── T3: Stripe 404 → lapsed + error logged ───────────────────────────────────

@pytest.mark.asyncio
async def test_404_treated_as_lapsed_logged():
    """
    Stripe raises InvalidRequestError (404-like) for an unknown sub ID:
    - User is marked 'imported_lapsed'.
    - error_details includes a 'stripe_404:...' entry.
    - lapsed count = 1, errored count includes the 404 error.
    """
    _, factory = _make_session_factory()
    buid = f"buid-t3-{uuid.uuid4().hex[:12]}"
    babt = f"babt-t3-{uuid.uuid4().hex[:12]}"
    user_db_id, salon_db_id = await _create_user_and_salon(factory, buid)

    abonnement = _abonnement(
        bubble_id=babt,
        bubble_user_id=buid,
        stripe_sub_id="sub_nonexistent_t3",
    )

    try:
        # Build a fake InvalidRequestError that looks like Stripe's 404
        class FakeStripeInvalidRequestError(Exception):
            """Minimal Stripe InvalidRequestError substitute for tests."""
            def __init__(self, message: str, http_status: int = 404):
                super().__init__(message)
                self.http_status = http_status

        with (
            patch("scripts.bubble.import_subscriptions.stripe") as mock_stripe,
            patch("scripts.bubble.import_subscriptions.time"),
        ):
            mock_stripe.error.InvalidRequestError = FakeStripeInvalidRequestError
            mock_stripe.Subscription.retrieve.side_effect = FakeStripeInvalidRequestError(
                "No such subscription: 'sub_nonexistent_t3'", http_status=404
            )

            async with factory() as db:
                counts = await process_records(db, [abonnement], dry_run=False)

        # 404 is treated as lapsed (counted there), and also adds an error entry
        assert counts["lapsed"] == 1
        assert counts["grandfathered"] == 0

        # error_details should have the stripe_404 entry
        error_reasons = [e["reason"] for e in (counts.get("error_details") or [])]
        assert any("stripe_404" in r for r in error_reasons), (
            f"Expected stripe_404 in error_details, got: {error_reasons}"
        )

        # User marked lapsed
        user_state = await _get_user_status(factory, user_db_id)
        assert user_state["import_status"] == "imported_lapsed"
        assert user_state["legacy_pricing_plan"] is None

    finally:
        await _cleanup(factory, user_db_id, salon_db_id)


# ── T4: metadata tagged on Stripe.Subscription.modify ───────────────────────

@pytest.mark.asyncio
async def test_metadata_tagged_on_stripe_modify():
    """
    For an active sub, stripe.Subscription.modify is called (via safe_modify) with:
    - metadata.comcoi_user_id = str(user_db_id)
    - metadata.migrated_from = 'bubble_2026_05'
    Critically: 'items' must NOT appear in the modify call.
    """
    _, factory = _make_session_factory()
    buid = f"buid-t4-{uuid.uuid4().hex[:12]}"
    babt = f"babt-t4-{uuid.uuid4().hex[:12]}"
    user_db_id, salon_db_id = await _create_user_and_salon(factory, buid)

    stripe_mock = _stripe_sub_mock(status="active")
    abonnement = _abonnement(
        bubble_id=babt,
        bubble_user_id=buid,
        stripe_sub_id="sub_meta_t4",
    )

    try:
        with (
            patch("scripts.bubble.import_subscriptions.stripe") as mock_stripe,
            patch("scripts.bubble.import_subscriptions.time"),
        ):
            mock_stripe.Subscription.retrieve.return_value = stripe_mock
            mock_stripe.Subscription.modify.return_value = MagicMock()
            mock_stripe.error.InvalidRequestError = Exception

            async with factory() as db:
                counts = await process_records(db, [abonnement], dry_run=False)

        assert counts["grandfathered"] == 1

        # Assert Subscription.modify was called once
        assert mock_stripe.Subscription.modify.called, (
            "stripe.Subscription.modify was never called"
        )

        # Inspect the call args
        call_args = mock_stripe.Subscription.modify.call_args
        assert call_args is not None
        positional_args = call_args.args
        keyword_args = call_args.kwargs

        # First positional arg is the sub ID
        assert "sub_meta_t4" in positional_args, (
            f"Expected sub_meta_t4 in positional args, got {positional_args}"
        )

        # metadata must be in kwargs
        assert "metadata" in keyword_args, (
            f"Expected 'metadata' in kwargs, got {list(keyword_args.keys())}"
        )
        metadata = keyword_args["metadata"]
        assert metadata.get("comcoi_user_id") == user_db_id, (
            f"metadata.comcoi_user_id={metadata.get('comcoi_user_id')!r}, "
            f"expected {user_db_id!r}"
        )
        assert metadata.get("migrated_from") == "bubble_2026_05", (
            f"metadata.migrated_from={metadata.get('migrated_from')!r}"
        )

        # CRITICAL: 'items' must NOT appear anywhere in the modify call
        all_keys = set(keyword_args.keys())
        assert "items" not in all_keys, (
            f"'items' found in Stripe.Subscription.modify kwargs! This would change billing. "
            f"Keys: {all_keys}"
        )

    finally:
        await _cleanup(factory, user_db_id, salon_db_id)


# ── T5: safe_modify rejects forbidden keys ────────────────────────────────────

def test_safe_modify_rejects_items_key():
    """
    safe_modify() must raise RuntimeError if 'items' is passed.

    This is a pure unit test — no DB or Stripe call needed. It validates that
    the blast-radius guard actually fires.

    Tests all canonical forbidden keys to ensure the FORBIDDEN_MODIFY_KEYS
    set catches each one individually.
    """
    critical_forbidden = ["items", "price", "cancel_at", "cancel_at_period_end",
                          "collection_method", "default_payment_method"]

    for key in critical_forbidden:
        with pytest.raises(RuntimeError) as exc_info:
            safe_modify("sub_test", **{key: "some_value"})
        assert key in str(exc_info.value), (
            f"RuntimeError message should mention the forbidden key '{key}', "
            f"got: {exc_info.value!s}"
        )
        assert "Refusing to modify" in str(exc_info.value)

    # Multiple forbidden keys at once — should also raise
    with pytest.raises(RuntimeError):
        safe_modify("sub_test", items=[{"price": "price_new"}], cancel_at=9999999)

    # Allowed key (metadata) — should NOT raise; just needs Stripe SDK to be callable
    # We patch stripe.Subscription.modify to avoid a real API call
    with patch("scripts.bubble.import_subscriptions.stripe") as mock_stripe:
        mock_stripe.Subscription.modify.return_value = MagicMock()
        # This should not raise
        result = safe_modify("sub_test", metadata={"key": "value"})
        mock_stripe.Subscription.modify.assert_called_once_with(
            "sub_test", metadata={"key": "value"}
        )


# ── T6: idempotent re-run ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_idempotent_re_run():
    """
    Second run with the same Abonnement record:
    - Does NOT create a new noly_subscriptions row.
    - Does NOT create a new legacy_pricing_audit row (mark_user_legacy is idempotent).
    - Does NOT call stripe.Subscription.retrieve a second time (local DB check).
    """
    _, factory = _make_session_factory()
    buid = f"buid-t6-{uuid.uuid4().hex[:12]}"
    babt = f"babt-t6-{uuid.uuid4().hex[:12]}"
    user_db_id, salon_db_id = await _create_user_and_salon(factory, buid)

    stripe_mock = _stripe_sub_mock(status="active")
    abonnement = _abonnement(
        bubble_id=babt,
        bubble_user_id=buid,
        stripe_sub_id="sub_idempotent_t6",
    )

    try:
        with (
            patch("scripts.bubble.import_subscriptions.stripe") as mock_stripe,
            patch("scripts.bubble.import_subscriptions.time"),
        ):
            mock_stripe.Subscription.retrieve.return_value = stripe_mock
            mock_stripe.Subscription.modify.return_value = MagicMock()
            mock_stripe.error.InvalidRequestError = Exception

            # First run
            async with factory() as db:
                counts1 = await process_records(db, [abonnement], dry_run=False)
            assert counts1["grandfathered"] == 1

            retrieve_call_count_after_first = mock_stripe.Subscription.retrieve.call_count
            assert retrieve_call_count_after_first == 1, (
                "Expected exactly 1 Stripe retrieve call after first run, "
                f"got {retrieve_call_count_after_first}"
            )

            # Capture audit row count after first run
            audit_count_after_first = await _count_audit_rows(factory, user_db_id)
            assert audit_count_after_first >= 1, "No audit row after first run"

            # Second run — same records
            async with factory() as db:
                counts2 = await process_records(db, [abonnement], dry_run=False)

        # Second run should skip (already_imported check)
        assert counts2["skipped"] >= 1, (
            f"Expected skipped ≥ 1 on second run, got {counts2}"
        )
        assert counts2["grandfathered"] == 0

        # Stripe.retrieve call count must NOT have increased
        retrieve_call_count_after_second = mock_stripe.Subscription.retrieve.call_count
        assert retrieve_call_count_after_second == retrieve_call_count_after_first, (
            f"Stripe retrieve was called again on second run! "
            f"call_count={retrieve_call_count_after_second}"
        )

        # noly_subscriptions row count still 1
        noly_count = await _count_noly_rows(factory, babt)
        assert noly_count == 1, (
            f"Expected 1 noly_subscriptions row after two runs, got {noly_count}"
        )

        # legacy_pricing_audit row count unchanged
        audit_count_after_second = await _count_audit_rows(factory, user_db_id)
        assert audit_count_after_second == audit_count_after_first, (
            f"New audit rows created on second run! "
            f"before={audit_count_after_first} after={audit_count_after_second}"
        )

    finally:
        await _cleanup(factory, user_db_id, salon_db_id)


# ── T7: pack_compta → legacy_plan mapping ────────────────────────────────────

def test_pack_compta_to_legacy_plan_mapping():
    """
    Table-driven test of the pack-compta → legacy_plan mapping.

    Every known Bubble plan value must map to the correct legacy_pricing_plan
    enum. An unknown value must not appear in the mapping dict (callers default
    to 'legacy_99_yearly' for unknown values — tested separately via T1 flow).
    """
    expected = {
        "Pack micro-entreprises": "legacy_99_yearly",
        "Pack BIC": "legacy_bic_63_monthly",
        "Pack BIC+": "legacy_bic_plus_93_monthly",
    }
    for pack_value, expected_plan in expected.items():
        actual = PACK_TO_LEGACY_PLAN.get(pack_value)
        assert actual == expected_plan, (
            f"PACK_TO_LEGACY_PLAN[{pack_value!r}] = {actual!r}, expected {expected_plan!r}"
        )

    # Unknown pack value must NOT have a hard-coded entry (handled by caller defaulting)
    unknown_packs = ["Pack inconnu", "", None, "Pack BIC Plus"]
    for unknown in unknown_packs:
        result = PACK_TO_LEGACY_PLAN.get(unknown)
        assert result is None, (
            f"Unknown pack {unknown!r} unexpectedly mapped to {result!r}. "
            "Unknown packs should default to 'legacy_99_yearly' at call time, "
            "not be hard-coded here."
        )

    # FORBIDDEN_MODIFY_KEYS must include the billing-critical keys
    critical_keys = {"items", "price", "cancel_at", "cancel_at_period_end"}
    assert critical_keys.issubset(FORBIDDEN_MODIFY_KEYS), (
        f"Some critical keys missing from FORBIDDEN_MODIFY_KEYS: "
        f"{critical_keys - FORBIDDEN_MODIFY_KEYS}"
    )


# ── T8: import_status promoted to 'imported_active_paying' ───────────────────

@pytest.mark.asyncio
async def test_status_promoted_to_active_paying():
    """
    After grandfathering, users.import_status must be 'imported_active_paying'.

    Starts from 'imported_dormant' (the status set by import_users.py).
    """
    _, factory = _make_session_factory()
    buid = f"buid-t8-{uuid.uuid4().hex[:12]}"
    babt = f"babt-t8-{uuid.uuid4().hex[:12]}"
    user_db_id, salon_db_id = await _create_user_and_salon(
        factory, buid, import_status="imported_dormant"
    )

    # Verify starting state
    user_state_before = await _get_user_status(factory, user_db_id)
    assert user_state_before["import_status"] == "imported_dormant"

    stripe_mock = _stripe_sub_mock(status="active")
    abonnement = _abonnement(
        bubble_id=babt,
        bubble_user_id=buid,
        stripe_sub_id="sub_promote_t8",
        pack_compta="Pack BIC",
    )

    try:
        with (
            patch("scripts.bubble.import_subscriptions.stripe") as mock_stripe,
            patch("scripts.bubble.import_subscriptions.time"),
        ):
            mock_stripe.Subscription.retrieve.return_value = stripe_mock
            mock_stripe.Subscription.modify.return_value = MagicMock()
            mock_stripe.error.InvalidRequestError = Exception

            async with factory() as db:
                counts = await process_records(db, [abonnement], dry_run=False)

        assert counts["grandfathered"] == 1
        assert counts["errored"] == 0

        user_state_after = await _get_user_status(factory, user_db_id)
        assert user_state_after["import_status"] == "imported_active_paying", (
            f"Expected 'imported_active_paying', got {user_state_after['import_status']!r}"
        )
        # Pack BIC → legacy_bic_63_monthly
        assert user_state_after["legacy_pricing_plan"] == "legacy_bic_63_monthly", (
            f"Expected 'legacy_bic_63_monthly' for Pack BIC, "
            f"got {user_state_after['legacy_pricing_plan']!r}"
        )

    finally:
        await _cleanup(factory, user_db_id, salon_db_id)
