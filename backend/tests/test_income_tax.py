"""
Sprint 7 — TASK-7.12 Income Tax (IR) calculation tests.

Tests the simplified French IR model:
  - Single person (1 part), BNC, no VL
  - Couple (2 parts)
  - Couple with 3 kids (4 parts → plafonnement)
  - VL = true → AE income excluded from IR
  - CESU credit reduces IR
  - Charity reduction
  - Salary income with 10% deduction
  - Other income (dividends)
  - Marginal and effective rates
"""

from decimal import Decimal

import pytest

from app.calculations.income_tax import (
    compute_ir,
    _apply_bareme,
    _marginal_rate,
    IR_TRANCHES_2024,
    AE_ABATTEMENTS,
    SALARY_DEDUCTION_RATE,
    SALARY_DEDUCTION_MIN,
    SALARY_DEDUCTION_MAX,
    MAX_ADVANTAGE_PER_HALF_PART,
)


class TestBareme:
    """Unit tests for the progressive barème calculation."""

    def test_zero_income(self):
        """Zero income → zero IR."""
        ir = _apply_bareme(Decimal("0"))
        assert ir == Decimal("0")

    def test_below_first_threshold(self):
        """Income entirely in the 0% bracket."""
        ir = _apply_bareme(Decimal("10000"))
        assert ir == Decimal("0")

    def test_in_11_pct_bracket(self):
        """Income in the 11% bracket (above 11,294)."""
        # 20,000: first 11,294 at 0%, remaining 8,706 at 11%
        # 8706 * 0.11 = 957.66
        ir = _apply_bareme(Decimal("20000"))
        expected = (Decimal("20000") - Decimal("11294")) * Decimal("0.11")
        assert ir.quantize(Decimal("0.01")) == expected.quantize(Decimal("0.01"))

    def test_in_30_pct_bracket(self):
        """Income in the 30% bracket."""
        # 50,000: 0% on 11,294 + 11% on (28,797-11,294) + 30% on (50,000-28,797)
        # = 0 + 17,503 * 0.11 + 21,203 * 0.30
        # = 0 + 1,925.33 + 6,360.90 = 8,286.23
        ir = _apply_bareme(Decimal("50000"))
        expected = (
            (Decimal("28797") - Decimal("11294")) * Decimal("0.11")
            + (Decimal("50000") - Decimal("28797")) * Decimal("0.30")
        )
        assert ir.quantize(Decimal("0.01")) == expected.quantize(Decimal("0.01"))

    def test_in_41_pct_bracket(self):
        """Income in the 41% bracket."""
        # 100,000: 0% on 11,294 + 11% on 17,503 + 30% on 53,544 + 41% on 17,659
        ir = _apply_bareme(Decimal("100000"))
        expected = (
            (Decimal("28797") - Decimal("11294")) * Decimal("0.11")
            + (Decimal("82341") - Decimal("28797")) * Decimal("0.30")
            + (Decimal("100000") - Decimal("82341")) * Decimal("0.41")
        )
        assert ir.quantize(Decimal("0.01")) == expected.quantize(Decimal("0.01"))

    def test_top_bracket(self):
        """Income above 177,106 (45% top rate)."""
        ir = _apply_bareme(Decimal("200000"))
        # Should include 45% on portion above 177,106
        expected = (
            (Decimal("28797") - Decimal("11294")) * Decimal("0.11")
            + (Decimal("82341") - Decimal("28797")) * Decimal("0.30")
            + (Decimal("177106") - Decimal("82341")) * Decimal("0.41")
            + (Decimal("200000") - Decimal("177106")) * Decimal("0.45")
        )
        assert ir.quantize(Decimal("0.01")) == expected.quantize(Decimal("0.01"))


class TestMarginalRate:
    """Tests for marginal rate calculation."""

    def test_all_brackets(self):
        """Each bracket should produce the correct marginal rate."""
        assert _marginal_rate(Decimal("0")) == Decimal("0")
        assert _marginal_rate(Decimal("10000")) == Decimal("0")  # still 0%
        assert _marginal_rate(Decimal("20000")) == Decimal("0.11")
        assert _marginal_rate(Decimal("50000")) == Decimal("0.30")
        assert _marginal_rate(Decimal("100000")) == Decimal("0.41")
        assert _marginal_rate(Decimal("200000")) == Decimal("0.45")


