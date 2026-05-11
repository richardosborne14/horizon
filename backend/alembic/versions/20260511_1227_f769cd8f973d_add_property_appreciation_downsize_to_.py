"""add_property_appreciation_downsize_to_net_worth

Revision ID: f769cd8f973d
Revises: 5f33d1354fee
Create Date: 2026-05-11 12:27:54.954256+00:00

Hand-written migration per LEARNINGS #51/#12 — autogenerate produces
phantom ComCoi table drops.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f769cd8f973d'
down_revision: Union[str, None] = '5f33d1354fee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "net_worth_snapshots",
        sa.Column(
            "property_appreciation_rate",
            sa.Numeric(5, 4),
            server_default="0.02",
            nullable=True,
        ),
    )
    op.add_column(
        "net_worth_snapshots",
        sa.Column(
            "downsize_enabled",
            sa.Boolean(),
            server_default="false",
            nullable=True,
        ),
    )
    op.add_column(
        "net_worth_snapshots",
        sa.Column(
            "downsize_year",
            sa.Integer(),
            nullable=True,
        ),
    )
    op.add_column(
        "net_worth_snapshots",
        sa.Column(
            "downsize_target_value",
            sa.Numeric(12, 2),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("net_worth_snapshots", "downsize_target_value")
    op.drop_column("net_worth_snapshots", "downsize_year")
    op.drop_column("net_worth_snapshots", "downsize_enabled")
    op.drop_column("net_worth_snapshots", "property_appreciation_rate")