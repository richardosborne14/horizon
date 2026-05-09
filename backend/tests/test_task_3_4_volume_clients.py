"""
Unit tests for Task 3.4: Volume Clients Calculator.

Test cases from Eric's Excel (Classeur1 > Nb de clients sheet):
- Test case: objectif=240000, pct_f=0.80, montant_f=65 → fiche_moyenne=58, nb_visites=4137.93
- Daily breakdown: 10.61 F/day, 2.65 H/day
- Simulation: +3% female ticket → gain ≈ 6455
"""

import pytest
from decimal import Decimal

from app.calculations.volume_clients import (
    compute_volume_clients,
    simulate_ticket_change,
    VolumeClientsResult,
    SimulationResult,
)


class TestVolumeClientsCalculation:
    """Test the volume clients calculation engine."""

    def test_basic_calculation(self):
        """Test case from Excel: fiche_moyenne=58, nb_visites=4137.93"""
        result = compute_volume_clients(
            objectif_ca=Decimal("240000"),
            pct_clients_f=Decimal("0.80"),
            pct_clients_h=Decimal("0.20"),
            montant_moyen_f=Decimal("65"),
            montant_moyen_h=Decimal("30"),
            nb_visites_moyen_f=Decimal("4.2"),
            nb_visites_moyen_h=Decimal("6.6"),
            jours_semaine=Decimal("6"),
            semaines_an=Decimal("52"),
        )

        # Core calculations from Excel
        assert result.fiche_moyenne_globale == Decimal("58.00")
        assert result.nb_visites_total_an == Decimal("4137.93")
        assert result.nb_visites_f == Decimal("3310.34")
        assert result.nb_visites_h == Decimal("827.59")

        # Client file calculations
        # fichier_f = 3310.34 / 4.2 = 788.18
        # fichier_h = 827.59 / 6.6 = 125.39
        assert result.nb_clients_fichier_f == Decimal("788.18")
        assert result.nb_clients_fichier_h == Decimal("125.39")
        assert result.nb_clients_fichier_total == Decimal("913.57")

        # Revenue split (actual values with rounding)
        # Due to rounding in intermediate steps: 215172.41 and 24827.59
        assert result.ca_femmes == Decimal("215172.41")
        assert result.ca_hommes == Decimal("24827.59")
        assert result.ca_total == Decimal("240000.00")

    def test_daily_breakdown(self):
        """Test daily breakdown: 10.61 F/day, 2.65 H/day"""
        result = compute_volume_clients(
            objectif_ca=Decimal("240000"),
            pct_clients_f=Decimal("0.80"),
            pct_clients_h=Decimal("0.20"),
            montant_moyen_f=Decimal("65"),
            montant_moyen_h=Decimal("30"),
            nb_visites_moyen_f=Decimal("4.2"),
            nb_visites_moyen_h=Decimal("6.6"),
            jours_semaine=Decimal("6"),
            semaines_an=Decimal("52"),
        )

        # jours_an = 6 * 52 = 312
        assert result.jours_an == Decimal("312")

        # visites_f_jour = 3310.34 / 312 = 10.61
        # visites_h_jour = 827.59 / 312 = 2.65
        assert result.visites_f_jour == Decimal("10.61")
        assert result.visites_h_jour == Decimal("2.65")
        assert result.visites_total_jour == Decimal("13.26")

        # ca_jour = 240000 / 312 = 769.23
        assert result.ca_jour == Decimal("769.23")

    def test_monthly_breakdown_exists(self):
        """Test that monthly breakdown is generated with 12 months."""
        result = compute_volume_clients(
            objectif_ca=Decimal("240000"),
            pct_clients_f=Decimal("0.80"),
            pct_clients_h=Decimal("0.20"),
            montant_moyen_f=Decimal("65"),
            montant_moyen_h=Decimal("30"),
            nb_visites_moyen_f=Decimal("4.2"),
            nb_visites_moyen_h=Decimal("6.6"),
            jours_semaine=Decimal("6"),
            semaines_an=Decimal("52"),
        )

        assert len(result.monthly_breakdown) == 12

        # Check first month (January)
        jan = result.monthly_breakdown[0]
        assert jan.month_name == "Janvier"
        assert jan.jours_ouverture == 31
        assert jan.visites_f > 0
        assert jan.ca_f > 0

        # Check February (28 days)
        feb = result.monthly_breakdown[1]
        assert feb.month_name == "Février"
        assert feb.jours_ouverture == 28

        # Check July (31 days)
        jul = result.monthly_breakdown[6]
        assert jul.month_name == "Juillet"
        assert jul.jours_ouverture == 31

    def test_default_values(self):
        """Test that default values work correctly."""
        result = compute_volume_clients(objectif_ca=Decimal("100000"))

        # Check defaults were applied
        assert result.pct_clients_f == Decimal("0.8000")
        assert result.pct_clients_h == Decimal("0.2000")
        assert result.montant_moyen_f == Decimal("65.00")
        assert result.montant_moyen_h == Decimal("30.00")
        assert result.nb_visites_moyen_f == Decimal("4.2000")
        assert result.nb_visites_moyen_h == Decimal("6.6000")
        assert result.jours_semaine == Decimal("6")
        assert result.semaines_an == Decimal("52")

    def test_all_female_clientele(self):
        """Test with 100% female clientele."""
        result = compute_volume_clients(
            objectif_ca=Decimal("100000"),
            pct_clients_f=Decimal("1.0"),
            pct_clients_h=Decimal("0.0"),
            montant_moyen_f=Decimal("60"),
        )

        assert result.nb_visites_h == Decimal("0.00")
        assert result.nb_clients_fichier_h == Decimal("0.00")
        assert result.nb_visites_total_an == result.nb_visites_f

    def test_all_male_clientele(self):
        """Test with 100% male clientele."""
        result = compute_volume_clients(
            objectif_ca=Decimal("100000"),
            pct_clients_f=Decimal("0.0"),
            pct_clients_h=Decimal("1.0"),
            montant_moyen_h=Decimal("25"),
        )

        assert result.nb_visites_f == Decimal("0.00")
        assert result.nb_clients_fichier_f == Decimal("0.00")
        assert result.nb_visites_total_an == result.nb_visites_h


