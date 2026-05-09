"""
Tests for Task 2.7 — Full monthly point mort calculation.

Covers:
  - compute_full_point_mort() unit tests (pure function, no DB)
  - GET /full endpoint integration test
  - remboursement_emprunt persistence on create + update
  - MonthlyFullPointMort schema validation

All monetary assertions use Decimal to avoid float imprecision.
Known reference values from CALCULATION_FORMULAS.md Section 2.
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

from app.schemas.monthly_report import MonthlyFullPointMort
from app.services.monthly_report import compute_full_point_mort


# ── Helpers to build lightweight mock ORM objects ─────────────────────────────


def _mock_expense(amount_ttc: str, amount_ht: str) -> MagicMock:
    """
    Build a mock Expense ORM object.

    Args:
        amount_ttc: TTC amount as string.
        amount_ht: HT amount as string.

    Returns:
        MagicMock with amount_ttc and amount_ht attributes.
    """
    e = MagicMock()
    e.amount_ttc = Decimal(amount_ttc)
    e.amount_ht = Decimal(amount_ht)
    return e


def _mock_salary(total_charge: str, salaire_brut: str, role_type: str = "salarie") -> MagicMock:
    """
    Build a mock MonthlySalary ORM object.

    Args:
        total_charge: Total charge string (brut + cotisations).
        salaire_brut: Gross/net salary string.
        role_type: 'salarie', 'apprenti', or 'dirigeant'.

    Returns:
        MagicMock with total_charge, salaire_brut, and employee.role_type set.
    """
    s = MagicMock()
    s.total_charge = Decimal(total_charge)
    s.salaire_brut = Decimal(salaire_brut)
    s.employee = MagicMock()
    s.employee.role_type = role_type
    return s


def _mock_report(
    ca: str = "0",
    subventions: str = "0",
    remboursement_emprunt: str = "0",
    expenses: list | None = None,
) -> MagicMock:
    """
    Build a mock MonthlyReport ORM object.

    Args:
        ca: CA réalisé TTC as string.
        subventions: Subventions as string.
        remboursement_emprunt: Monthly loan repayment as string.
        expenses: Optional list of mock Expense objects.

    Returns:
        MagicMock with all necessary MonthlyReport attributes.
    """
    r = MagicMock()
    r.ca_realise_ttc = Decimal(ca)
    r.subventions = Decimal(subventions)
    r.remboursement_emprunt = Decimal(remboursement_emprunt)
    r.expenses = expenses or []
    return r


# ── Unit tests: compute_full_point_mort ───────────────────────────────────────


class TestComputeFullPointMort:
    """Unit tests for compute_full_point_mort() — pure function, no DB needed."""

    def test_empty_report_zero_cash_flow(self):
        """
        Empty report (no expenses, no salaries, no loan, zero CA) should
        produce all-zero values with cash_flow = 0.
        """
        report = _mock_report(ca="0", remboursement_emprunt="0")
        result = compute_full_point_mort(report, [])

        assert result.total_A == Decimal("0")
        assert result.total_B == Decimal("0")
        assert result.total_AB == Decimal("0")
        assert result.total_decaissement == Decimal("0")
        assert result.point_mort_salon_ttc == Decimal("0")
        assert result.cash_flow == Decimal("0")

    def test_section_a_sums_all_salary_total_charges(self):
        """
        total_A must be the sum of ALL salary rows' total_charge,
        regardless of role_type.
        """
        salaries = [
            _mock_salary("3500.00", "2500.00", "salarie"),
            _mock_salary("3000.00", "2000.00", "salarie"),
        ]
        report = _mock_report(ca="20000")
        result = compute_full_point_mort(report, salaries)

        assert result.total_A == Decimal("6500.00")

    def test_section_b_sums_expense_ht(self):
        """total_B = sum of all expense amount_ht (HT basis — TASK-2.15.1).

        WHY HT: the business retains only CA HT; it pays expenses HT (TVA on
        purchases is reclaimed from the state). Using TTC overstated point mort
        by TVA_nette per month vs. the wizard preview. Fixed in TASK-2.15.1.
        """
        expenses = [
            _mock_expense("1200.00", "1000.00"),  # HT=1000
            _mock_expense("600.00", "500.00"),    # HT=500
        ]
        report = _mock_report(ca="20000", expenses=expenses)
        result = compute_full_point_mort(report, [])

        assert result.total_B == Decimal("1500.00")  # 1000 + 500 (HT, was 1800 TTC)

    def test_tva_payee_achats_is_ttc_minus_ht(self):
        """
        tva_payee_achats = total_B - SUM(amount_ht)
        = sum of TVA paid on purchases (informational).
        """
        expenses = [
            _mock_expense("1200.00", "1000.00"),  # TVA = 200
            _mock_expense("600.00", "500.00"),    # TVA = 100
        ]
        report = _mock_report(ca="20000", expenses=expenses)
        result = compute_full_point_mort(report, [])

        assert result.tva_payee_achats == Decimal("300.00")

    def test_remboursement_emprunt_added_to_decaissement(self):
        """
        Loan repayment is included in total_decaissement.
        total_decaissement = total_AB + remboursement_emprunt.
        """
        expenses = [_mock_expense("1200.00", "1000.00")]
        report = _mock_report(
            ca="20000",
            expenses=expenses,
            remboursement_emprunt="500.00",
        )
        result = compute_full_point_mort(report, [])

        assert result.remboursement_emprunt == Decimal("500.00")
        assert result.total_decaissement == Decimal("1500.00")  # 1000 HT + 500 loan (was 1200 TTC + 500)

    def test_point_mort_salon_equals_total_decaissement(self):
        """point_mort_salon_ttc must equal total_decaissement."""
        salaries = [_mock_salary("4000.00", "3000.00", "salarie")]
        expenses = [_mock_expense("1200.00", "1000.00")]
        report = _mock_report(
            ca="20000",
            expenses=expenses,
            remboursement_emprunt="300.00",
        )
        result = compute_full_point_mort(report, salaries)

        # total_A=4000, total_B=1000 (HT, was 1200 TTC), remboursement=300
        # total_decaissement = 4000 + 1000 + 300 = 5300 (TASK-2.15.1 fix)
        assert result.total_decaissement == Decimal("5300.00")
        assert result.point_mort_salon_ttc == result.total_decaissement

    def test_dirigeant_info_extracted(self):
        """
        salaire_net_dirigeant and dirigeant_majore are extracted from the
        dirigeant salary row (salaire_brut = net for TNS).
        dirigeant's cost is already in total_A — NOT added again.
        """
        salaries = [
            _mock_salary("4350.00", "3000.00", "dirigeant"),  # 3000 × 1.45 = 4350
            _mock_salary("3500.00", "2500.00", "salarie"),
        ]
        expenses = [_mock_expense("600.00", "500.00")]
        report = _mock_report(ca="20000", expenses=expenses)
        result = compute_full_point_mort(report, salaries)

        assert result.salaire_net_dirigeant == Decimal("3000.00")
        assert result.dirigeant_majore == Decimal("3000.00") * Decimal("1.45")

        # Dirigeant already in total_A: point_mort_dirigeant_inclus = point_mort_salon
        assert result.point_mort_dirigeant_inclus == result.point_mort_salon_ttc

    def test_no_dirigeant_returns_zero_net(self):
        """If no dirigeant salary row exists, salaire_net_dirigeant = 0."""
        salaries = [_mock_salary("3500.00", "2500.00", "salarie")]
        report = _mock_report(ca="20000")
        result = compute_full_point_mort(report, salaries)

        assert result.salaire_net_dirigeant == Decimal("0")
        assert result.dirigeant_majore == Decimal("0")

    def test_cash_flow_positive_profitable_month(self):
        """
        Cash flow = CA − point mort.
        Profitable month: CA > point mort.
        """
        # CA TTC = 20000, ca_ht = 16666.67 (÷1.2)
        # total_A = 8000, total_B = 3000 (HT, was 3600 TTC), remboursement = 0
        # point_mort = 11000, cash_flow = 16666.67 − 11000 = 5666.67 (TASK-2.15.1 fix)
        salaries = [_mock_salary("8000.00", "5000.00", "salarie")]
        expenses = [_mock_expense("3600.00", "3000.00")]
        report = _mock_report(ca="20000", expenses=expenses)
        result = compute_full_point_mort(report, salaries)

        assert result.point_mort_salon_ttc == Decimal("11000.00")
        assert result.cash_flow == Decimal("5666.67")

    def test_cash_flow_negative_loss_month(self):
        """
        Cash flow is negative when CA < point mort.
        Deficit month: CA 10000, costs 15000.
        """
        salaries = [_mock_salary("10000.00", "7000.00", "salarie")]
        expenses = [_mock_expense("5000.00", "4166.67")]
        report = _mock_report(ca="10000", expenses=expenses)
        result = compute_full_point_mort(report, salaries)

        assert result.cash_flow < Decimal("0")
        assert result.point_mort_salon_ttc > Decimal("10000.00")

    def test_tva_encaissee_formula(self):
        """
        tva_encaissee = CA × (1 − 1/1.2) = CA / 6
        For CA = 12000: tva_encaissee = 2000.00
        """
        report = _mock_report(ca="12000")
        result = compute_full_point_mort(report, [])

        # 12000 - 12000/1.2 = 12000 - 10000 = 2000
        assert result.tva_encaissee == Decimal("2000")

    def test_tva_a_payer_is_net(self):
        """
        tva_a_payer = tva_encaissee - tva_payee_achats
        Net TVA to remit to government.
        CA = 12000 → encaissee = 2000
        Expenses TTC = 1200, HT = 1000 → payee = 200
        tva_a_payer = 2000 - 200 = 1800
        """
        expenses = [_mock_expense("1200.00", "1000.00")]
        report = _mock_report(ca="12000", expenses=expenses)
        result = compute_full_point_mort(report, [])

        assert result.tva_encaissee == Decimal("2000")
        assert result.tva_payee_achats == Decimal("200.00")
        assert result.tva_a_payer == Decimal("1800")

    def test_reference_scenario_full_calculation(self):
        """
        Reference scenario with known values to verify against CALCULATION_FORMULAS.md:

        Inputs:
          - 2 salaried employees: total_charge = 3500 + 4000 = 7500
          - Dirigeant TNS: salaire_brut = 2500 (net), total_charge ≈ 3625 (×1.45)
          - Expenses TTC = 2400 (HT = 2000)
          - Remboursement emprunt = 600
          - CA = 22000

        Expected:
          - total_A = 7500 + 3625 = 11125
          - total_B = 2000 (HT, was 2400 TTC — TASK-2.15.1)
          - tva_payee_achats = 400 (2400 TTC − 2000 HT, informational only)
          - total_AB = 13125 (11125 + 2000)
          - total_decaissement = 13125 + 600 = 13725
          - point_mort_salon_ttc = 13725
          - salaire_net_dirigeant = 2500
          - dirigeant_majore = 2500 × 1.45 = 3625
          - point_mort_dirigeant_inclus = 13725 (same as salon)
          - tva_encaissee = 22000 - 22000/1.2 = 22000 - 18333.333... ≈ 3666.67
          - ca_ht = 18333.33, cash_flow = 18333.33 - 13725 = 4608.33
        """
        salaries = [
            _mock_salary("3500.00", "2500.00", "salarie"),
            _mock_salary("4000.00", "3000.00", "salarie"),
            _mock_salary("3625.00", "2500.00", "dirigeant"),  # 2500 × 1.45 = 3625
        ]
        expenses = [_mock_expense("2400.00", "2000.00")]
        report = _mock_report(
            ca="22000",
            expenses=expenses,
            remboursement_emprunt="600.00",
        )

        result = compute_full_point_mort(report, salaries)

        assert result.total_A == Decimal("11125.00")
        assert result.total_B == Decimal("2000.00")        # HT (was 2400 TTC)
        assert result.tva_payee_achats == Decimal("400.00") # 2400-2000, informational
        assert result.total_AB == Decimal("13125.00")       # 11125 + 2000 HT
        assert result.remboursement_emprunt == Decimal("600.00")
        assert result.total_decaissement == Decimal("13725.00")  # 13125 + 600
        assert result.point_mort_salon_ttc == Decimal("13725.00")
        assert result.salaire_net_dirigeant == Decimal("2500.00")
        assert result.dirigeant_majore == Decimal("3625.00")
        assert result.point_mort_dirigeant_inclus == Decimal("13725.00")
        assert result.cash_flow == Decimal("4608.33")       # 18333.33 - 13725


# ── MonthlyFullPointMort schema validation ────────────────────────────────────


class TestMonthlyFullPointMortSchema:
    """Verify MonthlyFullPointMort Pydantic schema round-trips correctly."""

    def test_schema_round_trip(self):
        """All Decimal fields must serialise and deserialise without loss."""
        data = {
            "total_A": Decimal("7500.00"),
            "total_B": Decimal("2400.00"),
            "total_AB": Decimal("9900.00"),
            "tva_payee_achats": Decimal("400.00"),
            "remboursement_emprunt": Decimal("600.00"),
            "total_decaissement": Decimal("10500.00"),
            "point_mort_salon_ttc": Decimal("10500.00"),
            "salaire_net_dirigeant": Decimal("2500.00"),
            "dirigeant_majore": Decimal("3625.00"),
            "point_mort_dirigeant_inclus": Decimal("10500.00"),
            "tva_encaissee": Decimal("3666.67"),
            "tva_a_payer": Decimal("3266.67"),
            "cash_flow": Decimal("7875.00"),
        }
        schema = MonthlyFullPointMort(**data)
        assert schema.total_A == Decimal("7500.00")
        assert schema.cash_flow == Decimal("7875.00")
        dumped = schema.model_dump()
        assert dumped["cash_flow"] == Decimal("7875.00")


# ── Integration tests — API endpoint ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_full_endpoint_returns_all_sections(
    client,
    auth_headers,
    salon,
    employee_salarie,
    monthly_report,
):
    """
    GET /full endpoint must return report, salary_totals, salary_rows,
    and point_mort keys in the response.
    """
    response = client.get(
        f"/api/salons/{salon.id}/monthly-reports/{monthly_report.id}/full",
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()

    assert "report" in body
    assert "salary_totals" in body
    assert "salary_rows" in body
    assert "point_mort" in body


@pytest.mark.asyncio
async def test_full_endpoint_point_mort_has_required_keys(
    client,
    auth_headers,
    salon,
    monthly_report,
):
    """point_mort section must contain all required calculation fields."""
    response = client.get(
        f"/api/salons/{salon.id}/monthly-reports/{monthly_report.id}/full",
        headers=auth_headers,
    )
    assert response.status_code == 200
    pm = response.json()["point_mort"]

    required_keys = [
        "total_A", "total_B", "total_AB", "tva_payee_achats",
        "remboursement_emprunt", "total_decaissement", "point_mort_salon_ttc",
        "salaire_net_dirigeant", "dirigeant_majore", "point_mort_dirigeant_inclus",
        "tva_encaissee", "tva_a_payer", "cash_flow",
    ]
    for key in required_keys:
        assert key in pm, f"Missing key in point_mort: {key}"


@pytest.mark.asyncio
async def test_full_endpoint_404_for_unknown_report(
    client,
    auth_headers,
    salon,
):
    """GET /full must return 404 for a non-existent report."""
    fake_id = uuid.uuid4()
    response = client.get(
        f"/api/salons/{salon.id}/monthly-reports/{fake_id}/full",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_remboursement_emprunt_persisted_on_create(
    client,
    auth_headers,
    salon,
):
    """Creating a report with remboursement_emprunt must persist the value."""
    response = client.post(
        f"/api/salons/{salon.id}/monthly-reports",
        json={
            "year": 2026,
            "month": 8,
            "ca_realise_ttc": "15000.00",
            "remboursement_emprunt": "450.00",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["remboursement_emprunt"] == "450.00"


@pytest.mark.asyncio
async def test_remboursement_emprunt_updatable(
    client,
    auth_headers,
    salon,
    monthly_report,
):
    """PUT on a report must update remboursement_emprunt."""
    response = client.put(
        f"/api/salons/{salon.id}/monthly-reports/{monthly_report.id}",
        json={"remboursement_emprunt": "750.00"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["remboursement_emprunt"] == "750.00"


@pytest.mark.asyncio
async def test_full_endpoint_cash_flow_matches_manual_calc(
    client,
    auth_headers,
    salon,
    monthly_report_with_ca,
):
    """
    For a report with CA=10000 and no expenses/salaries/loan,
    cash_flow should equal CA (nothing to pay).
    point_mort should be 0, cash_flow should be 10000.
    """
    response = client.get(
        f"/api/salons/{salon.id}/monthly-reports/{monthly_report_with_ca.id}/full",
        headers=auth_headers,
    )
    assert response.status_code == 200
    pm = response.json()["point_mort"]

    assert pm["total_A"] == "0"
    assert pm["total_B"] == "0"
    assert pm["point_mort_salon_ttc"] == "0"
    assert pm["cash_flow"] == "10000.00"
