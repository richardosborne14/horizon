"""
TASK-2.14.5 — RGDU 2026 audit tests.

Verifies that calc_rgdu() uses the correct constants published in:
  Décret n°2025-887 du 4 septembre 2025 (JORFTEXT000052194026)
  — confirmed by three independent professional bulletins:
    * Lefebvre-Dalloz: https://formation.lefebvre-dalloz.fr/actualite/reforme-des-allegements-de-cotisations-le-decret-fixant-les-modalites-de-calcul-de-la-rgdu-pour-2026-est-paru
    * Editions Tissot: https://www.editions-tissot.fr/actualite/droit-du-travail/reduction-generale-des-cotisations-patronales-quel-gain-ou-perte-a-prevoir-pour-2026
    * Baker Tilly: https://www.bakertilly.fr/actualites/erhs-allegement-cotisations-patronales-nouveau-calcul-et-impacts-pour-entreprise

2026 constants (<50 employees, applies to all coiffure salons):
    T_MIN   = 0.0200  (unchanged from 2025)
    T_DELTA = 0.3773  (was 0.3781 — recalibrated in décret n°2025-887)
    P       = 1.75    (unchanged)
    T_MAX   = 0.3973  (= T_MIN + T_DELTA)

For ≥50 employees:
    T_DELTA = 0.3813
    T_MAX   = 0.4013

These tests use SMIC_ANNUEL and PASS_ANNUEL from social_charges.py constants
so that if those values ever update, the expected RGDU adjusts automatically.
Expected RGDU values are verified to ±50 € (the tolerance of the ~45% rule
approximation used by the savings engine is ±200 €; ±50 is much tighter).
"""

import math
from decimal import Decimal
import pytest

from app.calculations.social_charges import (
    calc_rgdu,
    SMIC_ANNUEL,
    PASS_ANNUEL,
)

# ── Constants verified by audit (décret n°2025-887) ────────────────────────────
T_MIN_2026 = Decimal("0.0200")
T_DELTA_2026_LT50 = Decimal("0.3773")   # < 50 employees
T_DELTA_2026_GTE50 = Decimal("0.3813")  # ≥ 50 employees
P_2026 = 1.75
T_MAX_2026_LT50 = T_MIN_2026 + T_DELTA_2026_LT50   # = 0.3973
T_MAX_2026_GTE50 = T_MIN_2026 + T_DELTA_2026_GTE50  # = 0.4013


def _expected_rgdu(salaire_annuel: Decimal, effectif: int = 5) -> Decimal:
    """
    Reference implementation of the 2026 RGDU formula.

    Independently computes the expected value to cross-check calc_rgdu().
    Uses the same formula as the official decree:
        C = T_MIN + T_DELTA × [(1/2) × (3 × SMIC / S − 1)]^P
    """
    trois_smic = SMIC_ANNUEL * Decimal("3")
    if salaire_annuel <= Decimal("0") or salaire_annuel >= trois_smic:
        return Decimal("0")

    t_delta = T_DELTA_2026_LT50 if effectif < 50 else T_DELTA_2026_GTE50
    t_max = T_MIN_2026 + t_delta

    ratio = (trois_smic / salaire_annuel) - Decimal("1")
    half_ratio = Decimal("0.5") * ratio
    power_result = Decimal(str(float(half_ratio) ** P_2026))
    coeff = T_MIN_2026 + (t_delta * power_result)
    coeff = min(coeff, t_max)
    coeff = max(coeff, T_MIN_2026)
    return salaire_annuel * coeff


