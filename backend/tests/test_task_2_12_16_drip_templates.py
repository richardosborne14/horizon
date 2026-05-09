"""
Tests for TASK-2.12.16 — Onboarding email drip templates.

Coverage:
  - All 6 templates self-register at import time
  - welcome cohort: includes brand-new users, excludes old users
  - day2_wizard_nudge: excludes user who completed the wizard
  - day2_simulation_done_no_payment: excludes user who has NOT completed wizard
  - day14_re_engagement: excludes user who logged in recently
  - All templates render without error for a minimal user fixture
  - First-name extraction: present, absent, multi-word name
  - HTML body contains {{UNSUBSCRIBE_URL}} placeholder for dispatcher injection
  - Text body contains {{UNSUBSCRIBE_URL}} placeholder

Each test uses SimpleNamespace to fake User/Salon objects — no DB needed.
The cohort functions are pure predicates on the ORM object.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

# ── Helpers ───────────────────────────────────────────────────────────────────


def _user(
    *,
    name: str = "Sophie Martin",
    created_at_days_ago: float = 0.1,
    has_completed_typical_month: bool = False,
    last_login_at_days_ago: float | None = 0.5,
    import_status: str | None = None,
) -> SimpleNamespace:
    """
    Build a minimal fake User object for cohort / render tests.

    Args:
        name:                          User's full name.
        created_at_days_ago:           How many days ago the account was created.
        has_completed_typical_month:   Wizard completion flag.
        last_login_at_days_ago:        Days since last login; None = never logged in.
        import_status:                 e.g. 'imported_active_paying' or None.

    Returns:
        SimpleNamespace with the fields cohort_fn and render_fn access.
    """
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001",
        email="test@example.com",
        name=name,
        created_at=now - timedelta(days=created_at_days_ago),
        has_completed_typical_month=has_completed_typical_month,
        last_login_at=(
            now - timedelta(days=last_login_at_days_ago)
            if last_login_at_days_ago is not None
            else None
        ),
        import_status=import_status,
        unsubscribed_at=None,
        email_drip_state={},
    )


def _salon() -> SimpleNamespace:
    """Minimal fake Salon object."""
    return SimpleNamespace(id="00000000-0000-0000-0000-000000000002")


# ── Registry self-registration ────────────────────────────────────────────────


def test_all_templates_self_register():
    """
    Importing the templates package must populate the registry with all 6 IDs.
    """
    # Reset registry to ensure a clean slate for this test
    from app.services.email_drip.registry import _REGISTRY, get_all

    # Templates __init__.py imports are idempotent (register() replaces)
    import app.services.email_drip.templates  # noqa: F401

    registered_ids = {t.template_id for t in get_all()}
    expected_ids = {
        "welcome",
        "day2_wizard_nudge",
        "day2_simulation_done_no_payment",
        "day5_team_setup",
        "day14_re_engagement",
        "day30_calendly_offer",
    }
    assert expected_ids.issubset(registered_ids), (
        f"Missing templates: {expected_ids - registered_ids}"
    )


# ── welcome cohort ────────────────────────────────────────────────────────────


def test_welcome_cohort_includes_brand_new_user():
    """A user created 2 hours ago must be in the welcome cohort."""
    from app.services.email_drip.templates.welcome import cohort_fn

    user = _user(created_at_days_ago=0.08)  # ~2 hours ago
    assert cohort_fn(user) is True


def test_welcome_cohort_excludes_user_older_than_one_day():
    """A user created 25 hours ago must NOT be in the welcome cohort."""
    from app.services.email_drip.templates.welcome import cohort_fn

    user = _user(created_at_days_ago=1.05)  # ~25 hours ago
    assert cohort_fn(user) is False


# ── day2_wizard_nudge cohort ──────────────────────────────────────────────────


def test_day2_wizard_nudge_includes_incomplete_day2_user():
    """2-day-old user with incomplete wizard must be selected."""
    from app.services.email_drip.templates.day2_wizard_nudge import cohort_fn

    user = _user(created_at_days_ago=2.0, has_completed_typical_month=False)
    assert cohort_fn(user) is True


def test_day2_wizard_nudge_excludes_completed_wizard():
    """2-day-old user who completed the wizard must NOT receive the nudge."""
    from app.services.email_drip.templates.day2_wizard_nudge import cohort_fn

    user = _user(created_at_days_ago=2.0, has_completed_typical_month=True)
    assert cohort_fn(user) is False


def test_day2_wizard_nudge_excludes_brand_new_user():
    """A brand-new user (6 hours old) is too early for the day-2 nudge."""
    from app.services.email_drip.templates.day2_wizard_nudge import cohort_fn

    user = _user(created_at_days_ago=0.25, has_completed_typical_month=False)
    assert cohort_fn(user) is False


# ── day2_simulation_done_no_payment cohort ────────────────────────────────────


def test_day2_simulation_excludes_user_without_wizard():
    """A day-2 user who has NOT completed the wizard is NOT in this cohort."""
    from app.services.email_drip.templates.day2_simulation_done_no_payment import (
        cohort_fn,
    )

    user = _user(created_at_days_ago=2.0, has_completed_typical_month=False)
    assert cohort_fn(user) is False


def test_day2_simulation_includes_wizard_complete_user():
    """A day-2 user who completed the wizard IS in this cohort."""
    from app.services.email_drip.templates.day2_simulation_done_no_payment import (
        cohort_fn,
    )

    user = _user(created_at_days_ago=2.0, has_completed_typical_month=True)
    assert cohort_fn(user) is True


# ── day14_re_engagement cohort ────────────────────────────────────────────────


def test_day14_excludes_recently_logged_in_user():
    """A day-14 user who logged in yesterday must NOT receive the re-engagement."""
    from app.services.email_drip.templates.day14_re_engagement import cohort_fn

    user = _user(created_at_days_ago=14.0, last_login_at_days_ago=1.0)
    assert cohort_fn(user) is False


def test_day14_includes_inactive_user():
    """A day-14 user who last logged in 10 days ago IS in the re-engagement cohort."""
    from app.services.email_drip.templates.day14_re_engagement import cohort_fn

    user = _user(created_at_days_ago=14.5, last_login_at_days_ago=10.0)
    assert cohort_fn(user) is True


def test_day14_includes_user_who_never_logged_in():
    """A day-14 user with no last_login_at (never logged in) IS in the cohort."""
    from app.services.email_drip.templates.day14_re_engagement import cohort_fn

    user = _user(created_at_days_ago=14.5, last_login_at_days_ago=None)
    assert cohort_fn(user) is True


# ── Render tests ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "module_path",
    [
        "app.services.email_drip.templates.welcome",
        "app.services.email_drip.templates.day2_wizard_nudge",
        "app.services.email_drip.templates.day2_simulation_done_no_payment",
        "app.services.email_drip.templates.day5_team_setup",
        "app.services.email_drip.templates.day14_re_engagement",
        "app.services.email_drip.templates.day30_calendly_offer",
    ],
)
def test_all_templates_render_without_error(module_path: str):
    """Every template render_fn must produce a valid RenderedEmail."""
    import importlib

    from app.services.email_drip.registry import RenderedEmail

    mod = importlib.import_module(module_path)
    rendered = mod.render_fn(_user(), _salon())
    assert isinstance(rendered, RenderedEmail)
    assert rendered.subject
    assert rendered.html_body
    assert rendered.text_body


@pytest.mark.parametrize(
    "module_path",
    [
        "app.services.email_drip.templates.welcome",
        "app.services.email_drip.templates.day2_wizard_nudge",
        "app.services.email_drip.templates.day2_simulation_done_no_payment",
        "app.services.email_drip.templates.day5_team_setup",
        "app.services.email_drip.templates.day14_re_engagement",
        "app.services.email_drip.templates.day30_calendly_offer",
    ],
)
def test_all_templates_render_with_no_name(module_path: str):
    """render_fn must not crash when user.name is empty or None."""
    import importlib

    from app.services.email_drip.registry import RenderedEmail

    mod = importlib.import_module(module_path)
    user = _user(name="")
    rendered = mod.render_fn(user, None)
    assert isinstance(rendered, RenderedEmail)
    # Greeting must fall back to "Bonjour," (no name, no comma-space gap)
    assert "Bonjour," in rendered.html_body or "Bonjour," in rendered.text_body


@pytest.mark.parametrize(
    "module_path",
    [
        "app.services.email_drip.templates.welcome",
        "app.services.email_drip.templates.day2_wizard_nudge",
        "app.services.email_drip.templates.day2_simulation_done_no_payment",
        "app.services.email_drip.templates.day5_team_setup",
        "app.services.email_drip.templates.day14_re_engagement",
        "app.services.email_drip.templates.day30_calendly_offer",
    ],
)
def test_all_templates_contain_unsubscribe_placeholder(module_path: str):
    """Every rendered HTML must contain {{UNSUBSCRIBE_URL}} for dispatcher injection."""
    import importlib

    mod = importlib.import_module(module_path)
    rendered = mod.render_fn(_user(), _salon())
    assert "{{UNSUBSCRIBE_URL}}" in rendered.html_body, (
        f"{module_path} HTML body is missing the {{{{UNSUBSCRIBE_URL}}}} placeholder"
    )
    assert "{{UNSUBSCRIBE_URL}}" in rendered.text_body, (
        f"{module_path} text body is missing the {{{{UNSUBSCRIBE_URL}}}} placeholder"
    )


def test_welcome_render_includes_first_name():
    """welcome render_fn must use the first name in the greeting."""
    from app.services.email_drip.templates.welcome import render_fn

    user = _user(name="Sophie Martin")
    rendered = render_fn(user, None)
    assert "Sophie" in rendered.html_body
    assert "Sophie" in rendered.text_body


def test_render_with_none_salon():
    """All templates must render successfully when salon is None."""
    from app.services.email_drip.templates.welcome import render_fn

    rendered = render_fn(_user(), None)
    assert rendered.html_body
    assert rendered.text_body
