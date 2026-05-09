"""
TASK-2.14.3 — Two-axis savings engine: cost-equivalent mode tests.

Verifies compute_compare_types_cost_equivalent():
  - For the same company budget, TNS delivers more net than assimilé-salarié
  - Delta for current type is always 0
  - Current type appears first in sorted list with is_current=True
  - SASU current type: TNS alternatives show higher net (WHY: SASU costs more)
  - TNS current type: SASU alternative shows lower net (inverse)
  - Endpoint with mode="cost_equivalent" returns the new function's results
  - Endpoint with mode="net_equivalent" (default) unchanged
  - All returned values are Decimal (no float leakage)

Cost divisors under test (from _COUT_DIVISORS in compare_types.py):
  SASU/SAS:   cout = net × 1.885  → net = cout / 1.885
  TNS:        cout = net × 1.45   → net = cout / 1.45
  AE:         cout = net × 1.212  → net = cout / 1.212

WHY: TNS costs the company 1.45× net vs SASU's 1.885× net.
     So for the same budget, TNS gives more net.
     At net=36000 (3000/mois): SASU budget = 36000×1.885 = 67860
     TNS net from that budget   = 67860 / 1.45 ≈ 46800 → +10800/an
     This is the "8 000 €/an savings" order of magnitude (task 2.14.7 smoke-test).
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


def _make_sasu_profile(net: Decimal = Decimal("36000")) -> object:
    """Create a SASU CompareProfile with given dirigeant net remuneration."""
    from app.services.compare_types import CompareProfile
    return CompareProfile(
        ca_annuel_ttc=Decimal("150000"),
        charges_annuelles_fixes=Decimal("30000"),
        masse_salariale_annuelle=Decimal("40000"),
        dirigeant_remuneration_nette=net,
        business_type_actuel="sasu",
    )


def _make_tns_profile(net: Decimal = Decimal("36000")) -> object:
    """Create a EURL-IR CompareProfile with given dirigeant net remuneration."""
    from app.services.compare_types import CompareProfile
    return CompareProfile(
        ca_annuel_ttc=Decimal("150000"),
        charges_annuelles_fixes=Decimal("30000"),
        masse_salariale_annuelle=Decimal("40000"),
        dirigeant_remuneration_nette=net,
        business_type_actuel="eurl_ir",
    )


class TestCoutDirigeanActuel:
    """Unit tests for _cout_dirigeant_actuel() reverse-cost helper."""

    def test_sasu_multiplier_is_1885(self):
        """SASU cost = net × 1.885 (brut × 1.3 × 1.45)."""
        from app.services.compare_types import _cout_dirigeant_actuel
        profile = _make_sasu_profile(net=Decimal("36000"))
        cout = _cout_dirigeant_actuel(profile)
        expected = Decimal("36000") * Decimal("1.885")
        assert cout == expected

    def test_tns_multiplier_is_145(self):
        """TNS (EURL-IR) cost = net × 1.45."""
        from app.services.compare_types import _cout_dirigeant_actuel
        profile = _make_tns_profile(net=Decimal("36000"))
        cout = _cout_dirigeant_actuel(profile)
        expected = Decimal("36000") * Decimal("1.45")
        assert cout == expected

    def test_ae_multiplier_is_1212(self):
        """AE cost = net × 1.212 (21.2% URSSAF flat)."""
        from app.services.compare_types import _cout_dirigeant_actuel, CompareProfile
        profile = CompareProfile(
            ca_annuel_ttc=Decimal("60000"),
            charges_annuelles_fixes=Decimal("10000"),
            masse_salariale_annuelle=Decimal("0"),
            dirigeant_remuneration_nette=Decimal("30000"),
            business_type_actuel="auto_micro",
        )
        cout = _cout_dirigeant_actuel(profile)
        expected = Decimal("30000") * Decimal("1.212")
        assert cout == expected


class TestComputeCostEquivalent:
    """Tests for compute_compare_types_cost_equivalent()."""

    def test_current_type_delta_is_zero(self):
        """Current type always has delta_eur = 0 and is_current = True."""
        from app.services.compare_types import compute_compare_types_cost_equivalent
        profile = _make_sasu_profile()
        rows = compute_compare_types_cost_equivalent(profile)
        current_rows = [r for r in rows if r.is_current]
        assert len(current_rows) == 1
        assert current_rows[0].delta_eur == Decimal("0")

    def test_current_type_is_first(self):
        """Current type row is first in the sorted list."""
        from app.services.compare_types import compute_compare_types_cost_equivalent
        profile = _make_sasu_profile()
        rows = compute_compare_types_cost_equivalent(profile)
        assert rows[0].is_current is True
        assert rows[0].business_type == "sasu"

    def test_tns_net_higher_than_sasu_for_same_budget(self):
        """
        When current type = SASU, TNS alternatives show MORE net for the same budget.

        WHY: SASU budget = net × 1.885. TNS net from that = budget / 1.45.
             1.885 / 1.45 ≈ 1.30 → TNS delivers ~30% more net for the same cost.
        """
        from app.services.compare_types import compute_compare_types_cost_equivalent
        profile = _make_sasu_profile(net=Decimal("36000"))
        rows = compute_compare_types_cost_equivalent(profile)

        eurl_ir_row = next((r for r in rows if r.business_type == "eurl_ir"), None)
        sasu_row = next((r for r in rows if r.is_current), None)
        assert eurl_ir_row is not None, "eurl_ir must be in alternatives for SASU"
        assert sasu_row is not None

        assert eurl_ir_row.net_dirigeant_apres_charges > sasu_row.net_dirigeant_apres_charges, (
            f"TNS net {eurl_ir_row.net_dirigeant_apres_charges} should exceed "
            f"SASU net {sasu_row.net_dirigeant_apres_charges} for same budget"
        )
        assert eurl_ir_row.delta_eur > Decimal("0")

    def test_sasu_net_lower_than_tns_for_same_budget(self):
        """
        When current type = EURL-IR (TNS), SASU alternatives show LESS net.

        Same budget but SASU is less efficient: divisor 1.885 > 1.45.
        """
        from app.services.compare_types import compute_compare_types_cost_equivalent
        profile = _make_tns_profile(net=Decimal("36000"))
        rows = compute_compare_types_cost_equivalent(profile)

        sasu_row = next((r for r in rows if r.business_type == "sasu"), None)
        tns_row = next((r for r in rows if r.is_current), None)
        assert sasu_row is not None, "sasu must be in alternatives for EURL-IR"
        assert tns_row is not None

        assert sasu_row.net_dirigeant_apres_charges < tns_row.net_dirigeant_apres_charges, (
            f"SASU net {sasu_row.net_dirigeant_apres_charges} should be less than "
            f"TNS net {tns_row.net_dirigeant_apres_charges} for same budget"
        )
        assert sasu_row.delta_eur < Decimal("0")

    def test_savings_order_of_magnitude_sasu_to_tns(self):
        """
        TASK-2.14.7 pre-check: SASU→TNS saving is ≥ 8 000 € at net=36 000 €/an.

        At 3 000 €/mois net (reasonable 2-person salon owner):
          SASU budget  = 36 000 × 1.885 = 67 860 €
          TNS net      = 67 860 / 1.45  ≈ 46 800 €
          Delta        ≈ 10 800 €/an
        """
        from app.services.compare_types import compute_compare_types_cost_equivalent
        profile = _make_sasu_profile(net=Decimal("36000"))
        rows = compute_compare_types_cost_equivalent(profile)

        eurl_ir_row = next((r for r in rows if r.business_type == "eurl_ir"), None)
        assert eurl_ir_row is not None
        assert eurl_ir_row.delta_eur >= Decimal("8000"), (
            f"SASU→EURL-IR saving = {eurl_ir_row.delta_eur}, expected ≥ 8 000 €/an"
        )

    def test_all_rows_return_decimal_not_float(self):
        """All monetary fields must be Decimal."""
        from app.services.compare_types import compute_compare_types_cost_equivalent
        profile = _make_sasu_profile()
        rows = compute_compare_types_cost_equivalent(profile)
        for row in rows:
            assert isinstance(row.net_dirigeant_apres_charges, Decimal), (
                f"{row.business_type}.net is {type(row.net_dirigeant_apres_charges)}"
            )
            assert isinstance(row.total_charges_eur, Decimal)
            assert isinstance(row.delta_eur, Decimal)

    def test_charges_is_budget_minus_net(self):
        """total_charges_eur = company_budget - net (for each row)."""
        from app.services.compare_types import compute_compare_types_cost_equivalent, _cout_dirigeant_actuel
        profile = _make_sasu_profile()
        cout = _cout_dirigeant_actuel(profile)
        rows = compute_compare_types_cost_equivalent(profile)
        for row in rows:
            expected = (cout - row.net_dirigeant_apres_charges).quantize(Decimal("0.01"))
            assert row.total_charges_eur == expected, (
                f"{row.business_type}: charges {row.total_charges_eur} != "
                f"budget - net = {expected}"
            )


# ── API endpoint tests ────────────────────────────────────────────────────────


async def _register_and_login(client: AsyncClient, email: str) -> object:
    """Register a user and return login cookies."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    engine = create_async_engine(settings.database_url)
    async with AsyncSession(engine, expire_on_commit=False) as db:
        user = User(
            email=email,
            password_hash=hash_password("TestPass123!"),
            name="Cost Equiv Test",
        )
        db.add(user)
        await db.commit()
    await engine.dispose()

    login = await client.post("/api/auth/login", json={"email": email, "password": "TestPass123!"})
    assert login.status_code == 200
    return login.cookies


