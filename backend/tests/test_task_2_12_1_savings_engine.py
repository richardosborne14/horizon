"""
Tests for TASK-2.12.1: Savings engine + cache.

Covers:
- GET /api/salons/{id}/savings returns correct structure
- All six channels are present in response
- assurance + site_web channels always have null annual_savings_eur
- comptable channel always has a computed savings figure
- AE salon has statut_juridique savings; non-AE does not
- total_annual_savings_eur excludes opportunity channels
- Cache: second call returns from_cache=True
- POST /savings/refresh returns from_cache=False
- 401 for unauthenticated requests
- 404 for wrong user's salon

Pattern: ASGITransport — no real HTTP socket needed.
WHY asynccontextmanager: httpx AsyncClient tracks state (UNOPENED/OPENED/CLOSED).
Making requests before `async with` raises "Cannot open a client instance more than once".
"""

import uuid
import pytest
from contextlib import asynccontextmanager
from httpx import AsyncClient, ASGITransport

from app.main import app

SMOKE_EMAIL = "smoketest@comcoi.fr"
SMOKE_PASS = "Password123!"


# ── Helpers ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def _authed_client(email: str = SMOKE_EMAIL, password: str = SMOKE_PASS):
    """
    Async context manager yielding an ASGI client authenticated as the given user.

    Args:
        email:    User email.
        password: User password.

    Yields:
        Authenticated AsyncClient.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, f"Login failed: {r.text}"
        client.cookies.update(r.cookies)
        yield client


@asynccontextmanager
async def _register_and_login(email: str):
    """
    Register a new test user and yield an authenticated ASGI client.

    Args:
        email: Unique test email.

    Yields:
        Authenticated AsyncClient for the new user.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/auth/register", json={
            "email": email,
            "password": "Test1234!",
            "name": "Test Savings",
        })
        assert r.status_code == 201, f"Register failed: {r.text}"
        r = await client.post("/api/auth/login", json={"email": email, "password": "Test1234!"})
        assert r.status_code == 200, f"Login failed: {r.text}"
        client.cookies.update(r.cookies)
        yield client


async def _get_smoke_salon_id(client: AsyncClient) -> str:
    """
    Return the first salon ID for the authenticated user.

    Args:
        client: Authenticated ASGI client.

    Returns:
        Salon UUID string.
    """
    r = await client.get("/api/salons")
    assert r.status_code == 200, f"Get salons failed: {r.text}"
    salons = r.json()
    assert len(salons) > 0, "Smoke test user has no salons"
    return salons[0]["id"]


async def _create_salon(client: AsyncClient, business_type: str = "auto_micro") -> str:
    """
    Create a salon of the given business type and return its ID.

    Args:
        client:        Authenticated ASGI client.
        business_type: Business type string.

    Returns:
        Salon UUID string.
    """
    r = await client.post("/api/salons", json={
        "name": f"Salon Test Savings {uuid.uuid4().hex[:6]}",
        "business_type": business_type,
    })
    assert r.status_code == 201, f"Create salon failed: {r.text}"
    return r.json()["id"]


# ── Tests ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_savings_report_structure():
    """GET /api/salons/{id}/savings returns SavingsReport with all 6 channels."""
    async with _authed_client() as client:
        salon_id = await _get_smoke_salon_id(client)
        r = await client.get(f"/api/salons/{salon_id}/savings")
        assert r.status_code == 200, f"Savings report failed: {r.text}"

        data = r.json()
        assert data["salon_id"] == salon_id
        assert "channels" in data
        assert "total_annual_savings_eur" in data
        assert "computed_at" in data
        assert isinstance(data["channels"], list)

        channel_ids = [ch["channel_key"] for ch in data["channels"]]
        for expected_id in ["fiches_paie", "comptable", "produits", "statut_juridique", "assurance", "site_web"]:
            assert expected_id in channel_ids, f"Missing channel: {expected_id}"


@pytest.mark.asyncio
async def test_savings_channel_fields():
    """Each channel has required fields: channel_key, channel_label, is_paid_customer."""
    async with _authed_client() as client:
        salon_id = await _get_smoke_salon_id(client)
        r = await client.get(f"/api/salons/{salon_id}/savings")
        assert r.status_code == 200

        for ch in r.json()["channels"]:
            assert "channel_key" in ch
            assert "channel_label" in ch
            assert "is_paid_customer" in ch


