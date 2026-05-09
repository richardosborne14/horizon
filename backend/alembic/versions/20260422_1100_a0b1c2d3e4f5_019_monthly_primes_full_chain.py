"""monthly_primes full chain: add bands_snapshot, source_target_origin, schedule_id

Revision ID: a0b1c2d3e4f5
Revises: e1f2a3b4c5d6
Create Date: 2026-04-22 11:00:00.000000

Task 2.9.8.4 — Adds fields to monthly_primes to support:
- Immutable snapshot of the bonus bands used at compute time (bands_snapshot)
- Provenance tracking of the target source (source_target_origin)
- Reference to the linked calculation or reference string (source_target_ref)
- The schedule that was active when the bonus was computed (schedule_id)

WHY these fields:
- bands_snapshot ensures historical bonus records are self-contained —
  later schedule edits cannot silently rewrite old bonus calculations.
- source_target_origin records whether the target came from manual entry,
  seuil_salaire, or pilotage average — needed for staleness detection.
- schedule_id links to the employee_prime_schedules row used, for audit trail.

WHY IF NOT EXISTS:
  A parallel head (f0a1b2c3d4e5) already applied these columns to the DB
  before this migration was created. Using IF NOT EXISTS makes this
  migration idempotent so it can safely be applied even when columns exist.
"""

from alembic import op
import sqlalchemy as sa

revision = "a0b1c2d3e4f5"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use raw SQL with IF NOT EXISTS — idempotent against the parallel head
    # that already added these columns.
    op.execute("""
        ALTER TABLE monthly_primes
            ADD COLUMN IF NOT EXISTS bands_snapshot JSONB,
            ADD COLUMN IF NOT EXISTS source_target_origin VARCHAR(32) DEFAULT 'manual',
            ADD COLUMN IF NOT EXISTS source_target_ref VARCHAR(255),
            ADD COLUMN IF NOT EXISTS schedule_id UUID
    """)

    # Add FK only if it does not already exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_monthly_primes_schedule'
            ) THEN
                ALTER TABLE monthly_primes
                    ADD CONSTRAINT fk_monthly_primes_schedule
                    FOREIGN KEY (schedule_id)
                    REFERENCES employee_prime_schedules(id)
                    ON DELETE SET NULL;
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE monthly_primes
            DROP CONSTRAINT IF EXISTS fk_monthly_primes_schedule
    """)
    op.execute("""
        ALTER TABLE monthly_primes
            DROP COLUMN IF EXISTS schedule_id,
            DROP COLUMN IF EXISTS source_target_ref,
            DROP COLUMN IF EXISTS source_target_origin,
            DROP COLUMN IF EXISTS bands_snapshot
    """)
