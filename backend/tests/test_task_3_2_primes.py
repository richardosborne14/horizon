"""
Unit tests for Task 3.2 — Calculateur des Primes

Tests the tiered bonus calculation engine with deficit carry-forward.
"""

import pytest
from decimal import Decimal

from app.calculations.primes import (
    calculate_tiered_prime,
    compute_prime_month,
    compute_primes_annual,
    compute_objectif_jour_from_salary,
    PrimeTier,
    PrimeMonthInput,
    DEFAULT_PRIME_TIERS,
)


class TestCalculateTieredPrime:
    """Tests for the tiered bonus calculation."""

    def test_no_prime_when_ecart_is_zero(self):
        """Zero ecart = no bonus."""
        result = calculate_tiered_prime(Decimal("0"))
        assert result == Decimal("0")

    def test_no_prime_when_ecart_is_negative(self):
        """Negative ecart = no bonus (handled at month level)."""
        result = calculate_tiered_prime(Decimal("-100"))
        assert result == Decimal("0")

    def test_prime_first_tier_only(self):
        """Ecarts in the first tier (0-600) get 10%."""
        # 500€ excess should give 50€ prime (10%)
        result = calculate_tiered_prime(Decimal("500"))
        assert result == Decimal("50.00")

    def test_prime_exact_first_tier_threshold(self):
        """Exactly at first threshold: 600€ at 10% = 60€."""
        result = calculate_tiered_prime(Decimal("600"))
        assert result == Decimal("60.00")

    def test_prime_second_tier(self):
        """Ecarts in second tier (600-900) get 12% on the excess over 600."""
        # 750€ excess:
        # - First 600 at 10% = 60€
        # - Next 150 at 12% = 18€
        # Total = 78€
        result = calculate_tiered_prime(Decimal("750"))
        assert result == Decimal("78.00")

    def test_prime_multiple_tiers(self):
        """Full example from Eric's Excel: 1145.91 ecart."""
        # 600 at 10% = 60.00
        # 300 at 12% = 36.00
        # 245.91 at 14% = 34.43
        # Total = 130.43
        result = calculate_tiered_prime(Decimal("1145.91"))
        assert result == Decimal("130.43")

    def test_prime_beyond_all_tiers(self):
        """Excess beyond highest tier uses highest rate."""
        # 5000€ excess:
        # - 600 at 10% = 60
        # - 300 at 12% = 36
        # - 300 at 14% = 42
        # - 300 at 16% = 48
        # - 300 at 18% = 54
        # - 300 at 20% = 60
        # - 300 at 22% = 66
        # - 300 at 24% = 72
        # - 300 at 28% = 84
        # - 2000 at 28% = 560
        # Total = 1082
        result = calculate_tiered_prime(Decimal("5000"))
        assert result == Decimal("1082.00")

    def test_custom_tiers(self):
        """Test with custom tier configuration."""
        custom_tiers = [
            PrimeTier(Decimal("500"), Decimal("0.15")),  # 0-500: 15%
            PrimeTier(Decimal("1000"), Decimal("0.20")),  # 500-1000: 20%
        ]
        # 750€ excess:
        # - First 500 at 15% = 75
        # - Next 250 at 20% = 50
        # Total = 125
        result = calculate_tiered_prime(Decimal("750"), tiers=custom_tiers)
        assert result == Decimal("125.00")


