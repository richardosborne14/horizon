"""
TASK-2.17.4 — Import employees from Bubble User_salon: unit tests.

All tests call ``process_records()`` and ``synthesize_missing_dirigeants()``
directly. No Bubble API calls are made.

Self-contained pattern: each test seeds its own user + salon via raw SQL
and cleans up in a finally block.

Test coverage:
  T1. Gérant record → role_type='dirigeant', contract_type=NULL, name set.
  T2. Coiffeur record → role_type='salarie', contract_type='cdi'.
  T3. Record with null prénom/nom → fallback name 'Collaborateur', still imported.
  T4. Orphaned employee (Created By not in owner_map) → skipped + error logged.
  T5. Admin/test record (Created By = admin_user_communaute-coiffure_*) → skipped.
  T6. Re-running the import is idempotent; role_type set by user is preserved.
  T7. synthesize_missing_dirigeants creates a dirigeant for a salon with none.
"""

from __future__ import annotations

import uuid
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import settings
from scripts.bubble.import_employees import (
    process_records,
    synthesize_missing_dirigeants,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_session_factory():
    """Return a fresh session factory for this test."""
    engine = create_async_engine(settings.database_url, echo=False)
    return async_sessionmaker(engine, expire_on_commit=False)


def _user_salon_record(
    bubble_id: str | None = None,
    prenom: str | None = "Alice",
    nom: str | None = "Dupont",
    role: str = "Gérant",
    created_by: str | None = None,
    created_date: str = "2021-12-22T21:21:38.206Z",
) -> dict:
    """
    Build a minimal Bubble User_salon dict.

    Uses a random suffix to avoid clashes between test runs.
    """
    suffix = uuid.uuid4().hex[:8]
    return {
        "_id": bubble_id or f"bubble-emp-{suffix}",
        "prénom": prenom,
        "nom": nom,
        "role": role,
        "Created By": created_by or f"1638530707809x{suffix}",
        "Created Date": created_date,
        "Modified Date": "2024-03-01T10:00:00.000Z",
    }


async def _seed_user_and_salon(
    factory,
    bubble_user_id: str,
    name: str = "Test User",
) -> tuple[str, str]:
    """
    Insert a minimal user + salon row and return (user_db_id, salon_db_id).

    The salon has `bubble_salon_id` set so synthesize_missing_dirigeants includes it.
    """
    user_id = str(uuid.uuid4())
    salon_id = str(uuid.uuid4())
    bubble_salon_id = f"bs-{uuid.uuid4().hex[:8]}"

    async with factory() as db:
        await db.execute(
            text(
                "INSERT INTO users (id, email, password_hash, name, bubble_user_id) "
                "VALUES (:id, :email, 'placeholder', :name, :buid)"
            ),
            {"id": user_id, "email": f"{bubble_user_id}@t.invalid", "name": name, "buid": bubble_user_id},
        )
        await db.execute(
            text(
                "INSERT INTO salons "
                "(id, user_id, name, business_type, nb_employees, versement_liberatoire, acre, fiscal_year_start, bubble_salon_id) "
                "VALUES (:id, :uid, :name, NULL, 0, false, false, 1, :bsid)"
            ),
            {"id": salon_id, "uid": user_id, "name": "Salon Test", "bsid": bubble_salon_id},
        )
        await db.commit()
    return user_id, salon_id


async def _get_employee(factory, bubble_employee_id: str) -> dict | None:
    async with factory() as db:
        result = await db.execute(
            text("SELECT * FROM employees WHERE bubble_employee_id = :bid LIMIT 1"),
            {"bid": bubble_employee_id},
        )
        row = result.mappings().fetchone()
        return dict(row) if row else None


async def _cleanup(factory, bubble_employee_id: str, bubble_user_id: str) -> None:
    async with factory() as db:
        await db.execute(
            text("DELETE FROM employees WHERE bubble_employee_id = :bid"),
            {"bid": bubble_employee_id},
        )
        await db.execute(
            text("DELETE FROM salons WHERE user_id = (SELECT id FROM users WHERE bubble_user_id = :buid)"),
            {"buid": bubble_user_id},
        )
        await db.execute(
            text("DELETE FROM users WHERE bubble_user_id = :buid"),
            {"buid": bubble_user_id},
        )
        await db.commit()


async def _cleanup_user_and_salon(factory, bubble_user_id: str) -> None:
    """Clean up user and salon (when no employee was inserted)."""
    async with factory() as db:
        await db.execute(
            text("DELETE FROM salons WHERE user_id = (SELECT id FROM users WHERE bubble_user_id = :buid)"),
            {"buid": bubble_user_id},
        )
        await db.execute(
            text("DELETE FROM users WHERE bubble_user_id = :buid"),
            {"buid": bubble_user_id},
        )
        await db.commit()


async def _cleanup_employees_by_salon(factory, salon_id: str, bubble_user_id: str) -> None:
    """Clean up all employees for a salon and then the salon + user."""
    async with factory() as db:
        await db.execute(
            text("DELETE FROM employees WHERE salon_id = :sid"),
            {"sid": salon_id},
        )
        await db.execute(
            text("DELETE FROM salons WHERE id = :sid"),
            {"sid": salon_id},
        )
        await db.execute(
            text("DELETE FROM users WHERE bubble_user_id = :buid"),
            {"buid": bubble_user_id},
        )
        await db.commit()


# ── T1: Gérant → dirigeant, contract_type=NULL ────────────────────────────────

@pytest.mark.asyncio
async def test_gerant_becomes_dirigeant():
    """
    A User_salon record with role='Gérant' is imported as:
      - role_type = 'dirigeant'
      - contract_type = NULL (no contract for owner)
      - name = 'prénom nom'
      - hours_per_week = 35
    """
    factory = _make_session_factory()
    bubble_user_id = f"T1u-{uuid.uuid4().hex[:8]}"
    bubble_emp_id = f"T1e-{uuid.uuid4().hex[:8]}"

    _, salon_id = await _seed_user_and_salon(factory, bubble_user_id, "Marie Curie")
    owner_map = {bubble_user_id: salon_id}

    record = _user_salon_record(
        bubble_id=bubble_emp_id,
        prenom="Marie",
        nom="Curie",
        role="Gérant",
        created_by=bubble_user_id,
    )

    try:
        async with factory() as db:
            counts = await process_records(db, [record], owner_map, dry_run=False)

        assert counts["inserted"] == 1
        assert counts["errored"] == 0

        emp = await _get_employee(factory, bubble_emp_id)
        assert emp is not None
        assert emp["role_type"] == "dirigeant"
        assert emp["contract_type"] is None, "Dirigeant should have no contract_type"
        assert emp["name"] == "Marie Curie"
        assert str(emp["salon_id"]) == salon_id
        from decimal import Decimal
        assert Decimal(str(emp["hours_per_week"])) == Decimal("35")
    finally:
        await _cleanup(factory, bubble_emp_id, bubble_user_id)


# ── T2: Coiffeur → salarie, contract_type='cdi' ───────────────────────────────

@pytest.mark.asyncio
async def test_coiffeur_becomes_salarie():
    """
    A User_salon record with role='Coiffeur' is imported as:
      - role_type = 'salarie'
      - contract_type = 'cdi' (default — no contract data in Bubble)
    """
    factory = _make_session_factory()
    bubble_user_id = f"T2u-{uuid.uuid4().hex[:8]}"
    bubble_emp_id = f"T2e-{uuid.uuid4().hex[:8]}"

    _, salon_id = await _seed_user_and_salon(factory, bubble_user_id)
    owner_map = {bubble_user_id: salon_id}

    record = _user_salon_record(
        bubble_id=bubble_emp_id,
        prenom="Jean",
        nom="Martin",
        role="Coiffeur",
        created_by=bubble_user_id,
    )

    try:
        async with factory() as db:
            counts = await process_records(db, [record], owner_map, dry_run=False)

        assert counts["inserted"] == 1

        emp = await _get_employee(factory, bubble_emp_id)
        assert emp is not None
        assert emp["role_type"] == "salarie"
        assert emp["contract_type"] == "cdi"
    finally:
        await _cleanup(factory, bubble_emp_id, bubble_user_id)


# ── T3: null prénom and nom → fallback 'Collaborateur' ───────────────────────

@pytest.mark.asyncio
async def test_null_name_falls_back_to_collaborateur():
    """
    An employee record with null prénom and null nom is still imported.
    The name falls back to 'Collaborateur'.
    """
    factory = _make_session_factory()
    bubble_user_id = f"T3u-{uuid.uuid4().hex[:8]}"
    bubble_emp_id = f"T3e-{uuid.uuid4().hex[:8]}"

    _, salon_id = await _seed_user_and_salon(factory, bubble_user_id)
    owner_map = {bubble_user_id: salon_id}

    record = _user_salon_record(
        bubble_id=bubble_emp_id,
        prenom=None,
        nom=None,
        role="Coiffeur",
        created_by=bubble_user_id,
    )

    try:
        async with factory() as db:
            counts = await process_records(db, [record], owner_map, dry_run=False)

        assert counts["inserted"] == 1, "Employee with null name should still be imported"

        emp = await _get_employee(factory, bubble_emp_id)
        assert emp is not None
        assert emp["name"] == "Collaborateur"
    finally:
        await _cleanup(factory, bubble_emp_id, bubble_user_id)


# ── T4: orphaned employee skipped + error logged ──────────────────────────────

@pytest.mark.asyncio
async def test_orphaned_employee_is_skipped():
    """
    A User_salon record whose Created By has no entry in owner_map is skipped.
    The error_log entry has reason='orphan_employee'.
    """
    factory = _make_session_factory()
    bubble_emp_id = f"T4e-{uuid.uuid4().hex[:8]}"
    unknown_user_id = f"unknown-{uuid.uuid4().hex[:8]}"

    record = _user_salon_record(
        bubble_id=bubble_emp_id,
        prenom="Orphan",
        nom="Employee",
        role="Coiffeur",
        created_by=unknown_user_id,
    )
    owner_map: dict[str, str] = {}  # empty — no known owners

    async with factory() as db:
        counts = await process_records(db, [record], owner_map, dry_run=False)

    assert counts["skipped"] == 1
    assert counts["inserted"] == 0

    emp = await _get_employee(factory, bubble_emp_id)
    assert emp is None, "No employee row should exist for an orphaned record"

    # Verify error log
    async with factory() as db:
        result = await db.execute(
            text(
                "SELECT error_log FROM bubble_import_runs "
                "WHERE script_name = 'import_employees' "
                "ORDER BY started_at DESC LIMIT 1"
            )
        )
        row = result.fetchone()
    assert row is not None
    error_log = row[0] or []
    assert any(
        e.get("reason") == "orphan_employee"
        for e in (error_log if isinstance(error_log, list) else [])
    ), f"Expected orphan_employee in error_log, got: {error_log}"


# ── T5: admin/test record skipped ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_employee_is_skipped():
    """
    Records with Created By = 'admin_user_communaute-coiffure_*' are skipped.
    Even if a salon ID is in the owner_map, the record is not inserted.
    """
    factory = _make_session_factory()
    bubble_user_id = f"T5u-{uuid.uuid4().hex[:8]}"
    bubble_emp_id = f"T5e-{uuid.uuid4().hex[:8]}"

    _, salon_id = await _seed_user_and_salon(factory, bubble_user_id)
    owner_map = {bubble_user_id: salon_id}

    record = _user_salon_record(
        bubble_id=bubble_emp_id,
        prenom="Admin",
        nom="Demo",
        role="Gérant",
        created_by="admin_user_communaute-coiffure_live",  # admin — skip
    )
    # Even if the owner_map happens to have this key, it should be filtered
    owner_map["admin_user_communaute-coiffure_live"] = salon_id

    try:
        async with factory() as db:
            counts = await process_records(db, [record], owner_map, dry_run=False)

        assert counts["skipped"] == 1
        assert counts["inserted"] == 0

        emp = await _get_employee(factory, bubble_emp_id)
        assert emp is None
    finally:
        await _cleanup_user_and_salon(factory, bubble_user_id)


# ── T6: idempotency — role_type preserved ─────────────────────────────────────

@pytest.mark.asyncio
async def test_import_is_idempotent_and_preserves_role():
    """
    Running the import twice:
      - Does not create duplicate rows.
      - Does NOT overwrite role_type if the user changed it between runs.
    """
    factory = _make_session_factory()
    bubble_user_id = f"T6u-{uuid.uuid4().hex[:8]}"
    bubble_emp_id = f"T6e-{uuid.uuid4().hex[:8]}"

    _, salon_id = await _seed_user_and_salon(factory, bubble_user_id)
    owner_map = {bubble_user_id: salon_id}

    record = _user_salon_record(
        bubble_id=bubble_emp_id,
        prenom="Idempotent",
        nom="Test",
        role="Coiffeur",
        created_by=bubble_user_id,
    )

    try:
        # First run
        async with factory() as db:
            counts1 = await process_records(db, [record], owner_map, dry_run=False)
        assert counts1["inserted"] == 1

        # Simulate user changing role_type to 'dirigeant' via the app
        async with factory() as db:
            await db.execute(
                text(
                    "UPDATE employees SET role_type = 'dirigeant' "
                    "WHERE bubble_employee_id = :bid"
                ),
                {"bid": bubble_emp_id},
            )
            await db.commit()

        # Second run
        async with factory() as db:
            counts2 = await process_records(db, [record], owner_map, dry_run=False)
        assert counts2["inserted"] == 0
        assert counts2["updated"] == 1

        # Row count unchanged
        async with factory() as db:
            result = await db.execute(
                text("SELECT COUNT(*) FROM employees WHERE bubble_employee_id = :bid"),
                {"bid": bubble_emp_id},
            )
            count = result.scalar_one()
        assert count == 1

        # role_type must NOT have been reset to 'salarie'
        emp = await _get_employee(factory, bubble_emp_id)
        assert emp["role_type"] == "dirigeant", (
            f"role_type was overwritten on second run! got {emp['role_type']!r}"
        )
    finally:
        await _cleanup(factory, bubble_emp_id, bubble_user_id)


# ── T7: synthesize_missing_dirigeants ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_synthesize_creates_dirigeant_when_none_exists():
    """
    A salon that has employees (e.g. a Coiffeur) but NO dirigeant gets a
    synthesised Gérant row with:
      - role_type = 'dirigeant'
      - bubble_employee_id = 'synthesised:{salon_id}'
      - name = salon owner's display name
    Running synthesize a second time does NOT create a duplicate.
    """
    factory = _make_session_factory()
    bubble_user_id = f"T7u-{uuid.uuid4().hex[:8]}"
    bubble_emp_id = f"T7e-{uuid.uuid4().hex[:8]}"

    _, salon_id = await _seed_user_and_salon(factory, bubble_user_id, "Sophie Marceau")
    owner_map = {bubble_user_id: salon_id}

    # Seed only a Coiffeur (no Gérant) so synthesize should fire
    record = _user_salon_record(
        bubble_id=bubble_emp_id,
        prenom="Sophie",
        nom="Collaboratrice",
        role="Coiffeur",
        created_by=bubble_user_id,
    )

    try:
        async with factory() as db:
            await process_records(db, [record], owner_map, dry_run=False)

        # Verify: no dirigeant yet
        async with factory() as db:
            result = await db.execute(
                text(
                    "SELECT COUNT(*) FROM employees "
                    "WHERE salon_id = :sid AND role_type = 'dirigeant'"
                ),
                {"sid": salon_id},
            )
            dirigeant_count = result.scalar_one()
        assert dirigeant_count == 0, "Should have no dirigeant before synthesize"

        # Run synthesize
        async with factory() as db:
            synth = await synthesize_missing_dirigeants(db, dry_run=False)
        assert synth["synthesized"] >= 1, "Expected at least one synthesized dirigeant"

        synth_key = f"synthesised:{salon_id}"
        emp = await _get_employee(factory, synth_key)
        assert emp is not None, "Synthesized dirigeant row not found"
        assert emp["role_type"] == "dirigeant"
        assert emp["name"] == "Sophie Marceau"  # owner's display name
        assert str(emp["salon_id"]) == salon_id

        # Run synthesize again — should not create a duplicate
        async with factory() as db:
            synth2 = await synthesize_missing_dirigeants(db, dry_run=False)
        assert synth2["synthesized"] == 0, (
            "Second synthesize should not create a new dirigeant"
        )

        async with factory() as db:
            result = await db.execute(
                text(
                    "SELECT COUNT(*) FROM employees "
                    "WHERE salon_id = :sid AND role_type = 'dirigeant'"
                ),
                {"sid": salon_id},
            )
            final_count = result.scalar_one()
        assert final_count == 1, f"Expected 1 dirigeant, got {final_count}"
    finally:
        await _cleanup_employees_by_salon(factory, salon_id, bubble_user_id)
