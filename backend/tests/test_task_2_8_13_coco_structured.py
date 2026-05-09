"""
Tests for Task 2.8.13 — CoCo structured-output parser and schema extension.

Covers:
  1. _parse_structured_output — pure function, no mocks needed
  2. CocoMiniCard / CocoSuggestedReply / CocoSSEMiniCard / CocoSSESuggestedReplies schemas
  3. coco_prompts.build_system_prompt — verifies structured format is injected
  4. Edge cases: no tags, unknown variant fallback, malformed tags
"""

import pytest

from app.services.coco import _parse_structured_output
from app.schemas.coco import (
    CocoMiniCard,
    CocoSuggestedReply,
    CocoSSEMiniCard,
    CocoSSESuggestedReplies,
)
from app.services.coco_prompts import build_system_prompt


# ── _parse_structured_output ────────────────────────────────────────────────────


class TestParseStructuredOutput:
    """Unit tests for the post-stream tag parser."""

    def test_plain_text_returns_empty_cards_and_unchanged_text(self) -> None:
        """Plain prose response (no tags) should pass through unchanged."""
        text = "Bonjour ! Voici votre analyse mensuelle.\n\nTout va bien."
        cards, suggestions, clean = _parse_structured_output(text)
        assert cards == []
        assert suggestions == []
        assert "Bonjour" in clean
        assert "Tout va bien" in clean
        # No tags should appear in the clean text
        assert "[FINDING" not in clean
        assert "[SUGGESTIONS" not in clean

    def test_single_finding_parsed_correctly(self) -> None:
        """A single FINDING block is extracted with correct fields."""
        text = (
            "Voici mon analyse.\n\n"
            "[FINDING:gold:💇:Tes prix]\n"
            "Tes tarifs sont 4 € sous le seuil.\n"
            "[/FINDING]\n\n"
            "Bonne journée !"
        )
        cards, suggestions, clean = _parse_structured_output(text)
        assert len(cards) == 1
        assert cards[0]["variant"] == "gold"
        assert cards[0]["icon"] == "💇"
        assert cards[0]["title"] == "Tes prix"
        assert "4 €" in cards[0]["body"]
        assert suggestions == []
        # Tags stripped from clean text
        assert "[FINDING" not in clean
        assert "[/FINDING]" not in clean
        # Prose preserved
        assert "Bonne journée" in clean

    def test_two_findings_both_extracted(self) -> None:
        """Two FINDING blocks in sequence are both extracted."""
        text = (
            "[FINDING:gold:💇:Tes prix]\n"
            "Tes tarifs sont trop bas.\n"
            "[/FINDING]\n\n"
            "[FINDING:purple:📦:Tes achats]\n"
            "Tu as acheté 13% de ton CA.\n"
            "[/FINDING]"
        )
        cards, suggestions, clean = _parse_structured_output(text)
        assert len(cards) == 2
        assert cards[0]["variant"] == "gold"
        assert cards[1]["variant"] == "purple"
        assert cards[1]["icon"] == "📦"
        assert clean.strip() == ""  # Only tags, no prose — clean should be nearly empty

    def test_all_valid_variants_accepted(self) -> None:
        """All four valid variants are accepted without modification."""
        for variant in ("gold", "purple", "green", "red"):
            text = f"[FINDING:{variant}:🔵:Titre]\nBody.\n[/FINDING]"
            cards, _, _ = _parse_structured_output(text)
            assert len(cards) == 1
            assert cards[0]["variant"] == variant

    def test_unknown_variant_falls_back_to_gold(self) -> None:
        """
        An unknown variant is coerced to 'gold'.
        WHY: The model occasionally uses a wrong colour — we don't want to
        crash the UI; a graceful fallback is better.
        """
        text = "[FINDING:orange:🔥:Titre]\nBody.\n[/FINDING]"
        cards, _, _ = _parse_structured_output(text)
        assert len(cards) == 1
        assert cards[0]["variant"] == "gold"

    def test_suggestions_with_intents_parsed(self) -> None:
        """SUGGESTIONS block with pipe-separated intents is parsed correctly."""
        text = (
            "[SUGGESTIONS]\n"
            "- Commençons par les prix | focus_pricing\n"
            "- Plutôt les achats | focus_purchases\n"
            "[/SUGGESTIONS]"
        )
        cards, suggestions, clean = _parse_structured_output(text)
        assert cards == []
        assert len(suggestions) == 2
        assert suggestions[0]["label"] == "Commençons par les prix"
        assert suggestions[0]["intent"] == "focus_pricing"
        assert suggestions[1]["label"] == "Plutôt les achats"
        assert suggestions[1]["intent"] == "focus_purchases"
        assert "[SUGGESTIONS]" not in clean

    def test_suggestions_without_intent_accepted(self) -> None:
        """SUGGESTIONS lines without '|' are accepted with empty intent."""
        text = (
            "[SUGGESTIONS]\n"
            "- Voir mes prix\n"
            "- Voir mes charges\n"
            "[/SUGGESTIONS]"
        )
        _, suggestions, _ = _parse_structured_output(text)
        assert len(suggestions) == 2
        assert suggestions[0]["intent"] == ""
        assert suggestions[1]["intent"] == ""

    def test_full_structured_response(self) -> None:
        """A complete response with prose + 2 findings + suggestions."""
        text = (
            "Voici mon analyse de votre salon :\n\n"
            "[FINDING:gold:💇:Tes prix]\n"
            "À tes tarifs actuels, ton coupe-couleur est 4 € sous ton seuil.\n"
            "[/FINDING]\n\n"
            "[FINDING:purple:📦:Tes achats]\n"
            "En mars tu as acheté 13% de ton CA — la norme est 9%.\n"
            "[/FINDING]\n\n"
            "[SUGGESTIONS]\n"
            "- Commençons par les prix | focus_pricing\n"
            "- Plutôt les achats | focus_purchases\n"
            "[/SUGGESTIONS]\n\n"
            "Je suis là si tu as des questions !"
        )
        cards, suggestions, clean = _parse_structured_output(text)

        assert len(cards) == 2
        assert len(suggestions) == 2
        # Clean text contains prose but not tags
        assert "Voici mon analyse" in clean
        assert "Je suis là" in clean
        assert "[FINDING" not in clean
        assert "[SUGGESTIONS]" not in clean
        # Blank line collapsing — no triple+ blank lines
        assert "\n\n\n" not in clean

    def test_multiline_finding_body(self) -> None:
        """FINDING body can span multiple lines (re.DOTALL)."""
        text = (
            "[FINDING:green:✅:Bravo]\n"
            "Ligne 1.\n"
            "Ligne 2.\n"
            "Ligne 3.\n"
            "[/FINDING]"
        )
        cards, _, _ = _parse_structured_output(text)
        assert len(cards) == 1
        assert "Ligne 1." in cards[0]["body"]
        assert "Ligne 3." in cards[0]["body"]

    def test_empty_string_returns_empty(self) -> None:
        """Empty input returns empty lists and empty clean text."""
        cards, suggestions, clean = _parse_structured_output("")
        assert cards == []
        assert suggestions == []
        assert clean == ""

    def test_clean_text_strips_extra_blank_lines(self) -> None:
        """After stripping tags, no triple+ blank lines remain."""
        text = (
            "[FINDING:gold:💇:Titre]\n"
            "Body.\n"
            "[/FINDING]\n\n\n\n"
            "[FINDING:purple:📦:Titre 2]\n"
            "Body 2.\n"
            "[/FINDING]"
        )
        _, _, clean = _parse_structured_output(text)
        assert "\n\n\n" not in clean


