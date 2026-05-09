"""Add investment_allocations table.

Revision ID: a3b7c1d9e2f4
Revises: 312d73722b8e
Create Date: 2026-05-08 12:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a3b7c1d9e2f4"
down_revision: Union[str, None] = "312d73722b8e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "investment_allocations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("vehicle_key", sa.String(20), nullable=False),
        sa.Column(
            "existing_balance",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "monthly_contribution",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "user_id", "vehicle_key", name="uq_user_vehicle"
        ),
    )
    op.create_index(
        "ix_investment_allocations_user_id",
        "investment_allocations",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_investment_allocations_user_id",
        table_name="investment_allocations",
    )
    op.drop_table("investment_allocations")