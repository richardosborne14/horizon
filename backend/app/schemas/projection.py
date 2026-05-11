"""
Pydantic schemas for the projection API (TASK-4.2).

Response models for GET /api/projection — serialise the projection engine's
dataclass output into JSON. All Decimal fields serialise as strings.
"""
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class YearProjectionOut(BaseModel):
    """A single year in the projection timeline (accumulation + post-retirement)."""

    year: int
    age: int

    # Phase indicator
    is_retirement: bool = False

    # Revenue
    gross_annual: str
    ae_rate: str
    charges: str
    cfe: str

    # Expenses
    base_expenses: str
    kid_expenses: str
    pet_expenses: str
    car_expenses: str
    tech_expenses: str
    recurring_expenses: str
    project_expenses: str
    project_income: str

    # Income additions
    caf_annual: str
    tax_credits: str
    status_bonus: str

    # Post-retirement specific
    pension_monthly: str = "0.00"
    pension_annual: str = "0.00"
    withdrawal_annual: str = "0.00"

    # Net
    total_income: str
    total_outgoing: str
    net_annual: str

    # Investments
    year_invested: str
    year_returns: str
    total_wealth: str

    # Income Tax (TASK-7.12)
    ir_annual: str = "0.00"
    ir_monthly: str = "0.00"
    taux_effectif_ir: str = "0.0000"

    # Derived
    passive_monthly: str
    total_monthly_income: str
    goal_reached: bool

    # Loan expenses (Sprint 6)
    loan_expenses: str = "0.00"

    # Property (TASK-7.16)
    property_value: str = "0.00"
    downsize_freed: str = "0.00"


class MilestoneOut(BaseModel):
    """A wealth milestone reached during the projection."""

    label: str
    year: int
    age: int


class GoalYearOut(BaseModel):
    """The first year where the monthly income goal is reached."""

    year: int
    age: int


class ProjectionSummaryOut(BaseModel):
    """Summary statistics for the full projection timeline (extended Sprint 5)."""

    years: int
    final_wealth: str
    final_passive_monthly: str
    total_invested: str
    total_returns: str
    goal_year: GoalYearOut | None = None
    milestones: list[MilestoneOut] = Field(default_factory=list)
    # Post-retirement (Sprint 5)
    wealth_exhaustion_age: int | None = None
    retirement_monthly_income: str = "0.00"
    retirement_monthly_gap: str = "0.00"


class InsightOut(BaseModel):
    """A single actionable insight (TASK-5.4)."""

    id: str
    category: str
    severity: str
    title: str
    description: str
    impact_wealth: str  # Decimal as string
    action: str
    priority: int = 0


class ReadinessOut(BaseModel):
    """Retirement readiness score (TASK-5.5)."""

    score: int = 0
    label: str = "Fragile"
    color: str = "rose"
    components: dict[str, int] = Field(default_factory=dict)
    summary: str = ""


class ProjectionResponse(BaseModel):
    """Full projection API response — timeline + summary + insights + readiness."""

    timeline: list[YearProjectionOut]
    summary: ProjectionSummaryOut
    scale: str
    insights: list[InsightOut] = Field(default_factory=list)
    readiness: ReadinessOut = Field(default_factory=ReadinessOut)


