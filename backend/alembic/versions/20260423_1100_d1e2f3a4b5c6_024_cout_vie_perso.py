"""024 — Add cout_vie_perso_mensuel to salon_config

TASK-2.11.16: AE minimum vital mensuel.

For auto-entrepreneurs there is no salary; all money left after URSSAF + expenses
IS the owner's personal income. This column stores how much the AE needs each
month to cover rent, groceries, health cover, etc.

NULL = user has not set it yet (degrade gracefully, no block)
0    = explicitly set to zero (user confirmed they need nothing — very rare)

Revision ID: d1e2f3a4b5c6
Revises: c2d3e4f5a6b7
Create Date: 2026-04-23 11:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "d1e2f3a4b5c6"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "salon_config",
        sa.Column(
            "cout_vie_perso_mensuel",
            sa.Numeric(10, 2),
            nullable=True,
            comment=(
                "AE only — monthly personal living cost (loyer, courses, etc.). "
                "NULL = not yet configured. Included in point_mort for auto_micro salons."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("salon_config", "cout_vie_perso_mensuel")
