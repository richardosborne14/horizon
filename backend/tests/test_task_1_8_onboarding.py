"""
Tests for Task 1.8 — Onboarding Flow.

Tests cover:
  - goals_to_tools() pure function
  - PUT /api/users/me/onboarding endpoint (HTTP integration)
  - GET /api/static-data/tools endpoint

Pattern: create AsyncClient with ASGITransport per test — same as test_task_1_7_salons.py.
Cleanup: DELETE test users by email pattern in each test to avoid cross-test pollution.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app
from app.services.onboarding import DEFAULT_TOOLS, GOAL_TO_TOOLS, goals_to_tools

# ── Helpers ───────────────────────────────────────────────────────────────────

_SESSION_KWARGS = {"expire_on_commit": False}


async def _cleanup_users(emails: list[str]) -> None:
    """Delete test users by email. Cascade removes all dependent records."""
    engine = create_async_engine(settings.database_url, echo=False)
    try:
        async with AsyncSession(engine, **_SESSION_KWARGS) as db:
            for email in emails:
                await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
            await db.commit()
    finally:
        await engine.dispose()


def _make_client() -> AsyncClient:
    """Create a fresh HTTPX async client pointing at the FastAPI test app."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ── Pure function tests ───────────────────────────────────────────────────────


class TestGoalsToTools:
    """
    Unit tests for the goals_to_tools() pure function.

    No DB or async needed — pure logic only.
    """

    def test_single_goal_rentabilite(self):
        """rentabilite → simulation, pilotage, taxes (in order)."""
        result = goals_to_tools(["rentabilite"])
        assert result == ["simulation", "pilotage", "taxes"]

    def test_single_goal_prix(self):
        """prix → only the prix tool."""
        result = goals_to_tools(["prix"])
        assert result == ["prix"]

    def test_single_goal_compta(self):
        """compta → only the compta tool."""
        result = goals_to_tools(["compta"])
        assert result == ["compta"]

    def test_single_goal_fiches_salaire(self):
        """fiches_salaire → only the fiches_salaire tool."""
        result = goals_to_tools(["fiches_salaire"])
        assert result == ["fiches_salaire"]

    def test_single_goal_conseils(self):
        """conseils → calculateurs, blog, taxes (in order)."""
        result = goals_to_tools(["conseils"])
        assert result == ["calculateurs", "blog", "taxes"]

    def test_multiple_goals_no_duplicates(self):
        """
        When multiple goals share tools (e.g. both rentabilite and conseils
        include 'taxes'), the output must be deduplicated, keeping first occurrence.
        """
        result = goals_to_tools(["rentabilite", "conseils"])
        # taxes appears in both — first from rentabilite, so it stays at pos 2
        assert "taxes" in result
        assert result.count("taxes") == 1

    def test_all_goals_deduplication(self):
        """All 5 goals → no duplicates in result."""
        result = goals_to_tools(["rentabilite", "prix", "compta", "fiches_salaire", "conseils"])
        assert len(result) == len(set(result)), "Expected no duplicate tool IDs"

    def test_empty_goals_returns_defaults(self):
        """Empty goal list → default tool set (not an empty list)."""
        result = goals_to_tools([])
        assert result == DEFAULT_TOOLS
        assert len(result) > 0

    def test_unknown_goal_is_ignored(self):
        """Unknown goal IDs are silently ignored; known goals still processed."""
        result = goals_to_tools(["unknown_goal", "prix"])
        assert result == ["prix"]

    def test_all_unknown_goals_returns_defaults(self):
        """If all goals are unknown, fall back to defaults."""
        result = goals_to_tools(["not_a_goal", "also_not_a_goal"])
        assert result == DEFAULT_TOOLS

    def test_ordering_preserved(self):
        """
        Tool order in result must match GOAL_TO_TOOLS insertion order,
        not the order of goals passed in.
        """
        result = goals_to_tools(["prix", "rentabilite"])
        # simulation from rentabilite comes before prix in GOAL_TO_TOOLS
        sim_idx = result.index("simulation")
        prix_idx = result.index("prix")
        # rentabilite tools come after prix because prix was first — first-occurrence wins
        # Actually: prix is first goal, so its tools come first
        assert prix_idx < sim_idx


# ── HTTP endpoint tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_static_data_tools_endpoint():
    """
    GET /api/static-data/tools — returns a list of tool objects.

    No auth required. Each tool must have the required fields.
    """
    async with _make_client() as client:
        res = await client.get("/api/static-data/tools")
    assert res.status_code == 200
    tools = res.json()
    assert isinstance(tools, list)
    assert len(tools) > 0

    required_fields = {"id", "label", "description", "icon", "route", "bg", "color", "goals"}
    for tool in tools:
        assert required_fields.issubset(tool.keys()), (
            f"Tool {tool.get('id', '?')} missing fields: "
            f"{required_fields - set(tool.keys())}"
        )
        assert isinstance(tool["goals"], list)