class TestSingleBNC:
    """Single person (1 part), AE BNC, no VL, no other income."""

    def test_50k_ca(self):
        """BNC, 50,000€ CA → abattement 34% → taxable = 33,000€.

        IR for 1 part on 33,000:
          - 0% on 11,294 = 0
          - 11% on (28,797 - 11,294) = 17,503 * 0.11 = 1,925.33
          - 30% on (33,000 - 28,797) = 4,203 * 0.30 = 1,260.90
          - Total = 3,186.23
        """
        result = compute_ir(
            ae_ca_annual=Decimal("50000"),
            ae_activity_type="bnc",
            tax_parts=Decimal("1"),
        )
        assert Decimal(result["revenu_imposable"]) == Decimal("33000.00")
        assert Decimal(result["ir_net"]) == Decimal("3186.23")
        assert Decimal(result["taux_effectif"]) == Decimal("0.0966")
        assert Decimal(result["taux_marginal"]) == Decimal("0.30")

    def test_low_ca_no_tax(self):
        """BNC, 15,000€ CA → abattement 34% → taxable = 9,900€.
        All in 0% bracket → IR = 0.
        """
        result = compute_ir(
            ae_ca_annual=Decimal("15000"),
            ae_activity_type="bnc",
            tax_parts=Decimal("1"),
        )
        assert Decimal(result["ir_net"]) == Decimal("0")
        assert Decimal(result["taux_effectif"]) == Decimal("0")
        assert Decimal(result["taux_marginal"]) == Decimal("0")

    def test_bic_vente_high_abattement(self):
        """BIC vente: 71% abattement instead of 34%.
        50,000€ CA → taxable = 50,000 * (1 - 0.71) = 14,500€.

        IR on 14,500 for 1 part:
          - 0% on 11,294 = 0
          - 11% on (14,500 - 11,294) = 3,206 * 0.11 = 352.66
        """
        result = compute_ir(
            ae_ca_annual=Decimal("50000"),
            ae_activity_type="bic_vente",
            tax_parts=Decimal("1"),
        )
        assert Decimal(result["revenu_imposable"]) == Decimal("14500.00")
        assert Decimal(result["ir_net"]) == Decimal("352.66")

    def test_unknown_activity_defaults_to_bnc(self):
        """Unknown activity type should default to 34% abattement."""
        result = compute_ir(
            ae_ca_annual=Decimal("50000"),
            ae_activity_type="something_unknown",
            tax_parts=Decimal("1"),
        )
        assert Decimal(result["revenu_imposable"]) == Decimal("33000.00")


class TestVersementLiberatoire:
    """VL = true → AE income excluded from IR entirely."""

    def test_vl_excludes_ae(self):
        """With VL, AE CA should be excluded from IR."""
        result = compute_ir(
            ae_ca_annual=Decimal("50000"),
            ae_activity_type="bnc",
            tax_parts=Decimal("1"),
            has_vl=True,
        )
        assert Decimal(result["revenu_imposable"]) == Decimal("0.00")
        assert Decimal(result["ir_net"]) == Decimal("0")

    def test_vl_with_salary(self):
        """With VL and spouse salary, only salary is taxed."""
        result = compute_ir(
            ae_ca_annual=Decimal("50000"),
            ae_activity_type="bnc",
            salary_annual=Decimal("30000"),
            tax_parts=Decimal("2"),
            has_vl=True,
        )
        # Salary: 30,000 * 0.90 (10% deduction) = 27,000
        # Taxable = 27,000 (AE excluded via VL)
        assert Decimal(result["revenu_imposable"]) == Decimal("27000.00")
        # IR on 27,000 / 2 = 13,500 per part
        # 0% on 11,294 = 0, 11% on 2,206 = 242.66 * 2 parts = 485.32
        assert Decimal(result["ir_net"]) > Decimal("0")


