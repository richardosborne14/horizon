"""Add bubble_*_id columns + bubble_import_runs table for TASK-2.17.1.

Also folds in schema items referenced in later 2.17 tasks to avoid a churn
of micro-migrations:
  - users.last_paid_at          (TASK-2.17.7 — lapsed sub last payment date)
  - users.welcome_email_sent_at (TASK-2.17.9 — idempotency guard for batch send)
  - blog_articles enhancement columns (TASK-2.17.8 — AI cleanup diff viewer)

Every migration touch is ADDITIVE (NULL-able or has a server default). No
existing data is altered. Every new non-PK column gets a UNIQUE index where
it is the idempotency key for import scripts.

Revision ID: 040
Revises: 039
Create Date: 2026-04-29 18:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# ── revision identifiers ───────────────────────────────────────────────────────
revision = "040"
down_revision = "039"
branch_labels = None
depends_on = None


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────

def _add_nullable_text(table: str, column: str, unique: bool = False) -> None:
    """Add a nullable TEXT column and, optionally, a UNIQUE index."""
    op.add_column(table, sa.Column(column, sa.Text(), nullable=True))
    if unique:
        op.create_index(
            f"uq_{table}_{column}",
            table,
            [column],
            unique=True,
            postgresql_where=sa.text(f"{column} IS NOT NULL"),
        )


def _add_nullable_ts(table: str, column: str) -> None:
    """Add a nullable TIMESTAMPTZ column."""
    op.add_column(
        table,
        sa.Column(column, sa.TIMESTAMP(timezone=True), nullable=True),
    )


# ─────────────────────────────────────────────────────────────────────────────
# upgrade
# ─────────────────────────────────────────────────────────────────────────────

def upgrade() -> None:
    """Add Bubble migration metadata columns and bubble_import_runs table."""

    # ── users ──────────────────────────────────────────────────────────────────
    # bubble_user_id: idempotency key for import_users.py
    _add_nullable_text("users", "bubble_user_id", unique=True)
    # import_source: e.g. 'bubble_migration_2026_05' — which migration run created this row
    _add_nullable_text("users", "import_source")
    # import_status: cohort classification
    #   'imported_active_paying' | 'imported_active_unpaid' | 'imported_lapsed'
    #   | 'imported_dormant' | 'native' (NULL is also acceptable for native users)
    _add_nullable_text("users", "import_status")
    # import_completion_step: drives the first-login concierge wizard (TASK-2.17.10)
    #   'pending' | 'welcome' | 'legal_form' | 'salon_config' | 'team'
    #   | 'services' | 'savings_hook' | 'done' | 'deferred' | NULL (native)
    _add_nullable_text("users", "import_completion_step")
    # last_paid_at: populated by TASK-2.17.7 for lapsed users (from Stripe
    #   current_period_end of the cancelled subscription)
    _add_nullable_ts("users", "last_paid_at")
    # welcome_email_sent_at: idempotency guard for TASK-2.17.11 batch send
    _add_nullable_ts("users", "welcome_email_sent_at")

    # ── salons ─────────────────────────────────────────────────────────────────
    _add_nullable_text("salons", "bubble_salon_id", unique=True)
    # Preserves Bubble's type_Salon (establishment type, NOT legal form).
    # Distinct from salons.business_type which is the fiscal/legal structure.
    _add_nullable_text("salons", "bubble_establishment_type")

    # ── employees ──────────────────────────────────────────────────────────────
    _add_nullable_text("employees", "bubble_employee_id", unique=True)

    # ── services ───────────────────────────────────────────────────────────────
    _add_nullable_text("services", "bubble_service_id", unique=True)

    # ── monthly_reports ────────────────────────────────────────────────────────
    _add_nullable_text("monthly_reports", "bubble_month_id", unique=True)

    # ── expenses ───────────────────────────────────────────────────────────────
    _add_nullable_text("expenses", "bubble_item_id", unique=True)

    # ── monthly_salaries ───────────────────────────────────────────────────────
    _add_nullable_text("monthly_salaries", "bubble_item_id", unique=True)

    # ── noly_subscriptions ─────────────────────────────────────────────────────
    _add_nullable_text("noly_subscriptions", "bubble_abonnement_id", unique=True)
    # stripe_price_id: needed by TASK-2.17.7 grandfathering to record the
    # original Stripe Price ID being preserved.
    _add_nullable_text("noly_subscriptions", "stripe_price_id")

    # ── blog_articles (TASK-2.17.8 AI cleanup columns) ─────────────────────────
    _add_nullable_text("blog_articles", "bubble_blog_id", unique=True)
    # AI-cleaned HTML version (Claude Sonnet rewrite)
    op.add_column("blog_articles", sa.Column("body_html_cleaned", sa.Text(), nullable=True))
    # 'pending' | 'ai_cleaned' | 'reviewed' | 'rejected'
    op.add_column("blog_articles", sa.Column("enhancement_status", sa.Text(), nullable=True))
    # unified diff between original and cleaned (Python difflib output stored as JSONB)
    op.add_column(
        "blog_articles",
        sa.Column(
            "enhancement_diff",
            JSONB,
            nullable=True,
        ),
    )
    # 'original' | 'cleaned' — controls which version the public endpoint serves
    op.add_column(
        "blog_articles",
        sa.Column(
            "published_version",
            sa.Text(),
            nullable=False,
            server_default="original",
        ),
    )

    # ── bubble_import_runs ─────────────────────────────────────────────────────
    op.create_table(
        "bubble_import_runs",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Which script generated this run: 'import_users', 'import_salons', etc.
        sa.Column("script_name", sa.Text(), nullable=False),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # NULL while the run is in progress; set by finish_run()
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errored", sa.Integer(), nullable=False, server_default="0"),
        # Bubble pagination cursor — set by set_cursor() so a crash mid-run
        # can resume from where it left off rather than restarting.
        sa.Column("last_cursor", sa.Integer(), nullable=True),
        # JSONB array of {bubble_id, reason, timestamp} error records
        sa.Column(
            "error_log",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        # NULL for CLI runs; set when an admin triggers a re-sync from the
        # migration dashboard (TASK-2.17.9).
        sa.Column(
            "triggered_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        comment=(
            "TASK-2.17.1 — Audit trail of every Bubble import script execution. "
            "One row per run. Counters are incremented live so the admin dashboard "
            "can show progress without waiting for the script to finish. "
            "error_log is a JSONB array of {bubble_id, reason, timestamp} objects."
        ),
    )
    # Primary query: recent runs for a given script, ordered newest-first
    op.create_index(
        "ix_bubble_import_runs_script_started",
        "bubble_import_runs",
        ["script_name", "started_at"],
        postgresql_ops={"started_at": "DESC"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# downgrade
# ─────────────────────────────────────────────────────────────────────────────

def downgrade() -> None:
    """Remove all TASK-2.17.1 additions (reverse order of upgrade)."""

    # bubble_import_runs
    op.drop_index("ix_bubble_import_runs_script_started", "bubble_import_runs")
    op.drop_table("bubble_import_runs")

    # blog_articles
    op.drop_column("blog_articles", "published_version")
    op.drop_column("blog_articles", "enhancement_diff")
    op.drop_column("blog_articles", "enhancement_status")
    op.drop_column("blog_articles", "body_html_cleaned")
    op.drop_index("uq_blog_articles_bubble_blog_id", "blog_articles")
    op.drop_column("blog_articles", "bubble_blog_id")

    # noly_subscriptions
    op.drop_column("noly_subscriptions", "stripe_price_id")
    op.drop_index("uq_noly_subscriptions_bubble_abonnement_id", "noly_subscriptions")
    op.drop_column("noly_subscriptions", "bubble_abonnement_id")

    # monthly_salaries
    op.drop_index("uq_monthly_salaries_bubble_item_id", "monthly_salaries")
    op.drop_column("monthly_salaries", "bubble_item_id")

    # expenses
    op.drop_index("uq_expenses_bubble_item_id", "expenses")
    op.drop_column("expenses", "bubble_item_id")

    # monthly_reports
    op.drop_index("uq_monthly_reports_bubble_month_id", "monthly_reports")
    op.drop_column("monthly_reports", "bubble_month_id")

    # services
    op.drop_index("uq_services_bubble_service_id", "services")
    op.drop_column("services", "bubble_service_id")

    # employees
    op.drop_index("uq_employees_bubble_employee_id", "employees")
    op.drop_column("employees", "bubble_employee_id")

    # salons
    op.drop_column("salons", "bubble_establishment_type")
    op.drop_index("uq_salons_bubble_salon_id", "salons")
    op.drop_column("salons", "bubble_salon_id")

    # users
    op.drop_column("users", "welcome_email_sent_at")
    op.drop_column("users", "last_paid_at")
    op.drop_column("users", "import_completion_step")
    op.drop_column("users", "import_status")
    op.drop_column("users", "import_source")
    op.drop_index("uq_users_bubble_user_id", "users")
    op.drop_column("users", "bubble_user_id")
