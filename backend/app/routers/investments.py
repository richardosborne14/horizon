"""
Investment allocations CRUD router.

Manages per-user, per-vehicle investment allocations (balances and
monthly contributions). Uses an upsert pattern: all 7 vehicle rows
are guaranteed to exist for every user after the first GET request.

Routes:
    GET  /api/investments/vehicles      — public, no auth, vehicle specs
    GET  /api/investments               — all 7 allocations for current user
    PUT  /api/investments/{vehicle_key} — update single allocation
    PUT  /api/investments               — batch update all allocations
"""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.calculations.vehicles import (
    VEHICLE_ORDER,
    VEHICLE_SPECS,
    get_vehicle_spec,
    validate_vehicle_key,
)
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.investment import InvestmentAllocation
from app.models.user import User
from app.schemas.investment import (
    AllocationBatchItem,
    AllocationBatchWrite,
    AllocationRead,
    AllocationWrite,
    AllAllocationsRead,
    VehicleSpec,
)

router = APIRouter(prefix="/investments", tags=["investments"])


# ── Helpers ───────────────────────────────────────────────────────────────────


def _spec_to_pydantic(key: str, spec: dict) -> VehicleSpec:
    """Convert a VEHICLE_SPECS dict entry to a VehicleSpec Pydantic model."""
    # Some vehicles use scale-dependent rates (rates_by_scale with
    # pessimistic/moderate/optimistic) instead of a flat "rate" key.
    # For display/API purposes, use the moderate scale as the canonical rate.
    rate = spec.get("rate")
    if rate is None and "rates_by_scale" in spec:
        rate = spec["rates_by_scale"].get("moderate", Decimal("0"))

    return VehicleSpec(
        key=key,
        label=spec["label"],
        description=spec["description"],
        rate=rate,
        tax_free=spec["tax_free"],
        tax_rate=spec["tax_rate"],
        ceiling=spec["ceiling"],
        risk=spec["risk"],
        color=spec["color"],
        liquidity=spec["liquidity"],
        tax_deductible=spec.get("tax_deductible", False),
        informational=spec.get("informational", False),
        lock_up_years=spec.get("lock_up_years"),
    )


def _allocation_to_read(
    allocation: InvestmentAllocation,
) -> AllocationRead:
    """Convert an ORM allocation to an AllocationRead with embedded spec."""
    spec = get_vehicle_spec(allocation.vehicle_key)
    if spec is None:
        raise ValueError(
            f"Unknown vehicle_key in DB: {allocation.vehicle_key}"
        )

    # Ceiling warning: if balance exceeds the vehicle's ceiling
    warning = None
    ceiling = spec.get("ceiling")
    if (
        ceiling is not None
        and allocation.existing_balance > ceiling
    ):
        warning = (
            f"Le solde ({allocation.existing_balance}€) dépasse le "
            f"plafond de {ceiling}€"
        )

    return AllocationRead(
        id=allocation.id,
        vehicle_key=allocation.vehicle_key,
        existing_balance=allocation.existing_balance,
        monthly_contribution=allocation.monthly_contribution,
        spec=_spec_to_pydantic(allocation.vehicle_key, spec),
        warning=warning,
    )


async def _ensure_all_allocations(
    user_id: UUID, db: AsyncSession
) -> list[InvestmentAllocation]:
    """Guarantee all 7 vehicle rows exist for the user.

    Fetches existing allocations, creates missing ones with zero balances,
    and returns all 7 rows in vehicle display order.
    """
    # Fetch existing allocations
    result = await db.execute(
        select(InvestmentAllocation).where(
            InvestmentAllocation.user_id == user_id
        )
    )
    existing = {a.vehicle_key: a for a in result.scalars().all()}

    # Create missing ones
    created_any = False
    for key in VEHICLE_ORDER:
        if key not in existing:
            new_alloc = InvestmentAllocation(
                user_id=user_id,
                vehicle_key=key,
                existing_balance=Decimal("0"),
                monthly_contribution=Decimal("0"),
            )
            db.add(new_alloc)
            existing[key] = new_alloc
            created_any = True

    if created_any:
        await db.flush()

    # Return in display order
    return [existing[key] for key in VEHICLE_ORDER]


# ── Public Routes (no auth) ────────────────────────────────────────────────────


