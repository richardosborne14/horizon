"""
Tests for Task 2.6.1 — AE TVA Audit.

Verifies that auto-entrepreneurs (franchise en base de TVA, business_type='auto_micro')
never see computed TVA figures in:
  1. compute_simulation() — the quick profitability simulator
  2. compute_full_point_mort() — the monthly copilot point mort grid

All tests are pure unit tests — no database, no HTTP client.

Formulae verified against dev-docs/resources/05-calculation-reference.md and TASK-2.15.

WHY these tests matter:
  AE users on franchise en base de TVA are legally exempt from charging TVA on
  their revenue and cannot reclaim TVA on purchases. Showing a non-zero TVA figure
  would mislead them into thinking they owe money to the tax authorities when they
  don't. This is a correctness + legal compliance issue, not a cosmetic one.
"""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.calculations.simulation import compute_simulation
from app.services.monthly_report import compute_full_point_mort


# ── compute_simulation() — AE path ────────────────────────────────────────────


class TestSimulationAE:
    """AE (auto_micro) business type — TVA must always be zero."""

    def test_ae_tva_estimee_is_zero(self):
        """AE: TVA collected on revenue must be 0, not CA × (1 - 1/1.2)."""
        result = compute_simulation(
            ca_mensuel_ttc=Decimal("5000"),
            total_salaires_charges=Decimal("2000"),
            total_depenses_ttc=Decimal("800"),
            business_type="auto_micro",
        )
        assert result.tva_estimee == Decimal("0.00"), (
            f"Expected 0.00 but got {result.tva_estimee} — "
            "AE users do not charge TVA on their revenue"
        )

    def test_ae_tva_payee_achats_is_zero(self):
        """AE: TVA on purchases must be 0 — AE cannot reclaim TVA."""
        result = compute_simulation(
            ca_mensuel_ttc=Decimal("5000"),
            total_salaires_charges=Decimal("2000"),
            total_depenses_ttc=Decimal("800"),
            business_type="auto_micro",
        )
        assert result.tva_payee_achats == Decimal("0.00"), (
            f"Expected 0.00 but got {result.tva_payee_achats}"
        )

    def test_ae_tva_a_payer_is_zero(self):
        """AE: Net TVA due must be 0."""
        result = compute_simulation(
            ca_mensuel_ttc=Decimal("5000"),
            total_salaires_charges=Decimal("2000"),
            total_depenses_ttc=Decimal("800"),
            business_type="auto_micro",
        )
        assert result.tva_a_payer == Decimal("0.00"), (
            f"Expected 0.00 but got {result.tva_a_payer}"
        )

    def test_ae_cash_flow_still_calculated_correctly(self):
        """AE: Cash flow calculation must still work (TVA zeroing does not affect P&L)."""
        result = compute_simulation(
            ca_mensuel_ttc=Decimal("5000"),
            total_salaires_charges=Decimal("2000"),
            total_depenses_ttc=Decimal("800"),
            business_type="auto_micro",
        )
        # point_mort = salaires + dépenses = 2800
        # cash_flow = 5000 - 2800 = 2200
        assert result.point_mort_salon == Decimal("2800.00")
        assert result.cash_flow == Decimal("2200.00")
        assert result.is_profitable is True

    def test_ae_zero_ca_does_not_crash(self):
        """AE with zero CA — must not raise (div-by-zero guard)."""
        result = compute_simulation(
            ca_mensuel_ttc=Decimal("0"),
            total_salaires_charges=Decimal("0"),
            total_depenses_ttc=Decimal("0"),
            business_type="auto_micro",
        )
        assert result.tva_estimee == Decimal("0.00")
        assert result.tva_a_payer == Decimal("0.00")


# ── compute_simulation() — non-AE path ────────────────────────────────────────


