"""032 fiches_salaire_tables

Creates the payslip/dossier/contrat tables and Stripe event idempotency table
for Sprint 2.13 per-submission payment flow.

Replaces the Sprint-3 wallet spec (which was never built) with a simpler
per-submission PaymentIntent model — Richard's decision 2026-04-24.

Revision ID: 032_fiches_salaire_tables
Revises: 031_migrate_pret_bancaire
Create Date: 2026-04-25 18:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "032_fiches_salaire_tables"
down_revision = "031_migrate_pret_bancaire"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create four tables for the fiches de salaire flow:

    1. payslip_dossiers      — per-salon setup state (one row per salon)
    2. payslip_submissions   — one row per (salon, employee, period_month, period_year)
    3. contrat_requests      — one-off contrat de travail orders
    4. stripe_events_processed — Stripe webhook event idempotency dedup table
    """

    # ── 1. payslip_dossiers ───────────────────────────────────────────────────
    op.create_table(
        "payslip_dossiers",
        sa.Column("salon_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="not_started"),
        sa.Column("paid_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("activated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "activated_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("stripe_payment_intent_id", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["salon_id"], ["salons.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "status IN ('not_started', 'paid', 'active', 'suspended')",
            name="ck_payslip_dossiers_status",
        ),
    )

    # ── 2. payslip_submissions ────────────────────────────────────────────────
    op.create_table(
        "payslip_submissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
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
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # Period
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        # Variables (from variables-1.pdf)
        sa.Column("prime_conventionnelle_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("ca_services_ht", sa.Numeric(12, 2), nullable=True),
        sa.Column("prime_revente_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("ca_revente_ht", sa.Numeric(12, 2), nullable=True),
        sa.Column("absence_conges_du", sa.Date(), nullable=True),
        sa.Column("absence_conges_au", sa.Date(), nullable=True),
        sa.Column("absence_maladie_du", sa.Date(), nullable=True),
        sa.Column("absence_maladie_au", sa.Date(), nullable=True),
        sa.Column("absence_injustifiee_du", sa.Date(), nullable=True),
        sa.Column("absence_injustifiee_au", sa.Date(), nullable=True),
        sa.Column("commentaire", sa.Text(), nullable=True),
        # Lifecycle
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("stripe_payment_intent_id", sa.Text(), nullable=True),
        sa.Column("stripe_invoice_id", sa.Text(), nullable=True),
        sa.Column("subject_token", sa.Text(), nullable=True),
        sa.Column("emailed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("pdf_url", sa.Text(), nullable=True),
        sa.Column("pdf_attached_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("pdf_attached_by", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "period_month BETWEEN 1 AND 12",
            name="ck_payslip_submissions_period_month",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'paid_pending_email', 'emailed', 'pending_review', 'pdf_attached', 'error')",
            name="ck_payslip_submissions_status",
        ),
        sa.UniqueConstraint(
            "salon_id",
            "employee_id",
            "period_month",
            "period_year",
            name="uq_payslip_submissions_per_period",
        ),
    )

    op.create_index(
        "idx_payslip_sub_salon_period",
        "payslip_submissions",
        ["salon_id", "period_year", "period_month"],
    )
    op.create_index(
        "idx_payslip_sub_token",
        "payslip_submissions",
        ["subject_token"],
    )

    # ── 3. contrat_requests ───────────────────────────────────────────────────
    op.create_table(
        "contrat_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "salon_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("salons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "requester_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # Prospective employee data from the request form
        sa.Column(
            "employee_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        # Lifecycle
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="paid_pending_email",
        ),
        sa.Column("stripe_payment_intent_id", sa.Text(), nullable=True),
        sa.Column("stripe_invoice_id", sa.Text(), nullable=True),
        sa.Column("subject_token", sa.Text(), nullable=True),
        sa.Column("emailed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("pdf_url", sa.Text(), nullable=True),
        sa.Column("pdf_attached_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('paid_pending_email', 'emailed', 'pdf_attached', 'error')",
            name="ck_contrat_requests_status",
        ),
    )

    op.create_index(
        "idx_contrat_requests_token",
        "contrat_requests",
        ["subject_token"],
    )
    op.create_index(
        "idx_contrat_requests_salon",
        "contrat_requests",
        ["salon_id"],
    )

    # ── 4. stripe_events_processed (idempotency) ──────────────────────────────
    op.create_table(
        "stripe_events_processed",
        sa.Column("event_id", sa.Text(), primary_key=True),
        sa.Column(
            "processed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    """
    Drop all four tables in reverse dependency order.

    WHY: payslip_submissions references salons + employees;
    payslip_dossiers references salons + users;
    contrat_requests references salons + users.
    Indexes are dropped automatically with their tables.
    """
    op.drop_table("stripe_events_processed")
    op.drop_table("contrat_requests")
    op.drop_table("payslip_submissions")
    op.drop_table("payslip_dossiers")
