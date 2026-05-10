"""052_add_career_periods

Revision ID: b6477fa799ad
Revises: 051_add_loans
Create Date: 2026-05-09 18:29:14.355212+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b6477fa799ad'
down_revision: Union[str, None] = '051_add_loans'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create career_periods table for Sprint 6 TASK-6.1."""
    op.create_table(
        'career_periods',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('period_type', sa.String(20), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('employer_name', sa.String(200), nullable=True),
        sa.Column('job_title', sa.String(200), nullable=True),
        sa.Column('annual_gross', sa.Numeric(12, 2), nullable=True),
        sa.Column('is_full_time', sa.Boolean(), nullable=False,
                  server_default=sa.text('true')),
        sa.Column('time_percentage', sa.Integer(), nullable=False,
                  server_default=sa.text('100')),
        sa.Column('pension_regime', sa.String(20), nullable=True),
        sa.Column('notes', sa.String(500), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False,
                  server_default=sa.text('0')),
        sa.Column('is_active', sa.Boolean(), nullable=False,
                  server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(),
                  onupdate=sa.func.now()),
    )


def downgrade() -> None:
    """Drop career_periods table."""
    op.drop_table('career_periods')