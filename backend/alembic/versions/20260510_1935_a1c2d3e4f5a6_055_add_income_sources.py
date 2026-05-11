"""055_add_income_sources

Revision ID: a1c2d3e4f5a6
Revises: 054_add_custom_expenses
Create Date: 2026-05-10 19:35:00.000000+00:00

Add income_sources table for TASK-7.5 — individual revenue streams for
user or spouse. Replaces the single monthly_gross_ca field with tracked
sources each with earner, type, frequency, duration, confidence, and growth.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1c2d3e4f5a6'
down_revision: Union[str, None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create income_sources table."""
    op.create_table(
        'income_sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('earner', sa.String(10), nullable=False, server_default='user'),
        sa.Column('label', sa.String(200), nullable=False),
        sa.Column('source_type', sa.String(30), nullable=False, server_default='client'),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('frequency', sa.String(20), nullable=False, server_default='monthly'),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('confidence', sa.String(20), nullable=False, server_default='high'),
        sa.Column('annual_growth_rate', sa.Numeric(5, 4), nullable=True),
        sa.Column('is_ae_revenue', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index('ix_income_sources_user_id', 'income_sources', ['user_id'])
    op.create_foreign_key(
        'fk_income_sources_user_id',
        'income_sources',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    """Drop income_sources table."""
    op.drop_constraint('fk_income_sources_user_id', 'income_sources', type_='foreignkey')
    op.drop_index('ix_income_sources_user_id', table_name='income_sources')
    op.drop_table('income_sources')