class TestComputePrimeMonth:
    """Tests for single month calculation."""

    def test_basic_month_calculation(self):
        """Test a basic profitable month."""
        result = compute_prime_month(
            month=1,
            days_worked=22,
            resultat=Decimal("7000"),
            objectif_jour=Decimal("250"),
            deficit_anterieur=Decimal("0"),
        )
        
        assert result.month == 1
        assert result.days_worked == 22
        assert result.objectif_initial == Decimal("5500.00")  # 250 * 22
        assert result.deficit_anterieur == Decimal("0")
        assert result.objectif_final == Decimal("5500.00")
        assert result.resultat == Decimal("7000")
        assert result.ecart == Decimal("1500.00")  # 7000 - 5500
        # 1500 at tiered rates:
        # 600 at 10% = 60
        # 300 at 12% = 36
        # 300 at 14% = 42
        # 300 at 16% = 48
        assert result.prime == Decimal("186.00")

    def test_month_with_deficit_carried(self):
        """Test month where previous deficit increases objective."""
        result = compute_prime_month(
            month=2,
            days_worked=20,
            resultat=Decimal("4500"),
            objectif_jour=Decimal("250"),
            deficit_anterieur=Decimal("500"),  # Previous month was 500 short
        )
        
        assert result.month == 2
        assert result.objectif_initial == Decimal("5000.00")  # 250 * 20
        assert result.deficit_anterieur == Decimal("500")
        assert result.objectif_final == Decimal("5500.00")  # 5000 + 500
        assert result.resultat == Decimal("4500")
        assert result.ecart == Decimal("-1000.00")  # 4500 - 5500
        assert result.prime == Decimal("0")  # No prime when ecart < 0

    def test_month_exactly_meets_target(self):
        """Test month where resultat exactly equals objectif."""
        result = compute_prime_month(
            month=3,
            days_worked=22,
            resultat=Decimal("5500"),
            objectif_jour=Decimal("250"),
            deficit_anterieur=Decimal("0"),
        )
        
        assert result.ecart == Decimal("0")
        assert result.prime == Decimal("0")


class TestComputePrimesAnnual:
    """Tests for full year calculation with deficit carry-forward."""

    def test_full_year_profitable(self):
        """Test a profitable year where employee exceeds target every month."""
        monthly_data = [
            PrimeMonthInput(month=m, days_worked=22, resultat=Decimal("7000"))
            for m in range(1, 13)
        ]
        
        result = compute_primes_annual(
            employee_id="emp-123",
            employee_name="Julie Martin",
            year=2026,
            objectif_jour=Decimal("250"),
            monthly_data=monthly_data,
        )
        
        assert result.employee_id == "emp-123"
        assert result.employee_name == "Julie Martin"
        assert result.year == 2026
        assert result.objectif_jour == Decimal("250.00")
        assert len(result.months) == 12
        
        # Each month: 22 days * 250 = 5500 objective
        assert result.total_days_worked == 22 * 12
        assert result.total_objectif == Decimal("66000.00")  # 5500 * 12
        assert result.total_resultat == Decimal("84000.00")  # 7000 * 12
        assert result.total_ecart == Decimal("18000.00")  # 84000 - 66000
        assert result.total_prime > 0
        assert result.final_deficit == Decimal("0")  # No final deficit

    def test_full_year_with_deficit_propagation(self):
        """Test where deficits carry from month to month."""
        # First 3 months bad, rest good
        monthly_data = [
            PrimeMonthInput(month=1, days_worked=22, resultat=Decimal("4000")),  # -1500
            PrimeMonthInput(month=2, days_worked=20, resultat=Decimal("5000")),  # Carried deficit makes this -500
            PrimeMonthInput(month=3, days_worked=22, resultat=Decimal("6000")),  # Should be +500
            PrimeMonthInput(month=4, days_worked=22, resultat=Decimal("7000")),
            PrimeMonthInput(month=5, days_worked=22, resultat=Decimal("7000")),
            PrimeMonthInput(month=6, days_worked=22, resultat=Decimal("7000")),
            PrimeMonthInput(month=7, days_worked=22, resultat=Decimal("7000")),
            PrimeMonthInput(month=8, days_worked=22, resultat=Decimal("7000")),
            PrimeMonthInput(month=9, days_worked=22, resultat=Decimal("7000")),
            PrimeMonthInput(month=10, days_worked=22, resultat=Decimal("7000")),
            PrimeMonthInput(month=11, days_worked=22, resultat=Decimal("7000")),
            PrimeMonthInput(month=12, days_worked=22, resultat=Decimal("7000")),
        ]
        
        result = compute_primes_annual(
            employee_id="emp-123",
            employee_name="Jean Dupont",
            year=2026,
            objectif_jour=Decimal("250"),
            monthly_data=monthly_data,
        )
        
        assert len(result.months) == 12
        
        # Month 1: 22*250 = 5500, result 4000, ecart = -1500
        assert result.months[0].ecart == Decimal("-1500.00")
        
        # Month 2: 20*250 = 5000, +1500 deficit = 6500, result 5000, ecart = -1500
        assert result.months[1].deficit_anterieur == Decimal("1500.00")
        assert result.months[1].ecart == Decimal("-1500.00")
        
        # Month 3: 22*250 = 5500, +1500 deficit = 7000, result 6000, ecart = -1000
        assert result.months[2].deficit_anterieur == Decimal("1500.00")
        assert result.months[2].ecart == Decimal("-1000.00")
        
        # Month 4: Should recover
        assert result.months[3].ecart > 0
        
        # Final deficit should be 0 (recovered by end of year)
        assert result.final_deficit == Decimal("0")

    def test_invalid_month_count(self):
        """Test that missing months raises error."""
        monthly_data = [
            PrimeMonthInput(month=1, days_worked=22, resultat=Decimal("7000")),
            PrimeMonthInput(month=2, days_worked=20, resultat=Decimal("6000")),
            # Missing months 3-12
        ]
        
        with pytest.raises(ValueError, match="Expected 12 months"):
            compute_primes_annual(
                employee_id="emp-123",
                employee_name="Test",
                year=2026,
                objectif_jour=Decimal("250"),
                monthly_data=monthly_data,
            )


