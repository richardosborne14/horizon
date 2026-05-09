"""
Tests for Task 2.9.8.2 — Brand Purchases API (brand-level product expense breakdown).

Uses the project's synchronous TestClient + direct DB user creation pattern.

Run inside Docker:
    docker compose exec -w /app backend python -m pytest tests/test_task_2_9_8_2_brand_purchases.py -v
"""

import asyncio
from decimal import Decimal

import pytest
from starlette.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app
from app.services.auth import hash_password

# ── Shared test credentials ────────────────────────────────────────────────────

_EMAIL_A = "brand_test_user_a_2982@example.com"
_EMAIL_B = "brand_test_user_b_2982@example.com"
_PASSWORD = "TestPassword123!"


def _ensure_user(email: str) -> None:
    """Create a test user directly in the DB if they don't already exist."""
    engine = create_async_engine(settings.database_url, echo=False)

    async def _run():
        async with AsyncSession(engine, expire_on_commit=False) as db:
            from app.models.user import User
            result = await db.execute(select(User).where(User.email == email))
            if not result.scalar_one_or_none():
                user = User(
                    email=email,
                    password_hash=hash_password(_PASSWORD),
                    name="Brand Test",
                )
                db.add(user)
                await db.commit()
        await engine.dispose()

    asyncio.get_event_loop().run_until_complete(_run())


def _login(client: TestClient, email: str) -> dict:
    """Login and return cookies dict."""
    resp = client.post("/api/auth/login", json={"email": email, "password": _PASSWORD})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return dict(resp.cookies)


def _create_salon(client: TestClient, cookies: dict, name: str = "Brand Test Salon") -> str:
    """Create a salon and return its id."""
    resp = client.post("/api/salons", json={"name": name, "business_type": "sarl"}, cookies=cookies)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


