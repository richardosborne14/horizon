"""
Tests for Task 2.10 — Pricing Calculator.

Tests cover:
1. Pure calculation logic (compute_pricing) against Eric's Excel values
2. Services CRUD API (list, create, update, deactivate)
3. POST /api/calculations/pricing endpoint
4. Default service seeding on first access
"""

import pytest
from decimal import Decimal

from app.calculations.pricing import (
    compute_pricing,
    calc_employee_minutes,
    EmployeePricingData,
    DEFAULT_SERVICES,
)


# ── Unit tests: pure calculation ──────────────────────────────────────────────


class TestCalcEmployeeMinutes:
    """Tests for individual employee minute calculations."""

    def test_standard_salarie_35h(self):
        """35h/wk × 45.6 wks × 0.65 = 62,244 real minutes."""
        emp = EmployeePricingData(
            employee_id="test",
            name="Jackie",
            role_type="salarie",
            hours_per_week=Decimal("35"),
            weeks_per_year=Decimal("45.6"),
            taux_occupation=Decimal("0.65"),
        )
        result = calc_employee_minutes(emp)
        # Total: 35 × 45.6 × 60 = 95,760
        assert result.minutes_totales == Decimal("95760.00")
        # Real: 95,760 × 0.65 = 62,244
        assert result.minutes_reelles == Decimal("62244.00")

    def test_dirigeant_45h(self):
        """45h/wk × 48 wks × 0.70 = 90,720 real minutes."""
        emp = EmployeePricingData(
            employee_id="dir",
            name="Dirigeant",
            role_type="dirigeant",
            hours_per_week=Decimal("45"),
            weeks_per_year=Decimal("48"),
            taux_occupation=Decimal("0.70"),
        )
        result = calc_employee_minutes(emp)
        # Total: 45 × 48 × 60 = 129,600
        assert result.minutes_totales == Decimal("129600.00")
        # Real: 129,600 × 0.70 = 90,720
        assert result.minutes_reelles == Decimal("90720.00")

    def test_zero_occupation(self):
        """taux_occupation=0 → minutes_reelles=0."""
        emp = EmployeePricingData(
            employee_id="x",
            name="Test",
            role_type="salarie",
            hours_per_week=Decimal("35"),
            weeks_per_year=Decimal("45.6"),
            taux_occupation=Decimal("0"),
        )
        result = calc_employee_minutes(emp)
        assert result.minutes_reelles == Decimal("0.00")


