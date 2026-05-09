"""
Tests for TASK-3.6 — Blog admin CRUD endpoints.

Covers:
  - GET  /api/admin/blog/          — list articles (admin only)
  - PATCH /api/admin/blog/{id}     — update article (title, slug, tags, is_published)
  - DELETE /api/admin/blog/{id}    — permanently delete article
  - BlogArticleOut now includes published_at and created_at

Self-contained pattern: register → promote to admin → create article → test → cleanup.
WHY admin-only: All blog management endpoints require role='admin'.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.blog import BlogArticle
from app.models.user import User
from sqlalchemy import select, delete


BASE = "http://test"


async def _register_and_login(client: AsyncClient, email: str, password: str = "Pass123!") -> dict:
    """
    Register a new user and return auth cookies via login.

    Args:
        client: HTTPX async client.
        email: Email to register with.
        password: Password to use.

    Returns:
        Dict with 'access_token' or empty dict (cookie-based auth).
    """
    await client.post("/api/auth/register", json={
        "email": email,
        "password": password,
        "name": "Blog Tester",
    })
    resp = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return {}


async def _promote_to_admin(email: str) -> None:
    """
    Directly promote a user to admin role via DB.

    Args:
        email: User email to promote.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            user.role = "admin"
            db.add(user)
            await db.commit()


async def _cleanup(email: str, article_slugs: list[str]) -> None:
    """
    Delete test articles and user from DB.

    Args:
        email: User email to delete.
        article_slugs: Slugs of articles to delete.
    """
    async with AsyncSessionLocal() as db:
        for slug in article_slugs:
            await db.execute(delete(BlogArticle).where(BlogArticle.slug == slug))
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            await db.delete(user)
        await db.commit()


@pytest.mark.asyncio
async def test_list_articles_requires_admin() -> None:
    """
    GET /api/admin/blog/ returns 403 for non-admin users.
    """
    email = "test_blog_nonadmin_36@example.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        try:
            await _register_and_login(client, email)
            resp = await client.get("/api/admin/blog/")
            assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"
        finally:
            await _cleanup(email, [])


@pytest.mark.asyncio
async def test_list_articles_admin() -> None:
    """
    GET /api/admin/blog/ returns list with id, slug, title, is_published, has_embedding,
    published_at, created_at for admin users.
    """
    email = "test_blog_list_36@example.com"
    slug = "test-list-36"
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        try:
            await _register_and_login(client, email)
            await _promote_to_admin(email)

            # Create an article via import endpoint
            create = await client.post("/api/admin/blog/import", json={
                "title": "Test List Article",
                "slug": slug,
                "content_markdown": "## Test\n\nContent for list test.",
                "tags": ["test", "list"],
                "published": False,
            })
            assert create.status_code == 201, create.text

            resp = await client.get("/api/admin/blog/")
            assert resp.status_code == 200, resp.text
            articles = resp.json()
            assert isinstance(articles, list)

            # Find our article in the list
            found = next((a for a in articles if a["slug"] == slug), None)
            assert found is not None, "Created article not found in list"
            assert found["title"] == "Test List Article"
            assert found["is_published"] is False
            assert "has_embedding" in found
            assert "created_at" in found      # TASK-3.6 addition
            assert "published_at" in found    # TASK-3.6 addition
        finally:
            await _cleanup(email, [slug])


@pytest.mark.asyncio
async def test_patch_article_title_and_tags() -> None:
    """
    PATCH /api/admin/blog/{id} updates title and tags.
    Content left unchanged when not in payload.
    """
    email = "test_blog_patch_36@example.com"
    slug = "test-patch-36"
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        try:
            await _register_and_login(client, email)
            await _promote_to_admin(email)

            create = await client.post("/api/admin/blog/import", json={
                "title": "Original Title",
                "slug": slug,
                "content_markdown": "## Original\n\nOriginal content.",
                "tags": ["original"],
                "published": False,
            })
            assert create.status_code == 201
            article_id = create.json()["id"]

            patch = await client.patch(f"/api/admin/blog/{article_id}", json={
                "title": "Updated Title",
                "tags": ["updated", "patched"],
            })
            assert patch.status_code == 200, patch.text
            body = patch.json()
            assert body["title"] == "Updated Title"
            assert "updated" in body["tags"]
            assert "patched" in body["tags"]
            assert body["slug"] == slug  # unchanged
        finally:
            await _cleanup(email, [slug])


