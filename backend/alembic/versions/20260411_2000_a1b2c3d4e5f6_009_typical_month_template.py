"""009 — Add typical_month_template to salon_config and has_completed_typical_month to users.

These two fields support the Mon Mois Typique wizard (Task 2.5.3) and the
onboarding redirect (Task 2.5.4). The wizard collects the user's typical monthly
CA, staff costs, and expense breakdown, stores it as a JSON template, and marks
the user as having completed the initial setup.

Revision ID: a1b2c3d4e5f6
Revises: f2a3b4c5d6e7
Create Date: 2026-04-11 20:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'a1b2c3d4e5f6'
down_revision = 'f2a3b4c5d6e7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add:
      - salon_config.typical_month_template  JSONB nullable
        Stores the Mon Mois Typique wizard output: CA, staff list, expense lines.
        Used by year pre-population (Task 2.5.6) to seed all 12 months.

      - users.has_completed_typical_month  BOOLEAN default false
        Set to true after the wizard's step 4 CTA is confirmed.
        Used to gate the dashboard transformation (Task 2.5.5) and skip
        re-showing the wizard prompt.
    """
    op.add_column(
        'salon_config',
        sa.Column(
            'typical_month_template',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment=(
                'Mon Mois Typique wizard output. Schema: '
                '{"ca_ttc": Decimal, "staff": [{name, role, monthly_cost}], '
                '"expenses": [{category, amount_ttc}]}'
            )
        )
    )
    op.add_column(
        'users',
        sa.Column(
            'has_completed_typical_month',
            sa.Boolean(),
            nullable=False,
            server_default='false',
            comment='True after completing the Mon Mois Typique wizard. Controls dashboard mode.'
        )
    )


def downgrade() -> None:
    op.drop_column('users', 'has_completed_typical_month')
    op.drop_column('salon_config', 'typical_month_template')
