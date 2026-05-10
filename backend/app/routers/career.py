"""
Career History router — CRUD for career periods (TASK-6.1).

All endpoints require authentication and are scoped to the current user.
Each period represents a distinct phase of the user's professional life.
Periods are ordered by start_date.
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.career_period import CareerPeriod
from app.models.user import User
from app.schemas.career import (
    CareerPeriodCreate,
    CareerPeriodRead,
    CareerPeriodUpdate,
    CareerSummaryResponse,
    compute_trimestres_estimated,
    resolve_pension_regime,
    check_overlaps,
)
from app.calculations.pension import get_trimestres_requis

router = APIRouter(prefix="/career", tags=["career"])


# ── Helpers ───────────────────────────────────────────────────────────────────


def _period_to_read(
    period: CareerPeriod,
    all_periods: list[dict] | None = None,
) -> CareerPeriodRead:
    """Convert a CareerPeriod ORM object to a CareerPeriodRead response.

    Args:
        period: The ORM object.
        all_periods: Optional list of all periods for overlap detection.
            If None, overlap detection is skipped.

    Returns:
        A populated CareerPeriodRead.
    """
    end = period.end_date or date.today()
    duration_years = (end - period.start_date).days / 365.25 if end >= period.start_date else 0.0

    trimestres = compute_trimestres_estimated(
        period_type=period.period_type,
        start_date=period.start_date,
        end_date=period.end_date,
        annual_gross=period.annual_gross,
        is_full_time=period.is_full_time,
        time_percentage=period.time_percentage,
    )

    has_overlap = False
    overlaps_with: list[UUID] = []
    if all_periods:
        has_overlap, overlaps_with = check_overlaps(
            current_id=period.id,
            current_start=period.start_date,
            current_end=period.end_date,
            all_periods=all_periods,
        )

    regime = resolve_pension_regime(period.period_type, period.pension_regime)

    return CareerPeriodRead(
        id=period.id,
        user_id=period.user_id,
        period_type=period.period_type,
        start_date=period.start_date,
        end_date=period.end_date,
        employer_name=period.employer_name,
        job_title=period.job_title,
        annual_gross=period.annual_gross,
        is_full_time=period.is_full_time,
        time_percentage=period.time_percentage,
        pension_regime=regime,
        notes=period.notes,
        sort_order=period.sort_order,
        is_active=period.is_active,
        created_at=period.created_at,
        updated_at=period.updated_at,
        duration_years=round(duration_years, 1),
        trimestres_estimated=trimestres,
        has_overlap=has_overlap,
        overlaps_with=overlaps_with,
    )


# ── CRUD Endpoints ────────────────────────────────────────────────────────────


@router.get("", response_model=list[CareerPeriodRead])
async def list_career_periods(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all active career periods for the authenticated user.

    Ordered by start_date ascending. Includes computed fields:
    duration_years, trimestres_estimated, overlap detection.
    """
    result = await db.execute(
        select(CareerPeriod)
        .where(
            CareerPeriod.user_id == current_user.id,
            CareerPeriod.is_active == True,
        )
        .order_by(CareerPeriod.start_date)
    )
    periods = result.scalars().all()

    # Build simple dicts for overlap detection
    all_dicts = [
        {
            "id": p.id,
            "start_date": p.start_date,
            "end_date": p.end_date,
        }
        for p in periods
    ]

    return [_period_to_read(p, all_dicts) for p in periods]


