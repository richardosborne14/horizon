"""
TASK-2.17.3 — Import salons from Bubble: unit tests.

All tests call ``process_records()`` directly with fixture Bubble records and a
manually-constructed ``owner_map``. No Bubble API calls are made.

Tests follow the self-contained pattern (same as test_task_2_17_2_import_users.py):
each test creates its own fixtures via raw SQL and cleans up in a finally block.

Test coverage:
  T1. Salon is created with owner FK, business_type NULL, bubble_establishment_type set.
  T2. Orphaned salon (no entry in owner_map) is skipped + error logged.
  T3. Admin/test salon (Created By = admin_user_communaute-coiffure_*) is skipped.
  T4. salon_config row is auto-created with Eric's industry defaults.
  T5. Invalid SIRET (wrong length) → SIRET stays NULL, salon still created.
  T6. validé == False → deleted_at IS NOT NULL on the imported salon.
  T7. Re-running the import is idempotent; business_type chosen via wizard is preserved.
"""

from __future__ import annotations

import uuid
import pytest
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import settings
from scripts.bubble.import_salons import process_records


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_session_factory():
    """Return a fresh (engine, factory) pair for this test invocation."""
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


def _bubble_salon(
    bubble_id: str | None = None,
    name: str = "Salon Test",
    type_salon: str | None = "Coiffure mixte",
    siret: str | None = None,
    adresse: dict | None = None,
    created_by: str | None = None,
    valide: bool = True,
    created_date: str = "2023-05-10T09:00:00.000Z",
) -> dict:
    """
    Build a minimal Bubble Salon dict matching the shape returned by the API.

    Uses a random suffix by default so parallel test runs don't clash.
    """
    suffix = uuid.uuid4().hex[:8]
    record: dict = {
        "_id": bubble_id or f"bubble-salon-{suffix}",
        "name": name,
        "type_Salon": type_salon,
        "SIRET": siret,
        "adresse": adresse,
        "Created By": created_by or f"1615241986607x{suffix}",  # real-looking user ID
        "validé": valide,
        "Created Date": created_date,
        "Modified Date": "2024-03-01T10:00:00.000Z",
    }
    return record


async def _seed_user(factory, bubble_user_id: str, name: str = "Test User") -> str:
    """
    Insert a minimal imported-user row and return its DB UUID string.

    Uses a raw INSERT so we bypass the router's SalonCreate validation.
    Returns the str(UUID) of the created user.
    """
    user_id = str(uuid.uuid4())
    async with factory() as db:
        await db.execute(
            text(
                "INSERT INTO users "
                "(id, email, password_hash, name, bubble_user_id) "
                "VALUES (:id, :email, 'placeholder_hash', :name, :buid)"
            ),
            {
                "id": user_id,
                "email": f"{bubble_user_id}@import-test.invalid",
                "name": name,
                "buid": bubble_user_id,
            },
        )
        await db.commit()
    return user_id


async def _get_salon_by_bubble_id(factory, bubble_salon_id: str) -> dict | None:
    """Return the salons row for bubble_salon_id, or None."""
    async with factory() as db:
        result = await db.execute(
            text("SELECT * FROM salons WHERE bubble_salon_id = :bid LIMIT 1"),
            {"bid": bubble_salon_id},
        )
        row = result.mappings().fetchone()
        return dict(row) if row else None


async def _get_salon_config(factory, salon_id: str) -> dict | None:
    """Return the salon_config row for salon_id, or None."""
    async with factory() as db:
        result = await db.execute(
            text("SELECT * FROM salon_config WHERE salon_id = :sid LIMIT 1"),
            {"sid": salon_id},
        )
        row = result.mappings().fetchone()
        return dict(row) if row else None


async def _cleanup(factory, bubble_salon_id: str, bubble_user_id: str) -> None:
    """Delete the test salon and user rows created during a test."""
    async with factory() as db:
        await db.execute(
            text("DELETE FROM salons WHERE bubble_salon_id = :bid"),
            {"bid": bubble_salon_id},
        )
        await db.execute(
            text("DELETE FROM users WHERE bubble_user_id = :buid"),
            {"buid": bubble_user_id},
        )
        await db.commit()


