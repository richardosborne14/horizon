"""
Loan model — structured loan/mortgage data for accurate financial projection.

Sprint 6 (TASK-6.3): Replaces the flat "credit" field in monthly_expenses with
proper temporal modeling. Each loan has a start date, end date, monthly payment,
and optional original amount/rate. The projection engine drops loan payments
after end_date and does NOT inflation-adjust them (loans are fixed nominal).

end_date is computed from remaining_months if not explicitly provided.
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
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Loan(Base):
    """A loan or mortgage with a known end date.

    loan_type: "mortgage", "auto", "consumer", "student", "business", "other"
    end_action: "freed" (payment stops, freed cash available) or "refinanced"
    insurance_monthly: assurance emprunteur (borrower insurance), common on French mortgages
    """

    __tablename__ = "loans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Loan identity
    label = Column(String(200), nullable=False)  # "Crédit immobilier", "Prêt auto"
    loan_type = Column(String(30), nullable=False)
    # "mortgage", "auto", "consumer", "student", "business", "other"

    # Financial terms
    monthly_payment = Column(Numeric(10, 2), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)  # null → compute from remaining_months
    remaining_months = Column(Integer, nullable=True)  # Alternative to end_date
    original_amount = Column(Numeric(12, 2), nullable=True)  # Total borrowed
    interest_rate = Column(Numeric(5, 4), nullable=True)  # Annual rate (e.g., 0.025)
    remaining_balance = Column(Numeric(12, 2), nullable=True)  # What's still owed

    # Insurance (assurance emprunteur) — common for French mortgages
    insurance_monthly = Column(Numeric(8, 2), nullable=True, server_default="0")

    # What happens when the loan ends
    end_action = Column(String(20), nullable=False, server_default="'freed'")

    # Metadata
    notes = Column(String(500), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Relationship ───────────────────────────────────────────────────────
    user = relationship("User", backref="loans")

    def __repr__(self) -> str:
        return (
            f"<Loan id={self.id} label={self.label} "
            f"monthly={self.monthly_payment}>"
        )