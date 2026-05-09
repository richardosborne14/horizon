"""030 contract subtype

Revision ID: 030_contract_subtype
Revises: 029_savings_engine_tables
Create Date: 2026-04-25 12:00:00.000000

WHY (TASK-2.12.5): Adds contract_subtype column to employees to support:
  - Apprenti CAP (non-productive): contract_subtype = 'cap'
  - Apprenti BP (standard productive): contract_subtype = 'bp'
  - Apprenti BM (standard productive): contract_subtype = 'bm'
  NULL = not set (back-compat: treated as bp/bm for apprentis).

Backfill: any existing dirigeant whose contract_type is NULL or a legacy
salarié type (cdi, cdd, etc.) gets contract_type = 'tns'. This aligns
the database with the TNS-default convention introduced in TASK-2.11.6.

LEARNINGS: If any salon had a dirigeant with a wrong contract_type, they
will now correctly see the TNS transparency block. The admin should notify
affected salons to review their dirigeant row. Logged in LEARNINGS.md.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "030_contract_subtype"
down_revision = "029_savings_engine_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add contract_subtype column — NULL = not yet set.
    # WHY TEXT: values are cap | bp | bm, not a fixed enum — simpler to extend later.
    op.add_column(
        "employees",
        sa.Column("contract_subtype", sa.Text(), nullable=True),
    )

    # 2. Backfill: dirigeants with legacy/null contract_type → 'tns'.
    # WHY: TASK-2.11.6 introduced TNS as the default for dirigeants.
    # Old rows from before that task may still have NULL or a salarié contract.
    # This backfill makes the DB consistent so the EmployeeForm transparency block works.
    # Affected rows will be: any employee WHERE role_type = 'dirigeant'
    # AND (contract_type IS NULL OR contract_type NOT IN ('tns', 'assimile_salarie')).
    op.execute(
        """
        UPDATE employees
        SET contract_type = 'tns'
        WHERE role_type = 'dirigeant'
          AND (
            contract_type IS NULL
            OR contract_type NOT IN ('tns', 'assimile_salarie')
          )
        """
    )


def downgrade() -> None:
    # Reverse: drop the subtype column.
    # Note: the dirigeant contract_type backfill is NOT reversed —
    # reverting to old null/cdi values would break the UI.
    op.drop_column("employees", "contract_subtype")
