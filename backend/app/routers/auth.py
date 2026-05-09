"""
Auth router — register, login, logout, password reset, current user.

All endpoints are under /api (prefix applied in routers/__init__.py).
Cookie is set/cleared directly on the Response object.

Error messages are intentionally generic for security:
- Login failures always say "Identifiants invalides" (no user enumeration)
- Password reset always returns 200 even if email not found (no user enumeration)
"""

import logging

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.email import send_reset_password_email
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordConfirmRequest,
    ResetPasswordRequest,
    UserResponse,
)
from app.services import auth as auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    """
    Set the session cookie on the HTTP response.

    Uses httpOnly so JavaScript cannot read it (XSS protection).
    SameSite=Lax protects against CSRF while allowing normal navigation.
    Secure is enabled in production (HTTPS only).

    Args:
        response: The FastAPI Response object to set the cookie on.
        token: The session token string to store in the cookie.
    """
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
        max_age=settings.session_expire_days * 24 * 60 * 60,  # seconds
    )


def _clear_session_cookie(response: Response) -> None:
    """
    Clear the session cookie from the browser.

    Args:
        response: The FastAPI Response object to delete the cookie from.
    """
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


# ── POST /api/auth/register ───────────────────────────────────────────────────


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un compte",
)
async def register(
    body: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """
    Create a new user account and start a session.

    On success:
    - Creates the user record with a hashed password
    - Creates a session and sets the httpOnly session cookie
    - Returns the user profile

    On failure:
    - 409 if email already registered
    - 422 if validation fails (password too short, etc.)

    Args:
        body: Registration request with email, password, name, phone.
        response: FastAPI response object (used to set cookie).
        db: Async database session.

    Returns:
        AuthResponse with confirmation message and user profile.
    """
    # Check for duplicate email before trying to insert
    existing = await auth_service.get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte existe déjà avec cette adresse email",
        )

    try:
        user = await auth_service.create_user(
            db=db,
            email=body.email,
            password=body.password,
            name=body.name,
            phone=body.phone,
        )
        session = await auth_service.create_session(db, user.id)
        # Capture token BEFORE commit — commit expires all ORM attributes
        # and accessing session.token after commit triggers a sync lazy-load
        # which raises MissingGreenlet in async context. See LEARNINGS.md.
        session_token = session.token
        await db.commit()
        await db.refresh(user)
    except IntegrityError:
        await db.rollback()
        # Race condition: duplicate email registered simultaneously
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte existe déjà avec cette adresse email",
        )

    _set_session_cookie(response, session_token)
    logger.info(f"New user registered: {user.email}")

    return AuthResponse(
        message="Compte créé avec succès",
        user=UserResponse.model_validate(user),
    )


# ── POST /api/auth/login ──────────────────────────────────────────────────────


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Se connecter",
)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """
    Authenticate with email and password and start a session.

    On success:
    - Sets the httpOnly session cookie
    - Clears the rate-limit counter for this email
    - Updates last_login_at timestamp
    - Returns the user profile

    On failure:
    - 429 if rate limited (5 failed attempts in 15 minutes)
    - 401 for any credential error (generic message, no user enumeration)

    Args:
        body: Login request with email and password.
        response: FastAPI response object (used to set cookie).
        db: Async database session.

    Returns:
        AuthResponse with confirmation message and user profile.
    """
    email = body.email.lower().strip()

    # Rate limit check BEFORE looking up the user
    if not auth_service.check_rate_limit(email):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives. Réessayez dans 15 minutes.",
        )

    # Look up user — intentionally generic error if not found
    user = await auth_service.get_user_by_email(db, email)
    if not user or not auth_service.verify_password(body.password, user.password_hash):
        # Record failed attempt for rate limiting
        auth_service.record_login_attempt(email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides",
        )

    # Credentials valid — clear rate limit counter, create session
    auth_service.clear_login_attempts(email)
    session = await auth_service.create_session(db, user.id)
    # Capture token before commit — same MissingGreenlet issue as register.
    session_token = session.token
    await auth_service.update_last_login(db, user)
    await db.commit()
    await db.refresh(user)

    _set_session_cookie(response, session_token)
    logger.info(f"User logged in: {user.email}")

    return AuthResponse(
        message="Connexion réussie",
        user=UserResponse.model_validate(user),
    )


