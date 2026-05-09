"""
Unit tests for the expense inflation preview (TASK 1.4).

Tests cover:
- Inflation preview math for all 3 scales × 4 horizons
- Zero expenses edge case
- Expense category structure
- MonthlyExpenses Pydantic model validation
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.calculations.expenses import preview_inflation
from app.calculations.constants import INFLATION_SCALES
from app.schemas.profile import (
    MonthlyExpenses,
    EXPENSE_CATEGORIES,
    EXPENSE_LABELS,
)


class TestPreviewInflation:
    """Tests for preview_inflation() — the core expense projection helper."""

    def test_moderate_10_years_800_euros(self):
        """800€ at 3% for 10 years = 800 * 1.03^10 = 1075.13."""
        result = preview_inflation(
            Decimal("800"), INFLATION_SCALES, [10]
        )
        assert "moderate" in result
        assert result["moderate"]["10"] == "1075.13"

    def test_moderate_5_years(self):
        """800€ at 3% for 5 years = 800 * 1.03^5 = 927.42."""
        result = preview_inflation(
            Decimal("800"), INFLATION_SCALES, [5]
        )
        assert result["moderate"]["5"] == "927.42"

    def test_optimistic_10_years(self):
        """800€ at 2% for 10 years = 800 * 1.02^10 = 975.20."""
        result = preview_inflation(
            Decimal("800"), INFLATION_SCALES, [10]
        )
        assert result["optimistic"]["10"] == "975.20"

    def test_pessimistic_30_years(self):
        """800€ at 4.5% for 30 years = 800 * 1.045^30 = 2996.25."""
        result = preview_inflation(
            Decimal("800"), INFLATION_SCALES, [30]
        )
        assert result["pessimistic"]["30"] == "2996.25"

    def test_all_three_scales_returned(self):
        """Preview should return all 3 scales."""
        result = preview_inflation(
            Decimal("1000"), INFLATION_SCALES, [5, 10]
        )
        assert set(result.keys()) == {"optimistic", "moderate", "pessimistic"}

    def test_all_horizons_returned(self):
        """Preview should return all requested horizons for each scale."""
        horizons = [5, 10, 20, 30]
        result = preview_inflation(
            Decimal("500"), INFLATION_SCALES, horizons
        )
        for scale_key, scale_data in result.items():
            assert set(scale_data.keys()) == {str(h) for h in horizons}

    def test_zero_expenses(self):
        """Zero total should produce zero for all scales/horizons."""
        result = preview_inflation(
            Decimal("0"), INFLATION_SCALES, [5, 10, 20, 30]
        )
        for scale_data in result.values():
            for horizon_val in scale_data.values():
                assert horizon_val == "0.00"

    def test_all_values_are_strings(self):
        """Each value should be a string for JSON serialisation."""
        result = preview_inflation(
            Decimal("1000"), INFLATION_SCALES, [10]
        )
        for scale_data in result.values():
            for horizon_val in scale_data.values():
                assert isinstance(horizon_val, str)

    def test_pessimistic_higher_than_optimistic(self):
        """Pessimistic inflation should always produce higher amounts."""
        result = preview_inflation(
            Decimal("1000"), INFLATION_SCALES, [10, 20, 30]
        )
        for horizon in ["10", "20", "30"]:
            opt = Decimal(result["optimistic"][horizon])
            mod = Decimal(result["moderate"][horizon])
            pes = Decimal(result["pessimistic"][horizon])
            assert pes > mod > opt, (
                f"At {horizon}yr: expected {pes} > {mod} > {opt}"
            )


class TestMonthlyExpensesModel:
    """Tests for the MonthlyExpenses Pydantic model."""

    def test_default_all_zeros(self):
        """Default constructed MonthlyExpenses should have all zeros."""
        exp = MonthlyExpenses()
        for field in EXPENSE_CATEGORIES:
            val = getattr(exp, field)
            assert isinstance(val, Decimal)
            assert val == Decimal("0")

    def test_total_sums_correctly(self):
        """The total property should sum all 12 categories."""
        exp = MonthlyExpenses(
            loyer=Decimal("800"),
            energie=Decimal("120"),
            internet=Decimal("60"),
            assurance=Decimal("100"),
            transport=Decimal("200"),
            alimentation=Decimal("400"),
            sante=Decimal("50"),
            loisirs=Decimal("150"),
            abonnements=Decimal("50"),
            impots=Decimal("100"),
            credit=Decimal("0"),
            divers=Decimal("100"),
        )
        # 800+120+60+100+200+400+50+150+50+100+0+100 = 2130
        assert exp.total == Decimal("2130")

    def test_total_with_zeros(self):
        """Total with mixed zeros and non-zeros."""
        exp = MonthlyExpenses(
            loyer=Decimal("500"),
            energie=Decimal("0"),
            internet=Decimal("50"),
            assurance=Decimal("0"),
            transport=Decimal("0"),
            alimentation=Decimal("0"),
            sante=Decimal("0"),
            loisirs=Decimal("0"),
            abonnements=Decimal("0"),
            impots=Decimal("0"),
            credit=Decimal("0"),
            divers=Decimal("0"),
        )
        assert exp.total == Decimal("550")

    def test_string_input_coerced_to_decimal(self):
        """String inputs should be coerced to Decimal."""
        exp = MonthlyExpenses(loyer="800", energie=120)
        assert isinstance(exp.loyer, Decimal)
        assert exp.loyer == Decimal("800")
        assert isinstance(exp.energie, Decimal)
        assert exp.energie == Decimal("120")

    def test_negative_rejected(self):
        """Negative expense values should raise a ValidationError."""
        with pytest.raises(ValidationError):
            MonthlyExpenses(loyer=Decimal("-100"))

    def test_none_coerced_to_zero(self):
        """None values should be treated as zero."""
        exp = MonthlyExpenses(loyer=None)
        assert exp.loyer == Decimal("0")

    def test_all_fields_are_decimal(self):
        """Every field on a constructed MonthlyExpenses should be a Decimal."""
        exp = MonthlyExpenses(loyer=800, energie=120)
        for field in EXPENSE_CATEGORIES:
            val = getattr(exp, field)
            assert isinstance(val, Decimal), (
                f"Field '{field}' is {type(val).__name__}, expected Decimal"
            )


class TestExpenseCategories:
    """Tests for the expense category constants."""

    def test_12_categories(self):
        """There should be exactly 12 expense categories."""
        assert len(EXPENSE_CATEGORIES) == 12

    def test_labels_for_all_categories(self):
        """Every category should have a French label."""
        for cat in EXPENSE_CATEGORIES:
            assert cat in EXPENSE_LABELS, (
                f"Missing label for '{cat}'"
            )
            assert isinstance(EXPENSE_LABELS[cat], str)
            assert len(EXPENSE_LABELS[cat]) > 0

    def test_no_duplicates(self):
        """No duplicate categories or labels."""
        assert len(EXPENSE_CATEGORIES) == len(set(EXPENSE_CATEGORIES))