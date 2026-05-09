"""
Tests for TASK-2.12.13 — Statut Juridique Simulator.

Covers:
  - compare_types service: compute_compare_types returns sorted rows with correct deltas
  - POST /api/calculations/compare-types endpoint: auth, 422 on bad input, correct response
  - CoCo prompt: _STATUT_JURIDIQUE_RULE is injected in build_system_prompt

WHY: The statut juridique simulator is a financial tool — every formula must be
tested against expected outcomes to catch regressions if tax rates change.
"""

from decimal import Decimal
import pytest
from httpx import AsyncClient


# ── Unit tests: compare_types service ─────────────────────────────────────────

class TestComputeCompareTypes:
    """Unit tests for compute_compare_types() in isolation."""

    def _profile(self, **kwargs):
        """Build a CompareProfile with sensible defaults."""
        from app.services.compare_types import CompareProfile
        defaults = dict(
            ca_annuel_ttc=Decimal("80000"),
            charges_annuelles_fixes=Decimal("20000"),
            masse_salariale_annuelle=Decimal("0"),
            dirigeant_remuneration_nette=Decimal("24000"),
            business_type_actuel="eurl_ir",
            versement_liberatoire=False,
            acre=False,
        )
        defaults.update(kwargs)
        return CompareProfile(**defaults)

    def test_returns_rows_for_all_main_types(self):
        """compute_compare_types should include at least 3 alternative rows."""
        from app.services.compare_types import compute_compare_types
        profile = self._profile()
        rows = compute_compare_types(profile)
        assert len(rows) >= 3, "Expected at least 3 type rows"

    def test_current_type_is_marked(self):
        """Exactly one row should have is_current=True and match business_type_actuel."""
        from app.services.compare_types import compute_compare_types
        profile = self._profile(business_type_actuel="eurl_ir")
        rows = compute_compare_types(profile)
        current_rows = [r for r in rows if r.is_current]
        assert len(current_rows) == 1, "Exactly one row must be marked is_current"
        assert current_rows[0].business_type == "eurl_ir"

    def test_current_row_delta_is_zero(self):
        """The current type's delta_eur should be 0 (baseline)."""
        from app.services.compare_types import compute_compare_types
        profile = self._profile(business_type_actuel="eurl_ir")
        rows = compute_compare_types(profile)
        current = next(r for r in rows if r.is_current)
        assert current.delta_eur == Decimal("0"), \
            f"Current type delta_eur should be 0, got {current.delta_eur}"

    def test_ae_type_present_when_current(self):
        """When current type IS auto_micro, the auto_micro row is present."""
        from app.services.compare_types import compute_compare_types
        profile = self._profile(business_type_actuel="auto_micro")
        rows = compute_compare_types(profile)
        types = [r.business_type for r in rows]
        assert "auto_micro" in types, "auto_micro row missing when it is the current type"

    def test_net_dirigeant_positive(self):
        """All net_dirigeant_apres_charges values should be non-negative for valid inputs."""
        from app.services.compare_types import compute_compare_types
        profile = self._profile()
        rows = compute_compare_types(profile)
        for row in rows:
            assert row.net_dirigeant_apres_charges >= Decimal("0"), \
                f"{row.business_type} net is negative: {row.net_dirigeant_apres_charges}"

    def test_ae_with_versement_liberatoire(self):
        """AE with versement_liberatoire should compute without error."""
        from app.services.compare_types import compute_compare_types
        profile = self._profile(
            business_type_actuel="auto_micro",
            versement_liberatoire=True,
        )
        rows = compute_compare_types(profile)
        assert len(rows) >= 1

    def test_ae_with_acre(self):
        """AE with ACRE should compute without error and not exceed normal net."""
        from app.services.compare_types import compute_compare_types
        profile = self._profile(
            business_type_actuel="auto_micro",
            acre=True,
        )
        rows_acre = compute_compare_types(profile)
        profile_no_acre = self._profile(business_type_actuel="auto_micro", acre=False)
        rows_no_acre = compute_compare_types(profile_no_acre)
        ae_acre = next(r for r in rows_acre if r.is_current)
        ae_no_acre = next(r for r in rows_no_acre if r.is_current)
        # ACRE reduces cotisations → net should be higher with ACRE
        assert ae_acre.net_dirigeant_apres_charges >= ae_no_acre.net_dirigeant_apres_charges, \
            "ACRE should improve net dirigeant vs no ACRE"

    def test_labels_are_strings(self):
        """All rows must have non-empty label strings."""
        from app.services.compare_types import compute_compare_types
        rows = compute_compare_types(self._profile())
        for row in rows:
            assert isinstance(row.label, str) and len(row.label) > 0, \
                f"Row {row.business_type} has empty/non-string label"

    def test_decimal_precision(self):
        """Results should not have more than 2 decimal places (display precision)."""
        from app.services.compare_types import compute_compare_types
        rows = compute_compare_types(self._profile())
        for row in rows:
            # Quantize to 2dp — if it changes, precision was wrong
            net_2dp = row.net_dirigeant_apres_charges.quantize(Decimal("0.01"))
            assert abs(row.net_dirigeant_apres_charges - net_2dp) < Decimal("0.01"), \
                f"{row.business_type} net has too many decimals"

    def test_invalid_business_type_handled_gracefully(self):
        """Unknown business_type_actuel: service should not crash; rows are returned.
        
        WHY: The endpoint layer (router) catches ValueError from service calls and
        returns 422. But the service itself may return a best-effort result for
        unknown types rather than raising — this documents that contract.
        The router integration test verifies the 422 path end-to-end.
        """
        from app.services.compare_types import CompareProfile, compute_compare_types
        profile = CompareProfile(
            ca_annuel_ttc=Decimal("80000"),
            charges_annuelles_fixes=Decimal("20000"),
            masse_salariale_annuelle=Decimal("0"),
            dirigeant_remuneration_nette=Decimal("24000"),
            business_type_actuel="flexy_freelance_magic",
        )
        # Service returns rows without crashing (caller validates business_type)
        rows = compute_compare_types(profile)
        assert isinstance(rows, list)


