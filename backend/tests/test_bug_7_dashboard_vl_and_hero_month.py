"""
Tests for Bug 7 — two connected dashboard regressions reported by
richard2@digitalbricks.io on 23 April 2026:

  (A) VL not propagated into dashboard point mort.
      The `compute_full_point_mort` calls in `routers/salons.py` (latest_month,
      monthly_trend, current_month) and in `routers/monthly_reports.py`
      (list_monthly_reports) did not receive `versement_liberatoire`.
      Result: dashboard used 21.2% URSSAF instead of 22.9% (21.2% + 1.7% VL),
      so the dashboard's "résultat" was higher than the pilotage page's by
      exactly `CA × 0.017`. On a 4 000 € CA that's 68 €.

      Pilotage (correct):      4000 − (1000 + 916 + 2000) = 84 €
      Dashboard (was buggy):   4000 − (1000 + 848 + 2000) = 152 €

  (B) Dashboard hero showed a future month (e.g. "décembre 2026" when today
      is April 2026).
      The wizard pre-populates ALL 12 months of the year from the typical
      month template. The dashboard's `latest_month` query ordered by
      (year, month) DESC with no future filter → picked December every time.
      Fix: restrict to rows where (year, month) ≤ (today.year, today.month).

These tests exercise the real /dashboard-summary endpoint so we catch the
wiring bug at the correct seam (router → service → calculation).
"""
from __future__ import annotations

import contextlib
import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


# ── Helpers (deliberately isolated from other test files so this test suite
#    is self-contained and can be run alone with `pytest test_bug_7_*.py`) ──