class TestRgdu2026AuditConstants:
    """Verify TASK-2.14.5 constants in calc_rgdu() match décret n°2025-887."""

    def test_smic_coefficient_equals_t_max_lt50(self):
        """
        At SMIC level (effectif < 50), coefficient should be capped at T_MAX = 0.3973.

        WHY: ratio = (3×SMIC / SMIC) − 1 = 2, so half_ratio = 1.0, 1.0^1.75 = 1.0.
        coefficient = T_MIN + T_DELTA × 1.0 = 0.02 + 0.3773 = 0.3973 → capped at T_MAX.
        Source: décret n°2025-887 du 4 septembre 2025 — T_DELTA = 0.3773 for <50 employees.
        """
        result = calc_rgdu(SMIC_ANNUEL, effectif_entreprise=5)
        expected = SMIC_ANNUEL * T_MAX_2026_LT50

        # Coefficient should be exactly T_MAX (cap applies at SMIC)
        # WHY float(result): pytest.approx can't subtract float from Decimal
        assert float(result) == pytest.approx(float(expected), abs=1.0), (
            f"At SMIC: RGDU = {result}, expected ≈ {expected} "
            f"(T_MAX = {T_MAX_2026_LT50} per décret 2025-887)"
        )

    def test_smic_coefficient_equals_t_max_gte50(self):
        """
        At SMIC level with effectif ≥ 50, coefficient capped at T_MAX = 0.4013.

        Source: décret n°2025-887 du 4 septembre 2025 — T_DELTA = 0.3813 for ≥50 employees.
        This branch is unlikely in practice for coiffure (all salons < 50 employees)
        but must be correct for correctness of the code.
        """
        result = calc_rgdu(SMIC_ANNUEL, effectif_entreprise=50)
        expected = SMIC_ANNUEL * T_MAX_2026_GTE50

        assert float(result) == pytest.approx(float(expected), abs=1.0), (
            f"At SMIC (≥50 employees): RGDU = {result}, expected ≈ {expected} "
            f"(T_MAX = {T_MAX_2026_GTE50} per décret 2025-887)"
        )

    def test_old_t_delta_0_3781_not_used(self):
        """
        Regression: the PRE-2026 value T_DELTA = 0.3781 must NOT be used.

        The old value predated the LFSS 2025 reform that suppressed reduced taux
        for maladie (7%→13%) and alloc fam (3.45%→5.25%). The decree recalibrated
        T_DELTA to 0.3773 for <50 employees.

        At SMIC, the difference is small (~17 €/year per employee) but the constant
        must match the official decree to stay compliant.
        """
        result = calc_rgdu(SMIC_ANNUEL, effectif_entreprise=5)
        wrong_t_max = Decimal("0.0200") + Decimal("0.3781")  # = 0.3981 (old value)
        wrong_expected = float(SMIC_ANNUEL * wrong_t_max)

        # Result should NOT match the old T_DELTA computation
        assert abs(float(result) - wrong_expected) > 5.0, (
            f"calc_rgdu still uses old T_DELTA = 0.3781 — expected result to differ "
            f"from {wrong_expected:.2f} by > 5 €, got {result}"
        )


