"""
Pydantic schemas for Spouse — TASK-7.4.

The spouse is a 1:1 relationship off the user. Tracks identity,
relationship type, professional status, simplified revenue, and
Conjointe Collaboratrice (CC) settings.

current_age is computed from birth_date at display time.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Constants ─────────────────────────────────────────────────────────────────

VALID_RELATIONSHIPS = {"married", "pacsed", "concubinage"}
VALID_SPOUSE_STATUSES = {
    "cdi", "cdd", "ae", "eirl", "eurl", "sasu",
    "unemployed", "retired", "inactive", "conjointe_collaboratrice",
}
VALID_CC_OPTIONS = {
    "tiers_plafond", "moitie_plafond", "tiers_revenu", "moitie_revenu",
}

# CC cotisation constants
PLAFOND_SS_ANNUEL = Decimal("46368")  # 2024 PASS annuel
CC_RATE = Decimal("0.28")  # Simplified CC rate (retraite base + complémentaire + invalidité)


# ── Schemas ───────────────────────────────────────────────────────────────────


class SpouseCreate(BaseModel):
    """Payload for creating a spouse. All fields optional except defaults."""

    first_name: Optional[str] = Field(None, max_length=100)
    birth_date: Optional[date] = None
    relationship_type: str = Field(default="married", pattern="^(married|pacsed|concubinage)$")
    status: str = Field(default="cdi")
    ae_activity_type: Optional[str] = None
    versement_liberatoire: bool = False
    monthly_gross_income: Optional[Decimal] = Field(None, ge=0)
    growth_preset: str = "moderate"
    growth_rate_custom: Optional[Decimal] = None
    is_conjointe_collaboratrice: bool = False
    cc_cotisation_option: Optional[str] = None


class SpouseUpdate(BaseModel):
    """Partial update — all fields optional. Only send what changed."""

    first_name: Optional[str] = Field(None, max_length=100)
    birth_date: Optional[date] = None
    relationship_type: Optional[str] = None
    status: Optional[str] = None
    ae_activity_type: Optional[str] = None
    versement_liberatoire: Optional[bool] = None
    monthly_gross_income: Optional[Decimal] = None
    growth_preset: Optional[str] = None
    growth_rate_custom: Optional[Decimal] = None
    is_conjointe_collaboratrice: Optional[bool] = None
    cc_cotisation_option: Optional[str] = None


class SpouseRead(BaseModel):
    """Full spouse data returned by GET endpoints.

    current_age is computed from birth_date at display time.
    """

    id: UUID
    user_id: UUID
    first_name: Optional[str] = None
    birth_date: Optional[date] = None
    relationship_type: str
    status: str
    ae_activity_type: Optional[str] = None
    versement_liberatoire: bool
    monthly_gross_income: Optional[Decimal] = None
    growth_preset: str
    growth_rate_custom: Optional[Decimal] = None
    is_conjointe_collaboratrice: bool
    cc_cotisation_option: Optional[str] = None
    current_age: Optional[int] = None  # Computed from birth_date
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CCOptionEstimate(BaseModel):
    """Estimated cotisations for one CC option."""

    base_annuelle: str
    cotisation_annuelle: str
    cotisation_mensuelle: str


class CCEstimateResponse(BaseModel):
    """Estimated annual cotisations for each of the 4 CC options."""

    tiers_plafond: CCOptionEstimate
    moitie_plafond: CCOptionEstimate
    tiers_revenu: CCOptionEstimate
    moitie_revenu: CCOptionEstimate