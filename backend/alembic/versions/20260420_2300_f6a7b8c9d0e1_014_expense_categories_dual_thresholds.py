"""expense_categories: add percent_ca_seuil_alerte and percent_ca_min columns (Task 2.8.7)

WHY: Eric's 2026 benchmark grid introduces two new threshold concepts:
  - percent_ca_seuil_alerte: upper ceiling beyond which a red alert is raised
  - percent_ca_min: lower floor (used for Marketing = "too low = no visibility";
                    also used for EBITDA inverted logic = "too low = danger")

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-20 23:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'expense_categories',
        sa.Column('percent_ca_seuil_alerte', sa.Numeric(5, 4), nullable=True)
    )
    op.add_column(
        'expense_categories',
        sa.Column('percent_ca_min', sa.Numeric(5, 4), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('expense_categories', 'percent_ca_min')
    op.drop_column('expense_categories', 'percent_ca_seuil_alerte')
