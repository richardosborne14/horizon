"""
Tests for Tasks 2.11, 2.12, 2.13 — CoCo tool implementations.

Task 2.11: Blog RAG (embedding service + pgvector search)
Task 2.12: Web search (Perplexity + cache + rate limiting)
Task 2.13: Calculation explainer (benchmarks + suggestions)

All external API calls are mocked to run without real API keys.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.coco_tools import (
    call_tool,
    TOOL_DEFINITIONS,
    TOOL_UI_LABELS,
    _tool_search_blog,
    _tool_search_web,
    _tool_get_financial_summary,
    _tool_get_calculation_explanation,
)
from app.calculations import pricing  # noqa: F401 - ensure import chain


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    """Mock async DB session."""
    db = AsyncMock(spec=AsyncSession)
    # Mock execute to return empty results by default
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None
    mock_result.fetchall.return_value = []
    db.execute.return_value = mock_result
    return db


# ── Task 2.11: Blog search ─────────────────────────────────────────────────────

class TestBlogSearch:
    """Tests for _tool_search_blog (pgvector RAG)."""

    @pytest.mark.asyncio
    async def test_search_blog_no_api_key_returns_graceful_degradation(self, mock_db):
        """When DeepInfra key is missing, return found=False gracefully."""
        with patch(
            "app.services.coco_tools.generate_embedding",
            side_effect=ValueError("DEEPINFRA_API_KEY non configurée"),
        ):
            result = await _tool_search_blog(
                {"query": "cotisations sociales coiffeur"},
                db=mock_db,
                user_id="user-1",
                screen_context=None,
            )

        assert result["found"] is False
        assert "query" in result
        assert "raison" in result or "reason" in result

    @pytest.mark.asyncio
    async def test_search_blog_empty_query_returns_found_false(self, mock_db):
        """Empty query returns found=False immediately."""
        result = await _tool_search_blog(
            {"query": ""},
            db=mock_db,
            user_id="user-1",
            screen_context=None,
        )
        assert result["found"] is False

    @pytest.mark.asyncio
    async def test_search_blog_no_results_returns_found_false(self, mock_db):
        """When DB returns no rows, return found=False."""
        mock_db.execute.return_value.fetchall.return_value = []

        with patch(
            "app.services.coco_tools.generate_embedding",
            return_value=[0.1] * 1024,
        ):
            result = await _tool_search_blog(
                {"query": "gestion salon coiffure"},
                db=mock_db,
                user_id="user-1",
                screen_context=None,
            )

        assert result["found"] is False

    @pytest.mark.asyncio
    async def test_search_blog_returns_articles_above_threshold(self, mock_db):
        """When DB returns rows with similarity > 0.5, return them."""
        # Mock row objects
        mock_row = MagicMock()
        mock_row.title = "Gérer les cotisations d'un salon"
        mock_row.slug = "gerer-cotisations-salon"
        mock_row.excerpt = "Guide pratique sur les cotisations sociales."
        mock_row.tags = ["cotisations", "gestion"]
        mock_row.similarity = 0.82

        mock_db.execute.return_value.fetchall.return_value = [mock_row]

        with patch(
            "app.services.coco_tools.generate_embedding",
            return_value=[0.1] * 1024,
        ):
            result = await _tool_search_blog(
                {"query": "cotisations sociales coiffeur"},
                db=mock_db,
                user_id="user-1",
                screen_context=None,
            )

        assert result["found"] is True
        assert result["count"] == 1
        assert result["articles"][0]["slug"] == "gerer-cotisations-salon"
        assert result["articles"][0]["similarity"] == pytest.approx(0.82, abs=0.01)

    @pytest.mark.asyncio
    async def test_search_blog_filters_low_similarity(self, mock_db):
        """Articles with similarity <= 0.5 are filtered out."""
        mock_row = MagicMock()
        mock_row.title = "Article peu pertinent"
        mock_row.slug = "article-peu-pertinent"
        mock_row.excerpt = "Contenu peu pertinent."
        mock_row.tags = []
        mock_row.similarity = 0.35  # Below threshold

        mock_db.execute.return_value.fetchall.return_value = [mock_row]

        with patch(
            "app.services.coco_tools.generate_embedding",
            return_value=[0.1] * 1024,
        ):
            result = await _tool_search_blog(
                {"query": "cotisations sociales"},
                db=mock_db,
                user_id="user-1",
                screen_context=None,
            )

        assert result["found"] is False


# ── Task 2.12: Web search ──────────────────────────────────────────────────────

class TestWebSearch:
    """Tests for _tool_search_web (Perplexity + cache)."""

    @pytest.mark.asyncio
    async def test_search_web_empty_query_returns_found_false(self, mock_db):
        """Empty query returns found=False without calling API."""
        result = await _tool_search_web(
            {"query": ""},
            db=mock_db,
            user_id="user-1",
            screen_context=None,
        )
        assert result["found"] is False

    @pytest.mark.asyncio
    async def test_search_web_not_configured_returns_graceful(self, mock_db):
        """When Perplexity is not configured, return found=False gracefully."""
        from app.services.web_search import SearchNotConfiguredError

        with patch(
            "app.services.coco_tools.search_web",
            side_effect=SearchNotConfiguredError("PERPLEXITY_API_KEY non configurée"),
        ):
            result = await _tool_search_web(
                {"query": "taux TVA coiffure France 2026"},
                db=mock_db,
                user_id="user-1",
                screen_context=None,
            )

        assert result["found"] is False
        assert "query" in result

    @pytest.mark.asyncio
    async def test_search_web_rate_limited_returns_graceful(self, mock_db):
        """When rate limit hit, return found=False with rate_limited flag."""
        from app.services.web_search import SearchRateLimitError

        with patch(
            "app.services.coco_tools.search_web",
            side_effect=SearchRateLimitError("Limite de 5 recherches web atteinte"),
        ):
            result = await _tool_search_web(
                {"query": "taux TVA coiffure France 2026"},
                db=mock_db,
                user_id="user-1",
                screen_context=None,
                conversation_id="conv-123",
            )

        assert result["found"] is False
        assert result.get("rate_limited") is True

    @pytest.mark.asyncio
    async def test_search_web_safety_check_rejects_personal_data(self, mock_db):
        """When query contains personal financial data, return found=False."""
        with patch(
            "app.services.coco_tools.search_web",
            side_effect=ValueError("Requête contient des données financières personnelles"),
        ):
            result = await _tool_search_web(
                {"query": "mon CA est 3000 euros quelles cotisations"},
                db=mock_db,
                user_id="user-1",
                screen_context=None,
            )

        assert result["found"] is False
        # The actual query should be masked in the response
        assert result.get("query") == "[requête masquée]"

    @pytest.mark.asyncio
    async def test_search_web_returns_answer_on_success(self, mock_db):
        """Successful search returns found=True with answer."""
        with patch(
            "app.services.coco_tools.search_web",
            return_value={
                "found": True,
                "query": "taux TVA coiffure France 2026",
                "answer": "La TVA pour les prestations de coiffure est de 20% en France.",
                "source": "perplexity",
                "cached": False,
            },
        ):
            result = await _tool_search_web(
                {"query": "taux TVA coiffure France 2026"},
                db=mock_db,
                user_id="user-1",
                screen_context=None,
            )

        assert result["found"] is True
        assert "TVA" in result["answer"]


# ── Task 2.13: Calculation explainer ──────────────────────────────────────────

class TestCalculationExplainer:
    """Tests for _tool_get_calculation_explanation and explain_calculation."""

    @pytest.mark.asyncio
    async def test_explain_returns_found_true(self, mock_db):
        """Calculation explanation always returns found=True (no external deps)."""
        result = await _tool_get_calculation_explanation(
            {
                "calculation_type": "simulation",
                "inputs": {"ca_ht": 5000, "salaires": 2000, "charges_fixes": 1000},
                "outputs": {"cash_flow": 500, "point_mort": 4500},
            },
            db=mock_db,
            user_id="user-1",
            screen_context=None,
        )

        assert result["found"] is True
        assert "type" in result  # explain_calculation returns "type" key

    @pytest.mark.asyncio
    async def test_explain_uses_screen_context_fallback(self, mock_db):
        """When no inputs in tool_input, falls back to screen_context.calculator_state."""
        screen_context = {
            "screen": "/simulation",
            "calculator_state": {
                "inputs": {"ca_ht": 8000},
                "outputs": {"cash_flow": 1200},
            },
        }

        result = await _tool_get_calculation_explanation(
            {"calculation_type": "simulation"},  # No inputs/outputs
            db=mock_db,
            user_id="user-1",
            screen_context=screen_context,
        )

        assert result["found"] is True

    def test_explain_calculation_simulation(self):
        """Unit test: explain_calculation for simulation type."""
        from app.services.calculation_explainer import explain_calculation

        result = explain_calculation(
            "simulation",
            inputs={"ca_ht": 5000, "salaires": 2000},
            outputs={"cash_flow": 500, "point_mort": 4500},
        )

        assert "type" in result
        assert result["type"] == "simulation"

    def test_explain_calculation_with_empty_inputs(self):
        """explain_calculation handles empty inputs gracefully."""
        from app.services.calculation_explainer import explain_calculation

        result = explain_calculation("simulation", inputs={}, outputs={})

        assert "type" in result
        # Should not raise, just return minimal result

    def test_explain_calculation_unknown_type(self):
        """explain_calculation handles unknown type without crashing."""
        from app.services.calculation_explainer import explain_calculation

        result = explain_calculation("unknown_type", inputs={}, outputs={})
        assert result is not None


# ── Tool registry tests ────────────────────────────────────────────────────────

class TestToolRegistry:
    """Tests for tool definitions and dispatcher."""

    def test_all_tool_names_in_ui_labels(self):
        """Every tool in TOOL_DEFINITIONS has a TOOL_UI_LABELS entry."""
        definition_names = {t["name"] for t in TOOL_DEFINITIONS}
        label_names = set(TOOL_UI_LABELS.keys())

        missing = definition_names - label_names
        assert not missing, f"Missing UI labels for tools: {missing}"

    @pytest.mark.asyncio
    async def test_call_tool_unknown_returns_error(self, mock_db):
        """Calling an unknown tool returns found=False with error."""
        result = await call_tool(
            "nonexistent_tool",
            {},
            db=mock_db,
            user_id="user-1",
        )
        assert result["found"] is False
        assert "error" in result

    def test_tool_definitions_have_required_fields(self):
        """All tool definitions have name, description, and input_schema."""
        for tool in TOOL_DEFINITIONS:
            assert "name" in tool, f"Tool missing 'name': {tool}"
            assert "description" in tool, f"Tool '{tool.get('name')}' missing 'description'"
            assert "input_schema" in tool, f"Tool '{tool.get('name')}' missing 'input_schema'"

    def test_search_blog_tool_requires_query(self):
        """search_blog tool definition requires 'query' parameter."""
        blog_tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "search_blog")
        assert "query" in blog_tool["input_schema"]["required"]

    def test_search_web_tool_requires_query(self):
        """search_web tool definition requires 'query' parameter."""
        web_tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "search_web")
        assert "query" in web_tool["input_schema"]["required"]

    def test_get_calculation_explanation_requires_calculation_type(self):
        """get_calculation_explanation tool requires 'calculation_type'."""
        calc_tool = next(
            t for t in TOOL_DEFINITIONS if t["name"] == "get_calculation_explanation"
        )
        assert "calculation_type" in calc_tool["input_schema"]["required"]


# ── Financial summary tests ────────────────────────────────────────────────────

class TestFinancialSummary:
    """Tests for _tool_get_financial_summary."""

    @pytest.mark.asyncio
    async def test_financial_summary_no_user_returns_not_found(self, mock_db):
        """Without user_id, return found=False."""
        result = await _tool_get_financial_summary(
            {},
            db=mock_db,
            user_id=None,
            screen_context=None,
        )
        assert result["found"] is False

    @pytest.mark.asyncio
    async def test_financial_summary_no_salon_returns_not_found(self, mock_db):
        """When user has no salon, return found=False."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        result = await _tool_get_financial_summary(
            {},
            db=mock_db,
            user_id="user-1",
            screen_context=None,
        )
        assert result["found"] is False

    @pytest.mark.asyncio
    async def test_financial_summary_with_reports_returns_found_true(self, mock_db):
        """With reports, return found=True with monthly summaries."""
        # Mock salon
        mock_salon = MagicMock()
        mock_salon.id = "salon-1"
        mock_salon.name = "Mon Salon"

        # Mock reports
        mock_report = MagicMock()
        mock_report.month = 3
        mock_report.year = 2026
        mock_report.ca_ttc = 5000
        mock_report.depenses_total_ttc = 1500
        mock_report.salaires_charges_total = 2000
        mock_report.cash_flow = 300

        # Set up execute to return salon first, then reports
        call_count = 0

        async def mock_execute(query, *args, **kwargs):
            nonlocal call_count
            result = MagicMock()
            if call_count == 0:
                result.scalar_one_or_none.return_value = mock_salon
            else:
                result.scalars.return_value.all.return_value = [mock_report]
            call_count += 1
            return result

        mock_db.execute = mock_execute

        result = await _tool_get_financial_summary(
            {},
            db=mock_db,
            user_id="user-1",
            screen_context=None,
        )

        assert result["found"] is True
        assert result["salon_name"] == "Mon Salon"
        assert len(result["recent_months"]) == 1
        assert result["recent_months"][0]["period"] == "03/2026"
        assert result["recent_months"][0]["ca_ttc"] == 5000.0
        assert result["recent_months"][0]["cash_flow"] == 300.0