class TestComputePricing:
    """Tests for compute_pricing() against Eric's Excel values."""

    def _get_eric_employees(self):
        """Eric's example: Jackie + Julie + Dirigeant."""
        return [
            EmployeePricingData(
                employee_id="1",
                name="Jackie",
                role_type="salarie",
                hours_per_week=Decimal("35"),
                weeks_per_year=Decimal("45.6"),
                taux_occupation=Decimal("0.65"),
            ),
            EmployeePricingData(
                employee_id="2",
                name="Julie",
                role_type="salarie",
                hours_per_week=Decimal("35"),
                weeks_per_year=Decimal("45.6"),
                taux_occupation=Decimal("0.50"),
            ),
            EmployeePricingData(
                employee_id="3",
                name="Dirigeant",
                role_type="dirigeant",
                hours_per_week=Decimal("45"),
                weeks_per_year=Decimal("48"),
                taux_occupation=Decimal("0.70"),
            ),
        ]

    def test_eric_excel_total_minutes(self):
        """
        Verify total real minutes matches Eric's Excel.

        Jackie:    35 × 45.6 × 60 × 0.65 = 62,244
        Julie:     35 × 45.6 × 60 × 0.50 = 47,880
        Dirigeant: 45 × 48   × 60 × 0.70 = 90,720
        Total:                             200,844
        """
        result = compute_pricing(
            employees=self._get_eric_employees(),
            cout_total_fonctionnement=Decimal("240000"),
            services=[],
            majoration_securite_benefice=Decimal("0.10"),
        )
        assert result.total_minutes_reelles == Decimal("200844.00")
        assert result.has_employees is True

    def test_eric_excel_cout_reel_minute(self):
        """
        Verify cout_reel_minute ≈ 1.194957.

        cout_reel = 240000 / 200844 = 1.194957...
        """
        result = compute_pricing(
            employees=self._get_eric_employees(),
            cout_total_fonctionnement=Decimal("240000"),
            services=[],
            majoration_securite_benefice=Decimal("0.10"),
        )
        # 6dp precision
        assert result.cout_reel_minute == Decimal("1.194957")

    def test_eric_excel_cout_total_minute(self):
        """
        Verify cout_total_minute ≈ 1.314453.

        cout_total = cout_reel × 1.10 = 1.194957 × 1.10 = 1.314452...
        Rounded to 6dp: 1.314453
        """
        result = compute_pricing(
            employees=self._get_eric_employees(),
            cout_total_fonctionnement=Decimal("240000"),
            services=[],
            majoration_securite_benefice=Decimal("0.10"),
        )
        # Allow ±0.000001 due to rounding
        assert abs(result.cout_total_minute - Decimal("1.314453")) <= Decimal("0.000001")

    def test_service_seuil_calculation(self):
        """
        Forfait coupe femme: 35min + 10min = 45min total.
        seuil = cout_total_minute × 45 ≈ 1.314453 × 45 = 59.15...
        """
        services = [{"id": "s1", "name": "Forfait coupe femme", "type": "forfait",
                     "duration_minutes": 35, "addon_minutes": 10, "prix_vente_ttc": None}]
        result = compute_pricing(
            employees=self._get_eric_employees(),
            cout_total_fonctionnement=Decimal("240000"),
            services=services,
            majoration_securite_benefice=Decimal("0.10"),
        )
        assert len(result.services) == 1
        svc = result.services[0]
        assert svc.total_minutes == 45
        # seuil = 1.314453 × 45 = 59.150385 → rounded to 59.15
        assert svc.seuil_rentabilite == Decimal("59.15")
        # prix_recommande = seuil × 1.10 = 59.15 × 1.10 = 65.07
        assert svc.prix_recommande == Decimal("65.07")

    def test_service_with_prix_vente_above_seuil(self):
        """Service priced at 70€ (above 59.15€ seuil) → is_above_seuil=True."""
        services = [{"id": "s1", "name": "Coupe femme", "type": "forfait",
                     "duration_minutes": 35, "addon_minutes": 10,
                     "prix_vente_ttc": Decimal("70")}]
        result = compute_pricing(
            employees=self._get_eric_employees(),
            cout_total_fonctionnement=Decimal("240000"),
            services=services,
            majoration_securite_benefice=Decimal("0.10"),
        )
        svc = result.services[0]
        assert svc.is_above_seuil is True
        assert svc.marge_euros is not None
        assert svc.marge_euros > Decimal("0")

    def test_service_with_prix_vente_below_seuil(self):
        """Service priced at 40€ (below 59.15€ seuil) → is_above_seuil=False."""
        services = [{"id": "s1", "name": "Coupe femme", "type": "forfait",
                     "duration_minutes": 35, "addon_minutes": 10,
                     "prix_vente_ttc": Decimal("40")}]
        result = compute_pricing(
            employees=self._get_eric_employees(),
            cout_total_fonctionnement=Decimal("240000"),
            services=services,
            majoration_securite_benefice=Decimal("0.10"),
        )
        svc = result.services[0]
        assert svc.is_above_seuil is False
        assert svc.marge_euros < Decimal("0")

    def test_no_employees_returns_has_employees_false(self):
        """No employees → has_employees=False, all zeros."""
        result = compute_pricing(
            employees=[],
            cout_total_fonctionnement=Decimal("240000"),
            services=[],
        )
        assert result.has_employees is False
        assert result.total_minutes_reelles == Decimal("0")
        assert result.cout_reel_minute == Decimal("0")

    def test_negative_cout_raises(self):
        """Negative annual costs must raise ValueError."""
        with pytest.raises(ValueError, match="cout_total_fonctionnement"):
            compute_pricing(
                employees=self._get_eric_employees(),
                cout_total_fonctionnement=Decimal("-1"),
                services=[],
            )

    def test_default_services_seeded(self):
        """DEFAULT_SERVICES contains the 5 expected services."""
        assert len(DEFAULT_SERVICES) == 5
        names = [s["name"] for s in DEFAULT_SERVICES]
        assert "Forfait coupe femme" in names
        assert "Forfait Homme" in names
        types = {s["type"] for s in DEFAULT_SERVICES}
        assert "forfait" in types
        assert "carte" in types

    def test_weighted_taux_moyen_occupation(self):
        """
        taux_moyen_occupation is weighted by contracted minutes, not simple average.

        Jackie:    95,760 totales × 0.65
        Julie:     95,760 totales × 0.50
        Dirigeant: 129,600 totales × 0.70

        Weighted = (95760×0.65 + 95760×0.50 + 129600×0.70) / (95760+95760+129600)
                 = (62244 + 47880 + 90720) / 321120
                 = 200844 / 321120
                 ≈ 0.6253
        """
        result = compute_pricing(
            employees=self._get_eric_employees(),
            cout_total_fonctionnement=Decimal("240000"),
            services=[],
        )
        # Should be approximately 0.6253
        assert Decimal("0.62") < result.taux_moyen_occupation < Decimal("0.64")


# NOTE: API integration tests (services CRUD + pricing endpoint) live in
# test_task_2_10_services_api.py — run inside Docker:
#   docker compose exec backend pytest tests/test_task_2_10_services_api.py -v