@pytest.mark.asyncio
async def test_opportunity_channels_have_null_savings():
    """assurance and site_web always return null annual_savings_eur."""
    async with _authed_client() as client:
        salon_id = await _get_smoke_salon_id(client)
        r = await client.get(f"/api/salons/{salon_id}/savings")
        assert r.status_code == 200

        channels = {ch["channel_key"]: ch for ch in r.json()["channels"]}
        assert channels["assurance"]["annual_savings_eur"] is None
        assert channels["site_web"]["annual_savings_eur"] is None


@pytest.mark.asyncio
async def test_comptable_channel_has_savings():
    """comptable always has a positive annual_savings_eur (Phase 1: fixed estimate)."""
    async with _authed_client() as client:
        salon_id = await _get_smoke_salon_id(client)
        r = await client.get(f"/api/salons/{salon_id}/savings")
        assert r.status_code == 200

        channels = {ch["channel_key"]: ch for ch in r.json()["channels"]}
        comptable = channels["comptable"]
        assert comptable["annual_savings_eur"] is not None
        assert float(comptable["annual_savings_eur"]) > 0


@pytest.mark.asyncio
async def test_ae_statut_juridique_savings():
    """
    TASK-2.12.7: AE and non-assimilé salons get should_display=False for statut_juridique.

    Pre-2.12.7 behaviour: AE/EURL/SARL users saw the statut_juridique simulator,
    which is misleading (the comparison is "you should become SASU" — a big life
    decision outside savings-engine scope).
    Post-2.12.7: the channel is always returned (stable API contract) but carries
    should_display=False so the frontend hides the section for non-assimilé users.
    """
    email = f"test_savings_{uuid.uuid4().hex[:8]}@test.com"
    async with _register_and_login(email) as client:
        # AE user with 3 months of strong CA — should_display=False regardless
        ae_salon_id = await _create_salon(client, business_type="auto_micro")
        for month in (1, 2, 3):
            r_post = await client.post(
                f"/api/salons/{ae_salon_id}/monthly-reports",
                json={"year": 2026, "month": month, "ca_realise_ttc": 12000},
            )
            assert r_post.status_code == 201, r_post.text

        r = await client.get(f"/api/salons/{ae_salon_id}/savings")
        assert r.status_code == 200
        channels = {ch["channel_key"]: ch for ch in r.json()["channels"]}
        sj = channels["statut_juridique"]
        # TASK-2.12.7: AE → hidden. Channel still present (stable contract) but not displayable.
        assert sj.get("should_display") is False, (
            "AE user: statut_juridique should_display must be False — "
            "comparison 'switch to société' is out of savings-engine scope for AE"
        )
        # No simulator_inputs computed (early return before DB queries)
        assert sj.get("simulator_inputs") is None

        # EURL salon — also TNS, also hidden.
        eurl_salon_id = await _create_salon(client, business_type="eurl")
        r2 = await client.get(f"/api/salons/{eurl_salon_id}/savings")
        assert r2.status_code == 200
        channels2 = {ch["channel_key"]: ch for ch in r2.json()["channels"]}
        assert channels2["statut_juridique"].get("should_display") is False, (
            "EURL user: statut_juridique should_display must be False"
        )