# ── POST /api/auth/logout ─────────────────────────────────────────────────────


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Se déconnecter",
)
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> MessageResponse:
    """
    Destroy the current session and clear the cookie.

    Reads the session token directly from the cookie to delete the DB record,
    then clears the cookie. Requires an active session (authenticated) —
    401 is returned by get_current_user if the session is missing or expired.

    Args:
        response: FastAPI response object (used to clear cookie).
        db: Async database session.
        current_user: Injected authenticated user (validates the session exists).
        session_token: Raw cookie value read for DB deletion.

    Returns:
        MessageResponse confirming logout.
    """
    if session_token:
        await auth_service.delete_session(db, session_token)
        await db.commit()

    _clear_session_cookie(response)
    logger.info(f"User logged out: {current_user.email}")

    return MessageResponse(message="Déconnecté avec succès")


# ── POST /api/auth/reset-password ─────────────────────────────────────────────


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Demander une réinitialisation de mot de passe",
)
async def reset_password_request(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Request a password reset email.

    Always returns 200 regardless of whether the email is registered.
    This prevents user enumeration (an attacker cannot discover which
    emails are registered by probing this endpoint).

    If the email IS registered, a reset link is sent via SMTP.

    Args:
        body: Request body containing the email address.
        db: Async database session.

    Returns:
        MessageResponse — always 200, always the same message.
    """
    user = await auth_service.get_user_by_email(db, body.email)

    if user:
        reset_token = await auth_service.create_reset_token(db, user.id)
        # Capture token before commit — same MissingGreenlet reason as register.
        reset_token_str = reset_token.token
        await db.commit()
        # Send email asynchronously — errors are logged, not raised
        await send_reset_password_email(user.email, reset_token_str)
        logger.info(f"Password reset requested for: {user.email}")
    else:
        # Don't reveal that the email wasn't found — log for monitoring
        logger.debug(f"Password reset requested for unknown email: {body.email}")

    # Always same response regardless of whether user exists
    return MessageResponse(
        message="Si cette adresse email est associée à un compte, vous recevrez un email sous peu."
    )


# ── POST /api/auth/reset-password/confirm ─────────────────────────────────────


@router.post(
    "/reset-password/confirm",
    response_model=MessageResponse,
    summary="Confirmer la réinitialisation du mot de passe",
)
async def reset_password_confirm(
    body: ResetPasswordConfirmRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Complete the password reset using the token from the email.

    Validates the token (must be unused and within 1 hour of creation),
    updates the user's password, and marks the token consumed.

    Args:
        body: Request with the token and new password.
        db: Async database session.

    Returns:
        MessageResponse on success.

    Raises:
        HTTPException: 400 if the token is invalid or expired.
    """
    reset_token = await auth_service.get_valid_reset_token(db, body.token)
    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lien de réinitialisation invalide ou expiré",
        )

    await auth_service.consume_reset_token(db, reset_token, body.new_password)
    await db.commit()

    logger.info(f"Password reset completed for user_id: {reset_token.user_id}")

    return MessageResponse(message="Mot de passe mis à jour avec succès")


# ── GET /api/users/me ──────────────────────────────────────────────────────────
# Note: this lives here rather than a separate users router because it is tightly
# coupled to the auth session system. A dedicated users router will be added in
# Task 1.7 for salon CRUD and settings.

users_router = APIRouter(prefix="/users", tags=["users"])


@users_router.get(
    "/me",
    response_model=UserResponse,
    summary="Profil de l'utilisateur connecté",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """
    Return the current authenticated user's profile.

    Used by the frontend on page load to determine auth state and
    personalise the app shell (name, onboarding status, preferred tools).

    Args:
        current_user: Injected authenticated user from session cookie.

    Returns:
        UserResponse with all public user fields.
    """
    return UserResponse.model_validate(current_user)
