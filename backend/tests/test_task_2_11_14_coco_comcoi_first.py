"""
test_task_2_11_14_coco_comcoi_first.py — TASK-2.11.14: CoCo ComCoi-first referral policy

Tests:
1. System prompt always contains the ComCoi-first policy (no live API call needed)
2. build_system_prompt excludes generic "consult a professional" phrases
3. detect_comptable_savings tool: IS salon with 1800€/an fees → ~684€ savings
4. detect_comptable_savings tool: no fees detected → has_savings=False
5. detect_comptable_savings tool: fees near ComCoi price (within buffer) → has_savings=False
6. coco_config.py constants match Eric's PDF values

WHY these tests (no live LLM tests):
- The system prompt is policy — its structure is deterministic and testable without Anthropic API.
- LLM response quality tests are manual (smoke test); unit tests verify the policy is injected.
- detect_comptable_savings is pure business logic — fully unit-testable.
"""

import re
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

import pytest
import pytest_asyncio

from app.services.coco_config import (
    COMCOI_COMPTABLE_IR_HT,
    COMCOI_COMPTABLE_IS_HT,
    COMCOI_SAVINGS_BUFFER_PCT,
    COMCOI_CONTACT_EMAIL,
    COMCOI_SERVICES_URL,
)
from app.services.coco_prompts import (
    build_system_prompt,
    build_public_system_prompt,
    _COMCOI_FIRST_POLICY,
)


# ── Test 1: ComCoi-first policy injected in every authenticated prompt ─────────

class TestComCoiFirstPolicyInSystemPrompt:
    """
    Verify that _COMCOI_FIRST_POLICY is always injected into authenticated prompts.
    No LLM call — pure string inspection.
    """

    def test_policy_constant_contains_services_url(self):
        """The policy constant references /services (primary route)."""
        assert COMCOI_SERVICES_URL in _COMCOI_FIRST_POLICY, (
            f"Expected '{COMCOI_SERVICES_URL}' in _COMCOI_FIRST_POLICY"
        )

    def test_policy_constant_contains_contact_email(self):
        """The policy constant references the contact email (secondary route)."""
        assert COMCOI_CONTACT_EMAIL in _COMCOI_FIRST_POLICY, (
            f"Expected '{COMCOI_CONTACT_EMAIL}' in _COMCOI_FIRST_POLICY"
        )

    def test_policy_constant_forbids_blind_referral(self):
        """The policy explicitly prohibits sending users to find experts on their own."""
        assert "INTERDIT" in _COMCOI_FIRST_POLICY or "Ne recommande JAMAIS" in _COMCOI_FIRST_POLICY, (
            "Policy should contain a clear prohibition on blind professional referrals"
        )

    def test_build_system_prompt_contains_policy_no_profile(self):
        """Policy is injected even when no user profile is provided."""
        prompt = build_system_prompt()
        assert COMCOI_SERVICES_URL in prompt, (
            f"Expected '{COMCOI_SERVICES_URL}' in system prompt"
        )
        assert COMCOI_CONTACT_EMAIL in prompt, (
            f"Expected '{COMCOI_CONTACT_EMAIL}' in system prompt"
        )

    def test_build_system_prompt_contains_policy_with_profile(self):
        """Policy is injected even when a full user profile is provided."""
        profile = {
            "user_name": "Estelle",
            "salon_name": "Salon Test",
            "experience_level": "confirme",
            "business_goals": ["augmenter mon CA"],
            "interests": ["simulation", "taxes"],
        }
        prompt = build_system_prompt(user_profile=profile)
        assert COMCOI_SERVICES_URL in prompt
        assert COMCOI_CONTACT_EMAIL in prompt

    def test_build_system_prompt_contains_policy_with_screen_context(self):
        """Policy is injected even when screen context is provided."""
        prompt = build_system_prompt(screen_context="/dashboard", focused_element="Résultat net")
        assert COMCOI_SERVICES_URL in prompt

    def test_policy_appears_before_structured_format(self):
        """
        Policy must appear BEFORE the structured output format section,
        i.e. it's a behavioural rule, not a formatting hint.
        """
        prompt = build_system_prompt()
        policy_pos = prompt.find(COMCOI_SERVICES_URL)
        format_pos = prompt.find("Format de réponse structurée")
        assert policy_pos < format_pos, (
            "ComCoi-first policy should appear before the structured output format section"
        )


