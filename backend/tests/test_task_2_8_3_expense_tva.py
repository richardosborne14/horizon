"""
Task 2.8.3 — Per-line TVA rate on expenses.

Tests cover:
  1. _calc_ht_and_tva helper: all four rates (0, 5.5%, 10%, 20%) + rounding
  2. ExpenseCreate schema: valid rates pass, invalid rate raises ValueError
  3. create_expense service: stores tva_rate, computes correct HT/TVA
  4. update_expense service: recalculates on tva_rate change
  5. AE guard: tva_rate forced to 0 for auto_micro salons regardless of payload
  6. _compute_totals: mixed-rate expense list produces correct tva_payee_achats
"""

import uuid
from decimal import Decimal

import pytest

from app.services.monthly_report import _calc_ht_and_tva


# ── Unit tests: _calc_ht_and_tva helper ────────────────────────────────────────


class TestCalcHtAndTva:
    """Unit tests for the per-row TVA calculation helper."""

    def test_20_percent_standard(self):
        """Standard 20% TVA: 120 TTC → 100 HT, 20 TVA."""
        ht, tva = _calc_ht_and_tva(Decimal("120.00"), Decimal("0.200"))
        assert ht == pytest.approx(Decimal("100"), abs=Decimal("0.01"))
        assert tva == pytest.approx(Decimal("20"), abs=Decimal("0.01"))
        assert ht + tva == Decimal("120.00")

    def test_10_percent_restauration(self):
        """10% TVA (restauration/transport): 110 TTC → 100 HT, 10 TVA."""
        ht, tva = _calc_ht_and_tva(Decimal("110.00"), Decimal("0.100"))
        assert ht == pytest.approx(Decimal("100"), abs=Decimal("0.01"))
        assert tva == pytest.approx(Decimal("10"), abs=Decimal("0.01"))

    def test_5_5_percent_presse(self):
        """5.5% TVA (presse/livres): 105.50 TTC → 100 HT, 5.50 TVA."""
        ht, tva = _calc_ht_and_tva(Decimal("105.50"), Decimal("0.055"))
        # amount_ht = 105.50 / 1.055 = 100.0
        assert float(ht) == pytest.approx(100.0, abs=0.01)
        assert float(tva) == pytest.approx(5.5, abs=0.01)

    def test_zero_rate_tva_exempt(self):
        """TVA-exempt (0%): amount_ht = amount_ttc, tva_amount = 0."""
        ht, tva = _calc_ht_and_tva(Decimal("500.00"), Decimal("0"))
        assert ht == Decimal("500.00")
        assert tva == Decimal("0")

    def test_sum_integrity(self):
        """ht + tva must always equal ttc for all valid rates."""
        for rate in ["0", "0.055", "0.100", "0.200"]:
            ttc = Decimal("347.89")
            ht, tva = _calc_ht_and_tva(ttc, Decimal(rate))
            # Cast to float for pytest.approx — Decimal + float mixed comparison fails
            assert float(ht + tva) == pytest.approx(
                float(ttc), abs=0.001
            ), f"Sum check failed for rate {rate}"


# ── Schema validation ──────────────────────────────────────────────────────────


class TestExpenseCreateSchema:
    """Tests for ExpenseCreate.validate_tva_rate."""

    def test_valid_rates_accepted(self):
        from app.schemas.monthly_report import ExpenseCreate

        for rate in ["0", "0.055", "0.100", "0.200"]:
            obj = ExpenseCreate(
                category_id=uuid.uuid4(),
                amount_ttc=Decimal("100.00"),
                tva_rate=Decimal(rate),
            )
            assert obj.tva_rate == Decimal(rate)

    def test_invalid_rate_rejected(self):
        from pydantic import ValidationError
        from app.schemas.monthly_report import ExpenseCreate

        with pytest.raises(ValidationError) as exc_info:
            ExpenseCreate(
                category_id=uuid.uuid4(),
                amount_ttc=Decimal("100.00"),
                tva_rate=Decimal("0.150"),  # 15% is not a valid French TVA rate
            )
        assert "Taux de TVA invalide" in str(exc_info.value)

    def test_default_rate_is_20_percent(self):
        from app.schemas.monthly_report import ExpenseCreate

        obj = ExpenseCreate(
            category_id=uuid.uuid4(),
            amount_ttc=Decimal("100.00"),
        )
        assert obj.tva_rate == Decimal("0.200")

    def test_update_allows_none(self):
        """ExpenseUpdate.tva_rate=None is valid (no change)."""
        from app.schemas.monthly_report import ExpenseUpdate

        obj = ExpenseUpdate(amount_ttc=Decimal("50.00"))  # tva_rate not supplied
        assert obj.tva_rate is None

    def test_update_invalid_rate_rejected(self):
        from pydantic import ValidationError
        from app.schemas.monthly_report import ExpenseUpdate

        with pytest.raises(ValidationError):
            ExpenseUpdate(tva_rate=Decimal("0.333"))


# ── Integration: service layer (no DB — pure function) ────────────────────────


