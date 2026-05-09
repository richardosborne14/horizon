"""
Unit tests for Task 2.8.6 — YTD cumul cash-flow alert.

Tests cover:
  - _fmt_euros helper (French locale formatting)
  - _current_fiscal_ending_year helper (fiscal window determination)
  - compute_cash_flow_alert alert tiers (pure logic, mocked DB)
  - CashFlowAlertData.to_dict() serialisation

These tests run WITHOUT hitting the database — the DB session is fully mocked.
The _today parameter makes the service deterministic without patching date.today().
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.cash_flow_alert import (
    CashFlowAlertData,
    _current_fiscal_ending_year,
    _fmt_euros,
    compute_cash_flow_alert,
)


# ── _fmt_euros ─────────────────────────────────────────────────────────────────


class TestFmtEuros:
    def test_basic_amount(self) -> None:
        """1234.50 → '1 234,50 €'"""
        result = _fmt_euros(Decimal("1234.50"))
        assert result == "1 234,50 €"

    def test_small_amount(self) -> None:
        """99.99 → '99,99 €'"""
        result = _fmt_euros(Decimal("99.99"))
        assert result == "99,99 €"

    def test_large_amount(self) -> None:
        """12345.00 → '12 345,00 €'"""
        result = _fmt_euros(Decimal("12345.00"))
        assert result == "12 345,00 €"

    def test_negative_taken_abs(self) -> None:
        """Negative values are treated as absolute."""
        result = _fmt_euros(Decimal("-500.00"))
        assert result == "500,00 €"

    def test_zero(self) -> None:
        result = _fmt_euros(Decimal("0"))
        assert result == "0,00 €"


# ── _current_fiscal_ending_year ────────────────────────────────────────────────


class TestCurrentFiscalEndingYear:
    def test_january_always_current_year(self) -> None:
        """Calendar-aligned (Jan): ending year = current year."""
        assert _current_fiscal_ending_year(date(2026, 4, 21), 1) == 2026
        assert _current_fiscal_ending_year(date(2026, 12, 31), 1) == 2026

    def test_october_before_start(self) -> None:
        """Apr 2026, fiscal start Oct: haven't reached Oct yet → ends this year."""
        # Oct 2025 – Sep 2026 exercise → ending year 2026
        assert _current_fiscal_ending_year(date(2026, 4, 21), 10) == 2026

    def test_october_after_start(self) -> None:
        """Nov 2026, fiscal start Oct: past the start → ends next year."""
        # Oct 2026 – Sep 2027 exercise → ending year 2027
        assert _current_fiscal_ending_year(date(2026, 11, 1), 10) == 2027

    def test_june_start_in_june(self) -> None:
        """June 2026, fiscal start June: we're AT the start → ends next year."""
        # Jun 2026 – May 2027 exercise → ending year 2027
        assert _current_fiscal_ending_year(date(2026, 6, 1), 6) == 2027

    def test_june_start_before_june(self) -> None:
        """May 2026, fiscal start June: haven't reached start → ends this year."""
        # Jun 2025 – May 2026 exercise → ending year 2026
        assert _current_fiscal_ending_year(date(2026, 5, 31), 6) == 2026


# ── CashFlowAlertData ─────────────────────────────────────────────────────────


class TestCashFlowAlertData:
    def _make(self, **overrides: object) -> CashFlowAlertData:
        defaults = dict(
            fiscal_year=2026,
            fiscal_start_month=1,
            months_elapsed=3,
            months_with_data=3,
            cash_flow_ytd=Decimal("1000.00"),
            point_mort_ytd=Decimal("800.00"),
            target_with_securite_ytd=Decimal("840.00"),
            target_with_benefice_ytd=Decimal("920.00"),
            delta_vs_securite=Decimal("160.00"),
            delta_vs_benefice=Decimal("80.00"),
            alert_level="on_track",
            alert_message="Vous êtes sur la bonne voie.",
        )
        defaults.update(overrides)
        return CashFlowAlertData(**defaults)

    def test_to_dict_types(self) -> None:
        """All Decimal values become float in to_dict()."""
        d = self._make().to_dict()
        assert isinstance(d["cash_flow_ytd"], float)
        assert isinstance(d["point_mort_ytd"], float)
        assert isinstance(d["alert_level"], str)
        assert isinstance(d["fiscal_year"], int)

    def test_to_dict_values(self) -> None:
        """Values round-trip correctly through to_dict."""
        d = self._make(cash_flow_ytd=Decimal("500.00")).to_dict()
        assert d["cash_flow_ytd"] == 500.0


