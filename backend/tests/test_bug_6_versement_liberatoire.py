"""
Tests for Bug 6: Versement libératoire (VL) adds to URSSAF rate.

WHY: When an AE checks "versement libératoire sur l'impôt", their total URSSAF
payment must include both:
  - Social charges (subject to ACRE reduction)
  - IR replacement flat rate (NOT subject to ACRE)

Rates (source: service-public.fr, 2026):
  bic_vente:           social 12.3% + VL 1.0%  = 13.3%
  bic_services:        social 21.2% + VL 1.7%  = 22.9%
  bnc_non_reglementee: social 25.6% + VL 2.2%  = 27.8%
  bnc_cipav:           social 23.2% + VL 2.2%  = 25.4%

ACRE does not reduce the VL component.
"""
from decimal import Decimal

import pytest

from app.calculations.social_charges import (
    AE_VL_RATES,
    calc_ae_urssaf_cotisations,
    get_ae_urssaf_rate,
)


class TestVLRatesDict:
    """Basic sanity checks on the AE_VL_RATES constant."""

    def test_bic_services_vl_rate(self):
        """BIC services (most coiffeurs): VL = 1.7%."""
        assert AE_VL_RATES["bic_services"] == Decimal("0.017")

    def test_bic_vente_vl_rate(self):
        """BIC vente (product sales): VL = 1.0%."""
        assert AE_VL_RATES["bic_vente"] == Decimal("0.010")

    def test_bnc_vl_rates(self):
        """BNC non-réglementé and CIPAV: both VL = 2.2%."""
        assert AE_VL_RATES["bnc_non_reglementee"] == Decimal("0.022")
        assert AE_VL_RATES["bnc_cipav"] == Decimal("0.022")

    def test_all_activity_types_covered(self):
        """All four URSSAF types must also have a VL rate."""
        from app.calculations.social_charges import AE_URSSAF_RATES
        assert set(AE_VL_RATES.keys()) == set(AE_URSSAF_RATES.keys())


class TestGetAeUrssafRateWithVL:
    """Test get_ae_urssaf_rate with versement_liberatoire=True."""

    def test_bic_services_no_vl(self):
        """Without VL: standard 21.2%."""
        rate, resolved = get_ae_urssaf_rate("bic_services", versement_liberatoire=False)
        assert rate == Decimal("0.212")
        assert resolved == "bic_services"

    def test_bic_services_with_vl(self):
        """With VL: 21.2% + 1.7% = 22.9%."""
        rate, resolved = get_ae_urssaf_rate("bic_services", versement_liberatoire=True)
        assert rate == Decimal("0.229")
        assert resolved == "bic_services"

    def test_bic_vente_with_vl(self):
        """BIC vente: 12.3% + 1.0% = 13.3%."""
        rate, _ = get_ae_urssaf_rate("bic_vente", versement_liberatoire=True)
        assert rate == Decimal("0.133")

    def test_bnc_non_reglementee_with_vl(self):
        """BNC: 25.6% + 2.2% = 27.8%."""
        rate, _ = get_ae_urssaf_rate("bnc_non_reglementee", versement_liberatoire=True)
        assert rate == Decimal("0.278")

    def test_bnc_cipav_with_vl(self):
        """BNC CIPAV: 23.2% + 2.2% = 25.4%."""
        rate, _ = get_ae_urssaf_rate("bnc_cipav", versement_liberatoire=True)
        assert rate == Decimal("0.254")

    def test_none_activity_type_falls_back_to_bic_services(self):
        """Unknown type falls back to bic_services, VL still applied."""
        rate, resolved = get_ae_urssaf_rate(None, versement_liberatoire=True)
        assert resolved == "bic_services"
        assert rate == Decimal("0.229")


class TestAcreDoesNotReduceVL:
    """
    CRITICAL: ACRE exonerates SOCIAL CHARGES only, not the IR-replacement VL.
    """

    def test_acre_50pct_does_not_reduce_vl_component(self):
        """
        ACRE 50%: social 21.2% → 10.6%, VL stays at 1.7%.
        Total = 10.6% + 1.7% = 12.3%.
        """
        rate, _ = get_ae_urssaf_rate(
            "bic_services",
            has_acre=True,
            acre_apres_juillet_2026=False,
            versement_liberatoire=True,
        )
        # 21.2% × 0.5 = 0.106; + VL 1.7% = 0.123
        assert rate == Decimal("0.1230")

    def test_acre_25pct_does_not_reduce_vl_component(self):
        """
        ACRE 25% (after July 2026): social 21.2% → 15.9%, VL stays at 1.7%.
        Total = 15.9% + 1.7% = 17.6%.
        """
        rate, _ = get_ae_urssaf_rate(
            "bic_services",
            has_acre=True,
            acre_apres_juillet_2026=True,
            versement_liberatoire=True,
        )
        # 21.2% × 0.75 = 0.159; + VL 1.7% = 0.176
        assert rate == Decimal("0.1760")

    def test_acre_without_vl_unchanged(self):
        """Sanity: ACRE without VL still halves the social rate correctly."""
        rate, _ = get_ae_urssaf_rate(
            "bic_services",
            has_acre=True,
            acre_apres_juillet_2026=False,
            versement_liberatoire=False,
        )
        assert rate == Decimal("0.106")

    def test_vl_without_acre_standard_rate_plus_vl(self):
        """Sanity: VL without ACRE = base + VL."""
        rate, _ = get_ae_urssaf_rate(
            "bic_services",
            has_acre=False,
            versement_liberatoire=True,
        )
        assert rate == Decimal("0.229")


class TestCalcAeUrssafCotisationsWithVL:
    """Test the cotisations amount calculation including VL."""

    def test_bic_services_4000_no_vl(self):
        """4000 × 21.2% = 848.00 € (without VL)."""
        amount, rate, resolved = calc_ae_urssaf_cotisations(
            ca_mensuel=Decimal("4000"),
            ae_activity_type="bic_services",
            versement_liberatoire=False,
        )
        assert amount == Decimal("848.00")
        assert rate == Decimal("0.212")
        assert resolved == "bic_services"

    def test_bic_services_4000_with_vl(self):
        """4000 × 22.9% = 916.00 € (with VL 1.7% added)."""
        amount, rate, resolved = calc_ae_urssaf_cotisations(
            ca_mensuel=Decimal("4000"),
            ae_activity_type="bic_services",
            versement_liberatoire=True,
        )
        assert amount == Decimal("916.00")
        assert rate == Decimal("0.2290")
        assert resolved == "bic_services"

    def test_bic_services_3000_acre_with_vl(self):
        """
        3000 × (10.6% + 1.7%) = 3000 × 12.3% = 369.00 €.
        ACRE 50% + VL 1.7%.
        """
        amount, rate, _ = calc_ae_urssaf_cotisations(
            ca_mensuel=Decimal("3000"),
            ae_activity_type="bic_services",
            has_acre=True,
            acre_apres_juillet_2026=False,
            versement_liberatoire=True,
        )
        assert rate == Decimal("0.1230")
        assert amount == Decimal("369.00")

    def test_zero_ca_no_cotisations(self):
        """Zero CA produces zero cotisations even with VL."""
        amount, rate, _ = calc_ae_urssaf_cotisations(
            ca_mensuel=Decimal("0"),
            ae_activity_type="bic_services",
            versement_liberatoire=True,
        )
        assert amount == Decimal("0.00")
