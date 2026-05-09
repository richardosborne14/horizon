"""
Tests for Task 2.10.7 — Calculator history polish.

Verifies:
  - user_label can be set via PUT and takes priority in the response
  - user_label can be cleared (set to None)
  - DELETE returns 409 when entry is pinned
  - DELETE succeeds on unpinned entries (204)
  - headline_result is returned by the list endpoint (already generated on POST)
"""
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app
from app.services.auth import hash_password


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_engine():
    """Fresh async engine per test module run."""
    return create_async_engine(settings.database_url, echo=False)


async def _cleanup(db: AsyncSession, user_ids: list) -> None:
    """Hard-delete test users — cascade removes salons, history, etc."""
    for uid in user_ids:
        await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
    await db.commit()


async def _setup(c: AsyncClient, engine, suffix: str) -> tuple[str, str]:
    """
    Create user, log in (sets cookie on c), create salon, return (salon_id, user_id).

    WHY inline SQL: tests need atomic user creation before the first API call.
    """
    uid = str(uuid.uuid4())
    email = f"hist_polish_{suffix}_{uid[:8]}@test.com"
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, email, name, password_hash, onboarding_completed) "
                "VALUES (:id, :email, 'Test', :pw, true)"
            ),
            {"id": uid, "email": email, "pw": hash_password("Password123!")},
        )
    r = await c.post("/api/auth/login", json={"email": email, "password": "Password123!"})
    assert r.status_code == 200, r.text
    salon_r = await c.post(
        "/api/salons", json={"name": "Test Salon", "business_type": "salon_coiffure"}
    )
    assert salon_r.status_code in (200, 201), salon_r.text
    return salon_r.json()["id"], uid


async def _save_entry(c: AsyncClient, salon_id: str) -> str:
    """Save one seuil_salaire calculation and return its ID."""
    r = await c.post(
        f"/api/salons/{salon_id}/calculation-history/",
        json={
            "calculator_type": "seuil_salaire",
            "inputs": {"heures_semaine": 35, "salaire_brut": 2000},
            "outputs": {"objectif_jour_ttc": "157.50"},
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ── Tests: user_label ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_user_label_via_put():
    """Setting user_label persists and is returned in the GET list."""
    engine = _make_engine()
    uid = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            salon_id, uid = await _setup(c, engine, "ul_set")
            calc_id = await _save_entry(c, salon_id)

            # Set the user_label
            put_r = await c.put(
                f"/api/salons/{salon_id}/calculation-history/{calc_id}",
                json={"user_label": "Rick temps plein"},
            )
            assert put_r.status_code == 200, put_r.text
            assert put_r.json()["user_label"] == "Rick temps plein"

            # Confirm it persists in the GET list
            list_r = await c.get(
                f"/api/salons/{salon_id}/calculation-history/",
                params={"type": "seuil_salaire"},
            )
            assert list_r.status_code == 200
            found = next((e for e in list_r.json() if e["id"] == calc_id), None)
            assert found is not None
            assert found["user_label"] == "Rick temps plein"
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, [uid] if uid else [])
        await engine.dispose()


@pytest.mark.asyncio
async def test_clear_user_label_via_put():
    """Setting user_label to null clears it (reverts to headline_result)."""
    engine = _make_engine()
    uid = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            salon_id, uid = await _setup(c, engine, "ul_clear")
            calc_id = await _save_entry(c, salon_id)

            # Set a label first
            await c.put(
                f"/api/salons/{salon_id}/calculation-history/{calc_id}",
                json={"user_label": "Temporary label"},
            )

            # Now clear it
            clear_r = await c.put(
                f"/api/salons/{salon_id}/calculation-history/{calc_id}",
                json={"user_label": None},
            )
            assert clear_r.status_code == 200
            assert clear_r.json()["user_label"] is None
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, [uid] if uid else [])
        await engine.dispose()


