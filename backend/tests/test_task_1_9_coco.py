"""
Task 1.9: CoCo Infrastructure — Unit Tests

Tests for:
  - System prompt building (persona, profile, screen context, calculator state)
  - Individual tool executors (get_user_profile, get_screen_context, stubs)
  - Context assembly
  - Message history builder

These tests do NOT call the Anthropic API — the ReAct loop is integration-
tested separately when the stack is running. All tests are pure unit tests
using mocks and in-memory objects.
"""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.coco_prompts import (
    build_system_prompt,
    build_public_system_prompt,
    _build_profile_section,
    _build_screen_section,
    _screen_to_label,
)
from app.services.coco_tools import (
    TOOL_DEFINITIONS,
    TOOL_UI_LABELS,
    call_tool,
)
from app.services.coco import _build_message_history


# ── System Prompt Tests ────────────────────────────────────────────────────────

class TestBuildSystemPrompt:
    """Tests for the system prompt builder."""

    def test_build_system_prompt_base_only(self):
        """Without any profile or context, should return the core CoCo persona."""
        prompt = build_system_prompt()
        assert "CoCo" in prompt
        assert "Communauté Coiffure" in prompt
        assert "français" in prompt.lower() or "french" in prompt.lower() or "français" in prompt

    def test_build_system_prompt_has_language_rule(self):
        """System prompt must contain an explicit French language rule near the top."""
        prompt = build_system_prompt()
        # The language rule block should appear before other sections
        assert "TOUJOURS" in prompt
        assert "français" in prompt
        # Language rule must appear before the role section
        lang_pos = prompt.index("TOUJOURS")
        role_pos = prompt.index("Ton rôle")
        assert lang_pos < role_pos, "Language rule must appear before the role section"

    def test_build_system_prompt_with_full_profile(self):
        """Should include all profile fields when profile is provided."""
        profile = {
            "user_name": "Marie Dupont",
            "salon_name": "Salon Élégance",
            "experience_level": "debutant",
            "business_goals": ["comprendre_rentabilite", "fixer_prix"],
            "interests": ["simulation", "prix"],
            "profile_notes": {"preferred_tone": "simple"},
        }
        prompt = build_system_prompt(user_profile=profile)

        assert "Marie Dupont" in prompt
        assert "Salon Élégance" in prompt
        assert "debutant" in prompt
        assert "comprendre_rentabilite" in prompt
        assert "simulation" in prompt

    def test_build_system_prompt_experience_debutant_adapts_language(self):
        """Debutant experience level should add simplification hint to prompt."""
        profile = {"experience_level": "debutant", "user_name": "Test"}
        prompt = build_system_prompt(user_profile=profile)
        # The debutant hint mentions simple explanations
        assert "simple" in prompt.lower() or "analogies" in prompt.lower()

    def test_build_system_prompt_experience_confirme(self):
        """Confirmé level should indicate advanced vocabulary is ok."""
        profile = {"experience_level": "confirme", "user_name": "Test"}
        prompt = build_system_prompt(user_profile=profile)
        assert "confirmé" in prompt.lower() or "confirme" in prompt.lower() or "comptable" in prompt.lower()

    def test_build_system_prompt_with_screen_context(self):
        """Should include the current screen and its French label in the prompt."""
        # Use the correct route (no /app/ prefix — SvelteKit group routes are transparent)
        prompt = build_system_prompt(screen_context="/simulation")
        assert "/simulation" in prompt
        assert "Simulation de rentabilité" in prompt

    def test_build_system_prompt_with_focused_element(self):
        """Should include the focused element description."""
        prompt = build_system_prompt(
            screen_context="/simulation",
            focused_element="Résultat du seuil de rentabilité : 3 200 €",
        )
        assert "Résultat du seuil de rentabilité" in prompt

    def test_build_system_prompt_with_calculator_state(self):
        """Should include calculator inputs and outputs in the prompt."""
        calculator_state = {
            "inputs": {"ca_mensuel": "3500", "charges_fixes": "1200"},
            "outputs": {"point_mort": "2900", "marge_nette": "600"},
        }
        prompt = build_system_prompt(
            screen_context="/simulation",
            calculator_state=calculator_state,
        )
        assert "ca_mensuel" in prompt
        assert "3500" in prompt
        assert "point_mort" in prompt
        assert "2900" in prompt

    def test_build_system_prompt_no_profile_section_for_empty_profile(self):
        """An empty profile dict should not add a profile section header."""
        prompt = build_system_prompt(user_profile={})
        # Empty profile → no "Profil de l'utilisateur" section
        assert "Profil de l'utilisateur" not in prompt

    def test_build_system_prompt_sections_separated_by_divider(self):
        """Multiple sections should be separated by the divider."""
        profile = {"user_name": "Test", "experience_level": "intermediaire"}
        prompt = build_system_prompt(
            user_profile=profile,
            screen_context="/app/dashboard",
        )
        assert "---" in prompt

    def test_build_public_system_prompt_no_user_data(self):
        """Public prompt should NOT mention user profile or financial data access."""
        prompt = build_public_system_prompt()
        assert "CoCo" in prompt
        assert "Communauté Coiffure" in prompt
        # Public prompt must mention limitations
        assert "NE PAS" in prompt or "pas accéder" in prompt.lower()

    def test_build_public_system_prompt_encourages_signup(self):
        """Public prompt should encourage signing up."""
        prompt = build_public_system_prompt()
        assert "compte" in prompt.lower()


