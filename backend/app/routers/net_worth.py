"""
Net Worth API router — TASK-6.5.

Provides GET/PUT /api/net-worth (upsert pattern — single snapshot per user)
and GET /api/net-worth/summary (aggregated net worth from all sources).

Design:
  - Upsert: if no snapshot exists, create one. If exists, update it.
  - Summary aggregates: this snapshot + investment balances + loan balances.
  - Cash reserves from net worth are NOT automatically included in the
    readiness score unless explicitly queried — this avoids coupling the
    routers. The readiness score can access the snapshot via the projection
    router's _assemble_input.
"""

import logging
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.net_worth import NetWorthSnapshot
from app.models.investment import InvestmentAllocation
from app.models.loan import Loan
from app.models.user import User
from app.schemas.net_worth import NetWorthCreate, NetWorthRead, NetWorthSummary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/net-worth", tags=["net-worth"])


# ── Helper ──────────────────────────────────────────────────────────────────


def _snapshot_to_read(snapshot: NetWorthSnapshot) -> NetWorthRead:
    """Convert ORM model to Pydantic read schema."""
    return NetWorthRead(
        id=snapshot.id,
        user_id=snapshot.user_id,
        cash_current_accounts=snapshot.cash_current_accounts or Decimal("0"),
        cash_savings_other=snapshot.cash_savings_other or Decimal("0"),
        property_primary_value=snapshot.property_primary_value or Decimal("0"),
        property_other_value=snapshot.property_other_value or Decimal("0"),
        property_appreciation_rate=snapshot.property_appreciation_rate or Decimal("0.02"),
        downsize_enabled=bool(snapshot.downsize_enabled),
        downsize_year=snapshot.downsize_year,
        downsize_target_value=snapshot.downsize_target_value,
        business_value=snapshot.business_value or Decimal("0"),
        vehicle_value=snapshot.vehicle_value or Decimal("0"),
        other_assets=snapshot.other_assets or Decimal("0"),
        other_assets_label=snapshot.other_assets_label,
        other_debts=snapshot.other_debts or Decimal("0"),
        other_debts_label=snapshot.other_debts_label,
        snapshot_date=snapshot.snapshot_date,
        created_at=snapshot.created_at,
        updated_at=snapshot.updated_at,
    )


# ── Routes ──────────────────────────────────────────────────────────────────


