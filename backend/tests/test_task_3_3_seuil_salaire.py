"""
Unit tests for the Seuil de Rentabilité Salaire calculator (Task 3.3).

Pure calculation tests — no database required. Run locally:
    python -m pytest tests/test_task_3_3_seuil_salaire.py -v

Or inside Docker:
    docker compose exec backend python -m pytest tests/test_task_3_3_seuil_salaire.py -v

Test case source: dev-docs/CALCULATION_FORMULAS.md Section 3
and dev-docs/resources/05-calculation-reference.md Section 2.

JULIE test case from Eric's Excel:
  Input:  heures=35, brut=2200, charges=100, produits=10%, charges_fixes=25%,
          sécurité=5%, bénéfice=10%, jours=5, semaines=45.6

  Expected:
    heures_mois = 151.666667
    cout_total_mois = 2300
    cout_total_annuel = 27600
    marge_disponible = 0.65
    seuil_annuel_ht = 42461.538462 → rounds to 42461.54
    seuil_annuel_ttc = 50953.846154 → rounds to 50953.85
    pct_supplement = 0.15
    objectif_min_ttc = 58596.923077 → rounds to 58596.92
    objectif_min_ht = 48830.769231 → rounds to 48830.77
    benefice_brut_ht = 6369.230769 → rounds to 6369.23
    nb_jours_an = 228
    objectif_jour_ttc = 257.004049 → rounds to 257.00
    objectif_mois_ttc = 5782.59

  Part-time (120h/month):
    objectif_mois_partiel_ttc = 4575.236909 → rounds to 4575.24
    objectif_horaire_ttc = 38.126974 → rounds to 38.13
"""

import pytest
from decimal import Decimal

from app.calculations.seuil_salaire import (
    compute_seuil_salaire,
    SeuilSalaireResult,
)


class TestJulieCase:
    """JULIE test case from Eric's Excel — the primary acceptance criterion."""

    def test_full_time_julie(self) -> None:
        """
        Full-time JULIE: 35h/week, brut=2200, charges=100.
        From CALCULATION_FORMULAS.md Section 3 / Excel "seuil renta salaire".
        """
        result = compute_seuil_salaire(
            heures_semaine=Decimal("35"),
            salaire_brut=Decimal("2200"),
            cotisations_patronales=Decimal("100"),
        )

        # ── Inputs echoed ───────────────────────────────────────────────────────
        assert result.heures_semaine == Decimal("35.00")
        assert result.salaire_brut == Decimal("2200.00")
        assert result.cotisations_patronales == Decimal("100.00")
        assert result.taux_produits == Decimal("0.1000")
        assert result.taux_charges_fixes == Decimal("0.2500")
        assert result.pct_securite == Decimal("0.0500")
        assert result.pct_benefice == Decimal("0.1000")
        assert result.jours_semaine == Decimal("5")
        assert result.semaines_an == Decimal("45.6")

        # ── Monthly hours ──────────────────────────────────────────────────────
        # 35 × 52 / 12 = 151.666667
        assert result.heures_mois == Decimal("151.67")

        # ── Cost calculations ─────────────────────────────────────────────────
        assert result.cout_total_mois == Decimal("2300.00")
        assert result.cout_total_annuel == Decimal("27600.00")

        # ── Margins ────────────────────────────────────────────────────────────
        # 1 − 0.10 − 0.25 = 0.65
        assert result.marge_disponible == Decimal("0.6500")

        # ── Break-even annual ──────────────────────────────────────────────────
        # 27600 / 0.65 = 42461.538462 → 42461.54
        assert result.seuil_annuel_ht == Decimal("42461.54")
        # 42461.538462 × 1.2 = 50953.846154 → 50953.85
        assert result.seuil_annuel_ttc == Decimal("50953.85")

        # ── Objectives ───────────────────────────────────────────────────────
        # pct_supplement = 0.05 + 0.10 = 0.15
        assert result.pct_supplement == Decimal("0.1500")
        # 50953.846154 × 1.15 = 58596.923077 → 58596.92
        assert result.objectif_min_ttc == Decimal("58596.92")
        # 58596.923077 / 1.2 = 48830.769231 → 48830.77
        assert result.objectif_min_ht == Decimal("48830.77")
        # 48830.769231 − 42461.538462 = 6369.230769 → 6369.23
        assert result.benefice_brut_ht == Decimal("6369.23")

        # ── Daily objective ───────────────────────────────────────────────────
        # 5 × 45.6 = 228
        assert result.nb_jours_an == Decimal("228.00")
        # 58596.923077 / 228 = 257.004049 → 257.00
        assert result.objectif_jour_ttc == Decimal("257.00")

        # ── Monthly objectives ─────────────────────────────────────────────────
        assert result.jours_mois == Decimal("22.50")
        # 257.004049 × 22.5 = 5782.591103 → 5782.59
        assert result.objectif_mois_ttc == Decimal("5782.59")

    def test_part_time_julie(self) -> None:
        """
        Part-time JULIE: same params + 120h/month.
        Expected: objectif_mois_partiel_ttc = 4575.24, objectif_horaire = 38.13.
        """
        result = compute_seuil_salaire(
            heures_semaine=Decimal("35"),
            salaire_brut=Decimal("2200"),
            cotisations_patronales=Decimal("100"),
            heures_mois_partiel=Decimal("120"),
        )

        # Daily and full-time monthly are same
        assert result.objectif_jour_ttc == Decimal("257.00")
        assert result.objectif_mois_ttc == Decimal("5782.59")

        # Part-time specifics
        assert result.heures_mois_partiel == Decimal("120.00")
        # ratio = 120 / 151.666667 = 0.791209
        # objectif_partiel = 257.004049 × 22.5 × 0.791209 = 4575.236909 → 4575.24
        assert result.objectif_mois_partiel_ttc == Decimal("4575.24")
        # 4575.236909 / 120 = 38.126974 → 38.13
        assert result.objectif_horaire_ttc == Decimal("38.13")