class TestSimulationNonAE:
    """Non-AE (SARL, EI, EURL, SAS) — TVA must be calculated normally."""

    def test_sarl_tva_estimee_calculated(self):
        """SARL: TVA collected = CA × (1 - 1/1.2) ≈ 16.67% of CA TTC."""
        result = compute_simulation(
            ca_mensuel_ttc=Decimal("6000"),
            total_salaires_charges=Decimal("2000"),
            total_depenses_ttc=Decimal("1200"),
            business_type="sarl",
        )
        # tva_estimee = 6000 - (6000 / 1.2) = 6000 - 5000 = 1000
        assert result.tva_estimee == Decimal("1000.00")

    def test_sarl_tva_payee_achats_calculated(self):
        """SARL: TVA on purchases must be computed from total_depenses_ttc."""
        result = compute_simulation(
            ca_mensuel_ttc=Decimal("6000"),
            total_salaires_charges=Decimal("2000"),
            total_depenses_ttc=Decimal("1200"),
            business_type="sarl",
        )
        # tva_payee_achats = 1200 - (1200 / 1.2) = 1200 - 1000 = 200
        assert result.tva_payee_achats == Decimal("200.00")

    def test_sarl_tva_a_payer_calculated(self):
        """SARL: Net TVA = tva_estimee - tva_payee_achats."""
        result = compute_simulation(
            ca_mensuel_ttc=Decimal("6000"),
            total_salaires_charges=Decimal("2000"),
            total_depenses_ttc=Decimal("1200"),
            business_type="sarl",
        )
        # 1000 - 200 = 800
        assert result.tva_a_payer == Decimal("800.00")

    def test_empty_business_type_defaults_to_non_ae(self):
        """Empty business_type should behave like non-AE (safe default)."""
        result = compute_simulation(
            ca_mensuel_ttc=Decimal("5000"),
            total_salaires_charges=Decimal("2000"),
            total_depenses_ttc=Decimal("800"),
            business_type="",
        )
        # Should calculate TVA, not return zero
        assert result.tva_estimee > Decimal("0")


# ── compute_full_point_mort() — AE path ───────────────────────────────────────


def _make_report(
    ca: str = "5000",
    expenses_ttc: list[str] | None = None,
    remboursement: str = "0",
    is_ae: bool = False,
):
    """Create a minimal mock MonthlyReport for unit testing.

    Args:
        ca: CA TTC as string.
        expenses_ttc: List of expense TTC strings.
        remboursement: Loan repayment TTC as string.
        is_ae: When True, sets amount_ht = amount_ttc (AE: no TVA on purchases).
               When False, sets amount_ht = amount_ttc / 1.2 (20% TVA on purchases).
    """
    if expenses_ttc is None:
        expenses_ttc = ["600", "400"]

    expense_ns = [
        SimpleNamespace(
            amount_ttc=Decimal(e),
            # AE: no TVA on purchases (franchise en base de TVA) → HT = TTC.
            # Non-AE: standard 20% TVA → HT = TTC / 1.2.
            amount_ht=Decimal(e) if is_ae else Decimal(e) / Decimal("1.2"),
        )
        for e in expenses_ttc
    ]
    return SimpleNamespace(
        ca_realise_ttc=Decimal(ca),
        subventions=Decimal("0"),
        remboursement_emprunt=Decimal(remboursement),
        expenses=expense_ns,
    )


def _make_salary_rows(amounts: list[tuple[str, str]] | None = None):
    """Create minimal mock MonthlySalary rows with employee.role_type.

    Args:
        amounts: list of (total_charge, role_type) tuples.
    """
    if amounts is None:
        amounts = [("1800", "salarie")]
    return [
        SimpleNamespace(
            total_charge=Decimal(amt),
            salaire_brut=Decimal(amt),
            employee=SimpleNamespace(role_type=role),
        )
        for amt, role in amounts
    ]


