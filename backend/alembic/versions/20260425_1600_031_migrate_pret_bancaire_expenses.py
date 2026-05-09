"""031 - Migrate pret_bancaire expense rows: set tva_rate=0 for any rows labelled Prêt bancaire.

Revision ID: 031_migrate_pret_bancaire
Revises: 030_contract_subtype
Create Date: 2026-04-25 16:00:00.000000

WHY: Prior to sprint 2.12, "Prêt bancaire" was a free-text label in expense-labels.json
that users could select via the custom expense combobox. The loan repayment is never subject
to TVA (it is a capital repayment, not a service). Some older expense rows may have been saved
with a non-zero tva_rate if the user did not change the combobox default.

This migration:
  1. Sets tva_rate = 0.000, tva_amount = 0, amount_ht = amount_ttc for all expense rows
     whose `notes` column matches the Prêt bancaire label variants (case-insensitive).
  2. Makes no schema changes — no new columns or tables.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "031_migrate_pret_bancaire"
down_revision = "030_contract_subtype"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Correct tva_rate for any existing 'Prêt bancaire' expense rows.

    Matches case-insensitively on common label variants:
      - 'Prêt bancaire'
      - 'pret bancaire'
      - 'Prêt Bancaire'
      - 'emprunt' (free-text variants users may have typed)

    Sets:
      tva_rate    → 0.000  (no TVA on loan repayments)
      tva_amount  → 0.00   (no TVA collected/deductible)
      amount_ht   → amount_ttc (HT = TTC when tva_rate = 0)
    """
    op.execute(
        sa.text("""
        UPDATE expenses
           SET tva_rate   = 0.000,
               tva_amount = 0.00,
               amount_ht  = amount_ttc
         WHERE notes ~* 'pr.t.?bancaire|emprunt'
           AND tva_rate != 0.000
        """)
    )


def downgrade() -> None:
    """
    No downgrade — we cannot know what the original tva_rate was.
    This is a one-way data-quality fix.
    """
    pass
