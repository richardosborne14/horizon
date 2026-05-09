"""
Unit tests for Task 3.5: Marge Revente Calculator.

Test cases from Eric's Excel (Classeur1 > prix revente sheet):
- Test case: achat=10, coeff=2.5 → vente_ht=25, vente_ttc=30, marge=15, marge_pct=60%
"""

import pytest
from decimal import Decimal

from app.calculations.marge_revente import compute_marge_revente, MargeReventeResult


class TestMargeReventeCalculation:
    """Test the marge revente calculation engine."""

    def test_basic_calculation(self):
        """Test case from Excel: achat=10, coeff=2.5 → vente_ht=25, vente_ttc=30, marge=15, marge_pct=60%"""
        result = compute_marge_revente(
            prix_achat_ht=Decimal("10"),
            coefficient=Decimal("2.5"),
        )

        assert result.prix_achat_ht == Decimal("10.00")
        assert result.coefficient == Decimal("2.5")
        assert result.prix_vente_ht == Decimal("25.00")
        assert result.prix_vente_ttc == Decimal("30.00")
        assert result.marge_brute_ht == Decimal("15.00")
        assert result.marge_pct == Decimal("0.6000")
        assert result.tva_collectee == Decimal("5.00")

    def test_default_coefficient(self):
        """Test that default coefficient is 2.5."""
        result = compute_marge_revente(prix_achat_ht=Decimal("10"))

        assert result.coefficient == Decimal("2.5")
        assert result.marge_pct == Decimal("0.6000")

    def test_coefficient_2_0(self):
        """Test coefficient of 2.0 (50% margin)."""
        result = compute_marge_revente(
            prix_achat_ht=Decimal("10"),
            coefficient=Decimal("2.0"),
        )

        assert result.prix_vente_ht == Decimal("20.00")
        assert result.prix_vente_ttc == Decimal("24.00")
        assert result.marge_brute_ht == Decimal("10.00")
        assert result.marge_pct == Decimal("0.5000")

    def test_coefficient_3_0(self):
        """Test coefficient of 3.0 (66.67% margin)."""
        result = compute_marge_revente(
            prix_achat_ht=Decimal("10"),
            coefficient=Decimal("3.0"),
        )

        assert result.prix_vente_ht == Decimal("30.00")
        assert result.prix_vente_ttc == Decimal("36.00")
        assert result.marge_brute_ht == Decimal("20.00")
        assert result.marge_pct == Decimal("0.6667")

    def test_decimal_precision(self):
        """Test with decimal values."""
        result = compute_marge_revente(
            prix_achat_ht=Decimal("12.50"),
            coefficient=Decimal("2.75"),
        )

        # prix_vente_ht = 12.50 × 2.75 = 34.375 → 34.38
        # prix_vente_ttc = 34.375 × 1.2 = 41.25
        # marge_brute_ht = 34.375 - 12.50 = 21.875 → 21.88
        assert result.prix_achat_ht == Decimal("12.50")
        assert result.prix_vente_ht == Decimal("34.38")
        assert result.prix_vente_ttc == Decimal("41.25")
        assert result.marge_brute_ht == Decimal("21.88")

    def test_validation_zero_prix_achat(self):
        """Test that zero prix_achat raises ValueError."""
        with pytest.raises(ValueError, match="prix_achat_ht must be > 0"):
            compute_marge_revente(prix_achat_ht=Decimal("0"))

    def test_validation_negative_prix_achat(self):
        """Test that negative prix_achat raises ValueError."""
        with pytest.raises(ValueError, match="prix_achat_ht must be > 0"):
            compute_marge_revente(prix_achat_ht=Decimal("-10"))

    def test_validation_zero_coefficient(self):
        """Test that zero coefficient raises ValueError."""
        with pytest.raises(ValueError, match="coefficient must be > 0"):
            compute_marge_revente(
                prix_achat_ht=Decimal("10"),
                coefficient=Decimal("0"),
            )

    def test_validation_negative_coefficient(self):
        """Test that negative coefficient raises ValueError."""
        with pytest.raises(ValueError, match="coefficient must be > 0"):
            compute_marge_revente(
                prix_achat_ht=Decimal("10"),
                coefficient=Decimal("-2"),
            )


