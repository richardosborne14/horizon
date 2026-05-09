"""
Tests for Task 3.X — Auto-Entrepreneur UX Overhaul.

Verifies:
  1. get_ae_urssaf_rate() returns correct rates for each activity type
  2. ACRE halving/reduction applied correctly
  3. calc_ae_urssaf_cotisations() is correct for known CA amounts
  4. Unknown / None activity types fall back to bic_services
  5. compute_full_point_mort() includes URSSAF for AE, not for non-AE
  6. Non-AE behaviour is unchanged (regression protection)

All financial assertions use exact Decimal comparisons — never float equality.
Known inputs verified: 4000€ CA × 21.2% = 848.00€ URSSAF (bic_services)
"""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.calculations.social_charges import (
    AE_URSSAF_RATES,
    calc_ae_urssaf_cotisations,
    get_ae_urssaf_rate,
)
from app.schemas.monthly_report import MonthlyFullPointMort
from app.services.monthly_report import compute_full_point_mort


# ── Fixtures ───────────────────────────────────────────────────────────────────


def _make_report(ca: float, remboursement: float = 0.0, expenses=None):
    """
    Create a mock MonthlyReport with controllable CA and expenses.

    Args:
        ca: Monthly CA TTC (gross revenue).
        remboursement: Monthly loan repayment.
        expenses: List of mock Expense objects (optional).

    Returns:
        MagicMock with ca_realise_ttc, remboursement_emprunt, expenses.
    """
    report = MagicMock()
    report.ca_realise_ttc = Decimal(str(ca))
    report.remboursement_emprunt = Decimal(str(remboursement))
    report.expenses = expenses or []
    return report


def _make_expense(amount_ttc: float, amount_ht: float | None = None):
    """
    Create a mock Expense with known TTC/HT amounts.

    Args:
        amount_ttc: Amount TTC.
        amount_ht: Amount HT (auto-calculated from TTC/1.2 if omitted).

    Returns:
        MagicMock with amount_ttc, amount_ht.
    """
    e = MagicMock()
    e.amount_ttc = Decimal(str(amount_ttc))
    if amount_ht is None:
        e.amount_ht = (e.amount_ttc / Decimal("1.2")).quantize(Decimal("0.01"))
    else:
        e.amount_ht = Decimal(str(amount_ht))
    return e


# ── Unit tests: get_ae_urssaf_rate() ──────────────────────────────────────────


class TestGetAeUrssafRate:
    """Tests for the URSSAF rate lookup helper."""

    def test_bic_services_default_rate(self):
        """BIC services (most coiffeurs) = 21.2%."""
        rate, resolved = get_ae_urssaf_rate("bic_services")
        assert rate == Decimal("0.212")
        assert resolved == "bic_services"

    def test_bic_vente_rate(self):
        """BIC vente (product sales) = 12.3%."""
        rate, _ = get_ae_urssaf_rate("bic_vente")
        assert rate == Decimal("0.123")

    def test_bnc_non_reglementee_rate(self):
        """BNC non réglementé (prestataire libéral) = 25.6%."""
        rate, _ = get_ae_urssaf_rate("bnc_non_reglementee")
        assert rate == Decimal("0.256")

    def test_bnc_cipav_rate(self):
        """BNC CIPAV (professions libérales réglementées) = 23.2%."""
        rate, _ = get_ae_urssaf_rate("bnc_cipav")
        assert rate == Decimal("0.232")

    def test_none_falls_back_to_bic_services(self):
        """None activity type should fall back to bic_services."""
        rate, resolved = get_ae_urssaf_rate(None)
        assert rate == Decimal("0.212")
        assert resolved == "bic_services"

    def test_unknown_key_falls_back_to_bic_services(self):
        """Unrecognised activity type falls back to bic_services."""
        rate, resolved = get_ae_urssaf_rate("unknown_type")
        assert rate == Decimal("0.212")
        assert resolved == "bic_services"

    def test_acre_before_july_2026_halves_rate(self):
        """ACRE before July 2026: 50% exoneration → rate × 0.5."""
        rate, _ = get_ae_urssaf_rate("bic_services", has_acre=True, acre_apres_juillet_2026=False)
        assert rate == Decimal("0.106")  # 0.212 × 0.5

    def test_acre_after_july_2026_reduces_25pct(self):
        """ACRE from July 2026 onward: 25% exoneration → rate × 0.75."""
        rate, _ = get_ae_urssaf_rate("bic_services", has_acre=True, acre_apres_juillet_2026=True)
        assert rate == Decimal("0.159")  # 0.212 × 0.75

    def test_acre_bnc_before_july_2026(self):
        """BNC non réglementé with ACRE before July 2026 = 12.8%."""
        rate, _ = get_ae_urssaf_rate("bnc_non_reglementee", has_acre=True, acre_apres_juillet_2026=False)
        assert rate == Decimal("0.128")  # 0.256 × 0.5

    def test_no_acre_does_not_modify_rate(self):
        """has_acre=False should not change the base rate."""
        rate_no_acre, _ = get_ae_urssaf_rate("bic_services", has_acre=False)
        rate_with_acre_false, _ = get_ae_urssaf_rate("bic_services")
        assert rate_no_acre == rate_with_acre_false == Decimal("0.212")


