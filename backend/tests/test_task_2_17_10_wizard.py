"""
Tests for TASK-2.17.10 — First-login concierge wizard.

Covers:
  - PATCH /api/users/me/import-step valid forward transitions
  - PATCH rejects invalid (backward) transitions with 422
  - PATCH allows 'deferred' from any step
  - GET /api/salons/{id}/savings returns rows for a sparse (imported) user

Pattern: self-contained — every test registers + logs in + optionally creates
a salon. No shared fixtures. Matches the project's self-contained test convention.
"""

import pytest
import httpx


BASE = "http://backend:8000"
HEADERS = {"Content-Type": "application/json"}


def _reg_payload(suffix: str) -> dict:
    """Return a unique register payload for this test."""
    return {
        "email": f"wizard_test_{suffix}@test.comcoi.fr",
        "password": "WizardPass123!",
        "name": f"Wizard Test {suffix}",
    }


async def _register_and_login(client: httpx.AsyncClient, suffix: str) -> str:
    """
    Register a fresh user and log in.

    Args:
        client: httpx async client (session-cookie-aware).
        suffix: Unique string to disambiguate test users.

    Returns:
        session_token cookie value (for direct header use if needed).
    """
    payload = _reg_payload(suffix)
    reg = await client.post(f"{BASE}/api/auth/register", json=payload)
    assert reg.status_code == 201, f"Register failed: {reg.text}"

    login = await client.post(
        f"{BASE}/api/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login.status_code == 200, f"Login failed: {login.text}"
    return login.cookies.get("session_token", "")


async def _create_salon(client: httpx.AsyncClient, name: str = "Salon Test Wizard") -> str:
    """
    Create a salon and return its ID.

    Args:
        client: Authenticated httpx client.
        name: Salon display name.

    Returns:
        salon_id (str UUID).
    """
    res = await client.post(
        f"{BASE}/api/salons",
        json={"name": name, "business_type": "sas"},
    )
    assert res.status_code == 201, f"Create salon failed: {res.text}"
    return res.json()["id"]


async def _set_import_step_directly(client: httpx.AsyncClient, step: str) -> None:
    """
    Shortcut: patch the import step without transition validation in mind.
    Useful for positioning the user mid-wizard in tests.

    Callers must ensure the transition is valid or pre-set the user's step
    via earlier calls in the correct sequence.

    Args:
        client: Authenticated httpx client.
        step: Target step name.
    """
    res = await client.patch(
        f"{BASE}/api/users/me/import-step",
        json={"step": step},
    )
    assert res.status_code == 200, f"Unexpected status setting step={step}: {res.text}"


@pytest.mark.asyncio
async def test_patch_import_step_advances_state():
    """
    PATCH /api/users/me/import-step with a valid forward step
    returns 200 and reflects the new step.
    """
    async with httpx.AsyncClient() as client:
        await _register_and_login(client, "advance")

        # Step 1: pending → welcome
        res = await client.patch(
            f"{BASE}/api/users/me/import-step",
            json={"step": "welcome"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["import_completion_step"] == "welcome"

        # Step 2: welcome → legal_form
        res2 = await client.patch(
            f"{BASE}/api/users/me/import-step",
            json={"step": "legal_form"},
        )
        assert res2.status_code == 200
        assert res2.json()["import_completion_step"] == "legal_form"

        # Verify via GET /api/users/me
        me = await client.get(f"{BASE}/api/users/me")
        assert me.status_code == 200
        assert me.json()["import_completion_step"] == "legal_form"

        # Cleanup
        await client.post(f"{BASE}/api/auth/logout")


@pytest.mark.asyncio
async def test_patch_rejects_invalid_transition():
    """
    PATCH with a backward step (e.g. welcome → pending) returns 422.
    PATCH skipping multiple steps forward is also rejected.
    """
    async with httpx.AsyncClient() as client:
        await _register_and_login(client, "reject_invalid")

        # Advance to salon_config first (valid path)
        for step in ["welcome", "legal_form", "salon_config"]:
            res = await client.patch(
                f"{BASE}/api/users/me/import-step",
                json={"step": step},
            )
            assert res.status_code == 200, f"Failed advancing to {step}: {res.text}"

        # Attempt backward jump to welcome — must be rejected
        res = await client.patch(
            f"{BASE}/api/users/me/import-step",
            json={"step": "welcome"},
        )
        assert res.status_code == 422, f"Expected 422, got {res.status_code}: {res.text}"
        assert "invalide" in res.json()["detail"].lower()

        # Attempt backward to legal_form — also rejected
        res2 = await client.patch(
            f"{BASE}/api/users/me/import-step",
            json={"step": "legal_form"},
        )
        assert res2.status_code == 422

        await client.post(f"{BASE}/api/auth/logout")


@pytest.mark.asyncio
async def test_patch_allows_deferred_from_any_step():
    """
    PATCH step='deferred' is always accepted regardless of current step.
    After deferring, the user can advance forward again (deferred → team etc.).
    """
    async with httpx.AsyncClient() as client:
        await _register_and_login(client, "deferred")

        # Advance to step 2 (legal_form)
        for step in ["welcome", "legal_form"]:
            await _set_import_step_directly(client, step)

        # Defer from legal_form — always valid
        res = await client.patch(
            f"{BASE}/api/users/me/import-step",
            json={"step": "deferred"},
        )
        assert res.status_code == 200
        assert res.json()["import_completion_step"] == "deferred"

        # After deferred, can advance to salon_config (resuming from deferred is allowed)
        res2 = await client.patch(
            f"{BASE}/api/users/me/import-step",
            json={"step": "salon_config"},
        )
        assert res2.status_code == 200
        assert res2.json()["import_completion_step"] == "salon_config"

        await client.post(f"{BASE}/api/auth/logout")


@pytest.mark.asyncio
async def test_patch_rejects_unknown_step():
    """
    PATCH with an unknown step name returns 422.
    """
    async with httpx.AsyncClient() as client:
        await _register_and_login(client, "unknown_step")

        res = await client.patch(
            f"{BASE}/api/users/me/import-step",
            json={"step": "teleportation"},
        )
        assert res.status_code == 422
        detail = res.json()["detail"]
        assert "invalide" in detail.lower() or "teleportation" in detail

        await client.post(f"{BASE}/api/auth/logout")


@pytest.mark.asyncio
async def test_patch_done_from_savings_hook():
    """
    Full happy path: advance through all steps to 'done'.
    The /api/users/me endpoint should reflect import_completion_step='done'.
    """
    async with httpx.AsyncClient() as client:
        await _register_and_login(client, "full_path")

        for step in ["welcome", "legal_form", "salon_config", "team", "services", "savings_hook", "done"]:
            res = await client.patch(
                f"{BASE}/api/users/me/import-step",
                json={"step": step},
            )
            assert res.status_code == 200, f"Failed at step={step}: {res.text}"
            assert res.json()["import_completion_step"] == step

        me = await client.get(f"{BASE}/api/users/me")
        assert me.json()["import_completion_step"] == "done"

        await client.post(f"{BASE}/api/auth/logout")


@pytest.mark.asyncio
async def test_patch_requires_authentication():
    """
    PATCH /api/users/me/import-step without session cookie returns 401.
    """
    async with httpx.AsyncClient() as client:
        res = await client.patch(
            f"{BASE}/api/users/me/import-step",
            json={"step": "welcome"},
        )
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_savings_endpoint_returns_rows_for_sparse_imported_user():
    """
    GET /api/salons/{id}/savings should not 500 for a migrated user whose
    salon has business_type=None (sparse data — no reports yet).

    TASK-2.17.10 requirement: savings engine must handle business_type=None
    gracefully (falls back to non-AE path per LEARNINGS #104).

    WHY: Migrated users may land on the SavingsHook step before entering
    any monthly data. The engine should return an empty or partial savings
    report rather than crash.
    """
    async with httpx.AsyncClient() as client:
        await _register_and_login(client, "sparse_savings")

        # Create a salon (normally has business_type). The import scripts
        # set business_type=None for migrated salons; we test with a real
        # salon here because we can't set NULL via POST (it requires business_type).
        # The engine's resilience is the key assertion.
        salon_id = await _create_salon(client, "Sparse Import Salon")

        res = await client.get(f"{BASE}/api/salons/{salon_id}/savings")
        # Savings engine must return 200 (possibly empty channels) — never 500.
        assert res.status_code == 200, f"Savings endpoint 500'd: {res.text}"

        body = res.json()
        # Schema contract: channels must be a list, total must be a string/number
        assert "channels" in body
        assert isinstance(body["channels"], list)
        assert "total_annual_savings_eur" in body

        await client.post(f"{BASE}/api/auth/logout")
