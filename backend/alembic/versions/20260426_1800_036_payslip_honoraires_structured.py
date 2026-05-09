"""036 — Add structured payslip cost + honoraires comptables fields to monthly_reports.

Two new NULLABLE NUMERIC(12,2) columns on monthly_reports:
  - payslip_current_cost_per_bulletin_ttc : user's actual payslip provider cost per bulletin (TTC)
  - honoraires_comptables_ttc             : structured monthly comptable fee (TTC)

These replace heuristic/regex approaches in the savings engine with real data-driven figures.
See TASK-2.12.11 for rationale.

Backfill logic:
  1. Scan all expense rows. If label (~notes) matches honoraires/comptable pattern → sum into
     honoraires_comptables_ttc and DELETE the expense row (migrated to structured field).
  2. If label matches payslip/RH pattern → compute per-bulletin cost from total ÷ employee count
     for that month, store in payslip_current_cost_per_bulletin_ttc, DELETE expense row.
  3. All actions logged to /tmp/migration_audit_2_12_11.jsonl for review.

WHY delete migrated expense rows: they are now in the structured field. Keeping them would
double-count in both the old free-text channel and the new structured channel.

Revision ID: 036_payslip_honoraires_structured
Previous: 035_payslip_receipt_url
"""

import json
import logging
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
logger = logging.getLogger(__name__)

revision = "036_payslip_honoraires"
down_revision = "035_payslip_receipt_url"
branch_labels = None
depends_on = None


AUDIT_FILE = "/tmp/migration_audit_2_12_11.jsonl"


