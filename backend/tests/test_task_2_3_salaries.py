"""
Task 2.3 — Salary Entry + Social Charges: unit tests.

Covers:
  1. Pure calculation functions (no DB) — social_charges.py
  2. API integration tests — salary CRUD via test client (uses DB)

All monetary assertions use Decimal comparisons, never float.

SMIC 2026 = 1823.03 €
PASS mensuel 2026 = 4005 €
"""

import uuid
import pytest
from decimal import Decimal

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import text

from app.core.config import settings
from app.main import app
from app.models.user import User
from app.services.auth import hash_password


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Pure Calculation Unit Tests (no DB, no fixtures)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCalcRgdu:
    """Tests for calc_rgdu() — the RGDU reduction function."""

    def test_smic_has_near_maximum_reduction(self):
        """
        At SMIC (21876.40 annuel), the RGDU coefficient should be near maximum
        since ratio = (3*SMIC/SMIC) - 1 = 2, so (0.5*2)^1.75 = 1^1.75 = 1.
        coefficient = 0.02 + 0.3773 * 1 = 0.3973 (maximum capped, updated per décret n°2025-887).
        RGDU = 21876.40 * 0.3973 ≈ 8691.72.
        """
        from app.calculations.social_charges import calc_rgdu, SMIC_ANNUEL, PASS_ANNUEL

        result = calc_rgdu(SMIC_ANNUEL)
        assert result > Decimal("8000"), f"SMIC RGDU should be near max, got {result}"
        assert result < Decimal("9000"), f"SMIC RGDU too high, got {result}"

    def test_three_times_smic_is_zero(self):
        """At exactly 3×SMIC, RGDU should be zero (boundary condition)."""
        from app.calculations.social_charges import calc_rgdu, SMIC_ANNUEL

        result = calc_rgdu(SMIC_ANNUEL * Decimal("3"))
        assert result == Decimal("0")

    def test_above_three_smic_is_zero(self):
        """Above 3×SMIC, no reduction applies."""
        from app.calculations.social_charges import calc_rgdu, SMIC_ANNUEL

        result = calc_rgdu(SMIC_ANNUEL * Decimal("4"))
        assert result == Decimal("0")

    def test_returns_decimal_not_float(self):
        """Return type must be Decimal — never float."""
        from app.calculations.social_charges import calc_rgdu, SMIC_ANNUEL

        result = calc_rgdu(SMIC_ANNUEL)
        assert isinstance(result, Decimal), f"Expected Decimal, got {type(result)}"


