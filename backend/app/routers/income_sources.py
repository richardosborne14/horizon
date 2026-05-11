"""
Income Sources router — CRUD + summary for TASK-7.5.

Replaces the single monthly_gross_ca field with tracked revenue streams.
Each source belongs to an earner (user or spouse), has a type, frequency,
duration, confidence level, and optional growth rate.

Endpoints:
  GET    /api/income-sources          — list all (opt filter ?earner=user|spouse)
  GET    /api/income-sources/summary  — aggregated by earner
  POST   /api/income-sources          — create
  PUT    /api/income-sources/{id}     — update (partial)
  DELETE /api/income-sources/{id}     — delete (soft, sets is_active=False)

Auto-migration: On first GET, if user has no sources but profile.monthly_gross_ca > 0,
auto-creates one "Activité principale" source.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.income_source import IncomeSource
from app.models.profile import UserProfile
from app.models.user import User
from app.schemas.income_source import (
    IncomeSourceCreate,
    IncomeSourceRead,
    IncomeSourceUpdate,
    IncomeSourceSummaryResponse,
    EarnersSummary,
)

router = APIRouter(prefix="/income-sources", tags=["income_sources"])


# ── Helpers ───────────────────────────────────────────────────────────────────


def _source_to_read(source: IncomeSource) -> IncomeSourceRead:
    """Convert an IncomeSource ORM object to an IncomeSourceRead response.

    Args:
        source: The ORM object.

    Returns:
        A populated IncomeSourceRead.
    """
    return IncomeSourceRead(
        id=source.id,
        user_id=source.user_id,
        earner=source.earner,
        label=source.label,
        source_type=source.source_type,
        amount=source.amount,
        frequency=source.frequency,
        start_date=source.start_date,
        end_date=source.end_date,
        confidence=source.confidence,
        annual_growth_rate=source.annual_growth_rate,
        is_ae_revenue=source.is_ae_revenue,
        is_active=source.is_active,
        sort_order=source.sort_order,
        notes=source.notes,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


def _source_is_current(source: IncomeSource, ref_date: Optional[date] = None) -> bool:
    """Check if a source is currently active.

    A source is 'current' if:
      - is_active is True
      - start_date is None or ≤ ref_date
      - end_date is None or > ref_date

    Args:
        source: The income source to check.
        ref_date: Reference date (defaults to today).

    Returns:
        True if the source is currently active.
    """
    if not source.is_active:
        return False
    today = ref_date or date.today()
    if source.start_date is not None and source.start_date > today:
        return False
    if source.end_date is not None and source.end_date <= today:
        return False
    return True


async def sync_profile_ca(user_id: UUID, db: AsyncSession) -> None:
    """Recompute profile.monthly_gross_ca from active user-earner AE sources.

    Sums all active monthly+annual sources where earner='user'
    and is_ae_revenue=True. Annual sources are divided by 12.
    One-time sources are excluded.

    Call this after every create/update/delete of an income source to keep
    backward compatibility with the projection engine.

    Args:
        user_id: The user's UUID.
        db: Async database session.
    """
    from sqlalchemy import select, func, or_

    # Sum monthly sources
    monthly_result = await db.execute(
        select(func.coalesce(func.sum(IncomeSource.amount), Decimal("0")))
        .where(IncomeSource.user_id == user_id)
        .where(IncomeSource.earner == "user")
        .where(IncomeSource.is_ae_revenue == True)
        .where(IncomeSource.is_active == True)
        .where(IncomeSource.frequency == "monthly")
        .where(
            or_(
                IncomeSource.start_date == None,
                IncomeSource.start_date <= func.current_date(),
            )
        )
        .where(
            or_(
                IncomeSource.end_date == None,
                IncomeSource.end_date > func.current_date(),
            )
        )
    )
    monthly_total = monthly_result.scalar() or Decimal("0")

    # Sum annual sources (divide by 12)
    annual_result = await db.execute(
        select(func.coalesce(func.sum(IncomeSource.amount), Decimal("0")))
        .where(IncomeSource.user_id == user_id)
        .where(IncomeSource.earner == "user")
        .where(IncomeSource.is_ae_revenue == True)
        .where(IncomeSource.is_active == True)
        .where(IncomeSource.frequency == "annual")
        .where(
            or_(
                IncomeSource.start_date == None,
                IncomeSource.start_date <= func.current_date(),
            )
        )
        .where(
            or_(
                IncomeSource.end_date == None,
                IncomeSource.end_date > func.current_date(),
            )
        )
    )
    annual_total = annual_result.scalar() or Decimal("0")
    monthly_from_annual = annual_total / Decimal("12")

    total = (monthly_total + monthly_from_annual).quantize(Decimal("0.01"))

    # Update profile
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = profile_result.scalar_one_or_none()
    if profile is not None:
        profile.monthly_gross_ca = total
        await db.commit()


async def _auto_create_from_ca(
    user_id: UUID, db: AsyncSession
) -> Optional[IncomeSource]:
    """Auto-create an income source from existing profile.monthly_gross_ca.

    Called when the user has no income sources but a non-zero CA on their profile.
    Creates one "Activité principale" source with user's monthly CA.

    Args:
        user_id: The user's UUID.
        db: Async database session.

    Returns:
        The newly created IncomeSource, or None.
    """
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = profile_result.scalar_one_or_none()

    if profile is None:
        return None

    ca = profile.monthly_gross_ca
    if ca is None or ca <= 0:
        return None

    source = IncomeSource(
        user_id=user_id,
        earner="user",
        label="Activité principale",
        source_type="client",
        amount=ca,
        frequency="monthly",
        confidence="high",
        is_ae_revenue=True,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


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


# ── CRUD Endpoints ────────────────────────────────────────────────────────────


@router.get("", response_model=list[IncomeSourceRead])
async def list_income_sources(
    earner: Optional[str] = Query(None, pattern="^(user|spouse)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all active income sources for the authenticated user.

    Optionally filter by earner: ?earner=user or ?earner=spouse.
    Ordered by sort_order then label.

    Auto-migration: If user has no sources but profile.monthly_gross_ca > 0,
    auto-creates one "Activité principale" source.
    """
    # Ensure profile exists
    await _get_or_create_profile(current_user.id, db)

    # Build query
    query = (
        select(IncomeSource)
        .where(
            IncomeSource.user_id == current_user.id,
            IncomeSource.is_active == True,
        )
    )
    if earner:
        query = query.where(IncomeSource.earner == earner)
    query = query.order_by(IncomeSource.sort_order, IncomeSource.label)

    result = await db.execute(query)
    sources = result.scalars().all()

    # Auto-migration from existing CA (only when listing all, not earner-filtered)
    if not earner and not sources:
        profile_result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == current_user.id)
        )
        profile = profile_result.scalar_one_or_none()
        if (
            profile is not None
            and profile.monthly_gross_ca is not None
            and profile.monthly_gross_ca > 0
        ):
            auto_source = IncomeSource(
                user_id=current_user.id,
                earner="user",
                label="Activité principale",
                source_type="client",
                amount=profile.monthly_gross_ca,
                frequency="monthly",
                confidence="high",
                is_ae_revenue=True,
            )
            db.add(auto_source)
            await db.commit()
            await db.refresh(auto_source)
            sources = [auto_source]

    return [_source_to_read(s) for s in sources]


