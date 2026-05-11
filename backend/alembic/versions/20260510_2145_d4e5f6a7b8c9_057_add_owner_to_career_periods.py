"""add owner column to career_periods

Revision ID: d8e5f6a7b8c9
Revises: b2c3d4e5f6a7
Create Date: 2026-05-10 21:45:00.000000

Sprint 7 (TASK-7.7): Adds `owner` column to distinguish user vs spouse
career periods. Hand-written migration to avoid phantom ComCoi table drops
(LEARNINGS #12, #51).
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd8e5f6a7b8c9'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    # Hand-written: only add the column, no autogenerate phantom drops
    op.add_column(
        'career_periods',
        sa.Column(
            'owner',
            sa.String(10),
            nullable=False,
            server_default='user',
        ),
    )


def downgrade():
    op.drop_column('career_periods', 'owner')