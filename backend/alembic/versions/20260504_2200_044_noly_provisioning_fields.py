"""Add noly_user_id, noly_company_id, logical_sku_key to noly_subscriptions (TASK-3.11)

Revision ID: 044
Revises: 043
Create Date: 2026-05-04 22:00:00.000000

WHY:
  - noly_user_id    — Noly platform user ID returned by POST /api/officer/users.
                      Stored for audit and future Noly API calls that need user ID.
  - noly_company_id — Noly platform company ID returned at provisioning.
  - logical_sku_key — Which product key (BIC vs BIC+) the subscription corresponds to.
                      Needed to determine which tax_type was provisioned on Noly.
                      Also stored in plan_name (existing), but an explicit column
                      is cleaner for query filtering.

All three columns are nullable: existing rows (bubble-imported) may not have them,
and the noly_subscriptions table already exists for grandfathered users.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "044"
down_revision = "043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add Noly provisioning fields to noly_subscriptions."""
    op.add_column(
        "noly_subscriptions",
        sa.Column(
            "noly_user_id",
            sa.String(255),
            nullable=True,
            comment="Noly platform user ID from POST /api/officer/users",
        ),
    )
    op.add_column(
        "noly_subscriptions",
        sa.Column(
            "noly_company_id",
            sa.String(255),
            nullable=True,
            comment="Noly platform company ID from POST /api/officer/users",
        ),
    )
    op.add_column(
        "noly_subscriptions",
        sa.Column(
            "logical_sku_key",
            sa.String(100),
            nullable=True,
            comment=(
                "Our internal product key, e.g. 'pack_bic_ccpilot_monthly_2026_05'. "
                "Determines BIC vs BIC+ for access checks and Noly plan mapping."
            ),
        ),
    )


def downgrade() -> None:
    """Remove Noly provisioning fields from noly_subscriptions."""
    op.drop_column("noly_subscriptions", "logical_sku_key")
    op.drop_column("noly_subscriptions", "noly_company_id")
    op.drop_column("noly_subscriptions", "noly_user_id")