@router.get("", response_model=NetWorthRead)
async def get_net_worth(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current net worth snapshot for the authenticated user.

    Returns the snapshot if it exists, otherwise returns a default with
    all zeros and today's date (no DB row created until PUT).
    """
    result = await db.execute(
        select(NetWorthSnapshot).where(
            NetWorthSnapshot.user_id == str(current_user.id)
        )
    )
    snapshot = result.scalar_one_or_none()

    if snapshot is None:
        # Return a virtual default — no DB row yet
        # The frontend can display zeros; the user creates via PUT.
        return NetWorthRead(
            id=current_user.id,  # type: ignore — placeholder UUID
            user_id=current_user.id,
            cash_current_accounts=Decimal("0"),
            cash_savings_other=Decimal("0"),
            property_primary_value=Decimal("0"),
            property_other_value=Decimal("0"),
            property_appreciation_rate=Decimal("0.02"),
            downsize_enabled=False,
            downsize_year=None,
            downsize_target_value=None,
            business_value=Decimal("0"),
            vehicle_value=Decimal("0"),
            other_assets=Decimal("0"),
            other_assets_label=None,
            other_debts=Decimal("0"),
            other_debts_label=None,
            snapshot_date=date.today(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    return _snapshot_to_read(snapshot)


@router.put("", response_model=NetWorthRead)
async def put_net_worth(
    body: NetWorthCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update the net worth snapshot (upsert).

    Single snapshot per user. If one exists, updates it. Otherwise creates.
    """
    result = await db.execute(
        select(NetWorthSnapshot).where(
            NetWorthSnapshot.user_id == str(current_user.id)
        )
    )
    snapshot = result.scalar_one_or_none()

    if snapshot is None:
        snapshot = NetWorthSnapshot(
            user_id=str(current_user.id),
            cash_current_accounts=body.cash_current_accounts,
            cash_savings_other=body.cash_savings_other,
            property_primary_value=body.property_primary_value,
            property_other_value=body.property_other_value,
            property_appreciation_rate=body.property_appreciation_rate,
            downsize_enabled=body.downsize_enabled,
            downsize_year=body.downsize_year,
            downsize_target_value=body.downsize_target_value,
            business_value=body.business_value,
            vehicle_value=body.vehicle_value,
            other_assets=body.other_assets,
            other_assets_label=body.other_assets_label,
            other_debts=body.other_debts,
            other_debts_label=body.other_debts_label,
            snapshot_date=body.snapshot_date,
        )
        db.add(snapshot)
    else:
        snapshot.cash_current_accounts = body.cash_current_accounts
        snapshot.cash_savings_other = body.cash_savings_other
        snapshot.property_primary_value = body.property_primary_value
        snapshot.property_other_value = body.property_other_value
        snapshot.property_appreciation_rate = body.property_appreciation_rate
        snapshot.downsize_enabled = body.downsize_enabled
        snapshot.downsize_year = body.downsize_year
        snapshot.downsize_target_value = body.downsize_target_value
        snapshot.business_value = body.business_value
        snapshot.vehicle_value = body.vehicle_value
        snapshot.other_assets = body.other_assets
        snapshot.other_assets_label = body.other_assets_label
        snapshot.other_debts = body.other_debts
        snapshot.other_debts_label = body.other_debts_label
        snapshot.snapshot_date = body.snapshot_date

    await db.commit()
    await db.refresh(snapshot)

    return _snapshot_to_read(snapshot)


@router.get("/summary", response_model=NetWorthSummary)
async def get_net_worth_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregated net worth from all sources.

    Combines:
      1. Net worth snapshot (cash, property, business, vehicles, other)
      2. Investment balances from InvestmentAllocation
      3. Loan remaining balances from Loan

    Returns total_assets, total_debts, and net_worth with breakdowns.
    """
    uid = str(current_user.id)

    # ── Net worth snapshot ────────────────────────────────────────────
    nw_result = await db.execute(
        select(NetWorthSnapshot).where(NetWorthSnapshot.user_id == uid)
    )
    nw = nw_result.scalar_one_or_none()

    cash_total = nw.cash_current_accounts + nw.cash_savings_other if nw else Decimal("0")
    prop_total = (
        (nw.property_primary_value or Decimal("0"))
        + (nw.property_other_value or Decimal("0"))
    ) if nw else Decimal("0")
    business_val = nw.business_value if nw else Decimal("0")
    vehicle_val = nw.vehicle_value if nw else Decimal("0")
    other_assets_val = nw.other_assets if nw else Decimal("0")
    other_debts_val = nw.other_debts if nw else Decimal("0")
    snapshot_date_val = nw.snapshot_date if nw else date.today()

    # ── Investment balances ───────────────────────────────────────────
    alloc_result = await db.execute(
        select(InvestmentAllocation).where(InvestmentAllocation.user_id == uid)
    )
    allocations = alloc_result.scalars().all()

    investments_balance = sum(
        (a.existing_balance or Decimal("0") for a in allocations),
        Decimal("0"),
    )
    investments_monthly = sum(
        (a.monthly_contribution or Decimal("0") for a in allocations),
        Decimal("0"),
    )

    # ── Loan balances ─────────────────────────────────────────────────
    loan_result = await db.execute(
        select(Loan).where(
            Loan.user_id == uid,
            Loan.is_active == True,
        )
    )
    loans = loan_result.scalars().all()

    loans_total_remaining = Decimal("0")
    loans_total_monthly = Decimal("0")
    for loan in loans:
        if loan.remaining_balance:
            loans_total_remaining += loan.remaining_balance
        loans_total_monthly += loan.monthly_payment or Decimal("0")
        if loan.insurance_monthly:
            loans_total_monthly += loan.insurance_monthly

    # ── Compute totals ────────────────────────────────────────────────
    total_assets = (
        cash_total
        + prop_total
        + business_val
        + vehicle_val
        + other_assets_val
        + investments_balance
    )

    total_debts = loans_total_remaining + other_debts_val

    net_worth = total_assets - total_debts

    # ── Breakdowns for frontend display ───────────────────────────────
    assets_breakdown = {
        "liquidites": float(cash_total),
        "immobilier": float(prop_total),
        "placements": float(investments_balance),
        "entreprise": float(business_val),
        "vehicules": float(vehicle_val),
        "autres_actifs": float(other_assets_val),
    }

    debts_breakdown = {
        "credits_restants": float(loans_total_remaining),
        "autres_dettes": float(other_debts_val),
    }

    note = ""
    if investments_balance > Decimal("0"):
        note += f"Placements: {investments_balance:,.0f}€. "
    if loans_total_remaining > Decimal("0"):
        note += f"Crédits restants: {loans_total_remaining:,.0f}€."

    return NetWorthSummary(
        cash_total=cash_total,
        property_total=prop_total,
        business_value=business_val,
        vehicle_value=vehicle_val,
        other_assets=other_assets_val,
        other_debts=other_debts_val,
        investments_balance=investments_balance,
        investments_monthly=investments_monthly,
        loans_total_remaining=loans_total_remaining,
        loans_total_monthly=loans_total_monthly,
        total_assets=total_assets,
        total_debts=total_debts,
        net_worth=net_worth,
        assets_breakdown=assets_breakdown,
        debts_breakdown=debts_breakdown,
        snapshot_date=snapshot_date_val,
        note=note.strip(),
    )