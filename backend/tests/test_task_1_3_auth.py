"""
Tests for Task 1.3 — Auth API.

Covers:
- Unit tests: password hashing, rate limiting (no DB required)
- Service tests: session management, reset tokens (uses test DB)
- API integration tests: full register → login → me → logout flow

Pattern: create a fresh async engine per test (see LEARNINGS.md 2026-04-10
for why module-scoped engines cause asyncpg InterfaceError on second test).
"""

import pytest
from datetime import datetime, timedelta, timezone
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models import User, Session, PasswordResetToken  # noqa — registers models
from app.services.auth import (
    check_rate_limit,
    clear_login_attempts,
    hash_password,
    record_login_attempt,
    verify_password,
    _login_attempts,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


# Reusable session kwargs — expire_on_commit=False matches the production
# session factory (AsyncSessionLocal) so ORM objects are NOT expired after
# commit. Without this, attributes accessed after db.commit() in the same
# request (e.g. user.email in reset_password_request, or user in get_me
# after get_current_user's sliding-window commit) cause MissingGreenlet.
_SESSION_KWARGS = {"expire_on_commit": False}


async def _setup_engine():
    """
    Connect to the live DB (already migrated by Alembic). Return engine.

    Why NOT create_all: asyncpg mis-renders bare-string server_default values
    (e.g. "'[]'" becomes DEFAULT '''[]''') across multiple models, causing
    DDL errors at test collection time. Using the already-migrated live DB
    avoids this entirely and tests against the real schema.
    See LEARNINGS.md 2026-04-10.
    """
    engine = create_async_engine(settings.database_url, echo=False)
    return engine


async def _teardown_engine(engine):
    """
    Delete test rows inserted during this test run and dispose the engine.

    All integration tests use '@example.com' emails. Deleting by that domain
    cascades to sessions and password_reset_tokens automatically.
    """
    async with AsyncSession(engine, **_SESSION_KWARGS) as session:
        await session.execute(
            text("DELETE FROM users WHERE email LIKE '%@example.com'")
        )
        await session.commit()
    await engine.dispose()


# ─────────────────────────────────────────────────────────────────────────────
# Unit Tests — pure functions (no DB)
# ─────────────────────────────────────────────────────────────────────────────


class TestPasswordHashing:
    """Tests for hash_password and verify_password."""

    def test_hash_is_not_plain_text(self):
        """Hashed password must not equal the original string."""
        plain = "securepassword123"
        hashed = hash_password(plain)
        assert hashed != plain

    def test_hash_is_bcrypt_format(self):
        """Bcrypt hashes start with $2b$."""
        hashed = hash_password("anypassword!")
        assert hashed.startswith("$2b$")

    def test_verify_correct_password(self):
        """verify_password returns True for matching plain + hash."""
        plain = "correctpassword"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_wrong_password(self):
        """verify_password returns False when password doesn't match."""
        hashed = hash_password("correctpassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_two_hashes_of_same_password_differ(self):
        """bcrypt generates different salts — same plain → different hash."""
        plain = "samepassword"
        hash1 = hash_password(plain)
        hash2 = hash_password(plain)
        assert hash1 != hash2
        # But both should verify correctly
        assert verify_password(plain, hash1) is True
        assert verify_password(plain, hash2) is True


class TestRateLimiting:
    """Tests for the login rate limiter."""

    def setup_method(self):
        """Clear rate limit state before each test."""
        _login_attempts.clear()

    def test_first_five_attempts_allowed(self):
        """Up to 5 attempts should be allowed."""
        email = "ratelimit@test.com"
        for _ in range(5):
            assert check_rate_limit(email) is True
            record_login_attempt(email)

    def test_sixth_attempt_blocked(self):
        """After 5 failed attempts, the 6th should be blocked."""
        email = "blocked@test.com"
        for _ in range(5):
            record_login_attempt(email)
        assert check_rate_limit(email) is False

    def test_clear_resets_counter(self):
        """clear_login_attempts should allow further attempts."""
        email = "clearme@test.com"
        for _ in range(5):
            record_login_attempt(email)
        assert check_rate_limit(email) is False
        clear_login_attempts(email)
        assert check_rate_limit(email) is True

    def test_different_emails_are_independent(self):
        """Rate limit on one email doesn't affect another."""
        email_a = "a@test.com"
        email_b = "b@test.com"
        for _ in range(5):
            record_login_attempt(email_a)
        assert check_rate_limit(email_a) is False
        assert check_rate_limit(email_b) is True

    def test_old_attempts_expire_from_window(self):
        """Attempts outside the 15-minute window should not count."""
        email = "expiry@test.com"
        # Inject old timestamps directly into the store
        old_time = datetime.now(timezone.utc) - timedelta(minutes=20)
        _login_attempts[email] = [old_time] * 5
        # Should be allowed because all 5 are outside the window
        assert check_rate_limit(email) is True


class TestPasswordResetTokenIsValid:
    """Tests for PasswordResetToken.is_valid property."""

    def _make_token(self, used_at=None, expires_offset_hours=1):
        """
        Create a lightweight stub to test the is_valid property.

        We cannot use SQLAlchemy's __new__ directly — the mapper state
        is not initialised and attribute assignment raises AttributeError.
        Instead we create a plain object that has the same attributes
        and call the is_valid property directly on it.
        """
        from types import SimpleNamespace

        # Build a SimpleNamespace with the same attributes is_valid reads
        stub = SimpleNamespace(
            used_at=used_at,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=expires_offset_hours),
        )
        # Call the property's underlying function directly on our stub
        # (unbound call since stub is not a PasswordResetToken instance)
        stub.is_valid = PasswordResetToken.is_valid.fget(stub)  # type: ignore[attr-defined]
        return stub

    def test_fresh_token_is_valid(self):
        """A new token with future expiry and no used_at is valid."""
        token = self._make_token()
        assert token.is_valid is True

    def test_used_token_is_invalid(self):
        """A token with used_at set is invalid."""
        token = self._make_token(used_at=datetime.now(timezone.utc))
        assert token.is_valid is False

    def test_expired_token_is_invalid(self):
        """A token past its expiry is invalid."""
        token = self._make_token(expires_offset_hours=-1)
        assert token.is_valid is False


# ─────────────────────────────────────────────────────────────────────────────
# API Integration Tests — full HTTP round-trips
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_creates_user_and_sets_cookie():
    """POST /api/auth/register should create user and return session cookie."""
    engine = await _setup_engine()
    try:
        async def override_get_db():
            async with AsyncSession(engine, **_SESSION_KWARGS) as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/auth/register",
                json={
                    "email": "test@example.com",
                    "password": "securepassword123",
                    "name": "Test User",
                },
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["message"] == "Compte créé avec succès"
            assert data["user"]["email"] == "test@example.com"
            assert data["user"]["name"] == "Test User"
            assert data["user"]["role"] == "user"
            # Cookie should be set
            assert settings.session_cookie_name in resp.cookies
    finally:
        app.dependency_overrides.clear()
        await _teardown_engine(engine)


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409():
    """Registering with an existing email should return 409 Conflict."""
    engine = await _setup_engine()
    try:
        async def override_get_db():
            async with AsyncSession(engine, **_SESSION_KWARGS) as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            payload = {
                "email": "duplicate@example.com",
                "password": "password123",
                "name": "First User",
            }
            await client.post("/api/auth/register", json=payload)
            resp = await client.post("/api/auth/register", json=payload)
            assert resp.status_code == 409
    finally:
        app.dependency_overrides.clear()
        await _teardown_engine(engine)


@pytest.mark.asyncio
async def test_login_valid_credentials():
    """POST /api/auth/login with correct credentials should succeed."""
    engine = await _setup_engine()
    try:
        async def override_get_db():
            async with AsyncSession(engine, **_SESSION_KWARGS) as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Register first
            await client.post(
                "/api/auth/register",
                json={
                    "email": "login@example.com",
                    "password": "mypassword123",
                    "name": "Login User",
                },
            )
            # Then login
            resp = await client.post(
                "/api/auth/login",
                json={"email": "login@example.com", "password": "mypassword123"},
            )
            assert resp.status_code == 200
            assert resp.json()["message"] == "Connexion réussie"
            assert settings.session_cookie_name in resp.cookies
    finally:
        app.dependency_overrides.clear()
        await _teardown_engine(engine)


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401():
    """POST /api/auth/login with wrong password should return 401."""
    engine = await _setup_engine()
    try:
        async def override_get_db():
            async with AsyncSession(engine, **_SESSION_KWARGS) as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        _login_attempts.clear()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post(
                "/api/auth/register",
                json={
                    "email": "wrongpw@example.com",
                    "password": "correctpassword",
                    "name": "Test",
                },
            )
            resp = await client.post(
                "/api/auth/login",
                json={"email": "wrongpw@example.com", "password": "wrongpassword"},
            )
            assert resp.status_code == 401
            assert resp.json()["detail"] == "Identifiants invalides"
    finally:
        app.dependency_overrides.clear()
        _login_attempts.clear()
        await _teardown_engine(engine)


@pytest.mark.asyncio
async def test_login_unknown_email_returns_401():
    """POST /api/auth/login with unknown email should return 401 (not 404)."""
    engine = await _setup_engine()
    try:
        async def override_get_db():
            async with AsyncSession(engine, **_SESSION_KWARGS) as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        _login_attempts.clear()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/auth/login",
                json={"email": "nobody@example.com", "password": "anypassword"},
            )
            # Must be 401 — not 404 (no user enumeration)
            assert resp.status_code == 401
            assert resp.json()["detail"] == "Identifiants invalides"
    finally:
        app.dependency_overrides.clear()
        _login_attempts.clear()
        await _teardown_engine(engine)


