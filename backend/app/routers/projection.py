"""
Projection API router (TASK-4.2).

Bridge between the database and the projection engine.
GET /api/projection assembles all user data, calls the engine,
and returns the full timeline + summary.
"""
import logging
import time
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.calculations.constants import INFLATION_SCALES, get_growth_rate
from app.calculations.projection import (
    ProjectionInput,
    compute_summary,
    project_timeline,
)
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.investment import InvestmentAllocation
from app.models.life_entity import LifeEntity
from app.models.profile import UserProfile
from app.models.project import Project
from app.models.recurring_expense import RecurringExpense
from app.models.user import User
from app.schemas.projection import ProjectionResponse, build_projection_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projection", tags=["projection"])


# ── Data assembly helper ────────────────────────────────────────────────────


async def _assemble_input(
    user_id: str,
    scale: str,
    db: AsyncSession,
) -> ProjectionInput:
    """Assemble a ProjectionInput from all user data sources.

    Runs DB queries sequentially — SQLAlchemy async sessions do NOT support
    concurrent operations (asyncio.gather causes IllegalStateChangeError).
    Every data source falls back gracefully — empty lists for no entities,
    zeros for missing allocations.

    Args:
        user_id: The authenticated user's UUID.
        scale: The inflation scale to use.
        db: Async database session.

    Returns:
        A fully populated ProjectionInput dataclass.

    Raises:
        HTTPException 404 if no profile exists.
        HTTPException 422 if birth_date is null.
    """
    # Sequential DB queries — async session is not concurrency-safe
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    entities_result = await db.execute(
        select(LifeEntity)
        .where(
            LifeEntity.user_id == user_id,
            LifeEntity.is_active == True,
        )
        .order_by(LifeEntity.sort_order)
    )
    recurring_result = await db.execute(
        select(RecurringExpense)
        .where(
            RecurringExpense.user_id == user_id,
            RecurringExpense.is_active == True,
        )
    )
    allocations_result = await db.execute(
        select(InvestmentAllocation).where(
            InvestmentAllocation.user_id == user_id
        )
    )
    projects_result = await db.execute(
        select(Project)
        .where(
            Project.user_id == user_id,
            Project.is_active == True,
        )
    )

    profile: UserProfile | None = profile_result.scalar_one_or_none()

    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="Complétez votre profil d'abord",
        )

    if profile.birth_date is None:
        raise HTTPException(
            status_code=422,
            detail="Date de naissance requise pour la projection",
        )

    # Compute current age from birth_date
    today = date.today()
    current_age = today.year - profile.birth_date.year
    if (today.month, today.day) < (
        profile.birth_date.month,
        profile.birth_date.day,
    ):
        current_age -= 1

    # Resolve growth rate
    growth_rate = get_growth_rate(
        profile.growth_preset,
        profile.growth_rate_custom,
    )

    # Sum monthly expenses from JSONB
    monthly_expenses_total = Decimal("0")
    if profile.monthly_expenses:
        for amount in profile.monthly_expenses.values():
            monthly_expenses_total += Decimal(str(amount))

    # Life entities → pre-process flat schedule
    life_entities: list[dict] = []
    for entity in entities_result.scalars().all():
        # Compute entity age at projection start
        ref_date: date = entity.reference_date
        entity_age_at_start = today.year - ref_date.year
        if (today.month, today.day) < (ref_date.month, ref_date.day):
            entity_age_at_start -= 1
        if entity_age_at_start < 0:
            entity_age_at_start = max(-1, entity_age_at_start)

        life_entities.append(
            {
                "entity_type": entity.entity_type,
                "entity_name": entity.name,
                "entity_age_at_start": entity_age_at_start,
                "cost_events": entity.cost_events or [],
            }
        )

    # Recurring expenses
    recurring_list: list[dict] = []
    for r in recurring_result.scalars().all():
        recurring_list.append(
            {
                "label": r.label,
                "annual_amount": float(r.annual_amount),
                "from_year": r.from_year,
                "to_year": r.to_year,
            }
        )

    # Investment allocations
    allocations_dict: dict[str, dict[str, Decimal]] = {}
    for a in allocations_result.scalars().all():
        allocations_dict[a.vehicle_key] = {
            "balance": a.existing_balance,
            "monthly": a.monthly_contribution,
        }

    # Projects
    projects_list: list[dict] = []
    for p in projects_result.scalars().all():
        proj_dict = {
            "type": p.project_type,
            "label": p.label,
        }
        if p.project_type == "invest":
            proj_dict["start_year"] = p.start_year
            proj_dict["purchase_cost"] = (
                float(p.purchase_cost) if p.purchase_cost is not None else 0
            )
            proj_dict["annual_income"] = (
                float(p.annual_income) if p.annual_income is not None else 0
            )
            proj_dict["annual_expenses"] = (
                float(p.annual_expenses) if p.annual_expenses is not None else 0
            )
            proj_dict["tax_rate"] = (
                float(p.tax_rate) if p.tax_rate is not None else 0.30
            )
        elif p.project_type == "event":
            proj_dict["event_year"] = p.event_year
            proj_dict["event_cost"] = (
                float(p.event_cost) if p.event_cost is not None else 0
            )
        projects_list.append(proj_dict)

    # Kids birth dates for CAF
    kids_birth_dates: list[date] = []
    for entity in entities_result.scalars().all():
        if entity.entity_type == "kid":
            kids_birth_dates.append(entity.reference_date)

    return ProjectionInput(
        current_age=current_age,
        target_age=profile.target_retirement_age,
        monthly_gross=profile.monthly_gross_ca or Decimal("0"),
        growth_rate=growth_rate,
        ae_activity_type=profile.ae_activity_type,
        monthly_expenses_total=monthly_expenses_total,
        scale=scale,
        life_entities=life_entities,
        recurring_expenses=recurring_list,
        allocations=allocations_dict,
        projects=projects_list,
        kids_birth_dates=kids_birth_dates,
        caf_override_monthly=profile.caf_override_monthly,
        household_income_for_caf=profile.monthly_gross_ca or Decimal("0"),
        cesu_annual=profile.cesu_annual,
        charity_annual=profile.charity_annual,
        status_change_enabled=profile.status_change_enabled,
        status_change_year=profile.status_change_year,
        status_change_savings=profile.status_change_savings,
        monthly_revenue_goal=profile.monthly_revenue_goal,
    )


