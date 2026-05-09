"""
TASK-2.11.8: Multi-Salon Typical-Month Data Isolation Tests

Verifies that salon_config.typical_month_template is correctly scoped:
  - POST typical-month for salon A does NOT bleed into salon B
  - GET salon B config returns null template when only A has data
  - Cross-user access to salon A via salon B's endpoint returns 403/404

WHY inline client per test: asyncpg + session-scoped event_loop in conftest causes
"Future attached to different loop" errors when async generator fixtures span
loop teardown. Pattern matches test_task_1_7_salons.py.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


# ── helpers ───────────────────────────────────────────────────────────────────

MINIMAL_TEMPLATE = {
    "ca_ttc": 8000,
    "team": [],
    "expenses": [],
}


def _client() -> AsyncClient:
    """Return a fresh ASGI test client (not authenticated)."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _register_and_login(client: AsyncClient, email: str) -> str:
    """Register a fresh user and return session token from cookie."""
    await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "name": "Test Isolation",
        },
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    # Cookie is set by the response; httpx client stores it automatically
    return resp.cookies.get("session_token") or ""


async def _create_salon(client: AsyncClient, name: str) -> str:
    """Create a salon (client must already be authenticated) and return its ID."""
    resp = await client.post(
        "/api/salons",
        json={"name": name, "city": "Paris", "business_type": "EURL"},
    )
    assert resp.status_code in (200, 201), f"Create salon '{name}' failed: {resp.text}"
    return resp.json()["id"]


# ── tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_typical_month_per_salon_isolation() -> None:
    """
    Salon A saves typical-month template; Salon B (same user) must return null template.

    This is the exact scenario Eric reported: switching to salon B showed
    salon A's data in the Mon Mois Typique wizard.
    """
    async with _client() as client:
        await _register_and_login(client, "isolation_same_user_a@test.com")

        salon_a_id = await _create_salon(client, "Salon A – isolation")
        salon_b_id = await _create_salon(client, "Salon B – isolation")

        # Post typical-month data to salon A only
        resp = await client.post(
            f"/api/salons/{salon_a_id}/typical-month",
            json=MINIMAL_TEMPLATE,
        )
        assert resp.status_code in (200, 201), f"typical-month POST failed: {resp.text}"

        # Salon A config must have the template
        config_a = (
            await client.get(f"/api/salons/{salon_a_id}/config")
        ).json()
        assert config_a.get("typical_month_template") is not None, (
            "Salon A should have a typical_month_template after POST"
        )

        # Salon B config must NOT have A's template — the isolation assertion
        config_b = (
            await client.get(f"/api/salons/{salon_b_id}/config")
        ).json()
        assert config_b.get("typical_month_template") is None, (
            "Salon B must NOT inherit Salon A's typical_month_template (data isolation bug)"
        )


@pytest.mark.asyncio
async def test_cross_user_salon_isolation() -> None:
    """
    User B must not be able to read or overwrite User A's salon typical-month template.
    Verifies no accidental cross-user data leak.
    """
    async with _client() as client_a, _client() as client_b:
        await _register_and_login(client_a, "user_a_cross_iso@test.com")
        await _register_and_login(client_b, "user_b_cross_iso@test.com")

        salon_a_id = await _create_salon(client_a, "Salon UserA cross")

        # User A posts a template to their salon
        resp = await client_a.post(
            f"/api/salons/{salon_a_id}/typical-month",
            json=MINIMAL_TEMPLATE,
        )
        assert resp.status_code in (200, 201)

        # User B tries to read User A's salon config — should be 403 or 404
        resp_b_read = await client_b.get(f"/api/salons/{salon_a_id}/config")
        assert resp_b_read.status_code in (403, 404), (
            f"Cross-user config read must be blocked, got {resp_b_read.status_code}"
        )

        # User B tries to POST typical-month to User A's salon — should be 403 or 404
        resp_b_post = await client_b.post(
            f"/api/salons/{salon_a_id}/typical-month",
            json=MINIMAL_TEMPLATE,
        )
        assert resp_b_post.status_code in (403, 404), (
            f"Cross-user typical-month POST must be blocked, got {resp_b_post.status_code}"
        )


@pytest.mark.asyncio
async def test_per_salon_template_independent_updates() -> None:
    """
    Saving template for salon B must not overwrite salon A's template.
    """
    async with _client() as client:
        await _register_and_login(client, "isolation_update_2@test.com")

        salon_a_id = await _create_salon(client, "Salon A – updates")
        salon_b_id = await _create_salon(client, "Salon B – updates")

        template_a = {**MINIMAL_TEMPLATE, "ca_ttc": 10000}
        template_b = {**MINIMAL_TEMPLATE, "ca_ttc": 5000}

        resp_a_post = await client.post(f"/api/salons/{salon_a_id}/typical-month", json=template_a)
        assert resp_a_post.status_code in (200, 201), f"Salon A POST failed: {resp_a_post.text}"
        resp_b_post = await client.post(f"/api/salons/{salon_b_id}/typical-month", json=template_b)
        assert resp_b_post.status_code in (200, 201), f"Salon B POST failed: {resp_b_post.text}"

        config_a = (await client.get(f"/api/salons/{salon_a_id}/config")).json()
        assert config_a.get("typical_month_template") is not None
        assert config_a["typical_month_template"].get("ca_ttc") == 10000, (
            "Salon A template must not be overwritten by salon B's save"
        )

        config_b = (await client.get(f"/api/salons/{salon_b_id}/config")).json()
        assert config_b.get("typical_month_template") is not None
        assert config_b["typical_month_template"].get("ca_ttc") == 5000, (
            "Salon B template ca_ttc must be 5000, not Salon A's 10000"
        )
