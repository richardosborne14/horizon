"""Add subscription_events table for TASK-2.16.8 conversion/churn metrics.

Tracks trial starts, paid conversions, and cancellations (churn) from
Stripe webhook events. Segmented by sku_group and cohort (new vs legacy).

Revision ID: 039
Revises: 20260429_1500_038_add_legacy_pricing_plan
Create Date: 2026-04-29 17:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers
revision = "039"
down_revision = "038_legacy_pricing_plan"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create subscription_events table."""
    op.create_table(
        "subscription_events",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # user_id nullable: Stripe events may arrive before we resolve the user
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        # 'trial_started' | 'converted_to_paid' | 'churned'
        sa.Column("event_type", sa.String(50), nullable=False),
        # The Stripe subscription ID that this event relates to
        sa.Column("stripe_subscription_id", sa.Text(), nullable=True),
        # The Stripe customer ID
        sa.Column("stripe_customer_id", sa.Text(), nullable=True),
        # Logical SKU key (e.g. 'ccpilot_monthly_2026_05')
        sa.Column("logical_sku_key", sa.Text(), nullable=True),
        # Derived SKU group for cohort charting: 'ccpilot_solo' | 'pack_bic_ccpilot' | 'pack_bic_plus_ccpilot'
        sa.Column("sku_group", sa.String(50), nullable=True),
        # When the Stripe event fired (from event.created timestamp)
        sa.Column(
            "occurred_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # The raw Stripe event ID — UNIQUE so webhook replays are idempotent
        sa.Column("stripe_event_id", sa.Text(), nullable=True, unique=True),
        # Metadata / notes for debugging
        sa.Column("notes", sa.Text(), nullable=True),
        comment=(
            "TASK-2.16.8 — Subscription lifecycle events sourced from Stripe webhooks. "
            "Used for post-restructuration conversion/churn metrics on the admin dashboard. "
            "One row per event (trial_started, converted_to_paid, churned). "
            "Idempotent via stripe_event_id UNIQUE constraint."
        ),
    )

    # Index for the three main query patterns in the metrics endpoint
    op.create_index(
        "ix_subscription_events_event_type",
        "subscription_events",
        ["event_type"],
    )
    op.create_index(
        "ix_subscription_events_sku_group",
        "subscription_events",
        ["sku_group"],
    )
    op.create_index(
        "ix_subscription_events_occurred_at",
        "subscription_events",
        ["occurred_at"],
    )


def downgrade() -> None:
    """Drop subscription_events table."""
    op.drop_index("ix_subscription_events_occurred_at", "subscription_events")
    op.drop_index("ix_subscription_events_sku_group", "subscription_events")
    op.drop_index("ix_subscription_events_event_type", "subscription_events")
    op.drop_table("subscription_events")