@router.get("/summary", response_model=CareerSummaryResponse)
async def career_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregated career summary with trimestre count and timeline.

    Used by the frontend to show the "X / Y trimestres" progress bar
    and the career timeline visualization.
    """
    result = await db.execute(
        select(CareerPeriod)
        .where(
            CareerPeriod.user_id == current_user.id,
            CareerPeriod.is_active == True,
        )
        .order_by(CareerPeriod.start_date)
    )
    periods = result.scalars().all()

    if not periods:
        return CareerSummaryResponse(
            total_periods=0,
            total_years_worked=0.0,
            total_trimestres_estimated=0,
            trimestres_required=172,
            trimestres_remaining=172,
        )

    total_trimestres = 0
    total_years = 0.0
    regimes: set[str] = set()
    timeline_entries: list[dict] = []

    current_period_data = None

    for p in periods:
        end = p.end_date or date.today()
        if end >= p.start_date:
            dur = (end - p.start_date).days / 365.25
        else:
            dur = 0.0
        total_years += dur

        trimestres = compute_trimestres_estimated(
            period_type=p.period_type,
            start_date=p.start_date,
            end_date=p.end_date,
            annual_gross=p.annual_gross,
            is_full_time=p.is_full_time,
            time_percentage=p.time_percentage,
        )
        total_trimestres += trimestres

        regime = resolve_pension_regime(p.period_type, p.pension_regime)
        if regime:
            regimes.add(regime)

        # Is this the current (ongoing) period?
        if p.end_date is None:
            current_period_data = {
                "type": p.period_type,
                "since": p.start_date.isoformat(),
            }

        # Build yearly timeline entries
        start_year = p.start_date.year
        end_year = end.year + 1
        for yr in range(start_year, end_year):
            # Simple: 4 trimestres/year if full year of CDI, otherwise estimate
            year_trimestres = min(4, max(0, trimestres // max(1, end_year - start_year)))
            timeline_entries.append({
                "year": yr,
                "period_type": p.period_type,
                "trimestres": year_trimestres,
                "annual_gross": float(p.annual_gross) if p.annual_gross else None,
                "regime": regime,
            })

    # Estimate birth year from current AE period start
    # Fallback: assume birth year for 172 trimestres (post-1973)
    # In practice the projection engine provides the actual birth year
    trimestres_requis_val = 172  # Default for post-1973
    if current_period_data:
        # We'd need the user's birth_date from profile — default for now
        pass

    # Deduplicate and sort timeline
    seen_years: set[int] = set()
    unique_timeline: list[dict] = []
    for entry in timeline_entries:
        yr = entry["year"]
        if yr not in seen_years:
            seen_years.add(yr)
            unique_timeline.append(entry)
    unique_timeline.sort(key=lambda x: x["year"])

    return CareerSummaryResponse(
        total_periods=len(periods),
        total_years_worked=round(total_years, 1),
        total_trimestres_estimated=total_trimestres,
        trimestres_required=trimestres_requis_val,
        trimestres_remaining=max(0, trimestres_requis_val - total_trimestres),
        current_period=current_period_data,
        pension_regimes=sorted(regimes),
        timeline=unique_timeline,
    )


@router.get("/{period_id}", response_model=CareerPeriodRead)
async def get_career_period(
    period_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single career period by ID."""
    result = await db.execute(
        select(CareerPeriod).where(
            CareerPeriod.id == period_id,
            CareerPeriod.user_id == current_user.id,
            CareerPeriod.is_active == True,
        )
    )
    period = result.scalar_one_or_none()

    if period is None:
        raise HTTPException(status_code=404, detail="Career period not found")

    # Get all periods for overlap detection
    all_result = await db.execute(
        select(CareerPeriod).where(
            CareerPeriod.user_id == current_user.id,
            CareerPeriod.is_active == True,
        )
    )
    all_periods = [
        {"id": p.id, "start_date": p.start_date, "end_date": p.end_date}
        for p in all_result.scalars().all()
    ]

    return _period_to_read(period, all_periods)


@router.post("", response_model=CareerPeriodRead, status_code=201)
async def create_career_period(
    data: CareerPeriodCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new career period.

    pension_regime is auto-derived from period_type if not provided.
    """
    regime = resolve_pension_regime(data.period_type, data.pension_regime)

    period = CareerPeriod(
        user_id=current_user.id,
        period_type=data.period_type,
        start_date=data.start_date,
        end_date=data.end_date,
        employer_name=data.employer_name,
        job_title=data.job_title,
        annual_gross=data.annual_gross,
        is_full_time=data.is_full_time,
        time_percentage=data.time_percentage,
        pension_regime=regime,
        notes=data.notes,
        sort_order=data.sort_order,
    )

    db.add(period)
    await db.commit()
    await db.refresh(period)

    # Compute overlap with existing periods
    all_result = await db.execute(
        select(CareerPeriod).where(
            CareerPeriod.user_id == current_user.id,
            CareerPeriod.is_active == True,
        )
    )
    all_periods = [
        {"id": p.id, "start_date": p.start_date, "end_date": p.end_date}
        for p in all_result.scalars().all()
    ]

    return _period_to_read(period, all_periods)


@router.put("/{period_id}", response_model=CareerPeriodRead)
async def update_career_period(
    period_id: UUID,
    data: CareerPeriodUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a career period (partial update)."""
    result = await db.execute(
        select(CareerPeriod).where(
            CareerPeriod.id == period_id,
            CareerPeriod.user_id == current_user.id,
        )
    )
    period = result.scalar_one_or_none()

    if period is None:
        raise HTTPException(status_code=404, detail="Career period not found")

    update_data = data.model_dump(exclude_unset=True)

    for field in [
        "period_type", "start_date", "end_date", "employer_name",
        "job_title", "annual_gross", "is_full_time", "time_percentage",
        "pension_regime", "notes", "sort_order", "is_active",
    ]:
        if field in update_data and update_data[field] is not None:
            setattr(period, field, update_data[field])

    # Re-resolve pension regime if period_type changed
    if "period_type" in update_data and "pension_regime" not in update_data:
        period.pension_regime = resolve_pension_regime(
            period.period_type, period.pension_regime
        )

    await db.commit()
    await db.refresh(period)

    # Compute overlap with existing periods
    all_result = await db.execute(
        select(CareerPeriod).where(
            CareerPeriod.user_id == current_user.id,
            CareerPeriod.is_active == True,
        )
    )
    all_periods = [
        {"id": p.id, "start_date": p.start_date, "end_date": p.end_date}
        for p in all_result.scalars().all()
    ]

    return _period_to_read(period, all_periods)


@router.delete("/{period_id}", status_code=204)
async def delete_career_period(
    period_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a career period (sets is_active=False)."""
    result = await db.execute(
        select(CareerPeriod).where(
            CareerPeriod.id == period_id,
            CareerPeriod.user_id == current_user.id,
        )
    )
    period = result.scalar_one_or_none()

    if period is None:
        raise HTTPException(status_code=404, detail="Career period not found")

    period.is_active = False
    await db.commit()

    return None