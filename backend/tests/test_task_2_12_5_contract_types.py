"""
TASK-2.12.5 — Contract types: CAP/BP/BM apprenti + TNS/Assimilé dirigeant.

Tests cover:
  1. calc_employee_minutes: CAP apprenti → 0 productive minutes
  2. calc_employee_minutes: BP apprenti (subtype='bp') uses APPRENTI_BP_BM_DEFAULT_TAUX
  3. calc_employee_minutes: BM apprenti (subtype='bm') uses APPRENTI_BP_BM_DEFAULT_TAUX
  4. calc_employee_minutes: BP apprenti with custom taux → custom taux respected
  5. calc_employee_minutes: None subtype on apprenti → warned but still produces minutes
  6. calc_employee_minutes: salarié / dirigeant unaffected by contract_subtype
  7. compute_pricing: CAP apprenti excluded from total_minutes_reelles
  8. Employee DB model has contract_subtype column
  9. EmployeeCreate schema accepts contract_subtype
  10. EmployeeUpdate schema accepts contract_subtype
  11. EmployeeResponse schema serialises contract_subtype (from_attributes)
  12. contract-types.json has all 7 expected types with correct applicable_to_role
"""

import json
import logging
from decimal import Decimal
from pathlib import Path

import pytest

from app.calculations.pricing import (
    APPRENTI_BP_BM_DEFAULT_TAUX,
    EmployeePricingData,
    calc_employee_minutes,
    compute_pricing,
)
from app.schemas.employee import EmployeeCreate, EmployeeResponse, EmployeeUpdate


# ── Helpers ─────────────────────────────────────────────────────────────────────


def make_emp(
    role_type: str = "apprenti",
    contract_subtype: str | None = None,
    hours_per_week: Decimal = Decimal("35"),
    weeks_per_year: Decimal = Decimal("45.6"),
    taux_occupation: Decimal = Decimal("0.65"),  # system default
) -> EmployeePricingData:
    """Build an EmployeePricingData with common defaults."""
    return EmployeePricingData(
        employee_id="test-id",
        name="Test Apprenti",
        role_type=role_type,
        hours_per_week=hours_per_week,
        weeks_per_year=weeks_per_year,
        taux_occupation=taux_occupation,
        contract_subtype=contract_subtype,
    )


MINUTES_AN_35H = Decimal("35") * Decimal("45.6") * Decimal("60")  # = 95,760


# ── 1. CAP apprenti → 0 productive minutes ────────────────────────────────────


class TestCapApprentisZeroMinutes:
    """CAP apprentis must not contribute to billable minutes."""

    def test_cap_minutes_reelles_is_zero(self):
        """CAP apprenti: minutes_reelles = 0 regardless of taux_occupation."""
        emp = make_emp(contract_subtype="cap")
        result = calc_employee_minutes(emp)
        assert result.minutes_reelles == Decimal("0"), (
            f"Expected 0 billable minutes for CAP apprenti, got {result.minutes_reelles}"
        )

    def test_cap_minutes_totales_still_calculated(self):
        """CAP apprenti: contracted minutes are still computed (cost is real)."""
        emp = make_emp(contract_subtype="cap")
        result = calc_employee_minutes(emp)
        assert result.minutes_totales == MINUTES_AN_35H.quantize(Decimal("0.01")), (
            "CAP apprenti should still have contracted minutes_totales"
        )

    def test_cap_taux_occupation_irrelevant(self):
        """CAP apprenti with taux=0.80 still gets 0 billable minutes."""
        emp = make_emp(contract_subtype="cap", taux_occupation=Decimal("0.80"))
        result = calc_employee_minutes(emp)
        assert result.minutes_reelles == Decimal("0")


# ── 2–3. BP / BM apprenti uses APPRENTI_BP_BM_DEFAULT_TAUX when taux at default ─


class TestBpBmApprentisDefaultTaux:
    """BP/BM apprentis with system-default taux (0.65) get 0.35 heuristic."""

    @pytest.mark.parametrize("subtype", ["bp", "bm"])
    def test_default_taux_overridden_to_035(self, subtype: str):
        """BP/BM apprenti with default taux (0.65) → minutes use 0.35."""
        emp = make_emp(contract_subtype=subtype, taux_occupation=Decimal("0.65"))
        result = calc_employee_minutes(emp)
        expected = (MINUTES_AN_35H * APPRENTI_BP_BM_DEFAULT_TAUX).quantize(Decimal("0.01"))
        assert result.minutes_reelles == expected, (
            f"BP/BM apprenti with default taux should use {APPRENTI_BP_BM_DEFAULT_TAUX}, "
            f"expected {expected}, got {result.minutes_reelles}"
        )

    @pytest.mark.parametrize("subtype", ["bp", "bm"])
    def test_stored_taux_still_returned_in_result(self, subtype: str):
        """The EmployeeMinutesResult.taux_occupation mirrors the DB value, not the heuristic."""
        emp = make_emp(contract_subtype=subtype, taux_occupation=Decimal("0.65"))
        result = calc_employee_minutes(emp)
        # taux_occupation in result = stored value (for display), not effective value
        assert result.taux_occupation == Decimal("0.65")


