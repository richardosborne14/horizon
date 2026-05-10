"""Add loans table for structured loan/mortgage tracking (TASK-6.3).

Loans have fixed nominal monthly payments that do NOT inflate.
The projection engine reads loan data and drops payments after end_date.
"""

revision = "051_add_loans"
down_revision = "b4c8d2e0f1a5"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    op.create_table(
        "loans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("loan_type", sa.String(30), nullable=False),
        sa.Column("monthly_payment", sa.Numeric(10, 2), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("remaining_months", sa.Integer(), nullable=True),
        sa.Column("original_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("interest_rate", sa.Numeric(5, 4), nullable=True),
        sa.Column("remaining_balance", sa.Numeric(12, 2), nullable=True),
        sa.Column("insurance_monthly", sa.Numeric(8, 2), nullable=True, server_default="0"),
        sa.Column("end_action", sa.String(20), nullable=False, server_default="'freed'"),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("loans")