# ── Unit tests: calc_ae_urssaf_cotisations() ───────────────────────────────────


class TestCalcAeUrssafCotisations:
    """Tests for monthly URSSAF cotisation computation."""

    def test_4000_bic_services(self):
        """4000€ CA × 21.2% = 848.00€ (the key user scenario from the task spec)."""
        cotisations, rate, activity_type = calc_ae_urssaf_cotisations(
            Decimal("4000"), "bic_services"
        )
        assert cotisations == Decimal("848.00")
        assert rate == Decimal("0.212")
        assert activity_type == "bic_services"

    def test_4000_bnc_non_reglementee(self):
        """4000€ CA × 25.6% = 1024.00€."""
        cotisations, rate, _ = calc_ae_urssaf_cotisations(
            Decimal("4000"), "bnc_non_reglementee"
        )
        assert cotisations == Decimal("1024.00")
        assert rate == Decimal("0.256")

    def test_zero_ca_returns_zero(self):
        """Zero CA → zero cotisations."""
        cotisations, _, _ = calc_ae_urssaf_cotisations(Decimal("0"), "bic_services")
        assert cotisations == Decimal("0.00")

    def test_5000_bic_services(self):
        """5000€ CA × 21.2% = 1060.00€."""
        cotisations, _, _ = calc_ae_urssaf_cotisations(Decimal("5000"), "bic_services")
        assert cotisations == Decimal("1060.00")

    def test_avec_acre_bic_services(self):
        """4000€ × 10.6% (ACRE before July 2026) = 424.00€."""
        cotisations, rate, _ = calc_ae_urssaf_cotisations(
            Decimal("4000"), "bic_services", has_acre=True, acre_apres_juillet_2026=False
        )
        assert cotisations == Decimal("424.00")  # 4000 × 0.106
        assert rate == Decimal("0.106")

    def test_none_activity_type_uses_default(self):
        """None activity type: falls back to bic_services rate."""
        cotisations, rate, activity = calc_ae_urssaf_cotisations(Decimal("4000"), None)
        assert cotisations == Decimal("848.00")
        assert activity == "bic_services"

    def test_rounding_to_two_decimal_places(self):
        """Result must be rounded to exactly 2 decimal places."""
        # 1234.56 × 21.2% = 261.727... → rounds to 261.73
        cotisations, _, _ = calc_ae_urssaf_cotisations(Decimal("1234.56"), "bic_services")
        assert cotisations == Decimal("261.73")


# ── Unit tests: compute_full_point_mort() — AE behaviour ─────────────────────


