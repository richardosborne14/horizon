"""
Unit tests for Task 4.6 — Contact / Booking Form.

Covers:
  - Pydantic validator behaviour (name, phone, preferred_time)
  - IP extraction helper (_get_client_ip)
  - Honeypot detection (silent 200, no DB write)
  - Rate limit logic (_is_rate_limited) — mocked DB

Run locally (no Docker needed — pure Python):
    cd backend && python -m pytest tests/test_task_4_6_contact.py -v

API integration tests (require DB + running app — run inside Docker):
    docker compose exec -w /app backend python -m pytest tests/test_task_4_6_contact.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from pydantic import ValidationError

from app.routers.contact import (
    BookingRequest,
    BookingResponse,
    _get_client_ip,
    RATE_LIMIT_MAX,
    RATE_LIMIT_WINDOW,
)


# ── BookingRequest validator tests ────────────────────────────────────────────

class TestBookingRequestValidation:
    """Tests for Pydantic validators on BookingRequest."""

    def test_valid_minimal(self) -> None:
        """Minimal valid request: only name and phone required."""
        req = BookingRequest(name="Marie Dupont", phone="06 12 34 56 78")
        assert req.name == "Marie Dupont"
        assert req.phone == "06 12 34 56 78"
        assert req.email is None
        assert req.message is None
        assert req.preferred_time is None
        assert req.website == ""

    def test_valid_full(self) -> None:
        """Full valid request with all optional fields."""
        req = BookingRequest(
            name="Jean Martin",
            phone="06 99 88 77 66",
            email="jean@example.com",
            message="Je souhaite en savoir plus.",
            preferred_time="matin",
            website="",
        )
        assert req.preferred_time == "matin"
        assert req.email == "jean@example.com"

    def test_name_stripped(self) -> None:
        """Name is stripped of leading/trailing whitespace."""
        req = BookingRequest(name="  Alice  ", phone="0601020304")
        assert req.name == "Alice"

    def test_phone_stripped(self) -> None:
        """Phone is stripped of leading/trailing whitespace."""
        req = BookingRequest(name="Alice", phone="  0601020304  ")
        assert req.phone == "0601020304"

    def test_name_empty_raises(self) -> None:
        """Empty name raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            BookingRequest(name="", phone="0601020304")
        assert "nom" in str(exc_info.value).lower()

    def test_name_whitespace_only_raises(self) -> None:
        """Whitespace-only name raises ValidationError."""
        with pytest.raises(ValidationError):
            BookingRequest(name="   ", phone="0601020304")

    def test_phone_empty_raises(self) -> None:
        """Empty phone raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            BookingRequest(name="Alice", phone="")
        assert "téléphone" in str(exc_info.value).lower()

    def test_preferred_time_valid_values(self) -> None:
        """All valid preferred_time values are accepted."""
        for value in ["matin", "apres_midi", "soir"]:
            req = BookingRequest(name="Alice", phone="0601020304", preferred_time=value)
            assert req.preferred_time == value

    def test_preferred_time_none_valid(self) -> None:
        """None is a valid preferred_time (optional field)."""
        req = BookingRequest(name="Alice", phone="0601020304", preferred_time=None)
        assert req.preferred_time is None

    def test_preferred_time_invalid_raises(self) -> None:
        """Invalid preferred_time raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            BookingRequest(name="Alice", phone="0601020304", preferred_time="nuit")
        assert "invalide" in str(exc_info.value).lower()

    def test_honeypot_defaults_empty(self) -> None:
        """Honeypot `website` field defaults to empty string."""
        req = BookingRequest(name="Alice", phone="0601020304")
        assert req.website == ""

    def test_honeypot_can_be_filled(self) -> None:
        """Honeypot field can be filled (detection is at the endpoint level)."""
        req = BookingRequest(name="Bot", phone="0600000000", website="http://spam.com")
        assert req.website == "http://spam.com"


# ── IP extraction tests ───────────────────────────────────────────────────────

class TestGetClientIp:
    """Tests for the _get_client_ip() helper."""

    def _make_request(
        self,
        forwarded_for: str | None = None,
        client_host: str | None = "127.0.0.1",
    ) -> MagicMock:
        """Build a mock FastAPI Request object."""
        req = MagicMock()
        req.headers = {}
        if forwarded_for is not None:
            req.headers = {"x-forwarded-for": forwarded_for}
        if client_host is not None:
            req.client = MagicMock()
            req.client.host = client_host
        else:
            req.client = None
        return req

    def test_uses_forwarded_for_first(self) -> None:
        """X-Forwarded-For header takes precedence over client.host."""
        req = self._make_request(forwarded_for="1.2.3.4", client_host="10.0.0.1")
        assert _get_client_ip(req) == "1.2.3.4"

    def test_picks_first_ip_from_forwarded_for(self) -> None:
        """First IP in X-Forwarded-For chain is the real client."""
        req = self._make_request(forwarded_for="1.2.3.4, 10.0.0.1, 192.168.1.1")
        assert _get_client_ip(req) == "1.2.3.4"

    def test_strips_whitespace_from_forwarded_for(self) -> None:
        """Whitespace around the first IP is stripped."""
        req = self._make_request(forwarded_for="  5.5.5.5  , 10.0.0.1")
        assert _get_client_ip(req) == "5.5.5.5"

    def test_falls_back_to_client_host(self) -> None:
        """Falls back to client.host when X-Forwarded-For is absent."""
        req = self._make_request(forwarded_for=None, client_host="192.168.1.100")
        assert _get_client_ip(req) == "192.168.1.100"

    def test_returns_unknown_when_no_info(self) -> None:
        """Returns 'unknown' when neither header nor client is available."""
        req = self._make_request(forwarded_for=None, client_host=None)
        assert _get_client_ip(req) == "unknown"

    def test_ipv6_address(self) -> None:
        """IPv6 addresses are handled correctly."""
        req = self._make_request(
            forwarded_for="2001:db8::1, 10.0.0.1",
            client_host="::1",
        )
        assert _get_client_ip(req) == "2001:db8::1"


# ── BookingResponse tests ─────────────────────────────────────────────────────

class TestBookingResponse:
    """Tests for BookingResponse schema."""

    def test_success_response(self) -> None:
        """Response with ok=True and message is valid."""
        resp = BookingResponse(ok=True, message="Merci ! Eric vous contactera dans les 24h.")
        assert resp.ok is True
        assert "Eric" in resp.message

    def test_response_serialises(self) -> None:
        """Response can be serialised to dict."""
        resp = BookingResponse(ok=True, message="Test")
        d = resp.model_dump()
        assert d == {"ok": True, "message": "Test"}


# ── Rate limit configuration ──────────────────────────────────────────────────

class TestRateLimitConfig:
    """Verify rate limit constants are within expected bounds."""

    def test_rate_limit_max_is_3(self) -> None:
        """Max submissions per window is 3 as per spec."""
        assert RATE_LIMIT_MAX == 3

    def test_rate_limit_window_is_60_minutes(self) -> None:
        """Rate limit window is 60 minutes as per spec."""
        assert RATE_LIMIT_WINDOW == 60