async def _cleanup_user_only(factory, bubble_user_id: str) -> None:
    """Delete test user only (when salon was skipped)."""
    async with factory() as db:
        await db.execute(
            text("DELETE FROM users WHERE bubble_user_id = :buid"),
            {"buid": bubble_user_id},
        )
        await db.commit()


# ── T1: creates salon with owner FK + correct metadata ────────────────────────

@pytest.mark.asyncio
async def test_import_creates_salon_with_owner():
    """
    A valid Bubble Salon record creates a salons row with:
      - user_id pointing to the imported owner.
      - business_type IS NULL (forces first-login wizard).
      - bubble_establishment_type populated from Salon.type_Salon.
      - name and address preserved.
      - bubble_salon_id set for idempotency.
    """
    _, factory = _make_session_factory()
    bubble_user_id = f"T1-user-{uuid.uuid4().hex[:8]}"
    bubble_salon_id = f"T1-salon-{uuid.uuid4().hex[:8]}"

    user_db_id = await _seed_user(factory, bubble_user_id, "Marie Curie")
    owner_map = {bubble_salon_id: user_db_id}

    record = _bubble_salon(
        bubble_id=bubble_salon_id,
        name="Salon Marie",
        type_salon="Barbier",
        adresse={"address": "12 rue de la Paix, Paris", "lat": 48.87, "lng": 2.33},
    )

    try:
        async with factory() as db:
            counts = await process_records(db, [record], owner_map, dry_run=False)

        assert counts["inserted"] == 1
        assert counts["errored"] == 0

        salon = await _get_salon_by_bubble_id(factory, bubble_salon_id)
        assert salon is not None, "Salon row not found after import"
        assert str(salon["user_id"]) == user_db_id
        assert salon["business_type"] is None, "business_type should be NULL for imported salons"
        assert salon["bubble_establishment_type"] == "Barbier"
        assert salon["name"] == "Salon Marie"
        assert salon["address"] == "12 rue de la Paix, Paris"
        assert salon["bubble_salon_id"] == bubble_salon_id
        assert salon["deleted_at"] is None, "Active salon should not be soft-deleted"
    finally:
        await _cleanup(factory, bubble_salon_id, bubble_user_id)


# ── T2: orphaned salon skipped + error logged ─────────────────────────────────

@pytest.mark.asyncio
async def test_import_skips_orphaned_salon():
    """
    A Bubble Salon whose ID is not in the owner_map (no User.mon_salon match)
    is counted as skipped and its bubble_id appears in error_log with
    reason 'orphan_salon'.
    """
    _, factory = _make_session_factory()
    bubble_salon_id = f"T2-orphan-{uuid.uuid4().hex[:8]}"

    record = _bubble_salon(
        bubble_id=bubble_salon_id,
        name="Salon Orphelin",
    )
    # owner_map deliberately empty — no owner
    owner_map: dict[str, str] = {}

    async with factory() as db:
        counts = await process_records(db, [record], owner_map, dry_run=False)

    assert counts["skipped"] == 1
    assert counts["inserted"] == 0

    # Verify no salon row was created
    salon = await _get_salon_by_bubble_id(factory, bubble_salon_id)
    assert salon is None, "No salon row should be created for an orphaned salon"

    # Verify error_log has the orphan_salon entry
    async with factory() as db:
        result = await db.execute(
            text(
                "SELECT error_log FROM bubble_import_runs "
                "WHERE script_name = 'import_salons' "
                "ORDER BY started_at DESC LIMIT 1"
            )
        )
        row = result.fetchone()
    assert row is not None
    error_log = row[0]
    assert any(
        e.get("reason") == "orphan_salon"
        for e in (error_log if isinstance(error_log, list) else [])
    ), f"Expected orphan_salon in error_log, got: {error_log}"