@pytest.mark.asyncio
async def test_statut_juridique_should_display_assimile():
    """
    TASK-2.12.7: SASU/SAS users (assimilé-salarié) see should_display=True
    for the statut_juridique channel. With ≥3 months of CA data, simulator_inputs
    is also populated so the frontend widget can render.
    """
    email = f"test_sj_display_{uuid.uuid4().hex[:8]}@test.com"
    async with _register_and_login(email) as client:
        sasu_salon_id = await _create_salon(client, business_type="sasu")

        # Seed 3 months — below this the channel returns insufficient_data
        # (but still should_display=True for assimilé users).
        for month in (1, 2, 3):
            rp = await client.post(
                f"/api/salons/{sasu_salon_id}/monthly-reports",
                json={"year": 2026, "month": month, "ca_realise_ttc": 8000},
            )
            assert rp.status_code == 201, rp.text

        r = await client.get(f"/api/salons/{sasu_salon_id}/savings")
        assert r.status_code == 200
        channels = {ch["channel_key"]: ch for ch in r.json()["channels"]}
        sj = channels["statut_juridique"]

        # should_display defaults to True — field may be absent (True) or explicitly True
        assert sj.get("should_display", True) is True, (
            "SASU user: statut_juridique should be visible (should_display=True)"
        )
        # With 3 months of data the simulator_inputs payload must exist
        assert sj.get("simulator_inputs") is not None, (
            "SASU user with 3 months CA: simulator_inputs missing — "
            "frontend cannot render StatutJuridiqueSimulator"
        )

        # Same check for SAS
        sas_salon_id = await _create_salon(client, business_type="sas")
        for month in (1, 2, 3):
            rp2 = await client.post(
                f"/api/salons/{sas_salon_id}/monthly-reports",
                json={"year": 2026, "month": month, "ca_realise_ttc": 8000},
            )
            assert rp2.status_code == 201, rp2.text

        r2 = await client.get(f"/api/salons/{sas_salon_id}/savings")
        channels2 = {ch["channel_key"]: ch for ch in r2.json()["channels"]}
        sj2 = channels2["statut_juridique"]
        assert sj2.get("should_display", True) is True, (
            "SAS user: statut_juridique should be visible"
        )



@pytest.mark.asyncio
async def test_total_excludes_opportunity_channels():
    """total_annual_savings_eur = sum of computed channels only."""
    async with _authed_client() as client:
        salon_id = await _get_smoke_salon_id(client)
        r = await client.get(f"/api/salons/{salon_id}/savings")
        assert r.status_code == 200

        data = r.json()
        expected_total = sum(
            float(ch["annual_savings_eur"])
            for ch in data["channels"]
            if ch["annual_savings_eur"] is not None
        )
        actual_total = float(data["total_annual_savings_eur"])
        assert abs(actual_total - expected_total) < 0.01


@pytest.mark.asyncio
async def test_savings_cache():
    """Second call to GET /savings returns from_cache=True."""
    email = f"test_savings_{uuid.uuid4().hex[:8]}@test.com"
    async with _register_and_login(email) as client:
        salon_id = await _create_salon(client)

        r1 = await client.get(f"/api/salons/{salon_id}/savings")
        assert r1.status_code == 200
        assert r1.json()["from_cache"] is False

        r2 = await client.get(f"/api/salons/{salon_id}/savings")
        assert r2.status_code == 200
        assert r2.json()["from_cache"] is True


@pytest.mark.asyncio
async def test_savings_refresh():
    """POST /savings/refresh returns from_cache=False."""
    email = f"test_savings_{uuid.uuid4().hex[:8]}@test.com"
    async with _register_and_login(email) as client:
        salon_id = await _create_salon(client)

        await client.get(f"/api/salons/{salon_id}/savings")  # warm cache

        r = await client.post(f"/api/salons/{salon_id}/savings/refresh")
        assert r.status_code == 200
        assert r.json()["from_cache"] is False


@pytest.mark.asyncio
async def test_savings_unauthenticated():
    """GET /savings returns 401 for unauthenticated requests."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(f"/api/salons/{uuid.uuid4()}/savings")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_savings_wrong_user():
    """GET /savings returns 404 when requesting another user's salon."""
    email_a = f"test_savings_a_{uuid.uuid4().hex[:8]}@test.com"
    email_b = f"test_savings_b_{uuid.uuid4().hex[:8]}@test.com"

    async with _register_and_login(email_a) as client_a:
        salon_id = await _create_salon(client_a)

    async with _register_and_login(email_b) as client_b:
        r = await client_b.get(f"/api/salons/{salon_id}/savings")
        assert r.status_code == 404


# ── New tests for TASK-2.12.1 fixes: per-brand produits, comptable fields, cache invalidation ──


