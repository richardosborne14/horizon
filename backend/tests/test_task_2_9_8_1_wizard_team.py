"""
Pure unit tests for TASK-2.9.8.1 — Wizard Step 2 team import.

Tests the WizardTeamMember schema extensions (brut path, is_scenario, included)
without requiring a database connection. These run in ~0.01s locally.

For API integration tests (DB required), see test_task_2_9_8_1_wizard_team_api.py
which must be run inside Docker:
  docker compose exec -w /app backend python -m pytest tests/test_task_2_9_8_1_wizard_team_api.py -v
"""

import pytest
from decimal import Decimal

from app.schemas.typical_month import WizardTeamMember, TypicalMonthRequest


# ── Schema validation: brut path ──────────────────────────────────────────────

class TestWizardTeamMemberBrutPath:
    """WizardTeamMember accepts salary_brut + cotisations_patronales directly."""

    def test_brut_path_valid_real_employee(self) -> None:
        """Real employee imported from Parametrage: brut + cotisations provided."""
        # Rick Test from seed: brut=1680, patronales=529.60, cout=2209.60
        member = WizardTeamMember(
            name="Rick Test",
            role_type="salarie",
            salary_brut=1680.0,
            cotisations_patronales=529.60,
            employee_id="some-uuid-string",
            is_scenario=False,
            included=True,
        )
        assert member.salary_brut == 1680.0
        assert member.cotisations_patronales == 529.60
        assert member.net_salary is None      # not needed on brut path
        assert member.is_scenario is False
        assert member.included is True

    def test_brut_path_cout_annuel_math(self) -> None:
        """Verify the canonical Rick Test numbers: cout_mensuel = 2209.60."""
        brut = Decimal("1680.00")
        cotisations = Decimal("529.60")
        cout_mensuel = brut + cotisations
        cout_annuel = cout_mensuel * 12
        assert cout_mensuel == Decimal("2209.60")
        assert cout_annuel == Decimal("26515.20")

    def test_brut_path_zero_cotisations(self) -> None:
        """cotisations_patronales=0 is valid (some special cases)."""
        member = WizardTeamMember(
            name="Dirigeant TNS",
            role_type="dirigeant",
            salary_brut=2000.0,
            cotisations_patronales=0.0,
            included=True,
        )
        assert member.salary_brut == 2000.0
        assert member.cotisations_patronales == 0.0

    def test_scenario_employee_valid(self) -> None:
        """Fictional scenario employee: is_scenario=True, no employee_id."""
        member = WizardTeamMember(
            name="Julie (scénario)",
            role_type="salarie",
            salary_brut=1500.0,
            cotisations_patronales=480.0,   # 1500 × 32% estimate
            is_scenario=True,
            included=True,
        )
        assert member.is_scenario is True
        assert member.employee_id is None

    def test_scenario_cotisations_estimate(self) -> None:
        """UI default: cotisations = salary_brut × 0.32 for scenario employees."""
        brut = 1500.0
        cotisations = round(brut * 0.32, 2)
        cout_mensuel = brut + cotisations
        assert cotisations == 480.0
        assert cout_mensuel == 1980.0

    def test_included_false_valid(self) -> None:
        """included=False is valid — member excluded from calculation."""
        member = WizardTeamMember(
            name="Rick Test",
            role_type="salarie",
            salary_brut=1680.0,
            cotisations_patronales=529.60,
            employee_id="some-uuid",
            included=False,
        )
        assert member.included is False

    def test_included_default_true(self) -> None:
        """included defaults to True if not specified."""
        member = WizardTeamMember(
            name="Test",
            role_type="salarie",
            salary_brut=1500.0,
        )
        assert member.included is True


# ── Schema validation: legacy net path ───────────────────────────────────────

