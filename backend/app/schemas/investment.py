"""
Pydantic schemas for investment vehicle allocations.

- VehicleSpec: read-only vehicle metadata (from constants)
- AllocationRead: single allocation with embedded vehicle spec
- AllocationWrite: balance + contribution input
- AllAllocationsRead: all 7 vehicles with user's allocations + warnings
"""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.calculations.vehicles import validate_vehicle_key


# ── Vehicle Spec (read-only, from constants) ──────────────────────────────────


class VehicleSpec(BaseModel):
    """Read-only vehicle metadata from VEHICLE_SPECS constants."""

    key: str
    label: str
    description: str
    rate: Decimal
    tax_free: bool
    tax_rate: Decimal
    ceiling: Decimal | None
    risk: str
    color: str
    liquidity: str
    tax_deductible: bool = False
    informational: bool = False  # TASK-8.9: shown greyed/"Ajouter" when no allocation
    lock_up_years: int | None = None  # TASK-8.9: e.g. PEL=4, PEE=5

    model_config = {"from_attributes": True}


# ── Allocation Read ───────────────────────────────────────────────────────────


class AllocationRead(BaseModel):
    """A single allocation with embedded vehicle spec.

    Returned by GET /api/investments and GET /api/investments/{vehicle_key}.
    """

    id: UUID
    vehicle_key: str
    existing_balance: Decimal
    monthly_contribution: Decimal
    spec: VehicleSpec
    warning: str | None = None  # Ceiling warning if balance > ceiling

    model_config = {"from_attributes": True}


# ── Allocation Write ──────────────────────────────────────────────────────────


class AllocationWrite(BaseModel):
    """Input for creating/updating a single allocation.

    Both fields must be >= 0. Vehicle key is validated in the router
    (not here — the field isn't present in this schema since it's
    a path parameter for single PUT or in the batch wrapper).
    """

    existing_balance: Decimal = Field(
        default=Decimal("0"), ge=0, description="Current balance in EUR"
    )
    monthly_contribution: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Monthly contribution in EUR",
    )


# ── Batch Allocation Write ────────────────────────────────────────────────────


class AllocationBatchItem(BaseModel):
    """Single item in a batch allocation update."""

    vehicle_key: str
    existing_balance: Decimal = Field(default=Decimal("0"), ge=0)
    monthly_contribution: Decimal = Field(default=Decimal("0"), ge=0)

    @model_validator(mode="after")
    def check_vehicle_key(self) -> "AllocationBatchItem":
        """Validate vehicle_key against known keys."""
        if not validate_vehicle_key(self.vehicle_key):
            from app.calculations.vehicles import VEHICLE_ORDER

            raise ValueError(
                f"Invalid vehicle_key: {self.vehicle_key}. "
                f"Must be one of: {', '.join(VEHICLE_ORDER)}"
            )
        return self


class AllocationBatchWrite(BaseModel):
    """Batch update of multiple vehicle allocations at once."""

    allocations: list[AllocationBatchItem] = Field(
        min_length=1, max_length=11, description="Allocations to update"
    )


# ── List Response ─────────────────────────────────────────────────────────────


class AllAllocationsRead(BaseModel):
    """All 7 vehicle allocations for the current user.

    Always contains exactly 7 items (one per vehicle). Missing vehicles
    are auto-created with zero balances via the upsert pattern.
    """

    allocations: list[AllocationRead]
    total_existing: Decimal
    total_monthly: Decimal
    total_annual: Decimal