class TestComputeObjectifJour:
    """Tests for daily objective calculation from salary."""

    def test_basic_calculation(self):
        """Test basic objectif_jour calculation."""
        # Monthly cost: 2500 + 1000 = 3500
        # Annual cost: 3500 * 12 = 42000
        # Available margin: 1 - 0.10 - 0.25 = 0.65
        # seuil_annuel_ht: 42000 / 0.65 = 64615.38
        # seuil_annuel_ttc: 64615.38 × 1.2 = 77538.46  ← ×1.2 TVA added 2026-05-05
        # With safety + profit (15%): 77538.46 × 1.15 = 89169.23
        # Days per year: 5 * 45.6 = 228
        # Daily: 89169.23 / 228 = 391.09
        result = compute_objectif_jour_from_salary(
            salaire_brut=Decimal("2500"),
            cotisations_patronales=Decimal("1000"),
        )
        
        # Verify it's a positive value in the right ballpark
        assert result > 0
        assert 350 < float(result) < 450

    def test_zero_salary(self):
        """Test with zero salary returns zero."""
        result = compute_objectif_jour_from_salary(
            salaire_brut=Decimal("0"),
            cotisations_patronales=Decimal("0"),
        )
        assert result == Decimal("0")

    def test_custom_parameters(self):
        """Test with custom salon parameters."""
        result = compute_objectif_jour_from_salary(
            salaire_brut=Decimal("2000"),
            cotisations_patronales=Decimal("800"),
            taux_produits=Decimal("0.15"),  # Higher product cost
            taux_charges_fixes=Decimal("0.30"),  # Higher fixed charges
        )
        
        # Higher deductions = higher daily objective needed
        assert result > 0


class TestDefaultTiers:
    """Verify the default tier configuration."""

    def test_default_tiers_exist(self):
        """Verify default tiers are properly configured."""
        assert len(DEFAULT_PRIME_TIERS) == 9
        
        # First tier: 0-600 at 10%
        assert DEFAULT_PRIME_TIERS[0].threshold == Decimal("600")
        assert DEFAULT_PRIME_TIERS[0].percent == Decimal("0.10")
        
        # Last tier: 2700-3000 at 28%
        assert DEFAULT_PRIME_TIERS[-1].threshold == Decimal("3000")
        assert DEFAULT_PRIME_TIERS[-1].percent == Decimal("0.28")

    def test_tiers_are_sorted(self):
        """Verify default tiers are in ascending order."""
        thresholds = [t.threshold for t in DEFAULT_PRIME_TIERS]
        assert thresholds == sorted(thresholds)

    def test_tiers_are_increasing_rate(self):
        """Verify rates increase with each tier."""
        rates = [float(t.percent) for t in DEFAULT_PRIME_TIERS]
        # Each rate should be >= previous
        for i in range(1, len(rates)):
            assert rates[i] >= rates[i - 1]