class TestWizardTeamMemberNetPath:
    """Legacy net_salary path still works — backwards compat."""

    def test_legacy_net_path_valid(self) -> None:
        """net_salary-only path: backwards compatible with existing wizard submissions."""
        member = WizardTeamMember(
            name="Marie",
            role_type="salarie",
            contract_type="cdi",
            net_salary=1400.0,
            hours_per_week=35,
        )
        assert member.net_salary == 1400.0
        assert member.salary_brut is None

    def test_legacy_dirigeant_tns(self) -> None:
        """TNS dirigeant via legacy net path."""
        member = WizardTeamMember(
            name="Patron",
            role_type="dirigeant",
            contract_type="tns",
            net_salary=2000.0,
        )
        assert member.net_salary == 2000.0
        assert member.is_scenario is False

    def test_legacy_prestataire(self) -> None:
        """Prestataire via legacy net path."""
        member = WizardTeamMember(
            name="Freelance",
            role_type="prestataire",
            net_salary=800.0,
        )
        assert member.net_salary == 800.0


# ── Schema validation: error cases ────────────────────────────────────────────

class TestWizardTeamMemberValidation:
    """Schema rejects invalid combinations."""

    def test_no_salary_data_raises(self) -> None:
        """Neither net_salary nor salary_brut → validation error."""
        with pytest.raises(ValueError, match="salary"):
            WizardTeamMember(name="Nobody", role_type="salarie")

    def test_both_paths_valid(self) -> None:
        """Providing both salary_brut and net_salary is valid (brut path takes precedence in service)."""
        member = WizardTeamMember(
            name="Test",
            role_type="salarie",
            salary_brut=1680.0,
            cotisations_patronales=529.60,
            net_salary=1300.0,
        )
        assert member.salary_brut == 1680.0

    def test_salary_brut_zero_allowed(self) -> None:
        """salary_brut=0 is allowed (some scenario placeholders may start at 0)."""
        member = WizardTeamMember(
            name="TBD",
            role_type="salarie",
            salary_brut=0.0,
        )
        assert member.salary_brut == 0.0

    def test_net_salary_zero_not_allowed_alone(self) -> None:
        """net_salary=0 with no salary_brut → fails the > 0 check."""
        with pytest.raises(ValueError, match="salary"):
            WizardTeamMember(name="Zero", role_type="salarie", net_salary=0.0)


# ── TypicalMonthRequest: full payload validation ──────────────────────────────

class TestTypicalMonthRequest:
    """Full request payload with new fields."""

    def test_request_with_real_employee_brut_path(self) -> None:
        """Full wizard payload using the brut path for a real imported employee."""
        req = TypicalMonthRequest(
            ca_ttc=8000.0,
            team=[
                WizardTeamMember(
                    name="Rick Test",
                    role_type="salarie",
                    salary_brut=1680.0,
                    cotisations_patronales=529.60,
                    employee_id="abc123",
                    is_scenario=False,
                    included=True,
                )
            ],
            expenses=[],
        )
        assert len(req.team) == 1
        assert req.team[0].salary_brut == 1680.0
        assert req.team[0].is_scenario is False
        assert req.team[0].included is True

    def test_request_with_scenario_and_real(self) -> None:
        """Mixed payload: one real + one scenario employee."""
        req = TypicalMonthRequest(
            ca_ttc=8000.0,
            team=[
                WizardTeamMember(
                    name="Rick Test",
                    role_type="salarie",
                    salary_brut=1680.0,
                    cotisations_patronales=529.60,
                    employee_id="abc123",
                    is_scenario=False,
                    included=True,
                ),
                WizardTeamMember(
                    name="Julie (scénario)",
                    role_type="salarie",
                    salary_brut=1500.0,
                    cotisations_patronales=480.0,
                    is_scenario=True,
                    included=True,
                ),
            ],
            expenses=[],
        )
        assert len(req.team) == 2
        real = req.team[0]
        scenario = req.team[1]
        assert real.is_scenario is False
        assert scenario.is_scenario is True
        assert scenario.employee_id is None

    def test_request_with_excluded_member(self) -> None:
        """included=False member is valid in the payload."""
        req = TypicalMonthRequest(
            ca_ttc=8000.0,
            team=[
                WizardTeamMember(
                    name="Rick Test",
                    role_type="salarie",
                    salary_brut=1680.0,
                    cotisations_patronales=529.60,
                    employee_id="abc123",
                    included=False,
                ),
            ],
            expenses=[],
        )
        assert req.team[0].included is False

    def test_empty_team_valid(self) -> None:
        """Solo salon: no team members — still valid."""
        req = TypicalMonthRequest(ca_ttc=5000.0, team=[], expenses=[])
        assert req.team == []