def build_projection_response(
    timeline: list[Any],  # list of YearProjection (dataclass)
    summary: dict[str, Any],
    scale: str,
    insights: list[Any] | None = None,  # list of Insight dataclass from insights.py
    readiness: Any | None = None,  # ReadinessScore dataclass from readiness.py
) -> ProjectionResponse:
    """Convert engine output to Pydantic response models.

    Args:
        timeline: List of YearProjection dataclass instances.
        summary: Dict from compute_summary().
        scale: The inflation scale used for this projection.
        insights: Optional list of Insight dataclass instances from insights engine.
        readiness: Optional ReadinessScore dataclass from readiness engine.

    Returns:
        A fully serialisable ProjectionResponse.
    """
    timeline_out = [
        YearProjectionOut(
            year=t.year,
            age=t.age,
            is_retirement=t.is_retirement,
            gross_annual=str(t.gross_annual),
            ae_rate=str(t.ae_rate),
            charges=str(t.charges),
            cfe=str(t.cfe),
            base_expenses=str(t.base_expenses),
            kid_expenses=str(t.kid_expenses),
            pet_expenses=str(t.pet_expenses),
            car_expenses=str(t.car_expenses),
            tech_expenses=str(t.tech_expenses),
            recurring_expenses=str(t.recurring_expenses),
            project_expenses=str(t.project_expenses),
            project_income=str(t.project_income),
            caf_annual=str(t.caf_annual),
            tax_credits=str(t.tax_credits),
            status_bonus=str(t.status_bonus),
            pension_monthly=str(t.pension_monthly),
            pension_annual=str(t.pension_annual),
            withdrawal_annual=str(t.withdrawal_annual),
            total_income=str(t.total_income),
            total_outgoing=str(t.total_outgoing),
            net_annual=str(t.net_annual),
            year_invested=str(t.year_invested),
            year_returns=str(t.year_returns),
            total_wealth=str(t.total_wealth),
            ir_annual=str(getattr(t, "ir_annual", Decimal("0"))),
            ir_monthly=str(getattr(t, "ir_monthly", Decimal("0"))),
            taux_effectif_ir=str(getattr(t, "taux_effectif_ir", Decimal("0"))),
            passive_monthly=str(t.passive_monthly),
            total_monthly_income=str(t.total_monthly_income),
            goal_reached=t.goal_reached,
            loan_expenses=str(getattr(t, "loan_expenses", Decimal("0"))),
            property_value=str(getattr(t, "property_value", Decimal("0"))),
            downsize_freed=str(getattr(t, "downsize_freed", Decimal("0"))),
        )
        for t in timeline
    ]

    milestones_out = [
        MilestoneOut(label=m["label"], year=m["year"], age=m["age"])
        for m in summary.get("milestones", [])
    ]

    goal_out = None
    if summary.get("goal_year"):
        goal_out = GoalYearOut(
            year=summary["goal_year"]["year"],
            age=summary["goal_year"]["age"],
        )

    summary_out = ProjectionSummaryOut(
        years=summary["years"],
        final_wealth=summary["final_wealth"],
        final_passive_monthly=summary["final_passive_monthly"],
        total_invested=summary["total_invested"],
        total_returns=summary["total_returns"],
        goal_year=goal_out,
        milestones=milestones_out,
        wealth_exhaustion_age=summary.get("wealth_exhaustion_age"),
        retirement_monthly_income=summary.get("retirement_monthly_income", "0.00"),
        retirement_monthly_gap=summary.get("retirement_monthly_gap", "0.00"),
    )

    insights_out = []
    if insights:
        from app.calculations.insights import Insight
        insights_out = [
            InsightOut(
                id=i.id,
                category=i.category,
                severity=i.severity,
                title=i.title,
                description=i.description,
                impact_wealth=str(i.impact_wealth),
                action=i.action,
                priority=i.priority,
            )
            for i in insights
        ]

    readiness_out = ReadinessOut()
    if readiness is not None:
        readiness_out = ReadinessOut(
            score=readiness.score,
            label=readiness.label,
            color=readiness.color,
            components=readiness.components,
            summary=readiness.summary,
        )

    return ProjectionResponse(
        timeline=timeline_out,
        summary=summary_out,
        scale=scale,
        insights=insights_out,
        readiness=readiness_out,
    )


# ── Scenario comparison schemas (TASK-5.7) ────────────────────────────────


class ScenarioOverride(BaseModel):
    """Overrides for scenario comparison (TASK-5.7)."""

    monthly_savings: float | None = None
    target_retirement_age: int | None = None
    growth_rate: float | None = None
    monthly_expenses_delta: float | None = None
    disable_project: str | None = None
    extra_monthly_investment: dict | None = None


class ScenarioCompareRequest(BaseModel):
    """Request for POST /api/projection/compare (TASK-5.7)."""

    base_scale: str = "moderate"
    overrides: ScenarioOverride = Field(default_factory=ScenarioOverride)


class DeltaOut(BaseModel):
    """Key differences between base and scenario projections."""

    final_wealth: str
    passive_monthly: str
    goal_reached_year_delta: str | None = None
    wealth_exhaustion_delta: str | None = None


class CompareResponse(BaseModel):
    """Response for scenario comparison (TASK-5.7)."""

    base: ProjectionResponse
    scenario: ProjectionResponse
    delta: DeltaOut


# ── Expense timeline schemas (TASK-6.6) ──────────────────────────────────


class ExpenseTimelineEvent(BaseModel):
    """A key expense change event in the projection timeline."""

    year: int
    event: str
    impact_monthly: str  # Decimal as string, negative = expense decrease
    category: str  # "loan_end", "kid_independence", "pet_eol", "car_replacement", "loan_start"