# ── compute_cash_flow_alert (mocked DB) ───────────────────────────────────────
#
# Fixture rewrite (Bug 7 follow-up, 2026-04-23):
#   The service was refactored to call `compute_full_point_mort` (the same
#   formula used by the pilotage detail view) so the YTD cumul card agrees
#   with the per-month cards. That means the test mocks can no longer
#   short-circuit the calculation by returning raw sums — they have to
#   either feed real Decimal data through `compute_full_point_mort`, or
#   stub it out. We stub it: the alert-tier logic is what this test suite
#   cares about, the formula itself is covered by `test_task_3_x_ae_ux.py`
#   and `test_2_6_1_ae_tva.py`.


def _make_mock_report(report_id: str, ca_ttc: float) -> MagicMock:
    """Create a mock MonthlyReport object with the fields the service reads."""
    report = MagicMock()
    report.id = report_id
    report.ca_realise_ttc = Decimal(str(ca_ttc))
    report.expenses = []
    report.remboursement_emprunt = Decimal("0")
    report.subventions = Decimal("0")
    report.cout_vie_perso_override = None
    return report


def _make_db_one_month(
    report: MagicMock | None,
    extra_no_data_calls: int = 11,
) -> AsyncMock:
    """
    Mock AsyncSession for a fiscal year where only 1 month matters.

    With the refactored service, DB calls per elapsed month are:
      Call 1: select MonthlyReport for (year, month)  (always)
      Call 2: select MonthlySalary for salary rows   (only if report found)

    Months with no report make only Call 1.

    Args:
        report:              Mock report (None = no data for the first month).
        extra_no_data_calls: Additional "no report" calls for other elapsed months.
    """
    db = AsyncMock()
    side_effects = []

    if report is not None:
        # Report found → 2 calls (MonthlyReport + MonthlySalary rows)
        report_result = MagicMock()
        report_result.scalar_one_or_none.return_value = report

        salary_result = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = []  # no salary rows — point_mort controlled via stubbed compute_full_point_mort
        salary_result.scalars.return_value = scalars

        side_effects.extend([report_result, salary_result])
    else:
        # No report → 1 call only
        no_result = MagicMock()
        no_result.scalar_one_or_none.return_value = None
        side_effects.append(no_result)

    # Remaining elapsed months have no report → 1 call each
    for _ in range(extra_no_data_calls):
        no_result = MagicMock()
        no_result.scalar_one_or_none.return_value = None
        side_effects.append(no_result)

    db.execute = AsyncMock(side_effect=side_effects)
    return db


def _stub_pm(cash_flow: float, point_mort: float):
    """
    Build a stub `MonthlyFullPointMort`-like object with only the fields
    `compute_cash_flow_alert` reads.
    """
    return SimpleNamespace(
        cash_flow=Decimal(str(cash_flow)),
        point_mort_dirigeant_inclus=Decimal(str(point_mort)),
    )


