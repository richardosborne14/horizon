"""
Spouse model — partner financial identity for household projection.

Sprint 7 (TASK-7.4): Adds a spouse/partner entity as a 1:1 relationship
off the user. Tracks identity, relationship type, professional status,
simplified revenue, and Conjointe Collaboratrice (CC) settings.

Key design decisions:
- 1:1 relationship — unique constraint on user_id.
- CC (conjointe collaboratrice) only available for EIRL/EURL + married/pacsed.
- monthly_gross_income is a simplified field; detailed income goes via
  income_sources.earner='spouse' (TASK-7.5).
- Ages are computed from birth_date at display time.
"""

from uuid import uuid4

from sqlalchemy import (
    Column,
    String,
    Date,
    Boolean,
    Integer,
    Numeric,
    DateTime,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Spouse(Base):
    """Partner financial identity for household projection.

    relationship_type: "married", "pacsed", "concubinage"
    status: "cdi", "cdd", "ae", "eirl", "eurl", "sasu", "unemployed",
            "retired", "inactive", "conjointe_collaboratrice"
    cc_cotisation_option: "tiers_plafond", "moitie_plafond",
                          "tiers_revenu", "moitie_revenu"
    """

    __tablename__ = "spouses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # ── Identity ────────────────────────────────────────────────────────────
    first_name = Column(String(100), nullable=True)
    birth_date = Column(Date, nullable=True)

    # ── Relationship ────────────────────────────────────────────────────────
    relationship_type = Column(String(20), nullable=False, server_default="married")
    # Values: married, pacsed, concubinage

    # ── Professional status ─────────────────────────────────────────────────
    status = Column(String(30), nullable=False, server_default="cdi")
    # Values: cdi, cdd, ae, eirl, eurl, sasu, unemployed, retired,
    #         inactive, conjointe_collaboratrice
    ae_activity_type = Column(String(20), nullable=True)
    # Only when status=ae: bic_vente, bic_service, bnc, bic_heberg
    versement_liberatoire = Column(Boolean, nullable=False, server_default="false")

    # ── Revenue (simple field — detailed via income_sources table) ──────────
    monthly_gross_income = Column(Numeric(10, 2), nullable=True)
    growth_preset = Column(String(20), nullable=False, server_default="moderate")
    growth_rate_custom = Column(Numeric(5, 4), nullable=True)

    # ── Conjointe collaboratrice ────────────────────────────────────────────
    is_conjointe_collaboratrice = Column(Boolean, nullable=False, server_default="false")
    cc_cotisation_option = Column(String(30), nullable=True)
    # Values: tiers_plafond, moitie_plafond, tiers_revenu, moitie_revenu

    # ── Timestamps ──────────────────────────────────────────────────────────
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Relationship ────────────────────────────────────────────────────────
    user = relationship("User", backref="spouse")

    def __repr__(self) -> str:
        return (
            f"<Spouse id={self.id} first_name={self.first_name} "
            f"status={self.status}>"
        )