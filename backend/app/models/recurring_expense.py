"""
RecurringExpense model — time-bounded annual expenses.

Expenses that recur annually but have a defined start and end year.
Examples: loan repayments, annual holiday budget, kid's sports club,
car leases. These are not permanent monthly expenses and don't fit
the life entity model (they're not "things" with ages).

The projection engine (Sprint 4) queries this table per year:
  SUM(annual_amount) WHERE from_year <= :year AND to_year >= :year
"""

from uuid import uuid4

from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    Boolean,
    DateTime,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class RecurringExpense(Base):
    """A time-bounded recurring annual expense.

    label: description (e.g., "Remboursement prêt auto")
    annual_amount: yearly cost in EUR (NUMERIC 10,2)
    from_year / to_year: inclusive year range this expense applies
    category: optional grouping label
    """

    __tablename__ = "recurring_expenses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    label = Column(String(200), nullable=False)
    annual_amount = Column(Numeric(10, 2), nullable=False)
    from_year = Column(Integer, nullable=False)
    to_year = Column(Integer, nullable=False)

    category = Column(String(50), nullable=True)

    is_active = Column(Boolean, nullable=False, server_default="true")

    created_at = Column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Relationship ───────────────────────────────────────────────────────
    user = relationship("User", backref="recurring_expenses")

    def __repr__(self) -> str:
        return (
            f"<RecurringExpense id={self.id} "
            f"label='{self.label}' {self.from_year}→{self.to_year}>"
        )