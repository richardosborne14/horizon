"""
TASK-2.17.5 — Import services from Bubble Prestation_main: unit tests.

All tests call ``process_records()`` directly with fixture Bubble records and a
manually-constructed ``salon_map``. No Bubble API calls are made.

Test coverage:
  T1. Valid Prestation_main → service row with correct name, type='carte', duration, price.
  T2. Null ``temps (m)`` → duration defaults to 30 minutes, service still created.
  T3. Null ``nom`` → fallback name 'Prestation', service still created.
  T4. Orphaned service (Salon not in salon_map) → skipped + error logged.
  T5. Admin/test service (Created By = admin_user_communaute-coiffure_*) → skipped.
  T6. Re-running updates name/duration/price but preserves prix_seuil_rentabilite.
  T7. Non-numeric price → prix_vente_ttc=NULL, service still imported.
"""

from __future__ import annotations

import uuid
import pytest
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import settings
from scripts.bubble.import_services import process_records


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_session_factory():
    engine = create_async_engine(settings.database_url, echo=False)
    return async_sessionmaker(engine, expire_on_commit=False)


def _prestation_record(
    bubble_id: str | None = None,
    nom: str | None = "Coupe Femme",
    salon_id: str | None = None,
    prix: int | None = 45,
    temps: int | None = 60,
    created_by: str | None = None,
) -> dict:
    """Build a minimal Bubble Prestation_main dict."""
    suffix = uuid.uuid4().hex[:8]
    return {
        "_id": bubble_id or f"bubble-svc-{suffix}",
        "nom": nom,
        "Salon": salon_id or f"bubble-salon-{suffix}",
        "prix": prix,
        "temps (m)": temps,
        "Created By": created_by or f"1615241986607x{suffix}",
        "Created Date": "2021-03-09T22:14:33.103Z",
        "Modified Date": "2024-03-01T10:00:00.000Z",
    }


async def _seed_salon(factory, bubble_salon_id: str) -> str:
    """Create a minimal user + salon and return the salon's DB UUID string."""
    user_id = str(uuid.uuid4())
    salon_id = str(uuid.uuid4())
    async with factory() as db:
        await db.execute(
            text(
                "INSERT INTO users (id, email, password_hash, name) "
                "VALUES (:id, :email, 'placeholder', 'Test')"
            ),
            {"id": user_id, "email": f"{bubble_salon_id}@t.invalid"},
        )
        await db.execute(
            text(
                "INSERT INTO salons "
                "(id, user_id, name, business_type, nb_employees, "
                "versement_liberatoire, acre, fiscal_year_start, bubble_salon_id) "
                "VALUES (:id, :uid, 'Salon', NULL, 0, false, false, 1, :bsid)"
            ),
            {"id": salon_id, "uid": user_id, "bsid": bubble_salon_id},
        )
        await db.commit()
    return salon_id


async def _get_service(factory, bubble_service_id: str) -> dict | None:
    async with factory() as db:
        result = await db.execute(
            text("SELECT * FROM services WHERE bubble_service_id = :bid LIMIT 1"),
            {"bid": bubble_service_id},
        )
        row = result.mappings().fetchone()
        return dict(row) if row else None


async def _cleanup(factory, bubble_service_id: str, bubble_salon_id: str) -> None:
    async with factory() as db:
        await db.execute(
            text("DELETE FROM services WHERE bubble_service_id = :bid"),
            {"bid": bubble_service_id},
        )
        await db.execute(
            text("DELETE FROM salons WHERE bubble_salon_id = :bsid"),
            {"bsid": bubble_salon_id},
        )
        await db.execute(
            text(
                "DELETE FROM users WHERE email = :email",
            ),
            {"email": f"{bubble_salon_id}@t.invalid"},
        )
        await db.commit()


async def _cleanup_salon_only(factory, bubble_salon_id: str) -> None:
    async with factory() as db:
        await db.execute(
            text("DELETE FROM services WHERE salon_id = "
                 "(SELECT id FROM salons WHERE bubble_salon_id = :bsid)"),
            {"bsid": bubble_salon_id},
        )
        await db.execute(
            text("DELETE FROM salons WHERE bubble_salon_id = :bsid"),
            {"bsid": bubble_salon_id},
        )
        await db.execute(
            text("DELETE FROM users WHERE email = :email"),
            {"email": f"{bubble_salon_id}@t.invalid"},
        )
        await db.commit()


# ── T1: valid service created with correct fields ─────────────────────────────

