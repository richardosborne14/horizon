"""
User model — authentication and account data.

One user can own multiple salons. The CoCo profile and conversations
are linked via user_id. Role is either 'user' or 'admin'.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Text, func, text
from sqlalchemy.dialects.postgresql import ENUM as PgEnum, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.auth import Session, PasswordResetToken


class User(Base):
    """
    Application user account.

    Every person who signs up gets a User record. They can own multiple salons.
    The role column gates admin-only features. CoCo stores per-user context
    in coco_user_profiles.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    # repr=False is dataclass-only — not supported on mapped_column
    # Hash is excluded from __repr__ manually in the repr method below
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # 'user' | 'admin' — controls access to /admin endpoints
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="user",
        index=True,
    )

    # Set to True once the onboarding questionnaire is completed
    onboarding_completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )

    # Set to True once the Mon Mois Typique wizard (Task 2.5.3) is completed.
    # Controls dashboard mode: guided vs. data-rich (Task 2.5.5).
    has_completed_typical_month: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )

    # Tool IDs selected during onboarding (e.g. ["simulation", "copilot", "prix"])
    # Use sa.text() so asyncpg renders the literal correctly in create_all DDL.
    # See LEARNINGS.md 2026-04-10 — bare string server_default causes DDL errors.
    preferred_tools: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ── TASK-2.17.2: Stripe customer link (preserved from Bubble migration) ───
    # Bubble User.StripeCustomerID. Used by TASK-2.17.7 to verify sub status.
    # NULL for native users; may also be set when a native user subscribes.
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    # ── TASK-2.17.1: Bubble migration tracking ────────────────────────────────
    # Bubble _id — used as idempotency key in import_users.py.
    # UNIQUE partial index (NOT NULL only) in migration 040.
    bubble_user_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 'bubble_migration_2026_05' etc. — which migration produced this row.
    import_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Cohort classification set by import scripts and refined by 2.17.6/2.17.7:
    # 'imported_active_paying' | 'imported_active_unpaid' | 'imported_lapsed'
    # | 'imported_dormant' | 'native' (NULL = native, same effect)
    import_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    # First-login wizard step (TASK-2.17.10):
    # 'pending' | 'welcome' | 'legal_form' | 'salon_config' | 'team'
    # | 'services' | 'savings_hook' | 'done' | 'deferred' | NULL (native users)
    import_completion_step: Mapped[str | None] = mapped_column(Text, nullable=True)
    # TASK-2.17.7: Date of last successful payment from a since-cancelled Stripe sub.
    # Populated for 'imported_lapsed' cohort only; used for UI copy in welcome email.
    last_paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    # TASK-2.17.9/11: Timestamp of when the cutover welcome email was sent.
    # NULL = not yet sent. Used as idempotency guard in send_batch().
    welcome_email_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ── TASK-2.12.15: Email drip ─────────────────────────────────────────────
    # Per-template send/skip ledger used for idempotency.
    # Keys are template_id; values are {sent_at: ISO} | {skipped_at, reason} | null.
    email_drip_state: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    # NULL = subscribed to drip emails.  Non-null = opted out via unsubscribe link.
    # Does NOT block transactional emails (payslip-ready, password reset, etc.).
    unsubscribed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # TASK-2.16.2: Set when the user is grandfathered onto a legacy pricing plan.
    # NULL = standard new pricing applies.
    # Non-null = one of the legacy_pricing_plan_enum Postgres values.
    # WHY PgEnum(create_type=False): asyncpg requires the bind parameter to be
    # typed against the enum — a plain Text/VARCHAR binding causes
    # DatatypeMismatchError at runtime. create_type=False tells SQLAlchemy NOT to
    # CREATE TYPE (the Alembic migration 038 already created it).
    legacy_pricing_plan: Mapped[str | None] = mapped_column(
        PgEnum(
            "legacy_99_yearly",
            "legacy_bic_63_monthly",
            "legacy_bic_plus_93_monthly",
            "legacy_bic_plus_99_monthly",
            name="legacy_pricing_plan_enum",
            create_type=False,  # migration 038 owns the CREATE TYPE
        ),
        nullable=True,
        comment=(
            "TASK-2.16.2: Grandfathering flag. "
            "NULL = new pricing. "
            "Non-null = one of legacy_pricing_plan_enum values."
        ),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        "PasswordResetToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role!r}>"
