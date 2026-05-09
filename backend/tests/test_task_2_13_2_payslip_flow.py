"""
Tests for Task 2.13.2 — Payslip variables email + GET /submissions endpoint.

Coverage:
  - payslip_email formatting helpers (_fmt_period, _fmt_pct, _fmt_amount, _fmt_date, _fmt_absence)
  - payslip_email.send_variables_email idempotency (no-op when no pending submissions)
  - payslip_email HTML/text composition
  - GET /api/salons/{salon_id}/payslip/submissions endpoint (self-contained integration tests)
  - CoCo TOOL_DEFINITIONS includes get_fiches_salaire_status
  - coco_prompts.build_system_prompt includes _PAYSLIP_FIRST_RULE
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.payslip_email import (
    _fmt_absence,
    _fmt_amount,
    _fmt_date,
    _fmt_period,
    _fmt_pct,
    _compose_variables_email_html,
    _compose_variables_email_text,
)


# ── Self-contained helpers for integration tests ──────────────────────────────


def _api_client() -> AsyncClient:
    """Return a fresh ASGI test client (unauthenticated)."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _register_login(client: AsyncClient, email: str) -> None:
    """Register and log in a user (sets session cookie on client)."""
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "name": "Test Payslip"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"


async def _create_salon(client: AsyncClient, name: str = "Salon Test 2.13.2") -> str:
    """Create a salon and return its ID (client must be authenticated)."""
    resp = await client.post(
        "/api/salons",
        json={"name": name, "city": "Paris", "business_type": "EURL"},
    )
    assert resp.status_code in (200, 201), f"Create salon failed: {resp.text}"
    return resp.json()["id"]


# ── Formatting helpers ────────────────────────────────────────────────────────


class TestFmtPeriod:
    """_fmt_period: month+year → French label."""

    def test_known_month(self) -> None:
        """Formats April 2026 correctly."""
        assert _fmt_period(4, 2026) == "Avril 2026"

    def test_january(self) -> None:
        """January uses Janvier."""
        assert _fmt_period(1, 2025) == "Janvier 2025"

    def test_december(self) -> None:
        """December uses Décembre."""
        assert _fmt_period(12, 2026) == "Décembre 2026"

    def test_all_months_present(self) -> None:
        """All 12 months produce non-empty labels."""
        for month in range(1, 13):
            label = _fmt_period(month, 2026)
            assert label.endswith("2026")
            assert len(label.split()) == 2  # "MonthName Year"

    def test_unknown_month_fallback(self) -> None:
        """Unknown month falls back to month number as string."""
        assert "99" in _fmt_period(99, 2026)


class TestFmtDate:
    """_fmt_date: date → dd/mm/yyyy or "—"."""

    def test_none_returns_dash(self) -> None:
        """None returns "—"."""
        assert _fmt_date(None) == "—"

    def test_date_formats_french(self) -> None:
        """date object formats as dd/mm/yyyy."""
        assert _fmt_date(date(2026, 4, 15)) == "15/04/2026"

    def test_first_of_month(self) -> None:
        """First-of-month pads day correctly."""
        assert _fmt_date(date(2026, 1, 1)) == "01/01/2026"


class TestFmtAmount:
    """_fmt_amount: Decimal → "1 234,56 €" or "—"."""

    def test_none_returns_dash(self) -> None:
        assert _fmt_amount(None) == "—"

    def test_simple_amount(self) -> None:
        """Amount has euro sign and comma decimal separator."""
        result = _fmt_amount(Decimal("1234.56"))
        assert "€" in result
        assert "," in result
        assert "1" in result

    def test_zero(self) -> None:
        """Zero still renders with euro sign."""
        result = _fmt_amount(Decimal("0"))
        assert "€" in result


class TestFmtPct:
    """_fmt_pct: Decimal → "12,50 %" or "—"."""

    def test_none_returns_dash(self) -> None:
        assert _fmt_pct(None) == "—"

    def test_percentage_has_comma(self) -> None:
        """Uses comma decimal separator."""
        result = _fmt_pct(Decimal("12.5"))
        assert "," in result
        assert "%" in result

    def test_zero(self) -> None:
        result = _fmt_pct(Decimal("0"))
        assert "0,00" in result


class TestFmtAbsence:
    """_fmt_absence: (du, au) → date range or "—"."""

    def test_both_none_returns_dash(self) -> None:
        assert _fmt_absence(None, None) == "—"

    def test_both_dates_formats_range(self) -> None:
        """Returns "dd/mm/yyyy au dd/mm/yyyy" when both set."""
        result = _fmt_absence(date(2026, 4, 1), date(2026, 4, 7))
        assert "01/04/2026" in result
        assert "07/04/2026" in result
        assert "au" in result

    def test_only_start_date(self) -> None:
        """Partial range still renders (du = date, au = None → "—")."""
        result = _fmt_absence(date(2026, 4, 1), None)
        assert "01/04/2026" in result


