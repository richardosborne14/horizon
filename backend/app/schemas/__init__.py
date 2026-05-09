"""
Schemas package — re-export commonly used schemas for convenience.

Sprint 0: Only auth and user schemas remain.
"""
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    ResetPasswordRequest,
    ResetPasswordConfirmRequest,
    UserResponse,
    AuthResponse,
    MessageResponse,
)
from app.schemas.user import OnboardingRequest, OnboardingResponse

__all__ = [
    "RegisterRequest",
    "LoginRequest",
    "ResetPasswordRequest",
    "ResetPasswordConfirmRequest",
    "UserResponse",
    "AuthResponse",
    "MessageResponse",
    "OnboardingRequest",
    "OnboardingResponse",
]