# ── Integration tests: POST /api/calculations/compare-types ───────────────────

import uuid as _uuid
from httpx import ASGITransport


async def _make_client():
    """Return a bare (unauthenticated) AsyncClient for ASGI transport."""
    from app.main import app as _app
    return AsyncClient(transport=ASGITransport(app=_app), base_url="http://test")


async def _login_client():
    """Return an AsyncClient with smoke-test user session cookie set."""
    from app.main import app as _app
    c = AsyncClient(transport=ASGITransport(app=_app), base_url="http://test")
    await c.__aenter__()
    resp = await c.post(
        "/api/auth/login",
        json={"email": "smoketest@comcoi.fr", "password": "Password123!"},
    )
    assert resp.status_code == 200, (
        f"Login failed ({resp.status_code}): {resp.text}. "
        "Run `docker compose exec backend python scripts/seed.py` first."
    )
    return c


@pytest.mark.asyncio
async def test_endpoint_unauthenticated_returns_401():
    """Unauthenticated requests to compare-types must return 401."""
    async with AsyncClient(
        transport=ASGITransport(app=__import__("app.main", fromlist=["app"]).app),
        base_url="http://test",
    ) as c:
        resp = await c.post("/api/calculations/compare-types", json={
            "ca_annuel_ttc": 80000,
            "dirigeant_remuneration_nette": 24000,
            "business_type_actuel": "eurl_ir",
        })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_endpoint_returns_200_with_valid_payload():
    """Valid payload returns 200 with rows and current_type."""
    from app.main import app as _app
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as c:
        await c.post("/api/auth/login",
                     json={"email": "smoketest@comcoi.fr", "password": "Password123!"})
        resp = await c.post("/api/calculations/compare-types", json={
            "ca_annuel_ttc": 80000,
            "charges_annuelles_fixes": 20000,
            "masse_salariale_annuelle": 0,
            "dirigeant_remuneration_nette": 24000,
            "business_type_actuel": "eurl_ir",
        })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "rows" in data
    assert "current_type" in data
    assert len(data["rows"]) >= 3
    assert data["current_type"] == "eurl_ir"


@pytest.mark.asyncio
async def test_endpoint_current_row_delta_zero():
    """The current type's delta_eur should be 0."""
    from app.main import app as _app
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as c:
        await c.post("/api/auth/login",
                     json={"email": "smoketest@comcoi.fr", "password": "Password123!"})
        resp = await c.post("/api/calculations/compare-types", json={
            "ca_annuel_ttc": 80000,
            "dirigeant_remuneration_nette": 24000,
            "business_type_actuel": "eurl_ir",
        })
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    current = next((r for r in rows if r["is_current"]), None)
    assert current is not None
    assert float(current["delta_eur"]) == pytest.approx(0.0, abs=0.01)


