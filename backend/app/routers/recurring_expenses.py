"""
Recurring Expense CRUD router — manage time-bounded annual expenses.

All endpoints require authentication and are scoped to the current user.
POST creates an expense with year-range validation.
DELETE soft-deletes (sets is_active=false).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.recurring_expense import RecurringExpense
from app.models.user import User
from app.schemas.recurring_expense import (
    RecurringExpenseCreate,
    RecurringExpenseRead,
    RecurringExpenseUpdate,
    RecurringExpenseList,
)

router = APIRouter(prefix="/recurring-expenses", tags=["recurring-expenses"])


def _serialize_amount(amount) -> str:
    """Convert Decimal or float to string for JSON serialization."""
    return str(amount)


def _expense_to_read(expense: RecurringExpense) -> RecurringExpenseRead:
    """Convert a RecurringExpense ORM object to a RecurringExpenseRead response."""
    return RecurringExpenseRead(
        id=expense.id,
        user_id=expense.user_id,
        label=expense.label,
        annual_amount=_serialize_amount(expense.annual_amount),
        from_year=expense.from_year,
        to_year=expense.to_year,
        category=expense.category,
        is_active=expense.is_active,
        created_at=expense.created_at,
        updated_at=expense.updated_at,
    )


# ── CRUD Endpoints ────────────────────────────────────────────────────────────


@router.get("", response_model=RecurringExpenseList)
async def list_recurring_expenses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all recurring expenses for the authenticated user.

    Only returns active expenses, ordered by from_year ascending.
    """
    result = await db.execute(
        select(RecurringExpense)
        .where(
            RecurringExpense.user_id == current_user.id,
            RecurringExpense.is_active == True,
        )
        .order_by(RecurringExpense.from_year, RecurringExpense.label)
    )
    expenses = result.scalars().all()

    expenses_read = [_expense_to_read(e) for e in expenses]

    return RecurringExpenseList(
        expenses=expenses_read,
        total=len(expenses_read),
    )


@router.get("/{expense_id}", response_model=RecurringExpenseRead)
async def get_recurring_expense(
    expense_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single recurring expense by ID."""
    result = await db.execute(
        select(RecurringExpense).where(
            RecurringExpense.id == expense_id,
            RecurringExpense.user_id == current_user.id,
            RecurringExpense.is_active == True,
        )
    )
    expense = result.scalar_one_or_none()

    if expense is None:
        raise HTTPException(status_code=404, detail="Recurring expense not found")

    return _expense_to_read(expense)


@router.post("", response_model=RecurringExpenseRead, status_code=201)
async def create_recurring_expense(
    data: RecurringExpenseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new recurring expense.

    Year range is validated by Pydantic (to_year >= from_year).
    """
    expense = RecurringExpense(
        user_id=current_user.id,
        label=data.label,
        annual_amount=data.annual_amount,
        from_year=data.from_year,
        to_year=data.to_year,
        category=data.category,
    )

    db.add(expense)
    await db.commit()
    await db.refresh(expense)

    return _expense_to_read(expense)


@router.put("/{expense_id}", response_model=RecurringExpenseRead)
async def update_recurring_expense(
    expense_id: UUID,
    data: RecurringExpenseUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a recurring expense (partial update)."""
    result = await db.execute(
        select(RecurringExpense).where(
            RecurringExpense.id == expense_id,
            RecurringExpense.user_id == current_user.id,
        )
    )
    expense = result.scalar_one_or_none()

    if expense is None:
        raise HTTPException(status_code=404, detail="Recurring expense not found")

    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if value is not None:
            setattr(expense, field, value)

    await db.commit()
    await db.refresh(expense)

    return _expense_to_read(expense)


@router.delete("/{expense_id}", status_code=204)
async def delete_recurring_expense(
    expense_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a recurring expense (sets is_active=false)."""
    result = await db.execute(
        select(RecurringExpense).where(
            RecurringExpense.id == expense_id,
            RecurringExpense.user_id == current_user.id,
        )
    )
    expense = result.scalar_one_or_none()

    if expense is None:
        raise HTTPException(status_code=404, detail="Recurring expense not found")

    expense.is_active = False
    await db.commit()

    return None