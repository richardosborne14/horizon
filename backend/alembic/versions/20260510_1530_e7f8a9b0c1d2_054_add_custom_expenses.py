"""054_add_custom_expenses

Revision ID: e7f8a9b0c1d2
Revises: 053_add_net_worth_snapshots
Create Date: 2026-05-10 15:30:00.000000+00:00

Add custom_expenses JSONB column to user_profiles for TASK-7.3.
Users can add arbitrary expense categories beyond the 12 standard ones.
Stored as JSONB array: [{"id": "ce_001", "label": "Coworking", "amount": "250"}, ...]
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, None] = 'd8e9f0a1b2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add custom_expenses JSONB column to user_profiles."""
    op.add_column(
        'user_profiles',
        sa.Column(
            'custom_expenses',
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    """Remove custom_expenses column from user_profiles."""
    op.drop_column('user_profiles', 'custom_expenses')