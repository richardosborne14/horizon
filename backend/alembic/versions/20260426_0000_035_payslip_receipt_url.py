"""
035 — Add stripe_receipt_url to payslip_submissions and contrat_requests.

Replaces the never-populated stripe_invoice_id approach with receipt_url:
  - PaymentIntent → charge.receipt_url (Stripe-hosted, accounting-compliant)
  - Stored on the row at payment-success time for fast retrieval
  - Still refreshable via Stripe API if the URL changes (rare)

Revision: 035_payslip_receipt_url
Previous: 034_inbound_notifications
"""

import sqlalchemy as sa
from alembic import op

revision = "035_payslip_receipt_url"
down_revision = "034_inbound_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add stripe_receipt_url to payslip_submissions
    op.add_column(
        "payslip_submissions",
        sa.Column("stripe_receipt_url", sa.Text(), nullable=True),
    )
    # Add stripe_receipt_url to contrat_requests
    op.add_column(
        "contrat_requests",
        sa.Column("stripe_receipt_url", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("payslip_submissions", "stripe_receipt_url")
    op.drop_column("contrat_requests", "stripe_receipt_url")
