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
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.calculations.constants import INFLATION_SCALES, AE_RATE_ANNUAL_GROWTH, get_growth_rate
from app.calculations.projection import (
    ProjectionInput,
    compute_summary,
    project_timeline,
)
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.investment import InvestmentAllocation
from app.models.life_entity import LifeEntity
from app.models.loan import Loan
from app.models.profile import UserProfile
from app.models.project import Project
from app.models.recurring_expense import RecurringExpense
from app.models.spouse import Spouse
from app.models.user import User
from app.schemas.projection import (
    CompareResponse,
    DeltaOut,
    ExpenseTimelineResponse,
    LifecycleAlertOut,
    LifecycleAlertsResponse,
    ProjectionResponse,
    ScenarioCompareRequest,
    SensitivityParamOut,
    SensitivityResponse,
    YearDrillDownResponse,
    build_projection_response,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projection", tags=["projection"])


# ── Helpers ─────────────────────────────────────────────────────────────────


def _compute_cc_annual(cc_option: str, user_ca_annual: Decimal) -> Decimal:
    """Compute annual CC (conjointe collaboratrice) cotisation.

    Based on the chosen cotisation base option and the user's annual CA.

    Args:
        cc_option: The CC option (tiers_plafond, moitie_plafond, tiers_revenu, moitie_revenu).
        user_ca_annual: The user's annual chiffre d'affaires.

    Returns:
        Annual cotisation amount in €.
    """
    PLAFOND_SS = Decimal("46368")
    CC_RATE = Decimal("0.28")  # ~28% includes all CG branches

    bases: dict[str, Decimal] = {
        "tiers_plafond": PLAFOND_SS / Decimal("3"),
        "moitie_plafond": PLAFOND_SS / Decimal("2"),
        "tiers_revenu": user_ca_annual / Decimal("3"),
        "moitie_revenu": user_ca_annual / Decimal("2"),
    }
    base = bases.get(cc_option, Decimal("0"))
    return (base * CC_RATE).quantize(Decimal("0.01"))


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

    # Sum monthly expenses from JSONB (12 standard + custom)
    monthly_expenses_total = Decimal("0")
    if profile.monthly_expenses:
        for amount in profile.monthly_expenses.values():
            monthly_expenses_total += Decimal(str(amount))
    # Include custom expenses
    for ce in (profile.custom_expenses or []):
        monthly_expenses_total += Decimal(str(ce.get("amount", "0")))

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

    # Loans (Sprint 6)
    loans_result = await db.execute(
        select(Loan)
        .where(
            Loan.user_id == user_id,
            Loan.is_active == True,
        )
    )
    loans_list: list[dict] = []
    for loan in loans_result.scalars().all():
        loans_list.append(
            {
                "label": loan.label,
                "monthly_payment": float(loan.monthly_payment),
                "start_date": str(loan.start_date),
                "end_date": str(loan.end_date) if loan.end_date else None,
                "insurance_monthly": float(loan.insurance_monthly or Decimal("0")),
            }
        )

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

    # Income Tax (TASK-7.12) — assemble IR parameters from profile + spouse
    tax_parts = profile.tax_parts if profile.tax_parts else Decimal("1")
    has_vl = bool(profile.has_versement_liberatoire)

    spouse_annual_income = Decimal("0")
    spouse_row = await db.execute(
        select(Spouse).where(Spouse.user_id == user_id)
    )
    spouse = spouse_row.scalar_one_or_none()
    if spouse is not None and spouse.monthly_gross_income is not None:
        spouse_annual_income = spouse.monthly_gross_income * Decimal("12")

    # ── Spouse projection fields (TASK-7.8) ───────────────────────────
    spouse_monthly_gross = Decimal("0")
    spouse_growth_rate = Decimal("0.03")
    spouse_ae_type = None
    spouse_pension_monthly = Decimal("0")
    cc_annual_cotisation = Decimal("0")

    if spouse is not None:
        spouse_monthly_gross = spouse.monthly_gross_income or Decimal("0")
        spouse_ae_type = spouse.ae_activity_type

        # Compute CC annual cotisation if applicable
        if spouse.is_conjointe_collaboratrice and spouse.cc_cotisation_option:
            user_ca_annual = (profile.monthly_gross_ca or Decimal("0")) * Decimal("12")
            cc_annual_cotisation = _compute_cc_annual(
                spouse.cc_cotisation_option, user_ca_annual,
            )

    # ── Income sources (TASK-7.8) ─────────────────────────────────────
    from app.models.income_source import IncomeSource
    sources_result = await db.execute(
        select(IncomeSource).where(
            IncomeSource.user_id == user_id,
            IncomeSource.is_active == True,
        )
    )
    income_sources_list: list[dict] | None = None
    for s in sources_result.scalars().all():
        if income_sources_list is None:
            income_sources_list = []
        income_sources_list.append({
            "earner": s.earner,
            "label": s.label,
            "amount": str(s.amount),
            "frequency": s.frequency,
            "start_date": s.start_date.isoformat() if s.start_date else None,
            "end_date": s.end_date.isoformat() if s.end_date else None,
            "annual_growth_rate": str(s.annual_growth_rate) if s.annual_growth_rate else None,
            "is_ae_revenue": s.is_ae_revenue,
        })

    # ── Property (TASK-7.16) — load from net worth snapshot ───────────
    from app.models.net_worth import NetWorthSnapshot
    nw_result = await db.execute(
        select(NetWorthSnapshot).where(
            NetWorthSnapshot.user_id == user_id,
        )
    )
    nw = nw_result.scalar_one_or_none()

    prop_value = Decimal("0")
    prop_appreciation = Decimal("0.02")
    downsize_enabled = False
    downsize_year: int | None = None
    downsize_target = Decimal("0")

    if nw is not None:
        prop_value = (nw.property_primary_value or Decimal("0"))
        if nw.property_appreciation_rate is None:
            # AUDIT-8.2.6 #14: log when defaulting silently so it's visible in backend logs.
            # Users who haven't set an appreciation rate get 2% — the French long-run average.
            logger.info(
                "property_appreciation_rate not set for user %s — defaulting to 2%%/yr", user_id
            )
        prop_appreciation = (nw.property_appreciation_rate or Decimal("0.02"))
        downsize_enabled = bool(nw.downsize_enabled)
        downsize_year = nw.downsize_year
        downsize_target = (nw.downsize_target_value or Decimal("0"))

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
        loans=loans_list,
        monthly_revenue_goal=profile.monthly_revenue_goal,
        tax_parts=tax_parts,
        versement_liberatoire=has_vl,
        spouse_annual_income=spouse_annual_income,
        # TASK-7.8 spouse fields
        spouse_monthly_gross=spouse_monthly_gross,
        spouse_growth_rate=spouse_growth_rate,
        spouse_ae_type=spouse_ae_type,
        spouse_pension_monthly=spouse_pension_monthly,
        cc_annual_cotisation=cc_annual_cotisation,
        income_sources=income_sources_list,
        property_value=prop_value,
        property_appreciation_rate=prop_appreciation,
        downsize_enabled=downsize_enabled,
        downsize_year=downsize_year,
        downsize_target_value=downsize_target,
        # AUDIT-8.2.5: apply scale-appropriate AE rate annual growth
        ae_rate_annual_growth=AE_RATE_ANNUAL_GROWTH.get(scale, Decimal("0")),
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
    """Return an indicative state pension (retraite) estimate for the household.

    Computes user pension (via AE ca_history) and, if a spouse exists,
    spouse pension (via career history + optional CC trimestres).

    Response shape:
        {
            "user_pension": { ... flat pension dict ... },
            "spouse_pension": { ... flat pension dict or null ... },
            "household_pension_monthly": "xxx.xx"
        }

    IMPORTANT: This is an indicative estimate, not a replacement for
    info-retraite.fr. Always display with a caveat.
    """
    from datetime import date as date_type
    from decimal import Decimal as Dec

    from app.calculations.pension import (
        estimate_monthly_pension,
        estimate_monthly_pension_v2,
        estimate_cc_trimestres_per_year,
        get_trimestres_requis,
        TAUX_PLEIN,
        DECOTE_PER_TRIMESTRE,
        SURCOTE_PER_TRIMESTRE,
        MAX_DECOTE_TRIMESTRES,
        AGE_TAUX_PLEIN_AUTO,
        PASS,
    )
    from app.models.career_period import CareerPeriod

    # Validate scale
    if scale not in INFLATION_SCALES:
        valid = ", ".join(INFLATION_SCALES.keys())
        raise HTTPException(
            status_code=422,
            detail=f"Échelle inconnue: {scale!r}. Valides: {valid}",
        )

    infl_rate = INFLATION_SCALES[scale]["inflation"]

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

    # ── Fetch ALL career periods (user + spouse) once ─────────────
    career_result = await db.execute(
        select(CareerPeriod)
        .where(
            CareerPeriod.user_id == str(current_user.id),
            CareerPeriod.is_active == True,
        )
        .order_by(CareerPeriod.start_date)
    )
    all_periods = career_result.scalars().all()

    user_career_dicts: list[dict] = []
    spouse_career_dicts: list[dict] = []
    for cp in all_periods:
        d = {
            "period_type": cp.period_type,
            "start_date": cp.start_date.isoformat() if cp.start_date else None,
            "end_date": cp.end_date.isoformat() if cp.end_date else None,
            "annual_gross": cp.annual_gross,
            "is_full_time": cp.is_full_time,
            "time_percentage": cp.time_percentage,
        }
        if cp.owner == "user":
            user_career_dicts.append(d)
        elif cp.owner == "spouse":
            spouse_career_dicts.append(d)

    # ── User pension (v2 career-aware) ───────────────────────────
    # Build projected AE CA from income sources
    # user_years_to_ret must be in outer scope — referenced by deflation block
    # regardless of whether income_sources is populated.
    user_years_to_ret = max(
        0,
        (profile.target_retirement_age or 67) - (date.today().year - profile.birth_date.year),
    )
    user_projected_ae_ca: list[dict] = []
    if inp.income_sources:
        user_ae_sources = [
            s for s in inp.income_sources
            if s.get("earner") == "user" and s.get("is_ae_revenue", True)
        ]
        user_base_monthly = Decimal("0")
        for s in user_ae_sources:
            amt = Decimal(str(s.get("amount", "0")))
            freq = s.get("frequency", "monthly")
            if freq == "annual":
                user_base_monthly += amt / Decimal("12")
            elif freq == "monthly":
                user_base_monthly += amt
        user_growth = inp.growth_rate
        for i in range(user_years_to_ret):
            yr = date.today().year + i
            grown = user_base_monthly * Decimal("12") * ((Decimal("1") + user_growth) ** i)
            user_projected_ae_ca.append({"year": yr, "ca": grown})

    user_v2_raw = estimate_monthly_pension_v2(
        birth_year=birth_year,
        career_periods=user_career_dicts,
        projected_ae_ca=user_projected_ae_ca,
        ae_activity_type=activity_type,
        retirement_age=profile.target_retirement_age or 67,
        current_year=date.today().year,
        inflation_rate=infl_rate,
    )
    # Build a user_pension dict compatible with the existing response format
    user_pension = {
        "total_monthly": Decimal(str(user_v2_raw.get("total_monthly", "0"))).quantize(Decimal("0.01")),
        "base_monthly": Decimal(str(user_v2_raw.get("base_salarie_monthly", user_v2_raw.get("base_monthly", "0")))).quantize(Decimal("0.01")),
        "complementaire_monthly": Decimal(str(user_v2_raw.get("complementaire_monthly", "0"))).quantize(Decimal("0.01")),
        "trimestres_valides": user_v2_raw.get("trimestres", {}).get("total", 0),
        "trimestres_requis": user_v2_raw.get("trimestres", {}).get("required", get_trimestres_requis(birth_year)),
        "taux": user_v2_raw.get("taux", Decimal("0.5")),
        "confidence": user_v2_raw.get("confidence", "medium"),
        "is_taux_plein": user_v2_raw.get("is_taux_plein", False),
    }

    # PENSION-BUG-1 — Deflate nominal pension to today's purchasing power.
    # estimate_monthly_pension_v2() projects CA forward at nominal growth rate
    # (real growth + inflation) and inflates the PASS cap year-by-year.
    # The resulting SAM and pension are therefore in nominal retirement-year
    # euros, which is ~2× today's purchasing power over 28 years at 2.5%
    # inflation.  Divide by (1 + infl_rate)^years_to_retirement so the card
    # shows a figure users can compare against today's living costs.
    if user_years_to_ret > 0:
        _user_deflation = (Decimal("1") + infl_rate) ** Decimal(str(user_years_to_ret))
        for _k in ("total_monthly", "base_monthly", "complementaire_monthly"):
            user_pension[_k] = (user_pension[_k] / _user_deflation).quantize(Decimal("0.01"))

    # ── Spouse pension (TASK-7.7) ──────────────────────────────────────
    spouse_pension = None

    spouse_row = await db.execute(
        select(Spouse).where(Spouse.user_id == str(current_user.id))
    )
    spouse = spouse_row.scalar_one_or_none()

    if spouse is not None and spouse.birth_date is not None:
        # Use spouse_career_dicts already collected above

        # Compute CC trimestres if applicable
        cc_trimestres_total = 0
        if (
            spouse.is_conjointe_collaboratrice
            and spouse.cc_cotisation_option
            and profile.target_retirement_age
        ):
            spouse_age = date_type.today().year - spouse.birth_date.year
            years_to_retirement = max(
                0, profile.target_retirement_age - spouse_age
            )
            # Reconstruct ca_history from user's projected AE CA
            ca_history_cc: list[Dec] = [
                d["ca"] for d in user_projected_ae_ca
            ]
            for i in range(years_to_retirement):
                if i < len(ca_history_cc):
                    projected_ca = ca_history_cc[i]
                elif ca_history_cc:
                    projected_ca = ca_history_cc[-1] * (
                        (Dec("1") + inp.growth_rate) ** (i - len(ca_history_cc) + 1)
                    )
                else:
                    projected_ca = Dec("0")
                cc_trimestres_total += estimate_cc_trimestres_per_year(
                    spouse.cc_cotisation_option, projected_ca
                )

        # Build projected AE CA from spouse income sources
        projected_ae_ca: list[dict] = []
        if inp.income_sources:
            spouse_age_now = date_type.today().year - spouse.birth_date.year
            years_to_ret = max(0, profile.target_retirement_age - spouse_age_now)
            current_yr = date_type.today().year
            # Get spouse growth rate from profile or default to ambitious
            spouse_growth = inp.growth_rate  # use household growth rate
            spouse_ae_sources = [
                s for s in inp.income_sources
                if s["earner"] == "spouse" and s.get("is_ae_revenue", True)
            ]
            # Sum base monthly AE income for spouse
            spouse_base_monthly = Decimal("0")
            for s in spouse_ae_sources:
                amt = Decimal(s["amount"])
                if s["frequency"] == "annual":
                    spouse_base_monthly += amt / Decimal("12")
                elif s["frequency"] == "monthly":
                    spouse_base_monthly += amt
            # Project forward with growth
            for i in range(years_to_ret):
                yr = current_yr + i
                grown = spouse_base_monthly * Decimal("12") * ((Dec("1") + spouse_growth) ** i)
                projected_ae_ca.append({
                    "year": yr,
                    "ca": grown,
                })

        # Call v2 for spouse career-aware pension
        spouse_v2 = estimate_monthly_pension_v2(
            birth_year=spouse.birth_date.year,
            career_periods=spouse_career_dicts,
            projected_ae_ca=projected_ae_ca,
            ae_activity_type=spouse.ae_activity_type or "bnc_non_reglementee",
            retirement_age=profile.target_retirement_age,
            current_year=date_type.today().year,
            inflation_rate=infl_rate,
        )

        # Add CC trimestres to v2 result
        v2_trimestres = spouse_v2["trimestres"]
        total_trimestres = v2_trimestres["total"] + cc_trimestres_total
        trimestres_requis = get_trimestres_requis(spouse.birth_date.year)

        # Recompute taux/decote with CC trimestres included
        is_taux_plein_age = profile.target_retirement_age >= AGE_TAUX_PLEIN_AUTO
        is_taux_plein_trimestres = total_trimestres >= trimestres_requis
        is_taux_plein = is_taux_plein_age or is_taux_plein_trimestres
        missing_trimestres = max(0, trimestres_requis - total_trimestres)

        if is_taux_plein:
            taux = TAUX_PLEIN
            if (
                profile.target_retirement_age > AGE_TAUX_PLEIN_AUTO
                and total_trimestres > trimestres_requis
            ):
                extra = total_trimestres - trimestres_requis
                surcote = min(Dec(str(extra)), Dec("20")) * SURCOTE_PER_TRIMESTRE
                taux = min(TAUX_PLEIN + surcote, Dec("0.625"))
        else:
            missing = min(missing_trimestres, MAX_DECOTE_TRIMESTRES)
            taux = TAUX_PLEIN - (Dec(str(missing)) * DECOTE_PER_TRIMESTRE)
            taux = max(taux, Dec("0.375"))

        # Use v2's SAM (before CC augmentation) — CC cotisation base adds
        # to the spouse's pension rights but SAM is from salaried income
        sam = spouse_v2.get("sam", Dec("0"))
        if isinstance(sam, (int, float)):
            sam = Dec(str(sam))

        # Compute base pension with CC trimestres
        prorata = min(
            Dec("1"),
            Dec(str(total_trimestres)) / Dec(str(trimestres_requis)),
        )
        base_annual = sam * taux * prorata
        base_monthly = base_annual / Dec("12")

        # Complementaire from v2
        complementaire_monthly = Dec(
            str(spouse_v2.get("complementaire_monthly", "0"))
        )

        total_monthly = base_monthly + complementaire_monthly

        spouse_pension = {
            "total_monthly": total_monthly.quantize(Dec("0.01")),
            "base_monthly": base_monthly.quantize(Dec("0.01")),
            "complementaire_monthly": complementaire_monthly.quantize(Dec("0.01")),
            "trimestres_valides": total_trimestres,
            "trimestres_requis": trimestres_requis,
            "taux": taux.quantize(Dec("0.0001")),
            "is_taux_plein": is_taux_plein,
            "includes_cc_trimestres": cc_trimestres_total,
            "confidence": spouse_v2.get("confidence", "low"),
        }

        # PENSION-BUG-1 (spouse) — same nominal→real deflation as user pension.
        # spouse_age_now is computed above (line ~700); years_to_ret is already in scope.
        _spouse_years = max(0, profile.target_retirement_age - (
            date_type.today().year - spouse.birth_date.year
        ))
        if _spouse_years > 0:
            _spouse_deflation = (Decimal("1") + infl_rate) ** Decimal(str(_spouse_years))
            for _k in ("total_monthly", "base_monthly", "complementaire_monthly"):
                spouse_pension[_k] = (spouse_pension[_k] / _spouse_deflation).quantize(Dec("0.01"))

    # ── Household total ────────────────────────────────────────────────
    user_monthly = Dec(str(user_pension.get("total_monthly", "0")))
    spouse_monthly = (
        Dec(str(spouse_pension["total_monthly"]))
        if spouse_pension
        else Dec("0")
    )
    household_pension_monthly = (
        user_monthly + spouse_monthly
    ).quantize(Dec("0.01"))

    # ── Career gaps (TASK-8.8.D) ───────────────────────────────────────
    from app.calculations.pension import detect_career_gaps

    career_gaps = detect_career_gaps(
        career_periods=user_career_dicts,
        user_birth_date=profile.birth_date,
    )

    return {
        "user_pension": user_pension,
        "spouse_pension": spouse_pension,
        "household_pension_monthly": household_pension_monthly,
        "career_gaps": career_gaps,
    }


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


# ── Expense timeline endpoint (TASK-6.6) ──────────────────────────────────


@router.get("/expense-timeline", response_model=ExpenseTimelineResponse)
async def get_expense_timeline(
    scale: str = Query(
        default="moderate",
        description="Inflation scale: optimistic, moderate, or pessimistic",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a year-by-year expense breakdown with key change events.

    Computes the full projection, then extracts expense categories per year
    (monthly values) and detects lifecycle events:
      - Loan terminations
      - Kid cost phase transitions (independence)
      - Pet end-of-life
      - Car replacement years (large one-time spikes)

    This powers the stacked area chart on the Charges/Runway page.
    """
    from app.schemas.projection import (
        ExpenseTimelineEvent,
        ExpenseTimelineYear,
        ExpenseTimelineResponse,
    )

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
        logger.exception("Failed to assemble projection input for expense timeline")
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la préparation des données",
        ) from exc

    try:
        timeline = project_timeline(inp)
    except Exception as exc:
        logger.exception("Projection engine failed for expense timeline")
        raise HTTPException(
            status_code=500,
            detail="Erreur de calcul de la projection",
        ) from exc

    # ── Build year-by-year expense breakdown ──────────────────────────
    timeline_out: list[ExpenseTimelineYear] = []
    previous_total: Decimal | None = None

    for entry in timeline:
        # Convert annual amounts to monthly
        base_m = _to_monthly(entry.base_expenses)
        loan_m = _to_monthly(getattr(entry, "loan_expenses", Decimal("0")))
        kid_m = _to_monthly(entry.kid_expenses)
        pet_m = _to_monthly(entry.pet_expenses)
        car_m = _to_monthly(entry.car_expenses)
        tech_m = _to_monthly(entry.tech_expenses)
        rec_m = _to_monthly(entry.recurring_expenses)
        proj_m = _to_monthly(entry.project_expenses)

        total_m = base_m + loan_m + kid_m + pet_m + car_m + tech_m + rec_m + proj_m

        # Gather events for this year
        events: list[str] = []
        if loan_m > 0:
            events.append("Crédits en cours")
        if kid_m > 0:
            events.append("Enfants à charge")
        if entry.is_retirement:
            events.append("Retraite")
        if car_m > 0 and any(
            evt.get("entity_type") == "car" for evt in inp.life_entities
        ):
            events.append("Véhicule actif")

        # Compute delta vs previous year
        delta = Decimal("0")
        if previous_total is not None:
            delta = total_m - previous_total
        previous_total = total_m

        timeline_out.append(
            ExpenseTimelineYear(
                year=entry.year,
                age=entry.age,
                base_expenses_monthly=str(base_m.quantize(Decimal("0.01"))),
                loan_payments_monthly=str(loan_m.quantize(Decimal("0.01"))),
                kid_expenses_monthly=str(kid_m.quantize(Decimal("0.01"))),
                pet_expenses_monthly=str(pet_m.quantize(Decimal("0.01"))),
                car_expenses_monthly=str(car_m.quantize(Decimal("0.01"))),
                tech_expenses_monthly=str(tech_m.quantize(Decimal("0.01"))),
                recurring_monthly=str(rec_m.quantize(Decimal("0.01"))),
                project_expenses_monthly=str(proj_m.quantize(Decimal("0.01"))),
                total_monthly=str(total_m.quantize(Decimal("0.01"))),
                events=events,
                delta_vs_previous=str(delta.quantize(Decimal("0.01"))),
            )
        )

    # ── Detect key lifecycle events ───────────────────────────────────
    key_events = _detect_expense_events(timeline, inp)

    return ExpenseTimelineResponse(timeline=timeline_out, key_events=key_events)


def _to_monthly(annual: Decimal) -> Decimal:
    """Convert an annual Decimal amount to monthly."""
    if annual is None or (hasattr(annual, "__len__") and len(str(annual)) == 0):
        return Decimal("0")
    d = Decimal(str(annual))
    return d / Decimal("12")


def _detect_expense_events(
    timeline: list[Any],
    inp: Any,  # ProjectionInput
) -> list[dict[str, Any]]:
    """Detect key expense change events from the projection timeline.

    Looks for:
      - Loan terminations (payment drops to zero)
      - Kid cost phase transitions (last cost event ending = independence)
      - Pet end-of-life (last cost event)
      - Car replacement years (large one-time spikes)

    Args:
        timeline: Full projection timeline.
        inp: The assembled ProjectionInput.

    Returns:
        List of ExpenseTimelineEvent dicts sorted by year.
    """
    from decimal import Decimal

    key_events: list[dict[str, Any]] = []

    # ── Loan termination events ──────────────────────────────────
    if inp.loans:
        for loan in inp.loans:
            label = loan.get("label", "Crédit")
            monthly_payment = Decimal(str(loan.get("monthly_payment", 0)))
            insurance = Decimal(str(loan.get("insurance_monthly", 0)))
            total_monthly = monthly_payment + insurance

            if total_monthly <= 0:
                continue

            end_date_str = loan.get("end_date")
            if end_date_str is None:
                continue

            # Parse end date
            if isinstance(end_date_str, str):
                end_date = date.fromisoformat(end_date_str)
            else:
                end_date = end_date_str

            end_year = end_date.year

            # The loan is active until end_year inclusive, ends the year after
            termination_year = end_year + 1
            if termination_year >= inp.current_year and termination_year <= (
                inp.current_year + len(timeline)
            ):
                key_events.append(
                    {
                        "year": termination_year,
                        "event": f"✅ {label} terminé",
                        "impact_monthly": str((-total_monthly).quantize(Decimal("0.01"))),
                        "category": "loan_end",
                    }
                )

    # ── Kid cost phase transitions ────────────────────────────────
    for entity in inp.life_entities:
        if entity.get("entity_type") != "kid":
            continue
        name = entity.get("entity_name", "Enfant")
        cost_events = entity.get("cost_events", [])
        if not cost_events:
            continue

        # Find the event with the highest to_age — that's the "last" cost event
        max_to_age = max(
            int(evt.get("to_age", 0)) for evt in cost_events
        )
        entity_start_age = entity.get("entity_age_at_start", 0)

        # The last year of kid costs is when entity age reaches max_to_age
        # That year in the projection: start_age + y = max_to_age => y = max_to_age - start_age
        last_cost_year_index = max_to_age - entity_start_age
        if last_cost_year_index < 0:
            continue

        independence_year = inp.current_year + last_cost_year_index + 1  # year AFTER last costs

        # Compute the kid monthly expense in the last year for impact estimation
        if 0 <= last_cost_year_index < len(timeline):
            last_cost_entry = timeline[last_cost_year_index]
            kid_monthly = _to_monthly(last_cost_entry.kid_expenses)
            if kid_monthly > 0:
                key_events.append(
                    {
                        "year": independence_year,
                        "event": f"{name} indépendant(e)",
                        "impact_monthly": str((-kid_monthly).quantize(Decimal("0.01"))),
                        "category": "kid_independence",
                    }
                )

    # ── Pet end-of-life ───────────────────────────────────────────
    for entity in inp.life_entities:
        if entity.get("entity_type") != "pet":
            continue
        name = entity.get("entity_name", "Animal")
        cost_events = entity.get("cost_events", [])
        if not cost_events:
            continue

        max_to_age = max(
            int(evt.get("to_age", 0)) for evt in cost_events
        )
        entity_start_age = entity.get("entity_age_at_start", 0)
        last_cost_year_index = max_to_age - entity_start_age
        if last_cost_year_index < 0:
            continue

        eol_year = inp.current_year + last_cost_year_index + 1

        if 0 <= last_cost_year_index < len(timeline):
            last_cost_entry = timeline[last_cost_year_index]
            pet_monthly = _to_monthly(last_cost_entry.pet_expenses)
            if pet_monthly > 0:
                key_events.append(
                    {
                        "year": eol_year,
                        "event": f"{name} (fin de vie estimée)",
                        "impact_monthly": str((-pet_monthly).quantize(Decimal("0.01"))),
                        "category": "pet_eol",
                    }
                )

    # ── Car replacement years (large one-time spikes) ──────────────
    CAR_REPLACEMENT_THRESHOLD = Decimal("5000")  # One-time events above 5k€
    for i, entry in enumerate(timeline):
        car_annual = entry.car_expenses
        if car_annual <= CAR_REPLACEMENT_THRESHOLD:
            # Check if there's a dramatic spike vs previous year
            if i > 0:
                prev_car = timeline[i - 1].car_expenses
                if car_annual - prev_car > CAR_REPLACEMENT_THRESHOLD:
                    extra = car_annual - prev_car
                    key_events.append(
                        {
                            "year": entry.year,
                            "event": "Remplacement véhicule prévu",
                            "impact_monthly": str(
                                _to_monthly(extra).quantize(Decimal("0.01"))
                            ),
                            "category": "car_replacement",
                        }
                    )
        else:
            # Already above threshold — this is a replacement year
            key_events.append(
                {
                    "year": entry.year,
                    "event": "Remplacement véhicule prévu",
                    "impact_monthly": str(
                        _to_monthly(car_annual).quantize(Decimal("0.01"))
                    ),
                    "category": "car_replacement",
                }
            )

    # Sort by year
    key_events.sort(key=lambda e: e["year"])

    # Limit to most important (no spam)
    return key_events[:20]


# ── Sensitivity analysis endpoint (TASK-6.7) ─────────────────────────────


@router.get("/sensitivity", response_model=SensitivityResponse)
async def get_sensitivity_analysis(
    scale: str = Query(
        default="moderate",
        description="Inflation scale: optimistic, moderate, or pessimistic",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run sensitivity analysis on the user's projection.

    Tests how changes to key financial levers affect the outcome:
      - Saving 200€/mois more
      - Spending 300€/mois less
      - Growing CA 2% faster
      - Working 2 more years
      - Redirecting 50% savings to PEA
      - Redirecting freed loan payments to savings

    Returns ranked parameters by impact on final wealth.

    Each lever is tested by re-running the full projection engine
    (~7 passes, <1 second total).
    """
    from app.calculations.sensitivity import run_sensitivity_analysis
    from app.calculations.sensitivity import SensitivityResult

    # Validate scale
    if scale not in INFLATION_SCALES:
        valid = ", ".join(INFLATION_SCALES.keys())
        raise HTTPException(
            status_code=422,
            detail=f"Échelle inconnue: {scale!r}. Valides: {valid}",
        )

    t_start = time.perf_counter()

    try:
        inp = await _assemble_input(str(current_user.id), scale, db)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to assemble projection input for sensitivity")
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la préparation des données",
        ) from exc

    try:
        results: list[SensitivityResult] = run_sensitivity_analysis(inp, scale)
    except Exception as exc:
        logger.exception("Sensitivity analysis failed")
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de l'analyse de sensibilité",
        ) from exc

    # Build base wealth and exhaustion
    base_timeline = project_timeline(inp)
    base_summary = compute_summary(base_timeline)
    base_wealth = base_summary.get("final_wealth", "0")
    base_exhaustion = base_summary.get("wealth_exhaustion_age")

    # Build response parameters
    params_out = [
        SensitivityParamOut(
            parameter=r.parameter,
            label=r.label,
            description=r.description,
            base_value_display=r.base_value_display,
            test_value_display=r.test_value_display,
            base_wealth=str(r.base_wealth),
            test_wealth=str(r.test_wealth),
            delta_wealth=str(r.delta_wealth),
            delta_pct=str(r.delta_pct),
            delta_exhaustion=r.delta_exhaustion,
            rank=r.rank,
        )
        for r in results
    ]

    # Generate narrative for top lever
    top_narrative = ""
    if results:
        top = results[0]
        top_narrative = (
            f"Le levier le plus puissant est « {top.label.lower()} ». "
            f"Cela ajouterait {top.delta_wealth:.0f}€ à votre patrimoine final "
            f"(+{top.delta_pct}%), soit plus que toute autre action individuelle."
        )

    elapsed_ms = (time.perf_counter() - t_start) * 1000
    logger.info(
        "Sensitivity analysis user=%s scale=%s params=%d elapsed=%.1fms",
        current_user.id,
        scale,
        len(results),
        elapsed_ms,
    )

    return SensitivityResponse(
        base_wealth_at_retirement=str(base_wealth),
        base_exhaustion_age=base_exhaustion,
        parameters=params_out,
        scale=scale,
        top_lever_narrative=top_narrative,
    )


# ── Goal solver endpoint (TASK-7.11) ────────────────────────────────────


@router.get("/goal-solver")
async def solve_goal_endpoint(
    target_monthly: float = Query(..., description="Target monthly income at retirement"),
    target_age: int = Query(..., description="Target age to reach the goal"),
    scale: str = Query(default="moderate"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Find what changes are needed to reach a target monthly income by a target age.

    Tests 5 levers independently via binary search:
      - Increase monthly savings
      - Reduce monthly expenses
      - Increase CA growth rate
      - Work longer (delay retirement)
      - Redirect savings to PEA (higher yield)

    Returns solutions ranked by feasibility (easy → extreme).

    Each solution includes the current value, required value, and change amount.
    Performance: ~100 projection passes, target < 3s.
    """
    from app.calculations.goal_solver import solve_goal

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
        logger.exception("Failed to assemble projection input for goal solver")
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la préparation des données",
        ) from exc

    target_monthly_dec = Decimal(str(target_monthly))
    inp.monthly_revenue_goal = target_monthly_dec

    try:
        solutions = solve_goal(inp, target_monthly_dec, target_age, scale)
    except Exception as exc:
        logger.exception("Goal solver failed")
        raise HTTPException(
            status_code=500,
            detail="Erreur lors du calcul des solutions",
        ) from exc

    return {
        "target_monthly": target_monthly,
        "target_age": target_age,
        "solutions": [
            {
                "lever": s.lever,
                "label": s.label,
                "description": s.description,
                "current_value": s.current_value,
                "required_value": s.required_value,
                "change_amount": s.change_amount,
                "feasibility": s.feasibility,
                "goal_year": s.goal_year,
                "goal_age": s.goal_age,
            }
            for s in solutions
        ],
        "has_solution": len(solutions) > 0,
    }


# ── Lifecycle alerts endpoint (TASK-6.9) ────────────────────────────────


@router.get("/alerts", response_model=LifecycleAlertsResponse)
async def get_lifecycle_alerts(
    scale: str = Query(
        default="moderate",
        description="Inflation scale: optimistic, moderate, or pessimistic",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return time-specific lifecycle alerts from the projection.

    Generates alerts for:
      - Loan terminations (with savings redirection estimate)
      - Kid independence milestones
      - Car replacement due within 2 years
      - Investment ceiling approaching
      - Retirement countdown (10, 5, 3, 1 years)
      - Pet end-of-life approaching
      - Expense peak year identification
    """
    from app.calculations.insights import generate_lifecycle_alerts

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
        logger.exception("Failed to assemble projection input for alerts")
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la préparation des données",
        ) from exc

    try:
        timeline = project_timeline(inp)
    except Exception as exc:
        logger.exception("Projection engine failed for alerts")
        raise HTTPException(
            status_code=500,
            detail="Erreur de calcul de la projection",
        ) from exc

    # Build inputs for alerts
    allocations_list = [
        {
            "vehicle_key": vk,
            "balance": float(alloc.get("balance", Decimal("0"))),
            "monthly": float(alloc.get("monthly", Decimal("0"))),
        }
        for vk, alloc in inp.allocations.items()
    ]

    loan_dicts = inp.loans  # Already list of dicts
    entity_dicts = inp.life_entities  # Already list of dicts

    profile_data = {
        "monthly_gross": float(inp.monthly_gross),
        "growth_rate": float(inp.growth_rate),
        "target_age": inp.target_age,
        "current_age": inp.current_age,
    }

    # ── HOTFIX-4: Missing conjoint career history alert ──────────────
    from app.models.career_period import CareerPeriod
    from app.calculations.insights import LifecycleAlert

    spouse_alert = None
    # Fetch spouse record (not in scope from _assemble_input)
    sp_row = await db.execute(
        select(Spouse).where(Spouse.user_id == str(current_user.id))
    )
    sp = sp_row.scalar_one_or_none()
    if sp is not None:
        sp_status = sp.status or ""
        is_salaried = sp_status in ("cdi", "fonctionnaire", "cdd")
        if is_salaried and sp.birth_date is not None:
            today = date.today()
            sp_age = today.year - sp.birth_date.year
            if 25 <= sp_age <= 62:
                # Check if any career periods exist for spouse
                from sqlalchemy import func as sa_func
                sp_cp_count_result = await db.execute(
                    select(sa_func.count(CareerPeriod.id)).where(
                        CareerPeriod.user_id == str(current_user.id),
                        CareerPeriod.is_active == True,
                        CareerPeriod.owner == "spouse",
                    )
                )
                sp_cp_count = sp_cp_count_result.scalar() or 0
                if sp_cp_count == 0:
                    spouse_alert = LifecycleAlert(
                        id="spouse_no_career",
                        alert_type="data_gap",
                        year=int(today.year),
                        age=int(inp.current_age),
                        severity="warning",
                        title=f"Retraite de {sp.first_name or 'votre conjoint(e)'} non estimée",
                        description=(
                            f"{sp.first_name or 'Votre conjoint(e)'} est enregistré(e) comme"
                            f" salarié(e) mais aucune période de carrière n'a été saisie."
                            f" Sa retraite n'est pas incluse dans la projection du foyer."
                            f" Ajoutez son parcours pour voir l'impact complet."
                        ),
                        action_label="Ajouter le parcours",
                        action_link="identite",
                    )

    alerts = generate_lifecycle_alerts(
        timeline=timeline,
        summary={},  # summary not needed for lifecycle alerts
        loans=loan_dicts,
        life_entities=entity_dicts,
        allocations=allocations_list,
        profile_data=profile_data,
    )

    alerts_out = [
        LifecycleAlertOut(
            id=a.id,
            alert_type=a.alert_type,
            year=a.year,
            age=a.age,
            severity=a.severity,
            title=a.title,
            description=a.description,
            impact_monthly=str(a.impact_monthly) if a.impact_monthly is not None else None,
            impact_wealth=str(a.impact_wealth) if a.impact_wealth is not None else None,
            action_label=a.action_label,
            action_link=a.action_link,
        )
        for a in alerts
    ]

    # HOTFIX-4: Prepend spouse career gap alert if present
    if spouse_alert is not None:
        alerts_out.insert(0, LifecycleAlertOut(
            id=spouse_alert.id,
            alert_type=spouse_alert.alert_type,
            year=spouse_alert.year,
            age=spouse_alert.age,
            severity=spouse_alert.severity,
            title=spouse_alert.title,
            description=spouse_alert.description,
            action_label=spouse_alert.action_label,
            action_link=spouse_alert.action_link,
        ))

    return LifecycleAlertsResponse(alerts=alerts_out, total=len(alerts_out))


# ── Year drill-down endpoint (TASK-6.10) ────────────────────────────────


@router.get("/year/{year}", response_model=YearDrillDownResponse)
async def get_year_drill_down(
    year: int,
    scale: str = Query(
        default="moderate",
        description="Inflation scale: optimistic, moderate, or pessimistic",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a complete breakdown for a single projection year.

    Includes every income source, expense line, life entity cost event,
    loan status, and investment contribution/return for that year.
    Also generates a natural-language explanation of the year's key drivers.
    """
    from app.schemas.projection import (
        DrillDownLifeEntityEvent,
        DrillDownLifeEntity,
        DrillDownIncome,
        DrillDownCharges,
        DrillDownExpenses,
        DrillDownLifeEntitiesTotal,
        DrillDownLoan,
        DrillDownInvestments,
        DrillDownSummary,
        YearDrillDownResponse,
    )

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
        logger.exception("Failed to assemble projection input for drill-down")
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la préparation des données",
        ) from exc

    try:
        timeline = project_timeline(inp)
    except Exception as exc:
        logger.exception("Projection engine failed for drill-down")
        raise HTTPException(
            status_code=500,
            detail="Erreur de calcul de la projection",
        ) from exc

    # Find the requested year
    idx = year - inp.current_year
    if idx < 0 or idx >= len(timeline):
        raise HTTPException(
            status_code=404,
            detail=f"Année {year} hors de la période de projection",
        )

    entry = timeline[idx]
    is_retirement = getattr(entry, "is_retirement", False)

    # ── Income breakdown ──────────────────────────────────────────────
    growth_pct = f"{float(inp.growth_rate) * 100:.1f}%"
    income = DrillDownIncome(
        gross_ca=str(entry.gross_annual),
        growth_rate_applied=growth_pct,
        caf=str(entry.caf_annual),
        cesu_credit=str(
            Decimal(str(inp.cesu_annual)) * Decimal("0.5")
            if not is_retirement else Decimal("0")
        ),
        charity_credit=str(
            Decimal(str(inp.charity_annual)) * Decimal("0.66")
            if not is_retirement else Decimal("0")
        ),
        project_income=str(entry.project_income),
        pension=str(entry.pension_annual),
        total=str(entry.total_income),
    )

    # ── Charges breakdown ─────────────────────────────────────────────
    charges = DrillDownCharges(
        ae_cotisations=str(entry.charges),
        ae_rate=str(entry.ae_rate * Decimal("100")) + "%",
        cfe=str(entry.cfe),
        total=str(entry.charges + entry.cfe),
    )

    # ── Expenses breakdown ────────────────────────────────────────────
    inflation_scale = INFLATION_SCALES.get(scale, {})
    inflation_rate = Decimal(str(inflation_scale.get("inflation", "0.02")))
    years_from_start = year - inp.current_year
    inflation_factor = (Decimal("1") + inflation_rate) ** max(0, years_from_start)
    base_m = entry.base_expenses / Decimal("12")
    expenses = DrillDownExpenses(
        base_total_monthly=str(base_m.quantize(Decimal("0.01"))),
        base_total_annual=str(entry.base_expenses),
        inflation_factor=f"{float(inflation_factor):.3f} ({float(inflation_rate) * 100:.1f}%/an × {years_from_start} ans)",
    )

    # ── Life entities breakdown ───────────────────────────────────────
    entities_out: list[DrillDownLifeEntity] = []
    kids_total = Decimal("0")
    pets_total = Decimal("0")
    cars_total = Decimal("0")
    tech_total = Decimal("0")

    for entity in inp.life_entities:
        etype = entity.get("entity_type", "")
        ename = entity.get("entity_name", "Entité")
        estate_age = entity.get("entity_age_at_start", 0)
        cost_events = entity.get("cost_events", [])
        entity_age_this_year = estate_age + idx

        active_events: list[DrillDownLifeEntityEvent] = []
        subtotal = Decimal("0")
        notes_parts = []

        for evt in cost_events:
            from_age = int(evt.get("from_age", 0))
            to_age = int(evt.get("to_age", 0))
            amount = Decimal(str(evt.get("amount", 0)))
            freq = evt.get("frequency", "annual")

            if from_age <= entity_age_this_year <= to_age:
                # Inflate cost
                inflated = amount * inflation_factor
                if freq == "monthly":
                    annual_val = inflated * Decimal("12")
                elif freq == "once":
                    annual_val = inflated
                else:  # annual
                    annual_val = inflated

                subtotal += annual_val
                active_events.append(
                    DrillDownLifeEntityEvent(
                        label=evt.get("label", ""),
                        amount=str(inflated.quantize(Decimal("0.01"))),
                        frequency=freq,
                        annual=str(annual_val.quantize(Decimal("0.01"))),
                    )
                )

        # Auto-generate note for notable ages
        if etype == "kid":
            if entity_age_this_year == 18:
                notes_parts.append("Année du permis et peut-être première voiture")
            elif entity_age_this_year == 22:
                notes_parts.append("Fin des études supérieures")
        elif etype == "pet" and entity_age_this_year >= 10:
            notes_parts.append("Soins renforcés (vieillesse)")
        elif etype == "car" and entity_age_this_year >= 8:
            notes_parts.append("Véhicule vieillissant — entretien accru")

        if active_events:
            entities_out.append(
                DrillDownLifeEntity(
                    name=ename,
                    type=etype,
                    age=entity_age_this_year,
                    events_active=active_events,
                    subtotal=str(subtotal.quantize(Decimal("0.01"))),
                    note=". ".join(notes_parts) if notes_parts else "",
                )
            )

        # Accumulate per-type totals
        if etype == "kid":
            kids_total += subtotal
        elif etype == "pet":
            pets_total += subtotal
        elif etype == "car":
            cars_total += subtotal
        elif etype == "tech":
            tech_total += subtotal

    life_entities_total = DrillDownLifeEntitiesTotal(
        kids=str(kids_total),
        pets=str(pets_total),
        cars=str(cars_total),
        tech=str(tech_total),
        total=str(kids_total + pets_total + cars_total + tech_total),
    )

    # ── Loans breakdown ────────────────────────────────────────────────
    loans_out: list[DrillDownLoan] = []
    loan_year_date = date(year, 1, 1)
    for loan in inp.loans:
        label = loan.get("label", "Crédit")
        monthly = Decimal(str(loan.get("monthly_payment", 0)))
        insurance = Decimal(str(loan.get("insurance_monthly", 0)))
        total_m = monthly + insurance

        end_date_str = loan.get("end_date")
        end_date = None
        if end_date_str:
            if isinstance(end_date_str, str):
                end_date = date.fromisoformat(end_date_str)
            else:
                end_date = end_date_str

        if end_date and end_date < loan_year_date:
            status = "ended"
            total_m = Decimal("0")
        elif end_date and end_date.year == year:
            status = "active"  # Last year
        else:
            status = "active"

        if total_m > Decimal("0") or status == "ended":
            loans_out.append(
                DrillDownLoan(
                    label=label,
                    monthly=str(total_m),
                    annual=str(total_m * Decimal("12")),
                    status=status,
                    ends=str(end_date) if end_date else None,
                )
            )

    # ── Investments breakdown ──────────────────────────────────────────
    contribs: dict[str, str] = {}
    rets: dict[str, str] = {}
    balances: dict[str, str] = {}
    i_notes: list[str] = []

    # Estimate per-vehicle contributions and returns from totals
    total_contributed = Decimal(str(entry.year_invested))
    total_returned = Decimal(str(entry.year_returns))
    total_balance = Decimal(str(entry.total_wealth))

    if inp.allocations:
        total_monthly = sum(
            alloc.get("monthly", Decimal("0")) for alloc in inp.allocations.values()
        )
        if total_monthly > Decimal("0"):
            for vk, alloc in inp.allocations.items():
                monthly = alloc.get("monthly", Decimal("0"))
                share = monthly / total_monthly if total_monthly > Decimal("0") else Decimal("0")
                contribs[vk] = str((total_contributed * share).quantize(Decimal("0.01")))
                rets[vk] = str((total_returned * share).quantize(Decimal("0.01")))

                # Estimate balance from existing + cumulative
                existing = alloc.get("balance", Decimal("0"))
                # Simple projection
                bal = existing + (monthly * Decimal("12") * Decimal(str(max(1, idx + 1)))) * Decimal("1.05")
                balances[vk] = str(bal.quantize(Decimal("0.01")))

    from app.calculations.vehicles import VEHICLE_SPECS
    for vk, alloc in inp.allocations.items():
        spec = VEHICLE_SPECS.get(vk, {})
        ceiling = Decimal(str(spec.get("ceiling", 0)))
        if ceiling > Decimal("0") and balances.get(vk):
            bal = Decimal(balances[vk])
            if bal >= ceiling * Decimal("0.9"):
                i_notes.append(f"{spec.get('label', vk)} proche du plafond")

    investments = DrillDownInvestments(
        contributions=contribs,
        returns=rets,
        balances=balances,
        notes=i_notes,
    )

    # ── Summary with auto-generated explanation ───────────────────────
    net_val = entry.total_income - entry.total_outgoing
    net_status = "surplus" if net_val >= Decimal("0") else "deficit"

    # Generate explanation
    drivers = []
    if kids_total > Decimal("5000"):
        drivers.append(f"{len([e for e in inp.life_entities if e.get('entity_type') == 'kid'])} enfants à charge")
    if getattr(entry, "kid_expenses", Decimal("0")) > Decimal("10000"):
        drivers.append("pic de dépenses enfants")
    if any(l.status == "ended" for l in loans_out if hasattr(l, "status")):
        drivers.append("crédit terminé")
    car_spike = getattr(entry, "car_expenses", Decimal("0"))
    if car_spike > Decimal("5000"):
        drivers.append("remplacement véhicule")
    if getattr(entry, "project_income", Decimal("0")) > Decimal("0"):
        drivers.append("revenus de projet")

    if not drivers:
        drivers.append("année normale")

    exp = f"Année {'chargée' if net_val < Decimal('0') else 'normale'}: {', '.join(drivers[:3])}."

    summary = DrillDownSummary(
        total_income=str(entry.total_income),
        total_outgoing=str(entry.total_outgoing),
        net=str(net_val),
        net_status=net_status,
        explanation=exp,
    )

    return YearDrillDownResponse(
        year=entry.year,
        age=entry.age,
        phase="post-retirement" if is_retirement else "accumulation",
        income=income,
        charges=charges,
        expenses=expenses,
        life_entities=entities_out,
        life_entities_total=life_entities_total,
        loans=loans_out,
        investments=investments,
        summary=summary,
    )


# ── Action Plan (TASK-7.17) ──────────────────────────────────────────────────


@router.get("/action-plan")
async def get_action_plan(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate this month's prioritized action plan.

    Returns a list of concrete, specific actions the user should take
    this month to improve their financial trajectory. Each action includes
    a specific € amount where applicable and a navigation link.

    Capped at 10 actions, sorted by priority (1=do now, 2=this week, 3=this month).
    """
    from app.calculations.action_plan import generate_action_plan
    from app.models.income_source import IncomeSource

    # Load profile
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == str(current_user.id))
    )
    profile = profile_result.scalar_one_or_none()

    profile_context = {
        "cesu_annual": str(profile.cesu_annual or Decimal("0")) if profile else "0",
        "status": profile.status if profile else "ae",
    }

    # Load investments
    allocs_result = await db.execute(
        select(InvestmentAllocation).where(
            InvestmentAllocation.user_id == str(current_user.id)
        )
    )
    investments: dict[str, dict] = {}
    for alloc in allocs_result.scalars().all():
        investments[alloc.vehicle_key] = {
            "existing_balance": str(alloc.existing_balance or Decimal("0")),
            "monthly_contribution": str(alloc.monthly_contribution or Decimal("0")),
        }

    # Load active income sources
    sources_result = await db.execute(
        select(IncomeSource).where(
            IncomeSource.user_id == str(current_user.id),
            IncomeSource.is_active == True,
        )
    )
    income_sources_raw: list[dict] = []
    for s in sources_result.scalars().all():
        income_sources_raw.append({
            "id": str(s.id),
            "label": s.label,
            "amount": str(s.amount),
            "frequency": s.frequency,
            "end_date": s.end_date.isoformat() if s.end_date else None,
            "confidence": s.confidence or "high",
            "is_active": s.is_active,
        })

    # Load loans
    loans_result = await db.execute(
        select(Loan).where(
            Loan.user_id == str(current_user.id),
            Loan.is_active == True,
        )
    )
    loans_raw: list[dict] = []
    for loan in loans_result.scalars().all():
        loans_raw.append({
            "id": str(loan.id),
            "label": loan.label,
            "monthly_payment": str(loan.monthly_payment or Decimal("0")),
            "end_date": loan.end_date.isoformat() if loan.end_date else None,
        })

    actions = generate_action_plan(
        profile=profile_context,
        investments=investments,
        income_sources=income_sources_raw,
        loans=loans_raw,
        advice=[],
    )

    return {
        "month": date.today().strftime("%B %Y"),
        "actions": [
            {
                "id": a.id,
                "priority": a.priority,
                "category": a.category,
                "title": a.title,
                "detail": a.detail,
                "amount": str(a.amount) if a.amount else None,
                "link_to": a.link_to,
            }
            for a in actions
        ],
        "count": len(actions),
    }


# ── Prescriptive Advice (TASK-7.15) ───────────────────────────────────────────


@router.get("/advice")
async def get_advice(
    scale: str = Query(default="moderate"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate prescriptive advice based on the user's projection and financial data.

    Returns a list of actionable advice items with priority, impact estimates,
    and navigation links. Rule-based — no LLM.
    """
    from app.calculations.advice import generate_advice

    # Assemble projection input and run engine
    inp = await _assemble_input(str(current_user.id), scale, db)
    timeline = project_timeline(inp)

    # Get expense events (reuse existing helper from TASK-6.6)
    key_events = _detect_expense_events(timeline, inp)

    # Build investments dict from allocations
    investments: dict[str, dict] = {}
    allocs_result = await db.execute(
        select(InvestmentAllocation).where(
            InvestmentAllocation.user_id == str(current_user.id)
        )
    )
    for alloc in allocs_result.scalars().all():
        investments[alloc.vehicle_key] = {
            "existing_balance": str(alloc.existing_balance),
            "monthly_contribution": str(alloc.monthly_contribution),
        }

    # Check spouse status
    spouse_row = await db.execute(
        select(Spouse).where(Spouse.user_id == str(current_user.id))
    )
    spouse_data = spouse_row.scalar_one_or_none()

    # Get profile for status
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == str(current_user.id))
    )
    profile = profile_result.scalar_one_or_none()

    profile_context = {
        "status": profile.status if profile else "ae",
        "target_retirement_age": inp.target_age if inp.target_age else 70,
        "has_spouse": spouse_data is not None,
        "spouse_is_cc": spouse_data.is_conjointe_collaboratrice if spouse_data else False,
    }

    advice_list = generate_advice(
        timeline,
        [],
        [{"category": e.category, "event": e.event, "impact_monthly": e.impact_monthly, "year": e.year}
         for e in key_events],
        profile_context,
        investments,
    )

    return {
        "advice": [
            {
                "id": a.id,
                "category": a.category,
                "priority": a.priority,
                "title": a.title,
                "description": a.description,
                "impact_text": a.impact_text,
                "action_text": a.action_text,
                "trigger_year": a.trigger_year,
                "link_to": a.link_to,
            }
            for a in advice_list
        ],
        "count": len(advice_list),
    }
