"""Add users.stripe_customer_id for Bubble migration (TASK-2.17.2).

The Bubble User record carries a StripeCustomerID field. Storing it directly
on the users table lets TASK-2.17.7 (Stripe verification) simply do:
    SELECT * FROM users WHERE stripe_customer_id IS NOT NULL
to find all imported users that previously had a Stripe relationship, then
verify their subscription status without re-fetching from the Bubble API.

This is a one-column additive change — no data backfill needed.

Revision ID: 041
Revises: 040
Create Date: 2026-04-29 19:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "041"
down_revision = "040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add nullable stripe_customer_id to users table."""
    op.add_column(
        "users",
        sa.Column(
            "stripe_customer_id",
            sa.String(255),
            nullable=True,
            comment=(
                "TASK-2.17.2: Bubble User.StripeCustomerID, preserved during migration. "
                "Used by TASK-2.17.7 to verify Stripe subscription status. "
                "NULL for native (non-imported) users unless they subscribe later."
            ),
        ),
    )


def downgrade() -> None:
    """Remove users.stripe_customer_id."""
    op.drop_column("users", "stripe_customer_id")