@router.get("/summary", response_model=IncomeSourceSummaryResponse)
async def get_income_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregated income summary by earner.

    Computes current_monthly_total, guaranteed (confidence=high),
    speculative (confidence!=high), and ending_within_12_months per earner.
    One-time sources are excluded from monthly totals.
    Annual sources are divided by 12.
    """
    await _get_or_create_profile(current_user.id, db)

    # Fetch all active sources
    result = await db.execute(
        select(IncomeSource)
        .where(
            IncomeSource.user_id == current_user.id,
            IncomeSource.is_active == True,
        )
        .order_by(IncomeSource.earner, IncomeSource.sort_order, IncomeSource.label)
    )
    sources = result.scalars().all()

    today = date.today()
    twelve_months = today + timedelta(days=365)

    def compute_earner_summary(earner_val: str) -> EarnersSummary:
        """Compute summary for a specific earner."""
        earner_sources = [s for s in sources if s.earner == earner_val and _source_is_current(s)]

        monthly_total = Decimal("0")
        guaranteed_monthly = Decimal("0")
        speculative_monthly = Decimal("0")
        ending_soon: list[dict] = []

        for s in earner_sources:
            # Compute monthly contribution
            if s.frequency == "monthly":
                monthly_contrib = s.amount
            elif s.frequency == "annual":
                monthly_contrib = s.amount / Decimal("12")
            else:
                # one_time — excluded from monthly totals
                continue

            monthly_total += monthly_contrib

            if s.confidence == "high":
                guaranteed_monthly += monthly_contrib
            else:
                speculative_monthly += monthly_contrib

            # Check if ending within 12 months
            if s.end_date is not None and s.end_date <= twelve_months:
                ending_soon.append({
                    "label": s.label,
                    "ends": s.end_date.isoformat(),
                    "monthly": str(monthly_contrib.quantize(Decimal("0.01"))),
                })

        return EarnersSummary(
            current_monthly_total=str(monthly_total.quantize(Decimal("0.01"))),
            sources_count=len(earner_sources),
            guaranteed_monthly=str(guaranteed_monthly.quantize(Decimal("0.01"))),
            speculative_monthly=str(speculative_monthly.quantize(Decimal("0.01"))),
            ending_within_12_months=ending_soon,
        )

    user_summary = compute_earner_summary("user")
    spouse_sources = [s for s in sources if s.earner == "spouse" and _source_is_current(s)]
    spouse_summary = compute_earner_summary("spouse") if spouse_sources else None

    household_total = (
        Decimal(user_summary.current_monthly_total)
        + (Decimal(spouse_summary.current_monthly_total) if spouse_summary else Decimal("0"))
    )

    return IncomeSourceSummaryResponse(
        user=user_summary,
        spouse=spouse_summary,
        household_monthly_total=str(household_total.quantize(Decimal("0.01"))),
    )


@router.get("/{source_id}", response_model=IncomeSourceRead)
async def get_income_source(
    source_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single income source by ID."""
    result = await db.execute(
        select(IncomeSource).where(
            IncomeSource.id == source_id,
            IncomeSource.user_id == current_user.id,
            IncomeSource.is_active == True,
        )
    )
    source = result.scalar_one_or_none()

    if source is None:
        raise HTTPException(status_code=404, detail="Income source not found")

    return _source_to_read(source)


