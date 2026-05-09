"""
010 Monthly primes table

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-04-13 22:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a1"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # WHY idempotent check: migration 001 (initial_schema) was auto-generated AFTER
    # this migration was written, so it already includes the monthly_primes table
    # definition. On a fresh DB, 001 creates the table and this migration is a no-op.
    # On older DBs (pre-001 regen), this migration creates it. Both paths are safe.
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if "monthly_primes" in inspector.get_table_names():
        return  # Table already exists — skip silently

    # Create monthly_primes table for storing employee bonus calculations
    op.create_table(
        "monthly_primes",
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
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("days_worked", sa.Integer(), nullable=False),
        sa.Column(
            "objectif_initial",
            sa.Numeric(precision=12, scale=2),
            nullable=True,
        ),
        sa.Column(
            "deficit_anterieur",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "objectif_final",
            sa.Numeric(precision=12, scale=2),
            nullable=True,
        ),
        sa.Column(
            "resultat",
            sa.Numeric(precision=12, scale=2),
            nullable=True,
        ),
        sa.Column(
            "ecart",
            sa.Numeric(precision=12, scale=2),
            nullable=True,
        ),
        sa.Column(
            "prime_total",
            sa.Numeric(precision=12, scale=2),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        # Ensure only one monthly prime record per employee per month
        sa.UniqueConstraint(
            "employee_id", "year", "month",
            name="uq_monthly_prime_employee_year_month"
        ),
    )

    # Create indexes for performance
    op.create_index(
        "ix_monthly_primes_salon_id",
        "monthly_primes",
        ["salon_id"],
        unique=False,
    )
    op.create_index(
        "ix_monthly_primes_employee_id",
        "monthly_primes",
        ["employee_id"],
        unique=False,
    )
    op.create_index(
        "ix_monthly_primes_year_month",
        "monthly_primes",
        ["year", "month"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_monthly_primes_year_month", table_name="monthly_primes")
    op.drop_index("ix_monthly_primes_employee_id", table_name="monthly_primes")
    op.drop_index("ix_monthly_primes_salon_id", table_name="monthly_primes")
    op.drop_table("monthly_primes")