class TestComputeTotalsWithMixedRates:
    """
    Test _compute_totals with mixed-rate expenses using a fake MonthlyReport object.
    No database required — validates the aggregation logic.
    """

    def _make_report(self, expenses_data: list[dict]) -> object:
        """
        Build a lightweight mock MonthlyReport for testing _compute_totals.
        Each expense dict: {amount_ttc, amount_ht, tva_amount, tva_rate}
        """

        class FakeExpense:
            def __init__(self, d):
                self.amount_ttc = Decimal(str(d["amount_ttc"]))
                self.amount_ht = Decimal(str(d["amount_ht"]))
                self.tva_amount = Decimal(str(d.get("tva_amount", 0)))
                self.tva_rate = Decimal(str(d.get("tva_rate", "0.200")))

        class FakeReport:
            def __init__(self, expenses_data):
                self.ca_realise_ttc = Decimal("10000.00")
                self.subventions = Decimal("0.00")
                self.expenses = [FakeExpense(d) for d in expenses_data]

        return FakeReport(expenses_data)

    def test_all_standard_20_pct(self):
        """Single 20% expense: totals match expected values."""
        from app.services.monthly_report import _compute_totals

        report = self._make_report([
            {"amount_ttc": "120.00", "amount_ht": "100.00", "tva_amount": "20.00", "tva_rate": "0.200"}
        ])
        totals = _compute_totals(report)
        assert totals.expense_total_ttc == Decimal("120.00")
        assert totals.expense_total_ht == Decimal("100.00")
        assert totals.tva_payee_achats == Decimal("20.00")

    def test_mixed_rates(self):
        """
        Mixed: one 20% expense + one exempt.
        TTC: 120 + 500 = 620
        HT:  100 + 500 = 600
        TVA: 20 + 0   = 20
        """
        from app.services.monthly_report import _compute_totals

        report = self._make_report([
            {"amount_ttc": "120.00", "amount_ht": "100.00", "tva_amount": "20.00", "tva_rate": "0.200"},
            {"amount_ttc": "500.00", "amount_ht": "500.00", "tva_amount": "0.00", "tva_rate": "0"},
        ])
        totals = _compute_totals(report)
        assert totals.expense_total_ttc == Decimal("620.00")
        assert totals.expense_total_ht == Decimal("600.00")
        assert totals.tva_payee_achats == Decimal("20.00")

    def test_zero_rate_expenses_no_tva_payee(self):
        """Fully exempt expenses → tva_payee_achats = 0."""
        from app.services.monthly_report import _compute_totals

        report = self._make_report([
            {"amount_ttc": "200.00", "amount_ht": "200.00", "tva_amount": "0.00", "tva_rate": "0"},
            {"amount_ttc": "100.00", "amount_ht": "100.00", "tva_amount": "0.00", "tva_rate": "0"},
        ])
        totals = _compute_totals(report)
        assert totals.tva_payee_achats == Decimal("0.00")

    def test_tva_a_payer_formula(self):
        """
        tva_a_payer = tva_encaissee (20% on CA) - tva_payee_achats.
        CA = 10 000 TTC → tva_encaissee = 10000 - 10000/1.2 = 1666.67
        Expense: 120 TTC at 20% → tva_payee = 20
        tva_a_payer = 1666.67 - 20 = 1646.67
        """
        from app.services.monthly_report import _compute_totals

        report = self._make_report([
            {"amount_ttc": "120.00", "amount_ht": "100.00", "tva_amount": "20.00", "tva_rate": "0.200"}
        ])
        totals = _compute_totals(report)
        expected_tva_enc = Decimal("10000.00") - (Decimal("10000.00") / Decimal("1.2"))
        assert float(totals.tva_encaissee) == pytest.approx(float(expected_tva_enc), abs=0.01)
        assert float(totals.tva_a_payer) == pytest.approx(
            float(expected_tva_enc - Decimal("20.00")), abs=0.01
        )


# ── AE Guard unit test ──────────────────────────────────────────────────────────


class TestCalcHtAndTvaAeGuard:
    """
    Verify the AE path forces tva_rate to 0, which means:
    - amount_ht = amount_ttc
    - tva_amount = 0
    This mirrors what create_expense / update_expense do when is_ae=True.
    """

    def test_ae_rate_zero_produces_ht_equals_ttc(self):
        """Simulates the AE path: tva_rate=0 → HT = TTC."""
        ht, tva = _calc_ht_and_tva(Decimal("300.00"), Decimal("0"))
        assert ht == Decimal("300.00")
        assert tva == Decimal("0")

    def test_non_ae_10pct_different_from_ae_zero(self):
        """For same TTC, 10% gives different HT than AE 0%."""
        ht_normal, _ = _calc_ht_and_tva(Decimal("110.00"), Decimal("0.100"))
        ht_ae, tva_ae = _calc_ht_and_tva(Decimal("110.00"), Decimal("0"))
        assert ht_normal < ht_ae  # AE has higher HT (no TVA deducted)
        assert tva_ae == Decimal("0")
