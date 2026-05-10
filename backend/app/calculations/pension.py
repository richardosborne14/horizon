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

from datetime import date
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


# ── Pension Engine v2 (TASK-6.2) — Career-Aware Estimation ───────────────────

# AGIRC-ARRCO complementary pension constants (2024 values)
AGIRC_POINT_PRICE: Decimal = Decimal("19.63")  # Purchase price per point
AGIRC_POINT_VALUE: Decimal = Decimal("1.4159")  # Value at retirement per point
AGIRC_COTISATION_RATE: Decimal = Decimal("0.0787")  # Employee share on tranche 1

# SMIC horaire 2024 — used for trimestre validation from salaried work
# 1 trimestre per 150 × SMIC horaire of annual salary
SMIC_HORAIRE_2024: Decimal = Decimal("11.65")
SALARIE_TRIMESTRE_THRESHOLD: Decimal = Decimal("150") * SMIC_HORAIRE_2024 * Decimal("4")  # ~6,990€

# AE trimestre thresholds (2024 values)
AE_TRIMESTRE_THRESHOLDS: dict[str, Decimal] = {
    "bnc_non_reglementee": Decimal("2880"),
    "bic_services": Decimal("2540"),
    "bic_vente": Decimal("4208"),
    "bnc_cipav": Decimal("2880"),
}

# AE abattement rates (revenue pris en compte for SAM)
AE_ABATTEMENT_RATES: dict[str, Decimal] = {
    "bnc_non_reglementee": Decimal("0.34"),  # 34% abattement → 66% retained
    "bic_services": Decimal("0.50"),          # 50% abattement → 50% retained
    "bic_vente": Decimal("0.71"),             # 71% abattement → 29% retained
    "bnc_cipav": Decimal("0.34"),
}

# Unemployment: 1 trimestre per 50 days of indemnisation
# Max 4 trimestres/year
UNEMPLOYMENT_DAYS_PER_TRIMESTRE: int = 50

# Parental leave: up to 8 trimestres "gratuits" per child (AVPF)
MAX_AVPF_TRIMESTRES_TOTAL: int = 8

# Minimum pension floor (ASPA minimum vieillesse proxy)
ASPA_MONTHLY_2024: Decimal = Decimal("1012.02")  # For single person


def _compute_salarie_trimestres(
    annual_gross: Decimal,
    threshold: Decimal,
    is_full_time: bool,
    time_percentage: int,
) -> int:
    """Compute trimestres for one year of salaried work.

    1 trimestre per 150 × SMIC horaire of annual gross salary.
    Full-time CDI at 35k+ = 4 trimestres/year automatically.
    Part-time is proportional.

    Args:
        annual_gross: Gross annual salary.
        threshold: Year's threshold for 1 trimestre (inflates with SMIC).
        is_full_time: Whether full-time.
        time_percentage: Part-time percentage (100 = full time).

    Returns:
        Trimestres validated (0-4).
    """
    if annual_gross <= 0:
        return 0
    # Adjust for part-time
    adjusted_gross = annual_gross * Decimal(str(time_percentage)) / Decimal("100")
    return min(MAX_TRIMESTRES_PER_YEAR, int(float(adjusted_gross) / float(threshold)))


def _compute_ae_trimestres(
    annual_ca: Decimal,
    activity_type: str,
    threshold: Decimal,
) -> int:
    """Compute trimestres for one year of AE activity.

    Args:
        annual_ca: Annual chiffre d'affaires.
        activity_type: AE activity type.
        threshold: Year's threshold for 1 trimestre (inflates with SMIC).

    Returns:
        Trimestres validated (0-4).
    """
    if annual_ca <= 0:
        return 0
    return min(MAX_TRIMESTRES_PER_YEAR, int(float(annual_ca) / float(threshold)))


