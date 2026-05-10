"""053_add_net_worth_snapshots

Revision ID: c3d4e5f6a7b8
Revises: 052_add_career_periods
Create Date: 2026-05-09 21:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd8e9f0a1b2c3'
down_revision: Union[str, None] = 'b6477fa799ad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create net_worth_snapshots table for Sprint 6 TASK-6.5."""
    op.create_table(
        'net_worth_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        # Liquid assets
        sa.Column('cash_current_accounts', sa.Numeric(12, 2), nullable=False,
                  server_default='0'),
        sa.Column('cash_savings_other', sa.Numeric(12, 2), nullable=False,
                  server_default='0'),
        # Property
        sa.Column('property_primary_value', sa.Numeric(12, 2), nullable=False,
                  server_default='0'),
        sa.Column('property_other_value', sa.Numeric(12, 2), nullable=False,
                  server_default='0'),
        # Other assets
        sa.Column('business_value', sa.Numeric(12, 2), nullable=False,
                  server_default='0'),
        sa.Column('vehicle_value', sa.Numeric(12, 2), nullable=False,
                  server_default='0'),
        sa.Column('other_assets', sa.Numeric(12, 2), nullable=False,
                  server_default='0'),
        sa.Column('other_assets_label', sa.String(200), nullable=True),
        # Other debts
        sa.Column('other_debts', sa.Numeric(12, 2), nullable=False,
                  server_default='0'),
        sa.Column('other_debts_label', sa.String(200), nullable=True),
        # Metadata
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(),
                  onupdate=sa.func.now()),
    )


def downgrade() -> None:
    """Drop net_worth_snapshots table."""
    op.drop_table('net_worth_snapshots')