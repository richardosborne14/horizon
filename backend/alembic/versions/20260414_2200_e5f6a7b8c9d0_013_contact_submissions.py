"""013_contact_submissions

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-14 22:00:00.000000

WHY: Task 4.6 — Booking/contact form for Eric. Visitors submit their name,
phone, email, preferred contact time, and optional message. Submissions are
emailed to Eric and stored here for reference. Rate limiting is enforced per
IP (max 3/hour) checked in the router using this table.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'contact_submissions',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('phone', sa.String(50), nullable=False),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column(
            'preferred_time',
            sa.String(20),
            nullable=True,
            comment='matin | apres_midi | soir',
        ),
        sa.Column('ip_address', sa.String(45), nullable=True, comment='IPv4 or IPv6'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
    )
    # Index for rate-limit queries (by ip_address + created_at)
    op.create_index(
        'ix_contact_submissions_ip_created',
        'contact_submissions',
        ['ip_address', 'created_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_contact_submissions_ip_created', table_name='contact_submissions')
    op.drop_table('contact_submissions')