@contextlib.asynccontextmanager
async def _client():
    """In-process FastAPI client — no real HTTP, avoids host/docker confusion."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _register_login(client: AsyncClient, email: str) -> None:
    """Register a fresh user and log in."""
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "TestPass123!", "name": "Test VL"},
    )
    assert resp.status_code in (200, 201, 409), resp.text
    resp = await client.post("/api/auth/login", json={"email": email, "password": "TestPass123!"})
    assert resp.status_code == 200, resp.text


async def _create_ae_salon(client: AsyncClient, *, versement_liberatoire: bool) -> str:
    """Create an AE salon. `versement_liberatoire` is on the Salon model itself."""
    resp = await client.post(
        "/api/salons",
        json={
            "name": "Salon VL Test",
            "business_type": "auto_micro",
            "versement_liberatoire": versement_liberatoire,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _put_config(client: AsyncClient, salon_id: str, payload: dict) -> None:
    """PUT salon config — used for ae_activity_type and cout_vie_perso_mensuel."""
    resp = await client.put(f"/api/salons/{salon_id}/config", json=payload)
    assert resp.status_code == 200, resp.text


async def _first_category_id(client: AsyncClient) -> str:
    """Fetch first expense category for use in _post_report."""
    resp = await client.get("/api/static-data/expense-categories")
    assert resp.status_code == 200, resp.text
    return str(resp.json()[0]["id"])


async def _post_report(
    client: AsyncClient,
    salon_id: str,
    year: int,
    month: int,
    ca_ttc: float,
    expense_amount_ttc: float | None = None,
) -> str:
    """Create a MonthlyReport with an optional 0% TVA expense."""
    resp = await client.post(
        f"/api/salons/{salon_id}/monthly-reports",
        json={"year": year, "month": month, "ca_realise_ttc": ca_ttc},
    )
    assert resp.status_code in (200, 201), resp.text
    report_id = resp.json()["id"]

    if expense_amount_ttc is not None:
        cat = await _first_category_id(client)
        r = await client.post(
            f"/api/salons/{salon_id}/monthly-reports/{report_id}/expenses",
            json={"category_id": cat, "amount_ttc": str(expense_amount_ttc), "tva_rate": "0"},
        )
        assert r.status_code in (200, 201), r.text
    return report_id


async def _get_dashboard(client: AsyncClient, salon_id: str) -> dict:
    """GET /dashboard-summary."""
    resp = await client.get(f"/api/salons/{salon_id}/dashboard-summary")
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── (A) VL propagation tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bug_7_dashboard_latest_month_includes_versement_liberatoire() -> None:
    """
    Reproduces the exact scenario reported on 23 April 2026.

    AE · bic_services · VL=ON · cout_vie_perso=2000 · CA=4000 · expense=1000.

    Expected (matches pilotage/{month}/full):
      URSSAF rate   = 21.2% + 1.7% = 22.9%
      URSSAF amount = 4000 × 0.229 = 916.00
      point_mort    = 1000 (expenses) + 916 (URSSAF) + 2000 (min vital) = 3916
      cash_flow     = 4000 − 3916 = 84

    Before the fix the dashboard used 21.2% → point_mort=3848 → cash_flow=152.
    So the asserted tolerance (<1 €) will fail on the old code path.
    """
    email = f"vl_on_{uuid.uuid4().hex[:8]}@test.comcoi.fr"
    async with _client() as c:
        await _register_login(c, email)
        salon_id = await _create_ae_salon(c, versement_liberatoire=True)
        await _put_config(c, salon_id, {
            "ae_activity_type": "bic_services",
            "cout_vie_perso_mensuel": 2000,
        })

        # Create the current-month report (year/month chosen so it's not in
        # the future). Using 2026-04 mirrors the reported production date.
        await _post_report(c, salon_id, 2026, 4, 4000.0, expense_amount_ttc=1000.0)

        dash = await _get_dashboard(c, salon_id)
        lm = dash["latest_month"]

        # ±1 € tolerance absorbs ROUND_HALF_UP on the individual components.
        assert abs(lm["point_mort"] - 3916) < 1.0, (
            f"point_mort={lm['point_mort']:.2f} should be 3916 "
            f"(1000 expenses + 916 URSSAF@22.9% + 2000 min vital). "
            f"If you see 3848 the VL 1.7% component is missing — revisit "
            f"compute_full_point_mort calls in routers/salons.py."
        )
        assert abs(lm["resultat_net"] - 84) < 1.0, (
            f"resultat_net={lm['resultat_net']:.2f} should be 84 (not 152)."
        )


@pytest.mark.asyncio
async def test_bug_7_dashboard_without_vl_unchanged() -> None:
    """
    Sanity check: without VL the dashboard uses the standard 21.2% rate.

    This guards against an over-eager fix that always adds VL.
    """
    email = f"vl_off_{uuid.uuid4().hex[:8]}@test.comcoi.fr"
    async with _client() as c:
        await _register_login(c, email)
        salon_id = await _create_ae_salon(c, versement_liberatoire=False)
        await _put_config(c, salon_id, {
            "ae_activity_type": "bic_services",
            "cout_vie_perso_mensuel": 2000,
        })

        await _post_report(c, salon_id, 2026, 4, 4000.0, expense_amount_ttc=1000.0)

        dash = await _get_dashboard(c, salon_id)
        lm = dash["latest_month"]

        # 4000 × 21.2% = 848 → point_mort = 1000 + 848 + 2000 = 3848
        assert abs(lm["point_mort"] - 3848) < 1.0, (
            f"point_mort={lm['point_mort']:.2f} should be 3848 without VL."
        )
        assert abs(lm["resultat_net"] - 152) < 1.0


# ── (B) Hero never shows a future month ───────────────────────────────────────


@pytest.mark.asyncio
async def test_bug_7_hero_never_shows_future_month() -> None:
    """
    When the wizard has pre-populated future months (e.g. Dec 2026 when today
    is April 2026), the dashboard hero must pick the CURRENT month, not the
    latest-by-date.

    Setup:
      • Create a "real" month for 2026-04 with CA=3500.
      • Create a "future template" month for 2026-12 with CA=9999 (clearly
        different sentinel value so we can prove which one the hero picked).

    Expected:
      • dashboard.latest_month.month == 4   (April — today's month)
      • dashboard.latest_month.ca_ttc ≈ 3500 (not 9999)

    Before the fix the hero picked 2026-12 because it ordered by
    (year, month) DESC without filtering future rows.
    """
    email = f"hero_month_{uuid.uuid4().hex[:8]}@test.comcoi.fr"
    async with _client() as c:
        await _register_login(c, email)
        salon_id = await _create_ae_salon(c, versement_liberatoire=False)
        await _put_config(c, salon_id, {"ae_activity_type": "bic_services"})

        # WHY these specific dates:
        # The test asserts that (year, month) <= (today.year, today.month)
        # filters out 2026-12. At the time of this fix today is 2026-04-23,
        # but the test also needs to be stable if run later in 2026. As long
        # as today is any month < December 2026, the assertion holds.
        # When run in December 2026 or later, the test will be skipped.
        from datetime import date
        today = date.today()
        if today.year > 2026 or (today.year == 2026 and today.month >= 12):
            pytest.skip("Test only meaningful before Dec 2026.")

        # "Real" current-month entry — the one the hero should pick
        await _post_report(c, salon_id, today.year, today.month, 3500.0)
        # "Future template" entry — the one that MUST NOT be picked
        await _post_report(c, salon_id, 2026, 12, 9999.0)

        dash = await _get_dashboard(c, salon_id)
        lm = dash["latest_month"]
        assert lm is not None, "latest_month should not be null"
        assert lm["month"] == today.month, (
            f"Hero month={lm['month']} should be {today.month} (today), "
            f"not 12 (future template). "
            f"If you see month=12 the (year,month)<=today filter is missing "
            f"from the dashboard query in routers/salons.py."
        )
        assert abs(lm["ca_ttc"] - 3500.0) < 0.01, (
            f"ca_ttc={lm['ca_ttc']} should be 3500 (current month), not 9999 (future)."
        )


@pytest.mark.asyncio
async def test_bug_7_hero_falls_back_to_most_recent_past_when_no_current_month() -> None:
    """
    When today's month has no data but earlier months do, the hero must still
    show a real month (the most recent past one), not jump to a future template.

    Setup:
      • 2026-02 (past, real): CA=2500
      • 2026-12 (future, template): CA=9999
      • No entry for 2026-04 (today).

    Expected:
      • latest_month.month == 2 (February).
    """
    email = f"hero_past_{uuid.uuid4().hex[:8]}@test.comcoi.fr"
    async with _client() as c:
        await _register_login(c, email)
        salon_id = await _create_ae_salon(c, versement_liberatoire=False)
        await _put_config(c, salon_id, {"ae_activity_type": "bic_services"})

        from datetime import date
        today = date.today()
        if today.year > 2026 or (today.year == 2026 and today.month <= 2):
            pytest.skip("Test requires today > Feb 2026 and < Dec 2026.")

        await _post_report(c, salon_id, 2026, 2, 2500.0)
        await _post_report(c, salon_id, 2026, 12, 9999.0)

        dash = await _get_dashboard(c, salon_id)
        lm = dash["latest_month"]
        assert lm is not None
        assert lm["month"] == 2, (
            f"Hero should fall back to Feb 2026 (most recent past). Got month={lm['month']}."
        )
        assert abs(lm["ca_ttc"] - 2500.0) < 0.01


# ── Bug 7c — "Total A + B" display bug (pilotage page) ─────────────────────
#
# Same report from richard2@digitalbricks.io on 23 April 2026: on the pilotage
# page (/pilotage/mois/.../...) the "Total A + B" row displayed 3 916 € when
# the underlying numbers were salaries 0 + expenses 1 000 for an AE on VL.
# Root cause: `compute_full_point_mort` pre-added `urssaf_cotisations` and
# `cout_vie_perso` into `total_AB`, so the UI line labelled "Total A + B"
# silently included URSSAF (916 €) and minimum vital (2 000 €). The final
# point mort and cash flow were mathematically right, only the intermediate
# display was misleading.
#
# Fix: `total_AB = total_A + total_B` (literal). URSSAF and minimum vital are
# added into `total_decaissement` as separate terms, matching how the UI
# renders them (each on its own line below "Total A + B").

class TestBug7cTotalABDisplay:
    """total_AB must equal Section A + Section B literally — no hidden URSSAF."""

    def test_ae_total_ab_excludes_urssaf_and_minimum_vital(self):
        """
        Reproduce the exact numbers from the user's screenshot:
          CA 4 000 €, salaries 0, expenses 1 000, URSSAF 22.9 % (VL),
          minimum vital 2 000, no loan.

        Expected after Bug 7c fix:
          total_AB             = 0 + 1 000 = 1 000  (literal A + B, NOT 3 916)
          urssaf_cotisations   = 4 000 × 22.9 % = 916
          cout_vie_perso       = 2 000
          total_decaissement   = 1 000 + 916 + 2 000 = 3 916
          cash_flow            = 4 000 − 3 916 = 84
        """
        from decimal import Decimal
        from types import SimpleNamespace

        from app.services.monthly_report import compute_full_point_mort

        expense = SimpleNamespace(
            amount_ttc=Decimal("1000"),
            amount_ht=Decimal("1000"),  # AE: HT == TTC
        )
        report = SimpleNamespace(
            ca_realise_ttc=Decimal("4000"),
            subventions=Decimal("0"),
            remboursement_emprunt=Decimal("0"),
            expenses=[expense],
        )
        pm = compute_full_point_mort(
            report,
            [],  # no salary rows
            is_ae=True,
            ae_activity_type="bic_services",
            versement_liberatoire=True,  # 21.2 % + 1.7 % VL = 22.9 %
            cout_vie_perso=Decimal("2000"),
        )

        # The whole point of the bug fix: total_AB is literally A + B.
        assert pm.total_A == Decimal("0")
        assert pm.total_B == Decimal("1000")
        assert pm.total_AB == Decimal("1000"), (
            f"total_AB must be salaries + expenses (1000), got {pm.total_AB}. "
            "Bug 7c regression — URSSAF or minimum vital leaked into total_AB."
        )

        # URSSAF and minimum vital are surfaced as separate fields, NOT rolled
        # into total_AB.
        assert pm.urssaf_cotisations == Decimal("916.00")  # 4000 × 0.229
        assert pm.cout_vie_perso == Decimal("2000")

        # The end-to-end numbers must still be correct (cash flow unchanged).
        assert pm.total_decaissement == Decimal("3916.00")
        assert pm.cash_flow == Decimal("84.00")

    def test_non_ae_total_ab_equals_a_plus_b(self):
        """Non-AE: total_AB must still be literal A + B (unchanged behaviour)."""
        from decimal import Decimal
        from types import SimpleNamespace

        from app.services.monthly_report import compute_full_point_mort

        expense = SimpleNamespace(
            amount_ttc=Decimal("1200"),
            amount_ht=Decimal("1000"),
        )
        report = SimpleNamespace(
            ca_realise_ttc=Decimal("10000"),
            subventions=Decimal("0"),
            remboursement_emprunt=Decimal("0"),
            expenses=[expense],
        )
        salary_row = SimpleNamespace(
            total_charge=Decimal("3000"),
            salaire_brut=Decimal("2000"),
            employee=SimpleNamespace(role_type="salarie"),
        )
        pm = compute_full_point_mort(report, [salary_row], is_ae=False)

        assert pm.total_A == Decimal("3000")
        assert pm.total_B == Decimal("1200")
        assert pm.total_AB == Decimal("4200")  # 3000 + 1200, unchanged
        assert pm.urssaf_cotisations == Decimal("0")
        assert pm.cout_vie_perso == Decimal("0")
        assert pm.total_decaissement == Decimal("4200")  # A + B + 0 + 0 + 0 loan
