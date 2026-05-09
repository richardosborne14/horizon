"""
TASK-2.17.2 — Import users from Bubble: unit tests.

All five tests call ``process_records()`` directly with fixture Bubble records.
No network calls to the Bubble API are made.

Tests follow the self-contained pattern: each creates its own AsyncSession
via ``create_async_engine / async_sessionmaker`` and cleans up after itself
(see test_grandfathering_schema.py for the precedent).

Test coverage:
  T1. User is created with a bcrypt placeholder password and all Bubble metadata.
  T2. Re-running the import (same records) does not create duplicates and
      does NOT change the password_hash.
  T3. A Bubble record with no nested email is counted as errored and skipped.
  T4. Email collision: pre-existing native user blocks the import record.
  T5. dry_run=True leaves the users table untouched but still records
      inserted=N in bubble_import_runs.
"""

from __future__ import annotations

import uuid
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import settings
from scripts.bubble.import_users import process_records


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_session_factory():
    """Return a fresh (engine, factory) pair for this test invocation."""
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


def _bubble_user(
    bubble_id: str | None = None,
    email: str | None = None,
    first_name: str = "Jean",
    last_name: str = "Dupont",
    stripe_customer_id: str | None = None,
    created_date: str = "2023-04-25T16:11:23.480Z",
) -> dict:
    """
    Build a minimal Bubble User dict matching the shape returned by the API.

    Uses a random suffix by default so parallel test runs don't clash.
    """
    suffix = uuid.uuid4().hex[:8]
    return {
        "_id": bubble_id or f"bubble-test-{suffix}",
        "authentication": {
            "email": {
                "email": email or f"test-{suffix}@bubbleimport.test",
            }
        },
        "First Name": first_name,
        "Last Name": last_name,
        "StripeCustomerID": stripe_customer_id,
        "Created Date": created_date,
        "Modified Date": "2024-02-15T16:01:41.330Z",
    }


async def _get_user_by_email(db, email: str) -> dict | None:
    """Return the users row for email, or None."""
    result = await db.execute(
        text("SELECT * FROM users WHERE email = :e LIMIT 1"),
        {"e": email},
    )
    row = result.mappings().fetchone()
    return dict(row) if row else None


async def _count_users_with_bubble_id(db, bubble_id: str) -> int:
    result = await db.execute(
        text("SELECT COUNT(*) FROM users WHERE bubble_user_id = :bid"),
        {"bid": bubble_id},
    )
    return result.scalar_one()


async def _cleanup_user_by_email(factory, email: str) -> None:
    """Delete test user row by email (final teardown)."""
    async with factory() as db:
        await db.execute(
            text("DELETE FROM users WHERE email = :e"),
            {"e": email},
        )
        await db.commit()


async def _cleanup_user_by_bubble_id(factory, bubble_id: str) -> None:
    """Delete test user row by bubble_user_id (final teardown)."""
    async with factory() as db:
        await db.execute(
            text("DELETE FROM users WHERE bubble_user_id = :bid"),
            {"bid": bubble_id},
        )
        await db.commit()


# ── T1: creates user with placeholder password and all metadata fields ─────────

@pytest.mark.asyncio
async def test_import_creates_user_with_placeholder_password():
    """
    Importing a valid Bubble User record creates a row with:
      - password_hash starting with '$2b$' (bcrypt)
      - bubble_user_id, import_source, import_status='imported_dormant',
        import_completion_step='welcome' all set correctly.
      - name assembled from First Name + Last Name.
      - stripe_customer_id preserved.
    """
    _, factory = _make_session_factory()
    record = _bubble_user(
        bubble_id="T1-bubble-test-001",
        email="t1-user@bubbleimport.test",
        first_name="Marie",
        last_name="Curie",
        stripe_customer_id="cus_test_t1",
    )

    try:
        async with factory() as db:
            counts = await process_records(db, [record], dry_run=False)

        assert counts["inserted"] == 1
        assert counts["errored"] == 0

        async with factory() as db:
            user = await _get_user_by_email(db, "t1-user@bubbleimport.test")

        assert user is not None, "User row not found after import"
        assert user["password_hash"].startswith("$2b$"), (
            f"Expected bcrypt hash, got: {user['password_hash'][:10]}..."
        )
        assert user["bubble_user_id"] == "T1-bubble-test-001"
        assert user["import_source"] == "bubble_migration_2026_05"
        assert user["import_status"] == "imported_dormant"
        assert user["import_completion_step"] == "welcome"
        assert user["name"] == "Marie Curie"
        assert user["stripe_customer_id"] == "cus_test_t1"
        assert user["role"] == "user"
        assert user["onboarding_completed"] is False
        assert user["last_login_at"] is None
    finally:
        await _cleanup_user_by_bubble_id(factory, "T1-bubble-test-001")


# ── T2: idempotent — re-running does not duplicate and does not change password ─

@pytest.mark.asyncio
async def test_import_is_idempotent():
    """
    Running the import twice with the same records:
      - Does not create duplicate rows.
      - Does NOT overwrite the password_hash.
    """
    _, factory = _make_session_factory()
    record = _bubble_user(
        bubble_id="T2-bubble-idempotent-001",
        email="t2-idempotent@bubbleimport.test",
        first_name="Louis",
        last_name="Pasteur",
    )

    try:
        # First run
        async with factory() as db:
            counts1 = await process_records(db, [record], dry_run=False)
        assert counts1["inserted"] == 1

        # Capture password hash after first run
        async with factory() as db:
            user_after_first = await _get_user_by_email(db, "t2-idempotent@bubbleimport.test")
        assert user_after_first is not None
        hash_after_first = user_after_first["password_hash"]

        # Second run — same records
        async with factory() as db:
            counts2 = await process_records(db, [record], dry_run=False)
        assert counts2["inserted"] == 0
        assert counts2["updated"] == 1  # ON CONFLICT DO UPDATE path

        # Row count unchanged
        async with factory() as db:
            count = await _count_users_with_bubble_id(db, "T2-bubble-idempotent-001")
        assert count == 1, "Expected exactly one row after two runs"

        # Password hash must not have changed
        async with factory() as db:
            user_after_second = await _get_user_by_email(db, "t2-idempotent@bubbleimport.test")
        assert user_after_second["password_hash"] == hash_after_first, (
            "password_hash was overwritten on second import run!"
        )
    finally:
        await _cleanup_user_by_bubble_id(factory, "T2-bubble-idempotent-001")


