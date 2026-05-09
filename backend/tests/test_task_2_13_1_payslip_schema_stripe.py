"""
Tests for Sprint 2.13.1 — Payslip schema, pricing, and Stripe service layer.

Structure:
  - Pure unit tests (no DB, no network): pricing constants, schema validation,
    display-price framing, config fields, eligible contract types.
  - Stripe-mocked unit tests: create_payment_intent, webhook service handlers
    (use MagicMock AsyncSession to avoid needing a test DB fixture).
  - Route-level integration tests: 401/404 auth gating via ASGITransport +
    smoke test user (real DB must be up: docker compose up -d).

Tests do NOT require a live Stripe account. All Stripe calls are mocked.

WHY MagicMock for DB service tests: the conftest has no db_session fixture.
We test the service logic (state transitions, return values) by providing a
mock session that records calls. DB integration is covered by the migration
(applied in the live stack) and inspected via route-level tests.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app

SMOKE_EMAIL = "smoketest@comcoi.fr"
SMOKE_PASS = "Password123!"


# ── ASGI helper ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def _authed_client(email: str = SMOKE_EMAIL, password: str = SMOKE_PASS):
    """
    Async context manager yielding an ASGI client authenticated as smoke test user.

    Args:
        email:    User email.
        password: User password.

    Yields:
        Authenticated AsyncClient.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, f"Login failed: {r.text}"
        client.cookies.update(r.cookies)
        yield client


# ── 1. Pricing constants ──────────────────────────────────────────────────────


def test_pricing_constants_values():
    """All three pricing tiers must match locked values (no float drift)."""
    from app.services.stripe_per_submission import _PRICING

    assert _PRICING["payslip"]["ttc_cents"] == 2880
    assert _PRICING["payslip"]["ht_eur"] == Decimal("24.00")
    assert _PRICING["payslip"]["ttc_eur"] == Decimal("28.80")

    assert _PRICING["dossier"]["ttc_cents"] == 10200
    assert _PRICING["dossier"]["ht_eur"] == Decimal("85.00")
    assert _PRICING["dossier"]["ttc_eur"] == Decimal("102.00")

    assert _PRICING["contrat"]["ttc_cents"] == 6000
    assert _PRICING["contrat"]["ht_eur"] == Decimal("50.00")
    assert _PRICING["contrat"]["ttc_eur"] == Decimal("60.00")


def test_payslip_ttc_is_ht_times_tva():
    """24 × 1.20 = 28.80 — the core arithmetic identity. Never use 1.2 (float)."""
    from app.services.stripe_per_submission import _PRICING
    tva = Decimal("1.20")
    for kind in ("payslip", "dossier", "contrat"):
        assert _PRICING[kind]["ht_eur"] * tva == _PRICING[kind]["ttc_eur"], (
            f"TVA arithmetic identity failed for {kind!r}"
        )


def test_cents_match_eur():
    """ttc_cents == int(ttc_eur × 100) for all pricing kinds."""
    from app.services.stripe_per_submission import _PRICING
    for kind, p in _PRICING.items():
        expected = int(p["ttc_eur"] * 100)
        assert p["ttc_cents"] == expected, (
            f"Kind {kind!r}: ttc_cents={p['ttc_cents']} but int(ttc_eur×100)={expected}"
        )


# ── 2. DisplayPrice framing ───────────────────────────────────────────────────


def test_display_price_ae_uses_ttc_primary():
    """AE (auto_micro) salons should always see ttc_primary framing."""
    from app.services.stripe_per_submission import build_display_price
    price = build_display_price("payslip", "auto_micro")
    assert price.framing == "ttc_primary"
    assert price.ht_eur == Decimal("24.00")
    assert price.ttc_eur == Decimal("28.80")


def test_display_price_non_ae_uses_ht_primary():
    """Non-AE salons (SARL, SAS, EI, etc.) should see ht_primary framing."""
    from app.services.stripe_per_submission import build_display_price
    for business_type in ("sarl", "sas", "ei", "eurl", None):
        price = build_display_price("payslip", business_type)
        assert price.framing == "ht_primary", f"Expected ht_primary for {business_type!r}"