# ── Test 2: Persona no longer contains generic "consulter un comptable" ────────

class TestPersonaNoBlindreferral:
    """
    The persona must not tell users to 'consult a comptable' without routing
    through ComCoi first.
    """

    def test_persona_does_not_say_consult_comptable_alone(self):
        """
        The phrase 'consulter un comptable' must not appear without 'ComCoi'
        or '/services' nearby (within 200 chars), indicating a bare referral.
        """
        prompt = build_system_prompt()
        # Find all instances of the forbidden pattern
        pattern = re.compile(r"consult[ez]?\s+(?:un|votre)\s+comptable", re.IGNORECASE)
        matches = list(pattern.finditer(prompt))
        for match in matches:
            start = max(0, match.start() - 200)
            end = min(len(prompt), match.end() + 200)
            context = prompt[start:end]
            has_comcoi_reference = (
                "ComCoi" in context or
                "communaute-coiffure" in context or
                "/services" in context
            )
            assert has_comcoi_reference, (
                f"Found bare 'consulter un comptable' phrase without ComCoi reference:\n"
                f"...{context}..."
            )

    def test_public_prompt_still_functional(self):
        """
        The public prompt (pre-auth) is separate — it doesn't get the ComCoi-first
        policy (users can't access services yet). It should still be coherent.
        """
        prompt = build_public_system_prompt()
        assert "CoCo" in prompt
        assert len(prompt) > 100  # Not empty


# ── Test 3: detect_comptable_savings — IS salon with high fees ─────────────────

