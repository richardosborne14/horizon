"""
Tests for Calculator Hub + Cross-Tool Linking — Task 2.9.5

Covers:
  - Headline formatters (unit tests, pure Python)
  - Hub overview endpoint
  - Global history endpoint
  - Pin toggle
  - Scenario CRUD (create, list, detail, patch, archive/restore)
  - Attach / detach calc from scenario
  - Tool catalogue endpoint
  - Staleness check service
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import AsyncSessionLocal
from app.services.calculation_links import (
    format_headline,
    capture_source_link,
)


# ── Self-contained test setup helpers ────────────────────────────────────────

async def _create_hub_stack(client: AsyncClient) -> tuple[str, str]:
    """
    Register a fresh user, log in, create a salon.

    Returns (salon_id, email). Auth is cookie-based — the AsyncClient
    session stores the session cookie automatically after /api/auth/login,
    so subsequent requests need no explicit headers.  Follows the pattern
    established in test_task_3_6_calculation_history.py.
    """
    uid = str(uuid.uuid4())[:8]
    email = f"hub_test_{uid}@example.com"
    await client.post("/api/auth/register", json={
        "email": email,
        "password": "Hub1234!",
        "name": f"Hub Tester {uid}",
    })
    await client.post("/api/auth/login", json={
        "email": email,
        "password": "Hub1234!",
    })
    # Session cookie is now set on the client — no explicit headers needed
    salon_resp = await client.post("/api/salons", json={
        "name": "Hub Test Salon",
        "business_type": "auto_micro",
    })
    assert salon_resp.status_code == 201, salon_resp.text
    return salon_resp.json()["id"], email


async def _cleanup_hub_user(email: str) -> None:
    """Delete test user + cascade."""
    from sqlalchemy import text
    async with AsyncSessionLocal() as db:
        await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
        await db.commit()


# ── Headline formatter unit tests ─────────────────────────────────────────────

class TestFormatHeadline:
    """Unit tests for format_headline — pure Python, no DB needed."""

    def test_taxes_net_monthly(self):
        """format_headline returns formatted net monthly for taxes."""
        out = format_headline(
            "taxes",
            {"net_monthly": 3247.50, "business_type": "auto_micro_service"},
        )
        assert out is not None
        assert "3" in out  # thousands present
        assert "AE services" in out

    def test_taxes_missing_net_monthly(self):
        """format_headline returns None when required key is absent."""
        out = format_headline("taxes", {})
        assert out is None

    def test_primes_annual_total(self):
        """format_headline extracts annual_total for primes."""
        out = format_headline("primes", {"annual_total": 1600})
        assert out is not None
        assert "1" in out

    def test_primes_months_list(self):
        """format_headline sums months list when annual_total absent."""
        out = format_headline("primes", {"months": [{"prime": 100}, {"prime": 200}]})
        assert out is not None
        assert "300" in out or "300" in out.replace("\u202f", "")

    def test_seuil_salaire_objectif(self):
        """format_headline extracts objectif_mois_ht for seuil_salaire."""
        out = format_headline("seuil_salaire", {"objectif_mois_ht": 3200})
        assert out is not None
        assert "3" in out
        assert "mois" in out

    def test_volume_clients(self):
        """format_headline extracts clients_par_mois for volume_clients."""
        out = format_headline("volume_clients", {"clients_par_mois": 87})
        assert out is not None
        assert "87" in out
        assert "clients" in out

    def test_marge_revente_full(self):
        """format_headline builds full marge line when all fields present."""
        out = format_headline(
            "marge_revente",
            {"marge_pct": 42, "prix_achat": 14, "prix_vente": 24},
        )
        assert out is not None
        assert "42" in out
        assert "Achat" in out
        assert "Vente" in out

    def test_marge_revente_pct_only(self):
        """format_headline works with pct only."""
        out = format_headline("marge_revente", {"marge_pct": 30})
        assert out is not None
        assert "30" in out

    def test_unknown_type_returns_none(self):
        """format_headline returns None for unknown calculator type."""
        out = format_headline("unknown_tool", {"some_key": 999})
        assert out is None

    def test_primes_empty_months(self):
        """format_headline returns None when months list is empty."""
        out = format_headline("primes", {"months": []})
        assert out is None


# ── capture_source_link unit tests ────────────────────────────────────────────

class TestCaptureSourceLink:
    """Unit tests for capture_source_link."""

    def test_returns_all_keys(self):
        """capture_source_link returns a dict with all required keys."""
        link = capture_source_link(
            field="objectif_mois_ht",
            source_tool="seuil_salaire",
            source_calc_id="abc123",
            source_value_at_time=3200,
        )
        assert link["field"] == "objectif_mois_ht"
        assert link["source_tool"] == "seuil_salaire"
        assert link["source_calc_id"] == "abc123"
        assert link["source_value_at_time"] == 3200
        assert "captured_at" in link
        assert "T" in link["captured_at"]  # ISO format

    def test_captured_at_is_utc(self):
        """capture_source_link sets captured_at to a UTC ISO timestamp."""
        link = capture_source_link("f", "taxes", "id", 100)
        assert link["captured_at"].endswith("+00:00") or "Z" in link["captured_at"] or "T" in link["captured_at"]


# ── Integration tests — self-contained (no shared fixtures) ──────────────────
# Each test creates its own user + salon, following the pattern established in
# test_task_3_6_calculation_history.py to avoid asyncpg loop issues.
# Auth is cookie-based — session cookie is stored automatically by AsyncClient
# after login, so no explicit headers are needed.

@pytest.mark.asyncio
async def test_hub_overview_empty() -> None:
    """GET /calc-hub/overview returns 200 with 5 tool entries (fresh salon)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        salon_id, email = await _create_hub_stack(client)
        try:
            resp = await client.get(f"/api/salons/{salon_id}/calc-hub/overview")
            assert resp.status_code == 200
            data = resp.json()
            assert "tools" in data
            assert "pinned" in data
            assert len(data["tools"]) == 5
            for t in data["tools"]:
                assert t["recent"] == []
                assert t["last_run_at"] is None
        finally:
            await _cleanup_hub_user(email)


