"""056_add_spouses

Revision ID: b2c3d4e5f6a7
Revises: 055_add_income_sources
Create Date: 2026-05-10 19:45:00.000000+00:00

Add spouses table for TASK-7.4 — partner financial identity.
1:1 relationship with users (unique on user_id).
Tracks identity, relationship type, professional status,
simplified revenue, and Conjointe Collaboratrice settings.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create spouses table."""
    op.create_table(
        'spouses',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('first_name', sa.String(100), nullable=True),
        sa.Column('birth_date', sa.Date(), nullable=True),
        sa.Column('relationship_type', sa.String(20), nullable=False, server_default='married'),
        sa.Column('status', sa.String(20), nullable=False, server_default='cdi'),
        sa.Column('ae_activity_type', sa.String(20), nullable=True),
        sa.Column('versement_liberatoire', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('monthly_gross_income', sa.Numeric(10, 2), nullable=True),
        sa.Column('growth_preset', sa.String(20), nullable=False, server_default='moderate'),
        sa.Column('growth_rate_custom', sa.Numeric(5, 4), nullable=True),
        sa.Column('is_conjointe_collaboratrice', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('cc_cotisation_option', sa.String(30), nullable=True),
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
    op.create_unique_constraint('uq_spouses_user_id', 'spouses', ['user_id'])
    op.create_foreign_key(
        'fk_spouses_user_id',
        'spouses',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    """Drop spouses table."""
    op.drop_constraint('fk_spouses_user_id', 'spouses', type_='foreignkey')
    op.drop_constraint('uq_spouses_user_id', 'spouses', type_='unique')
    op.drop_table('spouses')