class TestEdgeCases:
    """Boundary and error cases."""

    def test_zero_cotisations(self) -> None:
        """Cotisations patronales can be zero (e.g. apprenti with partial exonération)."""
        result = compute_seuil_salaire(
            heures_semaine=Decimal("35"),
            salaire_brut=Decimal("1800"),
            cotisations_patronales=Decimal("0"),
        )
        assert result.cout_total_mois == Decimal("1800.00")
        assert result.cout_total_annuel == Decimal("21600.00")
        # Without part-time, optional fields are None
        assert result.objectif_mois_partiel_ttc is None
        assert result.objectif_horaire_ttc is None

    def test_non_default_taux(self) -> None:
        """Custom taux_produits and taux_charges_fixes change marge_disponible."""
        result = compute_seuil_salaire(
            heures_semaine=Decimal("35"),
            salaire_brut=Decimal("2000"),
            cotisations_patronales=Decimal("200"),
            taux_produits=Decimal("0.08"),
            taux_charges_fixes=Decimal("0.20"),
        )
        # marge = 1 − 0.08 − 0.20 = 0.72
        assert result.marge_disponible == Decimal("0.7200")
        # cout_annuel = 2200 × 12 = 26400
        # seuil_ht = 26400 / 0.72 = 36666.67
        assert result.seuil_annuel_ht == Decimal("36666.67")

    def test_non_default_pct_supplements(self) -> None:
        """Custom safety and profit margins change the supplement %."""
        result = compute_seuil_salaire(
            heures_semaine=Decimal("35"),
            salaire_brut=Decimal("2000"),
            cotisations_patronales=Decimal("100"),
            pct_securite=Decimal("0.10"),
            pct_benefice=Decimal("0.15"),
        )
        # pct_supplement = 0.10 + 0.15 = 0.25
        assert result.pct_supplement == Decimal("0.2500")

    def test_negative_heures_rejected(self) -> None:
        with pytest.raises(ValueError, match="heures_semaine must be >= 0"):
            compute_seuil_salaire(
                heures_semaine=Decimal("-1"),
                salaire_brut=Decimal("2000"),
                cotisations_patronales=Decimal("100"),
            )

    def test_negative_salaire_rejected(self) -> None:
        with pytest.raises(ValueError, match="salaire_brut must be >= 0"):
            compute_seuil_salaire(
                heures_semaine=Decimal("35"),
                salaire_brut=Decimal("-100"),
                cotisations_patronales=Decimal("100"),
            )

    def test_taux_produits_too_high_rejected(self) -> None:
        with pytest.raises(ValueError, match="marge_disponible must be > 0"):
            compute_seuil_salaire(
                heures_semaine=Decimal("35"),
                salaire_brut=Decimal("2000"),
                cotisations_patronales=Decimal("100"),
                taux_produits=Decimal("0.80"),  # 80% products + 25% fixed = > 100%
            )

    def test_taux_produits_individual_bound_rejected(self) -> None:
        """taux_produits > 1.0 triggers the individual bounds check before marge."""
        with pytest.raises(ValueError, match="taux_produits must be between 0 and 1"):
            compute_seuil_salaire(
                heures_semaine=Decimal("35"),
                salaire_brut=Decimal("2000"),
                cotisations_patronales=Decimal("100"),
                taux_produits=Decimal("1.50"),  # > 1.0 triggers individual check
            )

    def test_marge_disponible_zero_raises(self) -> None:
        """taux_produits + taux_charges_fixes must be < 1."""
        with pytest.raises(ValueError, match="marge_disponible must be > 0"):
            compute_seuil_salaire(
                heures_semaine=Decimal("35"),
                salaire_brut=Decimal("2000"),
                cotisations_patronales=Decimal("100"),
                taux_produits=Decimal("0.50"),
                taux_charges_fixes=Decimal("0.50"),
            )

    def test_zero_jours_raises(self) -> None:
        """jours_semaine × semaines_an must be > 0."""
        with pytest.raises(ValueError, match="jours_semaine × semaines_an must be > 0"):
            compute_seuil_salaire(
                heures_semaine=Decimal("35"),
                salaire_brut=Decimal("2000"),
                cotisations_patronales=Decimal("100"),
                jours_semaine=Decimal("0"),
            )

    def test_returns_seuil_salaire_result(self) -> None:
        """Return type is SeuilSalaireResult dataclass."""
        result = compute_seuil_salaire(
            heures_semaine=Decimal("35"),
            salaire_brut=Decimal("2200"),
            cotisations_patronales=Decimal("100"),
        )
        assert isinstance(result, SeuilSalaireResult)


