"""
InvestmentAllocation model — user allocations across 7 investment vehicles.

One row per user per vehicle. Created lazily on first GET /api/investments
(upsert pattern: if a row doesn't exist for a vehicle, it's created with
zero balances). This ensures the frontend always gets a complete set of
7 allocations without null handling.

Per-row design (not JSONB on profile) because:
1. The projection engine queries individual vehicles to compound balances
2. Future features (transaction history, rebalancing alerts) need per-vehicle rows
3. The unique constraint prevents duplicate vehicle entries per user
"""

from uuid import uuid4

from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import NUMERIC
from sqlalchemy.sql import func

from app.core.database import Base


class InvestmentAllocation(Base):
    """Per-user, per-vehicle investment allocation.

    existing_balance: current total in this vehicle (EUR)
    monthly_contribution: monthly amount added to this vehicle (EUR)

    Both are NUMERIC for precision — the projection engine (Sprint 4)
    compounds these with the vehicle's rate over 30 years.
    """

    __tablename__ = "investment_allocations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vehicle_key = Column(
        String(20), nullable=False
    )  # livret_a, ldds, av_euro, etc.

    existing_balance = Column(
        NUMERIC(12, 2), nullable=False, server_default="0"
    )
    monthly_contribution = Column(
        NUMERIC(10, 2), nullable=False, server_default="0"
    )

    created_at = Column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "vehicle_key", name="uq_user_vehicle"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<InvestmentAllocation user_id={self.user_id} "
            f"vehicle={self.vehicle_key} "
            f"balance={self.existing_balance} "
            f"contrib={self.monthly_contribution}>"
        )