def _compute_unemployment_trimestres(
    start_date: date,
    end_date: date,
    daily_allocation: Decimal | None,
) -> int:
    """Compute trimestres from unemployment.

    1 trimestre per 50 days of indemnisation. Without daily allocation data,
    estimate 1 trimestre per full quarter of unemployment.

    Args:
        start_date: Start of unemployment period.
        end_date: End of unemployment period.
        daily_allocation: Daily ARE allocation (optional).

    Returns:
        Estimated trimestres.
    """
    from datetime import date as date_type
    days = (end_date - start_date).days
    if days <= 0:
        return 0
    if daily_allocation and daily_allocation > 0:
        # Precise: 1 per 50 days
        return min(int(days / UNEMPLOYMENT_DAYS_PER_TRIMESTRE), MAX_TRIMESTRES_PER_YEAR)
    # Without data: estimate 1 per quarter
    return min(int(days / 90), MAX_TRIMESTRES_PER_YEAR)


def _compute_avpf_trimestres(
    start_date: date,
    end_date: date,
    total_avpf_so_far: int,
) -> int:
    """Compute AVPF trimestres for parental leave.

    Up to 8 trimestres total per parent. 1 trimestre per quarter of leave.

    Args:
        start_date: Start of parental leave.
        end_date: End of parental leave.
        total_avpf_so_far: AVPF trimestres already counted.

    Returns:
        AVPF trimestres for this period.
    """
    from datetime import date as date_type
    days = (end_date - start_date).days
    if days <= 0:
        return 0
    quarters = int(days / 90)
    remaining = max(0, MAX_AVPF_TRIMESTRES_TOTAL - total_avpf_so_far)
    return min(quarters, remaining)


def _inflate_threshold(
    base_threshold: Decimal,
    year_index: int,
    inflation_rate: Decimal,
) -> Decimal:
    """Inflate a threshold for a given year from the base.

    Args:
        base_threshold: Base year threshold.
        year_index: Years from base (0 = base year).
        inflation_rate: Annual inflation rate.

    Returns:
        Inflated threshold.
    """
    return base_threshold * ((Decimal("1") + inflation_rate) ** year_index)


