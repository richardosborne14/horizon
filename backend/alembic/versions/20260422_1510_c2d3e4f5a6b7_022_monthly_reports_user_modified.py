"""022 monthly_reports_user_modified — Task 2.10.8

Adds `is_user_modified` boolean to monthly_reports.

WHY: A month created by wizard-duplication starts as "estimation" data.
The first time the user edits any field in that month (CA, expenses, salaries)
the flag flips to True so the frontend can show an "réel" vs "estim" badge.

Default=false so ALL existing rows are treated as estimation until touched.
This is the correct safe default — we have no record of prior edits.

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-04-22 15:10:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c2d3e4f5a6b7"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "monthly_reports",
        sa.Column(
            "is_user_modified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_index(
        "idx_monthly_reports_modified",
        "monthly_reports",
        ["salon_id", "year", "is_user_modified"],
    )


def downgrade() -> None:
    op.drop_index("idx_monthly_reports_modified", table_name="monthly_reports")
    op.drop_column("monthly_reports", "is_user_modified")
