"""
Tests for TASK-2.17.8 — AI blog enhancement + diff viewer.

Test cases:
  test_enhance_skips_already_cleaned      — script skips 'ai_cleaned' articles
  test_enhance_writes_cleaned_and_diff    — happy path: sets fields, commits
  test_enhance_preserves_numbers_and_dates — numbers/dates intact in storage path
  test_approve_flips_published_version    — POST /approve sets published_version=cleaned
  test_reject_keeps_original_visible      — POST /reject keeps published_version=original
  test_public_endpoint_serves_correct_version — GET /blog/{slug} returns right body

Pattern: self-contained (register → login → seed article → test → cleanup).
All Claude/embedding calls are mocked — no real API calls.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.blog import BlogArticle


# ── Fixtures ──────────────────────────────────────────────────────────────────

ADMIN_EMAIL = f"admin-blog-test-{uuid.uuid4().hex[:6]}@example.com"
ADMIN_PASS = "AdminBlog123!"


async def _register_and_login_admin(client: AsyncClient) -> dict:
    """Register a user, promote to admin in DB, return login cookies."""
    await client.post(
        "/api/auth/register",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS, "name": "Admin Blog Tester"},
    )
    # Promote to admin
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("UPDATE users SET role='admin' WHERE email=:e"),
            {"e": ADMIN_EMAIL},
        )
        await db.commit()

    login_resp = await client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    return {}  # cookies are stored in client session


async def _create_test_article(
    db: AsyncSession,
    *,
    slug_suffix: str = "",
    content: str = "<p class='ql-align-justify'>Test article <b>contenu</b>.</p>",
    enhancement_status: str | None = None,
    published_version: str = "original",
    body_html_cleaned: str | None = None,
) -> BlogArticle:
    """
    Insert a minimal blog article for testing using raw SQL.

    WHY raw SQL: The ORM model maps `embedding` as Text, but the real DB column
    is `vector` type (set by Alembic via raw ALTER COLUMN). asyncpg rejects
    VARCHAR → vector even for NULL values when the ORM generates the INSERT
    with the column listed. Raw SQL omits the `embedding` column entirely so
    it defaults to NULL without a type-mismatch error.
    """
    result = await db.execute(
        text("""
            INSERT INTO blog_articles
                (slug, title, content, is_published, tags,
                 enhancement_status, published_version, body_html_cleaned)
            VALUES
                (:slug, :title, :content, TRUE, ARRAY['test']::text[],
                 :enhancement_status, :published_version, :body_html_cleaned)
            RETURNING id
        """),
        {
            "slug": f"test-article-2178{slug_suffix}",
            "title": "Article de test 2.17.8",
            "content": content,
            "enhancement_status": enhancement_status,
            "published_version": published_version,
            "body_html_cleaned": body_html_cleaned,
        },
    )
    row = result.fetchone()
    await db.commit()

    # Fetch the ORM object for callers that need it
    article_result = await db.execute(
        text("SELECT * FROM blog_articles WHERE id = :id"),
        {"id": row[0]},
    )
    # Return as a lightweight namespace — tests only need .id, .slug, .published_version etc.
    from sqlalchemy import select as sa_select
    orm_result = await db.execute(
        sa_select(BlogArticle).where(BlogArticle.id == row[0])
    )
    return orm_result.scalar_one()


async def _cleanup_articles(db: AsyncSession) -> None:
    """Remove test articles created by this test module."""
    await db.execute(
        text("DELETE FROM blog_articles WHERE slug LIKE 'test-article-2178%'")
    )
    await db.commit()


async def _cleanup_user() -> None:
    """Remove test admin user."""
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("DELETE FROM users WHERE email=:e"),
            {"e": ADMIN_EMAIL},
        )
        await db.commit()


# ── Test 1: enhance_article skips already-cleaned articles ────────────────────

@pytest.mark.asyncio
async def test_enhance_skips_already_cleaned():
    """
    process_articles() must skip articles with enhancement_status='ai_cleaned'
    unless --force is passed.

    WHY: Idempotency — re-running the script after partial processing should not
    double-clean and double-spend Anthropic API credits.
    """
    from scripts.bubble.enhance_blog_articles import process_articles, ALREADY_DONE_STATUSES

    async with AsyncSessionLocal() as db:
        article = await _create_test_article(
            db,
            slug_suffix="-skip",
            enhancement_status="ai_cleaned",
        )
        article_id = str(article.id)

        mock_client = MagicMock()

        with (
            patch("scripts.bubble.enhance_blog_articles.anthropic.Anthropic", return_value=mock_client),
            patch("scripts.bubble.enhance_blog_articles._load_system_prompt", return_value="mock prompt"),
        ):
            result = await process_articles(db, article_slug=f"test-article-2178-skip")

        # Should be skipped, not processed
        assert result["skipped"] == 1, f"Expected 1 skipped, got: {result}"
        assert result["processed"] == 0
        # Claude should never have been called
        mock_client.messages.create.assert_not_called()

        await _cleanup_articles(db)


# ── Test 2: enhance_article writes cleaned HTML, diff, and status ─────────────

@pytest.mark.asyncio
async def test_enhance_writes_cleaned_and_diff():
    """
    enhance_article() must store body_html_cleaned, enhancement_diff, and set
    enhancement_status='ai_cleaned' after a successful Claude call.
    """
    from scripts.bubble.enhance_blog_articles import enhance_article

    cleaned_html = "<p>Contenu nettoyé.</p>"
    changes_summary = ["Suppression des classes ql-*"]
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=f'{{"body_html_cleaned": "{cleaned_html}", "changes_summary": {changes_summary}}}')]

    # Build proper JSON string for the mock
    import json
    mock_response.content = [
        MagicMock(text=json.dumps({
            "body_html_cleaned": cleaned_html,
            "changes_summary": changes_summary,
        }))
    ]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    async with AsyncSessionLocal() as db:
        article = await _create_test_article(db, slug_suffix="-write")
        article_id = article.id

        with patch("app.services.embedding.generate_embedding", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 1024
            await enhance_article(article, db, mock_client, "mock prompt", dry_run=False)

    # WHY fresh SELECT in new session: `article` is detached after the session
    # closes. `db.refresh()` on a detached instance is unreliable in async SQLAlchemy.
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select as sa_select
        result = await db.execute(sa_select(BlogArticle).where(BlogArticle.id == article_id))
        fresh = result.scalar_one()
        assert fresh.body_html_cleaned == cleaned_html
        assert fresh.enhancement_status == "ai_cleaned"
        assert fresh.enhancement_diff is not None
        diff_data = fresh.enhancement_diff
        assert "diff" in diff_data
        assert diff_data["changes_summary"] == changes_summary
        # Embedding should have been regenerated (raw SQL ::vector write)
        assert fresh.embedding is not None

        await _cleanup_articles(db)


# ── Test 3: Claude result stored verbatim — numbers/dates preserved ───────────

@pytest.mark.asyncio
async def test_enhance_preserves_numbers_and_dates():
    """
    The storage path must not modify numbers, dates, or regulatory references.

    We mock Claude to return the original content unchanged. Assert that
    body_html_cleaned exactly equals what Claude returned — no transformation.

    This test is specifically about the storage path, not Claude's behaviour.
    """
    from scripts.bubble.enhance_blog_articles import enhance_article

    original_content = (
        "<p>Le versement libératoire est de 63 € HT/mois."
        " Applicable à compter du 1er janvier 2026.</p>"
    )
    # Mock Claude returns the content unchanged (simulating a perfect original)
    import json
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(text=json.dumps({
            "body_html_cleaned": original_content,
            "changes_summary": [],
        }))
    ]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    async with AsyncSessionLocal() as db:
        article = await _create_test_article(
            db,
            slug_suffix="-preserve",
            content=original_content,
        )
        article_id = article.id

        with patch("app.services.embedding.generate_embedding", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 1024
            await enhance_article(article, db, mock_client, "mock prompt", dry_run=False)

    # WHY fresh SELECT: raw SQL UPDATE doesn't update the in-memory ORM object,
    # so db.refresh() would reflect stale state. Always re-query after raw SQL writes.
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select as sa_select
        r = await db.execute(sa_select(BlogArticle).where(BlogArticle.id == article_id))
        fresh = r.scalar_one()
        # Storage path must not modify the cleaned HTML
        assert "63 €" in fresh.body_html_cleaned
        assert "1er janvier 2026" in fresh.body_html_cleaned
        # Exact preservation
        assert fresh.body_html_cleaned == original_content

        await _cleanup_articles(db)


# ── Test 4: approve flips published_version to 'cleaned' ──────────────────────

@pytest.mark.asyncio
async def test_approve_flips_published_version():
    """
    POST /api/admin/blog/articles/{id}/approve must set:
      - published_version = 'cleaned'
      - enhancement_status = 'reviewed'
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await _register_and_login_admin(client)

        async with AsyncSessionLocal() as db:
            article = await _create_test_article(
                db,
                slug_suffix="-approve",
                enhancement_status="ai_cleaned",
                body_html_cleaned="<p>Version nettoyée.</p>",
            )
            article_id = str(article.id)

        resp = await client.post(
            f"/api/admin/blog/articles/{article_id}/approve",
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["published_version"] == "cleaned"
        assert data["enhancement_status"] == "reviewed"

        # Verify DB was updated — fresh SELECT (article is detached from its session)
        async with AsyncSessionLocal() as db2:
            from sqlalchemy import select as sa_select
            r2 = await db2.execute(sa_select(BlogArticle).where(BlogArticle.id == uuid.UUID(article_id)))
            fresh = r2.scalar_one()
            assert fresh.published_version == "cleaned"
            assert fresh.enhancement_status == "reviewed"
            await _cleanup_articles(db2)

    await _cleanup_user()


# ── Test 5: reject keeps published_version = 'original' ──────────────────────

@pytest.mark.asyncio
async def test_reject_keeps_original_visible():
    """
    POST /api/admin/blog/articles/{id}/reject must set:
      - enhancement_status = 'rejected'
      - published_version remains (or resets to) 'original'
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await _register_and_login_admin(client)

        async with AsyncSessionLocal() as db:
            article = await _create_test_article(
                db,
                slug_suffix="-reject",
                enhancement_status="ai_cleaned",
                body_html_cleaned="<p>Version nettoyée.</p>",
            )
            article_id = str(article.id)

        resp = await client.post(
            f"/api/admin/blog/articles/{article_id}/reject",
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["published_version"] == "original"
        assert data["enhancement_status"] == "rejected"

        # Verify DB — published_version is original, not cleaned
        # WHY fresh SELECT: article object is detached from its original session
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select as sa_select
            r = await db.execute(sa_select(BlogArticle).where(BlogArticle.id == uuid.UUID(article_id)))
            fresh = r.scalar_one()
            assert fresh.published_version == "original"
            assert fresh.enhancement_status == "rejected"
            await _cleanup_articles(db)

    await _cleanup_user()


# ── Test 6: public endpoint serves correct version ────────────────────────────

@pytest.mark.asyncio
async def test_public_endpoint_serves_correct_version():
    """
    GET /api/blog/{slug} must:
      - return original content when published_version='original'
      - return body_html_cleaned when published_version='cleaned'

    No auth required — public endpoint.
    """
    from app.routers.blog import _resolve_body

    original = "<p class='ql-align'>Original Quill HTML.</p>"
    cleaned = "<p>Contenu nettoyé et corrigé.</p>"

    # ── Sub-case A: original version ──────────────────────────────────────────
    mock_original = MagicMock(spec=BlogArticle)
    mock_original.published_version = "original"
    mock_original.body_html_cleaned = cleaned
    mock_original.content = original
    assert _resolve_body(mock_original) == original

    # ── Sub-case B: cleaned version approved ─────────────────────────────────
    mock_cleaned = MagicMock(spec=BlogArticle)
    mock_cleaned.published_version = "cleaned"
    mock_cleaned.body_html_cleaned = cleaned
    mock_cleaned.content = original
    assert _resolve_body(mock_cleaned) == cleaned

    # ── Sub-case C: cleaned approved but body_html_cleaned is NULL (edge case)
    mock_null = MagicMock(spec=BlogArticle)
    mock_null.published_version = "cleaned"
    mock_null.body_html_cleaned = None
    mock_null.content = original
    # Must fall back to original to prevent serving an empty page
    assert _resolve_body(mock_null) == original

    # ── Integration: real DB article via /api/blog/{slug} ────────────────────
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        async with AsyncSessionLocal() as db:
            # Create an article with cleaned version approved
            article = await _create_test_article(
                db,
                slug_suffix="-public",
                content=original,
                enhancement_status="reviewed",
                published_version="cleaned",
                body_html_cleaned=cleaned,
            )

        resp = await client.get("/api/blog/test-article-2178-public")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # Must serve cleaned version
        assert data["body_html"] == cleaned
        assert data["is_ai_enhanced"] is True

        # Switch back to original
        async with AsyncSessionLocal() as db:
            await db.execute(
                text(
                    "UPDATE blog_articles SET published_version='original' "
                    "WHERE slug='test-article-2178-public'"
                )
            )
            await db.commit()

        resp2 = await client.get("/api/blog/test-article-2178-public")
        assert resp2.status_code == 200
        data2 = resp2.json()
        # Must serve original version
        assert data2["body_html"] == original
        assert data2["is_ai_enhanced"] is False

        async with AsyncSessionLocal() as db:
            await _cleanup_articles(db)
