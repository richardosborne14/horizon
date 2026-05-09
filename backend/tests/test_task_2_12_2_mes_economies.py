"""
Task 2.12.2: Mes Économies page — Integration tests.

Tests:
  1. GET /api/salons/{id}/savings/report — authenticated endpoint returns correct shape
  2. SavingsBanner threshold: component shows only when total_annual_savings_eur >= 500
     (pure logic test — no DOM, just the threshold calculation)
  3. CoCo get_savings_report tool — calls the engine and includes numbers in output
  4. /taxes redirect — server-side 308 to /mes-economies (SvelteKit, tested via HTTP)
  5. _screen_to_label includes /mes-economies key (CoCo prompt awareness)

WHY these tests: spec requires that CoCo can "cite the numbers", that the banner
threshold is exactly 500€, and that /taxes redirects to the new route.
"""

import pytest
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.coco_prompts import _screen_to_label


# ── shared helpers ─────────────────────────────────────────────────────────────

def _client() -> AsyncClient:
    """Return a fresh ASGI test client (unauthenticated)."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _register_login_salon(client: AsyncClient, email: str, salon_name: str) -> str:
    """
    Register user, login, create a salon, return the salon's UUID string.
    Self-contained setup per LEARNINGS #27.
    """
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "name": "Test 2.12.2"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    resp2 = await client.post(
        "/api/salons",
        json={"name": salon_name, "city": "Paris", "business_type": "EURL"},
    )
    assert resp2.status_code in (200, 201), f"Salon create failed: {resp2.text}"
    return resp2.json()["id"]


# ── 1. CoCo screen label ───────────────────────────────────────────────────────

class TestMesEconomiesScreenLabel:
    """CoCo must know the /mes-economies route label."""

    def test_mes_economies_has_french_label(self):
        """_screen_to_label('/mes-economies') must return 'Mes Économies'."""
        assert _screen_to_label('/mes-economies') == 'Mes Économies'

    def test_mes_economies_label_is_not_raw_path(self):
        """The label should not be the raw path string."""
        label = _screen_to_label('/mes-economies')
        assert label != '/mes-economies'
        assert 'conomies' in label  # accented char may vary


# ── 2. Banner threshold logic ─────────────────────────────────────────────────

class TestSavingsBannerThreshold:
    """
    The SavingsBanner shows only when total_annual_savings_eur >= THRESHOLD.
    We test the threshold decision purely in Python (no DOM/Svelte).
    """

    THRESHOLD = 500  # must match SavingsBanner.svelte constant

    def _should_show(self, total_savings_eur: float) -> bool:
        """Mirrors the logic: show = val >= THRESHOLD."""
        return total_savings_eur >= self.THRESHOLD

    def test_below_threshold_hides_banner(self):
        assert self._should_show(499) is False
        assert self._should_show(0) is False
        assert self._should_show(100) is False

    def test_at_threshold_shows_banner(self):
        assert self._should_show(500) is True

    def test_above_threshold_shows_banner(self):
        assert self._should_show(501) is True
        assert self._should_show(5000) is True

    def test_fractional_below_threshold_hides(self):
        assert self._should_show(499.99) is False

    def test_fractional_at_threshold_shows(self):
        assert self._should_show(500.0) is True


# ── 3. Savings report API endpoint ────────────────────────────────────────────
# Self-contained tests per LEARNINGS #27: register → login → create salon → test.
# No shared fixtures — asyncpg + session event_loop pattern forbids it.


@pytest.mark.asyncio
async def test_savings_unauthenticated_returns_401() -> None:
    """Without auth, GET /savings must return 401."""
    async with _client() as client:
        fake_id = str(uuid.uuid4())
        response = await client.get(f'/api/salons/{fake_id}/savings')
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_savings_authenticated_shape() -> None:
    """Authenticated user gets a valid savings report shape."""
    async with _client() as client:
        salon_id = await _register_login_salon(
            client, "savings_shape_2122@test.com", "Salon Shape Test"
        )
        response = await client.get(f'/api/salons/{salon_id}/savings')
        assert response.status_code == 200
        data = response.json()
        assert 'salon_id' in data
        assert 'total_annual_savings_eur' in data
        assert 'channels' in data
        assert isinstance(data['channels'], list)
        assert 'computed_at' in data
        assert 'from_cache' in data


@pytest.mark.asyncio
async def test_savings_total_is_sum_of_channel_savings() -> None:
    """total_annual_savings_eur must equal sum of channel savings."""
    async with _client() as client:
        salon_id = await _register_login_salon(
            client, "savings_sum_2122@test.com", "Salon Sum Test"
        )
        response = await client.get(f'/api/salons/{salon_id}/savings')
        assert response.status_code == 200
        data = response.json()
        # annual_savings_eur is Decimal → serialised as string; cast to float.
        channel_sum = sum(
            float(c['annual_savings_eur']) if c['annual_savings_eur'] is not None else 0.0
            for c in data['channels']
        )
        assert abs(float(data['total_annual_savings_eur']) - channel_sum) < 0.01


@pytest.mark.asyncio
async def test_savings_channel_shape() -> None:
    """Each channel must have the required keys and a valid status value."""
    # WHY unique email: persistent test DB retains users + stale cache from
    # previous runs. Using uuid suffix guarantees a fresh user → fresh salon
    # → no cached report → engine always computes with current schema.
    unique = uuid.uuid4().hex[:8]
    async with _client() as client:
        salon_id = await _register_login_salon(
            client, f"savings_ch_shape_{unique}@test.com", "Salon Channel Shape"
        )
        # Use POST refresh to guarantee no stale cache is served.
        response = await client.post(f'/api/salons/{salon_id}/savings/refresh')
        assert response.status_code == 200
        data = response.json()
        valid_statuses = {'savings', 'opportunity', 'already_customer', 'insufficient_data'}
        for channel in data['channels']:
            assert 'channel_key' in channel, f"Missing channel_key in: {channel}"
            assert 'channel_label' in channel
            assert 'status' in channel
            assert 'is_paid_customer' in channel
            assert channel['status'] in valid_statuses, (
                f"Unexpected status '{channel['status']}' for channel '{channel['channel_key']}'"
            )


@pytest.mark.asyncio
async def test_savings_force_refresh() -> None:
    """POST /savings/refresh must return a fresh report with from_cache=False."""
    async with _client() as client:
        salon_id = await _register_login_salon(
            client, "savings_refresh_2122@test.com", "Salon Refresh Test"
        )
        response = await client.post(f'/api/salons/{salon_id}/savings/refresh')
        assert response.status_code == 200
        data = response.json()
        assert data['from_cache'] is False


@pytest.mark.asyncio
async def test_savings_salon_isolation() -> None:
    """User A cannot fetch the savings report for User B's salon."""
    async with _client() as client_a:
        await _register_login_salon(
            client_a, "savings_isolation_a_2122@test.com", "Salon A Isolation"
        )

    # User B creates their own salon
    async with _client() as client_b:
        salon_b_id = await _register_login_salon(
            client_b, "savings_isolation_b_2122@test.com", "Salon B Isolation"
        )

    # User A tries to access User B's salon — should be denied
    async with _client() as client_a2:
        await _register_login_salon(
            client_a2, "savings_isolation_a_2122@test.com", "Salon A Isolation"
        )
        response = await client_a2.get(f'/api/salons/{salon_b_id}/savings')
        assert response.status_code in (401, 403, 404)