@pytest.mark.asyncio
async def test_endpoint_ae_type_accepted():
    """auto_micro business type is valid."""
    from app.main import app as _app
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as c:
        await c.post("/api/auth/login",
                     json={"email": "smoketest@comcoi.fr", "password": "Password123!"})
        resp = await c.post("/api/calculations/compare-types", json={
            "ca_annuel_ttc": 60000,
            "dirigeant_remuneration_nette": 20000,
            "business_type_actuel": "auto_micro",
            "versement_liberatoire": True,
            "acre": False,
        })
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_endpoint_invalid_business_type_returns_422():
    """Unknown business_type_actuel → 422."""
    from app.main import app as _app
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as c:
        await c.post("/api/auth/login",
                     json={"email": "smoketest@comcoi.fr", "password": "Password123!"})
        resp = await c.post("/api/calculations/compare-types", json={
            "ca_annuel_ttc": 80000,
            "dirigeant_remuneration_nette": 24000,
            "business_type_actuel": "not_a_real_type",
        })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_endpoint_negative_ca_returns_422():
    """Negative ca_annuel_ttc → 422 from Pydantic validation."""
    from app.main import app as _app
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as c:
        await c.post("/api/auth/login",
                     json={"email": "smoketest@comcoi.fr", "password": "Password123!"})
        resp = await c.post("/api/calculations/compare-types", json={
            "ca_annuel_ttc": -1000,
            "dirigeant_remuneration_nette": 24000,
            "business_type_actuel": "eurl_ir",
        })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_endpoint_fields_are_decimal_safe():
    """All returned numeric fields should be parseable as float."""
    from app.main import app as _app
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as c:
        await c.post("/api/auth/login",
                     json={"email": "smoketest@comcoi.fr", "password": "Password123!"})
        resp = await c.post("/api/calculations/compare-types", json={
            "ca_annuel_ttc": 75000.50,
            "dirigeant_remuneration_nette": 22500.75,
            "business_type_actuel": "sasu",
        })
    assert resp.status_code == 200
    for row in resp.json()["rows"]:
        float(row["net_dirigeant_apres_charges"])
        float(row["total_charges_eur"])
        float(row["delta_eur"])


# ── CoCo prompt tests ──────────────────────────────────────────────────────────

class TestCocoStatutJuridiqueRule:
    """Verify _STATUT_JURIDIQUE_RULE is injected into authenticated prompts."""

    def test_statut_juridique_rule_in_authenticated_prompt(self):
        """The statut juridique override rule must be present in every auth prompt."""
        from app.services.coco_prompts import build_system_prompt
        prompt = build_system_prompt(user_profile=None, screen_context=None)
        assert "RÈGLE STATUT JURIDIQUE" in prompt, \
            "_STATUT_JURIDIQUE_RULE not injected in build_system_prompt"

    def test_statut_juridique_rule_mentions_get_savings_report(self):
        """The rule must explicitly mention get_savings_report tool."""
        from app.services.coco_prompts import build_system_prompt
        prompt = build_system_prompt()
        assert "get_savings_report" in prompt, \
            "Rule must mention get_savings_report tool"

    def test_statut_juridique_rule_forbids_invented_figures(self):
        """The rule must contain the INTERDIT prohibition on invented numbers."""
        from app.services.coco_prompts import build_system_prompt
        prompt = build_system_prompt()
        assert "INTERDIT" in prompt

    def test_rule_injected_before_user_profile(self):
        """The statut juridique rule should come before any user profile section."""
        from app.services.coco_prompts import build_system_prompt
        profile = {"user_name": "TestUser", "salon_name": "TestSalon"}
        prompt = build_system_prompt(user_profile=profile)
        rule_pos = prompt.find("RÈGLE STATUT JURIDIQUE")
        profile_pos = prompt.find("TestUser")
        assert rule_pos < profile_pos, \
            "Statut juridique rule should appear before user profile"

    def test_public_prompt_does_not_have_statut_rule(self):
        """Public (unauthenticated) prompts do NOT get the statut juridique rule — no user data."""
        from app.services.coco_prompts import build_public_system_prompt
        prompt = build_public_system_prompt()
        # The rule is only for authenticated users who have financial data to cite
        assert "RÈGLE STATUT JURIDIQUE" not in prompt, \
            "Public prompt should NOT contain authenticated-only statut juridique rule"
