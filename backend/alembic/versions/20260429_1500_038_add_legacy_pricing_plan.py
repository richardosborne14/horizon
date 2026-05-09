"""Add legacy_pricing_plan flag and legacy_pricing_audit table

TASK-2.16.2 — Grandfathering schema for the Sprint 2.16 pricing restructure.

Two cohorts of users get grandfathered onto legacy pricing:
  - Cohort A: existing paying users at cutover (set via one-shot backfill script).
  - Cohort B: Bubble migration users (set by migrate_bubble_subscriptions.py).

NULL on users.legacy_pricing_plan means "standard new pricing applies".
Non-NULL means the user is locked to a legacy price and must never be moved
to the new Stripe Price IDs automatically.

Revision ID: 038_legacy_pricing_plan
Revises: 037_nb_bulletins_override
Create Date: 2026-04-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "038_legacy_pricing_plan"
down_revision = "037_nb_bulletins_override"
branch_labels = None
depends_on = None

# Enum name in Postgres
_ENUM_NAME = "legacy_pricing_plan_enum"

# Enum values — extend if a new legacy tier is created in a future sprint
_ENUM_VALUES = (
    "legacy_99_yearly",          # Original platform subscription, 99 €/an
    "legacy_bic_63_monthly",     # PACK BIC compta, 63 €/mois
    "legacy_bic_plus_93_monthly",  # PACK BIC+ compta at original 93 €/mois price
    "legacy_bic_plus_99_monthly",  # PACK BIC+ compta at v2 99 €/mois price (2026-05 restructure)
)


def upgrade() -> None:
    """
    1. Create the legacy_pricing_plan_enum Postgres enum type.
    2. Add legacy_pricing_plan column (nullable) to users.
    3. Add partial index for fast cohort queries.
    4. Create legacy_pricing_audit table with full audit trail per flag-setting event.
    """
    # ── 1. Create the enum type ────────────────────────────────────────────────
    legacy_pricing_plan_enum = postgresql.ENUM(
        *_ENUM_VALUES,
        name=_ENUM_NAME,
        create_type=True,
    )
    legacy_pricing_plan_enum.create(op.get_bind(), checkfirst=True)

    # ── 2. Add column to users ─────────────────────────────────────────────────
    op.add_column(
        "users",
        sa.Column(
            "legacy_pricing_plan",
            postgresql.ENUM(*_ENUM_VALUES, name=_ENUM_NAME, create_type=False),
            nullable=True,
            comment=(
                "TASK-2.16.2: Set when the user is grandfathered onto a legacy price. "
                "NULL = standard new pricing applies. "
                "Drives the pricing-page 'Forfait actuel' rendering and prevents "
                "accidental migration to new SKUs."
            ),
        ),
    )

    # ── 3. Partial index — fast lookup of legacy cohort ────────────────────────
    op.create_index(
        "ix_users_legacy_pricing_plan_nonnull",
        "users",
        ["legacy_pricing_plan"],
        postgresql_where=sa.text("legacy_pricing_plan IS NOT NULL"),
    )

    # ── 4. Create legacy_pricing_audit table ───────────────────────────────────
    op.create_table(
        "legacy_pricing_audit",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "set_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "plan",
            sa.Text(),
            nullable=False,
            comment="The legacy_pricing_plan_enum value that was set.",
        ),
        sa.Column(
            "source",
            sa.Text(),
            nullable=False,
            comment=(
                "'bubble_migration' | 'cutover_backfill' | 'manual_admin'. "
                "WHY: so support can explain exactly when/why a customer is on a legacy price."
            ),
        ),
        sa.Column(
            "stripe_subscription_id",
            sa.Text(),
            nullable=True,
            comment="The Stripe subscription ID being preserved, if known at the time of flagging.",
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
            comment="Free-form notes for support / audit trail.",
        ),
    )


def downgrade() -> None:
    """
    Drop the audit table, remove the column, drop the enum type.
    Order matters: column must be dropped before the enum type is dropped.
    """
    op.drop_table("legacy_pricing_audit")
    op.drop_index("ix_users_legacy_pricing_plan_nonnull", table_name="users")
    op.drop_column("users", "legacy_pricing_plan")

    # Drop the enum type last (after all columns referencing it are gone)
    legacy_pricing_plan_enum = postgresql.ENUM(name=_ENUM_NAME, create_type=False)
    legacy_pricing_plan_enum.drop(op.get_bind(), checkfirst=True)
