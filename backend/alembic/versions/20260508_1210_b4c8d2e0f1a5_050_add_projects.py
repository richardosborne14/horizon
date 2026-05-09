"""Add projects table.

Revision ID: b4c8d2e0f1a5
Revises: a3b7c1d9e2f4
Create Date: 2026-05-08 12:10:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b4c8d2e0f1a5"
down_revision: Union[str, None] = "a3b7c1d9e2f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
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
        sa.Column("project_type", sa.String(20), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        # Investment fields
        sa.Column("start_year", sa.Integer(), nullable=True),
        sa.Column("purchase_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("annual_income", sa.Numeric(10, 2), nullable=True),
        sa.Column("annual_expenses", sa.Numeric(10, 2), nullable=True),
        sa.Column("tax_rate", sa.Numeric(5, 3), nullable=True),
        # Event fields
        sa.Column("event_year", sa.Integer(), nullable=True),
        sa.Column("event_cost", sa.Numeric(12, 2), nullable=True),
        # Common
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
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
    )
    op.create_index(
        "ix_projects_user_id",
        "projects",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_projects_user_id", table_name="projects")
    op.drop_table("projects")