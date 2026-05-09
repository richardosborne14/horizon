"""Add tva_rate to expenses (Task 2.8.3).

Revision ID: c9d0e1f2a3b4
Revises: b3c4d5e6f7a8
Create Date: 2026-04-21 10:00:00.000000

WHY: Every expense was previously calculated at a hardcoded 20% TVA rate.
Eric's 2026-04-20 feedback identified that presse/livres (5.5%), restauration
and transport (10%), and some exempt items (0%) were being miscalculated.
This migration adds a per-row tva_rate column so each expense stores the rate
that applies to it individually, enabling mixed-rate TVA aggregation.

AE guard: The CHECK constraint allows 0 as a valid rate. The service layer
additionally enforces tva_rate=0 for auto_micro salons server-side.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c9d0e1f2a3b4"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add tva_rate column with CHECK constraint and backfill existing rows at 0.200."""
    # Add the column — server_default backfills all existing rows at 0.200
    op.add_column(
        "expenses",
        sa.Column(
            "tva_rate",
            sa.Numeric(4, 3),
            nullable=False,
            server_default="0.200",
        ),
    )
    # Enforce only the four supported rates — any other value is a data integrity error
    op.create_check_constraint(
        "expenses_tva_rate_valid",
        "expenses",
        "tva_rate IN (0, 0.055, 0.100, 0.200)",
    )


def downgrade() -> None:
    """Remove tva_rate column and its CHECK constraint."""
    op.drop_constraint("expenses_tva_rate_valid", "expenses", type_="check")
    op.drop_column("expenses", "tva_rate")
