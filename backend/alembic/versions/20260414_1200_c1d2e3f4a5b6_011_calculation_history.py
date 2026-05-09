"""
011 Calculation history table

Persists calculator inputs + outputs per salon so users can revisit and
reload any past calculation. Auto-prune (max 25 per calculator type per
salon) is handled at the application layer, not in the DB.

Revision ID: c1d2e3f4a5b6
Revises: b2c3d4e5f6a1
Create Date: 2026-04-14 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "b2c3d4e5f6a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the calculation_history table."""
    op.create_table(
        "calculation_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "salon_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("salons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # One of: taxes, primes, seuil_salaire, volume_clients, marge_revente
        sa.Column("calculator_type", sa.String(50), nullable=False),
        # Auto-generated smart label; user can rename inline
        sa.Column("label", sa.String(255), nullable=True),
        # Full form inputs at time of calculation (JSON blob)
        sa.Column(
            "inputs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        # Full API response at time of calculation (JSON blob)
        sa.Column(
            "outputs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        # Pinned entries are excluded from auto-prune
        sa.Column(
            "is_pinned",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Composite index for the hot query: list history for salon + calculator
    op.create_index(
        "ix_calc_history_salon_type_created",
        "calculation_history",
        ["salon_id", "calculator_type", sa.text("created_at DESC")],
        unique=False,
    )

    # Index for user-level queries (e.g. CoCo context lookup)
    op.create_index(
        "ix_calc_history_user_id",
        "calculation_history",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the calculation_history table."""
    op.drop_index("ix_calc_history_user_id", table_name="calculation_history")
    op.drop_index("ix_calc_history_salon_type_created", table_name="calculation_history")
    op.drop_table("calculation_history")
