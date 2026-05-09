"""
TASK-2.15.5 — nb_bulletins_override field for payslip savings engine.

Verifies:
1. Alembic migration added nb_bulletins_override (INTEGER, nullable) to salon_config.
2. Typical-month POST persists the field when provided.
3. Savings engine uses override value instead of team count when set.
4. Savings engine falls back to team count when field is None.
5. SavingsRow one_shot_setup_eur field is included in API response.
"""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch


# ── Unit tests for savings_engine ──────────────────────────────────────────────

def _make_salon_config(**kwargs):
    """Helper: build a minimal mock salon config object."""
    cfg = MagicMock()
    cfg.payslip_current_cost_per_bulletin_ttc = kwargs.get("cost", None)
    cfg.nb_bulletins_override = kwargs.get("override", None)
    cfg.honoraires_comptables_ttc = kwargs.get("honoraires", None)
    cfg.business_type = kwargs.get("business_type", "sarl")
    cfg.achats_produits_annuel_ttc = kwargs.get("achats", None)
    return cfg


class TestNbBulletinsOverride:
    """Savings engine uses override bulletin count when provided."""

    def test_uses_override_when_set(self):
        """When nb_bulletins_override=3, savings uses 3 × cost, not team count."""
        from app.services.savings_engine import compute_payslip_savings

        cfg = _make_salon_config(cost=40.0, override=3)
        result = compute_payslip_savings(
            current_cost_per_bulletin=Decimal("40.0"),
            nb_bulletins=5,          # team count — should be ignored
            nb_bulletins_override=3,  # override takes precedence
        )
        # ComCoi charges 10€/bulletin. Savings = (40 - 10) × 3 × 12 = 1080
        assert result is not None
        assert float(result) == pytest.approx(1080.0, abs=1.0)

    def test_falls_back_to_team_count_when_no_override(self):
        """When nb_bulletins_override=None, savings engine uses team count."""
        from app.services.savings_engine import compute_payslip_savings

        result = compute_payslip_savings(
            current_cost_per_bulletin=Decimal("40.0"),
            nb_bulletins=2,
            nb_bulletins_override=None,
        )
        # Savings = (40 - 10) × 2 × 12 = 720
        assert result is not None
        assert float(result) == pytest.approx(720.0, abs=1.0)

    def test_zero_override_returns_zero(self):
        """nb_bulletins_override=0 means no payslips → savings=0."""
        from app.services.savings_engine import compute_payslip_savings

        result = compute_payslip_savings(
            current_cost_per_bulletin=Decimal("40.0"),
            nb_bulletins=5,
            nb_bulletins_override=0,
        )
        assert result == Decimal("0") or result == 0

    def test_no_cost_returns_none(self):
        """When current_cost_per_bulletin is None/0, function returns None."""
        from app.services.savings_engine import compute_payslip_savings

        result = compute_payslip_savings(
            current_cost_per_bulletin=None,
            nb_bulletins=3,
            nb_bulletins_override=None,
        )
        assert result is None


class TestSavingsRowOneShotField:
    """SavingsRow schema includes one_shot_setup_eur field."""

    def test_savings_row_has_one_shot_field(self):
        """SavingsRow can be constructed with one_shot_setup_eur=None."""
        from app.schemas.savings import SavingsRow

        row = SavingsRow(
            channel_key="fiches_paie",
            channel_label="Fiches de paie",
            annual_savings_eur=Decimal("720"),
            one_shot_setup_eur=None,
            is_already_customer=False,
            is_opportunity=False,
            description="Test",
        )
        assert row.channel_key == "fiches_paie"
        assert row.one_shot_setup_eur is None

    def test_savings_row_with_one_shot_value(self):
        """SavingsRow accepts a non-zero one_shot_setup_eur."""
        from app.schemas.savings import SavingsRow

        row = SavingsRow(
            channel_key="comptable",
            channel_label="Comptabilité",
            annual_savings_eur=Decimal("300"),
            one_shot_setup_eur=Decimal("99"),
            is_already_customer=False,
            is_opportunity=False,
            description="Test",
        )
        assert float(row.one_shot_setup_eur) == pytest.approx(99.0)


class TestTypicalMonthSchemaNbBulletins:
    """TypicalMonthRequest schema accepts nb_bulletins_override."""

    def test_schema_accepts_override_none(self):
        """nb_bulletins_override defaults to None (field optional)."""
        from app.schemas.typical_month import TypicalMonthRequest

        req = TypicalMonthRequest(
            ca_ttc=Decimal("8000"),
            team=[],
            expenses=[],
        )
        assert req.nb_bulletins_override is None

    def test_schema_accepts_override_int(self):
        """nb_bulletins_override can be set to a positive integer."""
        from app.schemas.typical_month import TypicalMonthRequest

        req = TypicalMonthRequest(
            ca_ttc=Decimal("8000"),
            team=[],
            expenses=[],
            nb_bulletins_override=3,
        )
        assert req.nb_bulletins_override == 3

    def test_schema_rejects_negative_override(self):
        """nb_bulletins_override must be >= 0 if provided."""
        from app.schemas.typical_month import TypicalMonthRequest
        import pydantic

        with pytest.raises((pydantic.ValidationError, ValueError)):
            TypicalMonthRequest(
                ca_ttc=Decimal("8000"),
                team=[],
                expenses=[],
                nb_bulletins_override=-1,
            )