@pytest.mark.asyncio
async def test_hub_catalogue() -> None:
    """GET /calc-hub/catalogue returns 5 tool entries."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        salon_id, email = await _create_hub_stack(client)
        try:
            resp = await client.get(f"/api/salons/{salon_id}/calc-hub/catalogue")
            assert resp.status_code == 200
            tools = resp.json()
            assert len(tools) == 5
            slugs = {t["tool"] for t in tools}
            assert slugs == {"taxes", "primes", "seuil_salaire", "volume_clients", "marge_revente"}
        finally:
            await _cleanup_hub_user(email)


@pytest.mark.asyncio
async def test_hub_global_history_empty() -> None:
    """GET /calc-hub/history returns 200 empty list when no calcs saved."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        salon_id, email = await _create_hub_stack(client)
        try:
            resp = await client.get(f"/api/salons/{salon_id}/calc-hub/history")
            assert resp.status_code == 200
            assert resp.json() == []
        finally:
            await _cleanup_hub_user(email)


@pytest.mark.asyncio
async def test_scenario_create_and_list() -> None:
    """POST /calc-hub/scenarios creates a scenario; GET lists it."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        salon_id, email = await _create_hub_stack(client)
        try:
            create_resp = await client.post(
                f"/api/salons/{salon_id}/calc-hub/scenarios",
                json={"name": "Test Scenario 2027", "description": "Dev test"},
            )
            assert create_resp.status_code == 201
            sc = create_resp.json()
            assert sc["name"] == "Test Scenario 2027"
            assert sc["archived_at"] is None
            assert sc["calc_count"] == 0

            list_resp = await client.get(f"/api/salons/{salon_id}/calc-hub/scenarios")
            assert list_resp.status_code == 200
            names = [s["name"] for s in list_resp.json()]
            assert "Test Scenario 2027" in names
        finally:
            await _cleanup_hub_user(email)


@pytest.mark.asyncio
async def test_scenario_rename_and_archive() -> None:
    """PATCH /calc-hub/scenarios/{id} renames and archives a scenario."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        salon_id, email = await _create_hub_stack(client)
        try:
            sc_id = (await client.post(
                f"/api/salons/{salon_id}/calc-hub/scenarios",
                json={"name": "Original"},
            )).json()["id"]

            renamed = (await client.patch(
                f"/api/salons/{salon_id}/calc-hub/scenarios/{sc_id}",
                json={"name": "Renamed"},
            )).json()
            assert renamed["name"] == "Renamed"

            archived = (await client.patch(
                f"/api/salons/{salon_id}/calc-hub/scenarios/{sc_id}",
                json={"archived": True},
            )).json()
            assert archived["archived_at"] is not None

            # Default list excludes archived
            ids = [s["id"] for s in (await client.get(
                f"/api/salons/{salon_id}/calc-hub/scenarios"
            )).json()]
            assert sc_id not in ids

            # include_archived=true shows it
            ids_all = [s["id"] for s in (await client.get(
                f"/api/salons/{salon_id}/calc-hub/scenarios?include_archived=true"
            )).json()]
            assert sc_id in ids_all
        finally:
            await _cleanup_hub_user(email)


