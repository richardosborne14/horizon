"""
Tests for TASK-2.12.3: Welcome routing — primary_route() and landing-route endpoint.

Covers:
  - primary_route([]) → /dashboard
  - primary_route(['compta', 'simulation']) → /compta
  - primary_route(['simulation']) → /dashboard
  - primary_route(['unknown_tool']) → /dashboard
  - primary_route(['fiches_salaire']) → /fiches-salaire
  - primary_route(['prix']) → /prix
  - primary_route(['pilotage']) → /pilotage
  - primary_route(['taxes', 'compta']) → /mes-economies  (taxes route)
  - primary_route(['calculateurs']) → /calculateurs
  - primary_route(None) → /dashboard
  - GET /api/users/me/landing-route — returns {route: '/dashboard'} for default user
"""

import pytest
from contextlib import asynccontextmanager
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.onboarding import primary_route, TOOL_TO_ROUTE

SMOKE_EMAIL = "smoketest@comcoi.fr"
SMOKE_PASSWORD = "Password123!"


@asynccontextmanager
async def _login(email: str = SMOKE_EMAIL, password: str = SMOKE_PASSWORD):
    """Return an authenticated AsyncClient for the smoke-test user."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, f"Login failed: {r.text}"
        yield client


# ── Unit tests for primary_route() ────────────────────────────────────────────

class TestPrimaryRoute:
    """Unit tests for the primary_route() helper function."""

    def test_empty_list_returns_dashboard(self):
        """primary_route([]) must fall back to /dashboard."""
        assert primary_route([]) == "/dashboard"

    def test_none_returns_dashboard(self):
        """primary_route(None) must fall back to /dashboard (defensive guard)."""
        assert primary_route(None) == "/dashboard"  # type: ignore[arg-type]

    def test_compta_first_returns_compta(self):
        """compta tool → /compta (Eric's primary use case)."""
        assert primary_route(["compta", "simulation"]) == "/compta"

    def test_simulation_returns_dashboard(self):
        """simulation maps to /dashboard (surfaces simulation prominently there)."""
        assert primary_route(["simulation"]) == "/dashboard"

    def test_unknown_tool_returns_dashboard(self):
        """Unrecognised tool IDs must fall back to /dashboard."""
        assert primary_route(["unknown_tool"]) == "/dashboard"

    def test_fiches_salaire_returns_route(self):
        """fiches_salaire → /fiches-salaire."""
        assert primary_route(["fiches_salaire"]) == "/fiches-salaire"

    def test_prix_returns_route(self):
        """prix → /prix."""
        assert primary_route(["prix"]) == "/prix"

    def test_pilotage_returns_route(self):
        """pilotage → /pilotage."""
        assert primary_route(["pilotage"]) == "/pilotage"

    def test_taxes_returns_mes_economies(self):
        """taxes tool → /mes-economies."""
        assert primary_route(["taxes"]) == "/mes-economies"

    def test_calculateurs_returns_route(self):
        """calculateurs → /calculateurs."""
        assert primary_route(["calculateurs"]) == "/calculateurs"

    def test_blog_returns_route(self):
        """blog → /blog."""
        assert primary_route(["blog"]) == "/blog"

    def test_first_recognised_wins(self):
        """First recognised tool in the list wins — others are ignored."""
        assert primary_route(["unknown", "compta", "pilotage"]) == "/compta"

    def test_order_matters_simulation_before_compta(self):
        """simulation before compta → /dashboard (simulation maps to /dashboard)."""
        assert primary_route(["simulation", "compta"]) == "/dashboard"

    def test_all_unknown_returns_dashboard(self):
        """All-unknown list falls back to /dashboard."""
        assert primary_route(["foo", "bar", "baz"]) == "/dashboard"


# ── Mapping completeness check ────────────────────────────────────────────────

class TestToolToRouteMapping:
    """Ensure TOOL_TO_ROUTE covers all expected tools and returns valid routes."""

    def test_all_routes_start_with_slash(self):
        """Every route in TOOL_TO_ROUTE must start with '/'."""
        for tool, route in TOOL_TO_ROUTE.items():
            assert route.startswith("/"), f"Route for '{tool}' does not start with '/': {route!r}"

    def test_expected_tools_present(self):
        """All tools that Eric's onboarding can produce must have a mapping."""
        required = {"compta", "fiches_salaire", "prix", "pilotage", "simulation",
                    "calculateurs", "blog", "taxes"}
        missing = required - set(TOOL_TO_ROUTE.keys())
        assert not missing, f"Tools missing from TOOL_TO_ROUTE: {missing}"


# ── HTTP endpoint test ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_landing_route_endpoint_authenticated():
    """
    GET /api/users/me/landing-route returns {route: string starting with '/'} for
    the smoke-test user. We don't assert /dashboard specifically since the
    smoketest user's preferred_tools may vary between environments.
    """
    async with _login() as client:
        res = await client.get("/api/users/me/landing-route")
        assert res.status_code == 200
        data = res.json()
        assert "route" in data
        assert data["route"].startswith("/"), f"Route must start with '/': {data['route']!r}"


@pytest.mark.asyncio
async def test_landing_route_endpoint_unauthenticated():
    """GET /api/users/me/landing-route without auth must return 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/users/me/landing-route")
        assert res.status_code == 401
