"""
Pydantic schemas for the projection API (TASK-4.2).

Response models for GET /api/projection — serialise the projection engine's
dataclass output into JSON. All Decimal fields serialise as strings.
"""
from typing import Any

from pydantic import BaseModel, Field


class YearProjectionOut(BaseModel):
    """A single year in the 30-year projection timeline, serialised for JSON."""

    year: int
    age: int

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
    """Summary statistics for the full projection timeline."""

    years: int
    final_wealth: str
    final_passive_monthly: str
    total_invested: str
    total_returns: str
    goal_year: GoalYearOut | None = None
    milestones: list[MilestoneOut] = Field(default_factory=list)


class ProjectionResponse(BaseModel):
    """Full projection API response — timeline + summary."""

    timeline: list[YearProjectionOut]
    summary: ProjectionSummaryOut
    scale: str


def build_projection_response(
    timeline: list[Any],  # list of YearProjection (dataclass)
    summary: dict[str, Any],
    scale: str,
) -> ProjectionResponse:
    """Convert engine output to Pydantic response models.

    Args:
        timeline: List of YearProjection dataclass instances.
        summary: Dict from compute_summary().
        scale: The inflation scale used for this projection.

    Returns:
        A fully serialisable ProjectionResponse.
    """
    timeline_out = [
        YearProjectionOut(
            year=t.year,
            age=t.age,
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
    )

    return ProjectionResponse(
        timeline=timeline_out,
        summary=summary_out,
        scale=scale,
    )