"""Tests for TASK-7.15: Prescriptive Life-Phase Intelligence."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.calculations.advice import generate_advice, Advice


class TestGenerateAdvice:
    """Test the prescriptive advice engine rules."""

    def test_redirect_loan_payment(self):
        """Loan ending → advice to redirect freed payment."""
        expense_events = [
            {
                "category": "loan_end",
                "event": "Crédit immo terminé",
                "impact_monthly": "-590",
                "year": 2035,
            }
        ]
        profile = {"status": "ae", "target_retirement_age": 65}
        investments = {}

        result = generate_advice(
            timeline=[],
            lifecycle_alerts=[],
            expense_events=expense_events,
            profile=profile,
            investments=investments,
        )

        assert len(result) == 1
        assert result[0].id == "redirect_loan_2035"
        assert result[0].category == "savings"
        assert result[0].priority == 1
        assert "590" in result[0].title
        assert result[0].link_to == "/savings"

    def test_kid_independence_advice(self):
        """Kid becoming independent → advice to reduce budget."""
        expense_events = [
            {
                "category": "kid_independence",
                "event": "Emma indépendant(e)",
                "impact_monthly": "-320",
                "year": 2040,
            }
        ]
        profile = {"status": "ae", "target_retirement_age": 67}
        investments = {}

        result = generate_advice(
            timeline=[],
            lifecycle_alerts=[],
            expense_events=expense_events,
            profile=profile,
            investments=investments,
        )

        assert len(result) == 1
        assert result[0].category == "expenses"
        assert result[0].priority == 3
        assert result[0].link_to == "/expenses"

    def test_livret_a_ceiling_advice(self):
        """Livret A at ceiling → advice to redirect."""
        investments = {
            "livret_a": {
                "existing_balance": "25000",
                "monthly_contribution": "500",
            }
        }
        profile = {"status": "ae", "target_retirement_age": 65}

        result = generate_advice(
            timeline=[],
            lifecycle_alerts=[],
            expense_events=[],
            profile=profile,
            investments=investments,
        )

        assert len(result) >= 1
        ceiling_advice = [a for a in result if a.id == "livret_a_ceiling"]
        assert len(ceiling_advice) == 1
        assert "500" in ceiling_advice[0].title

    def test_livret_a_below_ceiling_no_advice(self):
        """Livret A at ceiling → advice to redirect."""
        investments = {
            "livret_a": {
                "existing_balance": "10000",
                "monthly_contribution": "200",
            }
        }
        profile = {"status": "ae", "target_retirement_age": 65}

        result = generate_advice(
            timeline=[],
            lifecycle_alerts=[],
            expense_events=[],
            profile=profile,
            investments=investments,
        )

        ceiling_advice = [a for a in result if a.id == "livret_a_ceiling"]
        assert len(ceiling_advice) == 0

    def test_no_pea_allocation_advice(self):
        """Saving but not in PEA → suggest PEA."""
        investments = {
            "livret_a": {
                "existing_balance": "5000",
                "monthly_contribution": "300",
            }
        }
        profile = {"status": "ae", "target_retirement_age": 65}

        result = generate_advice(
            timeline=[],
            lifecycle_alerts=[],
            expense_events=[],
            profile=profile,
            investments=investments,
        )

        assert len(result) >= 1
        no_pea = [a for a in result if a.id == "no_pea"]
        assert len(no_pea) == 1
        assert no_pea[0].category == "savings"

    def test_has_pea_no_advice(self):
        """Already saving in PEA → no PEA advice."""
        investments = {
            "livret_a": {
                "existing_balance": "5000",
                "monthly_contribution": "300",
            },
            "pea": {
                "existing_balance": "10000",
                "monthly_contribution": "200",
            },
        }
        profile = {"status": "ae", "target_retirement_age": 65}

        result = generate_advice(
            timeline=[],
            lifecycle_alerts=[],
            expense_events=[],
            profile=profile,
            investments=investments,
        )

        no_pea = [a for a in result if a.id == "no_pea"]
        assert len(no_pea) == 0

    def test_high_expense_ratio_advice(self):
        """Expenses >90% of income → advice to cut costs."""
        from app.calculations.projection import YearProjection

        timeline = [
            YearProjection(
                year=2026,
                age=40,
                total_income=Decimal("3000"),
                total_outgoing=Decimal("2850"),
                is_retirement=False,
            ),
        ]
        profile = {"status": "ae", "target_retirement_age": 65}
        investments = {}

        result = generate_advice(
            timeline=timeline,
            lifecycle_alerts=[],
            expense_events=[],
            profile=profile,
            investments=investments,
        )

        high_exp = [a for a in result if a.id == "high_expense_ratio"]
        assert len(high_exp) == 1
        assert high_exp[0].link_to == "/expenses"

    def test_cc_opportunity_advice(self):
        """EIRL/EURL with spouse but no CC → suggest CC."""
        profile = {"status": "eirl", "target_retirement_age": 65,
                   "has_spouse": True, "spouse_is_cc": False}
        investments = {}

        result = generate_advice(
            timeline=[],
            lifecycle_alerts=[],
            expense_events=[],
            profile=profile,
            investments=investments,
        )

        cc_advice = [a for a in result if a.id == "cc_opportunity"]
        assert len(cc_advice) == 1
        assert cc_advice[0].category == "status"

    def test_cc_already_active_no_advice(self):
        """Already has CC → no CC advice."""
        profile = {"status": "eirl", "target_retirement_age": 65,
                   "has_spouse": True, "spouse_is_cc": True}
        investments = {}

        result = generate_advice(
            timeline=[],
            lifecycle_alerts=[],
            expense_events=[],
            profile=profile,
            investments=investments,
        )

        cc_advice = [a for a in result if a.id == "cc_opportunity"]
        assert len(cc_advice) == 0

    def test_ae_status_no_cc_advice(self):
        """AE status → no CC advice (CC not applicable)."""
        profile = {"status": "ae", "target_retirement_age": 65,
                   "has_spouse": True, "spouse_is_cc": False}
        investments = {}

        result = generate_advice(
            timeline=[],
            lifecycle_alerts=[],
            expense_events=[],
            profile=profile,
            investments=investments,
        )

        cc_advice = [a for a in result if a.id == "cc_opportunity"]
        assert len(cc_advice) == 0

    def test_empty_data_returns_empty(self):
        """Empty input → no advice (no crashes)."""
        result = generate_advice(
            timeline=[],
            lifecycle_alerts=[],
            expense_events=[],
            profile={"status": "ae", "target_retirement_age": 65},
            investments={},
        )
        assert result == []

    def test_priority_sorting(self):
        """Advice items sorted by priority (critical first)."""
        investments = {
            "livret_a": {
                "existing_balance": "25000",
                "monthly_contribution": "500",
            }
        }

        result = generate_advice(
            timeline=[],
            lifecycle_alerts=[],
            expense_events=[
                {
                    "category": "kid_independence",
                    "event": "Enfant indépendant",
                    "impact_monthly": "-200",
                    "year": 2040,
                }
            ],
            profile={"status": "ae", "target_retirement_age": 65},
            investments=investments,
        )

        priorities = [a.priority for a in result]
        assert priorities == sorted(priorities)  # ascending: 1 before 2 before 3