class TestComputeFullPointMortAE:
    """compute_full_point_mort() — AE users must see zero TVA in the grid."""

    def test_ae_tva_payee_achats_zeroed(self):
        """AE: tva_payee_achats must be 0 in the returned MonthlyFullPointMort."""
        report = _make_report(expenses_ttc=["600", "400"])
        salaries = _make_salary_rows([("1800", "salarie")])
        pm = compute_full_point_mort(report, salaries, is_ae=True)
        assert pm.tva_payee_achats == Decimal("0"), (
            f"Expected 0 but got {pm.tva_payee_achats}"
        )

    def test_ae_tva_encaissee_zeroed(self):
        """AE: tva_encaissee must be 0."""
        report = _make_report()
        salaries = _make_salary_rows()
        pm = compute_full_point_mort(report, salaries, is_ae=True)
        assert pm.tva_encaissee == Decimal("0")

    def test_ae_tva_a_payer_zeroed(self):
        """AE: tva_a_payer must be 0."""
        report = _make_report()
        salaries = _make_salary_rows()
        pm = compute_full_point_mort(report, salaries, is_ae=True)
        assert pm.tva_a_payer == Decimal("0")

    def test_ae_cash_flow_unaffected_by_tva_zeroing(self):
        """AE: Cash flow = CA - point mort must be correct regardless of TVA zeroing.

        Note (Task 3.X + Bug 7 fix 2026-04-23): AE URSSAF (21.2 % BIC services
        default) is now part of the point mort, and total_AB is the literal
        salaries + expenses. point mort = 1800 + 1000 + 1060 URSSAF = 3860.

        WHY is_ae=True: AE expenses have no TVA (franchise en base de TVA), so
        amount_ht = amount_ttc. The fixture must reflect this; otherwise HT < TTC
        would give wrong total_B.
        """
        report = _make_report(ca="5000", expenses_ttc=["600", "400"], is_ae=True)
        salaries = _make_salary_rows([("1800", "salarie")])
        pm = compute_full_point_mort(report, salaries, is_ae=True)
        assert pm.total_A == Decimal("1800")
        assert pm.total_B == Decimal("1000")
        assert pm.total_AB == Decimal("2800")  # literal A + B
        assert pm.urssaf_cotisations == Decimal("1060.00")  # 5000 × 21.2 %
        assert pm.total_decaissement == Decimal("3860.00")  # A + B + URSSAF + 0 loan
        assert pm.cash_flow == Decimal("1140.00")  # 5000 − 3860

    def test_ae_default_is_false(self):
        """Non-AE (default is_ae=False): TVA must be non-zero for a SARL with CA."""
        report = _make_report(ca="5000", expenses_ttc=["600", "400"])
        salaries = _make_salary_rows()
        pm = compute_full_point_mort(report, salaries)  # is_ae defaults to False
        # tva_encaissee = 5000 - (5000 / 1.2) = 5000 - 4166.67 ≈ 833.33
        assert pm.tva_encaissee > Decimal("0"), (
            f"Expected non-zero tva_encaissee but got {pm.tva_encaissee}"
        )

    def test_non_ae_tva_encaissee_formula(self):
        """Non-AE: tva_encaissee = CA - (CA / 1.2) per 05-calculation-reference.md."""
        report = _make_report(ca="6000", expenses_ttc=["1200"])
        salaries = _make_salary_rows([("2000", "salarie")])
        pm = compute_full_point_mort(report, salaries, is_ae=False)
        # 6000 - (6000 / 1.2) = 6000 - 5000 = 1000
        assert pm.tva_encaissee == Decimal("1000")

    def test_with_remboursement_ae(self):
        """AE: Loan repayment still adds to point mort even with TVA zeroed.

        Note (Task 3.X): AE URSSAF 21.2 % is also in total_decaissement:
        total_decaissement = total_A 1800 + total_B 600 + URSSAF 1060 + loan 300 = 3760.
        """
        report = _make_report(ca="5000", expenses_ttc=["600"], remboursement="300", is_ae=True)
        salaries = _make_salary_rows([("1800", "salarie")])
        pm = compute_full_point_mort(report, salaries, is_ae=True)
        assert pm.remboursement_emprunt == Decimal("300")
        assert pm.urssaf_cotisations == Decimal("1060.00")
        assert pm.total_decaissement == Decimal("3760.00")
        assert pm.tva_a_payer == Decimal("0")  # still zeroed


# ── Edge cases ─────────────────────────────────────────────────────────────────


class TestSimulationEdgeCases:
    """Edge cases shared by AE and non-AE paths."""

    def test_negative_cash_flow_ae(self):
        """AE with losses: cash_flow must be negative, TVA must be zero."""
        result = compute_simulation(
            ca_mensuel_ttc=Decimal("1000"),
            total_salaires_charges=Decimal("1500"),
            total_depenses_ttc=Decimal("500"),
            business_type="auto_micro",
        )
        assert result.cash_flow < Decimal("0")
        assert result.is_profitable is False
        assert result.tva_estimee == Decimal("0.00")

    def test_simulation_raises_on_negative_ca(self):
        """compute_simulation() must raise ValueError for negative CA."""
        with pytest.raises(ValueError, match="ca_mensuel_ttc"):
            compute_simulation(
                ca_mensuel_ttc=Decimal("-100"),
                total_salaires_charges=Decimal("0"),
                total_depenses_ttc=Decimal("0"),
                business_type="auto_micro",
            )
