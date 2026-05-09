"""023 salon contact fields

Revision ID: a2b3c4d5e6f7
Revises: c2d3e4f5a6b7
Create Date: 2026-04-23 10:00:00.000000

WHY (TASK-2.11.1): Eric's data collection checklist requires a contact e-mail
and phone number per salon so that ComCoi team members can reach the salon owner
directly (newsletter, support calls, etc.). Both nullable so that existing salon
rows are not broken by the migration.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a2b3c4d5e6f7'
down_revision = 'c2d3e4f5a6b7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add contact_email and contact_phone to the salons table."""
    op.add_column(
        'salons',
        sa.Column('contact_email', sa.String(255), nullable=True, server_default=None),
    )
    op.add_column(
        'salons',
        sa.Column('contact_phone', sa.String(50), nullable=True, server_default=None),
    )


def downgrade() -> None:
    """Remove contact_email and contact_phone from the salons table."""
    op.drop_column('salons', 'contact_phone')
    op.drop_column('salons', 'contact_email')
