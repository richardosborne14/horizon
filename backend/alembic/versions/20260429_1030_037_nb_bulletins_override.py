"""Add nb_bulletins_override to monthly_reports

TASK-2.15.5 — Users can override the inferred bulletin count for the savings
engine. NULL = use len(active_employees). Set = use this number instead.

Revision ID: 037_nb_bulletins_override
Revises: a8b9c0d1e2f3
Create Date: 2026-04-29
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "037_nb_bulletins_override"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add nb_bulletins_override (NULLABLE INTEGER) to monthly_reports.

    WHY NULLABLE: NULL means "use inferred count (nb active employees)".
    A value of 0 means "no bulletins this month" (e.g. all employees on leave).
    A value > nb_employees is also valid (e.g. adding a new employee mid-year).
    """
    op.add_column(
        "monthly_reports",
        sa.Column(
            "nb_bulletins_override",
            sa.Integer(),
            nullable=True,
            comment=(
                "TASK-2.15.5: user-supplied bulletin count override for savings engine. "
                "NULL = infer from active employees. 0 = no bulletins this month."
            ),
        ),
    )


def downgrade() -> None:
    """Remove nb_bulletins_override column."""
    op.drop_column("monthly_reports", "nb_bulletins_override")