class TestBuildProfileSection:
    """Tests for the profile section builder in isolation."""

    def test_empty_profile_returns_empty_string(self):
        """Empty dict should return empty string (no section at all)."""
        result = _build_profile_section({})
        assert result == ""

    def test_profile_with_name_only(self):
        """Profile with just a name should return a section."""
        result = _build_profile_section({"user_name": "Sophie"})
        assert "Sophie" in result

    def test_profile_with_unknown_experience_level_ignored(self):
        """Unknown experience level should not crash and not appear in output."""
        result = _build_profile_section({
            "user_name": "Test",
            "experience_level": "expert_ninja",  # invalid
        })
        # Unknown level is silently ignored
        assert "expert_ninja" not in result

    def test_profile_goals_included(self):
        """Business goals should appear in the profile section."""
        result = _build_profile_section({
            "user_name": "Test",
            "business_goals": ["rentabilite", "prix"],
        })
        assert "rentabilite" in result
        assert "prix" in result


class TestBuildScreenSection:
    """Tests for the screen section builder."""

    def test_known_route_shows_label(self):
        """Known routes should resolve to their French label."""
        # Use correct routes (no /app/ prefix — SvelteKit route groups are transparent)
        section = _build_screen_section("/simulation", None, None)
        assert "Simulation de rentabilité" in section

    def test_unknown_route_shows_raw_path(self):
        """Unknown routes should still appear in the section."""
        section = _build_screen_section("/unknown-page", None, None)
        assert "/unknown-page" in section

    def test_screen_to_label_known_routes(self):
        """All known routes should return their French label."""
        # Correct routes — no /app/ prefix
        assert _screen_to_label("/dashboard") == "Tableau de bord"
        assert _screen_to_label("/simulation") == "Simulation de rentabilité"
        assert _screen_to_label("/prix") == "Calcul des prix"
        assert _screen_to_label("/pilotage") == "Pilotage annuel"  # WHY: route is /pilotage not /copilot
        assert _screen_to_label("/mes-economies") == "Mes Économies"  # Task 2.12.2 — new route
        assert _screen_to_label("/settings") == "Paramètres"
        assert _screen_to_label("/onboarding") == "Configuration initiale"

    def test_screen_to_label_unknown_returns_raw(self):
        """Unknown routes return the raw path as fallback."""
        assert _screen_to_label("/future-feature") == "/future-feature"


# ── Tool Definition Tests ──────────────────────────────────────────────────────

class TestToolDefinitions:
    """Tests for the tool definition structures."""

    def test_all_tools_have_required_fields(self):
        """Every tool definition must have name, description, and input_schema."""
        for tool in TOOL_DEFINITIONS:
            assert "name" in tool, f"Tool missing 'name': {tool}"
            assert "description" in tool, f"Tool missing 'description': {tool}"
            assert "input_schema" in tool, f"Tool missing 'input_schema': {tool}"
            assert tool["input_schema"]["type"] == "object"

    def test_all_tools_have_ui_labels(self):
        """Every tool in TOOL_DEFINITIONS should have a corresponding UI label."""
        for tool in TOOL_DEFINITIONS:
            assert tool["name"] in TOOL_UI_LABELS, (
                f"Tool '{tool['name']}' has no UI label in TOOL_UI_LABELS"
            )

    def test_tool_count(self):
        """Should have exactly 19 tools defined (Task 2.13.2 added get_employees + get_fiches_salaire_status)."""
        assert len(TOOL_DEFINITIONS) == 19

    def test_expected_tools_present(self):
        """All expected tool names should be present."""
        names = {t["name"] for t in TOOL_DEFINITIONS}
        expected = {
            "get_user_profile",
            "get_screen_context",
            "search_blog",
            "search_web",
            "get_financial_summary",
            "get_calculation_explanation",
            "navigate_user",
            "recommend_partner",
            "get_services",              # Added Task 2.5.8 — CoCo service catalog tool
            # Task 2.9.6 — Calculator Hub tools
            "hub_overview",
            "list_scenarios",
            "get_scenario",
            "check_stale_links",
            "explain_prime_breakdown",
            "run_prime_preview",
            "detect_comptable_savings",  # Added Task 2.11.14 — ComCoi-first referral policy
            "get_savings_report",        # Added Task 2.12.2 — full savings report tool
            "get_employees",             # Added Task 2.12.9 — employee cotisations tool
            "get_fiches_salaire_status", # Added Task 2.13.2 — payslip status tool
        }
        assert names == expected

    def test_search_web_description_mentions_anonymisation(self):
        """search_web description must mention not including personal data."""
        web_tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "search_web")
        desc = web_tool["description"].lower()
        assert "personal" in desc or "never" in desc or "jamais" in desc or "anonymi" in desc

    def test_navigate_user_has_required_fields(self):
        """navigate_user must require both route and reason."""
        nav_tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "navigate_user")
        schema = nav_tool["input_schema"]
        assert "route" in schema["required"]
        assert "reason" in schema["required"]


