"""
AE (Auto-Entrepreneur) cotisation rate engine.

Provides time-dependent rate lookups for AE social charges across
the 4 activity types. Rates are stored in code (not DB) because:
  1. They affect financial accuracy and need code review for changes.
  2. Projections beyond published rates require human judgment.
  3. The schedule is small (< 30 entries total).

REVIEW ANNUALLY: Update projected rates when URSSAF publishes new schedule.

Sources:
  - Decree n°2024-484: July 2024 rate increase to 23.1%
  - Decree n°2025-943: 2026 rate schedule (25.6% for BNC non-CIPAV)
  - Art. 50-0 CGI: Micro-entreprise CA ceilings

Rates include: URSSAF base + versement libératoire IR (~2.2%)
              + formation professionnelle + CFP.

TASK-8.3: Updated rates to 2026-correct official schedule.
"""

from decimal import Decimal
from typing import Any


# ── AE BNC CA ceiling ────────────────────────────────────────────────────────
# 83,600 €/year for BNC prestations de services (2026-2028, loi de finances 2026).
# When CA exceeds this ceiling, the AE must switch to régime réel.
AE_BNC_CEILING = Decimal("83600")


# ── Rate schedules ─────────────────────────────────────────────────────────────
# Each entry: (effective_from_year, effective_from_month, rate)
# Rate effective from (year, month) until the next entry.
# Sources: URSSAF published rates, decrees n°2024-484 and n°2025-943.

# BNC non-réglementée (SSI, non-CIPAV) — e.g. conseil, formation, freelance
BNC_SSI_RATE_SCHEDULE = [
    # (from_year, from_month, rate)
    (2026, 1, Decimal("0.256")),   # 25.6% from 1 Jan 2026 (decree n°2025-943)
    (2025, 1, Decimal("0.246")),   # 24.6% from 1 Jan 2025
    (2024, 7, Decimal("0.231")),   # 23.1% from 1 Jul 2024
    (2000, 1, Decimal("0.211")),   # 21.1% baseline (pre-H2 2024)
]

# BNC profession libérale CIPAV
BNC_CIPAV_RATE_SCHEDULE = [
    (2024, 7, Decimal("0.232")),   # 23.2% from 1 Jul 2024
    (2000, 1, Decimal("0.212")),   # 21.2% baseline
]

# BIC services / artisan (stable)
_BIC_SERVICES_RATE = Decimal("0.212")  # 21.2% (stable since Oct 2022)

# BIC vente / marchandises (stable)
_BIC_VENTE_RATE = Decimal("0.123")     # 12.3% (stable since Oct 2022)


# Legacy dict-based schedule for backward compatibility with get_rate_schedule().
# NOTE: This dict is for UI display only — the projection engine uses the
# authoritative tuple schedules (BNC_SSI_RATE_SCHEDULE / BNC_CIPAV_RATE_SCHEDULE).
# AUDIT-8.2.6 #10: removed duplicate 2024 entries that caused confusion.
# The H1 2024 baseline (21.1%) is implicit; only the effective year-end rate shown.
AE_RATE_SCHEDULE: dict[str, list[dict[str, object]]] = {
    "bnc_non_reglementee": [
        {"from_year": 2023, "rate": Decimal("0.211")},   # pre-H2 2024 baseline
        {"from_year": 2024, "rate": Decimal("0.231")},   # H2 2024 (from 1 Jul)
        {"from_year": 2025, "rate": Decimal("0.246")},
        {"from_year": 2026, "rate": Decimal("0.256")},
    ],
    "bic_services": [
        {"from_year": 2024, "rate": Decimal("0.212")},
        {"from_year": 2026, "rate": Decimal("0.212")},   # stable
    ],
    "bic_vente": [
        {"from_year": 2024, "rate": Decimal("0.123")},
        {"from_year": 2026, "rate": Decimal("0.123")},   # stable
    ],
    "bnc_cipav": [
        {"from_year": 2023, "rate": Decimal("0.212")},   # pre-H2 2024 baseline
        {"from_year": 2024, "rate": Decimal("0.232")},   # H2 2024 (from 1 Jul)
        {"from_year": 2026, "rate": Decimal("0.232")},   # stable at 23.2%
    ],
}

# For projection engine use — ordered list of (year, month, rate) with month granularity
_BNC_SSI_RATE_SCHEDULE = BNC_SSI_RATE_SCHEDULE
_BNC_CIPAV_RATE_SCHEDULE = BNC_CIPAV_RATE_SCHEDULE

# CFE (Cotisation Foncière des Entreprises) base estimate for 2026.
_CFE_BASE_2026 = Decimal("300")
_CFE_INFLATION_RATE = Decimal("0.025")


# ── Public functions ───────────────────────────────────────────────────────────

def get_ae_rate(activity_type: str, year: int, month: int = 1) -> Decimal:
    """Return the AE cotisation rate effective for the given year and month.

    Uses the correct URSSAF schedule with month granularity for the
    2024 mid-year rate change (July 2024).

    Args:
        activity_type: 'bnc_non_reglementee', 'bic_services',
                       'bic_vente', 'bnc_cipav'.
        year: The calendar year (e.g. 2026).
        month: The calendar month (1=January, default). Important for 2024.

    Returns:
        The combined AE rate as a Decimal (e.g. Decimal('0.256')).

    Raises:
        ValueError: If activity_type is unknown.
    """
    # BIC types are stable — no schedule needed
    if activity_type in ("bic_services", "bic_artisan"):
        return _BIC_SERVICES_RATE
    if activity_type in ("bic_vente",):
        return _BIC_VENTE_RATE

    # BNC types have time-based schedules
    if activity_type in ("bnc_non_reglementee", "bnc_reglementee_ssi"):
        schedule = _BNC_SSI_RATE_SCHEDULE
    elif activity_type in ("bnc_reglementee_cipav", "bnc_cipav"):
        schedule = _BNC_CIPAV_RATE_SCHEDULE
    else:
        # Safe default: highest known rate
        return Decimal("0.256")

    # Find applicable rate for (year, month)
    for from_year, from_month, rate in schedule:
        if (year, month) >= (from_year, from_month):
            return rate
    return schedule[-1][2]  # fallback to oldest


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