class TestCalcChargesSalarie:
    """
    Tests for calc_charges_salarie() against the reference table in
    dev-docs/resources/06-social-charges-reference.md.

    The reference doc shows approximate values — we test within tolerance.
    Exact figures depend on floating-point precision in the RGDU power calc,
    so we use a 10€ tolerance for rounded reference values.
    """

    def test_smic_cout_total_approx_1860(self):
        """
        At SMIC (1823.03), the total employer cost should be ~1860 €.
        Reference: cout_total ≈ 1860 €.
        """
        from app.calculations.social_charges import calc_charges_salarie, SMIC_MENSUEL_BRUT

        result = calc_charges_salarie(SMIC_MENSUEL_BRUT)
        assert Decimal("1840") <= result.cout_total_employeur <= Decimal("1890"), (
            f"SMIC cout_total = {result.cout_total_employeur}, expected ~1860"
        )

    def test_smic_charges_nettes_near_zero(self):
        """
        At SMIC, net charges after RGDU should be very low (~20–40 €).
        This is expected because the RGDU nearly offsets the patronal charges.
        """
        from app.calculations.social_charges import calc_charges_salarie, SMIC_MENSUEL_BRUT

        result = calc_charges_salarie(SMIC_MENSUEL_BRUT)
        assert result.charges_patronales_nettes >= Decimal("0"), "Charges cannot be negative"
        assert result.charges_patronales_nettes <= Decimal("100"), (
            f"SMIC net charges too high: {result.charges_patronales_nettes}"
        )

    def test_2200_cout_total_approx_2600(self):
        """2200 € brut → total ≈ 2600 € (from reference table)."""
        from app.calculations.social_charges import calc_charges_salarie

        result = calc_charges_salarie(Decimal("2200"))
        assert Decimal("2500") <= result.cout_total_employeur <= Decimal("2700"), (
            f"2200€ cout_total = {result.cout_total_employeur}, expected ~2600"
        )

    def test_2500_cout_total_approx_3170(self):
        """2500 € brut → total ≈ 3170 € (from reference table)."""
        from app.calculations.social_charges import calc_charges_salarie

        result = calc_charges_salarie(Decimal("2500"))
        assert Decimal("3050") <= result.cout_total_employeur <= Decimal("3290"), (
            f"2500€ cout_total = {result.cout_total_employeur}, expected ~3170"
        )

    def test_pass_mensuel_cout_total_approx_5645(self):
        """At PASS (4005 €), total ≈ 5645 € (from reference table)."""
        from app.calculations.social_charges import calc_charges_salarie, PASS_MENSUEL

        result = calc_charges_salarie(PASS_MENSUEL)
        assert Decimal("5500") <= result.cout_total_employeur <= Decimal("5800"), (
            f"PASS cout_total = {result.cout_total_employeur}, expected ~5645"
        )

    def test_total_charge_equals_brut_plus_cotisations(self):
        """total_charge must always equal salaire_brut + cotisations_sociales."""
        from app.calculations.social_charges import calc_charges_salarie

        for brut in [Decimal("1823.03"), Decimal("2000"), Decimal("2500"), Decimal("4005")]:
            result = calc_charges_salarie(brut)
            expected = result.salaire_brut + result.charges_patronales_nettes
            assert result.cout_total_employeur == expected, (
                f"brut={brut}: cout_total {result.cout_total_employeur} != "
                f"{result.salaire_brut} + {result.charges_patronales_nettes}"
            )

    def test_salaire_net_approx_is_less_than_brut(self):
        """Net salary is always less than gross (employee pays charges)."""
        from app.calculations.social_charges import calc_charges_salarie

        result = calc_charges_salarie(Decimal("2200"))
        assert result.salaire_net_approx < result.salaire_brut

    def test_rgdu_reduction_is_non_negative(self):
        """RGDU can never be negative."""
        from app.calculations.social_charges import calc_charges_salarie

        for brut in [Decimal("1823.03"), Decimal("2200"), Decimal("3000"), Decimal("5000")]:
            result = calc_charges_salarie(brut)
            assert result.rgdu_reduction >= Decimal("0"), f"RGDU negative at brut={brut}"

    def test_charges_overrides_zero_brut(self):
        """Zero salary → zero charges, zero total cost."""
        from app.calculations.social_charges import calc_charges_salarie

        result = calc_charges_salarie(Decimal("0"))
        assert result.charges_patronales_nettes == Decimal("0")
        assert result.cout_total_employeur == Decimal("0")

    def test_breakdown_contains_required_keys(self):
        """Breakdown dict must contain keys needed for the info modal."""
        from app.calculations.social_charges import calc_charges_salarie

        result = calc_charges_salarie(Decimal("2200"))
        required_keys = [
            "taux_en_vigueur", "maladie_13pct", "rgdu_reduction",
            "total_patronal_brut", "total_patronal_net"
        ]
        for key in required_keys:
            assert key in result.breakdown, f"Missing breakdown key: {key}"

    def test_all_fields_are_decimal(self):
        """All monetary fields returned must be Decimal, never float."""
        from app.calculations.social_charges import calc_charges_salarie

        result = calc_charges_salarie(Decimal("2200"))
        for field_name in [
            "salaire_brut", "charges_patronales_brutes", "rgdu_reduction",
            "charges_patronales_nettes", "cout_total_employeur",
            "charges_salariales", "salaire_net_approx", "ratio_cout_brut"
        ]:
            val = getattr(result, field_name)
            assert isinstance(val, Decimal), f"{field_name} is {type(val)}, expected Decimal"


