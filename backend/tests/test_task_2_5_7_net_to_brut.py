"""
Tests for Task 2.5.7: net_to_brut() and prestataire worker support.

Verified against:
  - 06-social-charges-reference.md (RGDU, salarié, TNS rates)
  - net_to_brut() docstring salarial rate derivation table

Run with: docker compose exec backend pytest tests/test_task_2_5_7_net_to_brut.py -v
"""

import pytest
from decimal import Decimal

from app.calculations.social_charges import net_to_brut, calc_charges_salarie


# ── Prestataire path ───────────────────────────────────────────────────────────


def test_net_to_brut_prestataire_contract_type():
    """Prestataire contract_type: no charges, cout_total == net."""
    result = net_to_brut(
        net_mensuel=Decimal("1500"),
        role_type="salarie",
        contract_type="prestataire",
    )
    assert result.method == "prestataire"
    assert result.brut == Decimal("1500")
    assert result.charges_salariales == Decimal("0")
    assert result.charges_patronales == Decimal("0")
    assert result.cout_total == Decimal("1500")


def test_net_to_brut_prestataire_role_type():
    """Prestataire role_type: no charges, cout_total == net."""
    result = net_to_brut(
        net_mensuel=Decimal("2000"),
        role_type="prestataire",
        contract_type="cdi",  # role_type takes precedence
    )
    assert result.method == "prestataire"
    assert result.cout_total == Decimal("2000")


def test_net_to_brut_prestataire_zero_net():
    """Zero net → method 'zero', all zeros."""
    result = net_to_brut(
        net_mensuel=Decimal("0"),
        role_type="prestataire",
        contract_type="prestataire",
    )
    assert result.method == "zero"
    assert result.cout_total == Decimal("0")


# ── Dirigeant / TNS path ───────────────────────────────────────────────────────


def test_net_to_brut_dirigeant_basic():
    """Dirigeant: cout_total = net × 1.45, method 'tns_45pct'."""
    result = net_to_brut(
        net_mensuel=Decimal("2000"),
        role_type="dirigeant",
        contract_type="cdi",
    )
    assert result.method == "tns_45pct"
    assert result.brut == Decimal("2000")  # TNS: brut == net
    assert result.charges_salariales == Decimal("0")
    # charges_patronales = 2000 × 0.45 = 900
    assert result.charges_patronales == Decimal("900.00")
    # cout_total = 2000 + 900 = 2900
    assert result.cout_total == Decimal("2900.00")


def test_net_to_brut_dirigeant_2500():
    """Dirigeant 2500€ net: cout_total = 2500 × 1.45 = 3625."""
    result = net_to_brut(
        net_mensuel=Decimal("2500"),
        role_type="dirigeant",
        contract_type="cdi",
    )
    assert result.cout_total == Decimal("3625.00")
    assert result.charges_patronales == Decimal("1125.00")


# ── Salarié iterative path ─────────────────────────────────────────────────────


def test_net_to_brut_salarie_round_trip_1500():
    """
    Salarié 1500€ net: verify that brut → forward calc → net ≈ 1500 (±1€).

    WHY tolerance 1€: The forward calc uses _q() rounding on final results,
    which can shift the net by up to €0.02 from the target. We use 1€ as a
    comfortable safety margin.
    """
    result = net_to_brut(
        net_mensuel=Decimal("1500"),
        role_type="salarie",
        contract_type="cdi",
    )
    assert result.method == "salarie_iteratif"
    assert result.brut > Decimal("1500")  # brut must be higher than net
    assert result.cout_total > result.brut  # cout > brut (patronal charges on top)
    assert result.charges_patronales >= Decimal("0")  # RGDU floor prevents negative

    # Round-trip: forward calc with the returned brut should reproduce ~1500 net
    fwd = calc_charges_salarie(result.brut)
    diff = abs(fwd.salaire_net_approx - Decimal("1500"))
    assert diff <= Decimal("1.00"), (
        f"Round-trip failed: target net=1500, got {fwd.salaire_net_approx}, diff={diff}"
    )


