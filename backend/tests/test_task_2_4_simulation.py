"""
Tests for Task 2.4 — Quick Monthly Profitability Simulation.

Covers:
  - Pure calculation function (compute_simulation)
  - API endpoint POST /api/calculations/simulation
  - Negative input validation
  - CA = 0 edge case (no percentages)
  - Dirigeant salary included / excluded
  - TVA calculations
  - Benchmark data present in response

All monetary comparisons use string comparison to avoid Decimal rounding issues.
"""

import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.calculations.simulation import compute_simulation, BENCHMARKS


# ── Pure calculation tests (no HTTP) ─────────────────────────────────────────


class TestComputeSimulation:
    """Unit tests for compute_simulation() — no DB, no HTTP."""

    def test_profitable_without_dirigeant(self):
        """Standard profitable month: CA covers all costs."""
        result = compute_simulation(
            ca_mensuel_ttc=Decimal("15000"),
            total_salaires_charges=Decimal("6000"),
            total_depenses_ttc=Decimal("3000"),
        )
        # point_mort_salon = 6000 + 3000 = 9000
        assert result.point_mort_salon == Decimal("9000.00")
        # No dirigeant → point_mort_final = point_mort_salon
        assert result.point_mort_final == Decimal("9000.00")
        assert result.point_mort_dirigeant is None
        assert result.dirigeant_total_cost is None
        # cash_flow = 15000 - 9000 = 6000
        assert result.cash_flow == Decimal("6000.00")
        assert result.is_profitable is True

    def test_deficit_scenario(self):
        """Month where costs exceed revenue."""
        result = compute_simulation(
            ca_mensuel_ttc=Decimal("5000"),
            total_salaires_charges=Decimal("4000"),
            total_depenses_ttc=Decimal("2000"),
        )
        assert result.point_mort_salon == Decimal("6000.00")
        assert result.cash_flow == Decimal("-1000.00")
        assert result.is_profitable is False

    def test_with_dirigeant_salary(self):
        """Owner salary adds × 1.45 to point mort."""
        result = compute_simulation(
            ca_mensuel_ttc=Decimal("15000"),
            total_salaires_charges=Decimal("6000"),
            total_depenses_ttc=Decimal("3000"),
            salaire_net_dirigeant=Decimal("2000"),
        )
        # dirigeant_total_cost = 2000 × 1.45 = 2900
        assert result.dirigeant_total_cost == Decimal("2900.00")
        # point_mort_dirigeant = 9000 + 2900 = 11900
        assert result.point_mort_dirigeant == Decimal("11900.00")
        assert result.point_mort_final == Decimal("11900.00")
        # cash_flow = 15000 - 11900 = 3100
        assert result.cash_flow == Decimal("3100.00")
        assert result.is_profitable is True

    def test_dirigeant_makes_unprofitable(self):
        """Adding owner salary tips the business into deficit."""
        result = compute_simulation(
            ca_mensuel_ttc=Decimal("12000"),
            total_salaires_charges=Decimal("6000"),
            total_depenses_ttc=Decimal("3000"),
            salaire_net_dirigeant=Decimal("3500"),
        )
        # point_mort_salon = 9000
        # dirigeant_cost = 3500 × 1.45 = 5075
        assert result.dirigeant_total_cost == Decimal("5075.00")
        # point_mort_dirigeant = 14075
        assert result.point_mort_dirigeant == Decimal("14075.00")
        # cash_flow = 12000 - 14075 = -2075
        assert result.cash_flow == Decimal("-2075.00")
        assert result.is_profitable is False

    def test_tva_calculation(self):
        """TVA is correctly calculated from TTC amounts."""
        result = compute_simulation(
            ca_mensuel_ttc=Decimal("12000"),
            total_salaires_charges=Decimal("5000"),
            total_depenses_ttc=Decimal("3000"),
        )
        # tva_estimee = 12000 - 12000/1.2 = 12000 - 10000 = 2000
        assert result.tva_estimee == Decimal("2000.00")
        # tva_payee = 3000 - 3000/1.2 = 3000 - 2500 = 500
        assert result.tva_payee_achats == Decimal("500.00")
        # tva_a_payer = 2000 - 500 = 1500
        assert result.tva_a_payer == Decimal("1500.00")

    def test_breakdown_percentages(self):
        """Breakdown percentages are correctly calculated."""
        result = compute_simulation(
            ca_mensuel_ttc=Decimal("10000"),
            total_salaires_charges=Decimal("5500"),
            total_depenses_ttc=Decimal("1500"),
        )
        # pct_salaires = 5500 / 10000 = 0.55
        assert result.pct_salaires == Decimal("0.5500")
        # pct_depenses = 1500 / 10000 = 0.15
        assert result.pct_depenses == Decimal("0.1500")
        # pct_marge = 3000 / 10000 = 0.30
        assert result.pct_marge == Decimal("0.3000")

    def test_zero_ca_no_percentages(self):
        """When CA = 0, percentages are None (no division by zero)."""
        result = compute_simulation(
            ca_mensuel_ttc=Decimal("0"),
            total_salaires_charges=Decimal("3000"),
            total_depenses_ttc=Decimal("1000"),
        )
        assert result.pct_salaires is None
        assert result.pct_depenses is None
        assert result.pct_marge is None
        assert result.cash_flow == Decimal("-4000.00")
        assert result.is_profitable is False

    def test_benchmarks_present(self):
        """Benchmarks dict is populated with expected keys."""
        result = compute_simulation(
            ca_mensuel_ttc=Decimal("10000"),
            total_salaires_charges=Decimal("5000"),
            total_depenses_ttc=Decimal("2000"),
        )
        assert "salaires" in result.benchmarks
        assert "depenses" in result.benchmarks
        assert "marge" in result.benchmarks
        assert result.benchmarks["salaires"]["repere"] == Decimal("0.55")
        assert result.benchmarks["salaires"]["ideal"] == Decimal("0.40")

    def test_negative_input_raises(self):
        """Negative inputs raise ValueError."""
        with pytest.raises(ValueError, match="ca_mensuel_ttc must be >= 0"):
            compute_simulation(
                ca_mensuel_ttc=Decimal("-1"),
                total_salaires_charges=Decimal("0"),
                total_depenses_ttc=Decimal("0"),
            )

    def test_zero_dirigeant_treated_as_none(self):
        """Dirigeant salary = 0 should not affect point mort (treated as not provided)."""
        result_none = compute_simulation(
            ca_mensuel_ttc=Decimal("10000"),
            total_salaires_charges=Decimal("5000"),
            total_depenses_ttc=Decimal("2000"),
        )
        result_zero = compute_simulation(
            ca_mensuel_ttc=Decimal("10000"),
            total_salaires_charges=Decimal("5000"),
            total_depenses_ttc=Decimal("2000"),
            salaire_net_dirigeant=Decimal("0"),
        )
        assert result_none.point_mort_final == result_zero.point_mort_final
        assert result_none.cash_flow == result_zero.cash_flow