@pytest.mark.asyncio
async def test_comptable_channel_cost_fields():
    """
    comptable channel must expose current_cost_eur and comcoi_cost_eur (parity requirement).

    These fields are required for _tool_detect_comptable_savings to delegate to the engine
    and cite identical numbers. Even with no expense data, the engine uses the 2000 € industry
    average for current_cost_eur.

    Acceptance criteria (TASK-2.12.1):
      - current_cost_eur is not null and > 0
      - comcoi_cost_eur is not null and > 0
      - annual_savings_eur = current_cost_eur - comcoi_cost_eur (within 1 cent)
    """
    async with _authed_client() as client:
        salon_id = await _get_smoke_salon_id(client)
        r = await client.post(f"/api/salons/{salon_id}/savings/refresh")
        assert r.status_code == 200

        channels = {ch["channel_key"]: ch for ch in r.json()["channels"]}
        assert "comptable" in channels, "comptable channel missing from report"

        ch = channels["comptable"]
        assert ch["current_cost_eur"] is not None, "current_cost_eur must be set"
        assert ch["comcoi_cost_eur"] is not None, "comcoi_cost_eur must be set"
        assert float(ch["current_cost_eur"]) > 0, "current_cost_eur must be > 0"
        assert float(ch["comcoi_cost_eur"]) > 0, "comcoi_cost_eur must be > 0"

        if ch["annual_savings_eur"] is not None:
            implied = float(ch["current_cost_eur"]) - float(ch["comcoi_cost_eur"])
            assert abs(float(ch["annual_savings_eur"]) - implied) < 0.02, (
                f"annual_savings_eur {ch['annual_savings_eur']} does not equal "
                f"current_cost_eur - comcoi_cost_eur ({implied:.2f})"
            )


@pytest.mark.asyncio
async def test_produits_fallback_channel_id():
    """
    A new salon (no brand data) must still include a 'produits' channel in the response.

    WHY: _channel_produits returns ['produits'] as fallback when there are no
    brand_purchases rows. The /mes-economies page must always render a products section.

    Acceptance criteria:
      - channel with id='produits' exists in the response
      - its annual_savings_eur is None (no data → no savings figure)
    """
    email = f"test_savings_{uuid.uuid4().hex[:8]}@test.com"
    async with _register_and_login(email) as client:
        salon_id = await _create_salon(client)

        r = await client.get(f"/api/salons/{salon_id}/savings")
        assert r.status_code == 200

        channel_ids = [ch["channel_key"] for ch in r.json()["channels"]]
        # Must have at least one produits channel (fallback when no brand data)
        produits_channels = [cid for cid in channel_ids if cid.startswith("produits")]
        assert len(produits_channels) > 0, (
            f"Expected at least one 'produits*' channel, got: {channel_ids}"
        )

        # Fallback channel is exactly 'produits' (not 'produits:loreal' etc.)
        assert "produits" in channel_ids, (
            "Expected fallback 'produits' channel for new salon with no brand data"
        )

        produits_ch = next(ch for ch in r.json()["channels"] if ch["channel_key"] == "produits")
        assert produits_ch["annual_savings_eur"] is None, (
            "produits fallback channel must have null savings (no data)"
        )


@pytest.mark.asyncio
async def test_cache_invalidated_on_monthly_report_write():
    """
    Cache is busted when a monthly report is created.

    Write-path invalidation (TASK-2.12.1):
      1. First GET → from_cache=False (computed fresh)
      2. Second GET → from_cache=True (served from cache)
      3. POST a monthly report → triggers invalidate_savings_cache()
      4. Third GET → from_cache=False (cache was invalidated, recomputed)

    Acceptance criteria: third GET must have from_cache=False.
    """
    email = f"test_savings_{uuid.uuid4().hex[:8]}@test.com"
    async with _register_and_login(email) as client:
        salon_id = await _create_salon(client)

        # Step 1: prime the cache
        r1 = await client.get(f"/api/salons/{salon_id}/savings")
        assert r1.status_code == 200
        assert r1.json()["from_cache"] is False

        # Step 2: verify cache is hot
        r2 = await client.get(f"/api/salons/{salon_id}/savings")
        assert r2.status_code == 200
        assert r2.json()["from_cache"] is True, "Expected cached response on second call"

        # Step 3: write a monthly report → must invalidate cache
        r_write = await client.post(
            f"/api/salons/{salon_id}/monthly-reports",
            json={"year": 2026, "month": 1, "ca_realise_ttc": 5000},
        )
        assert r_write.status_code == 201, f"Monthly report create failed: {r_write.text}"

        # Step 4: savings must recompute (cache was busted by the write)
        r3 = await client.get(f"/api/salons/{salon_id}/savings")
        assert r3.status_code == 200
        assert r3.json()["from_cache"] is False, (
            "Expected from_cache=False after monthly report write — "
            "cache invalidation not firing correctly"
        )