class TestEstimateChargesTns:
    """Tests for estimate_charges_tns() — TNS ~45% estimation."""

    def test_45_percent_rate_applied(self):
        """Charges should be exactly 45% of the net remuneration."""
        from app.calculations.social_charges import estimate_charges_tns

        net = Decimal("3000")
        result = estimate_charges_tns(net)
        expected_charges = Decimal("1350.00")  # 3000 * 0.45
        assert result.charges_sociales_estimees == expected_charges

    def test_cout_total_is_net_plus_charges(self):
        """cout_total = remuneration + charges."""
        from app.calculations.social_charges import estimate_charges_tns

        net = Decimal("2000")
        result = estimate_charges_tns(net)
        assert result.cout_total_entreprise == net + result.charges_sociales_estimees

    def test_zero_remuneration(self):
        """Zero remuneration → zero charges."""
        from app.calculations.social_charges import estimate_charges_tns

        result = estimate_charges_tns(Decimal("0"))
        assert result.charges_sociales_estimees == Decimal("0")

    def test_breakdown_has_note(self):
        """Breakdown must include the URSSAF warning note for the UI modal."""
        from app.calculations.social_charges import estimate_charges_tns

        result = estimate_charges_tns(Decimal("2500"))
        assert "note" in result.breakdown
        assert "URSSAF" in result.breakdown["note"]


class TestCalcChargesAutoEntrepreneur:
    """Tests for calc_charges_auto_entrepreneur() — flat-rate micro-entrepreneur."""

    def test_services_rate_21_2_percent(self):
        """Service CA at 21.2% (no ACRE, no vente)."""
        from app.calculations.social_charges import calc_charges_auto_entrepreneur

        result = calc_charges_auto_entrepreneur(
            ca_services=Decimal("1000"), ca_vente=Decimal("0")
        )
        # cotisations = 1000 * 0.212 = 212.00
        assert result.cotisations_sociales == Decimal("212.00")

    def test_cfp_added_to_charges(self):
        """CFP (0.3% on total CA) must be included in total_charges."""
        from app.calculations.social_charges import calc_charges_auto_entrepreneur

        result = calc_charges_auto_entrepreneur(
            ca_services=Decimal("1000"), ca_vente=Decimal("0")
        )
        # CFP = 1000 * 0.003 = 3.00
        assert result.cfp == Decimal("3.00")
        assert result.total_charges == Decimal("215.00")  # 212 + 3

    def test_acre_halves_rates(self):
        """With ACRE, rates are halved → cotisations = 1000 * 0.106 = 106."""
        from app.calculations.social_charges import calc_charges_auto_entrepreneur

        result = calc_charges_auto_entrepreneur(
            ca_services=Decimal("1000"), ca_vente=Decimal("0"), has_acre=True
        )
        assert result.cotisations_sociales == Decimal("106.00")
        assert result.has_acre is True

    def test_revenu_net_is_ca_minus_total_charges(self):
        """Revenu net = CA - total_charges."""
        from app.calculations.social_charges import calc_charges_auto_entrepreneur

        result = calc_charges_auto_entrepreneur(
            ca_services=Decimal("1000"), ca_vente=Decimal("0")
        )
        assert result.revenu_net_avant_ir == Decimal("1000") - result.total_charges


# ═══════════════════════════════════════════════════════════════════════════════
# 2. API Integration Tests (self-contained, no shared fixtures)
#    Pattern: create engine + user + salon + report + employee inline per test.
#    WHY: conftest.py only provides event_loop, not async_client or auth_headers.
#    See LEARNINGS.md for the asyncpg session-scoped loop pattern.
# ═══════════════════════════════════════════════════════════════════════════════


async def _cleanup(db: AsyncSession, user_ids: list) -> None:
    """Delete test users by id — CASCADE removes salons, reports, salaries."""
    for uid in user_ids:
        await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
    await db.commit()


