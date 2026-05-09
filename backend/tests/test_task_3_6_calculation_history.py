"""
Tests for Calculation History — Task 3.6

Tests the CRUD API for saving/listing/updating/deleting calculator history.
Follows the self-contained pattern (no shared fixtures — each test creates
its own user, salon, and cleans up after itself).

Run inside Docker:
  docker compose exec -w /app backend python -m pytest tests/test_task_3_6_calculation_history.py -v
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.financial import CalculationHistory


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _register_and_login(client: AsyncClient, uid: str) -> str:
    """Register + login a test user, return email."""
    email = f"hist_test_{uid}@example.com"
    await client.post("/api/auth/register", json={
        "email": email,
        "password": "Test1234!",
        "name": f"History Tester {uid}",
    })
    await client.post("/api/auth/login", json={
        "email": email,
        "password": "Test1234!",
    })
    return email


async def _create_salon(client: AsyncClient) -> str:
    """Create a salon and return its id."""
    res = await client.post("/api/salons", json={
        "name": "Salon Histoire Test",
        "business_type": "auto_micro",
    })
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def _cleanup(email: str) -> None:
    """Delete the test user from the DB."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy import text
        await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
        await db.commit()


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_and_list_history() -> None:
    """Saving a calculation and listing it back returns the entry."""
    uid = str(uuid.uuid4())[:8]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = await _register_and_login(client, uid)
        salon_id = await _create_salon(client)
        try:
            payload = {
                "calculator_type": "taxes",
                "inputs": {"business_type": "auto_micro", "ca_annuel": 50000},
                "outputs": {"net_monthly": "3247.00", "total_taxes": "10600.00"},
            }
            save_res = await client.post(
                f"/api/salons/{salon_id}/calculation-history/", json=payload
            )
            assert save_res.status_code == 201, save_res.text
            entry = save_res.json()
            assert entry["calculator_type"] == "taxes"
            assert entry["inputs"]["ca_annuel"] == 50000
            assert entry["is_pinned"] is False
            assert "id" in entry
            assert "created_at" in entry

            # List it back
            list_res = await client.get(
                f"/api/salons/{salon_id}/calculation-history/",
                params={"type": "taxes"},
            )
            assert list_res.status_code == 200
            entries = list_res.json()
            assert len(entries) == 1
            assert entries[0]["id"] == entry["id"]
        finally:
            await _cleanup(email)


@pytest.mark.asyncio
async def test_save_with_label() -> None:
    """Saving with an explicit label stores it correctly."""
    uid = str(uuid.uuid4())[:8]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = await _register_and_login(client, uid)
        salon_id = await _create_salon(client)
        try:
            payload = {
                "calculator_type": "seuil_salaire",
                "label": "Julie — 35h — 2200€",
                "inputs": {"salaire_brut": 2200, "heures_semaine": 35},
                "outputs": {"objectif_jour_ttc": "257.00"},
            }
            res = await client.post(
                f"/api/salons/{salon_id}/calculation-history/", json=payload
            )
            assert res.status_code == 201
            assert res.json()["label"] == "Julie — 35h — 2200€"
        finally:
            await _cleanup(email)


@pytest.mark.asyncio
async def test_list_filters_by_type() -> None:
    """Listing with type filter only returns entries of that type."""
    uid = str(uuid.uuid4())[:8]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = await _register_and_login(client, uid)
        salon_id = await _create_salon(client)
        try:
            base = f"/api/salons/{salon_id}/calculation-history/"
            # Save one taxes entry
            await client.post(base, json={
                "calculator_type": "taxes",
                "inputs": {"ca_annuel": 50000},
                "outputs": {"net_monthly": "3000"},
            })
            # Save one primes entry
            await client.post(base, json={
                "calculator_type": "primes",
                "inputs": {"objectif_jour": 300},
                "outputs": {"total_prime": "150"},
            })

            # Filter taxes only
            taxes_res = await client.get(base, params={"type": "taxes"})
            assert taxes_res.status_code == 200
            taxes_entries = taxes_res.json()
            assert len(taxes_entries) == 1
            assert taxes_entries[0]["calculator_type"] == "taxes"

            # Filter primes only
            primes_res = await client.get(base, params={"type": "primes"})
            assert primes_res.status_code == 200
            primes_entries = primes_res.json()
            assert len(primes_entries) == 1
            assert primes_entries[0]["calculator_type"] == "primes"
        finally:
            await _cleanup(email)