class TestDetectComptableSavings:
    """
    Test the detect_comptable_savings tool executor directly.
    Mocks the DB session to avoid needing a real database.

    Scenario from task spec (TASK-2.11.14 §6):
        - IS salon
        - 1800 €/an honoraires comptable
        - ComCoi IS price = 1116 € HT/an
        - Expected savings ≈ 1800 - 1116 = 684 €
        - 684 > 1116 * 10% = 111.6 → has_savings = True
    """

    def _make_expense_report(self, label: str, amount: float):
        """Helper: make a minimal MonthlyReport mock with one expense."""
        report = MagicMock()
        report.expenses = [{"label": label, "amount_ttc": amount}]
        return report

    @pytest.mark.asyncio
    async def test_is_salon_high_fees_detects_savings(self):
        """IS salon with 1800€/an honoraires → savings ≈ 684€, has_savings=True."""
        from app.services.coco_tools import _tool_detect_comptable_savings

        # 12 months at 150€/month = 1800€/an
        reports = [self._make_expense_report("Honoraires comptable", 150.0) for _ in range(12)]

        mock_salon = MagicMock()
        mock_salon.id = "salon-uuid-1"
        mock_salon.business_type = "SARL"  # IS regime

        mock_db = AsyncMock()

        # First call: get_salon_for_user → returns salon
        salon_result = MagicMock()
        salon_result.scalar_one_or_none.return_value = mock_salon

        # Second call: monthly reports
        reports_result = MagicMock()
        reports_result.scalars.return_value.all.return_value = reports

        mock_db.execute.side_effect = [salon_result, reports_result]

        result = await _tool_detect_comptable_savings(
            {"business_type": "IS"},
            db=mock_db,
            user_id="user-uuid-1",
            screen_context=None,
        )

        assert result["found"] is True
        assert result["has_savings"] is True
        assert result["regime_label"] == "IS"
        assert result["comcoi_price"] == COMCOI_COMPTABLE_IS_HT  # 1116
        # 12 * 150 = 1800€ fees
        assert abs(result["current_annual_fee"] - 1800.0) < 0.01
        # savings = 1800 - 1116 = 684
        assert abs(result["potential_savings"] - 684.0) < 0.01
        assert "recommendation" in result
        assert COMCOI_SERVICES_URL in result.get("services_url", "")

    @pytest.mark.asyncio
    async def test_ir_salon_high_fees_detects_savings(self):
        """IR salon with 1200€/an honoraires → savings ≈ 444€, has_savings=True."""
        from app.services.coco_tools import _tool_detect_comptable_savings

        # 12 months at 100€/month = 1200€/an
        reports = [self._make_expense_report("expert-comptable honoraires", 100.0) for _ in range(12)]

        mock_salon = MagicMock()
        mock_salon.id = "salon-uuid-2"
        mock_salon.business_type = "EI"  # IR regime

        mock_db = AsyncMock()
        salon_result = MagicMock()
        salon_result.scalar_one_or_none.return_value = mock_salon
        reports_result = MagicMock()
        reports_result.scalars.return_value.all.return_value = reports
        mock_db.execute.side_effect = [salon_result, reports_result]

        result = await _tool_detect_comptable_savings(
            {},
            db=mock_db,
            user_id="user-uuid-2",
            screen_context=None,
        )

        assert result["found"] is True
        assert result["has_savings"] is True
        assert result["regime_label"] == "IR"
        assert result["comcoi_price"] == COMCOI_COMPTABLE_IR_HT  # 756
        assert abs(result["current_annual_fee"] - 1200.0) < 0.01
        assert abs(result["potential_savings"] - 444.0) < 0.01

    @pytest.mark.asyncio
    async def test_no_fees_detected_returns_no_savings(self):
        """When no comptable expenses in reports, has_savings=False, found=True."""
        from app.services.coco_tools import _tool_detect_comptable_savings

        # Reports with unrelated expenses
        reports = [MagicMock(expenses=[{"label": "Loyer mensuel", "amount_ttc": 800.0}]) for _ in range(6)]

        mock_salon = MagicMock()
        mock_salon.id = "salon-uuid-3"
        mock_salon.business_type = "EI"

        mock_db = AsyncMock()
        salon_result = MagicMock()
        salon_result.scalar_one_or_none.return_value = mock_salon
        reports_result = MagicMock()
        reports_result.scalars.return_value.all.return_value = reports
        mock_db.execute.side_effect = [salon_result, reports_result]

        result = await _tool_detect_comptable_savings(
            {},
            db=mock_db,
            user_id="user-uuid-3",
            screen_context=None,
        )

        assert result["found"] is True
        assert result["has_savings"] is False
        assert result["current_annual_fee"] == 0.0
        assert result["potential_savings"] == 0.0
        assert "raison" in result or "reason" in result  # explains why no data

    @pytest.mark.asyncio
    async def test_fees_within_buffer_no_savings_flagged(self):
        """
        When fees are only slightly above ComCoi price (within 10% buffer),
        has_savings should be False to avoid noise.

        COMCOI_IR = 756. Buffer = 10%. Threshold = 756 * 1.10 = 831.60.
        Test fees = 800€/an < 831.60 → has_savings = False.
        """
        from app.services.coco_tools import _tool_detect_comptable_savings

        # 800€/an = ~66.67€/month * 12
        reports = [self._make_expense_report("Honoraires comptable", 66.67) for _ in range(12)]

        mock_salon = MagicMock()
        mock_salon.id = "salon-uuid-4"
        mock_salon.business_type = "EI"  # IR = 756

        mock_db = AsyncMock()
        salon_result = MagicMock()
        salon_result.scalar_one_or_none.return_value = mock_salon
        reports_result = MagicMock()
        reports_result.scalars.return_value.all.return_value = reports
        mock_db.execute.side_effect = [salon_result, reports_result]

        result = await _tool_detect_comptable_savings(
            {},
            db=mock_db,
            user_id="user-uuid-4",
            screen_context=None,
        )

        assert result["found"] is True
        # 800 - 756 = 44, 44 <= 756 * 0.10 = 75.6 → no significant savings
        assert result["has_savings"] is False
        # Still gives a recommendation (to compare, not to switch)
        assert "recommendation" in result

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_not_found(self):
        """Unauthenticated call returns found=False."""
        from app.services.coco_tools import _tool_detect_comptable_savings

        mock_db = AsyncMock()
        result = await _tool_detect_comptable_savings(
            {},
            db=mock_db,
            user_id=None,
            screen_context=None,
        )
        assert result["found"] is False