class ExpenseTimelineYear(BaseModel):
    """A single year in the expense evolution timeline."""

    year: int
    age: int
    base_expenses_monthly: str
    loan_payments_monthly: str
    kid_expenses_monthly: str
    pet_expenses_monthly: str
    car_expenses_monthly: str
    tech_expenses_monthly: str
    recurring_monthly: str
    project_expenses_monthly: str
    total_monthly: str
    events: list[str] = []
    delta_vs_previous: str = "0.00"


class ExpenseTimelineResponse(BaseModel):
    """Full expense timeline — year-by-year breakdown + key events."""

    timeline: list[ExpenseTimelineYear]
    key_events: list[ExpenseTimelineEvent]


# ── Sensitivity analysis schemas (TASK-6.7) ──────────────────────────────


class SensitivityParamOut(BaseModel):
    """A single sensitivity analysis result (one parameter tested)."""

    parameter: str
    label: str
    description: str
    base_value_display: str
    test_value_display: str
    base_wealth: str  # Decimal as string
    test_wealth: str  # Decimal as string
    delta_wealth: str  # Decimal as string
    delta_pct: str  # Decimal as string
    delta_exhaustion: int
    rank: int


class SensitivityResponse(BaseModel):
    """Full sensitivity analysis response."""

    base_wealth_at_retirement: str
    base_exhaustion_age: int | None = None
    parameters: list[SensitivityParamOut]
    scale: str
    top_lever_narrative: str = ""


# ── Lifecycle alerts schemas (TASK-6.9) ─────────────────────────────────


class LifecycleAlertOut(BaseModel):
    """A time-specific lifecycle alert."""

    id: str
    alert_type: str
    year: int
    age: int
    severity: str
    title: str
    description: str
    impact_monthly: str | None = None
    impact_wealth: str | None = None
    action_label: str | None = None
    action_link: str | None = None


class LifecycleAlertsResponse(BaseModel):
    """Response containing lifecycle alerts."""

    alerts: list[LifecycleAlertOut]
    total: int


# ── Year drill-down schemas (TASK-6.10) ──────────────────────────────────


class DrillDownLifeEntityEvent(BaseModel):
    """A single active cost event for a life entity in a specific year."""

    label: str
    amount: str  # Decimal as string
    frequency: str  # "monthly", "annual", "once"
    annual: str  # Decimal as string


class DrillDownLifeEntity(BaseModel):
    """A life entity active in the drill-down year with its costs."""

    name: str
    type: str  # "kid", "pet", "car", "tech"
    age: int
    events_active: list[DrillDownLifeEntityEvent]
    subtotal: str  # Decimal as string
    note: str = ""


class DrillDownIncome(BaseModel):
    """Breakdown of income sources for a specific year."""

    gross_ca: str
    growth_rate_applied: str
    caf: str
    cesu_credit: str
    charity_credit: str
    project_income: str
    pension: str
    total: str


class DrillDownCharges(BaseModel):
    """Breakdown of social charges for a specific year."""

    ae_cotisations: str
    ae_rate: str
    cfe: str
    total: str


class DrillDownExpenses(BaseModel):
    """Breakdown of expenses for a specific year."""

    base_total_monthly: str
    base_total_annual: str
    inflation_factor: str


class DrillDownLifeEntitiesTotal(BaseModel):
    """Aggregate life entity costs for the drill-down year."""

    kids: str
    pets: str
    cars: str
    tech: str
    total: str


class DrillDownLoan(BaseModel):
    """A loan in the drill-down year."""

    label: str
    monthly: str
    annual: str
    status: str  # "active" or "ended"
    ends: str | None = None


class DrillDownInvestments(BaseModel):
    """Investment breakdown for the drill-down year."""

    contributions: dict[str, str]  # vehicle_key → amount
    returns: dict[str, str]
    balances: dict[str, str]
    notes: list[str] = []


class DrillDownSummary(BaseModel):
    """Summary statistics for the drill-down year."""

    total_income: str
    total_outgoing: str
    net: str
    net_status: str  # "surplus", "deficit"
    explanation: str


class YearDrillDownResponse(BaseModel):
    """Complete drill-down for a single projection year."""

    year: int
    age: int
    phase: str  # "accumulation" or "post-retirement"
    income: DrillDownIncome
    charges: DrillDownCharges
    expenses: DrillDownExpenses
    life_entities: list[DrillDownLifeEntity]
    life_entities_total: DrillDownLifeEntitiesTotal
    loans: list[DrillDownLoan]
    investments: DrillDownInvestments
    summary: DrillDownSummary
