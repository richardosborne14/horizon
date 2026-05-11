"""
Profile API router — GET/PUT for the user's financial profile.

Auto-creates a profile on first GET (upsert pattern).
Partial updates via PUT — only send changed fields.
Includes expense sub-endpoints and a summary endpoint for the sidebar.
"""

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.profile import UserProfile
from app.models.user import User
from app.schemas.profile import (
    ProfileRead,
    ProfileWrite,
    MonthlyExpenses,
    EXPENSE_CATEGORIES,
    EXPENSE_LABELS,
)
from app.calculations.expenses import preview_inflation
from app.calculations.ae_rates import get_ae_rate
from app.calculations.constants import INFLATION_SCALES, get_growth_rate
from app.calculations.caf import get_caf_timeline

router = APIRouter(prefix="/profile", tags=["profile"])


async def _get_or_create_profile(
    user_id: UUID, db: AsyncSession
) -> UserProfile:
    """Get the user's profile, creating one with defaults if it doesn't exist."""
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if profile is None:
        profile = UserProfile(user_id=user_id)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)

    return profile


def _compute_age(birth_date_val: Optional[date]) -> Optional[int]:
    """Derive current age from birth date. Returns None if birth_date is null."""
    if birth_date_val is None:
        return None
    today = date.today()
    age = today.year - birth_date_val.year
    if (today.month, today.day) < (
        birth_date_val.month,
        birth_date_val.day,
    ):
        age -= 1
    return age


def _serialise(val) -> Optional[str]:
    """Convert a value to its string representation, handling None and Decimal."""
    if val is None:
        return None
    return str(val)


def _profile_to_read(profile: UserProfile) -> dict:
    """Convert a UserProfile ORM object to a ProfileRead-compatible dict."""
    age = _compute_age(profile.birth_date)
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "birth_date": profile.birth_date,
        "current_age": age,
        "target_retirement_age": profile.target_retirement_age,
        "tax_parts": str(profile.tax_parts),
        "status": profile.status,
        "ae_activity_type": profile.ae_activity_type,
        "has_versement_liberatoire": profile.has_versement_liberatoire,
        "monthly_gross_ca": _serialise(profile.monthly_gross_ca),
        "growth_preset": profile.growth_preset,
        "growth_rate_custom": _serialise(profile.growth_rate_custom),
        "cesu_annual": str(profile.cesu_annual),
        "charity_annual": str(profile.charity_annual),
        "caf_override_monthly": _serialise(profile.caf_override_monthly),
        "monthly_expenses": profile.monthly_expenses or {},
        "custom_expenses": profile.custom_expenses or [],
        "monthly_revenue_goal": _serialise(profile.monthly_revenue_goal),
        "world_scale": profile.world_scale,
        "status_change_enabled": profile.status_change_enabled,
        "status_change_year": profile.status_change_year,
        "status_change_target": profile.status_change_target,
        "status_change_savings": _serialise(profile.status_change_savings),
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


# ── Profile CRUD ────────────────────────────────────────────────────────────

@router.get("", response_model=ProfileRead)
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the authenticated user's profile.

    Creates an empty profile with defaults if one doesn't exist yet.
    """
    profile = await _get_or_create_profile(current_user.id, db)
    return _profile_to_read(profile)


@router.put("", response_model=ProfileRead)
async def update_profile(
    data: ProfileWrite,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the authenticated user's profile (partial update).

    Only send the fields you want to change. Fields not included
    in the request body are left unchanged.
    """
    profile = await _get_or_create_profile(current_user.id, db)

    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)

    return _profile_to_read(profile)


# ── Expenses sub-endpoints ────────────────────────────────────────────────────

@router.get("/expenses")
async def get_expenses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the user's monthly expenses with category labels and total."""
    profile = await _get_or_create_profile(current_user.id, db)
    stored = profile.monthly_expenses or {}

    expense_vals = {}
    for cat in EXPENSE_CATEGORIES:
        expense_vals[cat] = str(Decimal(str(stored.get(cat, 0))))

    base_total = sum(Decimal(v) for v in expense_vals.values())
    custom_expenses = profile.custom_expenses or []
    custom_total = sum(
        Decimal(str(ce.get("amount", "0"))) for ce in custom_expenses
    )
    total = base_total + custom_total

    return {
        "expenses": expense_vals,
        "custom_expenses": custom_expenses,
        "labels": EXPENSE_LABELS,
        "total": str(total),
    }


