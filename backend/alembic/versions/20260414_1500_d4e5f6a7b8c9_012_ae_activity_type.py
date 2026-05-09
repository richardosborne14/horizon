"""Add ae_activity_type to salon_config

Revision ID: d4e5f6a7b8c9
Revises: c1d2e3f4a5b6
Create Date: 2026-04-14 15:00:00.000000

WHY: Auto-entrepreneurs need to select their URSSAF activity type so the
system can use the correct cotisation rate. BIC services artisanales = 21.2%
(most coiffeurs), BNC non réglementée = 25.6% (prestataires de service),
BIC vente = 12.3% (product-only), BNC CIPAV = 23.2% (some liberal professions).
Default bic_services covers the vast majority of coiffeurs / esthéticiennes.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add ae_activity_type — nullable so existing rows default to NULL.
    # NULL is treated as 'bic_services' by the application layer.
    # WHY nullable: we cannot set a server_default on an existing non-empty table
    # without locking it. NULL + app-layer default is the safe migration approach.
    op.add_column(
        'salon_config',
        sa.Column(
            'ae_activity_type',
            sa.String(50),
            nullable=True,
            comment='AE activity type: bic_vente | bic_services | bnc_non_reglementee | bnc_cipav',
        )
    )


def downgrade() -> None:
    op.drop_column('salon_config', 'ae_activity_type')
