"""
Pydantic schemas for NetWorthSnapshot — TASK-6.5.

Net worth aggregates three data sources:
  1. This model's fields (cash, property, business, vehicles, other)
  2. Investment balances from InvestmentAllocation
  3. Loan remaining balances from Loan

The API reads all three sources and computes total_assets, total_debts, net_worth.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class NetWorthCreate(BaseModel):
    """Payload for creating or updating a net worth snapshot (upsert).

    All fields default to 0 — the user fills in what they know.
    snapshot_date is required to track recency.
    """

    cash_current_accounts: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=12, decimal_places=2
    )
    cash_savings_other: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=12, decimal_places=2
    )
    property_primary_value: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=12, decimal_places=2
    )
    property_other_value: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=12, decimal_places=2
    )
    property_appreciation_rate: Decimal = Field(
        default=Decimal("0.02"), ge=0, le=1, max_digits=5, decimal_places=4
    )
    downsize_enabled: bool = False
    downsize_year: int | None = None
    downsize_target_value: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    business_value: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=12, decimal_places=2
    )
    vehicle_value: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=12, decimal_places=2
    )
    other_assets: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=12, decimal_places=2
    )
    other_assets_label: Optional[str] = Field(default=None, max_length=200)
    other_debts: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=12, decimal_places=2
    )
    other_debts_label: Optional[str] = Field(default=None, max_length=200)
    snapshot_date: date


class NetWorthRead(BaseModel):
    """Full net worth snapshot data returned by GET endpoints.

    Includes computed totals from aggregated sources.
    """

    id: UUID
    user_id: UUID

    # Liquid assets
    cash_current_accounts: Decimal
    cash_savings_other: Decimal

    # Property
    property_primary_value: Decimal
    property_other_value: Decimal
    property_appreciation_rate: Decimal = Decimal("0.02")
    downsize_enabled: bool = False
    downsize_year: int | None = None
    downsize_target_value: Decimal | None = None

    # Other assets
    business_value: Decimal
    vehicle_value: Decimal
    other_assets: Decimal
    other_assets_label: Optional[str] = None

    # Other debts
    other_debts: Decimal
    other_debts_label: Optional[str] = None

    # Metadata
    snapshot_date: date
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NetWorthSummary(BaseModel):
    """Computed net worth with aggregated totals from all sources.

    total_assets = cash + property + business + vehicles + other_assets
                  + investments_balance + property_balances (from loans)
    total_debts = loan_remaining_balances + other_debts
    net_worth = total_assets - total_debts
    """

    # From this snapshot
    cash_total: Decimal  # cash_current_accounts + cash_savings_other
    property_total: Decimal  # property_primary_value + property_other_value
    business_value: Decimal
    vehicle_value: Decimal
    other_assets: Decimal
    other_debts: Decimal

    # From investment allocations
    investments_balance: Decimal
    investments_monthly: Decimal

    # From loans
    loans_total_remaining: Decimal
    loans_total_monthly: Decimal

    # Computed totals
    total_assets: Decimal
    total_debts: Decimal
    net_worth: Decimal

    # Breakdown for display
    assets_breakdown: dict  # {category: amount}
    debts_breakdown: dict   # {category: amount}

    snapshot_date: date
    note: str = ""  # Contextual note (e.g., "Investments at ~107k€")