"""
Pydantic schemas for projects (investments and life events).

- ProjectPNL: computed P&L for investment projects
- ProjectInvestmentCreate: create an investment project
- ProjectEventCreate: create a life event
- ProjectUpdate: partial update for any project
- ProjectRead: full project with computed P&L
- ProjectList: list response wrapper
"""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


# ── P&L (computed, not stored) ────────────────────────────────────────────────


class ProjectPNL(BaseModel):
    """Computed P&L for investment projects."""

    gross_annual: Decimal  # income - expenses
    tax_amount: Decimal  # gross * tax_rate (0 if gross <= 0)
    net_annual: Decimal  # gross - tax
    yield_pct: Decimal | None  # net / purchase_cost (None if cost=0)
    monthly_net: Decimal  # net / 12


# ── Create Schemas ────────────────────────────────────────────────────────────


class ProjectInvestmentCreate(BaseModel):
    """Create an investment-type project."""

    label: str = Field(max_length=200)
    start_year: int = Field(ge=2024, le=2080)
    purchase_cost: Decimal = Field(ge=0)
    annual_income: Decimal = Field(ge=0)
    annual_expenses: Decimal = Field(ge=0)
    tax_rate: Decimal = Field(ge=0, le=1)
    notes: str | None = None


class ProjectEventCreate(BaseModel):
    """Create a life-event project."""

    label: str = Field(max_length=200)
    event_year: int = Field(ge=2024, le=2080)
    event_cost: Decimal = Field(ge=0)
    notes: str | None = None


# ── Update Schema ─────────────────────────────────────────────────────────────


class ProjectUpdate(BaseModel):
    """Partial update for any project type.

    All fields optional — only send what you want to change.
    Changing project_type is not allowed (use delete + recreate).
    """

    label: str | None = Field(None, max_length=200)
    notes: str | None = None

    # Investment fields
    start_year: int | None = Field(None, ge=2024, le=2080)
    purchase_cost: Decimal | None = Field(None, ge=0)
    annual_income: Decimal | None = Field(None, ge=0)
    annual_expenses: Decimal | None = Field(None, ge=0)
    tax_rate: Decimal | None = Field(None, ge=0, le=1)

    # Event fields
    event_year: int | None = Field(None, ge=2024, le=2080)
    event_cost: Decimal | None = Field(None, ge=0)


# ── Read Schema ───────────────────────────────────────────────────────────────


class ProjectRead(BaseModel):
    """Full project with computed P&L (for investments)."""

    id: UUID
    user_id: UUID
    project_type: str

    label: str

    # Investment fields
    start_year: int | None = None
    purchase_cost: Decimal | None = None
    annual_income: Decimal | None = None
    annual_expenses: Decimal | None = None
    tax_rate: Decimal | None = None

    # Event fields
    event_year: int | None = None
    event_cost: Decimal | None = None

    # Computed P&L (only for invest type)
    pnl: ProjectPNL | None = None

    # Common
    notes: str | None = None
    is_active: bool = True

    model_config = {"from_attributes": True}


# ── List Schema ────────────────────────────────────────────────────────────────


class ProjectList(BaseModel):
    """Wrapper for list of projects."""

    projects: list[ProjectRead]
    total: int