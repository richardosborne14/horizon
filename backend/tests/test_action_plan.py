"""Tests for TASK-7.17: Monthly Action Plan Dashboard."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.calculations.action_plan import generate_action_plan, MonthlyAction


class TestGenerateActionPlan:
    """Test the monthly action plan generator rules."""

    def test_livret_a_ceiling_action(self):
        """Livret A at ceiling → redirect action."""
        investments = {
            "livret_a": {
                "existing_balance": "25000",
                "monthly_contribution": "500",
            }
        }
        profile = {"cesu_annual": "0"}
        income_sources: list[dict] = []
        loans: list[dict] = []

        result = generate_action_plan(
            profile=profile,
            investments=investments,
            income_sources=income_sources,
            loans=loans,
            advice=[],
            current_date=date(2026, 6, 1),
        )

        redirect = [a for a in result if a.id == "redirect_livret_a"]
        assert len(redirect) == 1
        assert redirect[0].priority == 1
        assert redirect[0].amount == Decimal("500")

    def test_client_ending_soon_action(self):
        """Client ending in 2 months → prospecting action."""
        investments = {}
        profile = {"cesu_annual": "0"}
        income_sources = [
            {
                "id": 1,
                "label": "Client ACME",
                "amount": "3000",
                "frequency": "monthly",
                "end_date": "2026-08-01",
                "confidence": "high",
                "is_active": True,
            }
        ]
        loans: list[dict] = []

        result = generate_action_plan(
            profile=profile,
            investments=investments,
            income_sources=income_sources,
            loans=loans,
            advice=[],
            current_date=date(2026, 6, 1),
        )

        client_actions = [a for a in result if a.id.startswith("client_ending_")]
        assert len(client_actions) == 1
        assert client_actions[0].priority == 1
        assert client_actions[0].amount == Decimal("3000")

    def test_client_ending_far_future_no_action(self):
        """Client ending in 12 months → no action yet."""
        investments = {}
        profile = {"cesu_annual": "0"}
        income_sources = [
            {
                "id": 1,
                "label": "Client ACME",
                "amount": "3000",
                "frequency": "monthly",
                "end_date": "2027-06-01",
                "confidence": "high",
                "is_active": True,
            }
        ]
        loans: list[dict] = []

        result = generate_action_plan(
            profile=profile,
            investments=investments,
            income_sources=income_sources,
            loans=loans,
            advice=[],
            current_date=date(2026, 6, 1),
        )

        client_actions = [a for a in result if a.id.startswith("client_ending_")]
        assert len(client_actions) == 0

    def test_loan_ending_soon_action(self):
        """Loan ending in 4 months → plan redirect."""
        investments = {}
        profile = {"cesu_annual": "0"}
        income_sources: list[dict] = []
        loans = [
            {
                "id": 100,
                "label": "Crédit auto",
                "monthly_payment": "350",
                "end_date": "2026-10-01",
            }
        ]

        result = generate_action_plan(
            profile=profile,
            investments=investments,
            income_sources=income_sources,
            loans=loans,
            advice=[],
            current_date=date(2026, 6, 1),
        )

        loan_actions = [a for a in result if a.id.startswith("loan_ending_")]
        assert len(loan_actions) == 1
        assert loan_actions[0].amount == Decimal("350")

    def test_no_savings_action(self):
        """Zero savings → critical action to start saving."""
        investments = {}
        profile = {"cesu_annual": "0"}
        income_sources: list[dict] = []
        loans: list[dict] = []

        result = generate_action_plan(
            profile=profile,
            investments=investments,
            income_sources=income_sources,
            loans=loans,
            advice=[],
            current_date=date(2026, 6, 1),
        )

        no_sav = [a for a in result if a.id == "no_savings"]
        assert len(no_sav) == 1
        assert no_sav[0].priority == 1
        assert no_sav[0].amount == Decimal("100")

    def test_cesu_opportunity_action(self):
        """CESU not used → opportunity action."""
        investments = {}
        profile = {"cesu_annual": "0"}
        income_sources: list[dict] = []
        loans: list[dict] = []

        result = generate_action_plan(
            profile=profile,
            investments=investments,
            income_sources=income_sources,
            loans=loans,
            advice=[],
            current_date=date(2026, 6, 1),
        )

        cesu_actions = [a for a in result if a.id == "cesu_opportunity"]
        assert len(cesu_actions) == 1
        assert cesu_actions[0].priority == 3

    def test_cesu_already_used_no_action(self):
        """CESU already used → no CESU action."""
        investments = {}
        profile = {"cesu_annual": "2000"}
        income_sources: list[dict] = []
        loans: list[dict] = []

        result = generate_action_plan(
            profile=profile,
            investments=investments,
            income_sources=income_sources,
            loans=loans,
            advice=[],
            current_date=date(2026, 6, 1),
        )

        cesu_actions = [a for a in result if a.id == "cesu_opportunity"]
        assert len(cesu_actions) == 0

    def test_per_yearend_action_in_october(self):
        """October → PER year-end action appears."""
        investments = {}
        profile = {"cesu_annual": "0"}
        income_sources: list[dict] = []
        loans: list[dict] = []

        result = generate_action_plan(
            profile=profile,
            investments=investments,
            income_sources=income_sources,
            loans=loans,
            advice=[],
            current_date=date(2026, 10, 15),
        )

        per_actions = [a for a in result if a.id == "per_yearend"]
        assert len(per_actions) == 1

    def test_per_yearend_no_action_in_june(self):
        """June → no PER year-end action."""
        investments = {}
        profile = {"cesu_annual": "0"}
        income_sources: list[dict] = []
        loans: list[dict] = []

        result = generate_action_plan(
            profile=profile,
            investments=investments,
            income_sources=income_sources,
            loans=loans,
            advice=[],
            current_date=date(2026, 6, 1),
        )

        per_actions = [a for a in result if a.id == "per_yearend"]
        assert len(per_actions) == 0

    def test_per_already_contributing_no_action(self):
        """Already contributing to PER → no year-end reminder."""
        investments = {
            "per": {
                "existing_balance": "5000",
                "monthly_contribution": "200",
            }
        }
        profile = {"cesu_annual": "0"}
        income_sources: list[dict] = []
        loans: list[dict] = []

        result = generate_action_plan(
            profile=profile,
            investments=investments,
            income_sources=income_sources,
            loans=loans,
            advice=[],
            current_date=date(2026, 11, 1),
        )

        per_actions = [a for a in result if a.id == "per_yearend"]
        assert len(per_actions) == 0

    def test_priority_sorting(self):
        """Actions sorted by priority."""
        investments = {
            "livret_a": {
                "existing_balance": "25000",
                "monthly_contribution": "500",
            }
        }
        profile = {"cesu_annual": "0"}
        income_sources: list[dict] = []
        loans: list[dict] = []

        result = generate_action_plan(
            profile=profile,
            investments=investments,
            income_sources=income_sources,
            loans=loans,
            advice=[],
            current_date=date(2026, 6, 1),
        )

        priorities = [a.priority for a in result]
        assert priorities == sorted(priorities)

    def test_max_10_actions(self):
        """Capped at 10 actions max."""
        # Generate many income sources to test cap
        investments = {}
        profile = {"cesu_annual": "0"}
        income_sources: list[dict] = [
            {
                "id": i,
                "label": f"Client {i}",
                "amount": "2000",
                "frequency": "monthly",
                "end_date": f"2026-07-01",
                "confidence": "high",
                "is_active": True,
            }
            for i in range(20)
        ]
        loans: list[dict] = []

        result = generate_action_plan(
            profile=profile,
            investments=investments,
            income_sources=income_sources,
            loans=loans,
            advice=[],
            current_date=date(2026, 6, 1),
        )

        assert len(result) <= 10