def test_display_price_dossier_ae():
    """Dossier pricing with AE framing returns correct amounts."""
    from app.services.stripe_per_submission import build_display_price
    price = build_display_price("dossier", "auto_micro")
    assert price.ttc_eur == Decimal("102.00")
    assert price.ht_eur == Decimal("85.00")
    assert price.framing == "ttc_primary"


def test_display_price_contrat_non_ae():
    """Contrat pricing for non-AE returns ht_primary."""
    from app.services.stripe_per_submission import build_display_price
    price = build_display_price("contrat", "sarl")
    assert price.ttc_eur == Decimal("60.00")
    assert price.ht_eur == Decimal("50.00")
    assert price.framing == "ht_primary"


def test_display_price_invalid_kind_raises():
    """Unknown kind should raise KeyError (not found in _PRICING dict)."""
    from app.services.stripe_per_submission import build_display_price
    with pytest.raises(KeyError):
        build_display_price("unknown_kind", "sarl")


# ── 3. SubmissionIntentRequest validation ─────────────────────────────────────


def test_submission_intent_request_valid():
    """A well-formed request passes Pydantic validation."""
    from app.schemas.payslip import SubmissionIntentRequest, EmployeeVariablesIn
    emp = EmployeeVariablesIn(employee_id=uuid.uuid4())
    req = SubmissionIntentRequest(
        period_month=3,
        period_year=2026,
        employees=[emp],
    )
    assert req.period_month == 3
    assert len(req.employees) == 1


def test_submission_intent_request_period_month_lower_bound():
    """period_month=0 must be rejected."""
    from app.schemas.payslip import SubmissionIntentRequest, EmployeeVariablesIn
    from pydantic import ValidationError
    emp = EmployeeVariablesIn(employee_id=uuid.uuid4())
    with pytest.raises(ValidationError):
        SubmissionIntentRequest(period_month=0, period_year=2026, employees=[emp])


def test_submission_intent_request_period_month_upper_bound():
    """period_month=13 must be rejected."""
    from app.schemas.payslip import SubmissionIntentRequest, EmployeeVariablesIn
    from pydantic import ValidationError
    emp = EmployeeVariablesIn(employee_id=uuid.uuid4())
    with pytest.raises(ValidationError):
        SubmissionIntentRequest(period_month=13, period_year=2026, employees=[emp])


def test_submission_intent_request_requires_at_least_one_employee():
    """employees list must have at least 1 item."""
    from app.schemas.payslip import SubmissionIntentRequest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        SubmissionIntentRequest(period_month=3, period_year=2026, employees=[])


def test_submission_intent_request_period_year_lower_bound():
    """period_year < 2020 must be rejected."""
    from app.schemas.payslip import SubmissionIntentRequest, EmployeeVariablesIn
    from pydantic import ValidationError
    emp = EmployeeVariablesIn(employee_id=uuid.uuid4())
    with pytest.raises(ValidationError):
        SubmissionIntentRequest(period_month=3, period_year=2019, employees=[emp])


def test_employee_variables_prime_pct_bounds():
    """prime_conventionnelle_pct must be 0–100."""
    from app.schemas.payslip import EmployeeVariablesIn
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        EmployeeVariablesIn(employee_id=uuid.uuid4(), prime_conventionnelle_pct=Decimal("101"))
    with pytest.raises(ValidationError):
        EmployeeVariablesIn(employee_id=uuid.uuid4(), prime_conventionnelle_pct=Decimal("-1"))


# ── 4. ContratEmployeeData validation ─────────────────────────────────────────


def test_contrat_employee_data_valid():
    """Valid contrat employee data passes Pydantic validation."""
    from app.schemas.payslip import ContratEmployeeData
    from datetime import date
    data = ContratEmployeeData(
        nom="Dupont",
        prenom="Marie",
        type_contrat="CDI",
        date_debut=date(2026, 5, 1),
        salaire_brut_mensuel=Decimal("2000.00"),
        heures_hebdomadaires=Decimal("35"),
        role="coiffeure",
    )
    assert data.nom == "Dupont"
    assert data.type_contrat == "CDI"