@router.get("/vehicles")
async def list_vehicles():
    """Return all 7 vehicle specs (public, no auth required).

    This is reference data — the vehicle rates, tax treatment,
    ceilings, risk levels, and colors.
    """
    return {
        key: _spec_to_pydantic(key, spec)
        for key, spec in VEHICLE_SPECS.items()
    }


@router.get("/catalog")
async def get_vehicle_catalog():
    """Return the full vehicle rules catalog for the savings tab rules panel (TASK-8.9.B).

    Returns VEHICLE_RULES from vehicles.py — rate, tax, ceiling, liquidity,
    lock_up, best_for, watch_out, horizon, open_conditions per vehicle.
    Public endpoint — no auth required.
    """
    from app.calculations.vehicles import VEHICLE_RULES

    return {"vehicles": VEHICLE_RULES}


# ── Authenticated Routes ──────────────────────────────────────────────────────


@router.get("", response_model=AllAllocationsRead)
async def list_allocations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all 7 vehicle allocations for the authenticated user.

    On first access, missing vehicle rows are auto-created with
    zero balances. Returns allocations in display order with stats.
    """
    allocations = await _ensure_all_allocations(current_user.id, db)

    alloc_reads = [_allocation_to_read(a) for a in allocations]

    total_existing = sum(
        (a.existing_balance for a in allocations), Decimal("0")
    )
    total_monthly = sum(
        (a.monthly_contribution for a in allocations), Decimal("0")
    )

    return AllAllocationsRead(
        allocations=alloc_reads,
        total_existing=total_existing,
        total_monthly=total_monthly,
        total_annual=total_monthly * 12,
    )


@router.put("/{vehicle_key}", response_model=AllocationRead)
async def update_single_allocation(
    vehicle_key: str,
    data: AllocationWrite,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update balance and/or contribution for one vehicle.

    The vehicle row is created if it doesn't exist yet.
    """
    if not validate_vehicle_key(vehicle_key):
        raise HTTPException(
            status_code=404,
            detail=(
                f"Invalid vehicle_key: {vehicle_key}. "
                f"Must be one of: {', '.join(VEHICLE_ORDER)}"
            ),
        )

    # Find or create the allocation
    result = await db.execute(
        select(InvestmentAllocation).where(
            InvestmentAllocation.user_id == current_user.id,
            InvestmentAllocation.vehicle_key == vehicle_key,
        )
    )
    allocation = result.scalar_one_or_none()

    if allocation is None:
        allocation = InvestmentAllocation(
            user_id=current_user.id,
            vehicle_key=vehicle_key,
        )
        db.add(allocation)

    allocation.existing_balance = data.existing_balance
    allocation.monthly_contribution = data.monthly_contribution

    await db.commit()
    await db.refresh(allocation)

    return _allocation_to_read(allocation)


@router.put("", response_model=AllAllocationsRead)
async def update_batch_allocations(
    data: AllocationBatchWrite,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Batch update multiple vehicle allocations at once.

    Sends a list of AllocationBatchItem objects. Only the vehicles
    included in the request are updated; others are unchanged.
    """
    # Build a map of existing allocations
    result = await db.execute(
        select(InvestmentAllocation).where(
            InvestmentAllocation.user_id == current_user.id
        )
    )
    existing = {a.vehicle_key: a for a in result.scalars().all()}

    updated_keys: set[str] = set()

    for item in data.allocations:
        allocation = existing.get(item.vehicle_key)

        if allocation is None:
            allocation = InvestmentAllocation(
                user_id=current_user.id,
                vehicle_key=item.vehicle_key,
            )
            db.add(allocation)
            existing[item.vehicle_key] = allocation

        allocation.existing_balance = item.existing_balance
        allocation.monthly_contribution = item.monthly_contribution
        updated_keys.add(item.vehicle_key)

    await db.commit()

    # Refresh only the updated rows
    for key in updated_keys:
        if key in existing:
            await db.refresh(existing[key])

    # Return all 7 allocations (re-fetch to include unmodified ones)
    all_allocs = await _ensure_all_allocations(current_user.id, db)
    alloc_reads = [_allocation_to_read(a) for a in all_allocs]

    total_existing = sum(
        (a.existing_balance for a in all_allocs), Decimal("0")
    )
    total_monthly = sum(
        (a.monthly_contribution for a in all_allocs), Decimal("0")
    )

    return AllAllocationsRead(
        allocations=alloc_reads,
        total_existing=total_existing,
        total_monthly=total_monthly,
        total_annual=total_monthly * 12,
    )