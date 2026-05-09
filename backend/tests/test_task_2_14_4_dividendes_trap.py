"""
TASK-2.14.4 — EURL-IS dividendes trap warning tests.

Verifies that the trap_warning field is set correctly:
  - eurl_is, sarl_is, ei_is rows carry the dividendes trap warning
  - AE, EURL-IR, SASU rows do NOT carry the warning
  - Warning text mentions "10 %" and "TNS" (key factual content)
  - Warning is present in both net_equivalent and cost_equivalent modes
  - Endpoint returns trap_warning in JSON rows
  - Warning for CURRENT type is also set when business_type_actuel is IS

WHY: Our simplified IS model assumes ALL dividendes at PFU 30%.
In reality, dividendes > 10% of (capital + réserves) for a TNS unique associé
are subject to TNS cotisations (~45%), not PFU. This could significantly reduce
the apparent advantage of IS structures — the user must consult a professional.
"""

import uuid
import pytest
from decimal import Decimal

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import text

from app.main import app
from app.core.config import settings
from app.models.user import User
from app.services.auth import hash_password


# ── Pure service unit tests ──────────────────────────────────────────────────


def _make_sasu_profile():
    """SASU profile — eurl_is will be an alternative."""
    from app.services.compare_types import CompareProfile
    return CompareProfile(
        ca_annuel_ttc=Decimal("150000"),
        charges_annuelles_fixes=Decimal("30000"),
        masse_salariale_annuelle=Decimal("40000"),
        dirigeant_remuneration_nette=Decimal("36000"),
        business_type_actuel="sasu",
    )


def _make_eurl_is_profile():
    """EURL-IS as current type — trap warning should be on current row too."""
    from app.services.compare_types import CompareProfile
    return CompareProfile(
        ca_annuel_ttc=Decimal("150000"),
        charges_annuelles_fixes=Decimal("30000"),
        masse_salariale_annuelle=Decimal("40000"),
        dirigeant_remuneration_nette=Decimal("36000"),
        business_type_actuel="eurl_is",
    )


class TestTrapWarningService:
    """Unit tests for trap_warning on CompareRow."""

    def test_eurl_is_row_has_trap_warning(self):
        """eurl_is row must have trap_warning set."""
        from app.services.compare_types import compute_compare_types
        profile = _make_sasu_profile()
        rows = compute_compare_types(profile)
        eurl_is = next((r for r in rows if r.business_type == "eurl_is"), None)
        assert eurl_is is not None, "eurl_is must be in SASU alternatives"
        assert eurl_is.trap_warning is not None
        assert len(eurl_is.trap_warning) > 10

    def test_sarl_is_row_has_trap_warning(self):
        """sarl_is row must have trap_warning set."""
        from app.services.compare_types import compute_compare_types, CompareProfile
        profile = CompareProfile(
            ca_annuel_ttc=Decimal("150000"),
            charges_annuelles_fixes=Decimal("30000"),
            masse_salariale_annuelle=Decimal("40000"),
            dirigeant_remuneration_nette=Decimal("36000"),
            business_type_actuel="sarl_ir",
        )
        rows = compute_compare_types(profile)
        sarl_is = next((r for r in rows if r.business_type == "sarl_is"), None)
        assert sarl_is is not None
        assert sarl_is.trap_warning is not None

    def test_sasu_row_has_no_trap_warning(self):
        """SASU rows must NOT have trap_warning (no dividendes trap for assimilé salarié)."""
        from app.services.compare_types import compute_compare_types
        profile = _make_eurl_is_profile()
        rows = compute_compare_types(profile)
        sasu = next((r for r in rows if r.business_type == "sasu"), None)
        assert sasu is not None
        assert sasu.trap_warning is None

    def test_eurl_ir_row_has_no_trap_warning(self):
        """EURL-IR rows must NOT have trap_warning (no dividendes in TNS-IR)."""
        from app.services.compare_types import compute_compare_types
        profile = _make_sasu_profile()
        rows = compute_compare_types(profile)
        eurl_ir = next((r for r in rows if r.business_type == "eurl_ir"), None)
        assert eurl_ir is not None
        assert eurl_ir.trap_warning is None

    def test_ae_row_has_no_trap_warning(self):
        """AE rows must NOT have trap_warning."""
        from app.services.compare_types import compute_compare_types, CompareProfile
        profile = CompareProfile(
            ca_annuel_ttc=Decimal("60000"),
            charges_annuelles_fixes=Decimal("10000"),
            masse_salariale_annuelle=Decimal("0"),
            dirigeant_remuneration_nette=Decimal("30000"),
            business_type_actuel="auto_micro",
        )
        rows = compute_compare_types(profile)
        ae = next((r for r in rows if r.business_type == "auto_micro"), None)
        assert ae is not None
        assert ae.trap_warning is None

    def test_trap_warning_mentions_10pct(self):
        """Warning text must mention '10 %' — the legal threshold."""
        from app.services.compare_types import compute_compare_types
        profile = _make_sasu_profile()
        rows = compute_compare_types(profile)
        eurl_is = next((r for r in rows if r.business_type == "eurl_is"), None)
        assert eurl_is is not None
        assert "10" in (eurl_is.trap_warning or ""), (
            "Warning must mention 10% threshold for dividendes trap"
        )

    def test_trap_warning_mentions_tns(self):
        """Warning text must mention 'TNS' — the relevant regime."""
        from app.services.compare_types import compute_compare_types
        profile = _make_sasu_profile()
        rows = compute_compare_types(profile)
        eurl_is = next((r for r in rows if r.business_type == "eurl_is"), None)
        assert eurl_is is not None
        assert "TNS" in (eurl_is.trap_warning or "").upper(), (
            "Warning must mention TNS cotisations"
        )

    def test_current_eurl_is_has_trap_warning(self):
        """Even the CURRENT row gets trap_warning when business_type_actuel == eurl_is."""
        from app.services.compare_types import compute_compare_types
        profile = _make_eurl_is_profile()
        rows = compute_compare_types(profile)
        current_row = next((r for r in rows if r.is_current), None)
        assert current_row is not None
        assert current_row.business_type == "eurl_is"
        assert current_row.trap_warning is not None

    def test_trap_warning_in_cost_equivalent_mode(self):
        """trap_warning is also set in cost_equivalent mode for IS types."""
        from app.services.compare_types import compute_compare_types_cost_equivalent
        profile = _make_sasu_profile()
        rows = compute_compare_types_cost_equivalent(profile)
        eurl_is = next((r for r in rows if r.business_type == "eurl_is"), None)
        assert eurl_is is not None
        assert eurl_is.trap_warning is not None