@pytest.mark.asyncio
async def test_import_creates_service_with_correct_fields():
    """
    A valid Prestation_main record creates a services row with:
      - name from nom
      - type = 'carte'
      - duration_minutes from temps (m)
      - prix_vente_ttc from prix (integer → Decimal)
      - bubble_service_id set
      - salon_id linked to the imported salon
    """
    factory = _make_session_factory()
    bubble_salon_id = f"bs-T1-{uuid.uuid4().hex[:8]}"
    bubble_svc_id = f"svc-T1-{uuid.uuid4().hex[:8]}"

    salon_db_id = await _seed_salon(factory, bubble_salon_id)
    salon_map = {bubble_salon_id: salon_db_id}

    record = _prestation_record(
        bubble_id=bubble_svc_id,
        nom="Coupe + Brushing",
        salon_id=bubble_salon_id,
        prix=55,
        temps=75,
    )

    try:
        async with factory() as db:
            counts = await process_records(db, [record], salon_map, dry_run=False)

        assert counts["inserted"] == 1
        assert counts["errored"] == 0

        svc = await _get_service(factory, bubble_svc_id)
        assert svc is not None
        assert svc["name"] == "Coupe + Brushing"
        assert svc["type"] == "carte"
        assert svc["duration_minutes"] == 75
        assert Decimal(str(svc["prix_vente_ttc"])) == Decimal("55")
        assert str(svc["salon_id"]) == salon_db_id
        assert svc["bubble_service_id"] == bubble_svc_id
        assert svc["is_active"] is True
    finally:
        await _cleanup(factory, bubble_svc_id, bubble_salon_id)


# ── T2: null duration → default 30 minutes ───────────────────────────────────

@pytest.mark.asyncio
async def test_null_duration_defaults_to_30():
    """
    A service with null ``temps (m)`` is imported with duration_minutes = 30.
    The service is NOT rejected.
    """
    factory = _make_session_factory()
    bubble_salon_id = f"bs-T2-{uuid.uuid4().hex[:8]}"
    bubble_svc_id = f"svc-T2-{uuid.uuid4().hex[:8]}"

    salon_db_id = await _seed_salon(factory, bubble_salon_id)
    salon_map = {bubble_salon_id: salon_db_id}

    record = _prestation_record(
        bubble_id=bubble_svc_id,
        nom="Soins Capillaires",
        salon_id=bubble_salon_id,
        prix=30,
        temps=None,
    )

    try:
        async with factory() as db:
            counts = await process_records(db, [record], salon_map, dry_run=False)

        assert counts["inserted"] == 1

        svc = await _get_service(factory, bubble_svc_id)
        assert svc is not None
        assert svc["duration_minutes"] == 30, (
            f"Expected default 30 min, got {svc['duration_minutes']}"
        )
    finally:
        await _cleanup(factory, bubble_svc_id, bubble_salon_id)


# ── T3: null nom → fallback 'Prestation' ─────────────────────────────────────

@pytest.mark.asyncio
async def test_null_nom_falls_back_to_prestation():
    """
    A service with null ``nom`` is imported with name='Prestation'.
    """
    factory = _make_session_factory()
    bubble_salon_id = f"bs-T3-{uuid.uuid4().hex[:8]}"
    bubble_svc_id = f"svc-T3-{uuid.uuid4().hex[:8]}"

    salon_db_id = await _seed_salon(factory, bubble_salon_id)
    salon_map = {bubble_salon_id: salon_db_id}

    record = _prestation_record(
        bubble_id=bubble_svc_id,
        nom=None,
        salon_id=bubble_salon_id,
        prix=20,
        temps=30,
    )

    try:
        async with factory() as db:
            counts = await process_records(db, [record], salon_map, dry_run=False)

        assert counts["inserted"] == 1

        svc = await _get_service(factory, bubble_svc_id)
        assert svc is not None
        assert svc["name"] == "Prestation"
    finally:
        await _cleanup(factory, bubble_svc_id, bubble_salon_id)


# ── T4: orphaned service skipped + error logged ───────────────────────────────

@pytest.mark.asyncio
async def test_orphaned_service_is_skipped():
    """
    A Prestation_main record whose Salon field does not match any key in
    salon_map is skipped. Error log has reason='orphan_service'.
    """
    factory = _make_session_factory()
    bubble_svc_id = f"svc-T4-{uuid.uuid4().hex[:8]}"

    record = _prestation_record(
        bubble_id=bubble_svc_id,
        nom="Orphan Service",
        salon_id="unknown-salon-id",
    )
    salon_map: dict[str, str] = {}  # empty

    async with factory() as db:
        counts = await process_records(db, [record], salon_map, dry_run=False)

    assert counts["skipped"] == 1
    assert counts["inserted"] == 0

    svc = await _get_service(factory, bubble_svc_id)
    assert svc is None

    async with factory() as db:
        result = await db.execute(
            text(
                "SELECT error_log FROM bubble_import_runs "
                "WHERE script_name = 'import_services' "
                "ORDER BY started_at DESC LIMIT 1"
            )
        )
        row = result.fetchone()
    assert row is not None
    error_log = row[0] or []
    assert any(
        e.get("reason") == "orphan_service"
        for e in (error_log if isinstance(error_log, list) else [])
    ), f"Expected orphan_service in error_log, got: {error_log}"