# ── Tool Executor Tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestCallTool:
    """Tests for the tool call dispatcher and executors."""

    async def test_unknown_tool_returns_error(self):
        """Calling an unknown tool should return a found=False error dict."""
        db = AsyncMock()
        result = await call_tool(
            "does_not_exist",
            {},
            db=db,
            user_id=None,
            screen_context=None,
        )
        assert result["found"] is False
        assert "error" in result

    async def test_get_screen_context_no_context_returns_not_found(self):
        """get_screen_context with no context should return found=False."""
        db = AsyncMock()
        result = await call_tool(
            "get_screen_context",
            {},
            db=db,
            user_id="some-user-id",
            screen_context=None,
        )
        assert result["found"] is False

    async def test_get_screen_context_with_context_returns_data(self):
        """get_screen_context should return screen and focused element when present."""
        db = AsyncMock()
        context = {
            "screen": "/app/simulation",
            "focused_element": "Résultat du point mort",
            "calculator_state": None,
        }
        result = await call_tool(
            "get_screen_context",
            {},
            db=db,
            user_id="some-user-id",
            screen_context=context,
        )
        assert result["found"] is True
        assert result["screen"] == "/app/simulation"
        assert result["focused_element"] == "Résultat du point mort"

    async def test_get_user_profile_no_user_returns_not_found(self):
        """get_user_profile without user_id should return found=False."""
        db = AsyncMock()
        result = await call_tool(
            "get_user_profile",
            {},
            db=db,
            user_id=None,
            screen_context=None,
        )
        assert result["found"] is False

    async def test_get_user_profile_user_with_no_profile(self):
        """get_user_profile for user with no coco_profile should return found=False."""
        # Mock the DB to return None (no profile)
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        result = await call_tool(
            "get_user_profile",
            {},
            db=db,
            user_id=str(uuid.uuid4()),
            screen_context=None,
        )
        assert result["found"] is False

    async def test_get_user_profile_returns_profile_data(self):
        """get_user_profile should return experience level, goals, interests."""
        # Mock a CocoUserProfile
        mock_profile = MagicMock()
        mock_profile.experience_level = "intermediaire"
        mock_profile.business_goals = ["rentabilite", "prix"]
        mock_profile.interests = ["simulation"]
        mock_profile.profile_notes = {}

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_profile
        db.execute = AsyncMock(return_value=mock_result)

        result = await call_tool(
            "get_user_profile",
            {},
            db=db,
            user_id=str(uuid.uuid4()),
            screen_context=None,
        )
        assert result["found"] is True
        assert result["experience_level"] == "intermediaire"
        assert "rentabilite" in result["business_goals"]
        assert "simulation" in result["interests"]

    async def test_search_blog_stub_returns_not_found(self):
        """Blog search stub should return found=False with a reason."""
        db = AsyncMock()
        result = await call_tool(
            "search_blog",
            {"query": "seuil rentabilité coiffeur"},
            db=db,
            user_id="some-id",
            screen_context=None,
        )
        assert result["found"] is False
        assert "query" in result

    async def test_search_web_stub_returns_not_found(self):
        """Web search stub should return found=False."""
        db = AsyncMock()
        result = await call_tool(
            "search_web",
            {"query": "taux TVA coiffure 2026"},
            db=db,
            user_id="some-id",
            screen_context=None,
        )
        assert result["found"] is False

    async def test_navigate_user_returns_route_and_label(self):
        """navigate_user should return a navigation dict with route, label, reason."""
        db = AsyncMock()
        result = await call_tool(
            "navigate_user",
            {"route": "/simulation", "reason": "Pour calculer votre seuil"},
            db=db,
            user_id="some-id",
            screen_context=None,
        )
        assert result["found"] is True
        assert result["route"] == "/simulation"
        assert result["label"] == "Simulation de rentabilité"
        assert "Pour calculer" in result["reason"]
        assert result["navigation_suggestion"] is True

    async def test_navigate_user_unknown_route_uses_raw_path(self):
        """navigate_user with unknown route should still return a result."""
        db = AsyncMock()
        result = await call_tool(
            "navigate_user",
            {"route": "/future-tool", "reason": "Test"},
            db=db,
            user_id="some-id",
            screen_context=None,
        )
        assert result["found"] is True
        assert result["label"] == "/future-tool"  # Fallback to raw path

    async def test_get_financial_summary_no_user_returns_not_found(self):
        """Financial summary with no user_id should return found=False.
        (Tool replaced stub in Sprint 2 — real impl guards on user_id first.)
        """
        db = AsyncMock()
        result = await call_tool(
            "get_financial_summary",
            {},
            db=db,
            user_id=None,  # No user → immediate found=False
            screen_context=None,
        )
        assert result["found"] is False

    async def test_recommend_partner_stub_returns_not_found(self):
        """Partner recommendation stub should return found=False."""
        db = AsyncMock()
        result = await call_tool(
            "recommend_partner",
            {"category": "juridique"},
            db=db,
            user_id="some-id",
            screen_context=None,
        )
        assert result["found"] is False
        assert result["category"] == "juridique"


