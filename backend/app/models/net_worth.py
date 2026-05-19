"""
NetWorthSnapshot model — user's complete financial position snapshot.

Sprint 6 (TASK-6.5): Stores liquid assets, property, vehicles, business value,
other assets and debts that aren't tracked in investment allocations or loans.
Gives the projection engine a complete starting point for net worth calculation.

Design decisions:
- Single snapshot per user (upsert pattern — GET/PUT, not POST with history).
- Cash reserves feed into readiness score buffer_adequacy component.
- Property/vehicle/business values are self-declared estimates.
- Loan balances are pulled from the loans model, not duplicated here.
- Investment balances are pulled from InvestmentAllocation, not duplicated here.
"""

from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class NetWorthSnapshot(Base):
    """A user's net worth snapshot — single record per user.

    Stores assets and debts NOT already tracked in InvestmentAllocation or Loan.
    The API aggregates all three sources to compute total net worth.
    """

    __tablename__ = "net_worth_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Liquid assets (not in investment vehicles) ───────────────────────
    cash_current_accounts = Column(Numeric(12, 2), default=0)  # Compte courant
    cash_savings_other = Column(Numeric(12, 2), default=0)     # Other savings
    # Investment balances pulled from InvestmentAllocation (not stored here)

    # ── Property ─────────────────────────────────────────────────────────
    property_primary_value = Column(Numeric(12, 2), default=0)  # Résidence principale
    property_other_value = Column(Numeric(12, 2), default=0)    # Other property
    residence_type = Column(String(30), nullable=False, server_default="primary_residence")
    property_other_type = Column(String(30), nullable=False, server_default="none")
    # residence_type: 'primary_residence', 'rental', 'secondary', 'land'
    # property_other_type: 'none', 'rental', 'secondary', 'land'
    property_appreciation_rate = Column(Numeric(5, 4), default=0.02)  # Annual appreciation (2% default)
    downsize_enabled = Column(Boolean, default=False)           # Enable downsizing simulation
    downsize_year = Column(Integer, nullable=True)               # Year of downsizing
    downsize_target_value = Column(Numeric(12, 2), nullable=True)  # Value of replacement property
    # Mortgage balance pulled from loans model

    # ── Other assets ─────────────────────────────────────────────────────
    business_value = Column(Numeric(12, 2), default=0)   # Fonds de commerce / clientèle
    vehicle_value = Column(Numeric(12, 2), default=0)     # Cars, estimated resale
    other_assets = Column(Numeric(12, 2), default=0)
    other_assets_label = Column(String(200), nullable=True)

    # ── Other debts (beyond tracked loans) ───────────────────────────────
    other_debts = Column(Numeric(12, 2), default=0)       # Family loans, tax debt, etc.
    other_debts_label = Column(String(200), nullable=True)

    # ── Metadata ─────────────────────────────────────────────────────────
    snapshot_date = Column(Date, nullable=False)  # When last updated
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Relationship ─────────────────────────────────────────────────────
    user = relationship("User", backref="net_worth_snapshot")

    def __repr__(self) -> str:
        return (
            f"<NetWorthSnapshot id={self.id} user_id={self.user_id} "
            f"date={self.snapshot_date}>"
        )