async def _cleanup_user(email: str):
    """Remove test user by email."""
    engine = create_async_engine(settings.database_url)
    async with AsyncSession(engine, expire_on_commit=False) as db:
        await db.execute(text(f"DELETE FROM users WHERE email = '{email}'"))
        await db.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_endpoint_cost_equivalent_mode_returns_mode_field():
    """
    POST /api/calculations/compare-types with mode=cost_equivalent
    returns the mode field in the response.
    """
    email = f"ce.mode.{uuid.uuid4().hex[:8]}@example.com"
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
            data = r.json()
            assert data["mode"] == "cost_equivalent"
            assert len(data["rows"]) > 0
        finally:
            await _cleanup_user(email)


@pytest.mark.asyncio
async def test_endpoint_cost_equivalent_tns_higher_than_sasu():
    """
    In cost_equivalent mode, SASU current type: TNS alternatives have positive delta.
    """
    email = f"ce.delta.{uuid.uuid4().hex[:8]}@example.com"
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
            data = r.json()
            rows = data["rows"]
            eurl_ir = next((r for r in rows if r["business_type"] == "eurl_ir"), None)
            assert eurl_ir is not None
            assert Decimal(eurl_ir["delta_eur"]) >= Decimal("8000"), (
                f"SASU→EURL-IR delta = {eurl_ir['delta_eur']}, expected ≥ 8 000 €/an"
            )
        finally:
            await _cleanup_user(email)


@pytest.mark.asyncio
async def test_endpoint_default_mode_is_net_equivalent():
    """
    POST without mode field defaults to net_equivalent (backward-compat check).
    """
    email = f"ce.default.{uuid.uuid4().hex[:8]}@example.com"
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
                    # No mode field — should default to net_equivalent
                },
            )
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["mode"] == "net_equivalent"
        finally:
            await _cleanup_user(email)


@pytest.mark.asyncio
async def test_endpoint_invalid_mode_returns_422():
    """mode must be 'net_equivalent' or 'cost_equivalent' — others return 422."""
    email = f"ce.bad.{uuid.uuid4().hex[:8]}@example.com"
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
                    "mode": "invalid_mode",
                },
            )
            assert r.status_code == 422
        finally:
            await _cleanup_user(email)
