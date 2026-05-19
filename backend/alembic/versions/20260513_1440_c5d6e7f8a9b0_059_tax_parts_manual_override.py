"""add_tax_parts_manual_override_to_user_profiles

Revision ID: c5d6e7f8a9b0
Revises: f769cd8f973d
Create Date: 2026-05-13 14:40:00.000000+00:00

Hand-written migration per LEARNINGS #51/#12 — autogenerate produces
phantom ComCoi table drops.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5d6e7f8a9b0'
down_revision: Union[str, None] = 'f769cd8f973d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column(
            "tax_parts_manual_override",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "tax_parts_manual_override")