def test_net_to_brut_salarie_round_trip_smic():
    """
    Salarié near SMIC net (≈1441): round-trip tolerance check.

    At SMIC brut (1823.03), salarial charges ≈ 20.84% → net ≈ 1442.
    The RGDU means patronal charges are nearly zero, but salarial charges still apply.
    """
    smic_net_approx = Decimal("1441")  # approximate net at SMIC brut
    result = net_to_brut(
        net_mensuel=smic_net_approx,
        role_type="salarie",
        contract_type="cdi",
    )
    assert result.method == "salarie_iteratif"
    fwd = calc_charges_salarie(result.brut)
    diff = abs(fwd.salaire_net_approx - smic_net_approx)
    assert diff <= Decimal("1.00"), f"SMIC round-trip diff={diff}"


def test_net_to_brut_salarie_round_trip_2000():
    """Salarié 2000€ net: round-trip check."""
    result = net_to_brut(
        net_mensuel=Decimal("2000"),
        role_type="salarie",
        contract_type="cdi",
    )
    fwd = calc_charges_salarie(result.brut)
    diff = abs(fwd.salaire_net_approx - Decimal("2000"))
    assert diff <= Decimal("1.00"), f"2000 net round-trip diff={diff}"


def test_net_to_brut_salarie_round_trip_high_salary():
    """
    Salarié 3500€ net (above PASS): round-trip check.

    Above PASS, T2 retraite complémentaire rates apply.
    The initial approximation is less accurate but iteration should still converge.
    """
    result = net_to_brut(
        net_mensuel=Decimal("3500"),
        role_type="salarie",
        contract_type="cdi",
    )
    fwd = calc_charges_salarie(result.brut)
    diff = abs(fwd.salaire_net_approx - Decimal("3500"))
    assert diff <= Decimal("1.00"), f"High salary round-trip diff={diff}"


def test_net_to_brut_salarie_cout_total_composition():
    """cout_total = brut + charges_patronales (to within rounding)."""
    result = net_to_brut(
        net_mensuel=Decimal("2000"),
        role_type="salarie",
        contract_type="cdi",
    )
    # cout_total from forward calc vs result — they should match
    fwd = calc_charges_salarie(result.brut)
    # The result.cout_total should equal fwd.cout_total_employeur (within €0.02)
    diff = abs(result.cout_total - fwd.cout_total_employeur)
    assert diff <= Decimal("0.02"), f"cout_total mismatch: {result.cout_total} vs {fwd.cout_total_employeur}"


def test_net_to_brut_apprenti_uses_salarie_path():
    """
    Apprenti uses the same salarial rate path as CDI (known approximation).
    Verify it returns method 'salarie_iteratif' and round-trips correctly.
    """
    result = net_to_brut(
        net_mensuel=Decimal("900"),
        role_type="apprenti",
        contract_type="apprentissage",
    )
    assert result.method == "salarie_iteratif"
    fwd = calc_charges_salarie(result.brut)
    diff = abs(fwd.salaire_net_approx - Decimal("900"))
    assert diff <= Decimal("1.00"), f"Apprenti round-trip diff={diff}"


# ── Edge cases ─────────────────────────────────────────────────────────────────


def test_net_to_brut_zero_returns_zero_method():
    """Zero net_mensuel → method 'zero', all values are 0."""
    for role, contract in [
        ("salarie", "cdi"),
        ("dirigeant", "cdi"),
        ("prestataire", "prestataire"),
    ]:
        result = net_to_brut(
            net_mensuel=Decimal("0"),
            role_type=role,
            contract_type=contract,
        )
        assert result.method == "zero", f"Expected 'zero' for {role}/{contract}"
        assert result.cout_total == Decimal("0")
        assert result.brut == Decimal("0")


def test_net_to_brut_negative_net_returns_zero_method():
    """Negative net_mensuel → method 'zero' (guard prevents nonsense input)."""
    result = net_to_brut(
        net_mensuel=Decimal("-100"),
        role_type="salarie",
        contract_type="cdi",
    )
    assert result.method == "zero"


def test_net_to_brut_prestataire_large_amount():
    """Large prestataire amount: no charges applied."""
    result = net_to_brut(
        net_mensuel=Decimal("5000"),
        role_type="prestataire",
        contract_type="prestataire",
    )
    assert result.cout_total == Decimal("5000")
    assert result.charges_patronales == Decimal("0")
    assert result.charges_salariales == Decimal("0")