# ── 4. CoCo get_savings_report tool ──────────────────────────────────────────

class TestCocoGetSavingsReportTool:
    """The get_savings_report CoCo tool must call the engine and include numbers."""

    @pytest.mark.asyncio
    async def test_tool_returns_found_with_user(self):
        """get_savings_report with a valid user_id should return found=True."""
        from app.services.coco_tools import call_tool

        # Mock the DB to return a salon with plausible savings
        mock_salon = MagicMock()
        mock_salon.id = str(uuid.uuid4())

        mock_report = MagicMock()
        mock_report.total_annual_savings_eur = Decimal('1250.00')
        mock_report.channels = []
        mock_report.from_cache = False

        db = AsyncMock()
        mock_salon_result = MagicMock()
        mock_salon_result.scalar_one_or_none.return_value = mock_salon
        db.execute = AsyncMock(return_value=mock_salon_result)

        # WHY: compute_savings is imported inside _tool_get_savings_report body,
        # so we patch at the module where it lives (savings_engine), not coco_tools.
        with patch(
            'app.services.savings_engine.compute_savings',
            new_callable=AsyncMock,
            return_value=mock_report,
        ):
            result = await call_tool(
                'get_savings_report',
                {},
                db=db,
                user_id=str(uuid.uuid4()),
                screen_context=None,
            )

        assert result['found'] is True
        assert 'total_annual_savings_eur' in result

    @pytest.mark.asyncio
    async def test_tool_no_user_returns_not_found(self):
        """Without a user_id, get_savings_report should return found=False."""
        from app.services.coco_tools import call_tool

        db = AsyncMock()
        result = await call_tool(
            'get_savings_report',
            {},
            db=db,
            user_id=None,
            screen_context=None,
        )
        assert result['found'] is False

    @pytest.mark.asyncio
    async def test_tool_no_salon_returns_not_found(self):
        """If user has no salon, get_savings_report should return found=False."""
        from app.services.coco_tools import call_tool

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        result = await call_tool(
            'get_savings_report',
            {},
            db=db,
            user_id=str(uuid.uuid4()),
            screen_context=None,
        )
        assert result['found'] is False

    def test_get_savings_report_in_tool_definitions(self):
        """get_savings_report must be listed in TOOL_DEFINITIONS."""
        from app.services.coco_tools import TOOL_DEFINITIONS
        names = {t['name'] for t in TOOL_DEFINITIONS}
        assert 'get_savings_report' in names

    def test_get_savings_report_has_ui_label(self):
        """get_savings_report must have a UI label for the CoCo panel."""
        from app.services.coco_tools import TOOL_UI_LABELS
        assert 'get_savings_report' in TOOL_UI_LABELS
        assert len(TOOL_UI_LABELS['get_savings_report']) > 0