# ── T5: admin/test service skipped ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_service_is_skipped():
    """
    Services with Created By = 'admin_user_communaute-coiffure_*' are skipped.
    """
    factory = _make_session_factory()
    bubble_salon_id = f"bs-T5-{uuid.uuid4().hex[:8]}"
    bubble_svc_id = f"svc-T5-{uuid.uuid4().hex[:8]}"

    salon_db_id = await _seed_salon(factory, bubble_salon_id)
    salon_map = {bubble_salon_id: salon_db_id}

    record = _prestation_record(
        bubble_id=bubble_svc_id,
        nom="Admin Demo Service",
        salon_id=bubble_salon_id,
        created_by="admin_user_communaute-coiffure_live",
    )
    # Even if salon is in the map, admin records are filtered
    try:
        async with factory() as db:
            counts = await process_records(db, [record], salon_map, dry_run=False)

        assert counts["skipped"] == 1
        assert counts["inserted"] == 0

        svc = await _get_service(factory, bubble_svc_id)
        assert svc is None
    finally:
        await _cleanup_salon_only(factory, bubble_salon_id)


# ── T6: idempotent — prix_seuil_rentabilite preserved ─────────────────────────

@pytest.mark.asyncio
async def test_import_is_idempotent_and_preserves_calculated_price():
    """
    Running the import twice:
      - Does not create duplicate rows.
      - Updates name, duration_minutes, prix_vente_ttc.
      - Does NOT overwrite prix_seuil_rentabilite set by the pricing wizard.
    """
    factory = _make_session_factory()
    bubble_salon_id = f"bs-T6-{uuid.uuid4().hex[:8]}"
    bubble_svc_id = f"svc-T6-{uuid.uuid4().hex[:8]}"

    salon_db_id = await _seed_salon(factory, bubble_salon_id)
    salon_map = {bubble_salon_id: salon_db_id}

    record = _prestation_record(
        bubble_id=bubble_svc_id,
        nom="Coupe Femme",
        salon_id=bubble_salon_id,
        prix=45,
        temps=60,
    )

    try:
        # First run
        async with factory() as db:
            counts1 = await process_records(db, [record], salon_map, dry_run=False)
        assert counts1["inserted"] == 1

        # Simulate pricing wizard calculating break-even price
        async with factory() as db:
            await db.execute(
                text(
                    "UPDATE services SET prix_seuil_rentabilite = 38.50 "
                    "WHERE bubble_service_id = :bid"
                ),
                {"bid": bubble_svc_id},
            )
            await db.commit()

        # Second run
        async with factory() as db:
            counts2 = await process_records(db, [record], salon_map, dry_run=False)
        assert counts2["inserted"] == 0
        assert counts2["updated"] == 1

        # Row count unchanged
        async with factory() as db:
            result = await db.execute(
                text("SELECT COUNT(*) FROM services WHERE bubble_service_id = :bid"),
                {"bid": bubble_svc_id},
            )
            assert result.scalar_one() == 1

        # prix_seuil_rentabilite MUST be preserved
        svc = await _get_service(factory, bubble_svc_id)
        assert Decimal(str(svc["prix_seuil_rentabilite"])) == Decimal("38.50"), (
            f"prix_seuil_rentabilite was overwritten! got {svc['prix_seuil_rentabilite']!r}"
        )
    finally:
        await _cleanup(factory, bubble_svc_id, bubble_salon_id)


# ── T7: non-numeric price → NULL, service still created ──────────────────────

@pytest.mark.asyncio
async def test_non_numeric_price_is_null():
    """
    A service whose ``prix`` field is missing or non-numeric is imported
    with prix_vente_ttc=NULL. The service row is NOT rejected.
    """
    factory = _make_session_factory()
    bubble_salon_id = f"bs-T7-{uuid.uuid4().hex[:8]}"
    bubble_svc_id = f"svc-T7-{uuid.uuid4().hex[:8]}"

    salon_db_id = await _seed_salon(factory, bubble_salon_id)
    salon_map = {bubble_salon_id: salon_db_id}

    record = _prestation_record(
        bubble_id=bubble_svc_id,
        nom="Prestation sans prix",
        salon_id=bubble_salon_id,
        prix=None,  # missing price
        temps=45,
    )

    try:
        async with factory() as db:
            counts = await process_records(db, [record], salon_map, dry_run=False)

        assert counts["inserted"] == 1, "Service with null price should still be imported"

        svc = await _get_service(factory, bubble_svc_id)
        assert svc is not None
        assert svc["prix_vente_ttc"] is None, (
            f"Expected prix_vente_ttc=None, got {svc['prix_vente_ttc']!r}"
        )
    finally:
        await _cleanup(factory, bubble_svc_id, bubble_salon_id)
