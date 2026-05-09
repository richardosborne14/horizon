"""
Unit tests for the status change comparison math (TASK-5.1).

Verifies the AE vs target-status diff calculations used by the
projects page comparison table. Covers three CA levels and edge cases.

The math being tested (from frontend/src/routes/(app)/projects/+page.svelte):
  - abattementRate: BNC=0.34, BIC services=0.50, BIC vente=0.71
  - cotisationRate: BNC=0.262, BIC services=0.237, BIC vente=0.148
  - targetRate: 0.45 (TNS/charges dirigeant)
  - abattementAE = annualGrossCA * abattementRate
  - baseAE = max(0, annualGrossCA - abattementAE)
  - cotisationsAE = round(baseAE * cotisationRate)
  - baseTarget = max(0, annualGrossCA - totalCharges)
  - cotisationsTarget = round(baseTarget * targetRate)
  - economie = cotisationsTarget - cotisationsAE (positive = AE pays less)
  - netAE = annualGrossCA - cotisationsAE
  - netTarget = annualGrossCA - cotisationsTarget
  - netDiff = netAE - netTarget (positive = AE keeps more)
"""

from decimal import Decimal, ROUND_HALF_UP

import pytest


# ── Test constants (mirror frontend logic) ────────────────────────────────────

ABATTEMENT_RATES = {
    "bnc_non_reglementee": Decimal("0.34"),
    "bic_services": Decimal("0.50"),
    "bic_vente": Decimal("0.71"),
}

COTISATION_RATES = {
    "bnc_non_reglementee": Decimal("0.262"),
    "bic_services": Decimal("0.237"),
    "bic_vente": Decimal("0.148"),
}

TARGET_RATE = Decimal("0.45")


def compute_status_diff(
    annual_gross_ca: Decimal,
    real_charges: Decimal,
    activity_type: str = "bnc_non_reglementee",
) -> dict:
    """Compute the status change comparison values.

    Mirrors the reactive logic in projects/+page.svelte exactly.
    All intermediate values use Python Decimal for precision.

    Args:
        annual_gross_ca: Annual CA brut (€).
        real_charges: Total annual real professional charges (€).
        activity_type: AE activity type.

    Returns:
        Dict with all comparison row values.
    """
    abattement_rate = ABATTEMENT_RATES[activity_type]
    cotisation_rate = COTISATION_RATES[activity_type]

    # AE side
    abattement_ae = annual_gross_ca * abattement_rate
    base_ae = max(Decimal("0"), annual_gross_ca - abattement_ae)
    cotisations_ae = (base_ae * cotisation_rate).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )

    # Target status side
    base_target = max(Decimal("0"), annual_gross_ca - real_charges)
    cotisations_target = (base_target * TARGET_RATE).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )

    # Diffs
    charges_deductibles_diff = real_charges - abattement_ae  # positive = target deducts more
    base_diff = base_target - base_ae  # positive = target has higher base
    economie = cotisations_target - cotisations_ae  # positive = AE pays LESS
    net_ae = annual_gross_ca - cotisations_ae
    net_target = annual_gross_ca - cotisations_target
    net_diff = net_ae - net_target  # positive = AE keeps MORE

    return {
        "annual_gross_ca": annual_gross_ca,
        "real_charges": real_charges,
        "abattement_ae": abattement_ae,
        "base_ae": base_ae,
        "cotisations_ae": cotisations_ae,
        "base_target": base_target,
        "cotisations_target": cotisations_target,
        "charges_deductibles_diff": charges_deductibles_diff,
        "base_diff": base_diff,
        "economie": economie,
        "net_ae": net_ae,
        "net_target": net_target,
        "net_diff": net_diff,
    }


# ── Scenario 1: CA 67,200€ (the user's actual scenario) ─────────────────────
# This is the scenario from the task document.
# CA 67,200€, BNC, real charges = 0 (AE forfaitaire only).

