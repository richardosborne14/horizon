"""Add scenarios table + enrich calculation_history (Task 2.9.5).

Revision ID: f0a1b2c3d4e5
Revises: d5e6f7a8b9c0
Create Date: 2026-04-21 12:00:00.000000

WHY:
  Task 2.9.5 — Calculator Hub & Cross-Tool Linking.

  Two additions:
  1. `scenarios` — named bundles of related calculation runs. A salon can
     group calcs into "Simulation 2027 — Ouverture 2e salon" and narrate
     the bundle through CoCo.

  2. Three new nullable columns on `calculation_history`:
     - scenario_id    : FK to scenarios (NULL = ad-hoc, unattached run)
     - source_links   : JSONB array recording which inputs were pulled from
                        another calculator (provenance metadata)
     - headline_result: Short human-readable summary auto-generated from
                        the calc outputs, e.g. "€161 / mois pour Frank"

  All new columns have safe NULL defaults so existing rows are unaffected.
  Idempotency: every CREATE/ALTER is guarded by an existence check.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import inspect, text


# revision identifiers
revision = "f0a1b2c3d4e5"
down_revision = "d5e6f7a8b9c0"
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


def _index_exists(index_name: str) -> bool:
    """Return True if an index with *index_name* already exists."""
    bind = op.get_bind()
    result = bind.execute(
        text(
            "SELECT 1 FROM pg_indexes WHERE indexname = :n",
        ),
        {"n": index_name},
    )
    return result.scalar() is not None


def upgrade() -> None:
    # ── 1. Create scenarios table ─────────────────────────────────────────────
    if not _table_exists("scenarios"):
        op.create_table(
            "scenarios",
            sa.Column(
                "id",
                UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column(
                "salon_id",
                UUID(as_uuid=True),
                sa.ForeignKey("salons.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "created_by",
                UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        )

    if not _index_exists("idx_scenarios_salon"):
        op.create_index(
            "idx_scenarios_salon",
            "scenarios",
            ["salon_id"],
            postgresql_where=sa.text("archived_at IS NULL"),
        )

    # ── 2. Enrich calculation_history ─────────────────────────────────────────
    if not _column_exists("calculation_history", "scenario_id"):
        op.add_column(
            "calculation_history",
            sa.Column(
                "scenario_id",
                UUID(as_uuid=True),
                sa.ForeignKey("scenarios.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )

    if not _column_exists("calculation_history", "source_links"):
        op.add_column(
            "calculation_history",
            sa.Column("source_links", JSONB, nullable=True),
        )

    if not _column_exists("calculation_history", "headline_result"):
        op.add_column(
            "calculation_history",
            sa.Column("headline_result", sa.Text(), nullable=True),
        )

    # Partial index for quick "pinned calcs" queries
    if not _index_exists("idx_calc_history_pinned"):
        op.create_index(
            "idx_calc_history_pinned",
            "calculation_history",
            ["salon_id", "created_at"],
            postgresql_where=sa.text("is_pinned = true"),
        )

    # Partial index for scenario membership queries
    if not _index_exists("idx_calc_history_scenario"):
        op.create_index(
            "idx_calc_history_scenario",
            "calculation_history",
            ["scenario_id"],
            postgresql_where=sa.text("scenario_id IS NOT NULL"),
        )


def downgrade() -> None:
    # Drop indexes first
    for idx in [
        "idx_calc_history_scenario",
        "idx_calc_history_pinned",
        "idx_scenarios_salon",
    ]:
        try:
            op.drop_index(idx)
        except Exception:
            pass

    # Drop columns
    for col in ["scenario_id", "source_links", "headline_result"]:
        if _column_exists("calculation_history", col):
            op.drop_column("calculation_history", col)

    # Drop table
    if _table_exists("scenarios"):
        op.drop_table("scenarios")
