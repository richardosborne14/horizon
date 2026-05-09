"""Add employee_prime_schedules + enrich monthly_primes (Task 2.9.4).

Revision ID: d5e6f7a8b9c0
Revises: c9d0e1f2a3b4
Create Date: 2026-04-21 11:00:00.000000

WHY: The original primes system used a single, salon-wide hard-coded tier table
(PrimeConfig on salon.py). Task 2.9.4 replaces this with per-employee bonus
schedules that support three model types:
  - preset_eric    : Eric's default 9-band table (0-600 @ 10% … 2700-3000 @ 28%)
  - tranches_fixes : repeating fixed-width bands with a cycling rate sequence
  - custom         : arbitrary (threshold, rate) band list

A `bands_snapshot` JSONB column is added to `monthly_primes` so every
persisted month stores the *exact* bands that were used to compute it.
Later schedule edits therefore never silently rewrite bonus history.

`source_target_origin` / `source_target_ref` record whether the monthly
objectif came from a manual entry or was cross-linked from the most recent
seuil_salaire CalculationHistory row.

Idempotency: each object-create is guarded by an existence check so running
`alembic upgrade head` a second time on an already-migrated DB is a no-op.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import inspect


# revision identifiers
revision = "d5e6f7a8b9c0"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    """Return True if a table with *name* already exists in the public schema."""
    bind = op.get_bind()
    insp = inspect(bind)
    return name in insp.get_table_names()


def _column_exists(table: str, column: str) -> bool:
    """Return True if *column* already exists on *table*."""
    bind = op.get_bind()
    insp = inspect(bind)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols


def upgrade() -> None:
    # ── 1. employee_prime_schedules ────────────────────────────────────────────
    # One active row per employee at a time (effective_to IS NULL).
    # Closed rows (effective_to IS NOT NULL) are kept as audit history.
    if not _table_exists("employee_prime_schedules"):
        op.create_table(
            "employee_prime_schedules",
            sa.Column(
                "id",
                UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "salon_id",
                UUID(as_uuid=True),
                sa.ForeignKey("salons.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "employee_id",
                UUID(as_uuid=True),
                sa.ForeignKey("employees.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            # One of: preset_eric | tranches_fixes | custom
            sa.Column("model_type", sa.String(30), nullable=False, server_default="preset_eric"),
            # tranches_fixes only: width of each band in euros (e.g. 500)
            sa.Column("tranche_width", sa.Numeric(10, 2), nullable=True),
            # tranches_fixes only: JSON array of rates (fractions 0-1) that cycle,
            # e.g. [0.10, 0.15, 0.20].  Last rate repeats to infinity.
            sa.Column("rate_sequence", JSONB, nullable=True),
            # custom only: JSON array of {threshold: number, rate: number} objects,
            # sorted ascending by threshold.  Final band extends to infinity.
            sa.Column("custom_bands", JSONB, nullable=True),
            # Optional label the gérant can set ("Barème Sophie 2026")
            sa.Column("label", sa.String(120), nullable=True),
            # Effective period: NULL effective_to means currently active
            sa.Column(
                "effective_from",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column("effective_to", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )
        # Only one active schedule per employee at a time (partial unique index)
        op.create_index(
            "uq_employee_prime_schedule_active",
            "employee_prime_schedules",
            ["employee_id"],
            unique=True,
            postgresql_where=sa.text("effective_to IS NULL"),
        )

    # ── 2. Enrich monthly_primes with 4 new columns ────────────────────────────
    # schedule_id: FK to the schedule row that generated this result (nullable
    # for legacy rows created before this migration).
    if not _column_exists("monthly_primes", "schedule_id"):
        op.add_column(
            "monthly_primes",
            sa.Column(
                "schedule_id",
                UUID(as_uuid=True),
                sa.ForeignKey("employee_prime_schedules.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )

    # bands_snapshot: frozen copy of the materialised band list at compute time.
    # Format: [{"from": 0, "to": 600, "rate": 0.10}, …, {"from": 2700, "to": null, "rate": 0.28}]
    if not _column_exists("monthly_primes", "bands_snapshot"):
        op.add_column(
            "monthly_primes",
            sa.Column("bands_snapshot", JSONB, nullable=True),
        )

    # source_target_origin: "manual" | "seuil_salaire" | "average_3m"
    if not _column_exists("monthly_primes", "source_target_origin"):
        op.add_column(
            "monthly_primes",
            sa.Column(
                "source_target_origin",
                sa.String(30),
                nullable=False,
                server_default="manual",
            ),
        )

    # source_target_ref: UUID of the CalculationHistory row that supplied the
    # target (populated when source_target_origin = 'seuil_salaire').
    if not _column_exists("monthly_primes", "source_target_ref"):
        op.add_column(
            "monthly_primes",
            sa.Column(
                "source_target_ref",
                UUID(as_uuid=True),
                sa.ForeignKey("calculation_history.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )


def downgrade() -> None:
    # Remove the 4 new monthly_primes columns
    for col in ("source_target_ref", "source_target_origin", "bands_snapshot", "schedule_id"):
        if _column_exists("monthly_primes", col):
            op.drop_column("monthly_primes", col)

    # Drop the schedules table and its partial index
    if _table_exists("employee_prime_schedules"):
        op.drop_index(
            "uq_employee_prime_schedule_active",
            table_name="employee_prime_schedules",
        )
        op.drop_table("employee_prime_schedules")