# ── Test 4: coco_config.py constants match Eric's PDF values ──────────────────

class TestCocoConfigConstants:
    """
    Verify that the ComCoi pricing constants match Eric's 2026-04-22 PDF (p4).
    These are the source of truth — if Eric changes his pricing, this test will
    catch any manual update that drifts from the constants.
    """

    def test_ir_price_matches_eric_pdf(self):
        """Eric PDF p4: ComCoi comptabilité IR = 756 € HT/an."""
        assert COMCOI_COMPTABLE_IR_HT == 756, (
            f"Expected 756 (from Eric PDF p4), got {COMCOI_COMPTABLE_IR_HT}"
        )

    def test_is_price_matches_eric_pdf(self):
        """Eric PDF p4: ComCoi comptabilité IS = 1116 € HT/an."""
        assert COMCOI_COMPTABLE_IS_HT == 1_116, (
            f"Expected 1116 (from Eric PDF p4), got {COMCOI_COMPTABLE_IS_HT}"
        )

    def test_buffer_pct_is_ten_percent(self):
        """Buffer is 10% — per task spec requirement."""
        assert COMCOI_SAVINGS_BUFFER_PCT == 0.10, (
            f"Expected 0.10, got {COMCOI_SAVINGS_BUFFER_PCT}"
        )

    def test_contact_email_correct(self):
        """Contact email must match the official ComCoi address."""
        assert COMCOI_CONTACT_EMAIL == "contact@communaute-coiffure.com"

    def test_services_url_correct(self):
        """Services URL must be the partner directory route."""
        assert COMCOI_SERVICES_URL == "/services"


# ── Test 5: detect_comptable_savings — partial year annualisation ──────────────

class TestDetectComptableSavingsAnnualisation:
    """
    When fewer than 12 months are available, fees should be annualised
    by projecting from the available months.
    """

    @pytest.mark.asyncio
    async def test_partial_year_annualised_correctly(self):
        """
        3 months of data at 200€/month → annual projection = 800€/an.
        IR salon: 800 > 756 * 1.10 = 831.6? No → has_savings = False.
        But 3 * 200 = 600, annualised = (600/3) * 12 = 2400€ — wait, that's very high.
        
        Actually: 3 months at 200 = total_fees=600. months_scanned=3.
        annual_fee = (600/3) * 12 = 2400€/an.
        IS: 2400 - 1116 = 1284. 1284 > 1116*0.10=111.6 → has_savings = True.
        """
        from app.services.coco_tools import _tool_detect_comptable_savings

        reports = [
            MagicMock(expenses=[{"label": "Honoraires comptable", "amount_ttc": 200.0}])
            for _ in range(3)
        ]

        mock_salon = MagicMock()
        mock_salon.id = "salon-uuid-5"
        mock_salon.business_type = "SARL"  # IS

        mock_db = AsyncMock()
        salon_result = MagicMock()
        salon_result.scalar_one_or_none.return_value = mock_salon
        reports_result = MagicMock()
        reports_result.scalars.return_value.all.return_value = reports
        mock_db.execute.side_effect = [salon_result, reports_result]

        result = await _tool_detect_comptable_savings(
            {},
            db=mock_db,
            user_id="user-uuid-5",
            screen_context=None,
        )

        # 3 months * 200 = 600, projected to 12 months = 2400
        assert result["found"] is True
        assert abs(result["current_annual_fee"] - 2400.0) < 1.0
        assert result["months_scanned"] == 3
        assert result["has_savings"] is True  # 2400 >> 1116