# ── Schema tests ──────────────────────────────────────────────────────────────


class TestCocoStructuredSchemas:
    """Pydantic schema validation for structured-output types."""

    def test_mini_card_schema_valid(self) -> None:
        """CocoMiniCard validates correct data."""
        card = CocoMiniCard(
            variant="gold",
            icon="💇",
            title="Tes prix",
            body="Tes tarifs sont trop bas.",
        )
        assert card.type == "mini_card"
        assert card.variant == "gold"

    def test_mini_card_schema_invalid_variant(self) -> None:
        """CocoMiniCard rejects invalid variant via Pydantic Literal."""
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            CocoMiniCard(
                variant="orange",  # not in Literal
                icon="🔥",
                title="Titre",
                body="Body",
            )

    def test_suggested_reply_schema_default_intent(self) -> None:
        """CocoSuggestedReply defaults intent to empty string."""
        reply = CocoSuggestedReply(label="Voir mes prix")
        assert reply.intent == ""

    def test_suggested_reply_schema_with_intent(self) -> None:
        """CocoSuggestedReply stores label and intent."""
        reply = CocoSuggestedReply(label="Commençons par les prix", intent="focus_pricing")
        assert reply.label == "Commençons par les prix"
        assert reply.intent == "focus_pricing"

    def test_sse_mini_card_serialises(self) -> None:
        """CocoSSEMiniCard serialises to JSON with correct type discriminator."""
        sse_event = CocoSSEMiniCard(
            variant="purple",
            icon="📦",
            title="Tes achats",
            body="En mars tu as acheté 13% de ton CA.",
        )
        data = sse_event.model_dump()
        assert data["type"] == "mini_card"
        assert data["variant"] == "purple"

    def test_sse_suggested_replies_serialises(self) -> None:
        """CocoSSESuggestedReplies serialises to JSON with replies list."""
        sse_event = CocoSSESuggestedReplies(
            replies=[
                CocoSuggestedReply(label="Commençons par les prix", intent="focus_pricing"),
                CocoSuggestedReply(label="Plutôt les achats", intent="focus_purchases"),
            ]
        )
        data = sse_event.model_dump()
        assert data["type"] == "suggested_replies"
        assert len(data["replies"]) == 2
        assert data["replies"][0]["label"] == "Commençons par les prix"


