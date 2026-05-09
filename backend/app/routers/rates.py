"""
Rates API router — AE cotisation rate schedule and CFE estimates.

All endpoints are public (no auth required) — this is reference data
that the frontend needs to render rate previews.
"""

from typing import Optional

from fastapi import APIRouter, Query

from app.calculations.ae_rates import (
    get_ae_rate,
    get_all_schedules,
    get_cfe_estimate,
    get_rate_schedule,
    compute_annual_charges,
)

router = APIRouter(prefix="/rates", tags=["rates"])


@router.get("/ae-schedule")
async def ae_schedule(
    type: str = Query(
        default="bnc_non_reglementee",
        description="AE activity type: bnc_non_reglementee, bic_services, bic_vente, bnc_cipav",
    ),
):
    """Return the full rate schedule for one AE activity type."""
    schedule = get_rate_schedule(type)
    return {"activity_type": type, "schedule": schedule}


@router.get("/ae-schedules")
async def ae_schedules():
    """Return all AE rate schedules for all activity types."""
    schedules = get_all_schedules()
    return {"schedules": schedules}


@router.get("/ae-rate")
async def ae_rate(
    type: str = Query(
        default="bnc_non_reglementee",
        description="AE activity type",
    ),
    year: int = Query(
        default=2026,
        ge=2020,
        le=2070,
        description="Calendar year for rate lookup",
    ),
):
    """Return the effective AE rate for a given type and year."""
    rate = str(get_ae_rate(type, year))
    return {"activity_type": type, "year": year, "rate": rate}


@router.get("/cfe")
async def cfe(
    year: int = Query(
        default=2026,
        ge=2020,
        le=2070,
        description="Calendar year",
    ),
):
    """Return the estimated CFE for a given year."""
    estimate = str(get_cfe_estimate(year))
    return {"year": year, "cfe_estimate": estimate}


@router.get("/annual-charges")
async def annual_charges(
    gross_annual: float = Query(
        ..., gt=0, description="Gross annual CA in EUR"
    ),
    type: str = Query(
        default="bnc_non_reglementee",
        description="AE activity type",
    ),
    year: int = Query(
        default=2026,
        ge=2020,
        le=2070,
        description="Calendar year",
    ),
):
    """Compute full annual AE charges breakdown for a given gross amount."""
    from decimal import Decimal
    result = compute_annual_charges(
        Decimal(str(gross_annual)), type, year
    )
    return {
        "gross_annual": str(gross_annual),
        "activity_type": type,
        "year": year,
        "rate": str(result["rate"]),
        "urssaf_and_others": str(result["urssaf_and_others"]),
        "cfe": str(result["cfe"]),
        "total": str(result["total"]),
    }