class TestSimulation:
    """Test the ticket price simulation feature."""

    def test_simulation_3_percent_female(self):
        """Test simulation: +3% on female ticket → gain ≈ 6455"""
        base = compute_volume_clients(
            objectif_ca=Decimal("240000"),
            pct_clients_f=Decimal("0.80"),
            pct_clients_h=Decimal("0.20"),
            montant_moyen_f=Decimal("65"),
            montant_moyen_h=Decimal("30"),
            nb_visites_moyen_f=Decimal("4.2"),
            nb_visites_moyen_h=Decimal("6.6"),
            jours_semaine=Decimal("6"),
            semaines_an=Decimal("52"),
        )

        sim = simulate_ticket_change(base, pct_change_f=Decimal("0.03"))

        # New female ticket: 65 * 1.03 = 66.95
        assert sim.new_montant_f == Decimal("66.95")
        assert sim.new_montant_h == Decimal("30.00")  # Unchanged

        # Gain from Excel target: ~6455 (actual: 6454.96 due to rounding)
        assert sim.gain == Decimal("6454.96")

        # New CA = 240000 + 6454.96 = 246454.96
        assert sim.new_ca_total == Decimal("246454.96")

    def test_simulation_5_percent_male(self):
        """Test simulation: +5% on male ticket."""
        base = compute_volume_clients(
            objectif_ca=Decimal("240000"),
            pct_clients_f=Decimal("0.80"),
            pct_clients_h=Decimal("0.20"),
            montant_moyen_f=Decimal("65"),
            montant_moyen_h=Decimal("30"),
        )

        sim = simulate_ticket_change(base, pct_change_h=Decimal("0.05"))

        # New male ticket: 30 * 1.05 = 31.50
        assert sim.new_montant_h == Decimal("31.50")
        assert sim.new_montant_f == Decimal("65.00")  # Unchanged

        # Should have positive gain
        assert sim.gain > Decimal("0")

    def test_simulation_both_genders(self):
        """Test simulation with both genders changing."""
        base = compute_volume_clients(
            objectif_ca=Decimal("240000"),
            pct_clients_f=Decimal("0.80"),
            pct_clients_h=Decimal("0.20"),
            montant_moyen_f=Decimal("65"),
            montant_moyen_h=Decimal("30"),
        )

        sim = simulate_ticket_change(
            base,
            pct_change_f=Decimal("0.03"),
            pct_change_h=Decimal("0.05"),
        )

        # Both changed
        assert sim.new_montant_f == Decimal("66.95")
        assert sim.new_montant_h == Decimal("31.50")

        # Gain should be larger than just female change
        assert sim.gain > Decimal("6454")

    def test_simulation_negative_change(self):
        """Test simulation with price decrease (negative change)."""
        base = compute_volume_clients(
            objectif_ca=Decimal("240000"),
            pct_clients_f=Decimal("0.80"),
            pct_clients_h=Decimal("0.20"),
            montant_moyen_f=Decimal("65"),
            montant_moyen_h=Decimal("30"),
        )

        sim = simulate_ticket_change(base, pct_change_f=Decimal("-0.05"))

        # Negative gain (loss)
        assert sim.gain < Decimal("0")
        assert sim.new_ca_total < base.objectif_ca

    def test_simulation_zero_change(self):
        """Test simulation with no change."""
        base = compute_volume_clients(
            objectif_ca=Decimal("240000"),
            pct_clients_f=Decimal("0.80"),
            pct_clients_h=Decimal("0.20"),
            montant_moyen_f=Decimal("65"),
            montant_moyen_h=Decimal("30"),
        )

        sim = simulate_ticket_change(base)

        # No change (small epsilon due to rounding)
        assert abs(sim.gain) < Decimal("0.01")
        assert sim.new_ca_total == base.objectif_ca


