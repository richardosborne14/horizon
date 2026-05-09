"""Add heures_supplementaires to payslip_submissions (TASK-2.12.4)

Revision ID: 043
Revises: 042
Create Date: 2026-05-04 21:00:00.000000

WHY: Eric's spec (PDF page 17) requires an "Heures supplémentaires" field on the
variables form so Marie has all information needed to compute the payslip. The field
was missing from the original Sprint 2.13 submission schema. Added as nullable so
existing rows are not broken.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "043"
down_revision = "042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add heures_supplementaires (nullable NUMERIC(5,2)) to payslip_submissions."""
    op.add_column(
        "payslip_submissions",
        sa.Column(
            "heures_supplementaires",
            sa.Numeric(precision=5, scale=2),
            nullable=True,
            comment="Heures supplémentaires pour la période (Eric PDF p.17)",
        ),
    )


def downgrade() -> None:
    """Drop heures_supplementaires from payslip_submissions."""
    op.drop_column("payslip_submissions", "heures_supplementaires")
