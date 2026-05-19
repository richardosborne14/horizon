"""
UserProfile model — the central data model for Horizon.

One profile per user (1:1 relationship). Captures financial identity:
age, tax situation, AE status, revenue, growth expectations, expenses,
and world scenario.

Monthly expenses are stored as JSONB for flexible category management.
Status change simulation fields live here (single active simulation).
"""

from uuid import uuid4

from sqlalchemy import (
    Column,
    String,
    Integer,
    Date,
    Numeric,
    Boolean,
    DateTime,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class UserProfile(Base):
    """User financial profile — one per user.

    Created lazily on first GET /api/profile (upsert pattern).
    All monetary values are NUMERIC(12,2) for precision.
    """

    __tablename__ = "user_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # ── Identity ───────────────────────────────────────────────────────────
    birth_date = Column(Date, nullable=True)
    target_retirement_age = Column(
        Integer, nullable=False, server_default="67"
    )
    tax_parts = Column(
        Numeric(3, 1), nullable=False, server_default="1.0"
    )
    tax_parts_manual_override = Column(
        Boolean, nullable=False, server_default="false"
    )

    # ── Status ─────────────────────────────────────────────────────────────
    status = Column(
        String(20), nullable=False, server_default="ae"
    )  # ae, eirl, eurl, sasu
    ae_activity_type = Column(
        String(50), nullable=False, server_default="bnc_non_reglementee"
    )  # bnc_non_reglementee, bic_services, bic_vente, bnc_cipav
    has_versement_liberatoire = Column(
        Boolean, nullable=False, server_default="true"
    )

    # ── Revenue ────────────────────────────────────────────────────────────
    monthly_gross_ca = Column(Numeric(10, 2), nullable=True)
    growth_preset = Column(
        String(20), nullable=False, server_default="moderate"
    )  # conservative, moderate, ambitious, custom
    growth_rate_custom = Column(
        Numeric(5, 4), nullable=True
    )  # only when preset=custom

    # ── Tax breaks ─────────────────────────────────────────────────────────
    cesu_annual = Column(
        Numeric(10, 2), nullable=False, server_default="0"
    )
    charity_annual = Column(
        Numeric(10, 2), nullable=False, server_default="0"
    )

    # ── CAF ────────────────────────────────────────────────────────────────
    caf_override_monthly = Column(
        Numeric(10, 2), nullable=True
    )  # null = auto-estimate (Sprint 2)

    # ── Monthly expenses (JSONB — 12 flexible categories) ─────────────────
    monthly_expenses = Column(
        JSONB, nullable=False, server_default="{}"
    )

    # ── Custom expenses (array of {id, label, amount}) ────────────────────
    custom_expenses = Column(
        JSONB, nullable=False, server_default="[]"
    )

    # ── Goal ──────────────────────────────────────────────────────────────
    monthly_revenue_goal = Column(Numeric(10, 2), nullable=True)

    # ── World scenario ─────────────────────────────────────────────────────
    world_scale = Column(
        String(20), nullable=False, server_default="moderate"
    )  # optimistic, moderate, pessimistic

    # ── Status change simulation ──────────────────────────────────────────
    status_change_enabled = Column(
        Boolean, nullable=False, server_default="false"
    )
    status_change_year = Column(Integer, nullable=True)
    status_change_target = Column(String(20), nullable=True)
    status_change_savings = Column(Numeric(10, 2), nullable=True)

    # ── Timestamps ─────────────────────────────────────────────────────────
    created_at = Column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Relationship ───────────────────────────────────────────────────────
    user = relationship("User", backref="profile")

    def __repr__(self) -> str:
        return (
            f"<UserProfile user_id={self.user_id} "
            f"status={self.status}>"
        )