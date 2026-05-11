"""
Pydantic schemas for CareerPeriod — TASK-6.1 / TASK-7.7.

Career periods represent distinct phases of the user's or spouse's professional life.
Each period feeds into the pension engine (TASK-6.2) for trimestre and
SAM (Salaire Annuel Moyen) calculation.

TASK-7.7: Added `owner` field to distinguish user vs spouse career periods.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

# ── Constants ─────────────────────────────────────────────────────────────────


# Pension regime auto-derived from period_type if not set explicitly
REGIME_MAP: dict[str, str | None] = {
    "cdi": "general",
    "cdd": "general",
    "interim": "general",
    "ae": "ae",
    "eirl": "tns",
    "eurl": "tns",
    "sasu": "general",          # Salaried director (président salarié)
    "apprenticeship": "general",
    "internship": None,          # No trimestres unless > 2 months
    "unemployment": "general",   # Trimestres validés on allocation
    "parental_leave": "general", # Trimestres from AVPF
    "education": None,
    "foreign": "foreign",
    "other": None,
}

PeriodType = Literal[
    "cdi", "cdd", "interim", "ae", "eirl", "eurl",
    "sasu", "apprenticeship", "internship",
    "unemployment", "parental_leave",
    "education", "foreign", "other",
]


# ── Schemas ───────────────────────────────────────────────────────────────────


class CareerPeriodCreate(BaseModel):
    """Payload for creating a new career period.

    period_type and start_date are required. All other fields are optional
    but improve pension accuracy when provided. pension_regime is auto-derived
    from period_type if not set explicitly.

    start_date and end_date represent the full period inclusive on both ends.
    end_date=None means ongoing (current period).
    
    owner defaults to "user". Use "spouse" for spouse career periods.
    """

    period_type: PeriodType
    start_date: date
    end_date: Optional[date] = None
    owner: str = Field(default="user", pattern="^(user|spouse)$")
    employer_name: Optional[str] = Field(default=None, max_length=200)
    job_title: Optional[str] = Field(default=None, max_length=200)
    annual_gross: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    is_full_time: bool = True
    time_percentage: int = Field(default=100, ge=10, le=100)
    pension_regime: Optional[str] = Field(default=None, max_length=20)
    notes: Optional[str] = Field(default=None, max_length=500)
    sort_order: int = Field(default=0, ge=0)


class CareerPeriodUpdate(BaseModel):
    """Partial update — all fields optional. Only send what changed."""

    period_type: Optional[PeriodType] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    owner: Optional[str] = Field(default=None, pattern="^(user|spouse)$")
    employer_name: Optional[str] = Field(default=None, max_length=200)
    job_title: Optional[str] = Field(default=None, max_length=200)
    annual_gross: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    is_full_time: Optional[bool] = None
    time_percentage: Optional[int] = Field(default=None, ge=10, le=100)
    pension_regime: Optional[str] = Field(default=None, max_length=20)
    notes: Optional[str] = Field(default=None, max_length=500)
    sort_order: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = None


class CareerPeriodRead(BaseModel):
    """Full career period data returned by GET endpoints.

    Computed fields:
      - duration_years: float — years between start_date and end_date (or today)
      - trimestres_estimated: int — approximate trimestres validated in this period
      - has_overlap: bool — overlaps with another period (warning only)
      - overlaps_with: list[str] — IDs of overlapping periods
    """

    id: UUID
    user_id: UUID
    owner: str = "user"
    period_type: str
    start_date: date
    end_date: Optional[date] = None
    employer_name: Optional[str] = None
    job_title: Optional[str] = None
    annual_gross: Optional[Decimal] = None
    is_full_time: bool = True
    time_percentage: int = 100
    pension_regime: Optional[str] = None
    notes: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    # Computed fields
    duration_years: float = 0.0
    trimestres_estimated: int = 0
    has_overlap: bool = False
    overlaps_with: list[UUID] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class CareerSummaryResponse(BaseModel):
    """Summary of all career periods for the user.

    Used by the frontend to show "144 / 172 trimestres" progress bar
    and the timeline visualization.
    """

    total_periods: int
    total_years_worked: float
    total_trimestres_estimated: int
    trimestres_required: int
    trimestres_remaining: int
    current_period: Optional[dict] = None  # {type, since_date}
    pension_regimes: list[str] = Field(default_factory=list)
    timeline: list[dict] = Field(default_factory=list)
    # Each timeline entry: {year, period_type, trimestres, annual_gross, regime}


def resolve_pension_regime(period_type: str, explicit_regime: Optional[str] = None) -> str | None:
    """Resolve the pension regime for a period.

    Uses the explicit regime if provided, otherwise derives from period_type.
    Returns None for period types that don't contribute to French pension.

    Args:
        period_type: The career period type.
        explicit_regime: User-specified regime override (optional).

    Returns:
        The pension regime string, or None if not applicable.
    """
    if explicit_regime:
        return explicit_regime
    return REGIME_MAP.get(period_type, None)


def compute_trimestres_estimated(
    period_type: str,
    start_date: date,
    end_date: Optional[date],
    annual_gross: Optional[Decimal],
    is_full_time: bool,
    time_percentage: int,
) -> int:
    """Estimate trimestres validated during this career period.

    Simplified model — the full engine (TASK-6.2) does the precise calculation.
    This provides a quick estimate for display purposes.

    Args:
        period_type: Period type string.
        start_date: Period start.
        end_date: Period end (None = ongoing).
        annual_gross: Gross annual income.
        is_full_time: Whether full-time.
        time_percentage: Part-time percentage (100 = full time).

    Returns:
        Estimated number of trimestres.
    """
    # Compute duration in years
    end = end_date or date.today()
    if end <= start_date:
        return 0
    duration_years = (end - start_date).days / 365.25

    # Cap at 4 trimestres/year regardless
    max_possible = int(duration_years * 4) + 1

    if period_type in ("education", "internship", "foreign"):
        return 0  # No trimestres unless explicit validation

    if annual_gross is None:
        # No salary data — assume 4/year for full-time CDI/CDD,
        # 0 for other types without revenue data
        if period_type in ("cdi", "cdd", "sasu") and is_full_time:
            return min(max_possible, int(duration_years * 4))
        if period_type in ("unemployment",):
            return min(max_possible, int(duration_years * 4))  # ARE validates
        if period_type in ("parental_leave",):
            return min(8, int(duration_years * 4))  # AVPF max 8 total
        return 0

    # AE trimestre thresholds (2024 values)
    ae_thresholds: dict[str, Decimal] = {
        "ae": Decimal("2880"),        # BNC non-réglementée default
    }

    # For CDI/CDD at full-time with salary: auto 4/year
    if period_type in ("cdi", "cdd", "sasu") and annual_gross:
        # Part-time prorating
        ft_adjusted = annual_gross * Decimal(str(time_percentage)) / Decimal("100")
        if ft_adjusted >= Decimal("6990"):  # ~4 × 150 SMIC horaire
            return min(max_possible, int(duration_years * 4))

    if period_type == "ae":
        threshold = ae_thresholds.get("ae", Decimal("2880"))
        trimestres_per_year = int(float(annual_gross) / float(threshold))
        return min(max_possible, int(duration_years * min(4, trimestres_per_year)))

    return 0


def check_overlaps(
    current_id: UUID,
    current_start: date,
    current_end: Optional[date],
    all_periods: list[dict],
) -> tuple[bool, list[UUID]]:
    """Check if a period overlaps with others in the set.

    Overlap is a warning, not a blocker (e.g., CDI + AE side activity).

    Args:
        current_id: The period being checked.
        current_start: Start date of the period.
        current_end: End date (None = ongoing).
        all_periods: List of {id, start_date, end_date} for all periods.

    Returns:
        Tuple of (has_overlap: bool, overlapping_ids: list[UUID]).
    """
    c_end = current_end or date.today()
    overlapping: list[UUID] = []

    for p in all_periods:
        other_id = p["id"]
        if other_id == current_id:
            continue
        o_start = p["start_date"]
        o_end = p.get("end_date") or date.today()

        # Two periods overlap if they intersect
        if current_start <= o_end and o_start <= c_end:
            overlapping.append(other_id)

    return len(overlapping) > 0, overlapping