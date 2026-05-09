"""Add email drip state columns + email_dispatches table (TASK-2.12.15)

Revision ID: 046
Revises: 045
Create Date: 2026-05-05 11:00:00

WHY: Email-drip infrastructure for onboarding sequences. Three changes:
  1. users.email_drip_state (JSONB) — per-template send/skip ledger, idempotency key
  2. users.unsubscribed_at (TIMESTAMPTZ) — drip opt-out timestamp (NULL = subscribed)
  3. email_dispatches table — immutable audit log of every dispatch attempt
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic
revision = "046"
down_revision = "045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. users: email drip state + unsubscribe timestamp ──────────────────
    op.add_column(
        "users",
        sa.Column(
            "email_drip_state",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment=(
                "TASK-2.12.15: Per-template drip ledger. "
                "Keys are template_id; values are "
                "{sent_at: ISO} | {skipped_at: ISO, reason: str} | null."
            ),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "unsubscribed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment=(
                "TASK-2.12.15: Timestamp when user opted out of drip emails. "
                "NULL = subscribed. Does NOT block transactional emails "
                "(payslip-ready, password reset, etc.)."
            ),
        ),
    )

    # ── 2. email_dispatches: immutable audit log ─────────────────────────────
    op.create_table(
        "email_dispatches",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("template_id", sa.Text, nullable=False),
        sa.Column(
            "dispatched_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "status",
            sa.Text,
            nullable=False,
            comment="'sent' | 'failed' | 'skipped'",
        ),
        sa.Column("failure_reason", sa.Text, nullable=True),
        sa.Column(
            "unsubscribe_token",
            sa.Text,
            nullable=False,
            comment="Per-dispatch HMAC token for the unsubscribe link.",
        ),
    )
    # Index user_id for "get all dispatches for user" queries
    op.create_index("ix_email_dispatches_user_id", "email_dispatches", ["user_id"])
    # Index (template_id, dispatched_at DESC) for "last dispatch of template X" queries
    op.create_index(
        "ix_email_dispatches_template_dispatched",
        "email_dispatches",
        ["template_id", sa.text("dispatched_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_email_dispatches_template_dispatched", table_name="email_dispatches")
    op.drop_index("ix_email_dispatches_user_id", table_name="email_dispatches")
    op.drop_table("email_dispatches")
    op.drop_column("users", "unsubscribed_at")
    op.drop_column("users", "email_drip_state")