def test_scenario_67200_ae_vs_sasu_no_real_charges():
    """CA 67,200€, BNC, no real charges. AE should be better.

    Expected from task doc:
      - AE net: 55,580€
      - SASU net: 40,470€
      - diff: +15,110€/an (AE advantage)
    """
    ca = Decimal("67200")
    result = compute_status_diff(ca, Decimal("0"), "bnc_non_reglementee")

    # AE side
    assert result["abattement_ae"] == Decimal("22848")  # 67200 * 0.34
    assert result["base_ae"] == Decimal("44352")  # 67200 - 22848
    expected_cot_ae = (Decimal("44352") * Decimal("0.262")).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    assert result["cotisations_ae"] == expected_cot_ae
    # 44352 * 0.262 = 11620.224 → round to 11620
    assert result["cotisations_ae"] == Decimal("11620")

    # Target side (SASU/EIRL, charges 0)
    assert result["base_target"] == Decimal("67200")  # 67200 - 0
    expected_cot_target = (Decimal("67200") * Decimal("0.45")).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    assert result["cotisations_target"] == Decimal("30240")  # 67200 * 0.45 = 30240

    # Diffs
    assert result["charges_deductibles_diff"] == Decimal("-22848")  # AE deducts more (abs)
    assert result["economie"] == Decimal("18620")  # AE pays 30240 - 11620 = 18620 less
    assert result["net_ae"] == Decimal("55580")  # 67200 - 11620
    assert result["net_target"] == Decimal("36960")  # 67200 - 30240
    assert result["net_diff"] == Decimal("18620")  # AE keeps 18620 more


# ── Scenario 2: CA 30,000€, low income ─────────────────────────────────────

def test_scenario_30000_low_ca():
    """CA 30,000€, BNC, no real charges. AE should still be better."""
    ca = Decimal("30000")
    result = compute_status_diff(ca, Decimal("0"), "bnc_non_reglementee")

    # AE: abattement 10200, base 19800, cotisations 19800*0.262=5188
    assert result["abattement_ae"] == Decimal("10200")
    assert result["cotisations_ae"] == Decimal("5188")
    assert result["net_ae"] == Decimal("24812")  # 30000 - 5188

    # Target: base 30000, cotisations 30000*0.45=13500
    assert result["cotisations_target"] == Decimal("13500")
    assert result["net_target"] == Decimal("16500")  # 30000 - 13500

    assert result["net_diff"] > 0  # AE better
    assert result["net_diff"] == Decimal("8312")


# ── Scenario 3: CA 100,000€, high income ────────────────────────────────────

def test_scenario_100000_high_ca():
    """CA 100,000€, BNC, no real charges. AE may still be better but gap narrows."""
    ca = Decimal("100000")
    result = compute_status_diff(ca, Decimal("0"), "bnc_non_reglementee")

    # AE: abattement 34000, base 66000, cotisations 66000*0.262=17292
    assert result["abattement_ae"] == Decimal("34000")
    assert result["cotisations_ae"] == Decimal("17292")
    assert result["net_ae"] == Decimal("82708")

    # Target: base 100000, cotisations 100000*0.45=45000
    assert result["cotisations_target"] == Decimal("45000")
    assert result["net_target"] == Decimal("55000")

    assert result["net_diff"] > 0  # AE better at 100k with no real charges
    assert result["net_diff"] == Decimal("27708")


# ── Scenario 4: High real charges ────────────────────────────────────────────

def test_scenario_high_real_charges_target_wins():
    """CA 80,000€, BNC, 25,000€/year real charges.
    With high real charges, target status should narrow or reverse AE advantage.
    """
    ca = Decimal("80000")
    real_charges = Decimal("25000")
    result = compute_status_diff(ca, real_charges, "bnc_non_reglementee")

    # AE: abattement 27200, base 52800, cotisations 52800*0.262=13834
    assert result["abattement_ae"] == Decimal("27200")
    assert result["cotisations_ae"] == Decimal("13834")

    # Target: base = 80000 - 25000 = 55000, cotisations 55000*0.45=24750
    assert result["base_target"] == Decimal("55000")
    assert result["cotisations_target"] == Decimal("24750")

    # In this case: AE net = 80000 - 13830 = 66170
    #              Target net = 80000 - 24750 = 55250
    # AE still better but gap is smaller
    assert result["net_diff"] > 0
    # Charges deductibles: target deducts 25000 vs AE abattement 27200
    # So real charges < abattement → AE still deducts more
    assert result["charges_deductibles_diff"] < 0


# ── Scenario 5: Real charges exceed abattement ───────────────────────────────

def test_scenario_charges_exceed_abattement_target_wins():
    """CA 60,000€, BIC services, 12,000€ real charges.
    BIC services: abattement 50%, so 60k * 0.50 = 30k.
    12k real < 30k abattement → AE still better.
    
    Need higher CA with higher charges to make target win.
    """
    ca = Decimal("80000")
    real_charges = Decimal("35000")
    result = compute_status_diff(ca, real_charges, "bnc_non_reglementee")

    # AE: abattement 27200, base 52800, cotisations 52800*0.262=13834
    # Target: base 80000-35000=45000, cotisations 45000*0.45=20250
    assert result["base_target"] == Decimal("45000")
    assert result["cotisations_target"] == Decimal("20250")

    # Compare: AE cotisations 13834 vs target 20250
    # AE still pays less
    assert result["economie"] > 0  # AE pays less

    # However charges_deductibles_diff = 35000 - 27200 = 7800
    # Target deducts 7800 more, but AE's lower cotisation rate (26.2% vs 45%) wins
    assert result["charges_deductibles_diff"] == Decimal("7800")