class TestCoupleWithSalary:
    """Couple (2 parts), AE + employed spouse."""

    def test_couple_ae_plus_cdi(self):
        """AE BNC 50,000€ + spouse CDI 36,000€, 2 parts.

        AE taxable: 50,000 * (1 - 0.34) = 33,000
        Salary taxable: 36,000 - 10% deduction = max(495, min(3,600, 14,171)) = 3,600
          → taxable salary = 36,000 - 3,600 = 32,400
        Total taxable = 33,000 + 32,400 = 65,400
        Per part = 65,400 / 2 = 32,700

        IR per part on 32,700:
          - 0% on 11,294 = 0
          - 11% on (28,797 - 11,294) = 17,503 * 0.11 = 1,925.33
          - 30% on (32,700 - 28,797) = 3,903 * 0.30 = 1,170.90
          - per part IR = 3,096.23
          - household IR = 3,096.23 * 2 = 6,192.46
        """
        result = compute_ir(
            ae_ca_annual=Decimal("50000"),
            ae_activity_type="bnc",
            salary_annual=Decimal("36000"),
            tax_parts=Decimal("2"),
        )
        assert Decimal(result["revenu_imposable"]) == Decimal("65400.00")
        # 65400/2 = 32700 per part → 3096.23 per part → 6192.46 total
        assert Decimal(result["ir_net"]) == Decimal("6192.46")
        assert Decimal(result["taux_marginal"]) == Decimal("0.30")

    def test_salary_deduction_minimum(self):
        """Very low salary should get min 495€ deduction."""
        result = compute_ir(
            ae_ca_annual=Decimal("0"),
            ae_activity_type="bnc",
            salary_annual=Decimal("3000"),
            tax_parts=Decimal("1"),
        )
        # 3,000 * 0.10 = 300, but min is 495 → taxable = 3,000 - 495 = 2,505
        assert Decimal(result["revenu_imposable"]) == Decimal("2505.00")

    def test_salary_deduction_maximum(self):
        """Very high salary should hit max 14,171€ deduction."""
        result = compute_ir(
            ae_ca_annual=Decimal("0"),
            ae_activity_type="bnc",
            salary_annual=Decimal("200000"),
            tax_parts=Decimal("1"),
        )
        # 200,000 * 0.10 = 20,000, but max is 14,171 → taxable = 200,000 - 14,171 = 185,829
        assert Decimal(result["revenu_imposable"]) == Decimal("185829.00")


class TestQuotientFamilialAndPlafonnement:
    """Quotient familial with plafonnement tests."""

    def test_couple_three_kids(self):
        """Couple (2) + 3 kids: first 2 kids = +1 part, 3rd kid = +1 part = 4 parts total.

        High income scenario where plafonnement applies.
        AE BNC 50,000€: taxable 33,000€
        No other income.
        Per part = 33,000 / 4 = 8,250 (entirely in 0% bracket)
        IR per part = 0, IR brut = 0.

        But what if income is much higher?
        AE BNC 200,000: taxable = 200,000 * 0.66 = 132,000€
        Per part = 132,000 / 4 = 33,000
        IR per part on 33,000:
          - 0% on 11,294
          - 11% on 17,503 = 1,925.33
          - 30% on 4,203 = 1,260.90
          - per part = 3,186.23, household = 12,744.92

        IR with 2 parts on 132,000: per part = 66,000
          - 0% on 11,294
          - 11% on 17,503 = 1,925.33
          - 30% on (66,000 - 28,797) = 37,203 * 0.30 = 11,160.90
          - per part = 13,086.23, household = 26,172.46

        Advantage = 26,172.46 - 12,744.92 = 13,427.54
        Max advantage for 2 extra half-parts above 2 = 4 extra half-parts * 1,759 = 7,036
        13,427.54 > 7,036 → plafonnement applies
        IR = 26,172.46 - 7,036 = 19,136.46
        """
        result = compute_ir(
            ae_ca_annual=Decimal("200000"),
            ae_activity_type="bnc",
            tax_parts=Decimal("4"),
        )
        assert Decimal(result["revenu_imposable"]) == Decimal("132000.00")
        # plafonnement should kick in
        assert Decimal(result["ir_net"]) == Decimal("19136.46")

    def test_plafonnement_not_triggered_for_low_income(self):
        """With low enough income, plafonnement shouldn't change the result."""
        result = compute_ir(
            ae_ca_annual=Decimal("50000"),
            ae_activity_type="bnc",
            tax_parts=Decimal("3"),  # couple + 2 kids
        )
        # 50,000 * 0.66 = 33,000 taxable
        # Per part = 33,000 / 3 = 11,000 (all in 0% bracket)
        # IR = 0
        assert Decimal(result["revenu_imposable"]) == Decimal("33000.00")
        assert Decimal(result["ir_net"]) == Decimal("0.00")


