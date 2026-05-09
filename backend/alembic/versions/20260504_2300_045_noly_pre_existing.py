"""Add noly_pre_existing to noly_subscriptions (TASK-3.11)

Revision ID: 045
Revises: 044
Create Date: 2026-05-04 23:00:00.000000

WHY:
  At Stripe checkout time we probe Noly's magic-link endpoint *before* calling
  POST /api/officer/users.  If the probe succeeds (201) the user already has a
  Noly account in our white-label — e.g. they migrated from Bubble, subscribed
  before, or their sub was paused.  We skip provisioning, note the flag here,
  and store the Noly user ID we got for free from the probe response.

  noly_pre_existing = True  → account already existed; we did NOT call
                               POST /api/officer/users.
  noly_pre_existing = False → we provisioned the account ourselves.
  noly_pre_existing = NULL  → row predates this column (migration 044 and older).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "045"
down_revision = "044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add noly_pre_existing flag to noly_subscriptions."""
    op.add_column(
        "noly_subscriptions",
        sa.Column(
            "noly_pre_existing",
            sa.Boolean,
            nullable=True,
            comment=(
                "True = user already existed in Noly white-label at checkout "
                "(detected via magic-link probe). False = we provisioned them. "
                "NULL = row predates this column."
            ),
        ),
    )


def downgrade() -> None:
    """Remove noly_pre_existing flag from noly_subscriptions."""
    op.drop_column("noly_subscriptions", "noly_pre_existing")
