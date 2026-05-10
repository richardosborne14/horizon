"""
Pydantic schemas for Loan — TASK-6.3.

Loans have fixed nominal monthly payments that do NOT inflate,
and terminate at end_date (computed from remaining_months if not provided).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class LoanCreate(BaseModel):
    """Payload for creating a new loan."""

    label: str = Field(min_length=1, max_length=200)
    loan_type: Literal["mortgage", "auto", "consumer", "student", "business", "other"]
    monthly_payment: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    start_date: date
    end_date: Optional[date] = None
    remaining_months: Optional[int] = Field(default=None, gt=0)
    original_amount: Optional[Decimal] = Field(default=None, max_digits=12, decimal_places=2)
    interest_rate: Optional[Decimal] = Field(default=None, ge=0, le=1, max_digits=5, decimal_places=4)
    remaining_balance: Optional[Decimal] = Field(default=None, max_digits=12, decimal_places=2)
    insurance_monthly: Decimal = Field(default=Decimal("0"), max_digits=8, decimal_places=2)
    end_action: Literal["freed", "refinanced"] = "freed"
    notes: Optional[str] = Field(default=None, max_length=500)


class LoanUpdate(BaseModel):
    """Partial update — all fields optional."""

    label: Optional[str] = Field(default=None, min_length=1, max_length=200)
    loan_type: Optional[Literal["mortgage", "auto", "consumer", "student", "business", "other"]] = None
    monthly_payment: Optional[Decimal] = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    remaining_months: Optional[int] = Field(default=None, gt=0)
    original_amount: Optional[Decimal] = Field(default=None, max_digits=12, decimal_places=2)
    interest_rate: Optional[Decimal] = Field(default=None, ge=0, le=1, max_digits=5, decimal_places=4)
    remaining_balance: Optional[Decimal] = Field(default=None, max_digits=12, decimal_places=2)
    insurance_monthly: Optional[Decimal] = Field(default=None, max_digits=8, decimal_places=2)
    end_action: Optional[Literal["freed", "refinanced"]] = None
    notes: Optional[str] = Field(default=None, max_length=500)
    is_active: Optional[bool] = None


class LoanRead(BaseModel):
    """Full loan data returned by GET endpoints."""

    id: UUID
    user_id: UUID
    label: str
    loan_type: str
    monthly_payment: Decimal
    start_date: date
    end_date: Optional[date] = None
    remaining_months: Optional[int] = None
    original_amount: Optional[Decimal] = None
    interest_rate: Optional[Decimal] = None
    remaining_balance: Optional[Decimal] = None
    insurance_monthly: Decimal
    end_action: str
    notes: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LoanSummary(BaseModel):
    """Aggregated loan summary with termination timeline."""

    total_monthly: Decimal
    total_remaining: Optional[Decimal] = None
    loans: list[LoanRead]
    timeline: list[dict]  # [{"year": 2026, "total_monthly": 590}, ...]