@pytest.mark.asyncio
async def test_get_me_authenticated():
    """GET /api/users/me should return user profile when authenticated."""
    engine = await _setup_engine()
    try:
        async def override_get_db():
            async with AsyncSession(engine, **_SESSION_KWARGS) as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Register (sets cookie)
            await client.post(
                "/api/auth/register",
                json={
                    "email": "me@example.com",
                    "password": "password123",
                    "name": "Me User",
                },
            )
            # GET /me with the cookie
            resp = await client.get("/api/users/me")
            assert resp.status_code == 200
            assert resp.json()["email"] == "me@example.com"
    finally:
        app.dependency_overrides.clear()
        await _teardown_engine(engine)


@pytest.mark.asyncio
async def test_get_me_unauthenticated_returns_401():
    """GET /api/users/me without a session cookie should return 401."""
    engine = await _setup_engine()
    try:
        async def override_get_db():
            async with AsyncSession(engine, **_SESSION_KWARGS) as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/users/me")
            assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()
        await _teardown_engine(engine)


@pytest.mark.asyncio
async def test_logout_clears_session():
    """POST /api/auth/logout should clear the session cookie."""
    engine = await _setup_engine()
    try:
        async def override_get_db():
            async with AsyncSession(engine, **_SESSION_KWARGS) as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post(
                "/api/auth/register",
                json={
                    "email": "logout@example.com",
                    "password": "password123",
                    "name": "Logout User",
                },
            )
            # Logout
            resp = await client.post("/api/auth/logout")
            assert resp.status_code == 200
            assert resp.json()["message"] == "Déconnecté avec succès"

            # After logout, /me should return 401
            resp_me = await client.get("/api/users/me")
            assert resp_me.status_code == 401
    finally:
        app.dependency_overrides.clear()
        await _teardown_engine(engine)