# ── API endpoint tests ────────────────────────────────────────────────────────


async def _register_and_login(client: AsyncClient, email: str) -> object:
    """Create a test user and return login cookies."""
    engine = create_async_engine(settings.database_url)
    async with AsyncSession(engine, expire_on_commit=False) as db:
        db.add(User(
            email=email,
            password_hash=hash_password("TestPass123!"),
            name="Trap Warning Test",
        ))
        await db.commit()
    await engine.dispose()
    login = await client.post("/api/auth/login", json={"email": email, "password": "TestPass123!"})
    assert login.status_code == 200
    return login.cookies


async def _cleanup(email: str):
    engine = create_async_engine(settings.database_url)
    async with AsyncSession(engine, expire_on_commit=False) as db:
        await db.execute(text(f"DELETE FROM users WHERE email = '{email}'"))
        await db.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_endpoint_eurl_is_row_has_trap_warning():
    """Endpoint returns trap_warning for eurl_is rows."""
    email = f"trap.w.{uuid.uuid4().hex[:8]}@example.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        cookies = await _register_and_login(client, email)
        try:
            r = await client.post(
                "/api/calculations/compare-types",
                cookies=cookies,
                json={
                    "ca_annuel_ttc": 150000,
                    "charges_annuelles_fixes": 30000,
                    "masse_salariale_annuelle": 40000,
                    "dirigeant_remuneration_nette": 36000,
                    "business_type_actuel": "sasu",
                },
            )
            assert r.status_code == 200, r.text
            rows = r.json()["rows"]
            eurl_is = next((row for row in rows if row["business_type"] == "eurl_is"), None)
            assert eurl_is is not None
            assert eurl_is["trap_warning"] is not None
            assert "10" in eurl_is["trap_warning"]
        finally:
            await _cleanup(email)


@pytest.mark.asyncio
async def test_endpoint_sasu_row_no_trap_warning():
    """Endpoint returns null trap_warning for SASU rows."""
    email = f"trap.n.{uuid.uuid4().hex[:8]}@example.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        cookies = await _register_and_login(client, email)
        try:
            r = await client.post(
                "/api/calculations/compare-types",
                cookies=cookies,
                json={
                    "ca_annuel_ttc": 150000,
                    "charges_annuelles_fixes": 30000,
                    "masse_salariale_annuelle": 40000,
                    "dirigeant_remuneration_nette": 36000,
                    "business_type_actuel": "eurl_is",
                },
            )
            assert r.status_code == 200, r.text
            rows = r.json()["rows"]
            sasu = next((row for row in rows if row["business_type"] == "sasu"), None)
            assert sasu is not None
            assert sasu["trap_warning"] is None
        finally:
            await _cleanup(email)


@pytest.mark.asyncio
async def test_endpoint_trap_warning_in_cost_equivalent_mode():
    """trap_warning appears in cost_equivalent mode too."""
    email = f"trap.ce.{uuid.uuid4().hex[:8]}@example.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        cookies = await _register_and_login(client, email)
        try:
            r = await client.post(
                "/api/calculations/compare-types",
                cookies=cookies,
                json={
                    "ca_annuel_ttc": 150000,
                    "charges_annuelles_fixes": 30000,
                    "masse_salariale_annuelle": 40000,
                    "dirigeant_remuneration_nette": 36000,
                    "business_type_actuel": "sasu",
                    "mode": "cost_equivalent",
                },
            )
            assert r.status_code == 200, r.text
            rows = r.json()["rows"]
            eurl_is = next((row for row in rows if row["business_type"] == "eurl_is"), None)
            assert eurl_is is not None
            assert eurl_is["trap_warning"] is not None
        finally:
            await _cleanup(email)
