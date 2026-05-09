"""020 brand_purchases — additive brand-level expense breakdown table

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
Create Date: 2026-04-22 14:00:00.000000

WHY: Salon owners enter a single "Achats produits" line per month.
This table allows breaking that line down by brand (L'Oréal, Wella, etc.)
for management decisions and renegotiation leverage.

Back-compat: if no rows exist for a monthly_report_id, the UI falls back
to showing the original single-line Achats produits row. Data in
monthly_expenses is never deleted.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "b1c2d3e4f5a6"
# Points to migration 019 (monthly_primes_full_chain, revision f0a1b2c3d4e5)
down_revision = "f0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "brand_purchases",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "monthly_report_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("monthly_reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # e.g. "L'Oréal Professionnel" or a custom free-text name
        sa.Column("brand", sa.String(255), nullable=False),
        # HT amount — NUMERIC(12,2) — never FLOAT
        sa.Column("amount_ht", sa.Numeric(12, 2), nullable=False),
        # TVA rate: 0.0000 – 1.0000 (default 20%)
        sa.Column(
            "tva_rate",
            sa.Numeric(5, 4),
            nullable=False,
            server_default=sa.text("0.2000"),
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Index for fast look-up by monthly report
    op.create_index(
        "idx_brand_purch_report",
        "brand_purchases",
        ["monthly_report_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_brand_purch_report", table_name="brand_purchases")
    op.drop_table("brand_purchases")
