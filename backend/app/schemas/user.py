"""
User-related Pydantic schemas — onboarding request/response.

These schemas handle the onboarding questionnaire submission endpoint.
Auth-related user schemas (UserResponse, AuthResponse, etc.) live in schemas/auth.py.
"""

from typing import Literal

from pydantic import BaseModel, Field

# ── TASK-2.17.10: First-login wizard step order ───────────────────────────────
# Ordered list of valid wizard steps. Used for forward-transition validation.
# 'deferred' is a special lateral transition allowed from any step.
WIZARD_STEP_ORDER: list[str] = [
    "pending",
    "welcome",
    "legal_form",
    "salon_config",
    "team",
    "services",
    "savings_hook",
    "done",
]


class OnboardingRequest(BaseModel):
    """
    Payload for completing the onboarding questionnaire.

    Submitted once when the user finishes all 4 steps.
    The service layer derives preferred_tools from business_goals and
    creates the salon + coco_user_profile in a single transaction.

    Args:
        salon_name: Name of the first salon (from step 1).
        business_type: Legal structure ID from business-types.json (from step 1).
        nb_employees: Number of employees excluding the owner (from step 2).
        business_goals: List of goal IDs selected in step 3.
                        Valid values: rentabilite, prix, compta, fiches_salaire, conseils.
        experience_level: Self-assessed experience level from step 4.
    """

    salon_name: str = Field(..., min_length=1, max_length=255, description="Nom du salon")
    business_type: str = Field(..., min_length=1, max_length=50, description="Type de structure juridique")
    nb_employees: int = Field(default=0, ge=0, le=999, description="Nombre d'employés hors dirigeant")
    business_goals: list[str] = Field(
        ...,
        min_length=1,
        description="Objectifs sélectionnés (au moins un requis)",
    )
    experience_level: Literal["debutant", "intermediaire", "confirme"] = Field(
        ...,
        description="Niveau d'expérience avec les outils de gestion",
    )
    # Fiscal year start month — only meaningful for non-AE salons.
    # AE users are legally locked to Jan (1) per CGI art. 151-0;
    # the service enforces this regardless of what is submitted.
    # Optional so existing clients that don't send this field still work.
    fiscal_year_start: int = Field(
        default=1,
        ge=1,
        le=12,
        description="Mois de début d'exercice (1=janvier). Ignoré pour auto-micro (toujours 1).",
    )


class OnboardingResponse(BaseModel):
    """
    Response returned after successful onboarding completion.

    Args:
        message: Confirmation message for the frontend.
        preferred_tools: Derived tool IDs now saved on the user profile.
    """

    message: str
    preferred_tools: list[str]


# ── TASK-2.17.10: Import-step wizard ──────────────────────────────────────────


class ImportStepRequest(BaseModel):
    """
    Body for PATCH /api/users/me/import-step.

    Advances the migrated user's first-login wizard to the given step.
    'deferred' is always valid (skip wizard, show progress bar).
    Forward-only transitions are enforced against WIZARD_STEP_ORDER.

    Args:
        step: The step to advance to.
    """

    step: str = Field(
        ...,
        description=(
            "Target wizard step. "
            "Valid values: pending, welcome, legal_form, salon_config, "
            "team, services, savings_hook, done, deferred."
        ),
    )


class ImportStepResponse(BaseModel):
    """
    Response from PATCH /api/users/me/import-step.

    Args:
        import_completion_step: The step that was just saved.
        message: Confirmation string for logging / debugging.
    """

    import_completion_step: str
    message: str