@pytest.mark.asyncio
async def test_reset_password_request_always_200():
    """
    POST /api/auth/reset-password should always return 200
    even for unknown emails (no user enumeration).
    """
    engine = await _setup_engine()
    try:
        async def override_get_db():
            async with AsyncSession(engine, **_SESSION_KWARGS) as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Known email
            await client.post(
                "/api/auth/register",
                json={
                    "email": "reset@example.com",
                    "password": "password123",
                    "name": "Reset User",
                },
            )
            resp_known = await client.post(
                "/api/auth/reset-password", json={"email": "reset@example.com"}
            )
            assert resp_known.status_code == 200

            # Unknown email — must also return 200
            resp_unknown = await client.post(
                "/api/auth/reset-password", json={"email": "nobody@example.com"}
            )
            assert resp_unknown.status_code == 200

            # Both responses should have the same message
            assert resp_known.json()["message"] == resp_unknown.json()["message"]
    finally:
        app.dependency_overrides.clear()
        await _teardown_engine(engine)


@pytest.mark.asyncio
async def test_reset_password_confirm_invalid_token():
    """POST /api/auth/reset-password/confirm with bad token should return 400."""
    engine = await _setup_engine()
    try:
        async def override_get_db():
            async with AsyncSession(engine, **_SESSION_KWARGS) as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/auth/reset-password/confirm",
                json={"token": "invalid-token-xyz", "new_password": "newpassword123"},
            )
            assert resp.status_code == 400
            assert "invalide" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()
        await _teardown_engine(engine)


@pytest.mark.asyncio
async def test_full_password_reset_flow():
    """
    Full password reset flow:
    register → request reset → confirm with token → login with new password.
    """
    from app.services.auth import create_reset_token, get_user_by_email

    engine = await _setup_engine()
    try:
        async def override_get_db():
            async with AsyncSession(engine, **_SESSION_KWARGS) as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Step 1: Register
            await client.post(
                "/api/auth/register",
                json={
                    "email": "flowtest@example.com",
                    "password": "oldpassword123",
                    "name": "Flow Test",
                },
            )

            # Step 2: Create a reset token directly (bypassing email)
            async with AsyncSession(engine, **_SESSION_KWARGS) as db:
                user = await get_user_by_email(db, "flowtest@example.com")
                reset_tok = await create_reset_token(db, user.id)
                await db.commit()
                token_str = reset_tok.token

            # Step 3: Confirm reset with the token
            resp = await client.post(
                "/api/auth/reset-password/confirm",
                json={"token": token_str, "new_password": "newpassword456"},
            )
            assert resp.status_code == 200

            # Step 4: Login with new password should work
            await client.post("/api/auth/logout")
            resp_login = await client.post(
                "/api/auth/login",
                json={"email": "flowtest@example.com", "password": "newpassword456"},
            )
            assert resp_login.status_code == 200

            # Step 5: Old password should no longer work
            await client.post("/api/auth/logout")
            resp_old = await client.post(
                "/api/auth/login",
                json={"email": "flowtest@example.com", "password": "oldpassword123"},
            )
            assert resp_old.status_code == 401
    finally:
        app.dependency_overrides.clear()
        _login_attempts.clear()
        await _teardown_engine(engine)
