"""
Tests for TASK-2.6.2: Prestataire Charges Logic Fix.

Verifies:
  1. calc_charges_prestataire() returns zero charges, cout_total = invoice amount
  2. _calc_charges_for_employee() routes prestataire correctly (no calc_charges_salarie)
  3. Salarié and TNS calculations are unchanged (regression)
  4. Prestataire section A contribution = invoice amount (not invoice + phantom charges)

All tests are pure unit tests — no database required.
"""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.calculations.social_charges import (
    calc_charges_prestataire,
    calc_charges_salarie,
    estimate_charges_tns,
    PrestataireResult,
)
from app.services.salary import _calc_charges_for_employee


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_employee(role_type: str) -> MagicMock:
    """
    Create a mock Employee ORM object with the given role_type.
    Used so _calc_charges_for_employee() can be unit-tested without a database.
    """
    emp = MagicMock()
    emp.role_type = role_type
    return emp


# ── calc_charges_prestataire() ─────────────────────────────────────────────────


class TestCalcChargesPrestataire:
    """Unit tests for the dedicated prestataire calculation function."""

    def test_prestataire_500_zero_charges(self) -> None:
        """
        TASK-2.6.2 acceptance criterion:
        Prestataire with 500 € invoice → charges = 0, cout_total = 500.
        """
        result = calc_charges_prestataire(Decimal("500.00"))
        assert isinstance(result, PrestataireResult)
        assert result.charges_patronales == Decimal("0")
        assert result.cout_total == Decimal("500.00")
        assert result.montant_facture == Decimal("500.00")

    def test_prestataire_invoice_is_total_cost(self) -> None:
        """
        The salon's only cost = invoice TTC. cout_total must equal montant_facture exactly.
        """
        for amount in ["250.00", "1000.00", "1823.03", "3500.00"]:
            result = calc_charges_prestataire(Decimal(amount))
            assert result.cout_total == result.montant_facture, (
                f"cout_total {result.cout_total} ≠ montant_facture {result.montant_facture}"
            )

    def test_prestataire_charges_always_zero(self) -> None:
        """
        No matter the invoice amount, charges_patronales must be zero.
        WHY: Prestataire invoices are not employment costs — no URSSAF, no retraite.
        """
        for amount in ["100.00", "500.00", "2000.00", "5000.00"]:
            result = calc_charges_prestataire(Decimal(amount))
            assert result.charges_patronales == Decimal("0"), (
                f"Expected 0 charges for {amount} € invoice, got {result.charges_patronales}"
            )

    def test_prestataire_invariants_enforced(self) -> None:
        """
        PrestataireResult.__post_init__ enforces: charges=0, cout_total=montant_facture.
        Even if dataclass fields were tampered, the invariant holds.
        """
        result = PrestataireResult(montant_facture=Decimal("750.00"))
        assert result.charges_patronales == Decimal("0")
        assert result.cout_total == Decimal("750.00")

    def test_prestataire_rounding(self) -> None:
        """Result is rounded to 2 decimal places."""
        result = calc_charges_prestataire(Decimal("333.333"))
        assert result.montant_facture == Decimal("333.33")
        assert result.cout_total == Decimal("333.33")


# ── _calc_charges_for_employee() ───────────────────────────────────────────────