# ── API endpoint tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_simulation_endpoint_requires_auth():
    """Unauthenticated request should return 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/calculations/simulation",
            json={
                "ca_mensuel_ttc": "15000",
                "total_salaires_charges": "6000",
                "total_depenses_ttc": "3000",
            },
        )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_simulation_endpoint_authenticated():
    """Authenticated request returns correct profitability result."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register + login
        email = "sim_test@example.com"
        await client.post("/api/auth/register", json={
            "email": email, "password": "Password123!", "name": "Sim Test",
        })
        await client.post("/api/auth/login", json={"email": email, "password": "Password123!"})

        res = await client.post(
            "/api/calculations/simulation",
            json={
                "ca_mensuel_ttc": "15000",
                "total_salaires_charges": "6000",
                "total_depenses_ttc": "3000",
                "salaire_net_dirigeant": "2000",
            },
        )
    assert res.status_code == 200
    data = res.json()
    assert data["point_mort_salon"] == "9000.00"
    assert data["dirigeant_total_cost"] == "2900.00"
    assert data["point_mort_dirigeant"] == "11900.00"
    assert data["cash_flow"] == "3100.00"
    assert data["is_profitable"] is True
    # tva_estimee = 15000 - 15000/1.2 = 15000 - 12500 = 2500
    assert data["tva_estimee"] == "2500.00"
    assert "salaires" in data["benchmarks"]


@pytest.mark.asyncio
async def test_simulation_endpoint_without_dirigeant():
    """Simulation without owner salary returns salon-only point mort."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = "sim_test2@example.com"
        await client.post("/api/auth/register", json={
            "email": email, "password": "Password123!", "name": "Sim Test 2",
        })
        await client.post("/api/auth/login", json={"email": email, "password": "Password123!"})

        res = await client.post(
            "/api/calculations/simulation",
            json={
                "ca_mensuel_ttc": "10000",
                "total_salaires_charges": "5500",
                "total_depenses_ttc": "1500",
            },
        )
    assert res.status_code == 200
    data = res.json()
    assert data["point_mort_dirigeant"] is None
    assert data["point_mort_final"] == "7000.00"
    assert data["cash_flow"] == "3000.00"
    assert data["pct_salaires"] == "0.5500"
    assert data["pct_depenses"] == "0.1500"


@pytest.mark.asyncio
async def test_simulation_endpoint_negative_values_rejected():
    """Negative values should be rejected with 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = "sim_test3@example.com"
        await client.post("/api/auth/register", json={
            "email": email, "password": "Password123!", "name": "Sim Test 3",
        })
        await client.post("/api/auth/login", json={"email": email, "password": "Password123!"})

        res = await client.post(
            "/api/calculations/simulation",
            json={
                "ca_mensuel_ttc": "-100",
                "total_salaires_charges": "5000",
                "total_depenses_ttc": "2000",
            },
        )
    assert res.status_code == 422