@pytest.mark.asyncio
async def test_list_returns_newest_first() -> None:
    """Entries are returned newest-first."""
    uid = str(uuid.uuid4())[:8]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = await _register_and_login(client, uid)
        salon_id = await _create_salon(client)
        try:
            base = f"/api/salons/{salon_id}/calculation-history/"
            ids = []
            for i in range(3):
                res = await client.post(base, json={
                    "calculator_type": "marge_revente",
                    "inputs": {"prix_achat_ht": i * 10},
                    "outputs": {"marge_pct": "0.60"},
                })
                ids.append(res.json()["id"])

            list_res = await client.get(base, params={"type": "marge_revente"})
            returned_ids = [e["id"] for e in list_res.json()]
            # Newest first = reverse insertion order
            assert returned_ids == list(reversed(ids))
        finally:
            await _cleanup(email)


@pytest.mark.asyncio
async def test_update_label_and_pin() -> None:
    """Renaming a label and pinning an entry via PUT works correctly."""
    uid = str(uuid.uuid4())[:8]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = await _register_and_login(client, uid)
        salon_id = await _create_salon(client)
        try:
            base = f"/api/salons/{salon_id}/calculation-history/"
            save_res = await client.post(base, json={
                "calculator_type": "volume_clients",
                "inputs": {"objectif_ca": 240000},
                "outputs": {"nb_clients_fichier_total": "450"},
            })
            calc_id = save_res.json()["id"]

            # Rename + pin in one call
            update_res = await client.put(
                f"{base}{calc_id}",
                json={"label": "Objectif 240k — Scénario A", "is_pinned": True},
            )
            assert update_res.status_code == 200
            updated = update_res.json()
            assert updated["label"] == "Objectif 240k — Scénario A"
            assert updated["is_pinned"] is True
        finally:
            await _cleanup(email)


@pytest.mark.asyncio
async def test_delete_entry() -> None:
    """Deleting an entry removes it from the list."""
    uid = str(uuid.uuid4())[:8]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = await _register_and_login(client, uid)
        salon_id = await _create_salon(client)
        try:
            base = f"/api/salons/{salon_id}/calculation-history/"
            save_res = await client.post(base, json={
                "calculator_type": "taxes",
                "inputs": {"ca_annuel": 30000},
                "outputs": {"net_monthly": "2000"},
            })
            calc_id = save_res.json()["id"]

            del_res = await client.delete(f"{base}{calc_id}")
            assert del_res.status_code == 204

            list_res = await client.get(base, params={"type": "taxes"})
            assert list_res.json() == []
        finally:
            await _cleanup(email)


@pytest.mark.asyncio
async def test_invalid_calculator_type_rejected() -> None:
    """Saving with an unknown calculator_type returns 400."""
    uid = str(uuid.uuid4())[:8]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = await _register_and_login(client, uid)
        salon_id = await _create_salon(client)
        try:
            res = await client.post(
                f"/api/salons/{salon_id}/calculation-history/",
                json={
                    "calculator_type": "invalid_type",
                    "inputs": {},
                    "outputs": {},
                },
            )
            assert res.status_code == 400
            assert "invalid_type" in res.json()["detail"]
        finally:
            await _cleanup(email)