class TestCreditsAndReductions:
    """CESU credit and charity deductions."""

    def test_cesu_credit_reduces_ir(self):
        """CESU credit of 600€ should reduce IR."""
        # 50k CA, BNC → IR = 3,186.23
        result = compute_ir(
            ae_ca_annual=Decimal("50000"),
            ae_activity_type="bnc",
            tax_parts=Decimal("1"),
            cesu_credit=Decimal("600"),
        )
        expected = Decimal("3186.23") - Decimal("600")
        assert Decimal(result["ir_net"]) == expected

    def test_cesu_credit_cannot_make_negative(self):
        """CESU cannot create negative IR (refundable isn't modelled)."""
        result = compute_ir(
            ae_ca_annual=Decimal("10000"),  # low CA → IR = 0
            ae_activity_type="bnc",
            tax_parts=Decimal("1"),
            cesu_credit=Decimal("2000"),
        )
        assert Decimal(result["ir_net"]) == Decimal("0")
        # IR brut should also be 0
        assert Decimal(result["ir_brut"]) == Decimal("0")

    def test_charity_reduction(self):
        """Charity reduction reduces IR."""
        # 50k CA → IR = 3,186.23
        result = compute_ir(
            ae_ca_annual=Decimal("50000"),
            ae_activity_type="bnc",
            tax_parts=Decimal("1"),
            charity_reduction=Decimal("500"),
        )
        expected = Decimal("3186.23") - Decimal("500")
        assert Decimal(result["ir_net"]) == expected

    def test_both_credits(self):
        """Both CESU and charity simultaneously."""
        result = compute_ir(
            ae_ca_annual=Decimal("50000"),
            ae_activity_type="bnc",
            tax_parts=Decimal("1"),
            cesu_credit=Decimal("600"),
            charity_reduction=Decimal("500"),
        )
        expected = Decimal("3186.23") - Decimal("600") - Decimal("500")
        assert Decimal(result["ir_net"]) == expected


class TestOtherIncome:
    """Other income (dividends, rental, etc.)"""

    def test_other_income_added_directly(self):
        """Other income is added without abattement."""
        result = compute_ir(
            ae_ca_annual=Decimal("50000"),
            ae_activity_type="bnc",
            other_income_annual=Decimal("10000"),
            tax_parts=Decimal("1"),
        )
        # Taxable = 33,000 + 10,000 = 43,000
        assert Decimal(result["revenu_imposable"]) == Decimal("43000.00")
        assert Decimal(result["ir_net"]) > Decimal("3186.23")  # higher than without

    def test_monthly_ir(self):
        """Monthly IR should be annual / 12."""
        result = compute_ir(
            ae_ca_annual=Decimal("50000"),
            ae_activity_type="bnc",
            tax_parts=Decimal("1"),
        )
        annual = Decimal(result["ir_net"])
        monthly = Decimal(result["monthly_ir"])
        assert monthly == (annual / Decimal("12")).quantize(Decimal("0.01"))


class TestEdgeCases:
    """Edge case handling."""

    def test_zero_everything(self):
        """All zeros should return zero IR."""
        result = compute_ir(
            ae_ca_annual=Decimal("0"),
            ae_activity_type="bnc",
            tax_parts=Decimal("1"),
        )
        assert Decimal(result["ir_net"]) == Decimal("0")
        assert Decimal(result["revenu_imposable"]) == Decimal("0.00")

    def test_ae_rate_above_top_bracket(self):
        """Very high income → all brackets filled."""
        result = compute_ir(
            ae_ca_annual=Decimal("500000"),
            ae_activity_type="bnc",
            tax_parts=Decimal("1"),
        )
        # Taxable = 500,000 * 0.66 = 330,000 → top bracket
        assert Decimal(result["taux_marginal"]) == Decimal("0.45")
        assert Decimal(result["ir_net"]) > Decimal("0")

    def test_negative_salary_handled(self):
        """Zero or negative salary should be fine."""
        result = compute_ir(
            ae_ca_annual=Decimal("50000"),
            ae_activity_type="bnc",
            salary_annual=Decimal("0"),
            tax_parts=Decimal("1"),
        )
        # Same as without salary
        assert Decimal(result["revenu_imposable"]) == Decimal("33000.00")