# ── Email composition ─────────────────────────────────────────────────────────


class TestEmailComposition:
    """HTML and text email composition helpers."""

    def _make_submission(self) -> MagicMock:
        """Build a minimal mock PayslipSubmission."""
        sub = MagicMock()
        sub.prime_conventionnelle_pct = Decimal("5.00")
        sub.ca_services_ht = Decimal("3000.00")
        sub.prime_revente_pct = Decimal("10.00")
        sub.ca_revente_ht = Decimal("500.00")
        sub.absence_conges_du = None
        sub.absence_conges_au = None
        sub.absence_maladie_du = None
        sub.absence_maladie_au = None
        sub.absence_injustifiee_du = None
        sub.absence_injustifiee_au = None
        sub.commentaire = None
        return sub

    def _make_employee(self) -> MagicMock:
        """Build a minimal mock Employee."""
        emp = MagicMock()
        emp.name = "Marie Dupont"
        emp.contract_type = "cdi"
        emp.role_type = "salarie"
        return emp

    def _make_salon(self) -> MagicMock:
        """Build a minimal mock Salon."""
        salon = MagicMock()
        salon.name = "Salon de la Paix"
        salon.contact_phone = "+33 6 12 34 56 78"
        return salon

    def test_html_contains_employee_name(self) -> None:
        """HTML body includes the employee's name."""
        sub = self._make_submission()
        emp = self._make_employee()
        salon = self._make_salon()
        html = _compose_variables_email_html(
            [(sub, emp)], salon, "patron@test.fr", "Avril 2026"
        )
        assert "Marie Dupont" in html

    def test_html_contains_salon_name(self) -> None:
        """HTML body includes the salon name in the heading."""
        sub = self._make_submission()
        emp = self._make_employee()
        salon = self._make_salon()
        html = _compose_variables_email_html(
            [(sub, emp)], salon, "patron@test.fr", "Avril 2026"
        )
        assert "Salon de la Paix" in html

    def test_html_contains_period(self) -> None:
        """HTML body includes the period label."""
        sub = self._make_submission()
        emp = self._make_employee()
        salon = self._make_salon()
        html = _compose_variables_email_html(
            [(sub, emp)], salon, "patron@test.fr", "Avril 2026"
        )
        assert "Avril 2026" in html

    def test_text_contains_employee_name(self) -> None:
        """Plain text body includes the employee's name."""
        sub = self._make_submission()
        emp = self._make_employee()
        salon = self._make_salon()
        text = _compose_variables_email_text(
            [(sub, emp)], salon, "patron@test.fr", "Avril 2026"
        )
        assert "Marie Dupont" in text

    def test_text_contains_prime_data(self) -> None:
        """Plain text body includes prime conventionnelle line."""
        sub = self._make_submission()
        emp = self._make_employee()
        salon = self._make_salon()
        text = _compose_variables_email_text(
            [(sub, emp)], salon, "patron@test.fr", "Avril 2026"
        )
        assert "Prime conventionnelle" in text

    def test_text_multiple_employees(self) -> None:
        """Both employees appear in text body."""
        sub = self._make_submission()
        emp1 = self._make_employee()
        emp2 = MagicMock()
        emp2.name = "Jean Martin"
        emp2.contract_type = "cdd"
        emp2.role_type = "salarie"
        salon = self._make_salon()
        text = _compose_variables_email_text(
            [(sub, emp1), (sub, emp2)], salon, "patron@test.fr", "Mai 2026"
        )
        assert "Marie Dupont" in text
        assert "Jean Martin" in text


# ── send_variables_email idempotency ─────────────────────────────────────────


class TestSendVariablesEmailIdempotency:
    """send_variables_email: no-op when no paid_pending_email submissions."""

    @pytest.mark.asyncio
    async def test_empty_ids_returns_false(self) -> None:
        """Empty submission_ids returns False immediately."""
        from app.services.payslip_email import send_variables_email

        db = AsyncMock()
        result = await send_variables_email([], db)
        assert result is False

    @pytest.mark.asyncio
    async def test_already_emailed_is_no_op(self) -> None:
        """If DB query returns no paid_pending_email rows, returns True (idempotent)."""
        from app.services.payslip_email import send_variables_email
        from sqlalchemy.engine import Result

        db = AsyncMock()
        # Simulate DB returning empty result (already emailed or not found)
        mock_result = MagicMock(spec=Result)
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        result = await send_variables_email(["some-uuid"], db)
        # Returns True (idempotent no-op) when nothing to send
        assert result is True