class TestCompetitorComparison:
    """Test competitor price comparison feature."""

    def test_single_competitor_cheaper(self):
        """Test competitor who is cheaper than us."""
        result = compute_marge_revente(
            prix_achat_ht=Decimal("10"),
            coefficient=Decimal("2.5"),
            competitor_prices=[{"name": "Amazon", "prix_ttc": Decimal("28")}],
        )

        assert len(result.competitor_comparisons) == 1
        comp = result.competitor_comparisons[0]
        assert comp.name == "Amazon"
        assert comp.prix_ttc == Decimal("28.00")
        # Our price is 30€ TTC, competitor is 28€ TTC → écart = -2€
        assert comp.ecart == Decimal("-2.00")

    def test_single_competitor_more_expensive(self):
        """Test competitor who is more expensive than us."""
        result = compute_marge_revente(
            prix_achat_ht=Decimal("10"),
            coefficient=Decimal("2.5"),
            competitor_prices=[{"name": "Boutique", "prix_ttc": Decimal("35")}],
        )

        comp = result.competitor_comparisons[0]
        assert comp.name == "Boutique"
        assert comp.prix_ttc == Decimal("35.00")
        # Our price is 30€ TTC, competitor is 35€ TTC → écart = +5€
        assert comp.ecart == Decimal("5.00")

    def test_single_competitor_same_price(self):
        """Test competitor with same price as us."""
        result = compute_marge_revente(
            prix_achat_ht=Decimal("10"),
            coefficient=Decimal("2.5"),
            competitor_prices=[{"name": "Concurrent", "prix_ttc": Decimal("30")}],
        )

        comp = result.competitor_comparisons[0]
        assert comp.ecart == Decimal("0.00")

    def test_multiple_competitors(self):
        """Test with multiple competitors."""
        result = compute_marge_revente(
            prix_achat_ht=Decimal("10"),
            coefficient=Decimal("2.5"),
            competitor_prices=[
                {"name": "Amazon", "prix_ttc": Decimal("28")},
                {"name": "Fnac", "prix_ttc": Decimal("32")},
                {"name": "Boutique", "prix_ttc": Decimal("30")},
            ],
        )

        assert len(result.competitor_comparisons) == 3

        # Amazon: 28€ vs our 30€ → -2€
        assert result.competitor_comparisons[0].name == "Amazon"
        assert result.competitor_comparisons[0].ecart == Decimal("-2.00")

        # Fnac: 32€ vs our 30€ → +2€
        assert result.competitor_comparisons[1].name == "Fnac"
        assert result.competitor_comparisons[1].ecart == Decimal("2.00")

        # Boutique: 30€ vs our 30€ → 0€
        assert result.competitor_comparisons[2].name == "Boutique"
        assert result.competitor_comparisons[2].ecart == Decimal("0.00")

    def test_no_competitors(self):
        """Test with no competitors."""
        result = compute_marge_revente(
            prix_achat_ht=Decimal("10"),
            coefficient=Decimal("2.5"),
            competitor_prices=None,
        )

        assert result.competitor_comparisons == []

    def test_empty_competitors_list(self):
        """Test with empty competitors list."""
        result = compute_marge_revente(
            prix_achat_ht=Decimal("10"),
            coefficient=Decimal("2.5"),
            competitor_prices=[],
        )

        assert result.competitor_comparisons == []


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_small_prix_achat(self):
        """Test with very small purchase price."""
        result = compute_marge_revente(
            prix_achat_ht=Decimal("0.01"),
            coefficient=Decimal("2.5"),
        )

        assert result.prix_achat_ht == Decimal("0.01")
        assert result.prix_vente_ht == Decimal("0.03")  # 0.01 × 2.5 = 0.025 → 0.03
        assert result.marge_pct == Decimal("0.6000")  # Margin % stays the same

    def test_very_large_prix_achat(self):
        """Test with large purchase price."""
        result = compute_marge_revente(
            prix_achat_ht=Decimal("100000"),
            coefficient=Decimal("2.0"),
        )

        assert result.prix_achat_ht == Decimal("100000.00")
        assert result.prix_vente_ht == Decimal("200000.00")
        assert result.marge_brute_ht == Decimal("100000.00")

    def test_fractional_coefficient(self):
        """Test with fractional coefficient."""
        result = compute_marge_revente(
            prix_achat_ht=Decimal("10"),
            coefficient=Decimal("2.33"),
        )

        # prix_vente_ht = 10 × 2.33 = 23.30
        # marge = 23.30 - 10 = 13.30
        # marge_pct = 13.30 / 23.30 = 0.5708...
        assert result.prix_vente_ht == Decimal("23.30")
        assert result.marge_brute_ht == Decimal("13.30")


class TestExcelReferenceCase:
    """
    Reference test case from Eric's Excel file.

    From CALCULATION_FORMULAS.md:
    Inputs:
      prix_achat_ht = 10, coefficient = 2.5

    Expected:
      prix_vente_ht = 25
      prix_vente_ttc = 30
      marge_brute_ht = 15
      marge_pct = 0.60 (60%)
    """

    def test_excel_reference_case(self):
        """Verify the exact test case from Eric's Excel matches."""
        result = compute_marge_revente(
            prix_achat_ht=Decimal("10"),
            coefficient=Decimal("2.5"),
        )

        # Exact values from Excel
        assert result.prix_vente_ht == Decimal("25.00"), "prix_vente_ht should be 25.00"
        assert result.prix_vente_ttc == Decimal("30.00"), "prix_vente_ttc should be 30.00"
        assert result.marge_brute_ht == Decimal("15.00"), "marge_brute_ht should be 15.00"
        assert result.marge_pct == Decimal("0.6000"), "marge_pct should be 0.6000 (60%)"

    def test_excel_case_with_competitor(self):
        """Test the Excel case with a competitor at 28€."""
        result = compute_marge_revente(
            prix_achat_ht=Decimal("10"),
            coefficient=Decimal("2.5"),
            competitor_prices=[{"name": "Concurrent", "prix_ttc": Decimal("28")}],
        )

        # Our price: 30€ TTC
        # Competitor: 28€ TTC
        # Écart: 28 - 30 = -2€
        assert result.competitor_comparisons[0].ecart == Decimal("-2.00")
