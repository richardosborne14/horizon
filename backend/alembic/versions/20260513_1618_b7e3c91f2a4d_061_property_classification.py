"""add_property_classification_to_net_worth_snapshots

Revision ID: b7e3c91f2a4d
Revises: 1e34841d335e
Create Date: 2026-05-13 16:18:00.000000+00:00

Hand-written migration per LEARNINGS #51/#12.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e3c91f2a4d'
down_revision: Union[str, None] = '1e34841d335e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "net_worth_snapshots",
        sa.Column(
            "residence_type",
            sa.String(30),
            nullable=False,
            server_default="primary_residence",
        ),
    )
    op.add_column(
        "net_worth_snapshots",
        sa.Column(
            "property_other_type",
            sa.String(30),
            nullable=False,
            server_default="none",
        ),
    )


def downgrade() -> None:
    op.drop_column("net_worth_snapshots", "property_other_type")
    op.drop_column("net_worth_snapshots", "residence_type")