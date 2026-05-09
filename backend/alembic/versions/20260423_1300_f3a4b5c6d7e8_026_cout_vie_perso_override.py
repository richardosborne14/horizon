"""026 — Add cout_vie_perso_override to monthly_reports

TASK-2.11.17: Per-month minimum vital for AE in Pilotage.

The salon-wide default lives in salon_config.cout_vie_perso_mensuel (migration 024).
This column adds a per-month override so an AE user can customise the amount for
any individual month without changing the default that flows into all other months.

Storage pattern:
    NULL  → use salon_config.cout_vie_perso_mensuel (fallback to 0 if also null)
    0     → explicitly zero for this month (AE confirmed no personal draw needed)
    > 0   → override for this month only

The column is ignored entirely for non-AE business types; the backend enforces
this in the PUT endpoint (422 if non-AE salon tries to set it).

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-04-23 13:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "monthly_reports",
        sa.Column(
            "cout_vie_perso_override",
            sa.Numeric(10, 2),
            nullable=True,
            comment=(
                "AE only — per-month override of salon_config.cout_vie_perso_mensuel. "
                "NULL = inherit salon default. 0 = explicitly zero for this month. "
                "Ignored for non-auto_micro business types."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("monthly_reports", "cout_vie_perso_override")
