"""
Auth service — business logic for authentication.

Handles password hashing/verification, session lifecycle, rate limiting,
and password reset token management.

Never import FastAPI request/response objects here — keep this layer
framework-agnostic so it can be tested without spinning up the web server.
"""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.auth import PasswordResetToken, Session
from app.models.user import User

# ── Rate limiting ─────────────────────────────────────────────────────────────
# In-memory store: { email: [(attempt_timestamp, ...), ...] }
# Sufficient for MVP single-instance deployment. Replace with Redis if scaling.
_login_attempts: dict[str, list[datetime]] = defaultdict(list)

# Config constants
RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_WINDOW_MINUTES = 15


# ── Password helpers ──────────────────────────────────────────────────────────


def hash_password(plain: str) -> str:
    """
    Hash a plain-text password using bcrypt.

    Args:
        plain: The raw password string from the user.

    Returns:
        A bcrypt hash string suitable for database storage.
    """
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify a plain-text password against a stored bcrypt hash.

    Args:
        plain: The raw password string to check.
        hashed: The bcrypt hash stored in the database.

    Returns:
        True if the password matches, False otherwise.
    """
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ── Rate limiting ─────────────────────────────────────────────────────────────


def check_rate_limit(email: str) -> bool:
    """
    Check whether a login attempt is allowed for the given email.

    Implements a sliding window: counts attempts within the last
    RATE_LIMIT_WINDOW_MINUTES and blocks if >= RATE_LIMIT_MAX_ATTEMPTS.

    Args:
        email: The email address being used for login.

    Returns:
        True if the attempt is allowed, False if rate-limited.
    """
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)

    # Prune attempts outside the window
    _login_attempts[email] = [
        ts for ts in _login_attempts[email] if ts > window_start
    ]

    return len(_login_attempts[email]) < RATE_LIMIT_MAX_ATTEMPTS


def record_login_attempt(email: str) -> None:
    """
    Record a failed login attempt for rate limiting purposes.

    Only failed attempts are recorded. Successful logins clear the counter
    (see clear_login_attempts).

    Args:
        email: The email address that attempted login.
    """
    _login_attempts[email].append(datetime.now(timezone.utc))


def clear_login_attempts(email: str) -> None:
    """
    Clear the failed attempt counter for an email after successful login.

    Args:
        email: The email address that logged in successfully.
    """
    _login_attempts.pop(email, None)


# ── User lookup ───────────────────────────────────────────────────────────────


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """
    Fetch a user by email address.

    Args:
        db: Async database session.
        email: Email to look up (case-insensitive via lower()).

    Returns:
        The User model instance, or None if not found.
    """
    result = await db.execute(
        select(User).where(User.email == email.lower().strip())
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
    """
    Fetch a user by UUID.

    Args:
        db: Async database session.
        user_id: The UUID of the user to fetch.

    Returns:
        The User model instance, or None if not found.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


# ── User creation ─────────────────────────────────────────────────────────────


async def create_user(
    db: AsyncSession,
    email: str,
    password: str,
    name: str,
    phone: Optional[str] = None,
) -> User:
    """
    Create a new user account.

    Hashes the password before storage. Email is normalised to lowercase.

    Args:
        db: Async database session.
        email: Email address (normalised to lowercase).
        password: Plain-text password to hash and store.
        name: Display name.
        phone: Optional phone number.

    Returns:
        The newly created and flushed User instance.
    """
    user = User(
        email=email.lower().strip(),
        password_hash=hash_password(password),
        name=name.strip(),
        phone=phone,
    )
    db.add(user)
    await db.flush()  # Flush to get the generated UUID without committing
    return user


# ── Session management ────────────────────────────────────────────────────────


def _session_expiry() -> datetime:
    """
    Calculate the session expiry timestamp.

    Returns:
        UTC datetime `session_expire_days` from now.
    """
    return datetime.now(timezone.utc) + timedelta(days=settings.session_expire_days)


async def create_session(db: AsyncSession, user_id: uuid.UUID) -> Session:
    """
    Create a new authenticated session for a user.

    Args:
        db: Async database session.
        user_id: UUID of the user to create a session for.

    Returns:
        The newly created Session instance (not yet committed).
    """
    session = Session(
        user_id=user_id,
        token=Session.generate_token(),
        expires_at=_session_expiry(),
    )
    db.add(session)
    await db.flush()
    return session


async def get_session_by_token(
    db: AsyncSession, token: str
) -> Optional[Session]:
    """
    Look up a session by its token string.

    Args:
        db: Async database session.
        token: The raw token string from the cookie.

    Returns:
        The Session if found and not expired, otherwise None.
    """
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Session).where(
            Session.token == token,
            Session.expires_at > now,
        )
    )
    return result.scalar_one_or_none()


async def refresh_session(db: AsyncSession, session: Session) -> None:
    """
    Extend a session's expiry (sliding window).

    Called on each authenticated request to keep active users logged in.

    Args:
        db: Async database session.
        session: The Session model instance to extend.
    """
    session.expires_at = _session_expiry()
    await db.flush()


async def delete_session(db: AsyncSession, token: str) -> None:
    """
    Delete a session by token (logout).

    Args:
        db: Async database session.
        token: The session token to invalidate.
    """
    session = await get_session_by_token(db, token)
    if session:
        await db.delete(session)
        await db.flush()


# ── Password reset ────────────────────────────────────────────────────────────


async def create_reset_token(
    db: AsyncSession, user_id: uuid.UUID
) -> PasswordResetToken:
    """
    Create a one-time password reset token.

    The token expires in 1 hour and can only be used once.
    Any existing unused tokens for this user are left in place
    (they will expire naturally).

    Args:
        db: Async database session.
        user_id: UUID of the user requesting a password reset.

    Returns:
        The newly created PasswordResetToken instance.
    """
    reset_token = PasswordResetToken(
        user_id=user_id,
        token=PasswordResetToken.generate_token(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(reset_token)
    await db.flush()
    return reset_token


async def get_valid_reset_token(
    db: AsyncSession, token: str
) -> Optional[PasswordResetToken]:
    """
    Look up a reset token that is still valid (not used, not expired).

    Args:
        db: Async database session.
        token: The token string from the reset URL.

    Returns:
        The PasswordResetToken if valid, otherwise None.
    """
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token == token,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
    )
    return result.scalar_one_or_none()


async def consume_reset_token(
    db: AsyncSession, reset_token: PasswordResetToken, new_password: str
) -> None:
    """
    Consume a reset token: update the user's password and mark the token used.

    Args:
        db: Async database session.
        reset_token: The valid PasswordResetToken to consume.
        new_password: The new plain-text password to hash and store.
    """
    # Mark token as used so it cannot be replayed
    reset_token.used_at = datetime.now(timezone.utc)

    # Update the user's password
    user = await get_user_by_id(db, reset_token.user_id)
    if user:
        user.password_hash = hash_password(new_password)

    await db.flush()


# ── Login stamp ───────────────────────────────────────────────────────────────


async def update_last_login(db: AsyncSession, user: User) -> None:
    """
    Update the user's last_login_at timestamp.

    Called after every successful login.

    Args:
        db: Async database session.
        user: The User model instance that just logged in.
    """
    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()