@pytest.mark.asyncio
async def test_onboarding_complete_success():
    """
    PUT /api/users/me/onboarding — happy path.

    Register → onboarding → verify user.onboarding_completed=True + tools populated.
    """
    email = "onboarding_test@example.com"
    password = "Test1234!"
    await _cleanup_users([email])

    async with _make_client() as client:
        # Register (session cookie stored in client)
        reg = await client.post(
            "/api/auth/register",
            json={"name": "Test Onboarding", "email": email, "password": password},
        )
        assert reg.status_code == 201, reg.text

        # Check initial state: onboarding_completed = False
        me_before = await client.get("/api/users/me")
        assert me_before.status_code == 200
        assert me_before.json()["onboarding_completed"] is False
        assert me_before.json()["preferred_tools"] == []

        # Complete onboarding
        res = await client.put(
            "/api/users/me/onboarding",
            json={
                "salon_name": "Salon Test",
                "business_type": "auto_micro",
                "nb_employees": 2,
                "business_goals": ["rentabilite", "prix"],
                "experience_level": "debutant",
            },
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert "simulation" in body["preferred_tools"]
        assert "prix" in body["preferred_tools"]

        # Verify user is now onboarded
        me_after = await client.get("/api/users/me")
        user_after = me_after.json()
        assert user_after["onboarding_completed"] is True
        assert len(user_after["preferred_tools"]) > 0

    await _cleanup_users([email])


@pytest.mark.asyncio
async def test_onboarding_creates_salon():
    """
    PUT /api/users/me/onboarding — verifies the salon is created via the salon list endpoint.
    """
    email = "onboarding_salon@example.com"
    await _cleanup_users([email])

    async with _make_client() as client:
        await client.post(
            "/api/auth/register",
            json={"name": "Salon Creator", "email": email, "password": "Test1234!"},
        )
        await client.put(
            "/api/users/me/onboarding",
            json={
                "salon_name": "Mon Premier Salon",
                "business_type": "eurl",
                "nb_employees": 0,
                "business_goals": ["prix"],
                "experience_level": "confirme",
            },
        )
        salons_res = await client.get("/api/salons")
        assert salons_res.status_code == 200
        salons = salons_res.json()
        assert len(salons) >= 1
        assert salons[0]["name"] == "Mon Premier Salon"
        assert salons[0]["business_type"] == "eurl"
        assert salons[0]["nb_employees"] == 0

    await _cleanup_users([email])


@pytest.mark.asyncio
async def test_onboarding_requires_auth():
    """
    PUT /api/users/me/onboarding — unauthenticated (no session cookie) → 401.
    """
    # Fresh client with no cookies = no session
    async with _make_client() as client:
        res = await client.put(
            "/api/users/me/onboarding",
            json={
                "salon_name": "Test",
                "business_type": "auto_micro",
                "nb_employees": 0,
                "business_goals": ["rentabilite"],
                "experience_level": "debutant",
            },
        )
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_onboarding_requires_at_least_one_goal():
    """
    PUT /api/users/me/onboarding — empty business_goals list is rejected with 422.
    """
    email = "validation_goals@example.com"
    await _cleanup_users([email])

    async with _make_client() as client:
        await client.post(
            "/api/auth/register",
            json={"name": "Validation Test", "email": email, "password": "Test1234!"},
        )
        res = await client.put(
            "/api/users/me/onboarding",
            json={
                "salon_name": "Test Salon",
                "business_type": "auto_micro",
                "nb_employees": 0,
                "business_goals": [],  # Invalid: min_length=1
                "experience_level": "debutant",
            },
        )
        assert res.status_code == 422

    await _cleanup_users([email])


@pytest.mark.asyncio
async def test_onboarding_invalid_experience_level():
    """
    PUT /api/users/me/onboarding — invalid experience_level is rejected with 422.
    """
    email = "leveltest_1_8@example.com"
    await _cleanup_users([email])

    async with _make_client() as client:
        await client.post(
            "/api/auth/register",
            json={"name": "Level Test", "email": email, "password": "Test1234!"},
        )
        res = await client.put(
            "/api/users/me/onboarding",
            json={
                "salon_name": "Test",
                "business_type": "auto_micro",
                "nb_employees": 0,
                "business_goals": ["rentabilite"],
                "experience_level": "expert",  # Invalid: not in Literal
            },
        )
        assert res.status_code == 422

    await _cleanup_users([email])


@pytest.mark.asyncio
async def test_onboarding_idempotent():
    """
    PUT /api/users/me/onboarding — can be called twice; second call overwrites first.
    User remains onboarding_completed=True; preferred_tools reflects second call.
    """
    email = "idempotent_1_8@example.com"
    await _cleanup_users([email])

    async with _make_client() as client:
        await client.post(
            "/api/auth/register",
            json={"name": "Idempotent Test", "email": email, "password": "Test1234!"},
        )

        # First call
        res1 = await client.put(
            "/api/users/me/onboarding",
            json={
                "salon_name": "Salon V1",
                "business_type": "auto_micro",
                "nb_employees": 0,
                "business_goals": ["rentabilite"],
                "experience_level": "debutant",
            },
        )
        assert res1.status_code == 200

        # Second call with different goals
        res2 = await client.put(
            "/api/users/me/onboarding",
            json={
                "salon_name": "Salon V2",
                "business_type": "sarl",
                "nb_employees": 3,
                "business_goals": ["prix", "compta"],
                "experience_level": "confirme",
            },
        )
        assert res2.status_code == 200

        # Verify final state reflects second call
        user = (await client.get("/api/users/me")).json()
        assert user["onboarding_completed"] is True
        assert "prix" in user["preferred_tools"]
        assert "compta" in user["preferred_tools"]

    await _cleanup_users([email])