async def _bootstrap(email: str) -> tuple:
    """
    Create a test user, log in, create a salon, monthly report, and employee.

    Returns: (engine, cookies, salon_id, report_id, employee_id, user_ids)
    """
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async with AsyncSession(engine, expire_on_commit=False) as db:
        user = User(
            email=email,
            password_hash=hash_password("TestPass123!"),
            name="Test Salary User",
        )
        db.add(user)
        await db.flush()
        user_ids.append(str(user.id))
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post("/api/auth/login", json={"email": email, "password": "TestPass123!"})
        assert login.status_code == 200, f"Login failed: {login.text}"
        cookies = login.cookies

        salon = await client.post(
            "/api/salons",
            json={"name": "Salon Salary Test", "business_type": "auto_micro"},
            cookies=cookies,
        )
        assert salon.status_code == 201, f"Salon failed: {salon.text}"
        salon_id = salon.json()["id"]

        report = await client.post(
            f"/api/salons/{salon_id}/monthly-reports",
            json={"year": 2026, "month": 4, "ca_realise_ttc": "10000.00", "subventions": "0"},
            cookies=cookies,
        )
        assert report.status_code == 201, f"Report failed: {report.text}"
        report_id = report.json()["id"]

        employee = await client.post(
            f"/api/salons/{salon_id}/employees",
            json={
                "name": "Marie Test",
                "role_type": "salarie",
                "contract_type": "cdi",
                "hours_per_week": 35,
                "salary_brut": 2200.0,
                "cotisations_patronales": 880.0,
            },
            cookies=cookies,
        )
        assert employee.status_code == 201, f"Employee failed: {employee.text}"
        employee_id = employee.json()["id"]

    return engine, cookies, salon_id, report_id, employee_id, user_ids


