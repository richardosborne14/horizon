"""
Unit tests for tax calculation engine (Task 3.1).

Pure calculation tests — no DB required. Run with:
  docker compose exec -w /app backend python -m pytest tests/test_task_3_1_taxes.py -v
"""

import pytest
from decimal import Decimal

from app.calculations.taxes import (
    compute_taxes,
    _compute_ir_progressive,
    _compute_is,
    _compute_cfe,
    DEFAULT_RATES,
)


# ── AE Auto-entrepreneur ────────────────────────────────────────────────────────

class TestAEAutoEntrepreneur:
    """Test auto-entrepreneur path (auto_micro)."""

    def test_ae_urssaf_normal_rate(self) -> None:
        """AE BIC Services, no ACRE, no VL — standard URSSAF 21.2%."""
        result = compute_taxes(
            business_type="auto_micro",
            ca_annuel=Decimal("60000"),
            acre=False,
            versement_liberatoire=False,
            nb_parts_ir=Decimal("1"),
        )
        assert result.is_auto is True
        assert result.has_tva is False
        assert len(result.cotisations) >= 2  # URSSAF + CFE
        urssaf = next(i for i in result.cotisations if "URSSAF" in i.label)
        assert urssaf.rate == Decimal("0.2120")
        assert urssaf.amount == Decimal("12720.00")  # 60000 × 0.212

    def test_ae_urssaf_standard_rate_amount(self) -> None:
        """URSSAF = CA × 21.2%."""
        result = compute_taxes(
            business_type="auto_micro",
            ca_annuel=Decimal("37500"),
            acre=False,
            versement_liberatoire=False,
        )
        urssaf = next(i for i in result.cotisations if "URSSAF" in i.label)
        assert urssaf.amount == Decimal("7950.00")  # 37500 × 0.212

    def test_ae_acre_avant_juillet_50pct(self) -> None:
        """ACRE before July 2026: URSSAF effective rate = 10.6%."""
        result = compute_taxes(
            business_type="auto_micro",
            ca_annuel=Decimal("60000"),
            acre=True,
            acre_apres_juillet_2026=False,
            versement_liberatoire=False,
        )
        urssaf = next(i for i in result.cotisations if "URSSAF" in i.label)
        assert urssaf.rate == Decimal("0.1060")  # 21.2% × 50%
        assert urssaf.amount == Decimal("6360.00")  # 60000 × 0.106

    def test_ae_acre_apres_juillet_25pct(self) -> None:
        """ACRE from July 2026: URSSAF effective rate = 15.9%."""
        result = compute_taxes(
            business_type="auto_micro",
            ca_annuel=Decimal("60000"),
            acre=True,
            acre_apres_juillet_2026=True,
            versement_liberatoire=False,
        )
        urssaf = next(i for i in result.cotisations if "URSSAF" in i.label)
        assert urssaf.rate == Decimal("0.1590")  # 21.2% × 25%
        assert urssaf.amount == Decimal("9540.00")  # 60000 × 0.159

    def test_ae_versement_liberatoire(self) -> None:
        """AE with VL: IR replaced by 1.7% flat rate."""
        result = compute_taxes(
            business_type="auto_micro",
            ca_annuel=Decimal("50000"),
            acre=False,
            versement_liberatoire=True,
        )
        assert any("libératoire" in i.label.lower() for i in result.impots)
        vl = next(i for i in result.impots if "libératoire" in i.label.lower())
        assert vl.rate == Decimal("0.0170")
        assert vl.amount == Decimal("850.00")  # 50000 × 0.017

    def test_ae_vl_ir_not_present(self) -> None:
        """With VL, no standard IR line."""
        result = compute_taxes(
            business_type="auto_micro",
            ca_annuel=Decimal("50000"),
            acre=False,
            versement_liberatoire=True,
        )
        assert not any("Impôt sur le revenu" in i.label for i in result.impots)

    def test_ae_tva_threshold_warning_near(self) -> None:
        """CA ≥ 90% of 37500 threshold triggers warning."""
        result = compute_taxes(
            business_type="auto_micro",
            ca_annuel=Decimal("35000"),  # 35000 / 37500 = 93.3% → warning
        )
        assert result.is_ae_near_tva_threshold is True

    def test_ae_tva_threshold_warning_below(self) -> None:
        """CA well below threshold: no warning."""
        result = compute_taxes(
            business_type="auto_micro",
            ca_annuel=Decimal("20000"),
        )
        assert result.is_ae_near_tva_threshold is False

    def test_ae_net_monthly(self) -> None:
        """Net monthly = (CA - total_taxes) / 12."""
        result = compute_taxes(
            business_type="auto_micro",
            ca_annuel=Decimal("60000"),
            acre=False,
            versement_liberatoire=False,
        )
        # 60000 - 12720 (URSSAF) - ~200 (CFE) - ~8000 (IR est) ≈ 39080
        assert result.net_annual < result.ca_annuel
        from decimal import ROUND_HALF_UP
        assert result.net_monthly == (result.net_annual / Decimal("12")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def test_ae_zero_ca(self) -> None:
        """Zero CA: all taxes = 0."""
        result = compute_taxes(
            business_type="auto_micro",
            ca_annuel=Decimal("0"),
        )
        # CFE minimum of 50 applies even at 0 CA (real rule)
        assert result.total_taxes == Decimal("50")
        assert result.net_annual == Decimal("-50")


# ── CFE ─────────────────────────────────────────────────────────────────────────

class TestCFE:
    """Test CFE calculation across CA brackets."""

    def test_cfe_below_min_ca(self) -> None:
        """CA below min_ca: fixed minimum CFE."""
        cfe = _compute_cfe(Decimal("2000"), DEFAULT_RATES)
        assert cfe.amount == DEFAULT_RATES["cfe_min_amount"]  # €50

    def test_cfe_above_max_ca(self) -> None:
        """CA above max_ca: capped CFE."""
        cfe = _compute_cfe(Decimal("200000"), DEFAULT_RATES)
        assert cfe.amount == DEFAULT_RATES["cfe_max_amount"]  # €1500

    def test_cfe_mid_bracket_linear_interpolation(self) -> None:
        """CA mid-range: linear interpolation."""
        # Midpoint of 5000-100000 range is 52500
        cfe = _compute_cfe(Decimal("52500"), DEFAULT_RATES)
        # Expected: 50 + (1500-50) * (52500-5000)/(100000-5000) = 50 + 1450 * 0.5473 = 843.6
        expected = Decimal("50") + (Decimal("1500") - Decimal("50")) * Decimal("47500") / Decimal("95000")
        assert cfe.amount == expected.quantize(Decimal("0.01"))


# ── IS ─────────────────────────────────────────────────────────────────────────

class TestIS:
    """Test IS calculation (SASU path)."""

    def test_is_benefice_zero(self) -> None:
        """Zero or negative benefit: IS = 0."""
        items = _compute_is(Decimal("0"), DEFAULT_RATES)
        assert items[0].amount == Decimal("0")

    def test_is_below_seuil_taux_reduit(self) -> None:
        """Benefit ≤ 42500: 15% flat."""
        items = _compute_is(Decimal("30000"), DEFAULT_RATES)
        assert len(items) == 1
        assert items[0].amount == Decimal("4500.00")  # 30000 × 0.15
        assert "15%" in items[0].label

    def test_is_above_seuil_split_rates(self) -> None:
        """Benefit > 42500: 15% on first 42500, 25% on rest."""
        items = _compute_is(Decimal("60000"), DEFAULT_RATES)
        assert len(items) == 2
        # First 42500 at 15%
        assert items[0].amount == Decimal("6375.00")
        # Remaining 17500 at 25%
        assert items[1].amount == Decimal("4375.00")
        assert items[1].amount == Decimal("17500.00") * Decimal("0.25")


# ── IR Progressive ─────────────────────────────────────────────────────────────

class TestIRProgressive:
    """Test progressive IR with family quotient."""

    def test_ir_zero_revenu(self) -> None:
        """Zero taxable income: IR = 0."""
        ir, details = _compute_ir_progressive(Decimal("0"), Decimal("1"), DEFAULT_RATES)
        assert ir == Decimal("0")
        assert details == []

    def test_ir_tranche_0_only(self) -> None:
        """Income in first bracket (0%): IR = 0."""
        ir, details = _compute_ir_progressive(Decimal("10000"), Decimal("1"), DEFAULT_RATES)
        assert ir == Decimal("0")

    def test_ir_one_part_single(self) -> None:
        """Single person, 1 part, income in 11% bracket."""
        # 20000 taxable — first 11600 at 0%, rest 8400 at 11% = 924
        ir, details = _compute_ir_progressive(Decimal("20000"), Decimal("1"), DEFAULT_RATES)
        assert ir == Decimal("924.00")
        assert len(details) == 2

    def test_ir_two_parts_couple(self) -> None:
        """Married couple, 2 parts: quotient halved, IR lower."""
        revenu = Decimal("40000")
        ir_1part, _ = _compute_ir_progressive(revenu, Decimal("1"), DEFAULT_RATES)
        ir_2parts, _ = _compute_ir_progressive(revenu, Decimal("2"), DEFAULT_RATES)
        # 2 parts → quotient = 20000 → lower IR
        assert ir_2parts < ir_1part
        # IR with 2 parts should be roughly half of 1 part for same income
        assert ir_2parts < ir_1part * Decimal("0.8")


# ── Non-AE structures ─────────────────────────────────────────────────────────

class TestNonAE:
    """Test EIRL, EURL, SARL (IR path) and SASU (IS path)."""

    def test_eurl_has_tva(self) -> None:
        """Non-AE structures are subject to TVA."""
        result = compute_taxes(
            business_type="eurl",
            ca_annuel=Decimal("80000"),
            salaire_dirigeant=Decimal("24000"),
        )
        assert result.has_tva is True
        assert result.is_auto is False

    def test_sasu_has_tva(self) -> None:
        """SASU is subject to TVA."""
        result = compute_taxes(
            business_type="sasu",
            ca_annuel=Decimal("80000"),
            salaire_dirigeant=Decimal("24000"),
        )
        assert result.has_tva is True

    def test_sasu_is_path(self) -> None:
        """SASU uses IS not IR."""
        result = compute_taxes(
            business_type="sasu",
            ca_annuel=Decimal("60000"),
            salaire_dirigeant=Decimal("24000"),
        )
        assert any("Sociétés" in i.label or "IS" in i.label for i in result.impots)
        assert not any("Impôt sur le revenu" in i.label for i in result.impots)

    def test_eurl_ir_path(self) -> None:
        """EURL uses IR not IS."""
        result = compute_taxes(
            business_type="eurl",
            ca_annuel=Decimal("60000"),
            salaire_dirigeant=Decimal("24000"),
        )
        assert any("Impôt sur le revenu" in i.label for i in result.impots)
        assert not any("Sociétés" in i.label for i in result.impots)

    def test_non_ae_cfe_present(self) -> None:
        """CFE is calculated for all business types."""
        result_auto = compute_taxes(business_type="auto_micro", ca_annuel=Decimal("50000"))
        result_eurl = compute_taxes(business_type="eurl", ca_annuel=Decimal("50000"))
        result_sasu = compute_taxes(business_type="sasu", ca_annuel=Decimal("50000"))
        assert result_auto.cfe > Decimal("0")
        assert result_eurl.cfe > Decimal("0")
        assert result_sasu.cfe > Decimal("0")


# ── Validation ─────────────────────────────────────────────────────────────────

class TestValidation:
    """Input validation."""

    def test_negative_ca_raises(self) -> None:
        """Negative CA raises ValueError."""
        with pytest.raises(ValueError, match="ca_annuel"):
            compute_taxes(business_type="auto_micro", ca_annuel=Decimal("-1000"))

    def test_zero_nb_parts_raises(self) -> None:
        """Zero parts raises ValueError."""
        with pytest.raises(ValueError, match="nb_parts_ir"):
            compute_taxes(business_type="auto_micro", ca_annuel=Decimal("50000"), nb_parts_ir=Decimal("0"))


# ── Effective tax rate ─────────────────────────────────────────────────────────

class TestEffectiveRate:
    """Effective tax rate calculation."""

    def test_effective_rate_auto_micro(self) -> None:
        """Effective rate = total_taxes / ca_annuel."""
        result = compute_taxes(
            business_type="auto_micro",
            ca_annuel=Decimal("60000"),
            acre=False,
            versement_liberatoire=False,
        )
        expected = result.total_taxes / Decimal("60000")
        assert result.effective_tax_rate == expected.quantize(Decimal("0.0001"))

    def test_effective_rate_zero_ca(self) -> None:
        """Zero CA: effective rate = 0."""
        result = compute_taxes(
            business_type="auto_micro",
            ca_annuel=Decimal("0"),
        )
        assert result.effective_tax_rate == Decimal("0")
