"""
AE (Auto-Entrepreneur) cotisation rate engine.

Provides time-dependent rate lookups for AE social charges across
the 4 activity types. Rates are stored in code (not DB) because:
  1. They affect financial accuracy and need code review for changes.
  2. Projections beyond published rates require human judgment.
  3. The schedule is small (< 30 entries total).

REVIEW ANNUALLY: Update projected rates when URSSAF publishes new schedule.

Rates include: URSSAF base + versement libératoire IR (~2.2%)
              + formation professionnelle + CFP.
"""

from decimal import Decimal
from typing import Any


# ── Rate schedules ─────────────────────────────────────────────────────────────
# Each entry: {"from_year": int, "rate": Decimal}
# Rate effective from 1 January of from_year until the next entry's from_year.
# Sources: URSSAF published rates + legislative trend projections.

AE_RATE_SCHEDULE: dict[str, list[dict[str, object]]] = {
    "bnc_non_reglementee": [
        {"from_year": 2024, "rate": Decimal("0.245")},
        {"from_year": 2025, "rate": Decimal("0.252")},
        {"from_year": 2026, "rate": Decimal("0.262")},
        {"from_year": 2027, "rate": Decimal("0.268")},   # projected
        {"from_year": 2028, "rate": Decimal("0.275")},   # projected
        {"from_year": 2030, "rate": Decimal("0.285")},   # projected
        {"from_year": 2035, "rate": Decimal("0.295")},   # projected
    ],
    "bic_services": [
        {"from_year": 2024, "rate": Decimal("0.218")},
        {"from_year": 2025, "rate": Decimal("0.224")},
        {"from_year": 2026, "rate": Decimal("0.237")},
        {"from_year": 2028, "rate": Decimal("0.245")},   # projected
        {"from_year": 2030, "rate": Decimal("0.255")},   # projected
        {"from_year": 2035, "rate": Decimal("0.265")},   # projected
    ],
    "bic_vente": [
        {"from_year": 2024, "rate": Decimal("0.132")},
        {"from_year": 2026, "rate": Decimal("0.148")},
        {"from_year": 2028, "rate": Decimal("0.155")},   # projected
        {"from_year": 2030, "rate": Decimal("0.162")},   # projected
    ],
    "bnc_cipav": [
        {"from_year": 2024, "rate": Decimal("0.232")},
        {"from_year": 2026, "rate": Decimal("0.254")},
        {"from_year": 2028, "rate": Decimal("0.262")},   # projected
        {"from_year": 2030, "rate": Decimal("0.272")},   # projected
    ],
}

# CFE (Cotisation Foncière des Entreprises) base estimate for 2026.
_CFE_BASE_2026 = Decimal("300")
_CFE_INFLATION_RATE = Decimal("0.025")


# ── Public functions ───────────────────────────────────────────────────────────

def get_ae_rate(activity_type: str, year: int) -> Decimal:
    """Return the AE cotisation rate effective for the given year.

    Walks the schedule for activity_type and returns the rate from the
    latest entry where from_year <= year. For years before the earliest
    entry, returns the earliest entry's rate. For years after the latest
    entry, returns the latest entry's rate (current projection holds).

    Args:
        activity_type: One of 'bnc_non_reglementee', 'bic_services',
                       'bic_vente', 'bnc_cipav'.
        year: The calendar year (e.g. 2026).

    Returns:
        The combined AE rate as a Decimal (e.g. Decimal('0.262')).

    Raises:
        ValueError: If activity_type is not in the schedule.
    """
    schedule = AE_RATE_SCHEDULE.get(activity_type)
    if schedule is None:
        raise ValueError(
            f"Unknown activity type: {activity_type!r}. "
            f"Valid types: {list(AE_RATE_SCHEDULE.keys())}"
        )

    # Schedule is ordered by from_year ascending. Walk until we
    # find the last entry where from_year <= target year.
    applicable_rate = schedule[0]["rate"]
    for entry in schedule:
        if int(entry["from_year"]) <= year:
            applicable_rate = entry["rate"]
        else:
            break

    return Decimal(str(applicable_rate))


def get_rate_schedule(activity_type: str) -> list[dict[str, Any]]:
    """Return the full rate schedule for a given activity type.

    Used by the frontend to render the rate schedule preview component.

    Args:
        activity_type: One of the 4 AE activity type keys.

    Returns:
        List of {"from_year": int, "rate": str} dicts, with rate
        serialised as a string for JSON.
    """
    schedule = AE_RATE_SCHEDULE.get(activity_type)
    if schedule is None:
        raise ValueError(
            f"Unknown activity type: {activity_type!r}. "
            f"Valid types: {list(AE_RATE_SCHEDULE.keys())}"
        )

    return [
        {"from_year": int(entry["from_year"]), "rate": str(entry["rate"])}
        for entry in schedule
    ]


def get_all_schedules() -> dict[str, list[dict[str, Any]]]:
    """Return all rate schedules for all activity types.

    Used for rate comparison UI (e.g. showing rates across types).

    Returns:
        Dict mapping activity_type → list of {"from_year": int, "rate": str}.
    """
    return {
        atype: get_rate_schedule(atype)
        for atype in AE_RATE_SCHEDULE
    }


def get_cfe_estimate(
    year: int,
    inflation_rate: Decimal | None = None,
) -> Decimal:
    """Estimate the CFE (Cotisation Foncière des Entreprises) for a given year.

    Base estimate of 300€ in 2026, inflation-adjusted forward and backward.

    Args:
        year: Target calendar year.
        inflation_rate: Annual inflation rate for adjustment.
                        Defaults to 2.5% if not provided.

    Returns:
        Estimated CFE in EUR as Decimal.
    """
    if inflation_rate is None:
        inflation_rate = _CFE_INFLATION_RATE

    years_diff = year - 2026
    return _CFE_BASE_2026 * ((Decimal("1") + inflation_rate) ** years_diff)


def compute_annual_charges(
    gross_annual: Decimal,
    activity_type: str,
    year: int,
) -> dict[str, Decimal]:
    """Compute the full annual AE charges breakdown.

    Args:
        gross_annual: Gross annual revenue (CA brut annuel).
        activity_type: AE activity type key.
        year: Calendar year for rate lookup.

    Returns:
        Dict with keys:
          - "rate": The combined AE rate applied.
          - "urssaf_and_others": URSSAF + VL + formation + CFP amount.
          - "cfe": CFE estimate for the year.
          - "total": Total annual charges (urssaf_and_others + cfe).
    """
    rate = get_ae_rate(activity_type, year)
    cfe = get_cfe_estimate(year)
    urssaf = gross_annual * rate
    total = urssaf + cfe

    return {
        "rate": rate,
        "urssaf_and_others": urssaf,
        "cfe": cfe,
        "total": total,
    }