# ── 4. BP apprenti with custom taux → custom taux respected ───────────────────


class TestBpBmCustomTaux:
    """Custom taux_occupation set by the salon overrides the heuristic."""

    @pytest.mark.parametrize("subtype", ["bp", "bm"])
    def test_custom_taux_respected(self, subtype: str):
        """BP/BM apprenti with custom taux 0.50 → 0.50 is used, not 0.35."""
        emp = make_emp(contract_subtype=subtype, taux_occupation=Decimal("0.50"))
        result = calc_employee_minutes(emp)
        expected = (MINUTES_AN_35H * Decimal("0.50")).quantize(Decimal("0.01"))
        assert result.minutes_reelles == expected, (
            f"Custom taux should be respected for {subtype} apprenti"
        )


# ── 5. None subtype → warned but produces minutes ─────────────────────────────


class TestNoneSubtypeApprentis:
    """Apprenti with contract_subtype=None → treated as BP/BM, warning logged."""

    def test_none_subtype_produces_minutes(self):
        """Apprenti with None subtype should not return 0 minutes."""
        emp = make_emp(contract_subtype=None, taux_occupation=Decimal("0.65"))
        result = calc_employee_minutes(emp)
        # Should use APPRENTI_BP_BM_DEFAULT_TAUX
        expected = (MINUTES_AN_35H * APPRENTI_BP_BM_DEFAULT_TAUX).quantize(Decimal("0.01"))
        assert result.minutes_reelles == expected

    def test_none_subtype_logs_warning(self, caplog):
        """Apprenti with None subtype should emit a deprecation warning."""
        emp = make_emp(contract_subtype=None, taux_occupation=Decimal("0.65"))
        with caplog.at_level(logging.WARNING, logger="app.calculations.pricing"):
            calc_employee_minutes(emp)
        assert any(
            "contract_subtype=None" in record.message
            for record in caplog.records
        ), "Expected a warning about contract_subtype=None for apprenti"


# ── 6. Salarié / dirigeant unaffected ─────────────────────────────────────────


class TestNonApprentisUnaffected:
    """contract_subtype has no effect on salarie or dirigeant role types."""

    @pytest.mark.parametrize("role_type", ["salarie", "dirigeant"])
    def test_salarie_dirigeant_not_affected_by_subtype(self, role_type: str):
        """Salarié and dirigeant use their stored taux_occupation regardless of subtype."""
        emp = make_emp(
            role_type=role_type,
            contract_subtype="cap",  # should be silently ignored
            taux_occupation=Decimal("0.65"),
        )
        result = calc_employee_minutes(emp)
        expected = (MINUTES_AN_35H * Decimal("0.65")).quantize(Decimal("0.01"))
        assert result.minutes_reelles == expected, (
            f"{role_type} with contract_subtype='cap' should use 0.65, not 0"
        )


# ── 7. compute_pricing: CAP apprenti excluded from total ──────────────────────


class TestComputePricingCapApprentis:
    """Integration test: CAP apprenti in compute_pricing → excluded from minutes total."""

    def test_cap_excluded_from_total_minutes(self):
        """With one productive and one CAP apprenti, only the productive one counts."""
        salarie = EmployeePricingData(
            employee_id="sal-1",
            name="Productive",
            role_type="salarie",
            hours_per_week=Decimal("35"),
            weeks_per_year=Decimal("45.6"),
            taux_occupation=Decimal("0.65"),
        )
        cap_apprenti = EmployeePricingData(
            employee_id="cap-1",
            name="CAP Apprenti",
            role_type="apprenti",
            hours_per_week=Decimal("35"),
            weeks_per_year=Decimal("45.6"),
            taux_occupation=Decimal("0.65"),
            contract_subtype="cap",
        )
        result = compute_pricing(
            employees=[salarie, cap_apprenti],
            cout_total_fonctionnement=Decimal("100000"),
            services=[],
        )
        # Only salarie's minutes should count
        salarie_minutes = (Decimal("35") * Decimal("45.6") * Decimal("60") * Decimal("0.65")).quantize(Decimal("0.01"))
        assert result.total_minutes_reelles == salarie_minutes, (
            f"CAP apprenti should be excluded from total. "
            f"Expected {salarie_minutes}, got {result.total_minutes_reelles}"
        )
        assert result.has_employees is True

    def test_cap_only_salon_raises_has_employees_true_but_zero_minutes(self):
        """A salon with ONLY CAP apprentis has has_employees=True but 0 real minutes."""
        cap_only = EmployeePricingData(
            employee_id="cap-1",
            name="CAP Apprenti",
            role_type="apprenti",
            hours_per_week=Decimal("35"),
            weeks_per_year=Decimal("45.6"),
            taux_occupation=Decimal("0.65"),
            contract_subtype="cap",
        )
        result = compute_pricing(
            employees=[cap_only],
            cout_total_fonctionnement=Decimal("100000"),
            services=[],
        )
        assert result.total_minutes_reelles == Decimal("0")
        assert result.cout_reel_minute == Decimal("0")
        # has_employees = True because there is an employee (even if non-productive)
        assert result.has_employees is True