class TestValidation:
    """Test input validation."""

    def test_validation_zero_objectif_ca(self):
        """Test that zero objectif_ca raises ValueError."""
        with pytest.raises(ValueError, match="objectif_ca must be > 0"):
            compute_volume_clients(objectif_ca=Decimal("0"))

    def test_validation_negative_objectif_ca(self):
        """Test that negative objectif_ca raises ValueError."""
        with pytest.raises(ValueError, match="objectif_ca must be > 0"):
            compute_volume_clients(objectif_ca=Decimal("-100000"))

    def test_validation_percentage_sum_not_100(self):
        """Test that percentages not summing to 100% raises ValueError."""
        with pytest.raises(ValueError):
            compute_volume_clients(
                objectif_ca=Decimal("100000"),
                pct_clients_f=Decimal("0.70"),
                pct_clients_h=Decimal("0.20"),  # Sum = 0.90
            )

    def test_validation_percentage_over_100(self):
        """Test that percentages over 100% raises ValueError."""
        with pytest.raises(ValueError):
            compute_volume_clients(
                objectif_ca=Decimal("100000"),
                pct_clients_f=Decimal("0.60"),
                pct_clients_h=Decimal("0.50"),  # Sum = 1.10
            )

    def test_validation_percentage_out_of_range(self):
        """Test that percentages outside 0-1 range raise ValueError."""
        with pytest.raises(ValueError, match="pct_clients_f must be between 0 and 1"):
            compute_volume_clients(
                objectif_ca=Decimal("100000"),
                pct_clients_f=Decimal("1.5"),
                pct_clients_h=Decimal("-0.5"),
            )


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_small_revenue_target(self):
        """Test with very small revenue target."""
        result = compute_volume_clients(objectif_ca=Decimal("100"))

        assert result.objectif_ca == Decimal("100.00")
        assert result.nb_visites_total_an > 0

    def test_very_large_revenue_target(self):
        """Test with large revenue target."""
        result = compute_volume_clients(objectif_ca=Decimal("1000000"))

        assert result.objectif_ca == Decimal("1000000.00")
        assert result.nb_visites_total_an > 0

    def test_high_ticket_prices(self):
        """Test with high average ticket prices."""
        result = compute_volume_clients(
            objectif_ca=Decimal("240000"),
            montant_moyen_f=Decimal("150"),
            montant_moyen_h=Decimal("80"),
        )

        # Higher tickets = fewer visits needed
        assert result.nb_visites_total_an < Decimal("4137.93")

    def test_low_visit_frequency(self):
        """Test with low visit frequency (infrequent clients)."""
        result = compute_volume_clients(
            objectif_ca=Decimal("240000"),
            nb_visites_moyen_f=Decimal("2.0"),
            nb_visites_moyen_h=Decimal("3.0"),
        )

        # Lower visit frequency = more unique clients needed
        assert result.nb_clients_fichier_total > Decimal("913.57")

    def test_high_visit_frequency(self):
        """Test with high visit frequency (very frequent clients)."""
        result = compute_volume_clients(
            objectif_ca=Decimal("240000"),
            nb_visites_moyen_f=Decimal("10.0"),
            nb_visites_moyen_h=Decimal("12.0"),
        )

        # Higher visit frequency = fewer unique clients needed
        assert result.nb_clients_fichier_total < Decimal("913.57")


