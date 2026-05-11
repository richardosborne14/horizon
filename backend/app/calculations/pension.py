"""
State pension estimation for auto-entrepreneurs (TASK-5.3 / TASK-7.7).

Simplified model that computes trimestres validés from CA history,
estimates retraite de base (CNAV) and retraite complémentaire (RCI),
applies décote/surcote, and returns a conservative monthly estimate.

IMPORTANT: This is an indicative estimate, NOT a replacement for
info-retraite.fr. The model errs on the side of conservative estimates.

TASK-7.7: Added CC (conjointe collaboratrice) trimestre calculation
and combined pension endpoint for household (user + spouse).

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
    1960: 167, 1961: 168, 1962: 168, 1963: 169, 1964: 169,
    1965: 170, 1966: 170, 1967: 170, 1968: 170, 1969: 170,
    1970: 171, 1971: 171, 1972: 171, 1973: 172, 1974: 172,
    1975: 172, 1976: 172, 1977: 172, 1978: 172, 1979: 172,
    1980: 172, 1981: 172, 1982: 172, 1983: 172, 1984: 172,
    1985: 172, 1986: 172, 1987: 172, 1988: 172, 1989: 172,
    1990: 172, 1991: 172, 1992: 172, 1993: 172, 1994: 172,
    1995: 172, 1996: 172, 1997: 172, 1998: 172, 1999: 172,
    2000: 172,
}

MAX_TRIMESTRES_PER_YEAR: int = 4
TAUX_PLEIN: Decimal = Decimal("0.50")
DECOTE_PER_TRIMESTRE: Decimal = Decimal("0.0125")
SURCOTE_PER_TRIMESTRE: Decimal = Decimal("0.0125")
MAX_DECOTE_TRIMESTRES: int = 20
AGE_TAUX_PLEIN_AUTO: int = 67
RCI_POINT_VALUE: Decimal = Decimal("1.35")
RCI_POINTS_PER_1000_CA: Decimal = Decimal("0.25")

# ── Public API ───────────────────────────────────────────────────────────────


def get_trimestres_requis(birth_year: int) -> int:
    """Return the number of trimestres required for taux plein."""
    return TRIMESTRES_REQUIS.get(birth_year, 172)


def estimate_monthly_pension(
    birth_year: int,
    activity_type: str,
    ca_history: list[Decimal],
    retirement_age: int,
    inflation_rate: Decimal = Decimal("0.025"),
) -> dict[str, Any]:
    """Estimate monthly state pension for an auto-entrepreneur."""
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
    threshold = TRIMESTRE_THRESHOLDS.get(
        activity_type, TRIMESTRE_THRESHOLDS["bnc_non_reglementee"]
    )
    trimestres_requis = get_trimestres_requis(birth_year)
    total_trimestres = 0
    best_25_ca: list[Decimal] = []
    for i, ca in enumerate(ca_history):
        reval_threshold = threshold * ((Decimal("1") + inflation_rate) ** i)
        trimestres_this_year = min(MAX_TRIMESTRES_PER_YEAR, int(float(ca) / float(reval_threshold)))
        total_trimestres += trimestres_this_year
        best_25_ca.append(min(ca, PASS))
    best_25_ca.sort(reverse=True)
    best_25_ca = best_25_ca[:25]
    sam = sum(best_25_ca, Decimal("0")) / Decimal(str(len(best_25_ca))) if best_25_ca else Decimal("0")
    is_taux_plein_age = retirement_age >= AGE_TAUX_PLEIN_AUTO
    is_taux_plein_trimestres = total_trimestres >= trimestres_requis
    is_taux_plein = is_taux_plein_age or is_taux_plein_trimestres
    if is_taux_plein:
        taux = TAUX_PLEIN
        if retirement_age > AGE_TAUX_PLEIN_AUTO and total_trimestres > trimestres_requis:
            extra = total_trimestres - trimestres_requis
            surcote = min(Decimal(str(extra)), Decimal("20")) * SURCOTE_PER_TRIMESTRE
            taux = min(TAUX_PLEIN + surcote, Decimal("0.625"))
    else:
        missing = min(trimestres_requis - total_trimestres, MAX_DECOTE_TRIMESTRES)
        taux = TAUX_PLEIN - (Decimal(str(missing)) * DECOTE_PER_TRIMESTRE)
        taux = max(taux, Decimal("0.375"))
    base_annual = sam * taux * (Decimal(str(min(total_trimestres, trimestres_requis))) / Decimal(str(trimestres_requis)))
    base_monthly = base_annual / Decimal("12")
    total_points = Decimal("0")
    for ca in ca_history:
        points_this_year = (ca / Decimal("1000")) * RCI_POINTS_PER_1000_CA
        total_points += points_this_year
    complementaire_annual = total_points * RCI_POINT_VALUE
    complementaire_monthly = complementaire_annual / Decimal("12")
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

AGIRC_POINT_PRICE: Decimal = Decimal("19.63")
AGIRC_POINT_VALUE: Decimal = Decimal("1.4159")
AGIRC_COTISATION_RATE: Decimal = Decimal("0.0787")
SMIC_HORAIRE_2024: Decimal = Decimal("11.65")
SALARIE_TRIMESTRE_THRESHOLD: Decimal = Decimal("150") * SMIC_HORAIRE_2024 * Decimal("4")

AE_TRIMESTRE_THRESHOLDS: dict[str, Decimal] = {
    "bnc_non_reglementee": Decimal("2880"),
    "bic_services": Decimal("2540"),
    "bic_vente": Decimal("4208"),
    "bnc_cipav": Decimal("2880"),
}

AE_ABATTEMENT_RATES: dict[str, Decimal] = {
    "bnc_non_reglementee": Decimal("0.34"),
    "bic_services": Decimal("0.50"),
    "bic_vente": Decimal("0.71"),
    "bnc_cipav": Decimal("0.34"),
}

UNEMPLOYMENT_DAYS_PER_TRIMESTRE: int = 50
MAX_AVPF_TRIMESTRES_TOTAL: int = 8
ASPA_MONTHLY_2024: Decimal = Decimal("1012.02")

# ── CC (Conjointe Collaboratrice) constants (TASK-7.7) ───────────────────────
# SMIC horaire 2024 threshold: 600 × SMIC = 6,990€ annual cotisation base
CC_SMIC_TRIM_THRESHOLD: Decimal = Decimal("600") * SMIC_HORAIRE_2024  # ~6,990€


def _compute_salarie_trimestres(
    annual_gross: Decimal, threshold: Decimal, is_full_time: bool, time_percentage: int,
) -> int:
    if annual_gross <= 0:
        return 0
    adjusted_gross = annual_gross * Decimal(str(time_percentage)) / Decimal("100")
    return min(MAX_TRIMESTRES_PER_YEAR, int(float(adjusted_gross) / float(threshold)))


def _compute_ae_trimestres(
    annual_ca: Decimal, activity_type: str, threshold: Decimal,
) -> int:
    if annual_ca <= 0:
        return 0
    return min(MAX_TRIMESTRES_PER_YEAR, int(float(annual_ca) / float(threshold)))


def _compute_unemployment_trimestres(
    start_date: date, end_date: date, daily_allocation: Decimal | None,
) -> int:
    days = (end_date - start_date).days
    if days <= 0:
        return 0
    if daily_allocation and daily_allocation > 0:
        return min(int(days / UNEMPLOYMENT_DAYS_PER_TRIMESTRE), MAX_TRIMESTRES_PER_YEAR)
    return min(int(days / 90), MAX_TRIMESTRES_PER_YEAR)


def _compute_avpf_trimestres(
    start_date: date, end_date: date, total_avpf_so_far: int,
) -> int:
    days = (end_date - start_date).days
    if days <= 0:
        return 0
    quarters = int(days / 90)
    remaining = max(0, MAX_AVPF_TRIMESTRES_TOTAL - total_avpf_so_far)
    return min(quarters, remaining)


def _inflate_threshold(
    base_threshold: Decimal, year_index: int, inflation_rate: Decimal,
) -> Decimal:
    return base_threshold * ((Decimal("1") + inflation_rate) ** year_index)


def estimate_monthly_pension_v2(
    birth_year: int,
    career_periods: list[dict[str, Any]],
    projected_ae_ca: list[dict[str, Any]],
    ae_activity_type: str,
    retirement_age: int,
    current_year: int,
    inflation_rate: Decimal = Decimal("0.025"),
) -> dict[str, Any]:
    """Career-aware pension estimation (TASK-6.2)."""
    from datetime import date as date_type
    trimestres_requis = get_trimestres_requis(birth_year)
    all_salaries: dict[int, Decimal] = {}
    all_ae_ca: dict[int, Decimal] = {}
    trimestres_salarie = 0
    trimestres_ae_total = 0
    trimestres_other = 0
    avpf_so_far = 0
    ae_threshold_base = AE_TRIMESTRE_THRESHOLDS.get(ae_activity_type, AE_TRIMESTRE_THRESHOLDS["bnc_non_reglementee"])
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
        start_yr = start.year
        end_yr = end.year
        for yr in range(start_yr, end_yr + 1):
            year_index = yr - start_yr
            if ptype in ("cdi", "cdd", "sasu", "interim", "apprenticeship"):
                threshold = _inflate_threshold(salarie_threshold_base, year_index, inflation_rate)
                t = _compute_salarie_trimestres(annual_gross, threshold, is_full, time_pct)
                trimestres_salarie += t
                if annual_gross > 0:
                    all_salaries[yr] = all_salaries.get(yr, Decimal("0")) + annual_gross
            elif ptype == "ae":
                threshold = _inflate_threshold(ae_threshold_base, year_index, inflation_rate)
                t = _compute_ae_trimestres(annual_gross, ae_activity_type, threshold)
                trimestres_ae_total += t
                if annual_gross > 0:
                    all_ae_ca[yr] = all_ae_ca.get(yr, Decimal("0")) + annual_gross
            elif ptype == "unemployment":
                daily = cp.get("daily_allocation")
                if isinstance(daily, (int, float)):
                    daily = Decimal(str(daily))
                t = _compute_unemployment_trimestres(start, end, daily)
                trimestres_other += t
            elif ptype == "parental_leave":
                t = _compute_avpf_trimestres(start, end, avpf_so_far)
                avpf_so_far += t
                trimestres_other += t

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

    all_income_for_sam: list[Decimal] = []
    for yr, salary in all_salaries.items():
        year_index = yr - min(all_salaries.keys()) if all_salaries else 0
        pass_val = _inflate_threshold(PASS, max(0, year_index), inflation_rate)
        all_income_for_sam.append(min(salary, pass_val))
    abattement_rate = AE_ABATTEMENT_RATES.get(ae_activity_type, AE_ABATTEMENT_RATES["bnc_non_reglementee"])
    retention_rate = Decimal("1") - abattement_rate
    for yr, ca in all_ae_ca.items():
        retained = ca * retention_rate
        year_index = yr - min(all_ae_ca.keys()) if all_ae_ca else 0
        pass_val = _inflate_threshold(PASS, max(0, year_index), inflation_rate)
        all_income_for_sam.append(min(retained, pass_val))
    all_income_for_sam.sort(reverse=True)
    best_25 = all_income_for_sam[:25]
    sam = sum(best_25, Decimal("0")) / Decimal(str(len(best_25))) if best_25 else Decimal("0")

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

    prorata = min(Decimal("1"), Decimal(str(total_trimestres)) / Decimal(str(trimestres_requis)))
    base_annual = sam * taux * prorata
    base_monthly = base_annual / Decimal("12")

    agirc_points = Decimal("0")
    for yr, salary in all_salaries.items():
        year_index = yr - min(all_salaries.keys()) if all_salaries else 0
        pass_val = _inflate_threshold(PASS, max(0, year_index), inflation_rate)
        capped = min(salary, pass_val)
        points_this_year = (capped * AGIRC_COTISATION_RATE) / AGIRC_POINT_PRICE
        agirc_points += points_this_year
    complementaire_salarie_monthly = (agirc_points * AGIRC_POINT_VALUE) / Decimal("12")

    rci_points = Decimal("0")
    for yr, ca in all_ae_ca.items():
        points_this_year = (ca / Decimal("1000")) * RCI_POINTS_PER_1000_CA
        rci_points += points_this_year
    complementaire_ae_monthly = (rci_points * RCI_POINT_VALUE) / Decimal("12")
    complementaire_monthly = complementaire_salarie_monthly + complementaire_ae_monthly
    total_monthly = base_monthly + complementaire_monthly
    confidence = "medium" if len(all_salaries) > 0 else "low"

    return {
        "base_salarie_monthly": base_monthly,
        "base_ae_monthly": Decimal("0"),
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


# ── CC Trimestre Calculation (TASK-7.7) ──────────────────────────────────────


def estimate_cc_trimestres_per_year(cc_option: str, user_ca: Decimal) -> int:
    """Estimate trimestres validated per year for a Conjointe Collaboratrice.

    CC validates trimestres based on the cotisation base (assiette) vs the
    SMIC threshold. If the annual cotisation base >= 4 × SMIC trimestre
    threshold (~6,990€ in 2024), the CC earns 4 trimestres. Otherwise
    proportional.

    Cotisation base options:
        "tiers_plafond": 1/3 of PASS (SS plafond)
        "moitie_plafond": 1/2 of PASS
        "tiers_revenu": 1/3 of user's annual CA
        "moitie_revenu": 1/2 of user's annual CA

    Args:
        cc_option: The CC cotisation option (tiers_plafond, moitie_plafond,
                   tiers_revenu, moitie_revenu).
        user_ca: The user's annual chiffre d'affaires.

    Returns:
        Number of trimestres validated (0-4).
    """
    PLAFOND_SS = Decimal("46368")

    bases: dict[str, Decimal] = {
        "tiers_plafond": PLAFOND_SS / Decimal("3"),
        "moitie_plafond": PLAFOND_SS / Decimal("2"),
        "tiers_revenu": user_ca / Decimal("3"),
        "moitie_revenu": user_ca / Decimal("2"),
    }

    base = bases.get(cc_option, Decimal("0"))
    if base <= 0:
        return 0

    # 4 trimestres if base >= 4 × SMIC threshold
    if base >= CC_SMIC_TRIM_THRESHOLD * 4:
        return 4

    return min(4, int(float(base) / float(CC_SMIC_TRIM_THRESHOLD)))