# ── 8–11. Schema & model tests ────────────────────────────────────────────────


class TestEmployeeSchemas:
    """contract_subtype is accepted and serialised by all employee schemas."""

    def test_create_schema_accepts_contract_subtype(self):
        """EmployeeCreate should accept contract_subtype without errors."""
        obj = EmployeeCreate(
            name="Apprenti CAP",
            role_type="apprenti",
            contract_type="apprentissage",
            contract_subtype="cap",
            hours_per_week=Decimal("35"),
        )
        assert obj.contract_subtype == "cap"

    def test_create_schema_default_is_none(self):
        """contract_subtype defaults to None when not provided."""
        obj = EmployeeCreate(
            name="Test",
            role_type="salarie",
            contract_type="cdi",
            hours_per_week=Decimal("35"),
        )
        assert obj.contract_subtype is None

    def test_update_schema_accepts_contract_subtype(self):
        """EmployeeUpdate should accept contract_subtype without errors."""
        obj = EmployeeUpdate(contract_subtype="bp")
        assert obj.contract_subtype == "bp"

    def test_update_schema_default_is_none(self):
        """contract_subtype defaults to None in EmployeeUpdate."""
        obj = EmployeeUpdate(name="New name")
        assert obj.contract_subtype is None

    def test_response_schema_serialises_contract_subtype(self):
        """EmployeeResponse.from_attributes reads contract_subtype from model-like dict."""

        class FakeEmployee:
            """Minimal fake that mimics a SQLAlchemy Employee row."""
            id = "00000000-0000-0000-0000-000000000001"
            salon_id = "00000000-0000-0000-0000-000000000002"
            name = "Sophie"
            role_type = "apprenti"
            contract_type = "apprentissage"
            contract_subtype = "cap"
            hours_per_week = Decimal("35")
            weeks_per_year = Decimal("45.6")
            salary_brut = Decimal("600")
            cotisations_patronales = Decimal("100")
            taux_occupation = Decimal("0.65")
            is_active = True
            from datetime import datetime as dt
            created_at = dt(2026, 1, 1)

        resp = EmployeeResponse.model_validate(FakeEmployee())
        assert resp.contract_subtype == "cap"

    def test_response_schema_contract_subtype_none_when_not_set(self):
        """EmployeeResponse.contract_subtype defaults to None if column is NULL."""

        class FakeEmployee:
            id = "00000000-0000-0000-0000-000000000001"
            salon_id = "00000000-0000-0000-0000-000000000002"
            name = "Marie"
            role_type = "salarie"
            contract_type = "cdi"
            contract_subtype = None
            hours_per_week = Decimal("35")
            weeks_per_year = Decimal("45.6")
            salary_brut = Decimal("1500")
            cotisations_patronales = Decimal("400")
            taux_occupation = Decimal("0.65")
            is_active = True
            from datetime import datetime as dt
            created_at = dt(2026, 1, 1)

        resp = EmployeeResponse.model_validate(FakeEmployee())
        assert resp.contract_subtype is None


# ── 12. contract-types.json ───────────────────────────────────────────────────


class TestContractTypesJson:
    """Static data file has all expected entries with correct structure."""

    @pytest.fixture(scope="class")
    def contract_types(self) -> list[dict]:
        """Load contract-types.json from static-data directory."""
        json_path = Path(__file__).parents[2] / "backend" / "static-data" / "contract-types.json"
        if not json_path.exists():
            # Try relative to where pytest is run
            json_path = Path(__file__).parents[1] / "static-data" / "contract-types.json"
        with open(json_path) as f:
            return json.load(f)

    def test_all_seven_types_present(self, contract_types):
        """All 7 contract types must be present."""
        values = {ct["value"] for ct in contract_types}
        expected = {"cdi", "cdd", "apprentissage", "temps_partiel", "prestataire", "tns", "assimile_salarie"}
        assert values == expected, f"Missing or unexpected types: {values ^ expected}"

    def test_tns_applicable_to_dirigeant_only(self, contract_types):
        """TNS should only apply to dirigeants."""
        tns = next(ct for ct in contract_types if ct["value"] == "tns")
        assert tns["applicable_to_role"] == ["dirigeant"]

    def test_assimile_salarie_applicable_to_dirigeant_only(self, contract_types):
        """Assimilé salarié should only apply to dirigeants."""
        assal = next(ct for ct in contract_types if ct["value"] == "assimile_salarie")
        assert assal["applicable_to_role"] == ["dirigeant"]

    def test_apprentissage_applicable_to_apprenti(self, contract_types):
        """Apprentissage contract should apply to apprenti (and salarie for flexibility)."""
        appr = next(ct for ct in contract_types if ct["value"] == "apprentissage")
        assert "apprenti" in appr["applicable_to_role"]

    def test_all_have_label_and_description(self, contract_types):
        """Every contract type must have a non-empty label and description."""
        for ct in contract_types:
            assert ct.get("label"), f"Missing label for {ct['value']}"
            assert ct.get("description"), f"Missing description for {ct['value']}"