# ── Route ────────────────────────────────────────────────────────────────────


@router.get("", response_model=ProjectionResponse)
async def get_projection(
    scale: str = Query(
        default="moderate",
        description="Inflation scale: optimistic, moderate, or pessimistic",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute and return the full 30-year projection.

    Assembles all user data, runs the projection engine, and returns
    the timeline (one entry per year) plus summary statistics including
    wealth milestones and goal attainment.

    Query params:
        scale: Override the profile's saved world_scale for this request.
               Does NOT persist — frontend saves the preference separately.
    """
    t_start = time.perf_counter()

    # Validate scale
    if scale not in INFLATION_SCALES:
        valid = ", ".join(INFLATION_SCALES.keys())
        raise HTTPException(
            status_code=422,
            detail=f"Échelle inconnue: {scale!r}. Valides: {valid}",
        )

    try:
        inp = await _assemble_input(str(current_user.id), scale, db)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to assemble projection input")
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la préparation des données de projection",
        ) from exc

    try:
        timeline = project_timeline(inp)
        summary = compute_summary(timeline)
    except Exception as exc:
        logger.exception("Projection engine failed")
        raise HTTPException(
            status_code=500,
            detail="Erreur de calcul de la projection",
        ) from exc

    elapsed_ms = (time.perf_counter() - t_start) * 1000
    logger.info(
        "Projection computed user=%s scale=%s years=%d elapsed=%.1fms",
        current_user.id,
        scale,
        len(timeline),
        elapsed_ms,
    )

    return build_projection_response(timeline, summary, scale)