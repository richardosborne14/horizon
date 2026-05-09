"""
025 — Data migration: auto-create dirigeant employee from salon_config.type_exploitant.

WHY (TASK-2.11.6): Dirigeant status was stored as `type_exploitant` in salon_config
(a salon-level field). Eric's feedback: everyone who is paid by the salon should live
in the employee list — one source of truth. The new UX removes the `type_exploitant`
dropdown from Paramétrage (for non-AE) and routes users to Mon équipe → Ajouter un
dirigeant instead.

This migration converts the pre-existing Paramétrage data for non-AE salons that had
a TNS or assimilé salarié statut set, by creating a corresponding Employee row. The
salary is initialised at 0€ (unknown) — the user will see a CTA in Mon équipe to
complete it. No data is deleted: `type_exploitant` stays on the config row as a
read-only legacy field.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-04-23 12:00:00
"""

from __future__ import annotations

import uuid
import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

logger = logging.getLogger("alembic.025_dirigeant_migration")

revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    For every salon_config where type_exploitant is 'tns' or 'assimile_salarie'
    and the parent salon is NOT auto_micro (AE), check if there is already a
    dirigeant employee. If not, create one with salary_brut = 0.

    This is safe to run multiple times — the NOT EXISTS check prevents duplicates.
    """
    conn = op.get_bind()

    # Fetch all salon_configs that need a dirigeant employee row.
    # Joins to salons to exclude auto_micro (AE) salons — they use cout_vie_perso_mensuel.
    rows = conn.execute(
        sa.text(
            """
            SELECT sc.salon_id, sc.type_exploitant
            FROM salon_config sc
            JOIN salons s ON s.id = sc.salon_id
            WHERE sc.type_exploitant IN ('tns', 'assimile_salarie')
              AND s.business_type != 'auto_micro'
              AND s.deleted_at IS NULL
              AND NOT EXISTS (
                SELECT 1 FROM employees e
                WHERE e.salon_id = sc.salon_id
                  AND e.role_type = 'dirigeant'
                  AND e.is_active = TRUE
              )
            """
        )
    ).fetchall()

    created_count = 0
    for row in rows:
        salon_id = row[0]
        type_exploitant = row[1]
        # Map type_exploitant → contract_type for employee table
        # 'tns' stays 'tns'; 'assimile_salarie' stays 'assimile_salarie'
        contract_type = type_exploitant
        emp_id = uuid.uuid4()

        conn.execute(
            sa.text(
                """
                INSERT INTO employees (
                    id, salon_id, name, role_type, contract_type,
                    hours_per_week, weeks_per_year, salary_brut,
                    cotisations_patronales, taux_occupation, is_active
                ) VALUES (
                    :id, :salon_id, :name, 'dirigeant', :contract_type,
                    39.0, 45.6, 0.00,
                    NULL, 0.65, TRUE
                )
                """
            ),
            {
                "id": str(emp_id),
                "salon_id": str(salon_id),
                "name": "Dirigeant",
                "contract_type": contract_type,
            },
        )
        created_count += 1
        logger.info(
            f"[025] Created dirigeant employee for salon {salon_id} "
            f"(contract: {contract_type}, salary: 0€ — to be completed by user)"
        )

    logger.info(f"[025] Migration complete — {created_count} dirigeant employee(s) created")


def downgrade() -> None:
    """
    Remove auto-created dirigeant rows (those with salary_brut = 0 and name = 'Dirigeant').

    WHY non-destructive guard: we only delete rows where salary_brut = 0 and
    name = 'Dirigeant' — these are the auto-created placeholders. If the user
    updated their salary or name after upgrade, we leave those rows alone.
    """
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            DELETE FROM employees
            WHERE role_type = 'dirigeant'
              AND name = 'Dirigeant'
              AND (salary_brut = 0 OR salary_brut IS NULL)
            """
        )
    )