# ── T3: admin/test salon skipped ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_import_skips_admin_test_salons():
    """
    Salons with Created By starting with 'admin_user_communaute-coiffure'
    (both _live and _test) are counted as skipped and not inserted.
    """
    _, factory = _make_session_factory()
    bubble_user_id = f"T3-user-{uuid.uuid4().hex[:8]}"
    bubble_salon_id_live = f"T3-admin-live-{uuid.uuid4().hex[:8]}"
    bubble_salon_id_test = f"T3-admin-test-{uuid.uuid4().hex[:8]}"

    user_db_id = await _seed_user(factory, bubble_user_id)
    # Even if the salons appear in owner_map, they should be filtered out
    owner_map = {
        bubble_salon_id_live: user_db_id,
        bubble_salon_id_test: user_db_id,
    }

    records = [
        _bubble_salon(
            bubble_id=bubble_salon_id_live,
            name="Admin Salon Live",
            created_by="admin_user_communaute-coiffure_live",
        ),
        _bubble_salon(
            bubble_id=bubble_salon_id_test,
            name="Admin Salon Test",
            created_by="admin_user_communaute-coiffure_test",
        ),
    ]

    try:
        async with factory() as db:
            counts = await process_records(db, records, owner_map, dry_run=False)

        assert counts["skipped"] == 2
        assert counts["inserted"] == 0

        # Neither row should exist in the DB
        salon_live = await _get_salon_by_bubble_id(factory, bubble_salon_id_live)
        salon_test = await _get_salon_by_bubble_id(factory, bubble_salon_id_test)
        assert salon_live is None
        assert salon_test is None
    finally:
        await _cleanup_user_only(factory, bubble_user_id)


# ── T4: salon_config auto-created with Eric's defaults ───────────────────────

@pytest.mark.asyncio
async def test_import_creates_salon_config_with_defaults():
    """
    After a successful salon import, a salon_config row exists with
    Eric's industry-default values:
      - jours_ouverture_semaine = 5
      - taux_charges_fixes = 0.25
      - taux_produits = 0.10
      - type_exploitant = 'auto_entrepreneur'
    """
    _, factory = _make_session_factory()
    bubble_user_id = f"T4-user-{uuid.uuid4().hex[:8]}"
    bubble_salon_id = f"T4-salon-{uuid.uuid4().hex[:8]}"

    user_db_id = await _seed_user(factory, bubble_user_id)
    owner_map = {bubble_salon_id: user_db_id}

    record = _bubble_salon(bubble_id=bubble_salon_id, name="Salon Config Test")

    try:
        async with factory() as db:
            counts = await process_records(db, [record], owner_map, dry_run=False)

        assert counts["inserted"] == 1

        salon = await _get_salon_by_bubble_id(factory, bubble_salon_id)
        assert salon is not None

        config = await _get_salon_config(factory, str(salon["id"]))
        assert config is not None, "salon_config row should be auto-created"

        # Verify Eric's default values
        assert Decimal(str(config["jours_ouverture_semaine"])) == Decimal("5"), (
            f"Expected jours_ouverture_semaine=5, got {config['jours_ouverture_semaine']}"
        )
        assert Decimal(str(config["taux_charges_fixes"])) == Decimal("0.25"), (
            f"Expected taux_charges_fixes=0.25, got {config['taux_charges_fixes']}"
        )
        assert Decimal(str(config["taux_produits"])) == Decimal("0.10"), (
            f"Expected taux_produits=0.10, got {config['taux_produits']}"
        )
        assert config["type_exploitant"] == "auto_entrepreneur", (
            f"Expected type_exploitant=auto_entrepreneur, got {config['type_exploitant']}"
        )
    finally:
        await _cleanup(factory, bubble_salon_id, bubble_user_id)


# ── T5: invalid SIRET → NULL but salon still imported ────────────────────────

@pytest.mark.asyncio
async def test_import_skips_invalid_siret():
    """
    A salon with a SIRET that is not exactly 14 digits after whitespace
    stripping is imported successfully — but with siret=NULL. The import
    is NOT rejected because of the bad SIRET.
    """
    _, factory = _make_session_factory()
    bubble_user_id = f"T5-user-{uuid.uuid4().hex[:8]}"
    bubble_salon_id = f"T5-siret-{uuid.uuid4().hex[:8]}"

    user_db_id = await _seed_user(factory, bubble_user_id)
    owner_map = {bubble_salon_id: user_db_id}

    record = _bubble_salon(
        bubble_id=bubble_salon_id,
        name="Salon SIRET Test",
        siret="123 456",  # too short — whitespace-stripped = 6 digits
    )

    try:
        async with factory() as db:
            counts = await process_records(db, [record], owner_map, dry_run=False)

        assert counts["inserted"] == 1, "Salon should be imported despite invalid SIRET"

        salon = await _get_salon_by_bubble_id(factory, bubble_salon_id)
        assert salon is not None
        assert salon["siret"] is None, (
            f"Expected siret=None for invalid SIRET, got {salon['siret']!r}"
        )
    finally:
        await _cleanup(factory, bubble_salon_id, bubble_user_id)


