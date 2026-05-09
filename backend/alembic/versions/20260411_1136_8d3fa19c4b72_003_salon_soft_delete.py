"""003_salon_soft_delete

Add deleted_at column to salons table for soft-delete support.

WHY: Our users are non-technical hairdressers who may accidentally delete their
salon data. Soft delete preserves all salon data (employees, reports, payslips)
for admin recovery while hiding the salon from all regular API queries.

Revision ID: 8d3fa19c4b72
Revises: a4f7c2d81b3e
Create Date: 2026-04-11 11:36:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8d3fa19c4b72"
down_revision: Union[str, None] = "a4f7c2d81b3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add deleted_at nullable column to salons and index it.

    Nullable — NULL means active (not deleted).
    Set to a timestamp when the salon is soft-deleted.
    Indexed for performance: all salon queries filter WHERE deleted_at IS NULL.
    Existing rows are unaffected (they get NULL = active).
    """
    op.add_column(
        "salons",
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index("ix_salons_deleted_at", "salons", ["deleted_at"])


def downgrade() -> None:
    """Remove deleted_at from salons (and its index)."""
    op.drop_index("ix_salons_deleted_at", table_name="salons")
    op.drop_column("salons", "deleted_at")
