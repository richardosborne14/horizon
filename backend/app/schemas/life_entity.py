"""
Pydantic schemas for LifeEntity — validation layer for life entity CRUD.

CostEvent validates individual cost events within the JSONB array.
LifeEntityCreate/Read/Update handle the full entity lifecycle.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ── Cost Event ────────────────────────────────────────────────────────────────


from decimal import ROUND_HALF_UP


class CostEvent(BaseModel):
    """A single cost event within a life entity's lifecycle.

    Each event has an age bracket (from_age → to_age, inclusive on both ends),
    an amount and frequency, and a source label indicating origin.
    A cost event with from_age == to_age fires once at that age.
    """

    id: str = Field(
        default_factory=lambda: str(uuid4())[:8],
        description="Short unique identifier for this event (8-char UUID prefix)"
    )
    label: str = Field(..., min_length=1, max_length=200)
    from_age: int = Field(ge=0, description="Start age (inclusive)")
    to_age: int = Field(ge=0, description="End age (inclusive)")
    amount: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    frequency: Literal["monthly", "annual", "once"]
    source: Literal["default", "user", "ai_suggested"] = "user"
    is_active: bool = True

    def rounded_amount(self) -> Decimal:
        """Return amount rounded to 2 decimal places for consistent serialization."""
        return self.amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def is_once_event(self) -> bool:
        """True if this is a one-time event at a specific age."""
        return self.from_age == self.to_age


# ── Life Entity Schemas ───────────────────────────────────────────────────────


class LifeEntityCreate(BaseModel):
    """Payload for creating a new life entity.

    If cost_events is empty, the backend populates canned defaults
    based on entity_type, reference_date, and metadata.
    """

    entity_type: Literal["kid", "pet", "car", "tech"]
    name: str = Field(min_length=1, max_length=100)
    reference_date: date
    metadata: dict = Field(default_factory=dict)
    cost_events: list[CostEvent] = Field(default_factory=list)
    sort_order: int = Field(default=0, ge=0)


class LifeEntityUpdate(BaseModel):
    """Partial update — all fields optional.

    Only send the fields you want to change. Fields not included
    in the request body are left unchanged.
    """

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    reference_date: Optional[date] = None
    metadata: Optional[dict] = None
    cost_events: Optional[list[CostEvent]] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = Field(default=None, ge=0)


class LifeEntityRead(BaseModel):
    """Full life entity data returned by GET endpoints.

    current_age is computed server-side as:
    (today - reference_date).days // 365

    expired is True when all cost events have a max to_age < current_age,
    meaning the entity contributes zero to the projection.
    """

    id: UUID
    user_id: UUID
    entity_type: str
    name: str
    reference_date: date
    current_age: int  # computed
    expired: bool = False  # computed — all cost events are in the past
    expired_message: Optional[str] = None  # human-readable explanation
    metadata: dict
    cost_events: list[CostEvent]
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LifeEntityList(BaseModel):
    """Wrapper for listing multiple entities, grouped or filtered."""

    entities: list[LifeEntityRead]
    total: int