# ── coco_prompts tests ────────────────────────────────────────────────────────


class TestCocoPromptsStructuredFormat:
    """Verify the structured format section is included in the system prompt."""

    def test_build_system_prompt_includes_format_instructions(self) -> None:
        """
        build_system_prompt() must include the FINDING/SUGGESTIONS format
        instructions so the model knows the tag syntax.
        """
        prompt = build_system_prompt()
        assert "[FINDING:" in prompt
        assert "[SUGGESTIONS]" in prompt
        assert "[/FINDING]" in prompt
        assert "[/SUGGESTIONS]" in prompt

    def test_build_system_prompt_format_at_end(self) -> None:
        """
        Format instructions come AFTER persona and profile sections.
        WHY: content context before format instructions.
        """
        prompt = build_system_prompt(
            user_profile={"user_name": "Marie", "experience_level": "debutant"},
        )
        persona_pos = prompt.find("Tu es CoCo")
        format_pos = prompt.find("Format de réponse structurée")
        assert persona_pos < format_pos, "Persona should precede format instructions"

    def test_build_system_prompt_with_no_args_includes_format(self) -> None:
        """Format section is injected even when called with no arguments."""
        prompt = build_system_prompt()
        assert "Format de réponse structurée" in prompt

    def test_build_public_prompt_does_not_include_format(self) -> None:
        """
        Public (landing-page) prompt should NOT include structured format.
        WHY: Public CoCo answers simple questions — mini-cards are not shown
        on the landing page widget, so injecting the format would waste tokens
        and risk the model emitting tags that the landing page widget can't render.
        """
        from app.services.coco_prompts import build_public_system_prompt
        prompt = build_public_system_prompt()
        assert "[FINDING:" not in prompt
