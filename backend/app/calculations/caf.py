"""
CAF Auto-Estimation Service — calculate estimated monthly CAF allocations.

French families with 2+ children under 20 receive allocations familiales from
the CAF (Caisse d'Allocations Familiales). The amount depends on the number
of qualifying children and household income.

This provides a reasonable ballpark estimate that the user can override with
their real amount. The estimation is intentionally approximate:
- CAF rules are Byzantine and change yearly
- We use a simplified two-tier income test (full / half / quarter)
- Base rates are hardcoded for 2026 and revalorised at 1.5%/year
- Children qualify until age 20 (not 18)
- PAJE / Complément de libre choix is NOT included (too variable)

The projection engine (Sprint 4) uses this estimate per year when
profile.caf_override_monthly is null.
"""

from datetime import date
from decimal import Decimal


# Base monthly rates for 2026 (allocations familiales, revalorised ~1.5%/year)
CAF_2026_BASE = {
    2: Decimal("148.00"),   # 2 children
    3: Decimal("338.00"),   # 3 children
}
CAF_PER_ADDITIONAL_CHILD = Decimal("190.00")  # per child beyond 3

# Income thresholds for 2026 (annual household gross)
# Simplified from the real sliding scale: full / half / quarter
CAF_INCOME_FULL_THRESHOLD = Decimal("70000")   # + 5000/child for each child beyond 2
CAF_INCOME_HALF_THRESHOLD = Decimal("93000")   # + 5000/child

# Annual revalorisation rate (long-term average)
CAF_REVALORISATION = Decimal("0.015")

# Max child age for CAF qualification
CAF_MAX_CHILD_AGE = 20


def _compute_income_threshold(base_threshold: Decimal, num_children: int) -> Decimal:
    """
    Adjust income threshold for number of children.
    
    Threshold increases by 5 000€ per child beyond 2.
    """
    if num_children <= 2:
        return base_threshold
    return base_threshold + (Decimal("5000") * (num_children - 2))


def _base_rate_for_year(base_year: int, target_year: int, base_amount: Decimal) -> Decimal:
    """
    Revalorise a CAF base amount from base_year to target_year at 1.5%/year.
    
    Returns the revalorised amount, quantized to 2 decimal places.
    """
    if target_year <= base_year:
        return base_amount
    years = target_year - base_year
    multiplier = (Decimal("1") + CAF_REVALORISATION) ** years
    return (base_amount * multiplier).quantize(Decimal("0.01"))


def estimate_monthly_caf(
    kids_birth_dates: list[date],
    reference_year: int,
    annual_household_income: Decimal,
) -> Decimal:
    """
    Estimate monthly CAF allocations familiales for a given year.
    
    Args:
        kids_birth_dates: List of birth dates for the user's children
        reference_year: The year to estimate CAF for
        annual_household_income: Gross annual household income for that year
    
    Returns:
        Estimated monthly CAF amount (Decimal)
    
    Income tiers:
        - Under (70k + 5k/child beyond 2): full rate
        - 70k-93k: half rate
        - Over 93k: quarter rate
    
    Children qualify until age 20 (as of January 1st of reference_year).
    """
    # Count qualifying kids (under 20 on Jan 1 of reference_year)
    jan_1 = date(reference_year, 1, 1)
    qualifying_kids = []
    for birth_date in kids_birth_dates:
        age_on_jan_1 = jan_1.year - birth_date.year
        if (jan_1.month, jan_1.day) < (birth_date.month, birth_date.day):
            age_on_jan_1 -= 1
        if age_on_jan_1 < CAF_MAX_CHILD_AGE:
            qualifying_kids.append(birth_date)

    num_kids = len(qualifying_kids)

    # 0 or 1 child → no CAF
    if num_kids < 2:
        return Decimal("0")

    # Determine base amount based on number of kids
    if num_kids == 2:
        base = CAF_2026_BASE[2]
    elif num_kids == 3:
        base = CAF_2026_BASE[3]
    else:
        base = CAF_2026_BASE[3] + (CAF_PER_ADDITIONAL_CHILD * (num_kids - 3))

    # Revalorise to the reference year
    amount = _base_rate_for_year(2026, reference_year, base)

    # Income-test the amount
    income_full_threshold = _compute_income_threshold(
        CAF_INCOME_FULL_THRESHOLD, num_kids
    )
    income_half_threshold = _compute_income_threshold(
        CAF_INCOME_HALF_THRESHOLD, num_kids
    )

    if annual_household_income <= income_full_threshold:
        # Full rate
        pass
    elif annual_household_income <= income_half_threshold:
        # Half rate
        amount = (amount / Decimal("2")).quantize(Decimal("0.01"))
    else:
        # Quarter rate
        amount = (amount / Decimal("4")).quantize(Decimal("0.01"))

    return amount


def get_caf_timeline(
    kids_birth_dates: list[date],
    from_year: int,
    to_year: int,
    annual_income: Decimal,
) -> list[dict]:
    """
    Compute CAF estimates for each year in a range.
    
    Returns a timeline showing how CAF changes as kids age past 20
    and base rates are revalorised.
    
    Args:
        kids_birth_dates: List of birth dates
        from_year: Start year (inclusive)
        to_year: End year (inclusive)
        annual_income: Estimated annual household income (used for all years)
    
    Returns:
        List of {"year": int, "qualifying_kids": int, "monthly_amount": Decimal}
    """
    timeline = []
    for year in range(from_year, to_year + 1):
        amount = estimate_monthly_caf(
            kids_birth_dates=kids_birth_dates,
            reference_year=year,
            annual_household_income=annual_income,
        )
        # Count qualifying kids for this year
        jan_1 = date(year, 1, 1)
        qualifying = 0
        for birth_date in kids_birth_dates:
            age = jan_1.year - birth_date.year
            if (jan_1.month, jan_1.day) < (birth_date.month, birth_date.day):
                age -= 1
            if age < CAF_MAX_CHILD_AGE:
                qualifying += 1

        timeline.append({
            "year": year,
            "qualifying_kids": qualifying,
            "monthly_amount": str(amount),
        })

    return timeline