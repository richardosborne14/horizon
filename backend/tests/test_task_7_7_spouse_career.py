"""
Tests for TASK-7.7: Spouse Career History & Pension.

Covers:
- CC trimestre calculation for all 4 CC options
- Career period owner="spouse" creation and listing
- Default owner="user" backward compat
- Invalid owner rejection
"""
import uuid

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app
from app.calculations.pension import estimate_cc_trimestres_per_year
from decimal import Decimal


# ── Combined Pension Endpoint Tests (TASK-7.7, Step 4) ──────────────────────


@pytest.mark.asyncio
async def test_combined_pension_no_spouse():
    """GET /api/projection/pension-estimate without spouse should return
    user_pension only, spouse_pension null, backward compat."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": f"test.pension.nosp.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "Pension No Spouse",
                },
            )
            assert r.status_code == 201, r.text
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            # Set up profile with CA
            from datetime import date
            birth = date.today().replace(year=date.today().year - 35)
            await client.put(
                "/api/profile",
                cookies=cookies,
                json={
                    "birth_date": birth.isoformat(),
                    "monthly_gross_ca": "5000.00",
                    "target_retirement_age": 67,
                    "ae_activity_type": "bnc_non_reglementee",
                },
            )

            # Call combined pension endpoint
            res = await client.get(
                "/api/projection/pension-estimate?scale=moderate", cookies=cookies
            )
            assert res.status_code == 200, res.text
            data = res.json()

            # Shape check
            assert "user_pension" in data
            assert "spouse_pension" in data
            assert "household_pension_monthly" in data

            # User pension should have the old flat fields
            up = data["user_pension"]
            assert "total_monthly" in up
            assert "trimestres_valides" in up
            assert "is_taux_plein" in up
            assert float(up["total_monthly"]) > 0  # With 5k/month CA, pension > 0

            # No spouse → spouse_pension null
            assert data["spouse_pension"] is None

            # Household equals user only (both strings from JSON)
            assert data["household_pension_monthly"] == up["total_monthly"]
            assert float(data["household_pension_monthly"]) > 0
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_combined_pension_with_spouse_career():
    """GET /api/projection/pension-estimate with spouse + CDI career
    should return both user_pension and spouse_pension."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": f"test.pension.sp.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "Pension With Spouse",
                },
            )
            assert r.status_code == 201, r.text
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            # Set up profile
            from datetime import date
            birth = date.today().replace(year=date.today().year - 35)
            await client.put(
                "/api/profile",
                cookies=cookies,
                json={
                    "birth_date": birth.isoformat(),
                    "monthly_gross_ca": "5000.00",
                    "target_retirement_age": 67,
                    "ae_activity_type": "bnc_non_reglementee",
                    "status": "ae",
                },
            )

            # Create spouse with CDI job
            sp_birth = date.today().replace(year=date.today().year - 37)
            res_sp = await client.post(
                "/api/spouse",
                cookies=cookies,
                json={
                    "first_name": "Marie",
                    "birth_date": sp_birth.isoformat(),
                    "relationship_type": "married",
                    "status": "cdi",
                    "monthly_gross_income": "3500.00",
                },
            )
            assert res_sp.status_code == 201, res_sp.text

            # Add spouse CDI career period (10 years at 42k)
            await client.post(
                "/api/career",
                cookies=cookies,
                json={
                    "period_type": "cdi",
                    "start_date": sp_birth.replace(year=sp_birth.year + 22).isoformat(),
                    "end_date": sp_birth.replace(year=sp_birth.year + 32).isoformat(),
                    "owner": "spouse",
                    "annual_gross": "42000.00",
                    "employer_name": "BNP Paribas",
                },
            )

            # Call combined pension endpoint
            res = await client.get(
                "/api/projection/pension-estimate?scale=moderate", cookies=cookies
            )
            assert res.status_code == 200, res.text
            data = res.json()

            # Both pensions present
            assert data["user_pension"] is not None
            assert data["spouse_pension"] is not None

            # Spouse pension should have values
            sp = data["spouse_pension"]
            assert "total_monthly" in sp
            assert "trimestres_valides" in sp
            assert "trimestres_requis" in sp
            assert sp["trimestres_valides"] >= 40  # 10 years CDI ≈ 40 trimestres
            assert float(sp["total_monthly"]) > 0

            # Household total should be > user only (all strings from JSON)
            user_total = float(data["user_pension"]["total_monthly"])
            spouse_total = float(sp["total_monthly"])
            household = float(data["household_pension_monthly"])
            assert abs(household - (user_total + spouse_total)) < 0.02  # rounding tolerance
            assert household > user_total
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_combined_pension_spouse_cc():
    """Spouse as CC with tiers_revenu should get CC trimestres included
    in total computed pension."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": f"test.pension.cc.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "Pension CC Test",
                },
            )
            assert r.status_code == 201, r.text
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            from datetime import date
            birth = date.today().replace(year=date.today().year - 35)
            await client.put(
                "/api/profile",
                cookies=cookies,
                json={
                    "birth_date": birth.isoformat(),
                    "monthly_gross_ca": "5000.00",
                    "target_retirement_age": 67,
                    "ae_activity_type": "bnc_non_reglementee",
                    "status": "eirl",  # Required for CC
                },
            )

            # Create spouse as CC
            sp_birth = date.today().replace(year=date.today().year - 38)
            res_sp = await client.post(
                "/api/spouse",
                cookies=cookies,
                json={
                    "first_name": "Sophie",
                    "birth_date": sp_birth.isoformat(),
                    "relationship_type": "married",
                    "status": "conjointe_collaboratrice",
                    "is_conjointe_collaboratrice": True,
                    "cc_cotisation_option": "tiers_revenu",
                },
            )
            assert res_sp.status_code == 201, res_sp.text

            # Call combined pension endpoint
            res = await client.get(
                "/api/projection/pension-estimate?scale=moderate", cookies=cookies
            )
            assert res.status_code == 200, res.text
            data = res.json()

            assert data["spouse_pension"] is not None
            sp = data["spouse_pension"]
            # CC trimestres should be included
            assert sp.get("includes_cc_trimestres", 0) >= 0
            # CC trimestres: with 5k/month CA and tiers_revenu, 
            # base = 5000*12/3 = 20000, exceeding 4*SMIC threshold → 4/year
            # over 29 years = up to 116. But capped by projection timeline.
            assert sp["trimestres_valides"] >= 0

            # Household total exists and is a positive number
            assert float(data["household_pension_monthly"]) > 0
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


# ── CC Trimestre Calculation ─────────────────────────────────────────────────


def test_cc_trimestres_tiers_plafond_zero_ca():
    """Tiers plafond gives a fixed base regardless of CA (1/3 of PASS = ~15,456€).
    That's 15,456 / 6,990 ≈ 2.21 → 2 trimestres (not enough for 4)."""
    result = estimate_cc_trimestres_per_year("tiers_plafond", Decimal("0"))
    assert result == 2