class TestExcelReferenceCase:
    """
    Reference test case from Eric's Excel file.

    From CALCULATION_FORMULAS.md:
    Inputs:
      objectif = 240000, pct_f = 0.80, montant_f = 65
      pct_h = 0.20, montant_h = 30
      visites_f = 4.2/year, visites_h = 6.6/year
      jours_semaine = 6, semaines_an = 52

    Expected:
      fiche_moyenne = 58
      nb_visites_total = 4137.93
      fichier_f = 788.18, fichier_h = 125.39
      jours_an = 312
      visites_f_jour = 10.61, visites_h_jour = 2.65

    Simulation: +3% on female ticket:
      new_montant_f = 66.95
      new_ca ≈ 246454.96
      gain ≈ 6454.96
    """

    def test_excel_reference_full(self):
        """Verify the exact test case from Eric's Excel matches."""
        result = compute_volume_clients(
            objectif_ca=Decimal("240000"),
            pct_clients_f=Decimal("0.80"),
            pct_clients_h=Decimal("0.20"),
            montant_moyen_f=Decimal("65"),
            montant_moyen_h=Decimal("30"),
            nb_visites_moyen_f=Decimal("4.2"),
            nb_visites_moyen_h=Decimal("6.6"),
            jours_semaine=Decimal("6"),
            semaines_an=Decimal("52"),
        )

        # Exact values from Excel
        assert result.fiche_moyenne_globale == Decimal("58.00"), "fiche_moyenne should be 58.00"
        assert result.nb_visites_total_an == Decimal("4137.93"), "nb_visites_total should be 4137.93"
        assert result.nb_visites_f == Decimal("3310.34"), "nb_visites_f should be 3310.34"
        assert result.nb_visites_h == Decimal("827.59"), "nb_visites_h should be 827.59"
        assert result.nb_clients_fichier_f == Decimal("788.18"), "fichier_f should be 788.18"
        assert result.nb_clients_fichier_h == Decimal("125.39"), "fichier_h should be 125.39"
        assert result.nb_clients_fichier_total == Decimal("913.57"), "fichier_total should be 913.57"
        assert result.jours_an == Decimal("312"), "jours_an should be 312"
        assert result.visites_f_jour == Decimal("10.61"), "visites_f_jour should be 10.61"
        assert result.visites_h_jour == Decimal("2.65"), "visites_h_jour should be 2.65"

    def test_excel_simulation_reference(self):
        """Verify the simulation gain matches Excel (within rounding tolerance)."""
        base = compute_volume_clients(
            objectif_ca=Decimal("240000"),
            pct_clients_f=Decimal("0.80"),
            pct_clients_h=Decimal("0.20"),
            montant_moyen_f=Decimal("65"),
            montant_moyen_h=Decimal("30"),
            nb_visites_moyen_f=Decimal("4.2"),
            nb_visites_moyen_h=Decimal("6.6"),
            jours_semaine=Decimal("6"),
            semaines_an=Decimal("52"),
        )

        sim = simulate_ticket_change(base, pct_change_f=Decimal("0.03"))

        # Exact values from simulation (accounting for rounding)
        assert sim.new_montant_f == Decimal("66.95"), "new_montant_f should be 66.95"
        assert sim.gain == Decimal("6454.96"), "gain should be 6454.96"
        assert sim.new_ca_total == Decimal("246454.96"), "new_ca_total should be 246454.96"