class TestIntermediateValues:
    """Spot-check intermediate values are computed correctly."""

    def test_intermediate_values_match_excel(self) -> None:
        """
        Verify every intermediate value matches the Excel column layout.
        From 05-calculation-reference.md Section 2 (JULIE example).
        """
        result = compute_seuil_salaire(
            heures_semaine=Decimal("35"),
            salaire_brut=Decimal("2200"),
            cotisations_patronales=Decimal("100"),
        )

        # heures_mois
        assert result.heures_mois == Decimal("151.67")

        # cout
        assert result.cout_total_mois == Decimal("2300.00")
        assert result.cout_total_annuel == Decimal("27600.00")

        # marge
        assert result.marge_disponible == Decimal("0.6500")

        # seuils
        assert result.seuil_annuel_ht == Decimal("42461.54")
        assert result.seuil_annuel_ttc == Decimal("50953.85")

        # supplements
        assert result.pct_supplement == Decimal("0.1500")
        assert result.objectif_min_ttc == Decimal("58596.92")
        assert result.objectif_min_ht == Decimal("48830.77")
        assert result.benefice_brut_ht == Decimal("6369.23")

        # objectifs
        assert result.nb_jours_an == Decimal("228.00")
        assert result.objectif_jour_ttc == Decimal("257.00")
        assert result.jours_mois == Decimal("22.50")
        assert result.objectif_mois_ttc == Decimal("5782.59")
