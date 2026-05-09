"""005 — eirl_legacy_flag

Add business_type_legacy boolean to salons.
Flag existing EIRL salons so the UI shows an amber legacy badge.

EIRL was suppressed by loi n°2022-172 du 14 février 2022 (effective 15/02/2022).
No new EIRLs can be created. Existing EIRLs continue to function.
This migration does NOT change any business_type value — that is a fiscal decision
the salon owner must make with their comptable.

See: dev-docs/resources/06-social-charges-reference.md §8
     TASK-2.14.2

Revision ID: a8b9c0d1e2f3
Revises: 036_payslip_honoraires
Create Date: 2026-04-27 15:30:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "a8b9c0d1e2f3"
# WHY: branched from migration 004 by mistake — corrected to chain after 036
# (the true latest migration when this was authored 2026-04-27).
down_revision = "036_payslip_honoraires"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add business_type_legacy column (default false for all existing salons)
    op.add_column(
        "salons",
        sa.Column(
            "business_type_legacy",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # Flag existing EIRL salons as legacy
    # WHY: We don't change the business_type value — that would silently alter the
    # dirigeant's fiscal regime. We only flag them so the UI can show the
    # "statut historique" badge and prevent selecting EIRL for new salons.
    op.execute(
        sa.text(
            "UPDATE salons SET business_type_legacy = true WHERE business_type = 'eirl'"
        )
    )


def downgrade() -> None:
    op.drop_column("salons", "business_type_legacy")