@router.post("", response_model=IncomeSourceRead, status_code=201)
async def create_income_source(
    data: IncomeSourceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new income source.

    After creation, syncs profile.monthly_gross_ca from active user AE sources.
    """
    source = IncomeSource(
        user_id=current_user.id,
        earner=data.earner,
        label=data.label,
        source_type=data.source_type,
        amount=data.amount,
        frequency=data.frequency,
        start_date=data.start_date,
        end_date=data.end_date,
        confidence=data.confidence,
        annual_growth_rate=data.annual_growth_rate,
        is_ae_revenue=data.is_ae_revenue,
        sort_order=data.sort_order,
        notes=data.notes,
    )

    db.add(source)
    await db.commit()
    await db.refresh(source)

    # Sync profile CA
    await sync_profile_ca(current_user.id, db)

    return _source_to_read(source)


@router.put("/{source_id}", response_model=IncomeSourceRead)
async def update_income_source(
    source_id: UUID,
    data: IncomeSourceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an income source (partial update).

    After update, syncs profile.monthly_gross_ca from active user AE sources.
    """
    result = await db.execute(
        select(IncomeSource).where(
            IncomeSource.id == source_id,
            IncomeSource.user_id == current_user.id,
        )
    )
    source = result.scalar_one_or_none()

    if source is None:
        raise HTTPException(status_code=404, detail="Income source not found")

    update_data = data.model_dump(exclude_unset=True)

    for field in [
        "earner", "label", "source_type", "amount", "frequency",
        "start_date", "end_date", "confidence", "annual_growth_rate",
        "is_ae_revenue", "sort_order", "notes", "is_active",
    ]:
        if field in update_data and update_data[field] is not None:
            setattr(source, field, update_data[field])

    await db.commit()
    await db.refresh(source)

    # Sync profile CA
    await sync_profile_ca(current_user.id, db)

    return _source_to_read(source)


@router.delete("/{source_id}", status_code=204)
async def delete_income_source(
    source_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete an income source (sets is_active=False).

    After deletion, syncs profile.monthly_gross_ca from remaining active sources.
    """
    result = await db.execute(
        select(IncomeSource).where(
            IncomeSource.id == source_id,
            IncomeSource.user_id == current_user.id,
        )
    )
    source = result.scalar_one_or_none()

    if source is None:
        raise HTTPException(status_code=404, detail="Income source not found")

    source.is_active = False
    await db.commit()

    # Sync profile CA after source removal
    await sync_profile_ca(current_user.id, db)

    return None