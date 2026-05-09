"""
Unit tests for the insights engine (TASK-5.4).

Tests each insight rule individually against a mocked projection,
plus integration tests that verify ranking and the full pipeline.
"""
from decimal import Decimal
from unittest.mock import MagicMock

from app.calculations.insights import (
    Insight,
    generate_insights,
    _check_wealth_exhaustion,
    _check_no_goal_reached,
    _check_negative_net_any_year,
    _check_low_savings_rate,
    _check_unbalanced_allocations,
    _check_livret_a_near_ceiling,
    _check_increase_ca_growth,
    _check_one_more_year,
    _check_kid_peak_cost,
    _check_goal_reached_early,
    _check_good_savings_rate,
)


def _mock(year=2026, age=40, **kwargs):
    """Create a mock YearProjection for testing."""
    defaults = {
        "year": year,
        "age": age,
        "net_annual": Decimal("30000"),
        "total_wealth": Decimal("50000"),
        "total_outgoing": Decimal("20000"),
        "total_income": Decimal("50000"),
        "is_retirement": False,
        "passive_monthly": Decimal("100"),
        "project_income": Decimal("0"),
        "kid_expenses": Decimal("0"),
        "goal_reached": False,
    }
    defaults.update(kwargs)
    return MagicMock(**defaults)


# ── Critical rules ───────────────────────────────────────────────────────────

class TestWealthExhaustion:
    def test_critical_when_exhausts_before_90(self):
        tl = [_mock(age=40), _mock(age=70, is_retirement=True, total_income=Decimal("0"), total_outgoing=Decimal("36000")),
              _mock(age=75, is_retirement=True, total_income=Decimal("0"), total_outgoing=Decimal("36000"), total_wealth=Decimal("0"))]
        i = _check_wealth_exhaustion(tl, {"wealth_exhaustion_age": 75})
        assert i is not None and i.severity == "critical"

    def test_none_after_90(self):
        assert _check_wealth_exhaustion([_mock()], {"wealth_exhaustion_age": 92}) is None

    def test_none_no_exhaustion(self):
        assert _check_wealth_exhaustion([_mock()], {}) is None


class TestNoGoalReached:
    def test_warning(self):
        i = _check_no_goal_reached([_mock() for _ in range(10)], {"goal_year": None})
        assert i is not None and i.severity == "warning"

    def test_none_when_reached(self):
        assert _check_no_goal_reached([_mock(goal_reached=True)], {"goal_year": {"year": 2035, "age": 49}}) is None


class TestNegativeNet:
    def test_critical(self):
        i = _check_negative_net_any_year([_mock(year=2030, net_annual=Decimal("-5000"))])
        assert i is not None and "2030" in i.title

    def test_ignores_retirement(self):
        assert _check_negative_net_any_year([_mock(is_retirement=True, net_annual=Decimal("-5000"))]) is None


# ── Warning rules ────────────────────────────────────────────────────────────

class TestLowSavingsRate:
    def test_warning(self):
        i = _check_low_savings_rate([_mock(net_annual=Decimal("40000"))], {},
                                      [{"vehicle_key": "livret_a", "monthly": 200, "balance": 5000}])
        assert i is not None and i.severity == "warning"

    def test_none_above_15_pct(self):
        assert _check_low_savings_rate([_mock(net_annual=Decimal("40000"))], {},
                                        [{"vehicle_key": "pea", "monthly": 600, "balance": 20000}]) is None


class TestUnbalancedAllocations:
    def test_warning(self):
        allocs = [{"vehicle_key": "livret_a", "monthly": 500}, {"vehicle_key": "ldds", "monthly": 400}, {"vehicle_key": "pea", "monthly": 100}]
        assert _check_unbalanced_allocations(allocs) is not None

    def test_none_diversified(self):
        allocs = [{"vehicle_key": "livret_a", "monthly": 200}, {"vehicle_key": "pea", "monthly": 400}, {"vehicle_key": "av_uc", "monthly": 200}]
        assert _check_unbalanced_allocations(allocs) is None


class TestLivretANearCeiling:
    def test_warning(self):
        assert _check_livret_a_near_ceiling([{"vehicle_key": "livret_a", "monthly": 200, "balance": 20000}]) is not None

    def test_none_low(self):
        assert _check_livret_a_near_ceiling([{"vehicle_key": "livret_a", "monthly": 100, "balance": 5000}]) is None