class TestCalcChargesForEmployee:
    """Unit tests for the salary service's charge routing function."""

    def test_prestataire_returns_zero_charges(self) -> None:
        """
        TASK-2.6.2: _calc_charges_for_employee() must return (0, invoice, None)
        for prestataire employees, regardless of salon business_type.

        Previously this fell through to calc_charges_salarie() producing ~2% charges.
        """
        emp = _make_employee("prestataire")
        cotisations, total, net_approx = _calc_charges_for_employee(
            emp, "sarl", Decimal("500.00")
        )
        assert cotisations == Decimal("0"), f"Expected 0 charges, got {cotisations}"
        assert total == Decimal("500.00"), f"Expected total=500, got {total}"
        assert net_approx is None, "salaire_net_approx should be None for prestataire"

    def test_prestataire_different_business_types(self) -> None:
        """
        Prestataire zero-charge logic applies regardless of salon structure.
        The salon's legal structure does NOT affect freelancer cost.
        """
        emp = _make_employee("prestataire")
        for btype in ["sarl", "sas", "sasu", "eurl", "eirl", "auto_micro"]:
            cotisations, total, _ = _calc_charges_for_employee(
                emp, btype, Decimal("800.00")
            )
            assert cotisations == Decimal("0"), (
                f"business_type={btype}: expected 0 charges, got {cotisations}"
            )
            assert total == Decimal("800.00"), (
                f"business_type={btype}: expected total=800, got {total}"
            )

    def test_prestataire_contribution_to_section_a(self) -> None:
        """
        TASK-2.6.2 acceptance criterion:
        Prestataire contributes invoice amount to Section A, NOT invoice + phantom charges.
        """
        emp = _make_employee("prestataire")
        invoice_amount = Decimal("1200.00")
        cotisations, total, _ = _calc_charges_for_employee(
            emp, "sarl", invoice_amount
        )
        # Section A total for this row = total_charge
        assert total == invoice_amount, (
            f"Section A contribution should be {invoice_amount}, got {total}"
        )
        # No phantom charges added on top
        assert total == invoice_amount + cotisations

    def test_salarie_charges_unchanged(self) -> None:
        """
        Regression: salarié calculation must not be affected by the prestataire fix.
        Uses a known value: 2200 € brut → charges ≈ 400 €, ratio ≈ 1.18.
        Verified against 06-social-charges-reference.md.
        """
        emp = _make_employee("salarie")
        salaire_brut = Decimal("2200.00")
        cotisations, total, net_approx = _calc_charges_for_employee(
            emp, "sarl", salaire_brut
        )
        # Sanity check: charges are positive and make sense for a salarié
        assert cotisations > Decimal("0"), "Salarié should have positive charges"
        assert total > salaire_brut, "Employer cost must exceed brut for salarié"
        # Rough range check (from reference doc: ~400 € charges at 2200 €)
        assert Decimal("300") < cotisations < Decimal("600"), (
            f"Salarié charges at 2200 € out of expected range: {cotisations}"
        )
        assert net_approx is not None, "Salarié should have net_approx"
        assert net_approx < salaire_brut, "Net should be less than brut"

    def test_tns_dirigeant_charges_unchanged(self) -> None:
        """
        Regression: TNS dirigeant calculation (45%) must not be affected.
        """
        emp = _make_employee("dirigeant")
        remuneration = Decimal("2000.00")
        cotisations, total, net_approx = _calc_charges_for_employee(
            emp, "sarl", remuneration  # SARL = TNS
        )
        # TNS: charges ≈ 45% of net remuneration
        expected_charges = remuneration * Decimal("0.45")
        assert abs(cotisations - expected_charges) < Decimal("1.00"), (
            f"TNS charges {cotisations} ≠ expected {expected_charges}"
        )
        assert total == remuneration + cotisations
        assert net_approx is None, "TNS dirigeant has no net_approx"

    def test_prestataire_does_not_use_smic_calculation(self) -> None:
        """
        At SMIC level (1823 €), a salarié gets almost zero charges due to RGDU.
        But a prestataire at 1823 € MUST still have zero charges, not RGDU-reduced charges.
        This ensures the prestataire guard fires BEFORE the salarié fallthrough.
        """
        emp = _make_employee("prestataire")
        from app.calculations.social_charges import SMIC_MENSUEL_BRUT
        cotisations, total, _ = _calc_charges_for_employee(
            emp, "sarl", SMIC_MENSUEL_BRUT
        )
        # For a prestataire, charges = 0 (not the tiny RGDU-reduced salarié amount)
        assert cotisations == Decimal("0")
        assert total == SMIC_MENSUEL_BRUT


# ── Module-level docstring test ────────────────────────────────────────────────


class TestPrestataireResult:
    """Unit tests for the PrestataireResult dataclass."""

    def test_charges_always_zero_on_construction(self) -> None:
        """charges_patronales is forced to 0 by __post_init__ even if caller passes a value."""
        result = PrestataireResult(
            montant_facture=Decimal("500.00"),
            charges_patronales=Decimal("999"),  # Will be overridden
            cout_total=Decimal("0"),             # Will be set to montant_facture
        )
        assert result.charges_patronales == Decimal("0")
        assert result.cout_total == Decimal("500.00")

    def test_zero_invoice(self) -> None:
        """Zero invoice → zero charges, zero total."""
        result = calc_charges_prestataire(Decimal("0"))
        assert result.charges_patronales == Decimal("0")
        assert result.cout_total == Decimal("0")
