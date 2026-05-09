"""
Auth models — sessions and password reset tokens.

Sessions are the source of truth for "is this user logged in?"
A session token is stored as an httpOnly cookie on the client.
On every request, the token is looked up here to get the user.

Password reset tokens are one-time-use, expire after 1 hour,
and are sent by email as part of the reset flow.
"""

import secrets
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Session(Base):
    """
    Active user session.

    Created on login or register; destroyed on logout or expiry.
    The token is a cryptographically random string stored as an httpOnly cookie.
    Expiry is a sliding window — reset on each authenticated request.

    Attributes:
        id: UUID primary key
        user_id: FK to the user who owns this session
        token: 32-byte URL-safe random token (stored in cookie)
        expires_at: When this session expires (sliding, reset each request)
        created_at: When the session was first created
    """

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 32-byte URL-safe token — unique per session
    token: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="sessions")

    def __repr__(self) -> str:
        return f"<Session id={self.id} user_id={self.user_id} expires={self.expires_at}>"

    @staticmethod
    def generate_token() -> str:
        """
        Generate a cryptographically secure session token.

        Returns:
            A 43-character URL-safe base64 string derived from 32 random bytes.
        """
        return secrets.token_urlsafe(32)


class PasswordResetToken(Base):
    """
    One-time-use password reset token.

    Generated when a user requests a password reset. Emailed as a link.
    Must be used within 1 hour. Marked used_at after consumption so it
    cannot be replayed.

    Attributes:
        id: UUID primary key
        user_id: FK to the user requesting the reset
        token: UUID token embedded in the reset URL
        expires_at: 1 hour after creation
        used_at: Set when the token is consumed (prevents replay)
        created_at: When the token was generated
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # UUID token sent in the reset link URL
    token: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    # Null until the token has been used
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="reset_tokens")

    @property
    def is_valid(self) -> bool:
        """
        True if the token has not been used and has not expired.

        Returns:
            bool: True if usable, False if expired or already consumed.
        """
        from datetime import timezone
        now = datetime.now(timezone.utc)
        return self.used_at is None and self.expires_at > now

    def __repr__(self) -> str:
        return f"<PasswordResetToken id={self.id} user_id={self.user_id} valid={self.is_valid}>"

    @staticmethod
    def generate_token() -> str:
        """
        Generate a secure reset token.

        Returns:
            A URL-safe 32-byte random string.
        """
        return secrets.token_urlsafe(32)
