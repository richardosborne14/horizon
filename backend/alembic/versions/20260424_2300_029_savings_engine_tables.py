"""029 savings engine tables

Revision ID: 029_savings_engine_tables
Revises: 028_remove_bnc_statuses
Create Date: 2026-04-24 23:00:00.000000

WHY (TASK-2.12.1): Creates the savings engine infrastructure:
  - paid_customer_flags: admin-managed flags marking which salons are paying
    ComCoi customers for each savings channel
  - salon_savings_cache: stores the computed savings report (JSONB) per salon
    to serve the /mes-economies page in < 10 ms on cache hits
  - has_website column on salons: NULL=unknown, TRUE/FALSE used to determine
    whether to surface the site_web opportunity channel
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = "029_savings_engine_tables"
down_revision = "028_remove_bnc_statuses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create paid_customer_flags, salon_savings_cache tables and add has_website
    to salons.
    """
    # ── paid_customer_flags ───────────────────────────────────────────────────
    op.create_table(
        "paid_customer_flags",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("salon_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(100), nullable=False),
        sa.Column("activated_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_by_user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["salon_id"], ["salons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("salon_id", "channel", name="uq_paid_customer_flags_salon_channel"),
    )
    op.create_index("ix_paid_customer_flags_salon_id", "paid_customer_flags", ["salon_id"])

    # ── salon_savings_cache ───────────────────────────────────────────────────
    op.create_table(
        "salon_savings_cache",
        sa.Column("salon_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("computed_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("report_json", JSONB, nullable=False),
        sa.PrimaryKeyConstraint("salon_id"),
        sa.ForeignKeyConstraint(["salon_id"], ["salons.id"], ondelete="CASCADE"),
    )

    # ── has_website on salons ─────────────────────────────────────────────────
    op.add_column(
        "salons",
        sa.Column("has_website", sa.Boolean, nullable=True),
    )


def downgrade() -> None:
    """Remove savings engine tables and has_website column."""
    op.drop_column("salons", "has_website")
    op.drop_table("salon_savings_cache")
    op.drop_index("ix_paid_customer_flags_salon_id", table_name="paid_customer_flags")
    op.drop_table("paid_customer_flags")