@pytest.mark.asyncio
async def test_put_without_user_label_does_not_clear_it():
    """A PUT that omits user_label entirely must NOT clear it."""
    engine = _make_engine()
    uid = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            salon_id, uid = await _setup(c, engine, "ul_notouch")
            calc_id = await _save_entry(c, salon_id)

            # Set a user_label
            await c.put(
                f"/api/salons/{salon_id}/calculation-history/{calc_id}",
                json={"user_label": "Do not touch"},
            )

            # Update is_pinned without mentioning user_label
            pin_r = await c.put(
                f"/api/salons/{salon_id}/calculation-history/{calc_id}",
                json={"is_pinned": True},
            )
            assert pin_r.status_code == 200
            # user_label must be preserved
            assert pin_r.json()["user_label"] == "Do not touch"
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, [uid] if uid else [])
        await engine.dispose()


# ── Tests: pinned-delete guard ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_pinned_returns_409():
    """Attempting to delete a pinned entry returns 409 Conflict."""
    engine = _make_engine()
    uid = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            salon_id, uid = await _setup(c, engine, "del_pin")
            calc_id = await _save_entry(c, salon_id)

            # Pin the entry
            await c.put(
                f"/api/salons/{salon_id}/calculation-history/{calc_id}",
                json={"is_pinned": True},
            )

            # Attempt to delete — must fail with 409
            del_r = await c.delete(
                f"/api/salons/{salon_id}/calculation-history/{calc_id}"
            )
            assert del_r.status_code == 409, del_r.text
            assert "épinglé" in del_r.json()["detail"]
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, [uid] if uid else [])
        await engine.dispose()


@pytest.mark.asyncio
async def test_unpin_then_delete_succeeds():
    """Unpin → delete gives 204 (no body)."""
    engine = _make_engine()
    uid = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            salon_id, uid = await _setup(c, engine, "del_unpin")
            calc_id = await _save_entry(c, salon_id)

            # Pin then unpin
            await c.put(
                f"/api/salons/{salon_id}/calculation-history/{calc_id}",
                json={"is_pinned": True},
            )
            await c.put(
                f"/api/salons/{salon_id}/calculation-history/{calc_id}",
                json={"is_pinned": False},
            )

            # Now delete — must succeed
            del_r = await c.delete(
                f"/api/salons/{salon_id}/calculation-history/{calc_id}"
            )
            assert del_r.status_code == 204, del_r.text

            # Confirm gone
            list_r = await c.get(f"/api/salons/{salon_id}/calculation-history/")
            ids = [e["id"] for e in list_r.json()]
            assert calc_id not in ids
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, [uid] if uid else [])
        await engine.dispose()


@pytest.mark.asyncio
async def test_delete_unpinned_returns_204():
    """A fresh (never pinned) entry can be deleted immediately."""
    engine = _make_engine()
    uid = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            salon_id, uid = await _setup(c, engine, "del_fresh")
            calc_id = await _save_entry(c, salon_id)

            del_r = await c.delete(
                f"/api/salons/{salon_id}/calculation-history/{calc_id}"
            )
            assert del_r.status_code == 204
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, [uid] if uid else [])
        await engine.dispose()


# ── Tests: headline_result ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_headline_result_populated_on_save():
    """
    headline_result is auto-generated on POST from outputs.
    For seuil_salaire with objectif_jour_ttc, it should be non-null.
    """
    engine = _make_engine()
    uid = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            salon_id, uid = await _setup(c, engine, "headline")
            calc_id = await _save_entry(c, salon_id)

            list_r = await c.get(
                f"/api/salons/{salon_id}/calculation-history/",
                params={"type": "seuil_salaire"},
            )
            assert list_r.status_code == 200
            found = next((e for e in list_r.json() if e["id"] == calc_id), None)
            assert found is not None
            # headline_result must be present (format_headline returns a non-None value
            # for seuil_salaire with objectif_jour_ttc)
            assert found["headline_result"] is not None
            assert len(found["headline_result"]) > 0
    finally:
        async with AsyncSession(engine) as db:
            await _cleanup(db, [uid] if uid else [])
        await engine.dispose()
