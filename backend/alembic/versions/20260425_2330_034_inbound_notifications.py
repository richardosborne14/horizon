"""034 — inbound email processing tables + payslip notifications

Revision ID: 034_inbound_notifications
Revises: 033_dossier_subject_token
Create Date: 2026-04-25 23:30:00+00:00

WHY: TASK-2.13.3 inbound email poller needs:
  - processed_emails:         IMAP dedup by RFC822 Message-ID
  - payslip_notifications:    in-app notification bell rows for salon users
  - payslip_unmatched_emails: audit queue for inbound mails that couldn't be matched
  - admin_audit_log:          immutable mutation log for admin actions (2.13.7 groundwork)
  - payslip_submissions.needs_review_note: free-text flag set by inbound poller when PDF
    attribution is ambiguous (multiple PDFs, multiple employees in same period).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "034_inbound_notifications"
down_revision = "033_dossier_subject_token"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create inbound email tables and add needs_review_note to submissions."""

    # ── processed_emails ──────────────────────────────────────────────────────
    # One row per RFC822 Message-ID. Prevents the IMAP poller from processing
    # the same email twice if the polling cycle races.
    op.create_table(
        "processed_emails",
        sa.Column("message_id", sa.Text(), nullable=False),
        sa.Column(
            "processed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("message_id", name="pk_processed_emails"),
    )

    # ── payslip_notifications ─────────────────────────────────────────────────
    # In-app bell notifications. One row per user event (PDF ready, etc.).
    # read_at = NULL means unread; set by POST /notifications/{id}/read.
    op.create_table(
        "payslip_notifications",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("notification_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("link", sa.Text(), nullable=True),
        sa.Column("read_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_payslip_notifications"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_payslip_notifications_user",
            ondelete="CASCADE",
        ),
    )
    # Index for fast unread count per user (most common query: bell badge)
    op.create_index(
        "ix_payslip_notifications_user_unread",
        "payslip_notifications",
        ["user_id", "read_at"],
    )

    # ── payslip_unmatched_emails ──────────────────────────────────────────────
    # Inbound emails that the poller couldn't match to a submission/contrat.
    # Eric reviews these in the admin panel and manually links them.
    op.create_table(
        "payslip_unmatched_emails",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("message_id", sa.Text(), nullable=False),
        sa.Column("from_address", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body_excerpt", sa.Text(), nullable=True),
        sa.Column("received_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("attachment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Text(), nullable=False, server_default="unmatched"),
        sa.Column("attached_submission_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_payslip_unmatched_emails"),
        sa.UniqueConstraint("message_id", name="uq_payslip_unmatched_emails_message_id"),
    )

    # ── admin_audit_log ───────────────────────────────────────────────────────
    # Immutable record of every admin mutation. Written by admin endpoints.
    # Provides accountability: "who activated this dossier?", "who uploaded this PDF?"
    op.create_table(
        "admin_audit_log",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("admin_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Text(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_admin_audit_log"),
        sa.ForeignKeyConstraint(
            ["admin_user_id"],
            ["users.id"],
            name="fk_admin_audit_log_user",
            ondelete="SET NULL",
        ),
    )

    # ── payslip_submissions.needs_review_note ─────────────────────────────────
    # Set by the inbound poller when PDF attribution is ambiguous.
    # e.g. "Attribution PDF à vérifier — plusieurs fichiers reçus."
    # Admin sees this in the stuck-submissions tab (2.13.7).
    op.add_column(
        "payslip_submissions",
        sa.Column("needs_review_note", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Remove inbound email tables and needs_review_note column."""
    op.drop_column("payslip_submissions", "needs_review_note")
    op.drop_table("admin_audit_log")
    op.drop_table("payslip_unmatched_emails")
    op.drop_index("ix_payslip_notifications_user_unread", table_name="payslip_notifications")
    op.drop_table("payslip_notifications")
    op.drop_table("processed_emails")