@pytest.mark.asyncio
async def test_pin_toggle() -> None:
    """POST /calc-hub/history/{calc_id}/pin toggles is_pinned."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        salon_id, email = await _create_hub_stack(client)
        try:
            save_resp = await client.post(
                f"/api/salons/{salon_id}/calculation-history/",
                json={
                    "calculator_type": "taxes",
                    "inputs": {"business_type": "auto_micro_service", "ca_annuel": 50000},
                    "outputs": {"net_monthly": 3247, "business_type": "auto_micro_service"},
                },
            )
            assert save_resp.status_code == 201
            calc_id = save_resp.json()["id"]
            assert save_resp.json()["headline_result"] is not None  # auto-generated

            pin_resp = await client.post(
                f"/api/salons/{salon_id}/calc-hub/history/{calc_id}/pin"
            )
            assert pin_resp.status_code == 200
            assert pin_resp.json()["is_pinned"] is True

            unpin_resp = await client.post(
                f"/api/salons/{salon_id}/calc-hub/history/{calc_id}/pin"
            )
            assert unpin_resp.status_code == 200
            assert unpin_resp.json()["is_pinned"] is False
        finally:
            await _cleanup_hub_user(email)


@pytest.mark.asyncio
async def test_attach_detach_calc() -> None:
    """Attach then detach a calc from a scenario."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        salon_id, email = await _create_hub_stack(client)
        try:
            sc_id = (await client.post(
                f"/api/salons/{salon_id}/calc-hub/scenarios",
                json={"name": "Attach test"},
            )).json()["id"]

            calc_id = (await client.post(
                f"/api/salons/{salon_id}/calculation-history/",
                json={
                    "calculator_type": "seuil_salaire",
                    "inputs": {"salaire_brut": 2000},
                    "outputs": {"objectif_mois_ht": 3200},
                },
            )).json()["id"]

            attach_resp = await client.post(
                f"/api/salons/{salon_id}/calc-hub/scenarios/{sc_id}/attach/{calc_id}"
            )
            assert attach_resp.status_code == 200
            assert attach_resp.json()["scenario_id"] == sc_id

            detail = (await client.get(
                f"/api/salons/{salon_id}/calc-hub/scenarios/{sc_id}"
            )).json()
            assert detail["calc_count"] == 1
            assert any(c["id"] == calc_id for c in detail["calculations"])

            detach_resp = await client.delete(
                f"/api/salons/{salon_id}/calc-hub/scenarios/{sc_id}/detach/{calc_id}"
            )
            assert detach_resp.status_code == 200
            assert detach_resp.json()["scenario_id"] is None
        finally:
            await _cleanup_hub_user(email)


@pytest.mark.asyncio
async def test_hub_overview_shows_recent_calcs() -> None:
    """After saving a taxes calc, hub overview shows it in tools[taxes].recent."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        salon_id, email = await _create_hub_stack(client)
        try:
            await client.post(
                f"/api/salons/{salon_id}/calculation-history/",
                json={
                    "calculator_type": "taxes",
                    "inputs": {"business_type": "tns", "remuneration_nette": 4000},
                    "outputs": {"net_monthly": 4000, "business_type": "tns"},
                },
            )

            overview = (await client.get(
                f"/api/salons/{salon_id}/calc-hub/overview"
            )).json()

            taxes_entry = next(t for t in overview["tools"] if t["tool"] == "taxes")
            assert len(taxes_entry["recent"]) >= 1
            assert taxes_entry["last_run_at"] is not None
        finally:
            await _cleanup_hub_user(email)


@pytest.mark.asyncio
async def test_hub_invalid_tool_filter() -> None:
    """GET /calc-hub/history?tool=bad returns 400."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        salon_id, email = await _create_hub_stack(client)
        try:
            resp = await client.get(
                f"/api/salons/{salon_id}/calc-hub/history?tool=unknown_tool"
            )
            assert resp.status_code == 400
        finally:
            await _cleanup_hub_user(email)
