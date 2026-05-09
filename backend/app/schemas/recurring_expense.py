"""Pydantic schemas for RecurringExpense — time-bounded annual expenses."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class RecurringExpenseCreate(BaseModel):
    """Payload for creating a new recurring expense."""

    label: str = Field(min_length=1, max_length=200)
    annual_amount: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    from_year: int = Field(ge=2000, le=2100)
    to_year: int = Field(ge=2000, le=2100)
    category: Optional[str] = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def check_year_range(self):
        """to_year must be >= from_year."""
        if self.to_year < self.from_year:
            raise ValueError(
                f"to_year ({self.to_year}) must be >= from_year ({self.from_year})"
            )
        return self


class RecurringExpenseUpdate(BaseModel):
    """Partial update — all fields optional."""

    label: Optional[str] = Field(default=None, min_length=1, max_length=200)
    annual_amount: Optional[Decimal] = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    from_year: Optional[int] = Field(default=None, ge=2000, le=2100)
    to_year: Optional[int] = Field(default=None, ge=2000, le=2100)
    category: Optional[str] = Field(default=None, max_length=50)
    is_active: Optional[bool] = None


class RecurringExpenseRead(BaseModel):
    """Full recurring expense data returned by GET endpoints."""

    id: UUID
    user_id: UUID
    label: str
    annual_amount: str  # Decimal as string
    from_year: int
    to_year: int
    category: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RecurringExpenseList(BaseModel):
    """Wrapper for listing multiple recurring expenses."""

    expenses: list[RecurringExpenseRead]
    total: int