@pytest.mark.asyncio
class TestComputeCashFlowAlert:
    _SALON_ID = uuid.uuid4()
    _MARGE = Decimal("0.05")
    _BENEFICE = Decimal("0.10")

    async def test_no_data(self) -> None:
        """Returns 'no_data' when no MonthlyReport exists in the fiscal year.

        Today = Jan 31, 2026, fiscal_start = 1 → 1 elapsed month, 0 with data.
        """
        # No report for Jan 2026
        db = _make_db_one_month(report=None, extra_no_data_calls=0)
        result = await compute_cash_flow_alert(
            db=db,
            salon_id=self._SALON_ID,
            fiscal_year_start=1,
            marge_securite_pct=self._MARGE,
            benefice_cible_pct=self._BENEFICE,
            _today=date(2026, 1, 31),
        )

        assert result.alert_level == "no_data"
        assert result.months_with_data == 0
        assert result.months_elapsed == 1
        assert result.cash_flow_ytd == Decimal("0.00")

    async def test_on_track(self) -> None:
        """
        on_track: cash_flow_ytd >= target_with_benefice_ytd.

        Stubbed: cash_flow=1400, point_mort=600
        target_benefice = 600 × 0.15 = 90 (= 0.05 + 0.10 aggregate rate)
        1400 >= 90 → on_track
        """
        report = _make_mock_report("r1", ca_ttc=2400.0)
        db = _make_db_one_month(report=report, extra_no_data_calls=0)

        with patch(
            "app.services.monthly_report.compute_full_point_mort",
            return_value=_stub_pm(cash_flow=1400.0, point_mort=600.0),
        ):
            result = await compute_cash_flow_alert(
                db=db,
                salon_id=self._SALON_ID,
                fiscal_year_start=1,
                marge_securite_pct=self._MARGE,
                benefice_cible_pct=self._BENEFICE,
                _today=date(2026, 1, 31),
            )

        assert result.alert_level == "on_track"
        assert result.months_with_data == 1
        assert result.cash_flow_ytd == Decimal("1400.00")
        assert result.point_mort_ytd == Decimal("600.00")
        assert result.target_with_benefice_ytd == Decimal("90.00")

    async def test_critical(self) -> None:
        """
        critical: cash_flow_ytd < -(25% of point_mort).

        Stubbed: cash_flow=-500, point_mort=600
        threshold = -150 (25% of 600) → -500 < -150 → critical
        """
        report = _make_mock_report("r1", ca_ttc=120.0)
        db = _make_db_one_month(report=report, extra_no_data_calls=0)

        with patch(
            "app.services.monthly_report.compute_full_point_mort",
            return_value=_stub_pm(cash_flow=-500.0, point_mort=600.0),
        ):
            result = await compute_cash_flow_alert(
                db=db,
                salon_id=self._SALON_ID,
                fiscal_year_start=1,
                marge_securite_pct=self._MARGE,
                benefice_cible_pct=self._BENEFICE,
                _today=date(2026, 1, 31),
            )

        assert result.alert_level == "critical"
        assert "Alerte" in result.alert_message

    async def test_warning(self) -> None:
        """
        warning: -(25% of point_mort) <= cash_flow < 0.

        Stubbed: cash_flow=-100, point_mort=800
        25% of 800 = 200 → -100 is within [-200, 0) → warning
        """
        report = _make_mock_report("r1", ca_ttc=840.0)
        db = _make_db_one_month(report=report, extra_no_data_calls=0)

        with patch(
            "app.services.monthly_report.compute_full_point_mort",
            return_value=_stub_pm(cash_flow=-100.0, point_mort=800.0),
        ):
            result = await compute_cash_flow_alert(
                db=db,
                salon_id=self._SALON_ID,
                fiscal_year_start=1,
                marge_securite_pct=self._MARGE,
                benefice_cible_pct=self._BENEFICE,
                _today=date(2026, 1, 31),
            )

        assert result.alert_level == "warning"
        assert "Attention" in result.alert_message

    async def test_above_break_even(self) -> None:
        """
        above_break_even: 0 <= cash_flow < target_securite.

        Stubbed: cash_flow=10, point_mort=800
        target_securite = 800 × 0.05 = 40 → 10 ∈ [0, 40) → above_break_even
        """
        report = _make_mock_report("r1", ca_ttc=972.0)
        db = _make_db_one_month(report=report, extra_no_data_calls=0)

        with patch(
            "app.services.monthly_report.compute_full_point_mort",
            return_value=_stub_pm(cash_flow=10.0, point_mort=800.0),
        ):
            result = await compute_cash_flow_alert(
                db=db,
                salon_id=self._SALON_ID,
                fiscal_year_start=1,
                marge_securite_pct=self._MARGE,
                benefice_cible_pct=self._BENEFICE,
                _today=date(2026, 1, 31),
            )

        assert result.alert_level == "above_break_even"

    async def test_safe_no_profit(self) -> None:
        """
        safe_no_profit: target_securite <= cash_flow < target_benefice.

        Stubbed: cash_flow=50, point_mort=600
        target_securite = 30, target_benefice = 90 → 50 ∈ [30, 90) → safe_no_profit
        """
        report = _make_mock_report("r1", ca_ttc=780.0)
        db = _make_db_one_month(report=report, extra_no_data_calls=0)

        with patch(
            "app.services.monthly_report.compute_full_point_mort",
            return_value=_stub_pm(cash_flow=50.0, point_mort=600.0),
        ):
            result = await compute_cash_flow_alert(
                db=db,
                salon_id=self._SALON_ID,
                fiscal_year_start=1,
                marge_securite_pct=self._MARGE,
                benefice_cible_pct=self._BENEFICE,
                _today=date(2026, 1, 31),
            )

        assert result.alert_level == "safe_no_profit"
        assert "marge de sécurité" in result.alert_message

    async def test_limited_data_suffix(self) -> None:
        """When months_with_data == 1, the message includes 'Données limitées'."""
        report = _make_mock_report("r1", ca_ttc=2400.0)
        db = _make_db_one_month(report=report, extra_no_data_calls=0)

        with patch(
            "app.services.monthly_report.compute_full_point_mort",
            return_value=_stub_pm(cash_flow=1400.0, point_mort=600.0),
        ):
            result = await compute_cash_flow_alert(
                db=db,
                salon_id=self._SALON_ID,
                fiscal_year_start=1,
                marge_securite_pct=self._MARGE,
                benefice_cible_pct=self._BENEFICE,
                _today=date(2026, 1, 31),
            )

        assert result.months_with_data == 1
        assert "Données limitées" in result.alert_message

    async def test_fiscal_year_non_january(self) -> None:
        """
        Fiscal year starting in October correctly scopes months.

        Today = Apr 21, 2026, fiscal_start = 10
        → fiscal year 2026 (Oct 2025 – Sep 2026)
        → elapsed: Oct, Nov, Dec 2025, Jan, Feb, Mar, Apr 2026 = 7 months
        → report only in Oct 2025 (first elapsed month)
        """
        report = _make_mock_report("r1", ca_ttc=1200.0)
        # 1 month with data, 6 months without
        db = _make_db_one_month(report=report, extra_no_data_calls=6)

        with patch(
            "app.services.monthly_report.compute_full_point_mort",
            return_value=_stub_pm(cash_flow=600.0, point_mort=600.0),
        ):
            result = await compute_cash_flow_alert(
                db=db,
                salon_id=self._SALON_ID,
                fiscal_year_start=10,
                marge_securite_pct=self._MARGE,
                benefice_cible_pct=self._BENEFICE,
                _today=date(2026, 4, 21),
            )

        assert result.fiscal_start_month == 10
        assert result.months_elapsed == 7
        assert result.months_with_data == 1
        assert result.fiscal_year == 2026

    async def test_multi_month_aggregation(self) -> None:
        """
        Three months of data are summed correctly.

        Stubbed: per-month cash_flow=1400, point_mort=600
        YTD (3 months): cash_flow = 4200, point_mort = 1800
        target_benefice = 1800 × 0.15 = 270 → 4200 >= 270 → on_track
        """
        report = _make_mock_report("r1", ca_ttc=2400.0)

        # 3 months with data → 3× (MonthlyReport select + MonthlySalary select)
        db = AsyncMock()
        side_effects = []
        for _ in range(3):
            rr = MagicMock()
            rr.scalar_one_or_none.return_value = report
            salary_result = MagicMock()
            scalars = MagicMock()
            scalars.all.return_value = []
            salary_result.scalars.return_value = scalars
            side_effects.extend([rr, salary_result])
        db.execute = AsyncMock(side_effect=side_effects)

        with patch(
            "app.services.monthly_report.compute_full_point_mort",
            return_value=_stub_pm(cash_flow=1400.0, point_mort=600.0),
        ):
            result = await compute_cash_flow_alert(
                db=db,
                salon_id=self._SALON_ID,
                fiscal_year_start=1,
                marge_securite_pct=self._MARGE,
                benefice_cible_pct=self._BENEFICE,
                _today=date(2026, 3, 31),
            )

        assert result.months_elapsed == 3
        assert result.months_with_data == 3
        assert result.cash_flow_ytd == Decimal("4200.00")
        assert result.point_mort_ytd == Decimal("1800.00")
        assert result.alert_level == "on_track"
        # Multi-month: no limited-data suffix
        assert "Données limitées" not in result.alert_message
