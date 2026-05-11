"""Tests for TASK-7.16: Real estate appreciation model."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.calculations.property import compute_downsize_capital, project_property_value


class TestPropertyAppreciation:
    """Property value projection with compound appreciation."""

    def test_appreciation_2pct_20years(self):
        """350k at 2% for 20 years → ~519k."""
        result = project_property_value(
            current_value=Decimal("350000"),
            appreciation_rate=Decimal("0.02"),
            years=20,
        )
        # Expected: 350000 * (1.02)^20 = 520,081.59
        assert result == Decimal("520081.59")

    def test_appreciation_zero_rate(self):
        """0% appreciation → value stays the same."""
        result = project_property_value(
            current_value=Decimal("400000"),
            appreciation_rate=Decimal("0"),
            years=10,
        )
        assert result == Decimal("400000.00")

    def test_appreciation_one_year(self):
        """1 year at 3% → 103%."""
        result = project_property_value(
            current_value=Decimal("200000"),
            appreciation_rate=Decimal("0.03"),
            years=1,
        )
        assert result == Decimal("206000.00")

    def test_appreciation_zero_years(self):
        """0 years → base value."""
        result = project_property_value(
            current_value=Decimal("300000"),
            appreciation_rate=Decimal("0.05"),
            years=0,
        )
        assert result == Decimal("300000.00")


class TestDownsizeCapital:
    """Downsizing freed capital computation."""

    def test_downsize_sell_450k_buy_200k(self):
        """Sell 450k, buy 200k → after costs ~197k freed."""
        freed = compute_downsize_capital(
            property_value_at_downsize=Decimal("450000"),
            replacement_value=Decimal("200000"),
        )
        # Net sale: 450000 * 0.92 = 414000
        # Gross purchase: 200000 * 1.08 = 216000
        # Freed: 414000 - 216000 = 198000
        assert freed == Decimal("198000.00")

    def test_downsize_buying_more_expensive_no_capital(self):
        """Buying more expensive → no freed capital (returns 0)."""
        freed = compute_downsize_capital(
            property_value_at_downsize=Decimal("300000"),
            replacement_value=Decimal("400000"),
        )
        # Net sale: 276000, purchase: 432000 → negative → 0
        assert freed == Decimal("0")

    def test_downsize_equal_value(self):
        """Sell and buy equal → slight loss from costs, returns 0."""
        freed = compute_downsize_capital(
            property_value_at_downsize=Decimal("300000"),
            replacement_value=Decimal("300000"),
        )
        # Net sale: 276000, purchase: 324000 → -48000 → 0
        assert freed == Decimal("0")

    def test_downsize_big_difference(self):
        """Selling 800k, buying 200k → substantial freed capital."""
        freed = compute_downsize_capital(
            property_value_at_downsize=Decimal("800000"),
            replacement_value=Decimal("200000"),
        )
        # Net sale: 736000, purchase: 216000 → 520000
        assert freed == Decimal("520000.00")


class TestPropertyInProjection:
    """Integration test: property in actual projection engine."""

    def test_property_value_in_timeline_without_investments(self):
        """Property value appears in timeline even with no investments."""
        from app.calculations.projection import ProjectionInput, project_timeline

        inp = ProjectionInput(
            current_age=40,
            target_age=65,
            property_value=Decimal("350000"),
            property_appreciation_rate=Decimal("0.02"),
        )
        timeline = project_timeline(inp)

        # First year: property_value should be ~350000 * 1.02^0 = 350000
        assert timeline[0].property_value > Decimal("0")
        assert timeline[0].downsize_freed == Decimal("0")

        # Property should appreciate over time
        assert timeline[10].property_value > timeline[0].property_value

    def test_downsize_frees_capital(self):
        """Downsizing in year 10 adds freed capital to balances."""
        from app.calculations.projection import ProjectionInput, project_timeline

        inp = ProjectionInput(
            current_age=40,
            target_age=65,
            current_year=2026,
            property_value=Decimal("500000"),
            property_appreciation_rate=Decimal("0.02"),
            downsize_enabled=True,
            downsize_year=2036,  # year 10
            downsize_target_value=Decimal("200000"),
            allocations={
                "av_euro": {"balance": Decimal("50000"), "monthly": Decimal("500")},
            },
        )
        timeline = project_timeline(inp)

        # Find the downsize year
        downsize_entries = [t for t in timeline if t.downsize_freed > 0]
        assert len(downsize_entries) == 1
        entry = downsize_entries[0]
        assert entry.year == 2036
        assert entry.downsize_freed > Decimal("100000")

        # After downsize, property_value should reflect replacement
        assert entry.property_value == Decimal("200000.00")

        # Wealth should increase by freed capital
        # Check wealth in year after downsizing vs before
        prev = timeline[8]  # year before downsize
        assert entry.total_wealth > prev.total_wealth + Decimal("50000")  # should have significant jump