"""
TASK-2.17.6 — Import monthly reports + expenses from Bubble: unit tests.

All tests call ``process_records()`` directly with fixture data. No Bubble API
calls are made. Category IDs are loaded from the real DB (expense_categories must
be seeded, which happens via the seed script on a fresh DB).

Test coverage:
  T1. Dormant salon (no 2026+ months) → month is skipped, no report created.
  T2. Active salon month → monthly_report row created with correct year/month.
  T3. Revenue item → ca_realise_ttc written on the monthly_report.
  T4. Dépense item with mapped title → expense linked to correct category.
  T5. Dépense item with unknown title → expense falls back to frais_generaux.
  T6. TVA parsing: "20 %" → 0.200 fraction; "0 %" → 0.000 fraction.
  T7. Import is idempotent: second run updates but does not duplicate rows.
"""

from __future__ import annotations

import uuid
import pytest
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import settings
from scripts.bubble.import_reports import (
    process_records,
    _build_active_salon_set,
    _parse_month,
    _parse_year,
    _parse_tva_rate,
    _map_title_to_category_key,
    DEFAULT_CATEGORY_KEY,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_session_factory():
    engine = create_async_engine(settings.database_url, echo=False)
    return async_sessionmaker(engine, expire_on_commit=False)


async def _seed_salon(factory, bubble_salon_id: str) -> tuple[str, str]:
    """Seed user + salon. Returns (user_db_id, salon_db_id)."""
    user_id = str(uuid.uuid4())
    salon_id = str(uuid.uuid4())
    async with factory() as db:
        await db.execute(
            text("INSERT INTO users (id, email, password_hash, name) VALUES (:id, :email, 'x', 'T')"),
            {"id": user_id, "email": f"{bubble_salon_id}@t.invalid"},
        )
        await db.execute(
            text(
                "INSERT INTO salons (id, user_id, name, business_type, nb_employees, "
                "versement_liberatoire, acre, fiscal_year_start, bubble_salon_id) "
                "VALUES (:id, :uid, 'S', NULL, 0, false, false, 1, :bsid)"
            ),
            {"id": salon_id, "uid": user_id, "bsid": bubble_salon_id},
        )
        await db.commit()
    return user_id, salon_id


async def _seed_employee(factory, salon_id: str, name: str, role_type: str = "salarie") -> str:
    """Seed an employee for a salon. Returns employee_db_id."""
    emp_id = str(uuid.uuid4())
    async with factory() as db:
        await db.execute(
            text(
                "INSERT INTO employees (id, salon_id, name, role_type, hours_per_week, taux_occupation, is_active) "
                "VALUES (:id, :sid, :name, :rt, 35, 0.65, true)"
            ),
            {"id": emp_id, "sid": salon_id, "name": name, "rt": role_type},
        )
        await db.commit()
    return emp_id


async def _get_category_map(factory) -> dict[str, str]:
    """Load real {i18n_key → id} from expense_categories."""
    async with factory() as db:
        r = await db.execute(text("SELECT i18n_key, id FROM expense_categories"))
        return {row[0]: str(row[1]) for row in r.fetchall()}


def _month_record(
    bubble_id: str,
    bubble_salon_id: str,
    year: str = "2026",
    month: str = "M3",
    item_ids: list[str] | None = None,
) -> dict:
    return {
        "_id": bubble_id,
        "belongsToSalon": bubble_salon_id,
        "Op_year": year,
        "OP_month": month,
        "listReportingItems": item_ids or [],
    }


def _item_record(
    bubble_id: str,
    line_type: str,
    title: str | None = None,
    amount: int | None = None,
    op_tva: str | None = "20 %",
) -> dict:
    return {
        "_id": bubble_id,
        "LineType": line_type,
        "Title": title,
        "amount": amount,
        "OP TVA": op_tva,
    }


async def _get_monthly_report(factory, bubble_month_id: str) -> dict | None:
    async with factory() as db:
        r = await db.execute(
            text("SELECT * FROM monthly_reports WHERE bubble_month_id = :bid"),
            {"bid": bubble_month_id},
        )
        row = r.mappings().fetchone()
        return dict(row) if row else None


async def _get_expenses(factory, report_db_id: str) -> list[dict]:
    async with factory() as db:
        r = await db.execute(
            text("SELECT * FROM expenses WHERE monthly_report_id = :rid"),
            {"rid": report_db_id},
        )
        return [dict(row) for row in r.mappings().fetchall()]


async def _cleanup_month(factory, bubble_month_id: str, bubble_salon_id: str) -> None:
    async with factory() as db:
        await db.execute(
            text(
                "DELETE FROM monthly_salaries WHERE monthly_report_id IN "
                "(SELECT id FROM monthly_reports WHERE bubble_month_id = :bid)"
            ),
            {"bid": bubble_month_id},
        )
        await db.execute(
            text(
                "DELETE FROM expenses WHERE monthly_report_id IN "
                "(SELECT id FROM monthly_reports WHERE bubble_month_id = :bid)"
            ),
            {"bid": bubble_month_id},
        )
        await db.execute(
            text("DELETE FROM monthly_reports WHERE bubble_month_id = :bid"),
            {"bid": bubble_month_id},
        )
        await db.execute(
            text("DELETE FROM employees WHERE salon_id = "
                 "(SELECT id FROM salons WHERE bubble_salon_id = :bsid)"),
            {"bsid": bubble_salon_id},
        )
        await db.execute(
            text("DELETE FROM salons WHERE bubble_salon_id = :bsid"),
            {"bsid": bubble_salon_id},
        )
        await db.execute(
            text("DELETE FROM users WHERE email = :e"),
            {"e": f"{bubble_salon_id}@t.invalid"},
        )
        await db.commit()


# ── T1: dormant salon → month skipped ────────────────────────────────────────

@pytest.mark.asyncio
async def test_dormant_salon_month_is_skipped():
    """
    A salon with no month in year >= 2026 is dormant. Its months are skipped and
    no monthly_report row is created.
    """
    bubble_salon_id = f"bs-T1-{uuid.uuid4().hex[:8]}"
    bubble_month_id = f"bm-T1-{uuid.uuid4().hex[:8]}"

    month = _month_record(bubble_month_id, bubble_salon_id, year="2025", month="M6")
    # Active salon set is empty — salon is dormant
    active_set: set[str] = set()
    salon_db_map = {bubble_salon_id: str(uuid.uuid4())}
    category_map: dict[str, str] = {}
    employee_map: dict[tuple[str, str], str] = {}

    factory = _make_session_factory()
    async with factory() as db:
        counts = await process_records(
            db, [month], {}, active_set, salon_db_map, category_map, employee_map
        )

    assert counts["months_skipped"] == 1
    assert counts["months_inserted"] == 0

    report = await _get_monthly_report(factory, bubble_month_id)
    assert report is None, "No monthly_report should exist for dormant salon"


# ── T2: active salon → monthly_report created ────────────────────────────────

@pytest.mark.asyncio
async def test_active_salon_creates_monthly_report():
    """
    A salon in active_salon_set gets a monthly_report row with correct year/month.
    """
    factory = _make_session_factory()
    bubble_salon_id = f"bs-T2-{uuid.uuid4().hex[:8]}"
    bubble_month_id = f"bm-T2-{uuid.uuid4().hex[:8]}"

    _, salon_db_id = await _seed_salon(factory, bubble_salon_id)

    month = _month_record(bubble_month_id, bubble_salon_id, year="2026", month="M3")
    active_set = {bubble_salon_id}
    salon_db_map = {bubble_salon_id: salon_db_id}

    try:
        async with factory() as db:
            counts = await process_records(
                db, [month], {}, active_set, salon_db_map, {}, {}
            )

        assert counts["months_inserted"] == 1
        assert counts["errored"] == 0

        report = await _get_monthly_report(factory, bubble_month_id)
        assert report is not None
        assert report["year"] == 2026
        assert report["month"] == 3
        assert str(report["salon_id"]) == salon_db_id
    finally:
        await _cleanup_month(factory, bubble_month_id, bubble_salon_id)


# ── T3: Revenue item → ca_realise_ttc updated ────────────────────────────────

@pytest.mark.asyncio
async def test_revenue_item_updates_ca():
    """
    A Revenue ReportingItem with amount=5200 sets ca_realise_ttc=5200 on the
    monthly_report.
    """
    factory = _make_session_factory()
    bubble_salon_id = f"bs-T3-{uuid.uuid4().hex[:8]}"
    bubble_month_id = f"bm-T3-{uuid.uuid4().hex[:8]}"
    bubble_item_id = f"bi-T3-{uuid.uuid4().hex[:8]}"

    _, salon_db_id = await _seed_salon(factory, bubble_salon_id)

    item = _item_record(bubble_item_id, "Revenue", title="Chiffre d'affaires réalisé", amount=5200)
    month = _month_record(
        bubble_month_id, bubble_salon_id,
        year="2026", month="M4",
        item_ids=[bubble_item_id],
    )
    active_set = {bubble_salon_id}
    salon_db_map = {bubble_salon_id: salon_db_id}
    items_by_id = {bubble_item_id: item}

    try:
        async with factory() as db:
            await process_records(
                db, [month], items_by_id, active_set, salon_db_map, {}, {}
            )

        report = await _get_monthly_report(factory, bubble_month_id)
        assert report is not None
        assert Decimal(str(report["ca_realise_ttc"])) == Decimal("5200")
    finally:
        await _cleanup_month(factory, bubble_month_id, bubble_salon_id)


# ── T4: Dépense with known title → correct category ──────────────────────────

@pytest.mark.asyncio
async def test_depense_known_title_maps_to_correct_category():
    """
    A Dépense item with title='Achats produits' is routed to the
    'expenses.achats_marchandises' category (not frais_generaux).
    """
    factory = _make_session_factory()
    bubble_salon_id = f"bs-T4-{uuid.uuid4().hex[:8]}"
    bubble_month_id = f"bm-T4-{uuid.uuid4().hex[:8]}"
    bubble_item_id = f"bi-T4-{uuid.uuid4().hex[:8]}"

    _, salon_db_id = await _seed_salon(factory, bubble_salon_id)
    category_map = await _get_category_map(factory)

    item = _item_record(bubble_item_id, "Dépense", title="Achats produits", amount=800, op_tva="20 %")
    month = _month_record(
        bubble_month_id, bubble_salon_id,
        year="2026", month="M5",
        item_ids=[bubble_item_id],
    )
    active_set = {bubble_salon_id}
    salon_db_map = {bubble_salon_id: salon_db_id}
    items_by_id = {bubble_item_id: item}

    try:
        async with factory() as db:
            counts = await process_records(
                db, [month], items_by_id, active_set, salon_db_map, category_map, {}
            )

        assert counts["expenses_inserted"] == 1

        report = await _get_monthly_report(factory, bubble_month_id)
        expenses = await _get_expenses(factory, str(report["id"]))
        assert len(expenses) == 1

        expected_cat_id = category_map["expenses.achats_marchandises"]
        assert str(expenses[0]["category_id"]) == expected_cat_id, (
            f"Expected achats_marchandises, got {expenses[0]['category_id']}"
        )
        assert Decimal(str(expenses[0]["amount_ttc"])) == Decimal("800")
        assert Decimal(str(expenses[0]["tva_rate"])) == Decimal("0.200")
    finally:
        await _cleanup_month(factory, bubble_month_id, bubble_salon_id)


# ── T5: unknown title → frais_generaux fallback ───────────────────────────────

@pytest.mark.asyncio
async def test_depense_unknown_title_falls_back_to_frais_generaux():
    """
    A Dépense item with an unrecognised title falls back to the
    'expenses.frais_generaux' category.
    """
    factory = _make_session_factory()
    bubble_salon_id = f"bs-T5-{uuid.uuid4().hex[:8]}"
    bubble_month_id = f"bm-T5-{uuid.uuid4().hex[:8]}"
    bubble_item_id = f"bi-T5-{uuid.uuid4().hex[:8]}"

    _, salon_db_id = await _seed_salon(factory, bubble_salon_id)
    category_map = await _get_category_map(factory)

    item = _item_record(bubble_item_id, "Dépense", title="Abonnement logiciel inconnu", amount=120)
    month = _month_record(
        bubble_month_id, bubble_salon_id,
        year="2026", month="M6",
        item_ids=[bubble_item_id],
    )
    active_set = {bubble_salon_id}
    salon_db_map = {bubble_salon_id: salon_db_id}
    items_by_id = {bubble_item_id: item}

    try:
        async with factory() as db:
            await process_records(
                db, [month], items_by_id, active_set, salon_db_map, category_map, {}
            )

        report = await _get_monthly_report(factory, bubble_month_id)
        expenses = await _get_expenses(factory, str(report["id"]))
        assert len(expenses) == 1

        expected_cat_id = category_map[DEFAULT_CATEGORY_KEY]
        assert str(expenses[0]["category_id"]) == expected_cat_id
    finally:
        await _cleanup_month(factory, bubble_month_id, bubble_salon_id)


# ── T6: TVA parsing ───────────────────────────────────────────────────────────

def test_tva_parsing():
    """
    Pure unit test: TVA rate strings are parsed to the correct NUMERIC(4,3) fraction.
    """
    assert _parse_tva_rate("20 %") == Decimal("0.200")
    assert _parse_tva_rate("0 %") == Decimal("0.000")
    assert _parse_tva_rate("5.5 %") == Decimal("0.055")
    assert _parse_tva_rate("10 %") == Decimal("0.100")
    assert _parse_tva_rate(None) == Decimal("0.200")   # default
    assert _parse_tva_rate("unknown") == Decimal("0.200")  # fallback


# ── T7: idempotency ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_report_import_is_idempotent():
    """
    Running the import twice does not duplicate monthly_report or expense rows.
    The second run returns months_updated=1 and expenses_updated=1.
    """
    factory = _make_session_factory()
    bubble_salon_id = f"bs-T7-{uuid.uuid4().hex[:8]}"
    bubble_month_id = f"bm-T7-{uuid.uuid4().hex[:8]}"
    bubble_item_id = f"bi-T7-{uuid.uuid4().hex[:8]}"

    _, salon_db_id = await _seed_salon(factory, bubble_salon_id)
    category_map = await _get_category_map(factory)

    item = _item_record(bubble_item_id, "Dépense", title="Loyer charges comprises", amount=1200)
    month = _month_record(
        bubble_month_id, bubble_salon_id,
        year="2026", month="M7",
        item_ids=[bubble_item_id],
    )
    active_set = {bubble_salon_id}
    salon_db_map = {bubble_salon_id: salon_db_id}
    items_by_id = {bubble_item_id: item}

    try:
        # First run
        async with factory() as db:
            c1 = await process_records(
                db, [month], items_by_id, active_set, salon_db_map, category_map, {}
            )
        assert c1["months_inserted"] == 1
        assert c1["expenses_inserted"] == 1

        # Second run
        async with factory() as db:
            c2 = await process_records(
                db, [month], items_by_id, active_set, salon_db_map, category_map, {}
            )
        assert c2["months_inserted"] == 0
        assert c2["months_updated"] == 1
        assert c2["expenses_inserted"] == 0
        assert c2["expenses_updated"] == 1

        # Verify no duplicates in DB
        report = await _get_monthly_report(factory, bubble_month_id)
        expenses = await _get_expenses(factory, str(report["id"]))
        assert len(expenses) == 1, f"Expected 1 expense, got {len(expenses)}"

        async with factory() as db:
            r = await db.execute(
                text("SELECT COUNT(*) FROM monthly_reports WHERE bubble_month_id = :bid"),
                {"bid": bubble_month_id},
            )
            assert r.scalar_one() == 1
    finally:
        await _cleanup_month(factory, bubble_month_id, bubble_salon_id)