# ── T3: missing email — skipped + error logged ────────────────────────────────

@pytest.mark.asyncio
async def test_import_handles_missing_email():
    """
    A Bubble record with no nested authentication.email.email path:
      - Is counted as errored.
      - Does NOT create a users row.
    """
    _, factory = _make_session_factory()

    # Record with completely missing authentication block
    record_no_auth = {
        "_id": "T3-bubble-noemail-001",
        "First Name": "Ghost",
        "Last Name": "User",
        "Created Date": "2023-06-01T10:00:00.000Z",
        # No 'authentication' key at all
    }

    # Record where nested email is empty string
    record_empty_email = {
        "_id": "T3-bubble-noemail-002",
        "authentication": {"email": {"email": ""}},
        "First Name": "Empty",
        "Last Name": "Email",
        "Created Date": "2023-06-01T10:00:00.000Z",
    }

    async with factory() as db:
        counts = await process_records(db, [record_no_auth, record_empty_email], dry_run=False)

    assert counts["errored"] == 2, f"Expected 2 errors, got {counts['errored']}"
    assert counts["inserted"] == 0

    # Verify no ghost rows were created
    async with factory() as db:
        n1 = await _count_users_with_bubble_id(db, "T3-bubble-noemail-001")
        n2 = await _count_users_with_bubble_id(db, "T3-bubble-noemail-002")
    assert n1 == 0
    assert n2 == 0


# ── T4: email collision — native user protected ───────────────────────────────

@pytest.mark.asyncio
async def test_import_handles_email_collision():
    """
    A Bubble record whose email already belongs to a native user
    (bubble_user_id IS NULL) is skipped. The native user row is untouched.
    """
    _, factory = _make_session_factory()
    native_email = f"t4-native-{uuid.uuid4().hex[:8]}@bubbleimport.test"
    bubble_id = f"T4-bubble-collision-{uuid.uuid4().hex[:8]}"

    # Pre-seed a native user with the same email (no bubble_user_id)
    async with factory() as db:
        await db.execute(
            text(
                "INSERT INTO users (email, password_hash, name) "
                "VALUES (:e, 'native_hash_unchanged', 'Native User')"
            ),
            {"e": native_email},
        )
        await db.commit()

    # Bubble record that would collide on email
    record = _bubble_user(
        bubble_id=bubble_id,
        email=native_email,
        first_name="Bubble",
        last_name="Intruder",
    )

    try:
        async with factory() as db:
            counts = await process_records(db, [record], dry_run=False)

        # Should be skipped (logged as error per spec)
        assert counts["skipped"] == 1
        assert counts["inserted"] == 0

        # Native user row must be untouched
        async with factory() as db:
            native = await _get_user_by_email(db, native_email)
        assert native is not None
        assert native["password_hash"] == "native_hash_unchanged", (
            "Native user password_hash was overwritten!"
        )
        assert native["bubble_user_id"] is None, (
            "Native user bubble_user_id was set — should remain NULL"
        )
    finally:
        await _cleanup_user_by_email(factory, native_email)


# ── T5: dry_run writes nothing but still counts ───────────────────────────────

@pytest.mark.asyncio
async def test_import_dry_run_writes_nothing():
    """
    dry_run=True with 5 fresh Bubble records:
      - Does NOT insert any users rows.
      - Records inserted=5 in bubble_import_runs (counts are tracked in dry-run).
      - The bubble_import_runs row itself has dry_run=True.
    """
    _, factory = _make_session_factory()

    # 5 unique records that don't exist in the DB
    records = [
        _bubble_user(
            bubble_id=f"T5-dryrun-{i:03d}",
            email=f"t5-dryrun-{i}-{uuid.uuid4().hex[:6]}@bubbleimport.test",
        )
        for i in range(5)
    ]

    async with factory() as db:
        # Count users before dry-run
        before_result = await db.execute(text("SELECT COUNT(*) FROM users"))
        count_before = before_result.scalar_one()

        counts = await process_records(db, records, dry_run=True)

        # Count users after dry-run — must not have changed
        after_result = await db.execute(text("SELECT COUNT(*) FROM users"))
        count_after = after_result.scalar_one()

    assert count_after == count_before, (
        f"users table changed during dry-run! before={count_before} after={count_after}"
    )

    # Counters should show 5 would-be-inserted
    assert counts["inserted"] == 5, f"Expected inserted=5, got {counts['inserted']}"
    assert counts["errored"] == 0

    # Verify the bubble_import_runs row was created with dry_run=True
    # and inserted counter = 5
    async with factory() as db:
        run_result = await db.execute(
            text(
                "SELECT dry_run, inserted FROM bubble_import_runs "
                "WHERE script_name = 'import_users' "
                "ORDER BY started_at DESC LIMIT 1"
            )
        )
        run_row = run_result.fetchone()

    assert run_row is not None, "No bubble_import_runs row found"
    assert run_row[0] is True, "bubble_import_runs.dry_run should be True"
    assert run_row[1] == 5, f"bubble_import_runs.inserted should be 5, got {run_row[1]}"
