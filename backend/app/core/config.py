"""
Application configuration loaded from environment variables.

Uses pydantic-settings to validate and type all config values.
All settings come from the environment (or .env file in development).
Never access os.environ directly — use `settings` from this module.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings pulled from environment variables.

    pydantic-settings automatically reads from:
    1. Environment variables (case-insensitive)
    2. .env file (if present, loaded via python-dotenv)
    """

    model_config = SettingsConfigDict(
        env_file="../.env",  # Root-level .env (relative to backend/)
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore unknown env vars
    )

    # ── Database ──────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://comcoi:comcoi_dev_password@localhost:5432/comcoi"

    # ── Security ──────────────────────────────────────────────────────────
    secret_key: str = "dev-secret-key-CHANGE-IN-PRODUCTION"

    # Session cookie settings
    session_cookie_name: str = "session_token"
    session_expire_days: int = 30  # Sliding window: reset expiry on each request

    # ── App ───────────────────────────────────────────────────────────────
    app_env: str = "development"
    frontend_url: str = "http://localhost:5173"

    @property
    def is_production(self) -> bool:
        """True when running in production environment."""
        return self.app_env == "production"

    @property
    def cookie_secure(self) -> bool:
        """Secure flag on cookies: True in production (HTTPS only)."""
        return self.is_production

    # ── AI: Anthropic ─────────────────────────────────────────────────────
    anthropic_api_key: str = ""

    # Model IDs (verify with Anthropic docs if these change)
    coco_model_haiku: str = "claude-haiku-4-5-20251001"  # Fast, affordable — CoCo standard
    coco_model_sonnet: str = "claude-sonnet-4-5"  # Deep analysis

    # ── AI: DeepInfra (embeddings for RAG) ───────────────────────────────
    deepinfra_api_key: str = ""
    # Model for French text embeddings — BAAI/bge-m3 is multilingual, 1024-dim
    deepinfra_embedding_model: str = "BAAI/bge-m3"
    deepinfra_embedding_dim: int = 1024

    # ── AI: Perplexity (web search for CoCo) ─────────────────────────────
    perplexity_api_key: str = ""
    # sonar = fast, cheap, real-time web search
    perplexity_model: str = "sonar"

    # ── Bubble (legacy data import) ───────────────────────────────────────
    bubble_api_key: str = ""
    bubble_api_base: str = "https://espacepro.communaute-coiffure.com/api/1.1/obj"

    # ── Payments: Stripe ──────────────────────────────────────────────────
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_publishable_key: str = ""

    # ── Stripe subscription Price IDs (2026-05 pricing restructure) ───────
    # Populated by running backend/scripts/stripe_seed_2026_05.py.
    # Each environment (dev / staging / prod) has its own Stripe objects.
    # Leave empty in dev until the seed script has been run.
    stripe_price_ccpilot_monthly: str = ""
    stripe_price_pack_bic_ccpilot_monthly: str = ""
    stripe_price_pack_bic_plus_ccpilot_monthly: str = ""
    # Only set once Eric confirms BIC+ standalone price (see SPRINT-2.16-PLAN.md).
    stripe_price_pack_bic_plus_monthly_v2: str = ""

    # ── Noly Compta ───────────────────────────────────────────────────────
    # API key for Noly white-label officer API (TASK-3.11).
    # Format: nly_xxxxxxxx...  — do not share or commit.
    # Set in .env: NOLY_API_KEY=nly_xxx...
    noly_api_key: str = ""
    # Legacy SSO URL (kept for reference; replaced by magic-link API in TASK-3.11)
    noly_sso_url: str = "https://app.noly-compta.fr/sso"

    # ── Email ─────────────────────────────────────────────────────────────
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = "dev@localhost"
    smtp_password: str = "dev"
    smtp_from: str = "Communauté Coiffure <noreply@communaute-coiffure.fr>"

    # ── Payslip / Fiches de salaire ───────────────────────────────────────
    # Notification email: CC'd on outbound payslip emails; reply-to set here so
    # Marie's replies go back to Eric, not to our system.
    payslip_notification_email: str = "contact@communaute-coiffure.com"
    # Processor email: TO address for outbound payslip emails (Marie).
    # Set this to Marie's actual address at deploy time.
    # WHY marie@actipaie.fr: Marie is the payslip processor (Actipaie). This is the
    # TO address for all variables + dossier + contrat emails. Override via env var
    # PAYSLIP_PROCESSOR_EMAIL in production if the address changes.
    payslip_processor_email: str = "marie@actipaie.fr"
    # Unit price in cents (TTC). Must equal 28.80 × 100 = 2880.
    # Verified at startup by the assertion in lifespan() in main.py.
    payslip_unit_price_cents: int = 2880  # €28.80 TTC

    # ── IMAP (Task 2.13.3 — inbound email poller) ─────────────────────────────
    # Set these when configuring the inbound email polling in 2.13.3.
    # Leave empty in dev — the poller will be a no-op when imap_host is unset.
    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""
    # PAYSLIP_INBOUND_ENABLED: set to true to activate the 5-minute IMAP poller.
    # When false (default): APScheduler is not started; safe for dev/CI.
    payslip_inbound_enabled: bool = False

    # ── Object Storage / S3 (Task 2.13.3 — PDF uploads) ──────────────────────
    # Hetzner Object Storage is S3-compatible. Set endpoint_url to the Hetzner
    # S3 endpoint for your project region (e.g. https://fsn1.your-objectstorage.com).
    # Leave empty in dev — PDF upload will be a stub when s3_endpoint_url is unset.
    s3_endpoint_url: str = ""
    s3_bucket_name: str = "comcoi-payslips"
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # ── Contact / Booking form (Task 4.6) ─────────────────────────────────
    # Eric's email address for booking notifications from the landing page
    contact_email: str = "eric@communaute-coiffure.fr"

    # ── Pricing restructure (TASK-2.16.8) ─────────────────────────────────
    # ISO date when the new 2026-05 pricing went live for new signups.
    # Used to segment "new pricing cohort" vs "legacy cohort" in metrics.
    # Defaults to 2026-05-01 (planned cutover). Set to the actual live date
    # once the pricing change is deployed to production.
    pricing_cutover_iso: str = "2026-05-01"

    # ── Email drip (TASK-2.12.15) ─────────────────────────────────────────
    # Master switch — set true in staging/prod once templates are reviewed by Eric.
    # Default FALSE so the scheduler is registered but exits immediately.
    email_drip_enabled: bool = False
    # Dry-run: write email_dispatches rows but don't call SMTP. Useful for QA.
    email_drip_dry_run: bool = False
    # Hour (Paris time) at which the daily drip batch runs (0–23).
    email_drip_send_hour_paris: int = 9
    # Comma-separated UUID strings of users to always exclude from drip cohorts.
    # Add smoketest@comcoi.fr's user ID here in .env.
    email_drip_exclude_user_ids: str = ""
    # Base URL of the frontend app, used to build absolute unsubscribe links.
    # Defaults to frontend_url — override in production to the canonical HTTPS URL.
    frontend_base_url: str = "https://app.comcoi.fr"


@lru_cache
def get_settings() -> Settings:
    """
    Return cached Settings instance.

    Using lru_cache means settings are only loaded once per process.
    This is the standard pattern for FastAPI settings.

    Usage:
        from app.core.config import get_settings
        settings = get_settings()
    """
    return Settings()


# Convenience alias for direct import
settings = get_settings()