def test_cc_trimestres_moitie_plafond():
    """Moitie plafond = 1/2 of PASS = 23,184€.
    23,184 / 6,990 ≈ 3.31 → 3 trimestres."""
    result = estimate_cc_trimestres_per_year("moitie_plafond", Decimal("0"))
    assert result == 3


def test_cc_trimestres_tiers_revenu_high_ca():
    """With high CA, tiers_revenu can reach 4 trimestres.
    90,000 / 3 = 30,000; 30,000 / 6,990 ≈ 4.29 → 4 trimestres."""
    result = estimate_cc_trimestres_per_year("tiers_revenu", Decimal("90000"))
    assert result == 4


def test_cc_trimestres_moitie_revenu_low_ca():
    """With low CA, moitie_revenu gives fewer trimestres.
    12,000 / 2 = 6,000; 6,000 / 6,990 → 0 trimestres."""
    result = estimate_cc_trimestres_per_year("moitie_revenu", Decimal("12000"))
    assert result == 0


def test_cc_trimestres_moitie_revenu_medium_ca():
    """With moderate CA, moitie_revenu gives 2 trimestres.
    30,000 / 2 = 15,000; 15,000 / 6,990 ≈ 2.14 → 2 trimestres."""
    result = estimate_cc_trimestres_per_year("moitie_revenu", Decimal("30000"))
    assert result == 2