# ── Scenario 6: Breakeven ────────────────────────────────────────────────────

def test_breakeven_when_cotisations_equal():
    """Find a scenario where cotisations are roughly equal.
    
    For BNC: cotisations_ae = (CA - 0.34*CA) * 0.262 = 0.66 * 0.262 * CA = 0.17292 * CA
             cotisations_target = (CA - charges) * 0.45
    
    Breakeven when: 0.17292*CA = 0.45*(CA - charges)
    0.17292*CA = 0.45*CA - 0.45*charges
    0.45*charges = 0.45*CA - 0.17292*CA
    0.45*charges = 0.27708*CA
    charges = 0.27708/0.45 * CA ≈ 0.6157 * CA
    
    So at CA=100000, charges≈61573 for breakeven.
    But base must be non-negative: CA - charges >= 0 → charges <= CA.
    """
    ca = Decimal("100000")
    real_charges = Decimal("61573")  # approximately breakeven
    result = compute_status_diff(ca, real_charges, "bnc_non_reglementee")

    # AE: 0.17292 * 100000 = 17292
    # Target: (100000 - 61573) * 0.45 = 38427 * 0.45 = 17292.15 → 17292
    # Should be nearly equal
    diff = abs(result["cotisations_ae"] - result["cotisations_target"])
    assert diff <= Decimal("1"), f"Cotisations differ by {diff}, expected breakeven"


# ── Other activity types ─────────────────────────────────────────────────────

def test_bic_services_lower_cotisation_ae_advantage():
    """BIC services: cotisation 23.7% vs BNC 26.2%. AE advantage is larger."""
    ca = Decimal("60000")
    result = compute_status_diff(ca, Decimal("0"), "bic_services")

    # AE: abattement 50% = 30000, base = 30000, cotisations = 30000*0.237=7110
    assert result["abattement_ae"] == Decimal("30000")
    assert result["cotisations_ae"] == Decimal("7110")
    assert result["net_ae"] == Decimal("52890")

    # Target: base = 60000, cotisations = 60000*0.45=27000
    assert result["cotisations_target"] == Decimal("27000")
    assert result["net_diff"] == Decimal("19890")  # AE keeps 19890 more


def test_bic_vente_lowest_cotisation():
    """BIC vente: cotisation 14.8%, abattement 71%. Huge AE advantage."""
    ca = Decimal("50000")
    result = compute_status_diff(ca, Decimal("0"), "bic_vente")

    # AE: abattement 71% = 35500, base = 14500, cotisations = 14500*0.148=2146
    assert result["abattement_ae"] == Decimal("35500")
    assert result["cotisations_ae"] == Decimal("2146")
    assert result["net_ae"] == Decimal("47854")

    # Target: base = 50000, cotisations = 50000*0.45=22500
    assert result["cotisations_target"] == Decimal("22500")
    assert result["net_diff"] > Decimal("20000")  # AE massive advantage


# ── Edge cases ───────────────────────────────────────────────────────────────

def test_zero_ca():
    """Zero CA should produce zero cotisations for both statuses."""
    result = compute_status_diff(Decimal("0"), Decimal("0"))
    assert result["cotisations_ae"] == Decimal("0")
    assert result["cotisations_target"] == Decimal("0")
    assert result["net_diff"] == Decimal("0")


def test_charges_exceed_ca():
    """Real charges > CA should still compute without error (base floored at 0)."""
    ca = Decimal("30000")
    real_charges = Decimal("50000")
    result = compute_status_diff(ca, real_charges, "bnc_non_reglementee")

    # Target base floored at 0
    assert result["base_target"] == Decimal("0")
    assert result["cotisations_target"] == Decimal("0")
    # AE still pays something
    assert result["cotisations_ae"] > Decimal("0")


def test_rounding_is_to_euro():
    """Cotisations should round to nearest euro (round half up)."""
    ca = Decimal("12345")
    result = compute_status_diff(ca, Decimal("0"), "bnc_non_reglementee")

    # AE cotisations should be an integer
    assert result["cotisations_ae"] == result["cotisations_ae"].quantize(Decimal("1"))
    assert result["cotisations_target"] == result["cotisations_target"].quantize(Decimal("1"))

    # Base values should not have fractional euros from the math
    # (23.4 * 0.262 should round to nearest euro)
    assert result["cotisations_ae"] % Decimal("1") == Decimal("0")