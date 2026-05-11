"""
Spouse router — CRUD + CC estimation for TASK-7.4.

A 1:1 relationship per user. Endpoints:
  POST   /api/spouse            — create (409 if one already exists)
  GET    /api/spouse            — get (404 if none exists)
  PUT    /api/spouse            — update (partial)
  DELETE /api/spouse            — delete
  GET    /api/spouse/cc-estimate — estimated CC cotisations for all 4 options
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.spouse import Spouse
from app.models.user import User
from app.schemas.spouse import (
    SpouseCreate,
    SpouseRead,
    SpouseUpdate,
    CCEstimateResponse,
    CCOptionEstimate,
    PLAFOND_SS_ANNUEL,
    CC_RATE,
)

router = APIRouter(prefix="/spouse", tags=["spouse"])


# ── Helpers ───────────────────────────────────────────────────────────────────


def _compute_age(birth_date_val: date | None) -> int | None:
    """Compute current age from birth date."""
    if birth_date_val is None:
        return None
    today = date.today()
    age = today.year - birth_date_val.year
    if (today.month, today.day) < (birth_date_val.month, birth_date_val.day):
        age -= 1
    return age


def _spouse_to_read(spouse: Spouse) -> SpouseRead:
    """Convert a Spouse ORM object to a SpouseRead response."""
    return SpouseRead(
        id=spouse.id,
        user_id=spouse.user_id,
        first_name=spouse.first_name,
        birth_date=spouse.birth_date,
        relationship_type=spouse.relationship_type,
        status=spouse.status,
        ae_activity_type=spouse.ae_activity_type,
        versement_liberatoire=spouse.versement_liberatoire,
        monthly_gross_income=spouse.monthly_gross_income,
        growth_preset=spouse.growth_preset,
        growth_rate_custom=spouse.growth_rate_custom,
        is_conjointe_collaboratrice=spouse.is_conjointe_collaboratrice,
        cc_cotisation_option=spouse.cc_cotisation_option,
        current_age=_compute_age(spouse.birth_date),
        created_at=spouse.created_at,
        updated_at=spouse.updated_at,
    )


# ── CRUD Endpoints ────────────────────────────────────────────────────────────


@router.post("", response_model=SpouseRead, status_code=201)
async def create_spouse(
    data: SpouseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a spouse for the authenticated user.

    Returns 409 if a spouse already exists (max 1 per user).
    """
    # Check for existing spouse
    existing = await db.execute(
        select(Spouse).where(Spouse.user_id == current_user.id)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409, detail="Un conjoint existe déjà pour ce compte"
        )

    spouse = Spouse(
        user_id=current_user.id,
        first_name=data.first_name,
        birth_date=data.birth_date,
        relationship_type=data.relationship_type,
        status=data.status,
        ae_activity_type=data.ae_activity_type,
        versement_liberatoire=data.versement_liberatoire,
        monthly_gross_income=data.monthly_gross_income,
        growth_preset=data.growth_preset,
        growth_rate_custom=data.growth_rate_custom,
        is_conjointe_collaboratrice=data.is_conjointe_collaboratrice,
        cc_cotisation_option=data.cc_cotisation_option,
    )

    db.add(spouse)
    await db.commit()
    await db.refresh(spouse)

    return _spouse_to_read(spouse)


@router.get("", response_model=SpouseRead)
async def get_spouse(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the authenticated user's spouse.

    Returns 404 if no spouse exists.
    """
    result = await db.execute(
        select(Spouse).where(Spouse.user_id == current_user.id)
    )
    spouse = result.scalar_one_or_none()

    if spouse is None:
        raise HTTPException(status_code=404, detail="Aucun conjoint trouvé")

    return _spouse_to_read(spouse)


@router.put("", response_model=SpouseRead)
async def update_spouse(
    data: SpouseUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the authenticated user's spouse (partial update).

    Returns 404 if no spouse exists.
    """
    result = await db.execute(
        select(Spouse).where(Spouse.user_id == current_user.id)
    )
    spouse = result.scalar_one_or_none()

    if spouse is None:
        raise HTTPException(status_code=404, detail="Aucun conjoint trouvé")

    update_data = data.model_dump(exclude_unset=True)

    for field in [
        "first_name", "birth_date", "relationship_type", "status",
        "ae_activity_type", "versement_liberatoire", "monthly_gross_income",
        "growth_preset", "growth_rate_custom",
        "is_conjointe_collaboratrice", "cc_cotisation_option",
    ]:
        if field in update_data and update_data[field] is not None:
            setattr(spouse, field, update_data[field])

    await db.commit()
    await db.refresh(spouse)

    return _spouse_to_read(spouse)


@router.delete("", status_code=204)
async def delete_spouse(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete the authenticated user's spouse.

    Returns 404 if no spouse exists.
    """
    result = await db.execute(
        select(Spouse).where(Spouse.user_id == current_user.id)
    )
    spouse = result.scalar_one_or_none()

    if spouse is None:
        raise HTTPException(status_code=404, detail="Aucun conjoint trouvé")

    await db.delete(spouse)
    await db.commit()

    return None


# ── CC Estimate Endpoint ─────────────────────────────────────────────────────


@router.get("/cc-estimate", response_model=CCEstimateResponse)
async def get_cc_estimate(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Estimate annual CC cotisations for all 4 CC options.

    CC cotisation rate is ~28% applied to the chosen base:
      - tiers_plafond: PASS / 3
      - moitie_plafond: PASS / 2
      - tiers_revenu: user_ca_annual / 3
      - moitie_revenu: user_ca_annual / 2

    User's annual CA is derived from profile.monthly_gross_ca * 12.
    Requires the user to be logged in. Does NOT require a spouse to exist.
    """
    from app.models.profile import UserProfile

    # Get user's profile for CA
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = profile_result.scalar_one_or_none()

    user_ca_annual = Decimal("0")
    if profile is not None and profile.monthly_gross_ca is not None:
        user_ca_annual = profile.monthly_gross_ca * Decimal("12")

    bases = {
        "tiers_plafond": PLAFOND_SS_ANNUEL / Decimal("3"),
        "moitie_plafond": PLAFOND_SS_ANNUEL / Decimal("2"),
        "tiers_revenu": user_ca_annual / Decimal("3"),
        "moitie_revenu": user_ca_annual / Decimal("2"),
    }

    def _estimate(option_key: str) -> CCOptionEstimate:
        base = bases[option_key]
        cotisation = base * CC_RATE
        return CCOptionEstimate(
            base_annuelle=str(base.quantize(Decimal("0.01"))),
            cotisation_annuelle=str(cotisation.quantize(Decimal("0.01"))),
            cotisation_mensuelle=str((cotisation / Decimal("12")).quantize(Decimal("0.01"))),
        )

    return CCEstimateResponse(
        tiers_plafond=_estimate("tiers_plafond"),
        moitie_plafond=_estimate("moitie_plafond"),
        tiers_revenu=_estimate("tiers_revenu"),
        moitie_revenu=_estimate("moitie_revenu"),
    )