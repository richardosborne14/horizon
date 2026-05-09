"""add marge_securite_pct and benefice_cible_pct to salon_config (Task 2.8.6)

Revision ID: b3c4d5e6f7a8
Revises: f6a7b8c9d0e1
Create Date: 2026-04-21 09:00:00.000000

WHY: Two separate margin percentages replace the single majoration_securite_benefice
field for the YTD cumul cash-flow alert feature. The old field (pricing calculator)
is kept untouched — these new fields are for the dashboard alert only.
"""
from alembic import op
import sqlalchemy as sa

revision = "b3c4d5e6f7a8"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Safety cushion for unexpected expenses (default 5%)
    op.add_column(
        "salon_config",
        sa.Column(
            "marge_securite_pct",
            sa.Numeric(5, 4),
            server_default=sa.text("'0.05'"),
            nullable=False,
        ),
    )
    # Profit target beyond break-even (default 10%)
    op.add_column(
        "salon_config",
        sa.Column(
            "benefice_cible_pct",
            sa.Numeric(5, 4),
            server_default=sa.text("'0.10'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("salon_config", "benefice_cible_pct")
    op.drop_column("salon_config", "marge_securite_pct")