def test_contrat_employee_data_all_valid_types():
    """All four valid contract types must be accepted."""
    from app.schemas.payslip import ContratEmployeeData
    from datetime import date
    for ct in ("CDI", "CDD", "Apprentissage", "Prestation"):
        d = ContratEmployeeData(
            nom="Test", prenom="User", type_contrat=ct,
            date_debut=date(2026, 6, 1),
            salaire_brut_mensuel=Decimal("1800"),
            heures_hebdomadaires=Decimal("35"),
            role="coiffeur",
        )
        assert d.type_contrat == ct


def test_contrat_employee_data_invalid_contract_type():
    """type_contrat must be CDI | CDD | Apprentissage | Prestation."""
    from app.schemas.payslip import ContratEmployeeData
    from datetime import date
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ContratEmployeeData(
            nom="Dupont", prenom="Marie", type_contrat="TempsPartiel",
            date_debut=date(2026, 5, 1),
            salaire_brut_mensuel=Decimal("2000.00"),
            heures_hebdomadaires=Decimal("35"),
            role="coiffeure",
        )


def test_contrat_employee_data_negative_salary_rejected():
    """Negative salary must be rejected."""
    from app.schemas.payslip import ContratEmployeeData
    from datetime import date
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ContratEmployeeData(
            nom="Dupont", prenom="Marie", type_contrat="CDI",
            date_debut=date(2026, 5, 1),
            salaire_brut_mensuel=Decimal("-1.00"),
            heures_hebdomadaires=Decimal("35"),
            role="coiffeure",
        )


# ── 5. Config assertion ───────────────────────────────────────────────────────


def test_payslip_unit_price_cents_is_2880():
    """settings.payslip_unit_price_cents must always equal 2880."""
    from app.core.config import settings
    assert settings.payslip_unit_price_cents == 2880


def test_config_has_new_payslip_fields():
    """New config fields added in 2.13.1 must be present with expected defaults."""
    from app.core.config import settings
    assert hasattr(settings, "payslip_processor_email")
    assert hasattr(settings, "imap_host")
    assert hasattr(settings, "imap_port")
    assert hasattr(settings, "s3_endpoint_url")
    assert hasattr(settings, "s3_bucket_name")
    assert settings.imap_port == 993
    assert settings.s3_bucket_name == "comcoi-payslips"
    # imap/s3 are empty by default (only set in production .env)
    assert settings.imap_host == ""
    assert settings.s3_endpoint_url == ""


# ── 6. ELIGIBLE_CONTRACT_TYPES ───────────────────────────────────────────────


def test_eligible_contract_types_includes_expected():
    """CDI, CDD, Apprentissage, Assimilé Salarié must all be eligible."""
    from app.services.stripe_per_submission import ELIGIBLE_CONTRACT_TYPES
    for ct in ("cdi", "cdd", "apprentissage", "assimile_salarie"):
        assert ct in ELIGIBLE_CONTRACT_TYPES, f"{ct!r} should be eligible"


def test_eligible_contract_types_excludes_ineligible():
    """TNS and prestataire must NOT be eligible for payslip submission."""
    from app.services.stripe_per_submission import ELIGIBLE_CONTRACT_TYPES
    for ct in ("contrat_prestataire", "tns", "gerant_majoritaire", "associe_non_gerant"):
        assert ct not in ELIGIBLE_CONTRACT_TYPES, f"{ct!r} should NOT be eligible"


# ── 7. create_payment_intent — mocked Stripe ─────────────────────────────────


