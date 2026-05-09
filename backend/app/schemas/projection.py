"""
Pydantic schemas for the projection API (TASK-4.2).

Response models for GET /api/projection — serialise the projection engine's
dataclass output into JSON. All Decimal fields serialise as strings.
"""
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

    # Derived
    passive_monthly: str
    total_monthly_income: str
    goal_reached: bool


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
            passive_monthly=str(t.passive_monthly),
            total_monthly_income=str(t.total_monthly_income),
            goal_reached=t.goal_reached,
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
