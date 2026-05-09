"""004 monthly salary charges fields

Rename monthly_salaries.salaire_net → salaire_brut (the primary input for all
employee types). Add salaire_net_approx (display-only auto-calc) and
charges_overridden (lock/unlock UX flag).

WHY: Task 2.3 — salary entry with auto-calculated social charges.
The column rename clarifies that the primary input is always the gross salary
(salaire brut). For dirigeants TNS, this column holds their net remuneration
(semantically different, but same DB column — distinguishable by role_type).

Revision ID: f3a1b2c4d5e6
Revises: 8d3fa19c4b72
Create Date: 2026-04-11
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f3a1b2c4d5e6"
down_revision = "8d3fa19c4b72"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename salaire_net → salaire_brut
    # For salarié/apprenti: this is the gross salary (brut).
    # For dirigeant TNS: this is their net remuneration (kept in same col for simplicity).
    op.alter_column("monthly_salaries", "salaire_net", new_column_name="salaire_brut")

    # Add salaire_net_approx — display-only, auto-calculated from salaire_brut.
    # Shows approximate take-home pay. NOT used in cost calculations.
    op.add_column(
        "monthly_salaries",
        sa.Column("salaire_net_approx", sa.Numeric(12, 2), nullable=True),
    )

    # Add charges_overridden — true when user has manually overridden the lock.
    # When true, backend does NOT recalculate cotisations_sociales on update.
    op.add_column(
        "monthly_salaries",
        sa.Column(
            "charges_overridden",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("monthly_salaries", "charges_overridden")
    op.drop_column("monthly_salaries", "salaire_net_approx")
    op.alter_column("monthly_salaries", "salaire_brut", new_column_name="salaire_net")