@pytest.mark.asyncio
async def test_patch_article_toggle_published() -> None:
    """
    PATCH /api/admin/blog/{id} with is_published=true publishes the article.
    """
    email = "test_blog_publish_36@example.com"
    slug = "test-publish-36"
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        try:
            await _register_and_login(client, email)
            await _promote_to_admin(email)

            create = await client.post("/api/admin/blog/import", json={
                "title": "Draft Article",
                "slug": slug,
                "content_markdown": "## Draft\n\nNot published yet.",
                "tags": [],
                "published": False,
            })
            assert create.status_code == 201
            article_id = create.json()["id"]
            assert create.json()["is_published"] is False

            patch = await client.patch(f"/api/admin/blog/{article_id}", json={
                "is_published": True,
            })
            assert patch.status_code == 200, patch.text
            assert patch.json()["is_published"] is True

            # Toggle back to unpublished
            patch2 = await client.patch(f"/api/admin/blog/{article_id}", json={
                "is_published": False,
            })
            assert patch2.status_code == 200
            assert patch2.json()["is_published"] is False
        finally:
            await _cleanup(email, [slug])


@pytest.mark.asyncio
async def test_delete_article_removes_from_db() -> None:
    """
    DELETE /api/admin/blog/{id} returns 204 and removes the article permanently.
    Subsequent GET /api/admin/blog/ no longer lists it.
    """
    email = "test_blog_delete_36@example.com"
    slug = "test-delete-36"
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        try:
            await _register_and_login(client, email)
            await _promote_to_admin(email)

            create = await client.post("/api/admin/blog/import", json={
                "title": "Article to Delete",
                "slug": slug,
                "content_markdown": "## Delete Me\n\nThis will be deleted.",
                "tags": ["delete-test"],
                "published": False,
            })
            assert create.status_code == 201
            article_id = create.json()["id"]

            # Delete it
            delete_resp = await client.delete(f"/api/admin/blog/{article_id}")
            assert delete_resp.status_code == 204, delete_resp.text

            # Confirm it's gone from the list
            list_resp = await client.get("/api/admin/blog/")
            assert list_resp.status_code == 200
            articles = list_resp.json()
            slugs = [a["slug"] for a in articles]
            assert slug not in slugs, "Deleted article still appears in list"
        finally:
            await _cleanup(email, [slug])


@pytest.mark.asyncio
async def test_delete_nonexistent_article_returns_404() -> None:
    """
    DELETE /api/admin/blog/{random-uuid} returns 404.
    """
    email = "test_blog_del404_36@example.com"
    fake_id = "00000000-0000-0000-0000-000000000999"
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        try:
            await _register_and_login(client, email)
            await _promote_to_admin(email)

            resp = await client.delete(f"/api/admin/blog/{fake_id}")
            assert resp.status_code == 404, resp.text
            assert "trouvé" in resp.json().get("detail", "").lower()
        finally:
            await _cleanup(email, [])


@pytest.mark.asyncio
async def test_patch_nonexistent_article_returns_404() -> None:
    """
    PATCH /api/admin/blog/{random-uuid} returns 404.
    """
    email = "test_blog_patch404_36@example.com"
    fake_id = "00000000-0000-0000-0000-000000000998"
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        try:
            await _register_and_login(client, email)
            await _promote_to_admin(email)

            resp = await client.patch(f"/api/admin/blog/{fake_id}", json={"title": "Ghost"})
            assert resp.status_code == 404, resp.text
        finally:
            await _cleanup(email, [])
