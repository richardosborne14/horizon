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
from app.schemas.projection import (
    CompareResponse,
    DeltaOut,
    ProjectionResponse,
    ScenarioCompareRequest,
    build_projection_response,
)

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

    # Post-retirement config (Sprint 5)
    post_retirement_years = getattr(
        profile, "post_retirement_years", None
    ) or 25
    pension_monthly = getattr(
        profile, "pension_monthly", None
    ) or Decimal("0")

    return ProjectionInput(
        current_age=current_age,
        target_age=profile.target_retirement_age,
        post_retirement_years=post_retirement_years,
        pension_monthly=pension_monthly,
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

    # ── Generate insights (TASK-5.4) ──────────────────────────────────
    from app.calculations.insights import generate_insights

    # Build allocations list for insights engine
    allocations_list = [
        {
            "vehicle_key": vk,
            "balance": float(alloc.get("balance", Decimal("0"))),
            "monthly": float(alloc.get("monthly", Decimal("0"))),
        }
        for vk, alloc in inp.allocations.items()
    ]

    # Build profile_data dict
    profile_data = {
        "monthly_gross": float(inp.monthly_gross),
        "growth_rate": float(inp.growth_rate),
        "target_age": inp.target_age,
        "current_age": inp.current_age,
    }

    insights = generate_insights(timeline, summary, profile_data, allocations_list)

    # ── Compute readiness score (TASK-5.5) ────────────────────────────
    from app.calculations.readiness import compute_readiness_score

    readiness = compute_readiness_score(
        timeline,
        summary,
        profile_data,
        allocations_list,
        monthly_revenue_goal=inp.monthly_revenue_goal,
    )

    elapsed_ms = (time.perf_counter() - t_start) * 1000
    logger.info(
        "Projection computed user=%s scale=%s years=%d insights=%d readiness=%d elapsed=%.1fms",
        current_user.id,
        scale,
        len(timeline),
        len(insights),
        readiness.score,
        elapsed_ms,
    )

    return build_projection_response(timeline, summary, scale, insights, readiness)


# ── Pension estimate endpoint (TASK-5.3) ──────────────────────────────────


@router.get("/pension-estimate")
async def get_pension_estimate(
    scale: str = Query(
        default="moderate",
        description="Inflation scale for pension threshold revalorisation",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return an indicative state pension (retraite) estimate.

    Uses the user's CA history from the projection engine to estimate
    trimestres validés, retraite de base, and retraite complémentaire.

    IMPORTANT: This is an indicative estimate, not a replacement for
    info-retraite.fr. Always display with a caveat.
    """
    from app.calculations.pension import estimate_monthly_pension

    # Validate scale
    if scale not in INFLATION_SCALES:
        valid = ", ".join(INFLATION_SCALES.keys())
        raise HTTPException(
            status_code=422,
            detail=f"Échelle inconnue: {scale!r}. Valides: {valid}",
        )

    # Get profile for birth date and activity type
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == str(current_user.id))
    )
    profile: UserProfile | None = profile_result.scalar_one_or_none()

    if profile is None or profile.birth_date is None:
        raise HTTPException(
            status_code=422,
            detail="Date de naissance requise pour l'estimation de retraite",
        )

    birth_year = profile.birth_date.year
    activity_type = profile.ae_activity_type or "bnc_non_reglementee"

    # Compute projection to get CA history
    try:
        inp = await _assemble_input(str(current_user.id), scale, db)
        timeline = project_timeline(inp)
    except Exception as exc:
        logger.exception("Failed to compute projection for pension estimate")
        raise HTTPException(
            status_code=500,
            detail="Erreur lors du calcul de la projection",
        ) from exc

    # Extract CA history from the timeline (only accumulation years)
    ca_history = [
        t.gross_annual for t in timeline if not t.is_retirement
    ]

    # Compute pension estimate
    result = estimate_monthly_pension(
        birth_year=birth_year,
        activity_type=activity_type,
        ca_history=ca_history,
        retirement_age=profile.target_retirement_age,
        inflation_rate=INFLATION_SCALES[scale]["inflation"],
    )

    return result


# ── Scenario comparison endpoint (TASK-5.7) ───────────────────────────────


@router.post("/compare", response_model=CompareResponse)
async def compare_scenarios(
    body: ScenarioCompareRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compare base projection with an overridden scenario.

    Runs the projection engine twice: once with base parameters and once
    with the overrides applied. Returns both timelines, summaries,
    insights, readiness scores, and key deltas.

    This is the backend for the "Et si...?" scenario comparison panel.
    """
    scale = body.base_scale
    if scale not in INFLATION_SCALES:
        valid = ", ".join(INFLATION_SCALES.keys())
        raise HTTPException(
            status_code=422,
            detail=f"Échelle inconnue: {scale!r}. Valides: {valid}",
        )

    overrides = body.overrides

    # ── Base projection ──────────────────────────────────────────
    try:
        base_inp = await _assemble_input(str(current_user.id), scale, db)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to assemble base input for compare")
        raise HTTPException(status_code=500, detail="Erreur de préparation") from exc

    base_timeline = project_timeline(base_inp)
    base_summary = compute_summary(base_timeline)

    # ── Scenario projection — apply overrides ────────────────────
    from copy import deepcopy

    sc_inp = deepcopy(base_inp)

    if overrides.monthly_savings is not None:
        total_savings = Decimal(str(overrides.monthly_savings))
        # Distribute proportionally across existing allocations
        existing_total = sum(
            alloc.get("monthly", Decimal("0")) for alloc in sc_inp.allocations.values()
        )
        if existing_total > Decimal("0"):
            for vk, alloc in sc_inp.allocations.items():
                current = alloc.get("monthly", Decimal("0"))
                if current > Decimal("0"):
                    share = current / existing_total
                    alloc["monthly"] = (total_savings * share).quantize(Decimal("0.01"))
        elif total_savings > Decimal("0"):
            # All savings go to a default vehicle if none set
            from app.calculations.vehicles import VEHICLE_SPECS
            vehicle_keys = [k for k, s in VEHICLE_SPECS.items() if s.get("default_investment")]
            default_vk = vehicle_keys[0] if vehicle_keys else "pea"
            sc_inp.allocations[default_vk] = sc_inp.allocations.get(default_vk, {"balance": Decimal("0"), "monthly": Decimal("0")})
            sc_inp.allocations[default_vk]["monthly"] = total_savings

    if overrides.target_retirement_age is not None:
        sc_inp.target_age = overrides.target_retirement_age

    if overrides.growth_rate is not None:
        sc_inp.growth_rate = Decimal(str(overrides.growth_rate))

    if overrides.monthly_expenses_delta is not None:
        delta = Decimal(str(overrides.monthly_expenses_delta))
        sc_inp.monthly_expenses_total = max(
            Decimal("0"),
            sc_inp.monthly_expenses_total + delta,
        )

    if overrides.disable_project is not None:
        sc_inp.projects = [
            p for p in sc_inp.projects
            if str(p.get("label", "")) != overrides.disable_project
        ]

    if overrides.extra_monthly_investment is not None:
        vk = overrides.extra_monthly_investment.get("vehicle_key", "")
        amount = Decimal(str(overrides.extra_monthly_investment.get("amount", 0)))
        if vk and amount > Decimal("0"):
            if vk not in sc_inp.allocations:
                sc_inp.allocations[vk] = {"balance": Decimal("0"), "monthly": Decimal("0")}
            sc_inp.allocations[vk]["monthly"] += amount

    sc_timeline = project_timeline(sc_inp)
    sc_summary = compute_summary(sc_timeline)

    # ── Compute insights and readiness for BOTH ──────────────────
    from app.calculations.insights import generate_insights
    from app.calculations.readiness import compute_readiness_score

    def _build_alloc_list(inp):
        return [
            {
                "vehicle_key": vk,
                "balance": float(alloc.get("balance", Decimal("0"))),
                "monthly": float(alloc.get("monthly", Decimal("0"))),
            }
            for vk, alloc in inp.allocations.items()
        ]

    def _build_profile_data(inp):
        return {
            "monthly_gross": float(inp.monthly_gross),
            "growth_rate": float(inp.growth_rate),
            "target_age": inp.target_age,
            "current_age": inp.current_age,
        }

    base_alloc_list = _build_alloc_list(base_inp)
    sc_alloc_list = _build_alloc_list(sc_inp)
    base_pdata = _build_profile_data(base_inp)
    sc_pdata = _build_profile_data(sc_inp)

    base_insights = generate_insights(base_timeline, base_summary, base_pdata, base_alloc_list)
    sc_insights = generate_insights(sc_timeline, sc_summary, sc_pdata, sc_alloc_list)
    base_readiness = compute_readiness_score(
        base_timeline, base_summary, base_pdata, base_alloc_list, base_inp.monthly_revenue_goal
    )
    sc_readiness = compute_readiness_score(
        sc_timeline, sc_summary, sc_pdata, sc_alloc_list, sc_inp.monthly_revenue_goal
    )

    base_resp = build_projection_response(base_timeline, base_summary, scale, base_insights, base_readiness)
    sc_resp = build_projection_response(sc_timeline, sc_summary, scale, sc_insights, sc_readiness)

    # ── Compute deltas ───────────────────────────────────────────
    def _parse(s: str) -> float:
        return float(s) if s else 0.0

    base_final = _parse(base_summary.get("final_wealth", "0"))
    sc_final = _parse(sc_summary.get("final_wealth", "0"))
    delta_wealth = int(sc_final - base_final)

    base_passive = _parse(base_summary.get("final_passive_monthly", "0"))
    sc_passive = _parse(sc_summary.get("final_passive_monthly", "0"))
    delta_passive = int(sc_passive - base_passive)

    delta_goal = None
    base_goal = base_summary.get("goal_year")
    sc_goal = sc_summary.get("goal_year")
    if base_goal and sc_goal:
        diff_years = sc_goal.get("year", 0) - base_goal.get("year", 0)
        if diff_years < 0:
            delta_goal = f"{abs(diff_years)} ans plus tôt"
        elif diff_years > 0:
            delta_goal = f"{diff_years} ans plus tard"
        else:
            delta_goal = "inchangé"
    elif not base_goal and sc_goal:
        delta_goal = "objectif désormais atteint"
    elif base_goal and not sc_goal:
        delta_goal = "objectif plus atteint"

    delta_exhaustion = None
    base_exh = base_summary.get("wealth_exhaustion_age")
    sc_exh = sc_summary.get("wealth_exhaustion_age")
    if base_exh and sc_exh:
        diff = int(sc_exh) - int(base_exh)
        if diff > 0:
            delta_exhaustion = f"+{diff} ans"
        elif diff < 0:
            delta_exhaustion = f"{diff} ans"
        else:
            delta_exhaustion = "inchangé"
    elif base_exh and not sc_exh:
        delta_exhaustion = "patrimoine durable"
    elif not base_exh and sc_exh:
        delta_exhaustion = f"épuisement à {sc_exh} ans"
    elif not base_exh and not sc_exh:
        delta_exhaustion = "pas d'épuisement"

    delta = DeltaOut(
        final_wealth=f"{delta_wealth:+d}€" if delta_wealth >= 0 else f"{delta_wealth}€",
        passive_monthly=f"{delta_passive:+d}€/mois" if delta_passive >= 0 else f"{delta_passive}€/mois",
        goal_reached_year_delta=delta_goal,
        wealth_exhaustion_delta=delta_exhaustion,
    )

    return CompareResponse(base=base_resp, scenario=sc_resp, delta=delta)
