"""006 monthly report emprunt

Add remboursement_emprunt column to monthly_reports table.

WHY: The point mort (break-even) calculation requires loan repayment as a
separate cash outflow line item. It sits between Total A+B and TOTAL DÉCAISSEMENT
in Eric's rentabilité grid. It was missing from the initial schema.

Revision ID: d2e3f4a5b6c7
Revises: c9d8e7f6a5b4
Create Date: 2026-04-11 18:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, None] = "c9d8e7f6a5b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add remboursement_emprunt to monthly_reports."""
    op.add_column(
        "monthly_reports",
        sa.Column(
            "remboursement_emprunt",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default="0.00",
            comment="Monthly loan repayment amount — used in TOTAL DÉCAISSEMENT calculation",
        ),
    )


def downgrade() -> None:
    """Remove remboursement_emprunt from monthly_reports."""
    op.drop_column("monthly_reports", "remboursement_emprunt")