@pytest.mark.asyncio
async def test_create_payment_intent_payslip_amount_and_metadata():
    """
    create_payment_intent for 'payslip' should call stripe.PaymentIntent.create
    with amount = N × 2880 and correct metadata keys.
    """
    from app.services.stripe_per_submission import create_payment_intent

    mock_intent = MagicMock()
    mock_intent.id = "pi_test_abc123"
    mock_intent.client_secret = "pi_test_abc123_secret_xyz"

    salon_id = uuid.uuid4()
    user_id = uuid.uuid4()
    emp1 = uuid.uuid4()
    emp2 = uuid.uuid4()

    with patch("stripe.PaymentIntent.create", return_value=mock_intent) as mock_create:
        intent = await create_payment_intent(
            kind="payslip",
            salon_id=salon_id,
            user_id=user_id,
            quantity=2,
            submission_ids=[emp1, emp2],
        )

    assert intent.id == "pi_test_abc123"
    call_kwargs = mock_create.call_args[1]
    assert call_kwargs["amount"] == 5760  # 2 × 2880 cents
    assert call_kwargs["currency"] == "eur"
    assert call_kwargs["metadata"]["kind"] == "payslip"
    assert call_kwargs["metadata"]["salon_id"] == str(salon_id)
    assert call_kwargs["metadata"]["quantity"] == "2"
    # Both emp IDs in submission_ids string
    assert str(emp1) in call_kwargs["metadata"]["submission_ids"]
    assert str(emp2) in call_kwargs["metadata"]["submission_ids"]


@pytest.mark.asyncio
async def test_create_payment_intent_dossier_amount():
    """create_payment_intent for 'dossier' charges 10200 cents (102 € TTC)."""
    from app.services.stripe_per_submission import create_payment_intent

    mock_intent = MagicMock()
    mock_intent.id = "pi_dossier_123"
    mock_intent.client_secret = "sec"

    with patch("stripe.PaymentIntent.create", return_value=mock_intent) as mock_create:
        await create_payment_intent(
            kind="dossier",
            salon_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            quantity=1,
        )
    assert mock_create.call_args[1]["amount"] == 10200


@pytest.mark.asyncio
async def test_create_payment_intent_contrat_amount():
    """create_payment_intent for 'contrat' charges 6000 cents (60 € TTC)."""
    from app.services.stripe_per_submission import create_payment_intent

    mock_intent = MagicMock()
    mock_intent.id = "pi_contrat_123"
    mock_intent.client_secret = "sec"

    with patch("stripe.PaymentIntent.create", return_value=mock_intent) as mock_create:
        await create_payment_intent(
            kind="contrat",
            salon_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            quantity=1,
        )
    assert mock_create.call_args[1]["amount"] == 6000


