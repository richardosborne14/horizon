"""Add user_label to calculation_history — Task 2.10.7

user_label is a separate TEXT column for explicit user-supplied names.
Distinct from `label` (legacy auto-generated field) so the two can coexist
without clobbering each other during the transition.

Display priority (frontend):
  user_label (user-set) > headline_result (backend-generated) > autoLabel() (frontend fallback)

Revision ID: c3d4e5f6a7b8
Revises: 20260422_1400_b1c2d3e4f5a6_020_brand_purchases
Create Date: 2026-04-22 18:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
# WHY tuple: migrations 019 (a0b1c2d3e4f5) and 020 (b1c2d3e4f5a6) are two independent
# branches both applied to the DB. This migration merges them into a single head while
# adding the user_label column.
revision = 'c3d4e5f6a7b8'
down_revision = ('a0b1c2d3e4f5', 'b1c2d3e4f5a6')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # WHY nullable: existing rows have no user-assigned name (they use the frontend auto-label)
    op.add_column(
        'calculation_history',
        sa.Column('user_label', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('calculation_history', 'user_label')
