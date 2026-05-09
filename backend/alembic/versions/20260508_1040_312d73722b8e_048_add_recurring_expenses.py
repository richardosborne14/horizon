"""048 add recurring_expenses

Create the recurring_expenses table — time-bounded annual expenses
that recur yearly but have a defined start and end year.

Examples: loan repayments, annual holiday budget, kid's sports club.
The projection engine queries SUM(annual_amount) per year from this table.

WHY: Sprint 2 — Recurring bounded expenses. Complements life entities
by handling costs that don't have an "age" but do have a time range.

Revision ID: 312d73722b8e
Revises: 5b5fe8574e7d
Create Date: 2026-05-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = "312d73722b8e"
down_revision = "5b5fe8574e7d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recurring_expenses",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "label",
            sa.String(200),
            nullable=False,
        ),
        sa.Column(
            "annual_amount",
            sa.Numeric(10, 2),
            nullable=False,
        ),
        sa.Column(
            "from_year",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "to_year",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "category",
            sa.String(50),
            nullable=True,
        ),
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
        ),
    )


def downgrade() -> None:
    op.drop_table("recurring_expenses")