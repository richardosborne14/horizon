"""
Pydantic schemas for IncomeSource — TASK-7.5.

Income sources replace the single monthly_gross_ca field with tracked
revenue streams. Each source belongs to an earner (user/spouse), has a type,
frequency, duration, confidence level, and optional growth rate.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Constants ─────────────────────────────────────────────────────────────────

VALID_EARNERS = {"user", "spouse"}
VALID_SOURCE_TYPES = {
    "client", "product", "salary", "dividends", "rental",
    "pension", "sale", "other",
}
VALID_FREQUENCIES = {"monthly", "annual", "one_time"}
VALID_CONFIDENCE_LEVELS = {"high", "medium", "low"}


# ── Schemas ───────────────────────────────────────────────────────────────────


class IncomeSourceCreate(BaseModel):
    """Payload for creating a new income source.

    label and amount are required. All other fields have sensible defaults.
    start_date=None means already active; end_date=None means ongoing.
    """

    earner: str = Field(default="user", pattern="^(user|spouse)$")
    label: str = Field(..., min_length=1, max_length=200)
    source_type: str = Field(default="client", pattern="^(client|product|salary|dividends|rental|pension|sale|other)$")
    amount: Decimal = Field(..., ge=0, max_digits=12, decimal_places=2)
    frequency: str = Field(default="monthly", pattern="^(monthly|annual|one_time)$")
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    confidence: str = Field(default="high", pattern="^(high|medium|low)$")
    annual_growth_rate: Optional[Decimal] = Field(None, ge=Decimal("0"), le=Decimal("1"), max_digits=5, decimal_places=4)
    is_ae_revenue: bool = True
    sort_order: int = Field(default=0, ge=0)
    notes: Optional[str] = Field(default=None, max_length=1000)


class IncomeSourceUpdate(BaseModel):
    """Partial update — all fields optional. Only send what changed."""

    earner: Optional[str] = Field(default=None, pattern="^(user|spouse)$")
    label: Optional[str] = Field(default=None, min_length=1, max_length=200)
    source_type: Optional[str] = Field(default=None, pattern="^(client|product|salary|dividends|rental|pension|sale|other)$")
    amount: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    frequency: Optional[str] = Field(default=None, pattern="^(monthly|annual|one_time)$")
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    confidence: Optional[str] = Field(default=None, pattern="^(high|medium|low)$")
    annual_growth_rate: Optional[Decimal] = Field(None, ge=Decimal("0"), le=Decimal("1"), max_digits=5, decimal_places=4)
    is_ae_revenue: Optional[bool] = None
    sort_order: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = Field(default=None, max_length=1000)
    is_active: Optional[bool] = None


class IncomeSourceRead(BaseModel):
    """Full income source data returned by GET endpoints."""

    id: UUID
    user_id: UUID
    earner: str
    label: str
    source_type: str
    amount: Decimal
    frequency: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    confidence: str
    annual_growth_rate: Optional[Decimal] = None
    is_ae_revenue: bool
    is_active: bool
    sort_order: int
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EarnersSummary(BaseModel):
    """Summary stats for one earner (user or spouse)."""

    current_monthly_total: str
    sources_count: int
    guaranteed_monthly: str
    speculative_monthly: str
    ending_within_12_months: list[dict] = Field(default_factory=list)
    # Each item: {label, ends (ISO date), monthly (str)}


class IncomeSourceSummaryResponse(BaseModel):
    """Aggregated income summary by earner.

    Used by the frontend to show household revenue breakdown
    and flag sources ending soon.
    """

    user: EarnersSummary
    spouse: Optional[EarnersSummary] = None
    household_monthly_total: str