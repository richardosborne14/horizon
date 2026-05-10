"""
Pydantic schemas for UserProfile.

ProfileRead: All fields + computed current_age.
ProfileWrite: Writable fields with validation.
MonthlyExpenses: Validated structure for the JSONB monthly_expenses column.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Expense categories ────────────────────────────────────────────────────────
# The 12 expense categories stored as JSONB keys on UserProfile.
# Order is intentional — maps to the frontend grid layout.

EXPENSE_CATEGORIES = [
    "loyer", "energie", "internet", "assurance", "transport",
    "alimentation", "sante", "loisirs", "abonnements",
    "impots", "credit", "divers",
]

EXPENSE_LABELS = {
    "loyer": "Loyer / Crédit immobilier",
    "energie": "Énergie (élec, gaz)",
    "internet": "Internet & téléphone",
    "assurance": "Assurances personnelles",
    "transport": "Carburant / Transport",
    "alimentation": "Alimentation",
    "sante": "Santé / Mutuelle",
    "loisirs": "Loisirs & sorties",
    "abonnements": "Abonnements",
    "impots": "Impôts locaux",
    "credit": "Crédits en cours",
    "divers": "Divers",
}


# ── Monthly Expenses ──────────────────────────────────────────────────────────

class MonthlyExpenses(BaseModel):
    """12 expense categories, all non-negative.

    Stored as JSONB on UserProfile.monthly_expenses.
    The `total` property returns the sum of all categories.
    """

    loyer: Decimal = Field(default=Decimal("0"), ge=0)
    energie: Decimal = Field(default=Decimal("0"), ge=0)
    internet: Decimal = Field(default=Decimal("0"), ge=0)
    assurance: Decimal = Field(default=Decimal("0"), ge=0)
    transport: Decimal = Field(default=Decimal("0"), ge=0)
    alimentation: Decimal = Field(default=Decimal("0"), ge=0)
    sante: Decimal = Field(default=Decimal("0"), ge=0)
    loisirs: Decimal = Field(default=Decimal("0"), ge=0)
    abonnements: Decimal = Field(default=Decimal("0"), ge=0)
    impots: Decimal = Field(default=Decimal("0"), ge=0)
    credit: Decimal = Field(default=Decimal("0"), ge=0)
    divers: Decimal = Field(default=Decimal("0"), ge=0)

    @field_validator("*", mode="before")
    @classmethod
    def coerce_to_decimal(cls, v):
        """Accept int/float/str and convert to Decimal."""
        if v is None:
            return Decimal("0")
        return Decimal(str(v))

    @property
    def total(self) -> Decimal:
        """Sum of all 12 categories."""
        return sum(
            getattr(self, field)
            for field in EXPENSE_CATEGORIES
        )


# ── Waterfall schemas (TASK-6.8) ──────────────────────────────────────────


class WaterfallMonthly(BaseModel):
    """Monthly disposable income waterfall for a specific year."""

    gross_ca: str  # Decimal as string
    charges: str
    cfe_monthly: str
    net_after_charges: str
    base_expenses: str
    loan_payments: str
    kid_costs: str
    pet_costs: str
    car_costs: str
    tech_costs: str
    recurring_costs: str
    caf_income: str
    tax_credits: str
    disposable: str
    savings_planned: str
    monthly_surplus_deficit: str


class WaterfallAnnual(BaseModel):
    """Annual equivalents of the waterfall."""

    gross_ca: str
    charges: str
    cfe: str
    net_after_charges: str
    total_expenses: str
    total_life_costs: str
    total_income_additions: str
    disposable: str
    savings_planned: str
    annual_surplus_deficit: str


class WaterfallResponse(BaseModel):
    """Complete disposable income waterfall."""

    year: int
    age: int
    monthly: WaterfallMonthly
    annual: WaterfallAnnual
    status: str  # "surplus", "deficit", "breakeven"
    deficit_note: str = ""


# ── Profile schemas ───────────────────────────────────────────────────────────

class ProfileWrite(BaseModel):
    """Writable profile fields — sent via PUT /api/profile.

    All fields are optional to support partial updates.
    Only send the fields you want to change.
    """

    birth_date: Optional[date] = None
    target_retirement_age: Optional[int] = Field(
        default=None, ge=50, le=85
    )
    tax_parts: Optional[Decimal] = Field(
        default=None, ge=Decimal("1.0")
    )

    status: Optional[str] = None  # ae, eirl, eurl, sasu
    ae_activity_type: Optional[str] = None
    has_versement_liberatoire: Optional[bool] = None

    monthly_gross_ca: Optional[Decimal] = Field(default=None, ge=0)
    growth_preset: Optional[str] = None
    growth_rate_custom: Optional[Decimal] = Field(
        default=None, ge=Decimal("0"), le=Decimal("0.5")
    )

    cesu_annual: Optional[Decimal] = Field(default=None, ge=Decimal("0"))
    charity_annual: Optional[Decimal] = Field(default=None, ge=Decimal("0"))

    caf_override_monthly: Optional[Decimal] = Field(default=None, ge=Decimal("0"))

    monthly_expenses: Optional[dict] = None

    monthly_revenue_goal: Optional[Decimal] = Field(default=None, ge=0)
    world_scale: Optional[str] = None

    status_change_enabled: Optional[bool] = None
    status_change_year: Optional[int] = None
    status_change_target: Optional[str] = None
    status_change_savings: Optional[Decimal] = Field(default=None, ge=Decimal("0"))


class ProfileRead(BaseModel):
    """Full profile data returned by GET /api/profile.

    Includes the computed `current_age` derived from birth_date.
    All Decimal fields serialised as strings for JSON precision.
    """

    id: UUID
    user_id: UUID

    # Identity
    birth_date: Optional[date] = None
    current_age: Optional[int] = None  # computed
    target_retirement_age: int
    tax_parts: str  # Decimal as string

    # Status
    status: str
    ae_activity_type: str
    has_versement_liberatoire: bool

    # Revenue
    monthly_gross_ca: Optional[str] = None
    growth_preset: str
    growth_rate_custom: Optional[str] = None

    # Tax breaks
    cesu_annual: str
    charity_annual: str

    # CAF
    caf_override_monthly: Optional[str] = None

    # Monthly expenses
    monthly_expenses: dict

    # Goal
    monthly_revenue_goal: Optional[str] = None

    # World scenario
    world_scale: str

    # Status change simulation
    status_change_enabled: bool
    status_change_year: Optional[int] = None
    status_change_target: Optional[str] = None
    status_change_savings: Optional[str] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}