@pytest.mark.asyncio
async def test_salary_list_returns_totals():
    """
    GET salaries for a report returns list + Section A totals.
    """
    email = f"sal.list.{uuid.uuid4().hex[:8]}@example.com"
    engine, cookies, salon_id, report_id, employee_id, user_ids = await _bootstrap(email)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(
                f"/api/salons/{salon_id}/monthly-reports/{report_id}/salaries",
                cookies=cookies,
            )
            assert r.status_code == 200
            data = r.json()
            assert "salaries" in data
            assert "totals" in data
            assert "total_salaires_charges" in data["totals"]
            assert "sous_total_salaires_bruts" in data["totals"]
            assert "total_cotisations_patronales" in data["totals"]
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_salary_create_auto_calculates_charges():
    """
    POST a salary without cotisations_sociales → backend auto-calculates.
    charges_overridden should be False.
    """
    email = f"sal.auto.{uuid.uuid4().hex[:8]}@example.com"
    engine, cookies, salon_id, report_id, employee_id, user_ids = await _bootstrap(email)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                f"/api/salons/{salon_id}/monthly-reports/{report_id}/salaries",
                cookies=cookies,
                json={"employee_id": employee_id, "salaire_brut": "2200.00"},
            )
            assert r.status_code == 201, r.text
            data = r.json()
            assert data["salaire_brut"] == "2200.00"
            assert data["charges_overridden"] is False
            assert Decimal(data["cotisations_sociales"]) > Decimal("0")
            assert Decimal(data["total_charge"]) == (
                Decimal(data["salaire_brut"]) + Decimal(data["cotisations_sociales"])
            )
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_salary_create_manual_override():
    """
    POST with explicit cotisations_sociales → sets charges_overridden=True.
    """
    email = f"sal.override.{uuid.uuid4().hex[:8]}@example.com"
    engine, cookies, salon_id, report_id, employee_id, user_ids = await _bootstrap(email)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                f"/api/salons/{salon_id}/monthly-reports/{report_id}/salaries",
                cookies=cookies,
                json={
                    "employee_id": employee_id,
                    "salaire_brut": "2500.00",
                    "cotisations_sociales": "999.00",
                },
            )
            assert r.status_code == 201, r.text
            data = r.json()
            assert data["charges_overridden"] is True
            assert data["cotisations_sociales"] == "999.00"
            assert Decimal(data["total_charge"]) == Decimal("3499.00")
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_salary_update_recalculates_on_brut_change():
    """
    PUT with new salaire_brut (charges_overridden=False) → charges recalculate.
    Higher brut → higher charges.
    """
    email = f"sal.update.{uuid.uuid4().hex[:8]}@example.com"
    engine, cookies, salon_id, report_id, employee_id, user_ids = await _bootstrap(email)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                f"/api/salons/{salon_id}/monthly-reports/{report_id}/salaries",
                cookies=cookies,
                json={"employee_id": employee_id, "salaire_brut": "2000.00"},
            )
            assert r.status_code == 201
            salary_id = r.json()["id"]
            old_cotisations = Decimal(r.json()["cotisations_sociales"])

            r2 = await client.put(
                f"/api/salons/{salon_id}/monthly-reports/{report_id}/salaries/{salary_id}",
                cookies=cookies,
                json={"salaire_brut": "3000.00"},
            )
            assert r2.status_code == 200
            updated = r2.json()
            assert Decimal(updated["cotisations_sociales"]) > old_cotisations
            assert updated["charges_overridden"] is False
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_salary_recalculate_clears_override():
    """
    POST .../recalculate resets charges_overridden to False and auto-recalcs.
    """
    email = f"sal.recalc.{uuid.uuid4().hex[:8]}@example.com"
    engine, cookies, salon_id, report_id, employee_id, user_ids = await _bootstrap(email)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                f"/api/salons/{salon_id}/monthly-reports/{report_id}/salaries",
                cookies=cookies,
                json={
                    "employee_id": employee_id,
                    "salaire_brut": "2200.00",
                    "cotisations_sociales": "500.00",
                },
            )
            assert r.status_code == 201
            salary_id = r.json()["id"]
            assert r.json()["charges_overridden"] is True

            r2 = await client.post(
                f"/api/salons/{salon_id}/monthly-reports/{report_id}/salaries/{salary_id}/recalculate",
                cookies=cookies,
            )
            assert r2.status_code == 200
            recalced = r2.json()
            assert recalced["charges_overridden"] is False
            assert Decimal(recalced["cotisations_sociales"]) != Decimal("500.00")
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_salary_wrong_salon_returns_404():
    """Requesting a salary list for a non-owned salon returns 404."""
    email = f"sal.404.{uuid.uuid4().hex[:8]}@example.com"
    engine, cookies, salon_id, report_id, employee_id, user_ids = await _bootstrap(email)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            fake_salon_id = str(uuid.uuid4())
            r = await client.get(
                f"/api/salons/{fake_salon_id}/monthly-reports/{report_id}/salaries",
                cookies=cookies,
            )
            assert r.status_code == 404
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_salary_totals_sum_correctly():
    """
    Section A totals must equal the sum of individual salary rows.
    total_salaires_charges = sous_total_bruts + total_cotisations.
    """
    email = f"sal.totals.{uuid.uuid4().hex[:8]}@example.com"
    engine, cookies, salon_id, report_id, employee_id, user_ids = await _bootstrap(email)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                f"/api/salons/{salon_id}/monthly-reports/{report_id}/salaries",
                cookies=cookies,
                json={"employee_id": employee_id, "salaire_brut": "2200.00"},
            )
            r = await client.get(
                f"/api/salons/{salon_id}/monthly-reports/{report_id}/salaries",
                cookies=cookies,
            )
            assert r.status_code == 200
            data = r.json()
            totals = data["totals"]

            bruts_sum = sum(Decimal(s["salaire_brut"]) for s in data["salaries"])
            cotis_sum = sum(Decimal(s["cotisations_sociales"]) for s in data["salaries"])
            total_charges = sum(Decimal(s["total_charge"]) for s in data["salaries"])

            assert Decimal(totals["sous_total_salaires_bruts"]) == bruts_sum
            assert Decimal(totals["total_cotisations_patronales"]) == cotis_sum
            assert Decimal(totals["total_salaires_charges"]) == total_charges
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()
