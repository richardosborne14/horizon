"""005 salon config extended fields

Add operational and legal fields to salon_config needed by Task 2.6 (parametrage page):
  - type_exploitant: which social-charge formula to use for the owner's salary
  - has_acre: ACRE reduction flag for auto-entrepreneurs
  - acre_start_date: start date for ACRE (needed to determine 50% vs 25% reduction)
  - effectif_entreprise: headcount; affects FNAL + formation professionnelle rates

WHY: Task 2.6 — the parametrage page needs to know the owner's legal status so
social charges are calculated with the correct formula (AE flat rate vs TNS 45%
vs assimilé salarié full salarié charges). effectif_entreprise drives the rate
selection inside calc_charges_salarie().

Revision ID: c9d8e7f6a5b4
Revises: f3a1b2c4d5e6
Create Date: 2026-04-11
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c9d8e7f6a5b4"
down_revision = "f3a1b2c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Legal status of the owner — drives which social charge formula applies.
    # auto_entrepreneur: flat AE rates on CA
    # tns: ~45% on remuneration (gérant majoritaire SARL/EURL/EI)
    # assimile_salarie: full salarié charges (gérant minoritaire/égalitaire SASU/SAS)
    op.add_column(
        "salon_config",
        sa.Column(
            "type_exploitant",
            sa.String(50),
            nullable=False,
            server_default="auto_entrepreneur",
        ),
    )

    # ACRE: Aide à la création/reprise d'entreprise — halves AE charges for first year
    op.add_column(
        "salon_config",
        sa.Column(
            "has_acre",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    # Date ACRE started — used to know if 50% or 25% reduction applies
    # (July 2026 ACRE drops from 50% to 25% reduction for new registrations)
    op.add_column(
        "salon_config",
        sa.Column(
            "acre_start_date",
            sa.Date(),
            nullable=True,
        ),
    )

    # Headcount: affects FNAL rate (0.10% if <50, 0.50% if ≥50) and
    # formation professionnelle rate (0.55% if <11, 1.00% if ≥11).
    # Default 1 (solo auto-entrepreneur). User can override to plan ahead.
    op.add_column(
        "salon_config",
        sa.Column(
            "effectif_entreprise",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )


def downgrade() -> None:
    op.drop_column("salon_config", "effectif_entreprise")
    op.drop_column("salon_config", "acre_start_date")
    op.drop_column("salon_config", "has_acre")
    op.drop_column("salon_config", "type_exploitant")
