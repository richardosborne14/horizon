"""
IncomeSource model — individual revenue streams for user or spouse.

Sprint 7 (TASK-7.5): Replaces the single monthly_gross_ca field with
tracked income sources. Each source has a label, amount, duration,
growth rate, and confidence level. Sources belong to either the user
or spouse (earner field).

Key design decisions:
- One table for all income streams (discriminated by earner + source_type).
- start_date=None means already active; end_date=None means ongoing.
- confidence levels: high (signed contract), medium (verbal), low (speculative).
- is_ae_revenue flag controls whether this income is subject to AE cotisations.
- backward compat: sync_profile_ca() keeps profile.monthly_gross_ca in sync.
"""

from uuid import uuid4

from sqlalchemy import (
    Column,
    String,
    Integer,
    Date,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class IncomeSource(Base):
    """A single income revenue stream for user or spouse.

    earner: "user" or "spouse"
    source_type: "client", "product", "salary", "dividends", "rental",
                 "pension", "sale", "other"
    frequency: "monthly", "annual", "one_time"
    confidence: "high", "medium", "low"
    """

    __tablename__ = "income_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Who earns this
    earner = Column(String(10), nullable=False, server_default="user")
    # "user" or "spouse"

    # Source identity
    label = Column(String(200), nullable=False)
    source_type = Column(String(30), nullable=False, server_default="client")
    # client, product, salary, dividends, rental, pension, sale, other

    # Revenue
    amount = Column(Numeric(12, 2), nullable=False)
    frequency = Column(String(20), nullable=False, server_default="monthly")
    # monthly, annual, one_time

    # Duration
    start_date = Column(Date, nullable=True)  # null = already active
    end_date = Column(Date, nullable=True)    # null = ongoing
    confidence = Column(String(20), nullable=False, server_default="high")
    # high (signed contract), medium (verbal), low (speculative)

    # Growth
    annual_growth_rate = Column(Numeric(5, 4), nullable=True)

    # Tax treatment
    is_ae_revenue = Column(Boolean, nullable=False, server_default="true")
    # If true → subject to AE cotisations.
    # If false (dividends, salary) → different tax treatment.

    # Status
    is_active = Column(Boolean, nullable=False, server_default="true")
    sort_order = Column(Integer, nullable=False, server_default="0")
    notes = Column(Text, nullable=True)

    # ── Timestamps ─────────────────────────────────────────────────────────
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Relationship ───────────────────────────────────────────────────────
    user = relationship("User", backref="income_sources")

    def __repr__(self) -> str:
        return (
            f"<IncomeSource id={self.id} label={self.label} "
            f"earner={self.earner} amount={self.amount}>"
        )