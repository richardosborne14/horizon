"""033 — add subject_token to payslip_dossiers

Revision ID: 033_dossier_subject_token
Revises: 032_fiches_salaire_tables
Create Date: 2026-04-25 23:00:00+00:00

WHY: PayslipDossier needs a subject_token column so the outbound dossier email
can embed a [REF-{token}] anchor in the subject line. The TASK-2.13.3 inbound
poller uses this token to match Marie's reply email to the correct salon's dossier.
The token is generated (secrets.token_hex(4)) when the dossier payment is confirmed
and stored so it is stable across webhook/confirm racing.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "033_dossier_subject_token"
down_revision = "032_fiches_salaire_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add subject_token column to payslip_dossiers."""
    op.add_column(
        "payslip_dossiers",
        sa.Column("subject_token", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Remove subject_token column from payslip_dossiers."""
    op.drop_column("payslip_dossiers", "subject_token")
