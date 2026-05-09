"""
Project model — investment projects and life events.

Two types share one table:
1. Investment projects (gîte, rental, business) — have purchase cost,
   annual income/expenses, tax rate, and yield a computed P&L.
2. Life events (wedding, trip, renovation) — one-time costs at a
   specific year. No income, just an expense spike.

Nullable fields per type enforce clean separation without needing
two tables. The Pydantic schemas (TASK-3.2) provide separate create
endpoints for each type with appropriate validation.
"""

from uuid import uuid4

from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Boolean,
    ForeignKey,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID, NUMERIC
from sqlalchemy.sql import func

from app.core.database import Base


class Project(Base):
    """User project — investment or life event.

    Investment fields (null for events):
        start_year, purchase_cost, annual_income, annual_expenses, tax_rate

    Event fields (null for investments):
        event_year, event_cost

    Common: label, notes, is_active (soft-delete).
    """

    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_type = Column(
        String(20), nullable=False
    )  # "invest" or "event"

    label = Column(String(200), nullable=False)

    # ── Investment fields (null for events) ───────────────────────────────
    start_year = Column(Integer, nullable=True)
    purchase_cost = Column(NUMERIC(12, 2), nullable=True)
    annual_income = Column(NUMERIC(10, 2), nullable=True)
    annual_expenses = Column(NUMERIC(10, 2), nullable=True)
    tax_rate = Column(NUMERIC(5, 3), nullable=True)  # e.g. 0.300

    # ── Event fields (null for investments) ───────────────────────────────
    event_year = Column(Integer, nullable=True)
    event_cost = Column(NUMERIC(12, 2), nullable=True)

    # ── Common ────────────────────────────────────────────────────────────
    notes = Column(Text, nullable=True)
    is_active = Column(
        Boolean, nullable=False, server_default="true"
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<Project id={self.id} type={self.project_type} "
            f"label={self.label} active={self.is_active}>"
        )