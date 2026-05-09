"""Make salons.business_type nullable for Bubble migration (TASK-2.17.3).

Imported Bubble salons must land with business_type=NULL so the first-login
wizard (TASK-2.17.10) can prompt the user to choose their statut juridique
(legal form). Bubble's type_Salon stores the establishment type (Barbier,
Coiffure mixte, etc.), which is a completely different concept from the legal
form (auto_micro, eurl, sasu…) — that information was never collected in Bubble.

WHY additive instead of using a sentinel: a sentinel value like 'pending'
would silently match the "!= auto_micro" branch in every calculation service,
producing nonsense figures for migrated users before they complete the wizard.
NULL is unambiguous and existing NULL-guards already handle this gracefully
(calculations fail with a clear 404 / "no salon" error rather than silent bad math).

Down migration: restore NOT NULL with a default so existing data isn't lost.
Any row that somehow has a null value after downgrade gets 'unknown' as a
placeholder — admin can clean up manually.

Revision ID: 042
Revises: 041
Create Date: 2026-04-29 20:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "042"
down_revision = "041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Drop NOT NULL constraint on salons.business_type."""
    op.alter_column(
        "salons",
        "business_type",
        existing_type=sa.String(length=50),
        nullable=True,
        comment=(
            "TASK-2.17.3: Made nullable to allow Bubble-imported salons to land without "
            "a legal form. The first-login wizard (TASK-2.17.10) prompts the user to "
            "choose their statut juridique. Native (non-imported) salons always have a "
            "non-null value because the create-salon flow requires one."
        ),
    )


def downgrade() -> None:
    """Restore NOT NULL on salons.business_type, backfilling nulls with 'unknown'."""
    # Backfill any null values introduced during migration so NOT NULL is satisfiable
    op.execute("UPDATE salons SET business_type = 'unknown' WHERE business_type IS NULL")
    op.alter_column(
        "salons",
        "business_type",
        existing_type=sa.String(length=50),
        nullable=False,
    )