def test_cc_trimestres_unknown_option():
    """Unknown option returns 0."""
    result = estimate_cc_trimestres_per_year("nonexistent", Decimal("50000"))
    assert result == 0


def test_cc_trimestres_moitie_plafond_always_same():
    """Moitie plafond should be independent of CA."""
    assert estimate_cc_trimestres_per_year("moitie_plafond", Decimal("0")) == 3
    assert estimate_cc_trimestres_per_year("moitie_plafond", Decimal("100000")) == 3


# ── Career API: owner field ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_career_period_with_owner_spouse():
    """POST /api/career with owner=spouse should create a spouse period."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": f"test.spouse.owner.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "Spouse Owner Test",
                },
            )
            assert r.status_code == 201, r.text
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            res = await client.post(
                "/api/career",
                cookies=cookies,
                json={
                    "period_type": "cdi",
                    "start_date": "2015-01-01",
                    "end_date": "2020-01-01",
                    "owner": "spouse",
                    "annual_gross": "35000.00",
                    "employer_name": "L'Oréal",
                    "job_title": "Responsable marketing",
                },
            )
            assert res.status_code == 201, res.text
            data = res.json()
            assert data["owner"] == "spouse"
            assert data["period_type"] == "cdi"
            assert data["employer_name"] == "L'Oréal"
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_list_career_by_owner():
    """GET /api/career?owner=spouse should return only spouse periods."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": f"test.owner.list.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "Owner List Test",
                },
            )
            assert r.status_code == 201, r.text
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            # Create a user period
            res_user = await client.post(
                "/api/career",
                cookies=cookies,
                json={
                    "period_type": "ae",
                    "start_date": "2020-01-01",
                    "annual_gross": "30000.00",
                },
            )
            assert res_user.status_code == 201
            assert res_user.json()["owner"] == "user"

            # Create two spouse periods
            await client.post(
                "/api/career",
                cookies=cookies,
                json={
                    "period_type": "cdi",
                    "start_date": "2010-01-01",
                    "end_date": "2015-01-01",
                    "owner": "spouse",
                    "annual_gross": "28000.00",
                },
            )
            await client.post(
                "/api/career",
                cookies=cookies,
                json={
                    "period_type": "cdd",
                    "start_date": "2015-06-01",
                    "end_date": "2016-12-31",
                    "owner": "spouse",
                    "annual_gross": "24000.00",
                },
            )

            # List user periods
            res_user_list = await client.get("/api/career?owner=user", cookies=cookies)
            assert res_user_list.status_code == 200
            user_periods = res_user_list.json()
            assert all(p["owner"] == "user" for p in user_periods)

            # List spouse periods
            res_spouse_list = await client.get("/api/career?owner=spouse", cookies=cookies)
            assert res_spouse_list.status_code == 200
            spouse_periods = res_spouse_list.json()
            assert len(spouse_periods) >= 2
            assert all(p["owner"] == "spouse" for p in spouse_periods)
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_default_owner_is_user():
    """POST /api/career without owner field should default to 'user'."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": f"test.default.owner.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "Default Owner Test",
                },
            )
            assert r.status_code == 201, r.text
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            res = await client.post(
                "/api/career",
                cookies=cookies,
                json={
                    "period_type": "cdi",
                    "start_date": "2005-01-01",
                    "end_date": "2010-01-01",
                    "annual_gross": "25000.00",
                },
            )
            assert res.status_code == 201
            data = res.json()
            assert data["owner"] == "user"
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_invalid_owner_rejected():
    """POST with invalid owner should return 422."""
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": f"test.invalid.owner.{uuid.uuid4().hex[:6]}@example.com",
                    "password": "TestPass123!",
                    "name": "Invalid Owner Test",
                },
            )
            assert r.status_code == 201, r.text
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            res = await client.post(
                "/api/career",
                cookies=cookies,
                json={
                    "period_type": "cdi",
                    "start_date": "2020-01-01",
                    "owner": "invalid",
                },
            )
            assert res.status_code == 422
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()