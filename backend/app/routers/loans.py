"""
Loan CRUD router — manage loans and mortgages (TASK-6.3).

All endpoints require authentication and are scoped to the current user.
Loans are NOT inflation-adjusted in the projection — they're fixed nominal.
The projection engine reads loan data and drops payments after end_date.
"""

from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.loan import Loan
from app.models.user import User
from app.schemas.loan import (
    LoanCreate,
    LoanRead,
    LoanUpdate,
    LoanSummary,
)

router = APIRouter(prefix="/loans", tags=["loans"])


# ── Helpers ───────────────────────────────────────────────────────────────────


def _resolve_end_date(
    start_date: date,
    end_date: date | None,
    remaining_months: int | None,
) -> date | None:
    """Compute end_date from remaining_months if end_date is not provided.

    Args:
        start_date: When the loan started.
        end_date: Explicit end date (takes priority).
        remaining_months: Alternative — compute end_date from this.

    Returns:
        The resolved end_date, or None if neither is provided.
    """
    if end_date is not None:
        return end_date
    if remaining_months is not None and remaining_months > 0:
        return start_date + relativedelta(months=remaining_months)
    return None


def _loan_to_read(loan: Loan) -> LoanRead:
    """Convert a Loan ORM object to a LoanRead response."""
    end_date_val = loan.end_date
    if end_date_val is None and loan.remaining_months is not None:
        end_date_val = loan.start_date + relativedelta(months=loan.remaining_months)

    return LoanRead(
        id=loan.id,
        user_id=loan.user_id,
        label=loan.label,
        loan_type=loan.loan_type,
        monthly_payment=loan.monthly_payment,
        start_date=loan.start_date,
        end_date=end_date_val,
        remaining_months=loan.remaining_months,
        original_amount=loan.original_amount,
        interest_rate=loan.interest_rate,
        remaining_balance=loan.remaining_balance,
        insurance_monthly=loan.insurance_monthly or Decimal("0"),
        end_action=loan.end_action,
        notes=loan.notes,
        is_active=loan.is_active,
        created_at=loan.created_at,
        updated_at=loan.updated_at,
    )


# ── CRUD Endpoints ────────────────────────────────────────────────────────────


@router.get("", response_model=list[LoanRead])
async def list_loans(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all active loans for the authenticated user."""
    result = await db.execute(
        select(Loan)
        .where(
            Loan.user_id == current_user.id,
            Loan.is_active == True,
        )
        .order_by(Loan.start_date)
    )
    loans = result.scalars().all()
    return [_loan_to_read(l) for l in loans]


@router.get("/summary", response_model=LoanSummary)
async def loan_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregated loan summary with termination timeline."""
    result = await db.execute(
        select(Loan)
        .where(
            Loan.user_id == current_user.id,
            Loan.is_active == True,
        )
        .order_by(Loan.start_date)
    )
    loans = result.scalars().all()
    loan_reads = [_loan_to_read(l) for l in loans]

    total_monthly = Decimal("0")
    for l in loans:
        if l.end_action == "refinanced":
            continue
        total_monthly += (l.monthly_payment or Decimal("0")) + (l.insurance_monthly or Decimal("0"))

    total_remaining = sum(
        (l.remaining_balance or Decimal("0")) for l in loans
    )
    if isinstance(total_remaining, int):
        total_remaining = Decimal(str(total_remaining))

    # Build termination timeline
    current_year = date.today().year
    year_payments: dict[int, Decimal] = {}
    for l in loans:
        end_date_val = l.end_date
        if end_date_val is None and l.remaining_months:
            end_date_val = l.start_date + relativedelta(months=l.remaining_months)
        if end_date_val is None:
            continue
        end_year = end_date_val.year
        monthly = l.monthly_payment + (l.insurance_monthly or Decimal("0"))
        for y in range(current_year, min(current_year + 30, end_year + 1)):
            year_payments[y] = year_payments.get(y, Decimal("0")) + monthly

    timeline = sorted(
        [{"year": y, "total_monthly": float(v)} for y, v in year_payments.items()],
        key=lambda x: x["year"],
    )

    return LoanSummary(
        total_monthly=total_monthly,
        total_remaining=total_remaining if total_remaining > 0 else None,
        loans=loan_reads,
        timeline=timeline,
    )


@router.get("/{loan_id}", response_model=LoanRead)
async def get_loan(
    loan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single loan by ID."""
    result = await db.execute(
        select(Loan).where(
            Loan.id == loan_id,
            Loan.user_id == current_user.id,
            Loan.is_active == True,
        )
    )
    loan = result.scalar_one_or_none()

    if loan is None:
        raise HTTPException(status_code=404, detail="Loan not found")

    return _loan_to_read(loan)


@router.post("", response_model=LoanRead, status_code=201)
async def create_loan(
    data: LoanCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new loan."""
    end_date_val = _resolve_end_date(data.start_date, data.end_date, data.remaining_months)

    loan = Loan(
        user_id=current_user.id,
        label=data.label,
        loan_type=data.loan_type,
        monthly_payment=data.monthly_payment,
        start_date=data.start_date,
        end_date=end_date_val,
        remaining_months=data.remaining_months,
        original_amount=data.original_amount,
        interest_rate=data.interest_rate,
        remaining_balance=data.remaining_balance,
        insurance_monthly=data.insurance_monthly,
        end_action=data.end_action,
        notes=data.notes,
    )

    db.add(loan)
    await db.commit()
    await db.refresh(loan)

    return _loan_to_read(loan)


@router.put("/{loan_id}", response_model=LoanRead)
async def update_loan(
    loan_id: UUID,
    data: LoanUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a loan (partial update)."""
    result = await db.execute(
        select(Loan).where(
            Loan.id == loan_id,
            Loan.user_id == current_user.id,
        )
    )
    loan = result.scalar_one_or_none()

    if loan is None:
        raise HTTPException(status_code=404, detail="Loan not found")

    update_data = data.model_dump(exclude_unset=True)

    # Handle end_date / remaining_months resolution
    new_start = update_data.get("start_date", loan.start_date)
    new_end = update_data.get("end_date", loan.end_date)
    new_remaining = update_data.get("remaining_months", loan.remaining_months)

    if "end_date" in update_data or "remaining_months" in update_data or "start_date" in update_data:
        loan.end_date = _resolve_end_date(new_start, new_end, new_remaining)

    for field in [
        "label", "loan_type", "monthly_payment", "start_date",
        "remaining_months", "original_amount", "interest_rate",
        "remaining_balance", "insurance_monthly", "end_action",
        "notes", "is_active",
    ]:
        if field in update_data and update_data[field] is not None:
            if field != "start_date" and field != "end_date":  # handled above
                setattr(loan, field, update_data[field])

    await db.commit()
    await db.refresh(loan)

    return _loan_to_read(loan)


@router.delete("/{loan_id}", status_code=204)
async def delete_loan(
    loan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a loan (sets is_active=False)."""
    result = await db.execute(
        select(Loan).where(
            Loan.id == loan_id,
            Loan.user_id == current_user.id,
        )
    )
    loan = result.scalar_one_or_none()

    if loan is None:
        raise HTTPException(status_code=404, detail="Loan not found")

    loan.is_active = False
    await db.commit()

    return None