@pytest.mark.asyncio
async def test_create_payment_intent_invalid_kind_raises():
    """Unknown kind must raise ValueError before calling Stripe."""
    from app.services.stripe_per_submission import create_payment_intent
    with pytest.raises(ValueError, match="Invalid payslip kind"):
        await create_payment_intent(
            kind="wallet",  # invalid — wallet model was never built
            salon_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_create_payment_intent_quantity_three():
    """Quantity=3 means 3 × 2880 = 8640 cents."""
    from app.services.stripe_per_submission import create_payment_intent
    mock_intent = MagicMock()
    mock_intent.id = "pi_q3"
    mock_intent.client_secret = "sec"
    emp_ids = [uuid.uuid4() for _ in range(3)]
    with patch("stripe.PaymentIntent.create", return_value=mock_intent) as mc:
        await create_payment_intent(
            kind="payslip",
            salon_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            quantity=3,
            submission_ids=emp_ids,
        )
    assert mc.call_args[1]["amount"] == 8640


# ── 8. mark_event_processed — idempotency (mocked DB) ─────────────────────────


@pytest.mark.asyncio
async def test_mark_event_processed_first_call_returns_true():
    """First call with a fresh event_id returns True (event recorded)."""
    from app.services.stripe_per_submission import mark_event_processed

    # Mock DB: flush succeeds (no IntegrityError)
    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.add = MagicMock()

    result = await mark_event_processed("evt_new_abc123", mock_db)
    assert result is True
    mock_db.add.assert_called_once()
    mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_mark_event_processed_duplicate_returns_false():
    """Second call with same event_id returns False (IntegrityError → rollback)."""
    from app.services.stripe_per_submission import mark_event_processed
    from sqlalchemy.exc import IntegrityError

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock(side_effect=IntegrityError("", {}, Exception()))
    mock_db.rollback = AsyncMock()

    result = await mark_event_processed("evt_duplicate", mock_db)
    assert result is False
    mock_db.rollback.assert_awaited_once()


# ── 9. _handle_payslip_succeeded — mocked DB ─────────────────────────────────


@pytest.mark.asyncio
async def test_handle_payslip_succeeded_no_submission_ids():
    """When metadata has no submission_ids, returns action=no_submission_ids."""
    from app.services.stripe_per_submission import _handle_payslip_succeeded
    mock_db = AsyncMock()
    result = await _handle_payslip_succeeded("pi_test", {}, mock_db)
    assert result["action"] == "no_submission_ids"


@pytest.mark.asyncio
async def test_handle_dossier_succeeded_no_salon_id():
    """When salon_id_str is empty, returns action=no_salon_id."""
    from app.services.stripe_per_submission import _handle_dossier_succeeded
    mock_db = AsyncMock()
    result = await _handle_dossier_succeeded("pi_test", "", mock_db)
    assert result["action"] == "no_salon_id"


@pytest.mark.asyncio
async def test_handle_contrat_succeeded_no_contrat_id():
    """When metadata has no contrat_request_id, returns action=no_contrat_request_id."""
    from app.services.stripe_per_submission import _handle_contrat_succeeded
    mock_db = AsyncMock()
    result = await _handle_contrat_succeeded("pi_test", {}, mock_db)
    assert result["action"] == "no_contrat_request_id"


# ── 10. DossierGatingError schema ────────────────────────────────────────────


def test_dossier_gating_error_defaults():
    """DossierGatingError must serialize with correct defaults."""
    from app.schemas.payslip import DossierGatingError
    err = DossierGatingError(dossier_status="not_started")
    data = err.model_dump()
    assert data["error"] == "dossier_not_active"
    assert data["dossier_status"] == "not_started"
    assert data["next_step"] == "/fiches-salaire/dossier"


def test_dossier_gating_error_paid_status():
    """DossierGatingError must work for 'paid' status (pending Eric activation)."""
    from app.schemas.payslip import DossierGatingError
    err = DossierGatingError(dossier_status="paid")
    assert err.dossier_status == "paid"
    assert err.error == "dossier_not_active"


def test_dossier_gating_error_suspended_status():
    """DossierGatingError must work for 'suspended' status."""
    from app.schemas.payslip import DossierGatingError
    err = DossierGatingError(dossier_status="suspended")
    assert err.dossier_status == "suspended"
    assert err.next_step == "/fiches-salaire/dossier"


# ── 11. Route-level auth tests (requires running stack) ──────────────────────


@pytest.mark.asyncio
async def test_submissions_intent_requires_auth():
    """POST /api/salons/{id}/payslip/submissions/intent returns 401 when unauthenticated."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            f"/api/salons/{uuid.uuid4()}/payslip/submissions/intent",
            json={"period_month": 3, "period_year": 2026, "employees": []},
        )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_dossier_status_requires_auth():
    """GET /api/salons/{id}/payslip/dossier returns 401 when unauthenticated."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(f"/api/salons/{uuid.uuid4()}/payslip/dossier")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_dossier_status_404_for_unknown_salon():
    """GET /api/salons/{random_id}/payslip/dossier returns 404 for a non-owned salon."""
    async with _authed_client() as client:
        r = await client.get(f"/api/salons/{uuid.uuid4()}/payslip/dossier")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_contrat_intent_requires_auth():
    """POST /api/salons/{id}/payslip/contrat/intent returns 401 when unauthenticated."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            f"/api/salons/{uuid.uuid4()}/payslip/contrat/intent",
            json={"employee_data": {}},
        )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_dossier_intent_requires_auth():
    """POST /api/salons/{id}/payslip/dossier/intent returns 401 when unauthenticated."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(f"/api/salons/{uuid.uuid4()}/payslip/dossier/intent")
    assert r.status_code == 401
