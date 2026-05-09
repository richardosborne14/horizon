"""
FastAPI dependency injection functions for Horizon.

These are used with FastAPI's Depends() system to inject the current
authenticated user into route handlers. Import and use like:

    @router.get("/protected")
    async def my_route(user: User = Depends(get_current_user)):
        ...

    @router.get("/admin-only")
    async def admin_route(user: User = Depends(get_admin_user)):
        ...
"""

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.services import auth as auth_service


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> User:
    """
    FastAPI dependency: extract and validate the session cookie.

    Looks up the session token from the httpOnly cookie, verifies it is
    valid (exists and not expired), refreshes the sliding expiry window,
    and returns the associated User.

    Raises HTTPException 401 if:
    - Cookie is missing
    - Token not found in database
    - Session has expired

    Args:
        db: Injected async database session.
        session_token: The session cookie value (read automatically by FastAPI).

    Returns:
        The authenticated User model instance.

    Raises:
        HTTPException: 401 if the session is missing or invalid.
    """
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non authentifié",
        )

    session = await auth_service.get_session_by_token(db, session_token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expirée ou invalide",
        )

    user = await auth_service.get_user_by_id(db, session.user_id)
    if not user:
        # Session exists but user was deleted — treat as unauthenticated
        await db.delete(session)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur introuvable",
        )

    # Sliding window: extend the session expiry on each authenticated request
    await auth_service.refresh_session(db, session)
    await db.commit()

    return user


async def get_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    FastAPI dependency: require an authenticated admin user.

    Builds on get_current_user — if the session is valid but the user
    is not an admin, raises 403 Forbidden.

    Args:
        current_user: Injected from get_current_user.

    Returns:
        The authenticated admin User model instance.

    Raises:
        HTTPException: 403 if the user's role is not 'admin'.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs",
        )
    return current_user