@pytest.mark.asyncio
async def test_other_salon_cannot_access_history() -> None:
    """A user cannot access another salon's history (returns 404)."""
    uid1 = str(uuid.uuid4())[:8]
    uid2 = str(uuid.uuid4())[:8]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client1:
        email1 = await _register_and_login(client1, uid1)
        salon1_id = await _create_salon(client1)
        save_res = await client1.post(
            f"/api/salons/{salon1_id}/calculation-history/",
            json={
                "calculator_type": "taxes",
                "inputs": {"ca_annuel": 50000},
                "outputs": {},
            },
        )
        calc_id = save_res.json()["id"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client2:
        email2 = await _register_and_login(client2, uid2)
        salon2_id = await _create_salon(client2)

        # User 2 tries to access salon 1's history entry
        res = await client2.get(f"/api/salons/{salon1_id}/calculation-history/")
        assert res.status_code == 404  # salon1 not owned by user2

    await _cleanup(email1)
    await _cleanup(email2)


@pytest.mark.asyncio
async def test_auto_prune_removes_oldest_unpinned() -> None:
    """Auto-prune removes the oldest unpinned entry when limit is reached."""
    uid = str(uuid.uuid4())[:8]
    from app.routers.calculation_history import MAX_HISTORY_PER_TYPE
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = await _register_and_login(client, uid)
        salon_id = await _create_salon(client)
        try:
            base = f"/api/salons/{salon_id}/calculation-history/"

            # Save MAX_HISTORY_PER_TYPE entries
            first_id = None
            second_id = None
            for i in range(MAX_HISTORY_PER_TYPE):
                res = await client.post(base, json={
                    "calculator_type": "taxes",
                    "inputs": {"ca_annuel": i * 1000},
                    "outputs": {"net_monthly": str(i * 100)},
                })
                if i == 0:
                    first_id = res.json()["id"]
                elif i == 1:
                    second_id = res.json()["id"]

            # At this point we have exactly MAX entries — save one more to trigger prune
            res = await client.post(base, json={
                "calculator_type": "taxes",
                "inputs": {"ca_annuel": 999999},
                "outputs": {"net_monthly": "99999"},
            })
            assert res.status_code == 201

            # List should still be MAX entries (one was pruned)
            list_res = await client.get(base, params={"type": "taxes", "limit": 100})
            entries = list_res.json()
            assert len(entries) == MAX_HISTORY_PER_TYPE

            # The oldest entry (first_id) should be gone
            entry_ids = {e["id"] for e in entries}
            assert first_id not in entry_ids, "Oldest entry should have been auto-pruned"
        finally:
            await _cleanup(email)


@pytest.mark.asyncio
async def test_pinned_entry_skips_auto_prune() -> None:
    """A pinned entry is NOT removed by auto-prune."""
    uid = str(uuid.uuid4())[:8]
    from app.routers.calculation_history import MAX_HISTORY_PER_TYPE
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = await _register_and_login(client, uid)
        salon_id = await _create_salon(client)
        try:
            base = f"/api/salons/{salon_id}/calculation-history/"

            # Save first entry and pin it
            first_res = await client.post(base, json={
                "calculator_type": "marge_revente",
                "inputs": {"prix_achat_ht": 1},
                "outputs": {"marge_pct": "0.60"},
            })
            first_id = first_res.json()["id"]
            await client.put(f"{base}{first_id}", json={"is_pinned": True})

            # Fill up to MAX with unpinned entries
            for i in range(1, MAX_HISTORY_PER_TYPE):
                await client.post(base, json={
                    "calculator_type": "marge_revente",
                    "inputs": {"prix_achat_ht": i * 10},
                    "outputs": {"marge_pct": "0.60"},
                })

            # Save one more — should prune the oldest UNPINNED (not the pinned first entry)
            await client.post(base, json={
                "calculator_type": "marge_revente",
                "inputs": {"prix_achat_ht": 9999},
                "outputs": {"marge_pct": "0.60"},
            })

            # The pinned entry must still exist
            list_res = await client.get(base, params={"type": "marge_revente", "limit": 100})
            entry_ids = {e["id"] for e in list_res.json()}
            assert first_id in entry_ids, "Pinned entry must survive auto-prune"
        finally:
            await _cleanup(email)