class TestComputeFullPointMortAe:
    """Tests for the point mort calculation when is_ae=True."""

    def test_ae_includes_urssaf_in_total(self):
        """
        AE with 4000€ CA, no expenses, no staff:
        URSSAF = 4000 × 21.2% = 848€
        point_mort = 848€
        cash_flow = 4000 - 848 = 3152€
        """
        report = _make_report(ca=4000.0)
        pm = compute_full_point_mort(
            report, [],
            is_ae=True,
            ae_activity_type="bic_services",
        )
        assert pm.urssaf_cotisations == Decimal("848.00")
        assert pm.urssaf_rate == Decimal("0.212")
        # Bug 7 fix (2026-04-23): total_AB is now the literal Section A + Section B
        # (salaries + expenses). URSSAF is a separate line folded into total_decaissement.
        assert pm.total_AB == Decimal("0")  # 0 salaries + 0 expenses
        assert pm.total_decaissement == Decimal("848.00")  # 0 + 848 URSSAF
        assert pm.cash_flow == Decimal("3152.00")  # 4000 - 848

    def test_ae_with_expenses(self):
        """
        AE with 4000€ CA, 500€ expenses:
        URSSAF = 848€, expenses = 500€
        point_mort = 1348€
        cash_flow = 4000 - 1348 = 2652€
        """
        expense = _make_expense(500.0, 500.0)  # AE: HT == TTC
        report = _make_report(ca=4000.0, expenses=[expense])
        pm = compute_full_point_mort(
            report, [],
            is_ae=True,
            ae_activity_type="bic_services",
        )
        assert pm.urssaf_cotisations == Decimal("848.00")
        assert pm.total_B == Decimal("500.00")
        assert pm.cash_flow == Decimal("2652.00")  # 4000 - 848 - 500

    def test_ae_tva_fields_are_zero(self):
        """AE: all TVA fields must be zero (franchise en base de TVA)."""
        report = _make_report(ca=4000.0)
        pm = compute_full_point_mort(report, [], is_ae=True)
        assert pm.tva_encaissee == Decimal("0")
        assert pm.tva_a_payer == Decimal("0")
        assert pm.tva_payee_achats == Decimal("0")

    def test_ae_urssaf_rate_exposed(self):
        """urssaf_rate must equal the effective rate used."""
        report = _make_report(ca=4000.0)
        pm = compute_full_point_mort(
            report, [], is_ae=True, ae_activity_type="bnc_non_reglementee"
        )
        assert pm.urssaf_rate == Decimal("0.256")
        assert pm.urssaf_cotisations == Decimal("1024.00")  # 4000 × 0.256

    def test_ae_no_urssaf_for_zero_ca(self):
        """Zero CA → zero URSSAF and zero cash_flow."""
        report = _make_report(ca=0.0)
        pm = compute_full_point_mort(report, [], is_ae=True)
        assert pm.urssaf_cotisations == Decimal("0.00")
        assert pm.cash_flow == Decimal("0.00")


# ── Regression tests: non-AE behaviour must be unchanged ──────────────────────


class TestComputeFullPointMortNonAe:
    """Regression tests — non-AE point mort must not be changed."""

    def test_non_ae_urssaf_fields_are_zero(self):
        """Non-AE: URSSAF fields must always be 0 (no change to existing logic)."""
        report = _make_report(ca=10000.0)
        pm = compute_full_point_mort(report, [], is_ae=False)
        assert pm.urssaf_cotisations == Decimal("0")
        assert pm.urssaf_rate == Decimal("0")

    def test_non_ae_tva_fields_populated(self):
        """Non-AE: TVA fields must be calculated as before.

        WHY round(, 2): compute_full_point_mort returns unrounded Decimal per
        the architecture rule "round at display time only, not intermediate steps".
        The test verifies the value is correct to 2dp without asserting the
        internal precision level.
        """
        report = _make_report(ca=10000.0)
        pm = compute_full_point_mort(report, [], is_ae=False)
        # tva_encaissee = 10000 - (10000 / 1.2) = 1666.666... → 1666.67 at display time
        assert round(pm.tva_encaissee, 2) == Decimal("1666.67")
        assert pm.tva_encaissee > Decimal("0")

    def test_non_ae_cash_flow_without_expenses(self):
        """Non-AE with 10000€ CA HT, no expenses, no salaries: cash_flow = ca_ht = 8333.33.

        WHY 8333.33: non-AE cash_flow = ca_ht - point_mort = (ca_ttc/1.2) - 0.
        Before TASK-2.15.1 the code used ca_ttc (10000) which overstated cash flow.
        """
        report = _make_report(ca=10000.0)
        pm = compute_full_point_mort(report, [], is_ae=False)
        # ca_ht = 10000 / 1.2 = 8333.33, point_mort = 0
        assert round(pm.cash_flow, 2) == Decimal("8333.33")


# ── AE rate table completeness ────────────────────────────────────────────────


def test_all_activity_types_in_rate_table():
    """All four activity types must be in AE_URSSAF_RATES."""
    assert "bic_vente" in AE_URSSAF_RATES
    assert "bic_services" in AE_URSSAF_RATES
    assert "bnc_non_reglementee" in AE_URSSAF_RATES
    assert "bnc_cipav" in AE_URSSAF_RATES


def test_all_rates_are_decimal():
    """All rates must be Decimal, not float."""
    for key, rate in AE_URSSAF_RATES.items():
        assert isinstance(rate, Decimal), f"Rate for {key} is not Decimal: {type(rate)}"


def test_rate_values_are_reasonable():
    """All rates must be between 0 and 1 (i.e. are percentages as decimals)."""
    for key, rate in AE_URSSAF_RATES.items():
        assert Decimal("0") < rate < Decimal("1"), f"Rate for {key} out of range: {rate}"