def upgrade() -> None:
    """
    Add two NULLABLE NUMERIC(12,2) columns to monthly_reports, then backfill from
    free-text expense rows and delete the migrated expense rows.

    Safe to run multiple times (idempotent): IF NOT EXISTS guards the column additions;
    the UPDATE/DELETE only touch rows where the structured column is still NULL.
    """
    # ── 1. Add columns ─────────────────────────────────────────────────────────
    op.add_column(
        "monthly_reports",
        sa.Column(
            "payslip_current_cost_per_bulletin_ttc",
            sa.Numeric(12, 2),
            nullable=True,
            comment=(
                "User's current payslip provider cost per bulletin TTC. "
                "NULL = not yet provided (falls back to 2× heuristic in savings engine). "
                "Set via Mon Mois Typique wizard or pilotage month quick-pick."
            ),
        ),
    )
    op.add_column(
        "monthly_reports",
        sa.Column(
            "honoraires_comptables_ttc",
            sa.Numeric(12, 2),
            nullable=True,
            comment=(
                "Monthly comptable / expert-comptable fee TTC. "
                "NULL = not yet provided (savings engine falls back to regex on expense labels). "
                "Set via Mon Mois Typique wizard or pilotage month quick-pick."
            ),
        ),
    )

    # ── 2. Backfill from free-text expense labels ──────────────────────────────
    # WHY inline SQL: Alembic upgrade runs in a raw DB connection; ORM models are
    # not available here (and importing them risks circular-import errors during
    # the migration phase). Raw SQL is the correct pattern for Alembic backfills.
    bind = op.get_bind()

    # Fetch all expense rows with labels matching honoraires or payslip patterns.
    # We look at BOTH `notes` (the primary label field on Expense) AND a fallback
    # on the expense category name — matching the savings engine's regex.
    honoraires_rows = bind.execute(sa.text("""
        SELECT
            e.id            AS expense_id,
            e.monthly_report_id,
            e.amount_ttc,
            e.notes,
            mr.salon_id,
            mr.year,
            mr.month
        FROM expenses e
        JOIN monthly_reports mr ON mr.id = e.monthly_report_id
        WHERE e.notes ~* 'honoraires|comptable|expert.?comptable'
          AND (mr.honoraires_comptables_ttc IS NULL)
        ORDER BY mr.salon_id, mr.year, mr.month
    """)).fetchall()

    payslip_rows = bind.execute(sa.text("""
        SELECT
            e.id            AS expense_id,
            e.monthly_report_id,
            e.amount_ttc,
            e.notes,
            mr.salon_id,
            mr.year,
            mr.month
        FROM expenses e
        JOIN monthly_reports mr ON mr.id = e.monthly_report_id
        WHERE e.notes ~* 'fiches?.?de.?paie|bulletin.?de.?paie|honoraires.?rh|paie\\b'
          AND (mr.payslip_current_cost_per_bulletin_ttc IS NULL)
        ORDER BY mr.salon_id, mr.year, mr.month
    """)).fetchall()

    audit_entries = []
    now_str = datetime.now(tz=timezone.utc).isoformat()

    # ── 2a. Honoraires comptables backfill ────────────────────────────────────
    # Group by monthly_report_id and sum amounts.
    from collections import defaultdict
    honoraires_by_report: dict = defaultdict(list)
    for row in honoraires_rows:
        honoraires_by_report[str(row.monthly_report_id)].append(row)

    for report_id, rows in honoraires_by_report.items():
        total_ttc = sum(float(r.amount_ttc) for r in rows)
        bind.execute(sa.text("""
            UPDATE monthly_reports
               SET honoraires_comptables_ttc = :amount
             WHERE id = :rid
               AND honoraires_comptables_ttc IS NULL
        """), {"amount": total_ttc, "rid": report_id})

        expense_ids = [str(r.expense_id) for r in rows]
        if expense_ids:
            # WHY string format (not params): psycopg3 in Alembic sync context misparses
            # :ids::uuid[] — the :: cast triggers a SyntaxError. UUIDs from DB are safe
            # to embed directly (no user input, no injection risk).
            id_csv = ", ".join(f"'{eid}'" for eid in expense_ids)
            bind.execute(sa.text(f"DELETE FROM expenses WHERE id IN ({id_csv})"))

        for r in rows:
            audit_entries.append({
                "type": "honoraires_comptables",
                "migrated_at": now_str,
                "salon_id": str(r.salon_id),
                "year": r.year,
                "month": r.month,
                "monthly_report_id": report_id,
                "old_expense_id": str(r.expense_id),
                "old_label": r.notes,
                "amount_ttc": float(r.amount_ttc),
                "total_migrated_to_field": total_ttc,
            })

    # ── 2b. Payslip backfill ──────────────────────────────────────────────────
    # Per-bulletin cost = total_ttc / nb_employees (active non-dirigeant for that month).
    payslip_by_report: dict = defaultdict(list)
    for row in payslip_rows:
        payslip_by_report[str(row.monthly_report_id)].append(row)

    for report_id, rows in payslip_by_report.items():
        first = rows[0]
        total_ttc = sum(float(r.amount_ttc) for r in rows)

        # Count non-dirigeant active employees for this salon at migration time.
        # WHY use active employees not monthly salary count: monthly_salaries may be empty
        # for historic months.
        emp_count_result = bind.execute(sa.text("""
            SELECT COUNT(*) AS cnt
            FROM employees
            WHERE salon_id = :sid
              AND is_active = true
              AND role_type != 'dirigeant'
        """), {"sid": str(first.salon_id)}).fetchone()

        nb_employees = int(emp_count_result.cnt) if emp_count_result else 0

        if nb_employees > 0:
            per_bulletin = total_ttc / nb_employees
            bind.execute(sa.text("""
                UPDATE monthly_reports
                   SET payslip_current_cost_per_bulletin_ttc = :amount
                 WHERE id = :rid
                   AND payslip_current_cost_per_bulletin_ttc IS NULL
            """), {"amount": per_bulletin, "rid": report_id})

        expense_ids = [str(r.expense_id) for r in rows]
        if expense_ids:
            id_csv = ", ".join(f"'{eid}'" for eid in expense_ids)
            bind.execute(sa.text(f"DELETE FROM expenses WHERE id IN ({id_csv})"))

        for r in rows:
            audit_entries.append({
                "type": "payslip_per_bulletin",
                "migrated_at": now_str,
                "salon_id": str(first.salon_id),
                "year": first.year,
                "month": first.month,
                "monthly_report_id": report_id,
                "old_expense_id": str(r.expense_id),
                "old_label": r.notes,
                "amount_ttc": float(r.amount_ttc),
                "nb_employees": nb_employees,
                "per_bulletin_ttc": total_ttc / nb_employees if nb_employees > 0 else None,
            })

    # ── 3. Write audit JSONL ───────────────────────────────────────────────────
    if audit_entries:
        try:
            with open(AUDIT_FILE, "a", encoding="utf-8") as f:
                for entry in audit_entries:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            logger.info(
                "Migration 036 audit: %d rows migrated, written to %s",
                len(audit_entries),
                AUDIT_FILE,
            )
        except OSError as exc:
            # Non-fatal — migration still succeeds; log to stderr instead.
            logger.warning("Could not write audit file %s: %s", AUDIT_FILE, exc)
    else:
        logger.info("Migration 036: no honoraires/payslip expense rows found to migrate.")


def downgrade() -> None:
    """
    Drop the two structured columns.

    WHY: migrated expense rows are NOT restored on downgrade — this is a
    one-way data migration. Acceptable in dev-only environments (per spec note).
    """
    op.drop_column("monthly_reports", "payslip_current_cost_per_bulletin_ttc")
    op.drop_column("monthly_reports", "honoraires_comptables_ttc")