# ── T6: validé=False → deleted_at IS NOT NULL ────────────────────────────────

@pytest.mark.asyncio
async def test_import_marks_invalid_salons_as_deleted():
    """
    A Bubble Salon with ``validé=False`` is imported but immediately soft-deleted
    (deleted_at IS NOT NULL). The salon row exists so data is preserved.
    """
    _, factory = _make_session_factory()
    bubble_user_id = f"T6-user-{uuid.uuid4().hex[:8]}"
    bubble_salon_id = f"T6-deleted-{uuid.uuid4().hex[:8]}"

    user_db_id = await _seed_user(factory, bubble_user_id)
    owner_map = {bubble_salon_id: user_db_id}

    record = _bubble_salon(
        bubble_id=bubble_salon_id,
        name="Salon Invalide",
        valide=False,  # not validated in Bubble → soft-delete on import
    )

    try:
        async with factory() as db:
            counts = await process_records(db, [record], owner_map, dry_run=False)

        # The salon is imported (inserted), not skipped
        assert counts["inserted"] == 1

        salon = await _get_salon_by_bubble_id(factory, bubble_salon_id)
        assert salon is not None
        assert salon["deleted_at"] is not None, (
            "validé=False salon should have deleted_at set"
        )
    finally:
        await _cleanup(factory, bubble_salon_id, bubble_user_id)


# ── T7: idempotency + wizard choice preserved ─────────────────────────────────

@pytest.mark.asyncio
async def test_import_is_idempotent():
    """
    Running the import twice:
      - Does not create duplicate rows.
      - Does NOT overwrite business_type if the user set it via wizard between runs.
    """
    _, factory = _make_session_factory()
    bubble_user_id = f"T7-user-{uuid.uuid4().hex[:8]}"
    bubble_salon_id = f"T7-idem-{uuid.uuid4().hex[:8]}"

    user_db_id = await _seed_user(factory, bubble_user_id)
    owner_map = {bubble_salon_id: user_db_id}

    record = _bubble_salon(
        bubble_id=bubble_salon_id,
        name="Salon Idempotent",
        type_salon="Coiffure mixte",
    )

    try:
        # First run — inserts the salon
        async with factory() as db:
            counts1 = await process_records(db, [record], owner_map, dry_run=False)
        assert counts1["inserted"] == 1

        # Simulate the user setting business_type via the first-login wizard
        async with factory() as db:
            await db.execute(
                text(
                    "UPDATE salons SET business_type = 'auto_micro' "
                    "WHERE bubble_salon_id = :bid"
                ),
                {"bid": bubble_salon_id},
            )
            await db.commit()

        # Second run — updates (no conflict overwrite)
        async with factory() as db:
            counts2 = await process_records(db, [record], owner_map, dry_run=False)
        assert counts2["inserted"] == 0
        assert counts2["updated"] == 1

        # Row count unchanged
        async with factory() as db:
            result = await db.execute(
                text("SELECT COUNT(*) FROM salons WHERE bubble_salon_id = :bid"),
                {"bid": bubble_salon_id},
            )
            count = result.scalar_one()
        assert count == 1, f"Expected 1 row after two runs, got {count}"

        # business_type MUST NOT have been overwritten back to NULL
        salon = await _get_salon_by_bubble_id(factory, bubble_salon_id)
        assert salon["business_type"] == "auto_micro", (
            f"business_type was overwritten on second run! got {salon['business_type']!r}"
        )
    finally:
        await _cleanup(factory, bubble_salon_id, bubble_user_id)