# ── Message History Builder Tests ──────────────────────────────────────────────

class TestBuildMessageHistory:
    """Tests for the conversation history builder."""

    def test_empty_messages_returns_empty_list(self):
        """No messages should return empty list."""
        result = _build_message_history([])
        assert result == []

    def test_filters_invalid_roles(self):
        """Messages with invalid roles should be filtered out."""
        messages = [
            {"role": "user", "content": "Hello", "timestamp": "2026-04-11"},
            {"role": "system", "content": "Ignored", "timestamp": "2026-04-11"},  # invalid
            {"role": "assistant", "content": "Hi!", "timestamp": "2026-04-11"},
        ]
        result = _build_message_history(messages)
        assert len(result) == 2
        assert all(m["role"] in ("user", "assistant") for m in result)

    def test_filters_empty_content(self):
        """Messages with empty content should be filtered out."""
        messages = [
            {"role": "user", "content": "", "timestamp": "2026-04-11"},
            {"role": "user", "content": "Real message", "timestamp": "2026-04-11"},
        ]
        result = _build_message_history(messages)
        assert len(result) == 1
        assert result[0]["content"] == "Real message"

    def test_respects_max_messages_limit(self):
        """Should only return the last max_messages messages."""
        messages = [
            {"role": "user", "content": f"Message {i}", "timestamp": "2026-04-11"}
            for i in range(30)
        ]
        result = _build_message_history(messages, max_messages=10)
        assert len(result) == 10
        # Should be the LAST 10
        assert result[0]["content"] == "Message 20"
        assert result[-1]["content"] == "Message 29"

    def test_returns_correct_format(self):
        """Returned dicts should only have role and content keys."""
        messages = [
            {"role": "user", "content": "Hello", "timestamp": "2026-04-11"},
        ]
        result = _build_message_history(messages)
        assert result[0] == {"role": "user", "content": "Hello"}
        assert "timestamp" not in result[0]  # timestamp stripped


# ── Schema Tests ───────────────────────────────────────────────────────────────

class TestCocoSchemas:
    """Basic schema validation tests."""

    def test_coco_chat_request_requires_message(self):
        """CocoChatRequest should require a message."""
        from pydantic import ValidationError
        from app.schemas.coco import CocoChatRequest

        with pytest.raises(ValidationError):
            CocoChatRequest()  # No message

    def test_coco_chat_request_defaults(self):
        """CocoChatRequest should have sensible defaults."""
        from app.schemas.coco import CocoChatRequest

        req = CocoChatRequest(message="Hello CoCo")
        assert req.message == "Hello CoCo"
        assert req.conversation_id is None
        assert req.context.screen == ""
        assert req.context.focused_element is None
        assert req.context.calculator_state is None

    def test_coco_screen_context_defaults(self):
        """CocoScreenContext should have empty defaults."""
        from app.schemas.coco import CocoScreenContext

        ctx = CocoScreenContext()
        assert ctx.screen == ""
        assert ctx.focused_element is None
        assert ctx.calculator_state is None

    def test_coco_public_chat_request(self):
        """CocoPublicChatRequest should accept message and optional session_id."""
        from app.schemas.coco import CocoPublicChatRequest

        req = CocoPublicChatRequest(message="Qu'est-ce que Communauté Coiffure ?")
        assert req.message == "Qu'est-ce que Communauté Coiffure ?"
        assert req.session_id is None

        req_with_session = CocoPublicChatRequest(
            message="Test",
            session_id="anon-123",
        )
        assert req_with_session.session_id == "anon-123"