def estimate_monthly_pension_v2(
    birth_year: int,
    career_periods: list[dict[str, Any]],
    projected_ae_ca: list[dict[str, Any]],  # [{year, ca}]
    ae_activity_type: str,
    retirement_age: int,
    current_year: int,
    inflation_rate: Decimal = Decimal("0.025"),
) -> dict[str, Any]:
    """Career-aware pension estimation (TASK-6.2).

    Uses the full career history — salaried periods (CDI/CDD/SASU),
    AE periods (past + projected), unemployment, parental leave — to
    compute a much more accurate pension estimate.

    Args:
        birth_year: Year of birth.
        career_periods: List of career period dicts with keys:
            period_type, start_date, end_date, annual_gross,
            is_full_time, time_percentage, pension_regime.
        projected_ae_ca: Projected future AE annual CA (year, ca).
        ae_activity_type: AE activity type (e.g., bnc_non_reglementee).
        retirement_age: Planned retirement age.
        current_year: Current year for projection alignment.
        inflation_rate: Annual inflation rate for threshold revalorisation.

    Returns:
        Dict with breakdown: base_salarie, base_ae, complementaire,
        trimestres breakdown, taux, decote, confidence.
    """
    from datetime import date as date_type

    trimestres_requis = get_trimestres_requis(birth_year)

    # ── Gather income data year by year ─────────────────────────────────
    # We collect all income sources into a year-indexed structure
    # Year 0 = start of projection (current_year)
    all_salaries: dict[int, Decimal] = {}   # year → gross salary
    all_ae_ca: dict[int, Decimal] = {}       # year → AE CA
    trimestres_salarie = 0
    trimestres_ae_total = 0
    trimestres_other = 0
    avpf_so_far = 0

    ae_threshold_base = AE_TRIMESTRE_THRESHOLDS.get(
        ae_activity_type, AE_TRIMESTRE_THRESHOLDS["bnc_non_reglementee"]
    )
    salarie_threshold_base = SALARIE_TRIMESTRE_THRESHOLD

    for cp in career_periods:
        ptype = cp.get("period_type", "")
        start = cp.get("start_date")
        end = cp.get("end_date")
        annual_gross = cp.get("annual_gross", Decimal("0"))
        if isinstance(annual_gross, (int, float)):
            annual_gross = Decimal(str(annual_gross))
        is_full = cp.get("is_full_time", True)
        time_pct = cp.get("time_percentage", 100)

        if isinstance(start, str):
            start = date_type.fromisoformat(start)
        if end and isinstance(end, str):
            end = date_type.fromisoformat(end)
        if end is None:
            end = date_type.today()

        # Iterate through each year of this period
        start_yr = start.year
        end_yr = end.year
        for yr in range(start_yr, end_yr + 1):
            year_index = yr - start_yr

            if ptype in ("cdi", "cdd", "sasu", "interim", "apprenticeship"):
                # Salaried work → regime général
                threshold = _inflate_threshold(salarie_threshold_base, year_index, inflation_rate)
                t = _compute_salarie_trimestres(annual_gross, threshold, is_full, time_pct)
                trimestres_salarie += t
                if annual_gross > 0:
                    all_salaries[yr] = all_salaries.get(yr, Decimal("0")) + annual_gross

            elif ptype == "ae":
                # AE period
                threshold = _inflate_threshold(ae_threshold_base, year_index, inflation_rate)
                t = _compute_ae_trimestres(annual_gross, ae_activity_type, threshold)
                trimestres_ae_total += t
                if annual_gross > 0:
                    all_ae_ca[yr] = all_ae_ca.get(yr, Decimal("0")) + annual_gross

            elif ptype == "unemployment":
                # Unemployment
                daily = cp.get("daily_allocation")
                if isinstance(daily, (int, float)):
                    daily = Decimal(str(daily))
                t = _compute_unemployment_trimestres(start, end, daily)
                trimestres_other += t

            elif ptype == "parental_leave":
                t = _compute_avpf_trimestres(start, end, avpf_so_far)
                avpf_so_far += t
                trimestres_other += t

    # ── Add projected AE CA ────────────────────────────────────────────
    for proj in projected_ae_ca:
        yr = proj.get("year", 0)
        ca = proj.get("ca", Decimal("0"))
        if isinstance(ca, (int, float)):
            ca = Decimal(str(ca))
        year_index = yr - current_year
        threshold = _inflate_threshold(ae_threshold_base, year_index, inflation_rate)
        t = _compute_ae_trimestres(ca, ae_activity_type, threshold)
        trimestres_ae_total += t
        if ca > 0:
            all_ae_ca[yr] = all_ae_ca.get(yr, Decimal("0")) + ca

    total_trimestres = trimestres_salarie + trimestres_ae_total + trimestres_other

    # ── SAM: régime général (best 25 years, capped at PASS) ────────────
    all_income_for_sam: list[Decimal] = []

    for yr, salary in all_salaries.items():
        # PASS inflates over time
        year_index = yr - min(all_salaries.keys()) if all_salaries else 0
        pass_val = _inflate_threshold(PASS, max(0, year_index), inflation_rate)
        all_income_for_sam.append(min(salary, pass_val))

    # AE income for SAM (revenue pris en compte: CA × (1 - abattement))
    abattement_rate = AE_ABATTEMENT_RATES.get(
        ae_activity_type, AE_ABATTEMENT_RATES["bnc_non_reglementee"]
    )
    retention_rate = Decimal("1") - abattement_rate
    for yr, ca in all_ae_ca.items():
        retained = ca * retention_rate
        year_index = yr - min(all_ae_ca.keys()) if all_ae_ca else 0
        pass_val = _inflate_threshold(PASS, max(0, year_index), inflation_rate)
        all_income_for_sam.append(min(retained, pass_val))

    # Sort descending and take best 25
    all_income_for_sam.sort(reverse=True)
    best_25 = all_income_for_sam[:25]
    if best_25:
        sam = sum(best_25, Decimal("0")) / Decimal(str(len(best_25)))
    else:
        sam = Decimal("0")

    # ── Taux de pension ──────────────────────────────────────────────
    is_taux_plein_age = retirement_age >= AGE_TAUX_PLEIN_AUTO
    is_taux_plein_trimestres = total_trimestres >= trimestres_requis
    is_taux_plein = is_taux_plein_age or is_taux_plein_trimestres

    missing_trimestres = max(0, trimestres_requis - total_trimestres)
    decote_pct = Decimal("0")

    if is_taux_plein:
        taux = TAUX_PLEIN
        if retirement_age > AGE_TAUX_PLEIN_AUTO and total_trimestres > trimestres_requis:
            extra = total_trimestres - trimestres_requis
            surcote = min(Decimal(str(extra)), Decimal("20")) * SURCOTE_PER_TRIMESTRE
            taux = min(TAUX_PLEIN + surcote, Decimal("0.625"))
    else:
        missing = min(missing_trimestres, MAX_DECOTE_TRIMESTRES)
        quarters_to_67 = (AGE_TAUX_PLEIN_AUTO - retirement_age) * MAX_TRIMESTRES_PER_YEAR
        missing = min(missing, max(0, quarters_to_67))
        taux = TAUX_PLEIN - (Decimal(str(missing)) * DECOTE_PER_TRIMESTRE)
        taux = max(taux, Decimal("0.375"))
        decote_pct = Decimal(str(min(missing, MAX_DECOTE_TRIMESTRES))) * DECOTE_PER_TRIMESTRE * Decimal("100")

    # ── Base pension ─────────────────────────────────────────────────
    # Prorata: trimestres validés / trimestres requis
    prorata = min(Decimal("1"),
                  Decimal(str(total_trimestres)) / Decimal(str(trimestres_requis)))

    base_annual = sam * taux * prorata
    base_monthly = base_annual / Decimal("12")

    # ── AGIRC-ARRCO complémentaire (regime général) ──────────────────
    agirc_points = Decimal("0")
    for yr, salary in all_salaries.items():
        year_index = yr - min(all_salaries.keys()) if all_salaries else 0
        pass_val = _inflate_threshold(PASS, max(0, year_index), inflation_rate)
        capped = min(salary, pass_val)
        points_this_year = (capped * AGIRC_COTISATION_RATE) / AGIRC_POINT_PRICE
        agirc_points += points_this_year

    complementaire_salarie_monthly = (agirc_points * AGIRC_POINT_VALUE) / Decimal("12")

    # ── RCI complémentaire (AE side) ──────────────────────────────────
    rci_points = Decimal("0")
    for yr, ca in all_ae_ca.items():
        points_this_year = (ca / Decimal("1000")) * RCI_POINTS_PER_1000_CA
        rci_points += points_this_year
    complementaire_ae_monthly = (rci_points * RCI_POINT_VALUE) / Decimal("12")

    complementaire_monthly = complementaire_salarie_monthly + complementaire_ae_monthly
    total_monthly = base_monthly + complementaire_monthly

    # Determine confidence
    has_salaried = len(all_salaries) > 0
    confidence = "medium" if has_salaried else "low"

    return {
        "base_salarie_monthly": base_monthly,
        "base_ae_monthly": Decimal("0"),  # Base is unified now
        "complementaire_salarie_monthly": complementaire_salarie_monthly,
        "complementaire_ae_monthly": complementaire_ae_monthly,
        "complementaire_monthly": complementaire_monthly,
        "total_monthly": total_monthly,
        "trimestres": {
            "salarie": trimestres_salarie,
            "ae_past_projected": trimestres_ae_total,
            "other": trimestres_other,
            "total": total_trimestres,
            "required": trimestres_requis,
            "missing": missing_trimestres,
        },
        "sam": sam,
        "taux": taux,
        "decote_pct": decote_pct,
        "is_taux_plein": is_taux_plein,
        "confidence": confidence,
        "note": (
            "Estimation indicative basée sur votre parcours déclaré. "
            "Le calcul définitif relève de l'Assurance Retraite. "
            "Consultez info-retraite.fr pour un relevé de carrière officiel."
        ),
    }
