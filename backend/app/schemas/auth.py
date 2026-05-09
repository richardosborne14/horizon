"""
Pydantic schemas for authentication endpoints.

Request bodies, response models, and shared types used by the auth router.
All sensitive fields (password, token) are write-only (excluded from responses).
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Request schemas ────────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    """
    Body for POST /api/auth/register.

    Attributes:
        email: User's email address (must be valid format)
        password: Plain-text password — min 8 chars, never stored
        name: Display name (full name)
        phone: Optional mobile phone number
    """

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=20)

    @field_validator("password")
    @classmethod
    def password_not_trivial(cls, v: str) -> str:
        """Reject passwords that are all whitespace."""
        if v.strip() == "":
            raise ValueError("Le mot de passe ne peut pas être vide")
        return v


class LoginRequest(BaseModel):
    """
    Body for POST /api/auth/login.

    Attributes:
        email: User's email address
        password: Plain-text password to verify against stored hash
    """

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ResetPasswordRequest(BaseModel):
    """
    Body for POST /api/auth/reset-password.

    Attributes:
        email: Email address to send the reset link to
    """

    email: EmailStr


class ResetPasswordConfirmRequest(BaseModel):
    """
    Body for POST /api/auth/reset-password/confirm.

    Attributes:
        token: Reset token received by email
        new_password: New password to set (min 8 chars)
    """

    token: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_not_trivial(cls, v: str) -> str:
        """Reject passwords that are all whitespace."""
        if v.strip() == "":
            raise ValueError("Le mot de passe ne peut pas être vide")
        return v


# ── Response schemas ───────────────────────────────────────────────────────────


class UserResponse(BaseModel):
    """
    Public user data returned by the API.

    Never includes password_hash or session tokens.

    Attributes:
        id: User UUID
        email: User email
        name: Display name
        phone: Optional phone
        role: 'user' or 'admin'
        onboarding_completed: Whether onboarding questionnaire is done
        preferred_tools: List of tool IDs selected during onboarding
        created_at: Account creation timestamp
        last_login_at: Most recent login timestamp
    """

    model_config = {"from_attributes": True}

    id: uuid.UUID
    email: str
    name: str
    phone: str | None
    role: str
    onboarding_completed: bool
    preferred_tools: list
    # Added Task 2.5.3 — wizard completion flag used by frontend to skip wizard next visit
    has_completed_typical_month: bool
    created_at: datetime
    last_login_at: datetime | None
    # TASK-2.16.2: Grandfathering flag. NULL for standard users; set for legacy-price cohorts.
    # Frontend reads this to render "Forfait actuel" pill on the pricing page and to
    # suppress "Subscribe to CCPilot" CTAs for grandfathered customers.
    legacy_pricing_plan: Optional[str] = None
    # TASK-2.17.10: Bubble migration tracking fields.
    # NULL for native users; set by the import scripts.
    import_source: Optional[str] = None
    import_status: Optional[str] = None
    # First-login wizard step: 'pending' | 'welcome' | 'legal_form' | 'salon_config'
    # | 'team' | 'services' | 'savings_hook' | 'done' | 'deferred' | NULL
    import_completion_step: Optional[str] = None


class AuthResponse(BaseModel):
    """
    Response returned on successful register or login.

    The session cookie is set on the HTTP response separately —
    this body just confirms the action and returns the user profile.

    Attributes:
        message: Human-readable confirmation message
        user: The authenticated user's profile
    """

    message: str
    user: UserResponse


class MessageResponse(BaseModel):
    """
    Generic success message response.

    Used for logout, password reset request, and other
    endpoints that only need to confirm an action.

    Attributes:
        message: Human-readable message
    """

    message: str
