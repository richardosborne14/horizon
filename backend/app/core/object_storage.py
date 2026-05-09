"""
Object storage wrapper for Hetzner S3-compatible storage (TASK-2.13.3).

Hetzner Object Storage is S3-compatible — boto3 works with a custom endpoint_url.
PDFs are stored at: payslips/{salon_id}/{YYYY-MM}/{uuid}-{filename}.pdf

Stub mode:
  When S3_ENDPOINT_URL, S3_ACCESS_KEY or S3_SECRET_KEY are empty (default in dev),
  the module operates in stub mode: uploads are no-ops and signed URLs are fake
  local paths. This lets the rest of the inbound pipeline run and test without
  real object storage credentials.

  Stub mode is detected at module load time from settings.
  In production, all three vars must be set or the app should refuse to start
  (not enforced here — document in SETUP-FICHES-SALAIRE.md).

Signing:
  Signed URLs expire after `expiry_seconds` (default: 900 = 15 min).
  Never cache the returned URL client-side — always call generate_signed_url()
  to get a fresh URL. See TASK-2.13.5 for the PDF download endpoint.

WHY boto3 not async: boto3 has no native async API. We run it in a thread pool
via loop.run_in_executor() to avoid blocking the event loop. Same pattern as
Stripe SDK in stripe_per_submission.py.
"""

from __future__ import annotations

import asyncio
import io
import logging
import uuid as _uuid
from functools import partial
from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _is_stub_mode() -> bool:
    """
    Return True when object storage credentials are not configured.

    Stub mode is safe for dev/CI — all operations are no-ops.
    In production, set S3_ENDPOINT_URL, S3_ACCESS_KEY, S3_SECRET_KEY.

    Returns:
        True if any required credential is absent.
    """
    return not all([
        settings.s3_endpoint_url,
        settings.s3_access_key,
        settings.s3_secret_key,
    ])


def _make_s3_client():
    """
    Create a boto3 S3 client for Hetzner Object Storage.

    Called lazily (not at module import) so we don't fail at startup when
    boto3 is installed but credentials are absent (stub mode).

    Returns:
        A boto3 S3 client instance.
    """
    import boto3  # lazy import — only available after pip install
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        # Hetzner Object Storage uses path-style addressing
        config=boto3.session.Config(s3={"addressing_style": "path"}),
    )


# ── Synchronous helpers (run in executor) ─────────────────────────────────────


def _upload_pdf_sync(pdf_bytes: bytes, key: str) -> str:
    """
    Upload PDF bytes to object storage. Synchronous — run in executor.

    Args:
        pdf_bytes: Raw PDF content.
        key:       Storage key (path within bucket).

    Returns:
        The storage key (same as input — unchanged).

    Raises:
        botocore.exceptions.ClientError on S3 errors.
    """
    if _is_stub_mode():
        logger.debug("object_storage: stub mode — skipping upload for key=%s", key)
        return key

    client = _make_s3_client()
    client.upload_fileobj(
        io.BytesIO(pdf_bytes),
        settings.s3_bucket_name,
        key,
        ExtraArgs={"ContentType": "application/pdf"},
    )
    logger.info(
        "object_storage: uploaded key=%s to bucket=%s", key, settings.s3_bucket_name
    )
    return key


def _generate_signed_url_sync(key: str, expiry_seconds: int) -> str:
    """
    Generate a pre-signed GET URL. Synchronous — run in executor.

    Args:
        key:            Storage key as returned by upload_pdf().
        expiry_seconds: URL lifetime in seconds.

    Returns:
        Time-limited HTTPS URL, or a stub path if in stub mode.
    """
    if _is_stub_mode():
        return f"/stub-pdf/{key}"

    client = _make_s3_client()
    url: str = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket_name, "Key": key},
        ExpiresIn=expiry_seconds,
    )
    return url


# ── Public async API ──────────────────────────────────────────────────────────


async def upload_pdf(
    pdf_bytes: bytes,
    salon_id: str,
    period_year: int,
    period_month: int,
    filename: str,
) -> str:
    """
    Upload a PDF to object storage and return the storage key.

    The returned key is stored in `payslip_submissions.pdf_url`.
    To produce a download URL, call generate_signed_url(key).

    Storage path:  payslips/{salon_id}/{YYYY-MM}/{uuid}-{safe_filename}.pdf

    Args:
        pdf_bytes:    Raw PDF bytes.
        salon_id:     Salon UUID string (used in storage path).
        period_year:  Period year (e.g. 2026).
        period_month: Period month (1–12).
        filename:     Original attachment filename (sanitised before use).

    Returns:
        Storage key string, e.g.
        "payslips/abc123/2026-04/f9e1d2a3-Julie_Martin.pdf".
    """
    # Sanitise filename: keep alphanumerics, dots, dashes, underscores only
    safe_name = "".join(
        c if c.isalnum() or c in "._-" else "_" for c in filename
    )
    if not safe_name.lower().endswith(".pdf"):
        safe_name += ".pdf"

    key = (
        f"payslips/{salon_id}/"
        f"{period_year:04d}-{period_month:02d}/"
        f"{_uuid.uuid4()}-{safe_name}"
    )

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, partial(_upload_pdf_sync, pdf_bytes, key)
    )


async def generate_signed_url(key: str, expiry_seconds: int = 900) -> str:
    """
    Generate a time-limited pre-signed URL for downloading a stored PDF.

    Call this on every download request — never cache the URL client-side
    (Hetzner signed URLs expire; stale URLs return 403).

    Args:
        key:            Storage key as returned by upload_pdf().
        expiry_seconds: URL lifetime in seconds (default 900 = 15 min).

    Returns:
        HTTPS URL string. In stub mode, returns "/stub-pdf/{key}".
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, partial(_generate_signed_url_sync, key, expiry_seconds)
    )
