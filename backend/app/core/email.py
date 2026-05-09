"""
Email sending utility using aiosmtplib.

Wraps SMTP sending for auth flows (password reset) and transactional emails
(payslip notifications, dossier creation). All email configuration comes from
settings (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD).

In development (SMTP_HOST=localhost, port 1025) this works with Mailhog or
any local SMTP sink. In production, configure a real SMTP relay.
"""

import logging

import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_email(
    to_email: str,
    subject: str,
    body_html: str,
    body_text: str,
    cc: list[str] | None = None,
    reply_to: str | None = None,
) -> None:
    """
    Send an email via SMTP.

    Sends a multipart/alternative message with both HTML and plain-text
    fallback. Logs errors but does not raise — the caller should not fail
    a user-facing request because of a transient email error.

    Args:
        to_email:  Recipient email address.
        subject:   Email subject line.
        body_html: HTML version of the email body.
        body_text: Plain-text fallback version.
        cc:        Optional list of CC email addresses.
        reply_to:  Optional Reply-To address (used for payslip emails so
                   Marie's replies go to Eric, not to our system).
    """
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = settings.smtp_from
    message["To"] = to_email
    if cc:
        message["Cc"] = ", ".join(cc)
    if reply_to:
        message["Reply-To"] = reply_to

    # Plain text first, HTML second (clients prefer the last part)
    message.attach(MIMEText(body_text, "plain", "utf-8"))
    message.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user if settings.smtp_user else None,
            password=settings.smtp_password if settings.smtp_password else None,
            # Use STARTTLS in production; plain in dev (MailHog / local sink)
            use_tls=False,
            start_tls=settings.is_production,
        )
        logger.info(f"Email sent to {to_email}: {subject!r}")
    except Exception as exc:
        # Log but don't crash — email failure should not break user flows.
        # The reset token is still valid; the user can request again.
        logger.error(f"Failed to send email to {to_email}: {exc}", exc_info=True)
        raise  # Re-raise so callers that handle retries can act


async def send_reset_password_email(to_email: str, reset_token: str) -> None:
    """
    Send a password reset email containing a one-time link.

    The link expires in 1 hour. The token is embedded as a query parameter
    so the SvelteKit frontend can extract it on the /reset-password page.

    Args:
        to_email: The user's email address.
        reset_token: The PasswordResetToken.token string.
    """
    reset_url = f"{settings.frontend_url}/reset-password?token={reset_token}"

    subject = "Réinitialisation de votre mot de passe — Communauté Coiffure"

    body_text = f"""Bonjour,

Vous avez demandé une réinitialisation de votre mot de passe.

Cliquez sur ce lien pour choisir un nouveau mot de passe (valable 1 heure) :
{reset_url}

Si vous n'avez pas fait cette demande, ignorez cet email — votre mot de passe reste inchangé.

Cordialement,
L'équipe Communauté Coiffure
"""

    body_html = f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
  <h2 style="color: #1A1A2E;">Réinitialisation de votre mot de passe</h2>
  <p>Bonjour,</p>
  <p>Vous avez demandé une réinitialisation de votre mot de passe.</p>
  <p>
    <a href="{reset_url}"
       style="display: inline-block; padding: 12px 24px; background-color: #C8A951;
              color: #1A1A2E; text-decoration: none; border-radius: 4px; font-weight: bold;">
      Réinitialiser mon mot de passe
    </a>
  </p>
  <p style="color: #666; font-size: 14px;">
    Ce lien est valable <strong>1 heure</strong>. Si vous n'avez pas fait cette demande,
    ignorez cet email — votre mot de passe reste inchangé.
  </p>
  <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
  <p style="color: #999; font-size: 12px;">
    Communauté Coiffure — Votre assistant financier pour coiffeurs indépendants
  </p>
</body>
</html>"""

    # Password reset uses simple send_email without cc/reply_to
    await send_email(
        to_email=to_email,
        subject=subject,
        body_html=body_html,
        body_text=body_text,
    )
