"""028 remove bnc statuses

Revision ID: 028_remove_bnc_statuses
Revises: 20260423_1100_d1e2f3a4b5c6_024_cout_vie_perso
Create Date: 2026-04-24 22:30:00.000000

WHY: TASK-2.12.10 — Eric confirmed BNC (Bénéfices Non Commerciaux) does not
apply to coiffure. The business_type values 'bnc_non_reglemente' and
'bnc_cipav' were removed from backend/static-data/business-types.json.

This migration is a DOCUMENTED NO-OP: no salons in the dev or prod DB have
ever used a BNC business type (verified 2026-04-24). The schema does not store
a constraint referencing this static data — business_type is a free-text
varchar, so no ALTER TABLE is required.

If a future audit finds prod salons with BNC types, the manual fix is:
  UPDATE salons SET business_type = 'bic_services'
    WHERE business_type IN ('bnc_non_reglemente', 'bnc_cipav');
  -- Log: salon_id, user email, old type, new type → report to Eric.

LEARNINGS: BNC entries never existed in any Atlas DB. The static-data file
never included them. Confirmed via grep of Alembic history and DB inspection.
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "028_remove_bnc_statuses"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    No-op: BNC business types never existed in any Atlas database.

    The static-data file (business-types.json) was audited and confirmed to
    contain only: auto_micro, eirl, eurl, sarl, sas, sasu. No BNC entries
    were present. No schema changes are needed.
    """
    # Intentional no-op — see module docstring for full explanation.
    pass


def downgrade() -> None:
    """
    No-op: nothing was changed, nothing to revert.
    """
    pass
