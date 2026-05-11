"""
CareerPeriod model — stores past employment history for pension calculation.

Sprint 6 (TASK-6.1): Each period represents a distinct phase of the user's
professional life — CDI, CDD, AE, unemployment, parental leave, etc.
The pension engine v2 (TASK-6.2) uses this to compute trimestres from
regime général (salaried) + AE periods + other period types.

Sprint 7 (TASK-7.7): Added `owner` column to distinguish user vs spouse
career periods. Values: "user" or "spouse".

Key design decisions:
- One table for all period types (discriminated by period_type).
- end_date=None means ongoing (current period).
- annual_gross is the gross annual income for that period.
- pension_regime is auto-derived from period_type if not set explicitly.
- Overlapping periods are allowed (e.g., CDI + AE side activity).
- owner discriminates user vs spouse career history for couple mode.
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


class CareerPeriod(Base):
    """A single period of the user's or spouse's professional career.

    period_type: "cdi", "cdd", "interim", "ae", "eirl", "eurl", "sasu",
                "apprenticeship", "internship", "unemployment",
                "parental_leave", "education", "foreign", "other"

    owner: "user" (default) or "spouse" — who this period belongs to.

    pension_regime: auto-derived from period_type (can be overridden):
        "general" — régime général (CNAV) for salaried work
        "ae" — auto-entrepreneur (was RSI, now under CNAV)
        "tns" — travailleur non-salarié (EIRL, EURL)
        "cipav" — professions libérales
        "foreign" — no French trimestres
        None — no pension contribution (education, some internships)
    """

    __tablename__ = "career_periods"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Period type
    period_type = Column(String(20), nullable=False)

    # Owner discriminator — "user" or "spouse"
    owner = Column(String(10), nullable=False, server_default="user")

    # Dates
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)  # null = ongoing (current period)

    # Employment details
    employer_name = Column(String(200), nullable=True)
    job_title = Column(String(200), nullable=True)

    # Salary / Revenue — for pension calculation
    # CDI/CDD: gross annual salary (used for SAM calculation)
    # AE: annual CA (used for trimestre validation)
    # Unemployment: daily allocation (for trimestre validation)
    annual_gross = Column(Numeric(12, 2), nullable=True)
    is_full_time = Column(Boolean, nullable=False, server_default="true")
    # Part-time percentage (100 = full time, 80 = 4/5ths)
    time_percentage = Column(Integer, nullable=False, server_default="100")

    # Pension regime
    # Auto-derived from period_type if not set explicitly
    pension_regime = Column(String(20), nullable=True)

    # Metadata
    notes = Column(String(500), nullable=True)
    sort_order = Column(Integer, nullable=False, server_default="0")
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Relationship ───────────────────────────────────────────────────────
    user = relationship("User", backref="career_periods")

    def __repr__(self) -> str:
        return (
            f"<CareerPeriod id={self.id} type={self.period_type} "
            f"owner={self.owner} start={self.start_date}>"
        )