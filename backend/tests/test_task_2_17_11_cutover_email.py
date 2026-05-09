"""
Tests for TASK-2.17.11 — Cutover welcome email (two templates).

Tests:
  test_template_a_subject_and_copy      — paying user gets template A with correct copy
  test_template_b_unpaid_copy           — unpaid user gets template B with trial copy
  test_template_b_lapsed_copy           — lapsed user gets template B with lapsed copy
  test_template_b_dormant_copy          — dormant user gets template B with dormant copy
  test_reset_token_expiry_48h           — migration token expires in 48 h, not 1 h
  test_reset_url_has_migration_param    — reset URL contains ?migration=1
  test_idempotent_skip_already_sent     — second send is skipped; already_sent=True returned
  test_force_flag_overrides_idempotency — force=True re-sends even if already_sent_at is set
  test_non_imported_user_rejected       — non-imported users return error, no send
  test_missing_user_returns_error_dict  — unknown UUID returns error, no exception
  test_send_batch_dry_run               — dry_run returns counts without sending
  test_send_batch_status_filter         — status_filter limits cohort queried
  test_send_batch_stamps_sent_at        — real send stamps welcome_email_sent_at on user
  test_coco_disclaimer_in_footer        — both templates include CoCo legal disclaimer

All tests mock send_email so no SMTP connection is needed.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select, text

from app.core.database import AsyncSessionLocal
from app.models.auth import PasswordResetToken
from app.models.user import User
from app.services.migration_email import (
    _render_template_a,
    _render_template_b,
    send_batch,
    send_welcome_email_for_user,
)


# ── Fixture helpers ────────────────────────────────────────────────────────────

async def _make_imported_user(
    import_status: str,
    *,
    welcome_email_sent_at: datetime | None = None,
) -> uuid.UUID:
    """
    Insert a minimal imported user row for testing.

    Args:
        import_status:          The cohort status for the user.
        welcome_email_sent_at:  Pre-set sent timestamp (for idempotency tests).

    Returns:
        The new user's UUID.
    """
    uid = uuid.uuid4()
    suffix = uid.hex[:8]
    async with AsyncSessionLocal() as db:
        await db.execute(
            text(
                """
                INSERT INTO users
                  (id, email, password_hash, name, role, created_at,
                   import_status, welcome_email_sent_at)
                VALUES
                  (:id, :email, 'placeholder', :name, 'user', NOW(),
                   :status, :sent_at)
                """
            ),
            {
                "id": uid,
                "email": f"cutover-test-{suffix}@example.com",
                "name": f"Cutover Tester {suffix}",
                "status": import_status,
                "sent_at": welcome_email_sent_at,
            },
        )
        await db.commit()
    return uid


async def _cleanup_user(user_id: uuid.UUID) -> None:
    """Remove the test user and any associated reset tokens."""
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("DELETE FROM password_reset_tokens WHERE user_id = :id"),
            {"id": user_id},
        )
        await db.execute(
            text("DELETE FROM users WHERE id = :id"),
            {"id": user_id},
        )
        await db.commit()


# ── Template rendering tests (pure unit, no DB) ─────────────────────────────

@pytest.mark.asyncio
async def test_template_a_subject_and_copy():
    """
    Template A must contain subscription-continuation copy and a CTA for
    choosing a password — not trial language.
    """
    subject, html, text_body = _render_template_a(
        user_name="Sophie Martin",
        reset_url="https://app.comcoi.fr/reset-password?token=abc123&migration=1",
    )

    assert "mot de passe" in subject.lower()
    assert "Sophie Martin" in html
    assert "abonnement continue" in html
    assert "tarif est préservé" in html
    assert "Choisir mon mot de passe" in html
    # Must NOT use trial language
    assert "14 jours" not in html
    # Plain text fallback
    assert "abonnement continue au même tarif" in text_body
    assert "abc123" in text_body


@pytest.mark.asyncio
async def test_template_b_unpaid_copy():
    """Template B for imported_active_unpaid includes data-import and trial messaging."""
    subject, html, text_body = _render_template_b(
        user_name="Marie Dupont",
        reset_url="https://app.comcoi.fr/reset-password?token=tok456&migration=1",
        import_status="imported_active_unpaid",
    )

    assert "14 jours" in subject
    assert "Marie Dupont" in html
    assert "données Bubble" in html
    assert "14 jours offerts" in html
    # No subscription-preservation language
    assert "tarif est préservé" not in html
    assert "tok456" in text_body


@pytest.mark.asyncio
async def test_template_b_lapsed_copy():
    """Template B for imported_lapsed mentions read-only access and reactivation."""
    _, html, text_body = _render_template_b(
        user_name="Isabelle Blanc",
        reset_url="https://example.com/reset?token=lapsed",
        import_status="imported_lapsed",
    )

    assert "données restent accessibles en lecture" in html
    assert "réactivez votre abonnement" in html
    assert "14 jours offerts" in html


@pytest.mark.asyncio
async def test_template_b_dormant_copy():
    """Template B for imported_dormant introduces the platform without Bubble data mention."""
    _, html, text_body = _render_template_b(
        user_name="",
        reset_url="https://example.com/reset?token=dormant",
        import_status="imported_dormant",
    )

    assert "Communauté Coiffure" in html
    assert "coiffeurs indépendants" in html
    # Dormant users don't have data imported, so no Bubble data mention
    assert "données Bubble" not in html
    # Fallback greeting used when name is empty
    assert "coiffeuse" in html.lower() or "Chère" in html


@pytest.mark.asyncio
async def test_coco_disclaimer_in_footer():
    """Both templates must include the CoCo no-legal-advice disclaimer."""
    _, html_a, _ = _render_template_a("Test", "https://example.com/r")
    _, html_b, _ = _render_template_b("Test", "https://example.com/r", "imported_lapsed")

    for html in (html_a, html_b):
        assert "CoCo ne donne pas de conseils juridiques" in html
        assert "professionnel" in html


# ── Service-level integration tests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_reset_token_expiry_48h():
    """
    Migration reset token must expire in 48 h, not the standard 1 h.

    We call send_welcome_email_for_user with a mocked send_email and then
    verify the token's expires_at is ~48 h from now.
    """
    user_id = await _make_imported_user("imported_active_paying")
    try:
        with patch(
            "app.services.migration_email.send_email",
            new_callable=AsyncMock,
        ) as mock_send:
            async with AsyncSessionLocal() as db:
                result = await send_welcome_email_for_user(db, user_id)
                await db.commit()

        assert result["sent"] is True

        # Inspect the reset token
        async with AsyncSessionLocal() as db:
            token_result = await db.execute(
                select(PasswordResetToken).where(
                    PasswordResetToken.user_id == user_id
                )
            )
            token = token_result.scalar_one_or_none()

        assert token is not None
        now = datetime.now(UTC)
        delta = token.expires_at - now
        # Should be ~48 h ± 5 min
        assert timedelta(hours=47, minutes=55) < delta < timedelta(hours=48, minutes=5)
    finally:
        await _cleanup_user(user_id)


@pytest.mark.asyncio
async def test_reset_url_has_migration_param():
    """Reset URL passed to send_email must include ?migration=1."""
    user_id = await _make_imported_user("imported_active_unpaid")
    try:
        captured_html: list[str] = []

        async def _capture_send(to_email, subject, body_html, body_text, **_):
            captured_html.append(body_html)

        with patch(
            "app.services.migration_email.send_email",
            side_effect=_capture_send,
        ):
            async with AsyncSessionLocal() as db:
                result = await send_welcome_email_for_user(db, user_id)
                await db.commit()

        assert result["sent"] is True
        assert len(captured_html) == 1
        assert "migration=1" in captured_html[0]
        assert "reset-password" in captured_html[0]
    finally:
        await _cleanup_user(user_id)


@pytest.mark.asyncio
async def test_idempotent_skip_already_sent():
    """
    If welcome_email_sent_at is already set, the function returns
    already_sent=True and does NOT call send_email.
    """
    user_id = await _make_imported_user(
        "imported_active_paying",
        welcome_email_sent_at=datetime(2026, 5, 1, 10, 0, 0, tzinfo=UTC),
    )
    try:
        with patch(
            "app.services.migration_email.send_email",
            new_callable=AsyncMock,
        ) as mock_send:
            async with AsyncSessionLocal() as db:
                result = await send_welcome_email_for_user(db, user_id)

        assert result["already_sent"] is True
        assert result["sent"] is False
        mock_send.assert_not_called()
    finally:
        await _cleanup_user(user_id)


@pytest.mark.asyncio
async def test_force_flag_overrides_idempotency():
    """
    force=True causes a re-send even if welcome_email_sent_at is already set.
    """
    user_id = await _make_imported_user(
        "imported_lapsed",
        welcome_email_sent_at=datetime(2026, 5, 1, 10, 0, 0, tzinfo=UTC),
    )
    try:
        with patch(
            "app.services.migration_email.send_email",
            new_callable=AsyncMock,
        ) as mock_send:
            async with AsyncSessionLocal() as db:
                result = await send_welcome_email_for_user(db, user_id, force=True)
                await db.commit()

        assert result["sent"] is True
        mock_send.assert_called_once()
        assert result["template"] == "B"
    finally:
        await _cleanup_user(user_id)


@pytest.mark.asyncio
async def test_non_imported_user_rejected():
    """
    A native (non-imported) user should return an error dict without calling send_email.
    """
    # Create a native user (import_status = None)
    uid = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        await db.execute(
            text(
                "INSERT INTO users (id, email, password_hash, name, role, created_at) "
                "VALUES (:id, :email, 'ph', 'Native User', 'user', NOW())"
            ),
            {"id": uid, "email": f"native-cutover-{uid.hex[:8]}@example.com"},
        )
        await db.commit()

    try:
        with patch(
            "app.services.migration_email.send_email",
            new_callable=AsyncMock,
        ) as mock_send:
            async with AsyncSessionLocal() as db:
                result = await send_welcome_email_for_user(db, uid)

        assert result["sent"] is False
        assert result["error"] == "not_imported_user"
        mock_send.assert_not_called()
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(text("DELETE FROM users WHERE id=:id"), {"id": uid})
            await db.commit()


@pytest.mark.asyncio
async def test_missing_user_returns_error_dict():
    """Unknown UUID must return an error dict, not raise an exception."""
    fake_id = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        result = await send_welcome_email_for_user(db, fake_id)

    assert result["sent"] is False
    assert result["error"] == "user_not_found"


@pytest.mark.asyncio
async def test_send_batch_dry_run():
    """
    dry_run=True counts emails that would be sent but calls send_email 0 times.
    Creates two unsent imported users; batch should report sent=2 without sending.
    """
    u1 = await _make_imported_user("imported_active_paying")
    u2 = await _make_imported_user("imported_dormant")
    try:
        with patch(
            "app.services.migration_email.send_email",
            new_callable=AsyncMock,
        ) as mock_send:
            async with AsyncSessionLocal() as db:
                result = await send_batch(db, batch_size=10, dry_run=True)

        assert result["dry_run"] is True
        # Both (at minimum) the two users we created should appear in dry_run count
        assert result["sent"] >= 2
        mock_send.assert_not_called()
    finally:
        await _cleanup_user(u1)
        await _cleanup_user(u2)


@pytest.mark.asyncio
async def test_send_batch_status_filter():
    """
    status_filter limits the batch to users of that cohort only.
    Create one paying + one dormant; filter to 'imported_dormant' — only dormant
    should appear in the send_batch result.
    """
    u_paying = await _make_imported_user("imported_active_paying")
    u_dormant = await _make_imported_user("imported_dormant")

    sent_emails: list[str] = []

    async def _capture(to_email, **_kwargs):
        sent_emails.append(to_email)

    try:
        with patch("app.services.migration_email.send_email", side_effect=_capture):
            async with AsyncSessionLocal() as db:
                result = await send_batch(
                    db,
                    status_filter="imported_dormant",
                    batch_size=100,
                    dry_run=False,
                )
                await db.commit()

        # Only dormant emails should have been sent
        async with AsyncSessionLocal() as db:
            dormant_row = await db.execute(
                select(User).where(User.id == u_dormant)
            )
            dormant_user = dormant_row.scalar_one()
            paying_row = await db.execute(
                select(User).where(User.id == u_paying)
            )
            paying_user = paying_row.scalar_one()

        # Dormant user's email must be in the sent list
        assert dormant_user.email in sent_emails
        # Paying user's email must NOT be in the sent list
        assert paying_user.email not in sent_emails
    finally:
        await _cleanup_user(u_paying)
        await _cleanup_user(u_dormant)


@pytest.mark.asyncio
async def test_send_batch_stamps_sent_at():
    """
    After a real (non-dry-run) batch send, welcome_email_sent_at is set on the user.
    """
    user_id = await _make_imported_user("imported_active_unpaid")
    try:
        with patch(
            "app.services.migration_email.send_email",
            new_callable=AsyncMock,
        ):
            async with AsyncSessionLocal() as db:
                result = await send_batch(
                    db,
                    status_filter="imported_active_unpaid",
                    batch_size=5,
                    dry_run=False,
                )
                await db.commit()

        assert result["sent"] >= 1

        # Verify the DB stamp
        async with AsyncSessionLocal() as db:
            row = await db.execute(select(User).where(User.id == user_id))
            user = row.scalar_one()
        assert user.welcome_email_sent_at is not None
    finally:
        await _cleanup_user(user_id)