# ── Opportunity rules ────────────────────────────────────────────────────────

class TestIncreaseCAGrowth:
    def test_opportunity(self):
        i = _check_increase_ca_growth([_mock(total_wealth=Decimal("100000"))], {"final_wealth": "100000"}, {"growth_rate": Decimal("0.01")})
        assert i is not None and i.severity == "opportunity"

    def test_none_high_growth(self):
        assert _check_increase_ca_growth([], {}, {"growth_rate": Decimal("0.05")}) is None


class TestOneMoreYear:
    def test_opportunity(self):
        i = _check_one_more_year([_mock(total_wealth=Decimal("100000")), _mock(year=2027, total_wealth=Decimal("115000"))], {})
        assert i is not None and i.severity == "opportunity"

    def test_none_short_timeline(self):
        assert _check_one_more_year([_mock()], {}) is None


class TestKidPeakCost:
    def test_opportunity(self):
        i = _check_kid_peak_cost([_mock(kid_expenses=Decimal("2000")), _mock(year=2030, kid_expenses=Decimal("8000"))], {})
        assert i is not None and "2030" in i.title

    def test_none_no_kids(self):
        assert _check_kid_peak_cost([_mock()], {}) is None


# ── Positive rules ───────────────────────────────────────────────────────────

class TestGoalReachedEarly:
    def test_positive(self):
        tl = [_mock(year=2035, goal_reached=True), _mock(year=2070, is_retirement=True)]
        i = _check_goal_reached_early(tl, {"goal_year": {"year": 2035, "age": 49}})
        assert i is not None and i.severity == "positive"

    def test_none_at_retirement(self):
        tl = [_mock(year=2070, goal_reached=True), _mock(year=2070, is_retirement=True)]
        assert _check_goal_reached_early(tl, {"goal_year": {"year": 2070, "age": 84}}) is None


class TestGoodSavingsRate:
    def test_positive(self):
        i = _check_good_savings_rate([_mock(net_annual=Decimal("40000"))], {}, [{"vehicle_key": "pea", "monthly": 1000, "balance": 30000}])
        assert i is not None and i.severity == "positive"

    def test_none_below_25(self):
        assert _check_good_savings_rate([_mock(net_annual=Decimal("40000"))], {}, [{"vehicle_key": "pea", "monthly": 400, "balance": 10000}]) is None


# ── Integration tests ────────────────────────────────────────────────────────

class TestGenerateInsights:
    def test_returns_up_to_5(self):
        """Full pipeline with accumulation + retirement + wealth exhaustion."""
        tl = [_mock(year=2026 + i, age=40 + i, kid_expenses=Decimal("3000") if i < 15 else Decimal("0"), total_wealth=Decimal(str(50000 + i * 5000)))
              for i in range(30)]
        # Add retirement years with negative net + shortfall
        for i in range(10):
            tl.append(_mock(year=2056 + i, age=70 + i, is_retirement=True,
                            net_annual=Decimal("-10000"), total_wealth=Decimal(str(max(0, 200000 - i * 25000))),
                            total_income=Decimal("0"), total_outgoing=Decimal("30000")))
        summary = {"wealth_exhaustion_age": 78, "goal_year": None, "final_wealth": "50000"}
        profile = {"growth_rate": 0.01}
        allocs = [{"vehicle_key": "livret_a", "monthly": 50, "balance": 2000}]
        insights = generate_insights(tl, summary, profile, allocs)
        assert 1 <= len(insights) <= 5
        # Critical (wealth exhaustion) or negative_net should be first
        critical = [i for i in insights if i.severity == "critical"]
        assert len(critical) >= 1

    def test_empty_returns_empty(self):
        assert generate_insights([], {}, {}, []) == []

    def test_positive_scenario(self):
        tl = [_mock(net_annual=Decimal("60000"), total_wealth=Decimal("1000000"), passive_monthly=Decimal("3000"), goal_reached=True)]
        insights = generate_insights(tl, {"goal_year": {"year": 2035, "age": 49}}, {"growth_rate": 0.05},
                                      [{"vehicle_key": "pea", "monthly": 1500, "balance": 100000},
                                       {"vehicle_key": "av_uc", "monthly": 500, "balance": 50000}])
        positive = [i for i in insights if i.severity == "positive"]
        assert len(positive) >= 1