@router.put("/expenses")
async def update_expenses(
    data: MonthlyExpenses,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the 12 standard monthly_expenses JSONB categories.

    Custom expenses are saved separately via PUT /api/profile
    with {"custom_expenses": [...]}. This endpoint only handles
    the 12 standard categories defined in EXPENSE_CATEGORIES.
    """
    profile = await _get_or_create_profile(current_user.id, db)

    expenses_dict = {
        field: str(getattr(data, field))
        for field in EXPENSE_CATEGORIES
    }
    profile.monthly_expenses = expenses_dict

    await db.commit()
    await db.refresh(profile)

    base_total = sum(Decimal(v) for v in expenses_dict.values())
    custom_list = profile.custom_expenses or []
    custom_total = sum(
        Decimal(str(ce.get("amount", "0"))) for ce in custom_list
    )
    total = base_total + custom_total

    return {
        "expenses": expenses_dict,
        "custom_expenses": custom_list,
        "labels": EXPENSE_LABELS,
        "total": str(total),
    }


@router.get("/expenses/inflation-preview")
async def get_inflation_preview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return an inflation preview grid for the user's current expenses.

    3 scales (optimistic / moderate / pessimistic) × 4 horizons
    (+5, +10, +20, +30 years). Returns inflated monthly totals.
    """
    profile = await _get_or_create_profile(current_user.id, db)
    stored = profile.monthly_expenses or {}

    monthly_total = sum(
        Decimal(str(stored.get(cat, 0)))
        for cat in EXPENSE_CATEGORIES
    )

    horizons = [5, 10, 20, 30]
    preview = preview_inflation(monthly_total, INFLATION_SCALES, horizons)

    return {"preview": preview, "current_monthly_total": str(monthly_total)}


# ── Summary endpoint (TASK 1.8) ───────────────────────────────────────────────

@router.get("/summary")
async def get_profile_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a compact summary of the user's profile for the sidebar.

    kid_count, monthly_savings_total, and investment_project_count
    return 0 until Sprint 2/3 models are created. The endpoint queries
    gracefully — try/except guards against missing tables.
    """
    profile = await _get_or_create_profile(current_user.id, db)

    age = _compute_age(profile.birth_date)

    kid_count = 0
    savings_total = Decimal("0")
    project_count = 0

    # Gracefully query Sprint 2/3 tables if they exist
    try:
        from app.models.life_entity import LifeEntity
        result = await db.execute(
            select(func.count()).where(
                LifeEntity.user_id == current_user.id,
                LifeEntity.entity_type == "kid",
                LifeEntity.is_active == True,
            )
        )
        kid_count = result.scalar() or 0
    except Exception:
        pass

    try:
        from app.models.investment import InvestmentAllocation
        result = await db.execute(
            select(func.coalesce(func.sum(InvestmentAllocation.monthly_contribution), 0)).where(
                InvestmentAllocation.user_id == current_user.id,
            )
        )
        savings_total = result.scalar() or Decimal("0")
    except Exception:
        pass

    try:
        from app.models.project import Project
        result = await db.execute(
            select(func.count()).where(
                Project.user_id == current_user.id,
                Project.project_type == "invest",
                Project.is_active == True,
            )
        )
        project_count = result.scalar() or 0
    except Exception:
        pass

    # Completeness flags for sidebar dots
    completeness = {
        "identity": profile.birth_date is not None,
        "revenue": profile.monthly_gross_ca is not None and profile.monthly_gross_ca > Decimal("0"),
        "expenses": bool(profile.monthly_expenses) and sum(
            Decimal(str(v)) for v in (profile.monthly_expenses or {}).values()
        ) > Decimal("0"),
        "life": kid_count > 0,
        "savings": savings_total > Decimal("0"),
        "projects": project_count > 0,
        "runway": profile.birth_date is not None and profile.monthly_gross_ca is not None,
    }

    return {
        "monthly_gross_ca": _serialise(profile.monthly_gross_ca) or "0",
        "current_age": age,
        "target_retirement_age": profile.target_retirement_age,
        "kid_count": kid_count,
        "monthly_savings_total": str(savings_total),
        "investment_project_count": project_count,
        "completeness": completeness,
    }


# ── CAF Estimate endpoint (TASK 2.4) ──────────────────────────────────────────

@router.get("/caf-estimate")
async def get_caf_estimate(
    from_year: int = 2026,
    to_year: int = 2056,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a CAF timeline for the user's kids.
    
    Estimates allocations familiales for each year based on:
    - Number of qualifying children (under 20) from life_entities
    - Annual household income (estimated from monthly_gross_ca)
    
    If profile.caf_override_monthly is set, that value is used instead
    for years where it applies.
    """
    profile = await _get_or_create_profile(current_user.id, db)
    
    # Get kids' birth dates from life_entities
    kids_birth_dates = []
    try:
        from app.models.life_entity import LifeEntity
        result = await db.execute(
            select(LifeEntity).where(
                LifeEntity.user_id == current_user.id,
                LifeEntity.entity_type == "kid",
                LifeEntity.is_active == True,
            )
        )
        kids = result.scalars().all()
        kids_birth_dates = [k.reference_date for k in kids]
    except Exception:
        pass

    # Estimate annual household income from monthly_gross_ca
    monthly_ca = profile.monthly_gross_ca or Decimal("0")
    annual_income = monthly_ca * Decimal("12")

    timeline = get_caf_timeline(
        kids_birth_dates=kids_birth_dates,
        from_year=from_year,
        to_year=to_year,
        annual_income=annual_income,
    )

    return {
        "timeline": timeline,
        "caf_override_monthly": _serialise(profile.caf_override_monthly),
        "kid_count": len(kids_birth_dates),
    }


# ── Waterfall endpoint (TASK-6.8) ─────────────────────────────────────────


@router.get("/waterfall", response_model=None)
async def get_waterfall(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a disposable income waterfall for the current year.

    Shows the flow from gross CA → charges → net → expenses → life costs
    → income additions → disposable → savings → surplus/deficit.

    Uses projection year 0 data (current year) and the life entities
    to estimate the full monthly picture.
    """
    from app.calculations.projection import project_timeline
    from app.calculations.constants import INFLATION_SCALES
    from app.schemas.profile import WaterfallMonthly, WaterfallAnnual, WaterfallResponse
    from app.routers.projection import _assemble_input

    scale = "moderate"

    try:
        inp = await _assemble_input(str(current_user.id), scale, db)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la préparation des données",
        ) from exc

    try:
        timeline = project_timeline(inp)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Erreur de calcul de la projection",
        ) from exc

    if not timeline:
        raise HTTPException(status_code=500, detail="Projection vide")

    entry = timeline[0]  # Year 0 = current year

    # ── Monthly breakdown ────────────────────────────────────────────
    def _m(annual_val) -> Decimal:
        """Convert annual to monthly."""
        d = Decimal(str(annual_val))
        return (d / Decimal("12")).quantize(Decimal("0.01"))

    gross_ca_m = _m(entry.gross_annual)
    charges_m = _m(entry.charges)
    cfe_m = _m(entry.cfe)
    net_charges_m = gross_ca_m - charges_m - cfe_m
    base_exp_m = _m(entry.base_expenses)
    loan_m = _m(getattr(entry, "loan_expenses", Decimal("0")))
    kid_m = _m(entry.kid_expenses)
    pet_m = _m(entry.pet_expenses)
    car_m = _m(entry.car_expenses)
    tech_m = _m(entry.tech_expenses)
    rec_m = _m(entry.recurring_expenses)
    caf_m = _m(entry.caf_annual)
    tax_m = _m(entry.tax_credits)

    total_expenses_m = base_exp_m + loan_m + kid_m + pet_m + car_m + tech_m + rec_m
    disposable_m = net_charges_m - total_expenses_m + caf_m + tax_m

    # Savings planned from allocations
    savings_m = Decimal("0")
    for alloc in inp.allocations.values():
        savings_m += alloc.get("monthly", Decimal("0"))

    surplus_deficit_m = disposable_m - savings_m

    monthly = WaterfallMonthly(
        gross_ca=str(gross_ca_m),
        charges=str(charges_m),
        cfe_monthly=str(cfe_m),
        net_after_charges=str(net_charges_m),
        base_expenses=str(base_exp_m),
        loan_payments=str(loan_m),
        kid_costs=str(kid_m),
        pet_costs=str(pet_m),
        car_costs=str(car_m),
        tech_costs=str(tech_m),
        recurring_costs=str(rec_m),
        caf_income=str(caf_m),
        tax_credits=str(tax_m),
        disposable=str(disposable_m),
        savings_planned=str(savings_m),
        monthly_surplus_deficit=str(surplus_deficit_m),
    )

    # ── Annual breakdown ─────────────────────────────────────────────
    net_charges_a = entry.gross_annual - entry.charges - entry.cfe
    total_expenses_a = (
        entry.base_expenses
        + getattr(entry, "loan_expenses", Decimal("0"))
        + entry.kid_expenses
        + entry.pet_expenses
        + entry.car_expenses
        + entry.tech_expenses
        + entry.recurring_expenses
    )
    total_life_costs_a = (
        entry.kid_expenses
        + entry.pet_expenses
        + entry.car_expenses
        + entry.tech_expenses
    )
    income_additions_a = entry.caf_annual + entry.tax_credits
    disposable_a = net_charges_a - total_expenses_a + income_additions_a
    savings_a = savings_m * Decimal("12")
    surplus_deficit_a = disposable_a - savings_a

    annual = WaterfallAnnual(
        gross_ca=str(entry.gross_annual),
        charges=str(entry.charges),
        cfe=str(entry.cfe),
        net_after_charges=str(net_charges_a),
        total_expenses=str(total_expenses_a),
        total_life_costs=str(total_life_costs_a),
        total_income_additions=str(income_additions_a),
        disposable=str(disposable_a),
        savings_planned=str(savings_a),
        annual_surplus_deficit=str(surplus_deficit_a),
    )

    # ── Status ───────────────────────────────────────────────────────
    if surplus_deficit_m > Decimal("10"):
        status = "surplus"
        note = ""
    elif surplus_deficit_m < Decimal("-10"):
        status = "deficit"
        note = (
            f"Vos dépenses dépassent vos revenus de {abs(surplus_deficit_m):.0f}€/mois "
            f"avant épargne. Assurez-vous d'avoir des réserves pour couvrir ce déficit."
        )
    else:
        status = "breakeven"
        note = "Votre budget est à l'équilibre. Pas de marge pour l'imprévu."

    return WaterfallResponse(
        year=entry.year,
        age=entry.age,
        monthly=monthly,
        annual=annual,
        status=status,
        deficit_note=note,
    )