def _create_report(client: TestClient, cookies: dict, salon_id: str, month: int = 4) -> str:
    """Create a monthly report and return its id."""
    resp = client.post(
        f"/api/salons/{salon_id}/monthly-reports",
        json={"year": 2026, "month": month, "ca_realise_ttc": "4000.00", "subventions": "0.00"},
        cookies=cookies,
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


# ── Module-level fixture ───────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    _ensure_user(_EMAIL_A)
    _ensure_user(_EMAIL_B)
    with TestClient(app) as c:
        yield c


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_crud_happy_path(client: TestClient) -> None:
    """POST → GET list → PATCH amount → DELETE → GET returns empty."""
    cookies = _login(client, _EMAIL_A)
    salon_id = _create_salon(client, cookies, "Salon CRUD Test")
    report_id = _create_report(client, cookies, salon_id)

    # POST — add L'Oréal row
    resp = client.post(
        f"/api/monthly-reports/{report_id}/brands?salon_id={salon_id}",
        json={"brand": "L'Oréal Professionnel", "amount_ht": "680.00", "tva_rate": "0.2000"},
        cookies=cookies,
    )
    assert resp.status_code == 201, resp.text
    row = resp.json()
    assert row["brand"] == "L'Oréal Professionnel"
    assert Decimal(row["amount_ht"]) == Decimal("680.00")
    assert Decimal(row["amount_ttc"]) == Decimal("816.00")  # 680 × 1.2
    purchase_id = row["id"]

    # GET list — 1 row
    resp = client.get(f"/api/monthly-reports/{report_id}/brands?salon_id={salon_id}", cookies=cookies)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # PATCH — change amount
    resp = client.patch(
        f"/api/brand-purchases/{purchase_id}?salon_id={salon_id}",
        json={"amount_ht": "750.00"},
        cookies=cookies,
    )
    assert resp.status_code == 200
    assert Decimal(resp.json()["amount_ht"]) == Decimal("750.00")

    # DELETE
    resp = client.delete(f"/api/brand-purchases/{purchase_id}?salon_id={salon_id}", cookies=cookies)
    assert resp.status_code == 204

    # GET list — empty
    resp = client.get(f"/api/monthly-reports/{report_id}/brands?salon_id={salon_id}", cookies=cookies)
    assert resp.status_code == 200
    assert resp.json() == []


def test_sum_of_rows(client: TestClient) -> None:
    """Multiple brand rows sum to the expected total."""
    cookies = _login(client, _EMAIL_A)
    salon_id = _create_salon(client, cookies, "Salon Sum Test")
    report_id = _create_report(client, cookies, salon_id)

    brands = [
        ("L'Oréal Professionnel", "680.00"),
        ("Kérastase", "320.00"),
        ("Wella Professionals", "280.00"),
    ]
    for brand, amt in brands:
        resp = client.post(
            f"/api/monthly-reports/{report_id}/brands?salon_id={salon_id}",
            json={"brand": brand, "amount_ht": amt, "tva_rate": "0.2000"},
            cookies=cookies,
        )
        assert resp.status_code == 201

    resp = client.get(f"/api/monthly-reports/{report_id}/brands?salon_id={salon_id}", cookies=cookies)
    assert resp.status_code == 200
    rows = resp.json()
    total = sum(Decimal(r["amount_ht"]) for r in rows)
    assert total == Decimal("1280.00")
    assert len(rows) == 3


def test_empty_list_when_no_rows(client: TestClient) -> None:
    """GET list returns [] for report with no brand rows — no crash."""
    cookies = _login(client, _EMAIL_A)
    salon_id = _create_salon(client, cookies, "Salon Empty Test")
    report_id = _create_report(client, cookies, salon_id)

    resp = client.get(f"/api/monthly-reports/{report_id}/brands?salon_id={salon_id}", cookies=cookies)
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_non_empty_after_add(client: TestClient) -> None:
    """GET list returns rows after at least one is added."""
    cookies = _login(client, _EMAIL_A)
    salon_id = _create_salon(client, cookies, "Salon NonEmpty Test")
    report_id = _create_report(client, cookies, salon_id)

    resp = client.post(
        f"/api/monthly-reports/{report_id}/brands?salon_id={salon_id}",
        json={"brand": "Generik", "amount_ht": "140.00"},
        cookies=cookies,
    )
    assert resp.status_code == 201

    resp = client.get(f"/api/monthly-reports/{report_id}/brands?salon_id={salon_id}", cookies=cookies)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_monthly_trend_zero_fill(client: TestClient) -> None:
    """Trend endpoint returns 12 zero-filled points per brand."""
    cookies = _login(client, _EMAIL_A)
    salon_id = _create_salon(client, cookies, "Salon Trend Test")
    report_id = _create_report(client, cookies, salon_id, month=4)  # April 2026

    client.post(
        f"/api/monthly-reports/{report_id}/brands?salon_id={salon_id}",
        json={"brand": "L'Oréal Professionnel", "amount_ht": "500.00"},
        cookies=cookies,
    )

    resp = client.get(f"/api/salons/{salon_id}/brand-purchases/trends/2026", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["year"] == 2026
    assert "L'Oréal Professionnel" in data["brands"]
    points = data["brands"]["L'Oréal Professionnel"]
    assert len(points) == 12

    april = next(p for p in points if p["month"] == 4)
    assert Decimal(april["amount_ht"]) == Decimal("500.00")

    jan = next(p for p in points if p["month"] == 1)
    assert Decimal(jan["amount_ht"]) == Decimal("0")


def test_scope_guard_write(client: TestClient) -> None:
    """User B cannot POST to user A's report (403)."""
    cookies_a = _login(client, _EMAIL_A)
    salon_id_a = _create_salon(client, cookies_a, "Salon A Scope")
    report_id_a = _create_report(client, cookies_a, salon_id_a)

    cookies_b = _login(client, _EMAIL_B)
    salon_id_b = _create_salon(client, cookies_b, "Salon B Scope")

    # User B posts to A's report using B's salon_id as scope guard
    resp = client.post(
        f"/api/monthly-reports/{report_id_a}/brands?salon_id={salon_id_b}",
        json={"brand": "Wella", "amount_ht": "100.00"},
        cookies=cookies_b,
    )
    assert resp.status_code == 403


def test_scope_guard_read(client: TestClient) -> None:
    """User B cannot GET user A's brand rows (403)."""
    cookies_a = _login(client, _EMAIL_A)
    salon_id_a = _create_salon(client, cookies_a, "Salon A Read Scope")
    report_id_a = _create_report(client, cookies_a, salon_id_a)

    cookies_b = _login(client, _EMAIL_B)
    salon_id_b = _create_salon(client, cookies_b, "Salon B Read Scope")

    resp = client.get(
        f"/api/monthly-reports/{report_id_a}/brands?salon_id={salon_id_b}",
        cookies=cookies_b,
    )
    assert resp.status_code == 403


def test_tva_rate_too_high(client: TestClient) -> None:
    """tva_rate > 1 raises 422 validation error."""
    cookies = _login(client, _EMAIL_A)
    salon_id = _create_salon(client, cookies, "Salon TVA Test")
    report_id = _create_report(client, cookies, salon_id)

    resp = client.post(
        f"/api/monthly-reports/{report_id}/brands?salon_id={salon_id}",
        json={"brand": "Wella", "amount_ht": "100.00", "tva_rate": "1.5"},
        cookies=cookies,
    )
    assert resp.status_code == 422


def test_amount_ht_must_be_positive(client: TestClient) -> None:
    """amount_ht ≤ 0 raises 422."""
    cookies = _login(client, _EMAIL_A)
    salon_id = _create_salon(client, cookies, "Salon Amount Test")
    report_id = _create_report(client, cookies, salon_id)

    for bad_amt in ["0.00", "-50.00"]:
        resp = client.post(
            f"/api/monthly-reports/{report_id}/brands?salon_id={salon_id}",
            json={"brand": "Wella", "amount_ht": bad_amt},
            cookies=cookies,
        )
        assert resp.status_code == 422, f"Expected 422 for amount_ht={bad_amt}"


def test_static_data_product_brands() -> None:
    """GET /api/static-data/product-brands returns 25 brands, no auth required."""
    with TestClient(app) as client:
        resp = client.get("/api/static-data/product-brands")
        assert resp.status_code == 200
        brands = resp.json()
        assert len(brands) == 25
        keys = [b["key"] for b in brands]
        assert "loreal" in keys
        assert "autre" in keys
        assert all(not b["is_partner"] for b in brands)
