"""add_sasu_gerant_type_to_career_periods

Revision ID: 1e34841d335e
Revises: c5d6e7f8a9b0
Create Date: 2026-05-13 16:11:00.000000+00:00

Hand-written migration per LEARNINGS #51/#12 — autogenerate produces
phantom ComCoi table drops.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1e34841d335e'
down_revision: Union[str, None] = 'c5d6e7f8a9b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "career_periods",
        sa.Column(
            "sasu_gerant_type",
            sa.String(20),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("career_periods", "sasu_gerant_type")