"""
State pension estimation for auto-entrepreneurs (TASK-5.3).

Simplified model that computes trimestres validés from CA history,
estimates retraite de base (CNAV) and retraite complémentaire (RCI),
applies décote/surcote, and returns a conservative monthly estimate.

IMPORTANT: This is an indicative estimate, NOT a replacement for
info-retraite.fr. The model errs on the side of conservative estimates.

Regime rules (2024):
  - BNC non-réglementée: 1 trimestre per ~2,880€ CA, max 4/year
  - BIC services: 1 trimestre per ~2,540€ CA, max 4/year
  - BIC vente: 1 trimestre per ~4,208€ CA, max 4/year
  - PASS = 46,368€ (Plafond Annuel de la Sécurité Sociale)
  - Trimestres requis for born 1986: 172
  - Taux plein = 50% (at 67 or with enough trimestres)
  - Décote: -1.25% per missing trimester (max 20 trimestres)
  - Surcote: +1.25% per extra trimester (after taux plein age + required)
  - SAM = average of best 25 years of annual income (capped at PASS)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any


# ── Constants ────────────────────────────────────────────────────────────────

# Trimestre validation thresholds per activity type (2024 values, € of annual CA)
TRIMESTRE_THRESHOLDS: dict[str, Decimal] = {
    "bnc_non_reglementee": Decimal("2880"),
    "bic_services": Decimal("2540"),
    "bic_vente": Decimal("4208"),
    "bnc_cipav": Decimal("2880"),
}

# PASS (Plafond Annuel de la Sécurité Sociale) — 2024 value
PASS: Decimal = Decimal("46368")

# Trimestres requis by birth year — lookup table
# Source: législation française (réforme 2023)
TRIMESTRES_REQUIS: dict[int, int] = {
    1960: 167,
    1961: 168,
    1962: 168,
    1963: 169,
    1964: 169,
    1965: 170,
    1966: 170,
    1967: 170,
    1968: 170,
    1969: 170,
    1970: 171,
    1971: 171,
    1972: 171,
    1973: 172,
    1974: 172,
    1975: 172,
    1976: 172,
    1977: 172,
    1978: 172,
    1979: 172,
    1980: 172,
    1981: 172,
    1982: 172,
    1983: 172,
    1984: 172,
    1985: 172,
    1986: 172,
    1987: 172,
    1988: 172,
    1989: 172,
    1990: 172,
    1991: 172,
    1992: 172,
    1993: 172,
    1994: 172,
    1995: 172,
    1996: 172,
    1997: 172,
    1998: 172,
    1999: 172,
    2000: 172,
}

# Maximum trimestres per year (cannot validate more than 4/year)
MAX_TRIMESTRES_PER_YEAR: int = 4

# Retraite de base taux plein
TAUX_PLEIN: Decimal = Decimal("0.50")

# Décote: reduction per missing trimester (1.25% = 0.0125)
DECOTE_PER_TRIMESTRE: Decimal = Decimal("0.0125")

# Surcote: increase per extra trimester (1.25% = 0.0125)
SURCOTE_PER_TRIMESTRE: Decimal = Decimal("0.0125")

# Maximum trimestres for décote calculation (cap at 20)
MAX_DECOTE_TRIMESTRES: int = 20

# Age at which taux plein is automatic regardless of trimestres
AGE_TAUX_PLEIN_AUTO: int = 67

# Retraite complémentaire: simplified points-based model
# Average points value per € of annual CA (very simplified)
# RCI point value ~1.35€/point in 2024
RCI_POINT_VALUE: Decimal = Decimal("1.35")
# Points earned per € of CA (approximate — ~0.25 points per 1,000€ CA)
RCI_POINTS_PER_1000_CA: Decimal = Decimal("0.25")


# ── Public API ───────────────────────────────────────────────────────────────


def get_trimestres_requis(birth_year: int) -> int:
    """Return the number of trimestres required for taux plein.

    Falls back to 172 for birth years not in the table (default for post-1973).

    Args:
        birth_year: Year of birth.

    Returns:
        Required trimestres for full-rate pension.
    """
    return TRIMESTRES_REQUIS.get(birth_year, 172)


def estimate_monthly_pension(
    birth_year: int,
    activity_type: str,
    ca_history: list[Decimal],  # annual CA for each year of career
    retirement_age: int,
    inflation_rate: Decimal = Decimal("0.025"),
) -> dict[str, Any]:
    """Estimate monthly state pension for an auto-entrepreneur.

    Computes trimestres from CA history, estimates retraite de base
    (CNAV) and retraite complémentaire (RCI), applies décote/surcote,
    and returns a conservative monthly estimate.

    Args:
        birth_year: Year of birth (used for trimestres requis lookup).
        activity_type: AE activity type (bnc_non_reglementee, bic_services, bic_vente).
        ca_history: List of annual CA values (one per year of career).
        retirement_age: Age at which the user plans to retire.
        inflation_rate: Annual inflation rate for threshold revalorisation (default 2.5%).

    Returns:
        Dict with keys:
          - base_monthly: estimated retraite de base monthly amount
          - complementaire_monthly: estimated retraite complémentaire monthly
          - total_monthly: base + complémentaire
          - trimestres_valides: total trimestres validated
          - trimestres_requis: required trimestres for taux plein
          - taux: applied pension rate (0.50 at taux plein, less with décote)
          - confidence: "low" — always, we're estimating
          - is_taux_plein: whether taux plein is reached
    """
    if not ca_history:
        return {
            "base_monthly": Decimal("0"),
            "complementaire_monthly": Decimal("0"),
            "total_monthly": Decimal("0"),
            "trimestres_valides": 0,
            "trimestres_requis": get_trimestres_requis(birth_year),
            "taux": Decimal("0"),
            "confidence": "low",
            "is_taux_plein": False,
        }

    # Get the trimestre threshold for this activity type
    threshold = TRIMESTRE_THRESHOLDS.get(
        activity_type, TRIMESTRE_THRESHOLDS["bnc_non_reglementee"]
    )

    trimestres_requis = get_trimestres_requis(birth_year)

    # ── Compute trimestres validés from CA history ────────────────────
    total_trimestres = 0
    best_25_ca: list[Decimal] = []

    for i, ca in enumerate(ca_history):
        # Threshold is revalorised with inflation
        reval_threshold = threshold * (
            (Decimal("1") + inflation_rate) ** i
        )
        # Trimestres this year: min(4, floor(CA / threshold))
        trimestres_this_year = min(
            MAX_TRIMESTRES_PER_YEAR,
            int(float(ca) / float(reval_threshold)),
        )
        total_trimestres += trimestres_this_year

        # Track CA for SAM calculation (best 25 years, capped at PASS)
        best_25_ca.append(min(ca, PASS))

    # Sort descending and take best 25
    best_25_ca.sort(reverse=True)
    best_25_ca = best_25_ca[:25]

    # ── SAM: Salaire Annuel Moyen of best 25 years ───────────────────
    if best_25_ca:
        sam = sum(best_25_ca, Decimal("0")) / Decimal(str(len(best_25_ca)))
    else:
        sam = Decimal("0")

    # ── Taux de pension ──────────────────────────────────────────────
    # Determine if taux plein is reached
    is_taux_plein_age = retirement_age >= AGE_TAUX_PLEIN_AUTO
    is_taux_plein_trimestres = total_trimestres >= trimestres_requis
    is_taux_plein = is_taux_plein_age or is_taux_plein_trimestres

    if is_taux_plein:
        taux = TAUX_PLEIN
        # Surcote if continuing past required trimestres
        if is_taux_plein_trimestres and not is_taux_plein_age:
            # Only surcote if retiring after having enough trimestres but before auto age
            # This is not the typical case — simplified: no surcote in MVP
            pass
        # Surcote: extra trimestres beyond required after taux plein age
        if retirement_age > AGE_TAUX_PLEIN_AUTO and total_trimestres > trimestres_requis:
            extra = total_trimestres - trimestres_requis
            surcote = min(Decimal(str(extra)), Decimal("20")) * SURCOTE_PER_TRIMESTRE
            taux = min(TAUX_PLEIN + surcote, Decimal("0.625"))  # cap at 62.5%
    else:
        # Décote: missing trimestres × 1.25%, capped at 20
        missing = min(
            trimestres_requis - total_trimestres,
            MAX_DECOTE_TRIMESTRES,
        )
        taux = TAUX_PLEIN - (Decimal(str(missing)) * DECOTE_PER_TRIMESTRE)
        taux = max(taux, Decimal("0.375"))  # floor at 37.5%

    # ── Retraite de base mensuelle ──────────────────────────────────
    base_annual = sam * taux * (
        Decimal(str(min(total_trimestres, trimestres_requis)))
        / Decimal(str(trimestres_requis))
    )
    base_monthly = base_annual / Decimal("12")

    # ── Retraite complémentaire (RCI) ────────────────────────────────
    # Points-based: each year earns points based on CA
    total_points = Decimal("0")
    for i, ca in enumerate(ca_history):
        # Points per year = (CA / 1000) * POINTS_PER_1000_CA
        # This is very simplified — real RCI uses brackets
        points_this_year = (ca / Decimal("1000")) * RCI_POINTS_PER_1000_CA
        total_points += points_this_year

    # Value at retirement: points × point_value (revalorised)
    complementaire_annual = total_points * RCI_POINT_VALUE
    complementaire_monthly = complementaire_annual / Decimal("12")

    # ── Total ───────────────────────────────────────────────────────
    total_monthly = base_monthly + complementaire_monthly

    return {
        "base_monthly": base_monthly.quantize(Decimal("0.01")),
        "complementaire_monthly": complementaire_monthly.quantize(Decimal("0.01")),
        "total_monthly": total_monthly.quantize(Decimal("0.01")),
        "trimestres_valides": total_trimestres,
        "trimestres_requis": trimestres_requis,
        "taux": taux.quantize(Decimal("0.0001")),
        "confidence": "low",
        "is_taux_plein": is_taux_plein,
    }