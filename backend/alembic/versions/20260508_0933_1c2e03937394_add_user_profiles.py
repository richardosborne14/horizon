"""add_user_profiles

Revision ID: 1c2e03937394
Revises: 046
Create Date: 2026-05-08 09:33:00+00:00

Creates the user_profiles table — the central data model for Horizon.
One profile per user (1:1). Monthly expenses stored as JSONB.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '1c2e03937394'
down_revision: Union[str, None] = '046'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_profiles',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('birth_date', sa.Date(), nullable=True),
        sa.Column('target_retirement_age', sa.Integer(), server_default='67', nullable=False),
        sa.Column('tax_parts', sa.Numeric(precision=3, scale=1), server_default='1.0', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='ae', nullable=False),
        sa.Column('ae_activity_type', sa.String(length=50), server_default='bnc_non_reglementee', nullable=False),
        sa.Column('has_versement_liberatoire', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('monthly_gross_ca', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('growth_preset', sa.String(length=20), server_default='moderate', nullable=False),
        sa.Column('growth_rate_custom', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('cesu_annual', sa.Numeric(precision=10, scale=2), server_default='0', nullable=False),
        sa.Column('charity_annual', sa.Numeric(precision=10, scale=2), server_default='0', nullable=False),
        sa.Column('caf_override_monthly', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('monthly_expenses', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('monthly_revenue_goal', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('world_scale', sa.String(length=20), server_default='moderate', nullable=False),
        sa.Column('status_change_enabled', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('status_change_year', sa.Integer(), nullable=True),
        sa.Column('status_change_target', sa.String(length=20), nullable=True),
        sa.Column('status_change_savings', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_user_profiles_user_id'), 'user_profiles', ['user_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_user_profiles_user_id'), table_name='user_profiles')
    op.drop_table('user_profiles')