class TestRgdu2026FormulaPoints:
    """Verify RGDU formula at key salary points (2026, effectif < 50)."""

    def test_two_smic_formula(self):
        """
        At 2 × SMIC annuel, verify the coefficient against the reference formula.

        2 × SMIC = 43752.80 €/an
        ratio = (3 × SMIC / 2 × SMIC) - 1 = 1.5 - 1 = 0.5
        half = 0.25
        0.25^1.75 ≈ 0.0882
        coeff = 0.02 + 0.3773 × 0.0882 ≈ 0.0533
        RGDU ≈ 43752.80 × 0.0533 ≈ 2 332 €/an
        """
        deux_smic = SMIC_ANNUEL * Decimal("2")
        result = calc_rgdu(deux_smic, effectif_entreprise=5)
        expected = _expected_rgdu(deux_smic, effectif=5)

        # WHY float(result): pytest.approx can't subtract float from Decimal
        assert float(result) == pytest.approx(float(expected), abs=1.0), (
            f"At 2×SMIC: RGDU = {result:.2f}, reference formula gives {expected:.2f}"
        )
        # Absolute sanity bounds: should be in 2 000–2 700 €/an range
        assert Decimal("2000") < result < Decimal("2700"), (
            f"2×SMIC RGDU {result:.2f} outside expected band [2000, 2700]"
        )

    def test_just_below_three_smic_uses_floor(self):
        """
        Just below 3 × SMIC (threshold), RGDU should be positive but near T_MIN.

        At salary very close to 3 × SMIC, ratio ≈ 0, power_result ≈ 0,
        so coefficient ≈ T_MIN = 0.02.
        RGDU ≈ (3 × SMIC − 1) × 0.02 ≈ ~1 312 €/an.

        This verifies the T_MIN floor is active and RGDU is NOT zero.
        """
        just_below = SMIC_ANNUEL * Decimal("3") - Decimal("1")
        result = calc_rgdu(just_below, effectif_entreprise=5)

        # Must be positive — still within the threshold
        assert result > Decimal("0"), (
            f"RGDU should be > 0 just below 3×SMIC, got {result}"
        )
        # Coefficient at this point is approximately T_MIN → RGDU ≈ salary × 0.02
        expected_floor_rgdu = just_below * T_MIN_2026
        assert float(result) == pytest.approx(float(expected_floor_rgdu), abs=50.0), (
            f"Just below 3×SMIC RGDU = {result:.2f}, expected ≈ floor "
            f"T_MIN × salary = {expected_floor_rgdu:.2f}"
        )

    def test_three_smic_exact_is_zero(self):
        """
        At exactly 3 × SMIC, RGDU must be zero — threshold boundary.

        The formula uses `if salaire >= trois_smic: return 0`.
        This test verifies the boundary is correct and hasn't regressed.
        """
        trois_smic = SMIC_ANNUEL * Decimal("3")
        result = calc_rgdu(trois_smic, effectif_entreprise=5)
        assert result == Decimal("0"), (
            f"RGDU should be exactly 0 at 3×SMIC threshold, got {result}"
        )

    def test_above_three_smic_is_zero(self):
        """
        Above 3 × SMIC, RGDU must be zero — no reduction applies.
        """
        above = SMIC_ANNUEL * Decimal("3") + Decimal("100")
        result = calc_rgdu(above, effectif_entreprise=5)
        assert result == Decimal("0"), (
            f"RGDU above 3×SMIC should be 0, got {result}"
        )

    def test_zero_salary_is_zero(self):
        """
        Zero salary → zero RGDU (avoids DivisionByZero).
        """
        result = calc_rgdu(Decimal("0"), effectif_entreprise=5)
        assert result == Decimal("0")

    def test_negative_salary_is_zero(self):
        """
        Negative salary → zero RGDU (guard condition).
        """
        result = calc_rgdu(Decimal("-1000"), effectif_entreprise=5)
        assert result == Decimal("0")


class TestRgdu2026EffectifBranching:
    """Verify effectif_entreprise correctly selects T_DELTA branch."""

    @pytest.mark.parametrize("effectif", [1, 5, 10, 49])
    def test_lt50_uses_0_3773(self, effectif):
        """
        For any effectif < 50, T_DELTA = 0.3773 — T_MAX = 0.3973 at SMIC.
        """
        result = calc_rgdu(SMIC_ANNUEL, effectif_entreprise=effectif)
        expected = SMIC_ANNUEL * T_MAX_2026_LT50
        assert float(result) == pytest.approx(float(expected), abs=1.0)

    @pytest.mark.parametrize("effectif", [50, 100, 500])
    def test_gte50_uses_0_3813(self, effectif):
        """
        For any effectif ≥ 50, T_DELTA = 0.3813 — T_MAX = 0.4013 at SMIC.
        """
        result = calc_rgdu(SMIC_ANNUEL, effectif_entreprise=effectif)
        expected = SMIC_ANNUEL * T_MAX_2026_GTE50
        assert float(result) == pytest.approx(float(expected), abs=1.0)

    def test_lt50_and_gte50_differ_at_smic(self):
        """
        The two T_DELTA values should produce measurably different RGDU at SMIC.

        Expected difference = SMIC_ANNUEL × (0.3813 - 0.3773) = ~8.75 €/an.
        """
        result_lt50 = calc_rgdu(SMIC_ANNUEL, effectif_entreprise=5)
        result_gte50 = calc_rgdu(SMIC_ANNUEL, effectif_entreprise=50)
        diff = result_gte50 - result_lt50
        # Should be approximately SMIC × 0.004 = ~87.5 €/an
        assert Decimal("50") < diff < Decimal("150"), (
            f"Effectif difference should be ~87 €/an, got {diff:.2f}"
        )
