"""
TASK-2.12.12 — Fiscal-year correctness in duplicate_month + generate_year_from_template.

Verifies the bug fix for richard3 (`fiscal_year_start=3`):

  • `duplicate_month`: when called from a non-AE salon whose source report sits
    in the middle of a cross-year fiscal exercise (e.g. Apr 2025 in fiscal-ending
    2026), duplicating to fiscal positions that fall in the NEXT calendar year
    (Jan-2026, Feb-2026) must land in calendar 2026 — NOT in calendar 2025.

  • `generate_year_from_template`: when called with `year=2026` for a salon
    whose fiscal start is March, must populate Mar-2025 → Feb-2026 (12 months
    spanning two calendar years) — NOT Jan-2026 → Dec-2026.

For AE/calendar salons (fiscal_year_start=1), behaviour is IDENTICAL to before
the fix — the existing tests in `test_task_2_8_9_annual_duplicate.py` and
`test_task_2_5_6_year_prepopulation.py` already cover that path.

Self-contained async pattern (matches Sprint 2 convention).
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app
from app.services.auth import hash_password


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _make_engine():
    return create_async_engine(settings.database_url, echo=False)


async def _create_user(db: AsyncSession, email: str) -> str:
    from app.models.user import User
    user = User(
        email=email,
        password_hash=hash_password("TestPass123!"),
        name="Fiscal Test",
    )
    db.add(user)
    await db.flush()
    uid = str(user.id)
    await db.commit()
    return uid


async def _login(client: AsyncClient, email: str):
    r = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "TestPass123!"},
    )
    assert r.status_code == 200, r.text
    return r.cookies


async def _create_salon(
    client: AsyncClient, cookies, fiscal_year_start: int
) -> str:
    """
    Create a non-AE salon (so fiscal_year_start is honoured).

    Note: AE salons would force fiscal_year_start=1 server-side regardless of
    the request, so we use 'sarl' to allow the custom fiscal start to stick.
    """
    r = await client.post(
        "/api/salons",
        json={
            "name": f"Salon Fiscal {fiscal_year_start}",
            "business_type": "sarl",
            "fiscal_year_start": fiscal_year_start,
        },
        cookies=cookies,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _create_report(
    client: AsyncClient, cookies, salon_id: str, year: int, month: int,
    ca: str = "5000.00",
) -> str:
    r = await client.post(
        f"/api/salons/{salon_id}/monthly-reports",
        json={
            "year": year, "month": month,
            "ca_realise_ttc": ca, "subventions": "0",
        },
        cookies=cookies,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _cleanup(db: AsyncSession, user_ids: list[str]) -> None:
    for uid in user_ids:
        await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
    await db.commit()


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_duplicate_month_respects_fiscal_year_for_richard3_pattern():
    """
    Setup: salon with fiscal_year_start=3, source = Apr 2025 (fiscal-ending 2026).
    Action: duplicate to fiscal positions [11, 12] = Jan 2026 + Feb 2026.
    Expect: new reports in calendar 2026 (months 1, 2) — NOT 2025.
    """
    engine = await _make_engine()
    user_ids: list[str] = []
    try:
        async with engine.connect() as conn:
            db: AsyncSession = AsyncSession(bind=conn, expire_on_commit=False)
            email = f"fiscal-{uuid.uuid4().hex[:8]}@example.com"
            uid = await _create_user(db, email)
            user_ids.append(uid)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            cookies = await _login(client, email)
            salon_id = await _create_salon(client, cookies, fiscal_year_start=3)

            # Source = Apr 2025 (fiscal position 2 within fiscal-ending 2026)
            source_id = await _create_report(
                client, cookies, salon_id, year=2025, month=4, ca="12000.00"
            )

            # Duplicate to fiscal positions 11 (Jan 2026) + 12 (Feb 2026)
            r = await client.post(
                f"/api/salons/{salon_id}/monthly-reports/{source_id}/duplicate",
                json={"target_months": [11, 12], "overwrite": False},
                cookies=cookies,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["created"] == 2, body
            assert body["errors"] == 0
            assert sorted(body["created_months"]) == [11, 12]

        # Verify rows landed in calendar 2026, NOT 2025
        async with engine.connect() as conn:
            db = AsyncSession(bind=conn, expire_on_commit=False)
            from app.models.financial import MonthlyReport
            rows = (await db.execute(
                select(MonthlyReport).where(MonthlyReport.salon_id == salon_id)
            )).scalars().all()
            pairs = sorted((r.year, r.month) for r in rows)
            # Source Apr 2025 + duplicates Jan/Feb 2026
            assert pairs == [(2025, 4), (2026, 1), (2026, 2)], pairs

    finally:
        async with engine.connect() as conn:
            db = AsyncSession(bind=conn, expire_on_commit=False)
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_duplicate_month_calendar_salon_unchanged():
    """
    Regression guard: AE-style calendar salon (fiscal_year_start=1) — duplicate
    behaviour identical to before the fix because position == calendar month.
    """
    engine = await _make_engine()
    user_ids: list[str] = []
    try:
        async with engine.connect() as conn:
            db = AsyncSession(bind=conn, expire_on_commit=False)
            email = f"fiscal-cal-{uuid.uuid4().hex[:8]}@example.com"
            uid = await _create_user(db, email)
            user_ids.append(uid)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            cookies = await _login(client, email)
            salon_id = await _create_salon(client, cookies, fiscal_year_start=1)

            src = await _create_report(
                client, cookies, salon_id, year=2025, month=3, ca="8000.00"
            )
            r = await client.post(
                f"/api/salons/{salon_id}/monthly-reports/{src}/duplicate",
                json={"target_months": [4, 5, 6], "overwrite": False},
                cookies=cookies,
            )
            assert r.status_code == 200, r.text
            assert r.json()["created"] == 3

        async with engine.connect() as conn:
            db = AsyncSession(bind=conn, expire_on_commit=False)
            from app.models.financial import MonthlyReport
            rows = (await db.execute(
                select(MonthlyReport).where(MonthlyReport.salon_id == salon_id)
            )).scalars().all()
            pairs = sorted((r.year, r.month) for r in rows)
            assert pairs == [(2025, 3), (2025, 4), (2025, 5), (2025, 6)], pairs

    finally:
        async with engine.connect() as conn:
            db = AsyncSession(bind=conn, expire_on_commit=False)
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_generate_from_template_uses_fiscal_window_for_richard3_pattern():
    """
    For salon with fiscal_year_start=3, generate-from-template year=2026 must
    populate Mar 2025 → Feb 2026 (cross-year window) — NOT Jan→Dec 2026.
    """
    engine = await _make_engine()
    user_ids: list[str] = []
    try:
        async with engine.connect() as conn:
            db = AsyncSession(bind=conn, expire_on_commit=False)
            email = f"fiscal-tpl-{uuid.uuid4().hex[:8]}@example.com"
            uid = await _create_user(db, email)
            user_ids.append(uid)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            cookies = await _login(client, email)
            salon_id = await _create_salon(client, cookies, fiscal_year_start=3)

            # Seed template via wizard
            wizard_payload = {
                "ca_ttc": 10000.0,
                "team": [],
                "expenses": [
                    {"category": "expenses.loyer_immobilier", "label": "Loyer",
                     "amount_ttc": 1200.0, "tva_rate": 0.200},
                ],
                "brand_purchases": [],
            }
            r = await client.post(
                f"/api/salons/{salon_id}/typical-month",
                json=wizard_payload,
                cookies=cookies,
            )
            assert r.status_code in (200, 201), r.text

            # Generate fiscal-ending year 2026
            r = await client.post(
                f"/api/salons/{salon_id}/years/2026/generate-from-template",
                json={},
                cookies=cookies,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["fiscal_year_start"] == 3
            # Wizard creates today's report first; subsequent generation may skip it.
            # Either way, total combined report count for fiscal-2026 must be 12.

        async with engine.connect() as conn:
            db = AsyncSession(bind=conn, expire_on_commit=False)
            from app.models.financial import MonthlyReport
            rows = (await db.execute(
                select(MonthlyReport).where(MonthlyReport.salon_id == salon_id)
            )).scalars().all()
            pairs = {(r.year, r.month) for r in rows}

            # Every month of fiscal-ending 2026 must exist
            expected = set(
                [(2025, m) for m in range(3, 13)]
                + [(2026, 1), (2026, 2)]
            )
            missing = expected - pairs
            assert not missing, (
                f"Missing fiscal-2026 months: {sorted(missing)}; got {sorted(pairs)}"
            )
            # NB: the wizard creates a calendar 'today' report as a side-effect
            # of the typical-month seeding (using `date.today()`), which can
            # land outside the fiscal-2026 window. That's an orthogonal
            # behaviour separately tracked — we don't assert against it here.
            # The critical fact for TASK-2.12.12 is the `expected` window
            # check above, which proves generate_year_from_template now
            # correctly populates the cross-year fiscal exercise.


    finally:
        async with engine.connect() as conn:
            db = AsyncSession(bind=conn, expire_on_commit=False)
            await _cleanup(db, user_ids)
        await engine.dispose()