# ── GET /submissions endpoint (self-contained integration tests) ──────────────


@pytest.mark.asyncio
async def test_submissions_invalid_month_returns_422() -> None:
    """month=13 returns 422 Unprocessable Entity."""
    async with _api_client() as client:
        await _register_login(client, "payslip_month_422_a@test.com")
        salon_id = await _create_salon(client, "Salon PayslipTest-422a")
        resp = await client.get(
            f"/api/salons/{salon_id}/payslip/submissions?month=13&year=2026"
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_submissions_month_zero_returns_422() -> None:
    """month=0 returns 422 Unprocessable Entity."""
    async with _api_client() as client:
        await _register_login(client, "payslip_month_zero_a@test.com")
        salon_id = await _create_salon(client, "Salon PayslipTest-zero")
        resp = await client.get(
            f"/api/salons/{salon_id}/payslip/submissions?month=0&year=2026"
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_submissions_unauthenticated_returns_401() -> None:
    """Without auth cookie returns 401."""
    async with _api_client() as authed_client:
        await _register_login(authed_client, "payslip_auth_owner@test.com")
        salon_id = await _create_salon(authed_client, "Salon PayslipTest-auth")

    # Fresh unauthenticated client
    async with _api_client() as anon_client:
        resp = await anon_client.get(
            f"/api/salons/{salon_id}/payslip/submissions?month=4&year=2026"
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_submissions_valid_period_returns_200() -> None:
    """Valid month/year returns 200 with expected response shape."""
    async with _api_client() as client:
        await _register_login(client, "payslip_valid_period@test.com")
        salon_id = await _create_salon(client, "Salon PayslipTest-valid")
        resp = await client.get(
            f"/api/salons/{salon_id}/payslip/submissions?month=4&year=2026"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "dossier_status" in data
        assert "salaried_employees" in data
        assert "submissions" in data
        assert "is_ae" in data
        assert isinstance(data["salaried_employees"], list)
        assert isinstance(data["submissions"], list)


@pytest.mark.asyncio
async def test_submissions_dossier_status_not_started_for_new_salon() -> None:
    """When no dossier row exists, dossier_status is 'not_started'."""
    async with _api_client() as client:
        await _register_login(client, "payslip_no_dossier@test.com")
        salon_id = await _create_salon(client, "Salon PayslipTest-nodossier")
        resp = await client.get(
            f"/api/salons/{salon_id}/payslip/submissions?month=4&year=2026"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dossier_status"] == "not_started"


# ── CoCo TOOL_DEFINITIONS count ───────────────────────────────────────────────


class TestCocoToolCount:
    """TOOL_DEFINITIONS must include get_fiches_salaire_status."""

    def test_tool_definition_exists(self) -> None:
        """get_fiches_salaire_status is in TOOL_DEFINITIONS."""
        from app.services.coco_tools import TOOL_DEFINITIONS
        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "get_fiches_salaire_status" in names

    def test_tool_has_required_schema(self) -> None:
        """The tool definition has correct structure."""
        from app.services.coco_tools import TOOL_DEFINITIONS
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "get_fiches_salaire_status")
        assert "description" in tool
        assert "input_schema" in tool
        assert tool["input_schema"]["type"] == "object"

    def test_call_tool_dispatch_includes_tool(self) -> None:
        """The tool is in TOOL_UI_LABELS."""
        from app.services.coco_tools import TOOL_UI_LABELS
        assert "get_fiches_salaire_status" in TOOL_UI_LABELS


# ── CoCo prompt payslip rule ──────────────────────────────────────────────────


class TestCocoPromptPayslipRule:
    """build_system_prompt includes the payslip-first routing rule."""

    def test_payslip_rule_in_prompt(self) -> None:
        """The payslip routing rule is present in the authenticated prompt."""
        from app.services.coco_prompts import build_system_prompt
        prompt = build_system_prompt()
        assert "get_fiches_salaire_status" in prompt
        assert "RÈGLE FICHES DE SALAIRE" in prompt

    def test_payslip_rule_after_savings_rule(self) -> None:
        """The payslip rule appears after the savings rule in the prompt."""
        from app.services.coco_prompts import build_system_prompt
        prompt = build_system_prompt()
        savings_pos = prompt.index("RÈGLE ÉCONOMIES")
        payslip_pos = prompt.index("RÈGLE FICHES DE SALAIRE")
        assert payslip_pos > savings_pos
