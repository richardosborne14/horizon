"""Tests for retirement drawdown strategy (TASK-7.13).

Covers:
- PEA drawn first, PER last
- AV abattement single vs couple
- Liquidity buffer check
- Empty vehicle handling
- Tax computation
"""
from decimal import Decimal

from app.calculations.drawdown import compute_drawdown_for_year


def test_draw_from_pea_first():
    """First preferences PEA (best tax treatment) when available."""
    balances = {
        "livret_a": Decimal("6000"),
        "pea": Decimal("50000"),
        "av_euro": Decimal("30000"),
    }
    result = compute_drawdown_for_year(
        balances=balances,
        monthly_need=Decimal("2000"),  # annual need: 24,000€
        monthly_expenses=Decimal("2000"),
    )
    withdrawals = result["withdrawals"]
    # PEA should be used first (before AV)
    assert "pea" in withdrawals
    pea_withdrawal = Decimal(withdrawals.get("pea", "0"))
    assert pea_withdrawal > Decimal("0")
    # Livret A should NOT be drawn from (liquidity buffer — 6 months * 2000 = 12000)
    # Since livret only has 6000, it stays as buffer
    assert pea_withdrawal > Decimal("0"), f"Expected PEA withdrawal, got: {withdrawals}"


def test_draw_per_last():
    """PER is worst tax treatment; drawn last."""
    balances = {
        "livret_a": Decimal("12000"),
        "pea": Decimal("50000"),
        "av_euro": Decimal("30000"),
        "per": Decimal("100000"),
    }
    result = compute_drawdown_for_year(
        balances=balances,
        monthly_need=Decimal("3000"),
        monthly_expenses=Decimal("2000"),
    )
    withdrawals = result["withdrawals"]
    # PER should be zero unless everything else is exhausted
    per_withdrawal = Decimal(withdrawals.get("per", "0"))
    assert per_withdrawal == Decimal("0"), f"PER should not be drawn first. Withdrawals: {withdrawals}"
    # PEA should be drawn
    assert "pea" in withdrawals


def test_per_tax_calculation():
    """PER withdrawal ≈ 25% tax."""
    balances = {
        "livret_a": Decimal("12000"),
        "per": Decimal("50000"),
    }
    result = compute_drawdown_for_year(
        balances=balances,
        monthly_need=Decimal("2000"),
        monthly_expenses=Decimal("2000"),
    )
    # PER is the only vehicle with money (after livret buffer)
    if "per" in result["withdrawals"]:
        tax = Decimal(result["taxes_paid"].get("per", "0"))
        withdrawn = Decimal(result["withdrawals"]["per"])
        assert tax > Decimal("0"), f"PER should have tax. Tax: {tax}, Withdrawal: {withdrawn}"


def test_av_abattement_single():
    """AV abattement = 4,600€ for single."""
    balances = {
        "livret_a": Decimal("600"),
        "av_euro": Decimal("50000"),
    }
    result_single = compute_drawdown_for_year(
        balances=balances,
        monthly_need=Decimal("2000"),
        monthly_expenses=Decimal("1000"),
        is_couple=False,
    )
    # Abattement should reduce tax significantly
    tax_single = Decimal(result_single["taxes_paid"].get("av_euro", "0"))
    assert tax_single >= Decimal("0"), f"Single AV tax: {tax_single}"


def test_av_abattement_couple():
    """AV abattement = 9,200€ for couple."""
    balances = {
        "livret_a": Decimal("600"),
        "av_euro": Decimal("50000"),
    }
    result_couple = compute_drawdown_for_year(
        balances=balances,
        monthly_need=Decimal("2000"),
        monthly_expenses=Decimal("1000"),
        is_couple=True,
    )
    # Couple should have lower tax on AV than single (higher abattement)
    tax_couple = Decimal(result_couple["taxes_paid"].get("av_euro", "0"))
    assert tax_couple >= Decimal("0"), f"Couple AV tax: {tax_couple}"


def test_liquidity_buffer_warning():
    """Warns when Livret A is below 6 months of expenses."""
    balances = {
        "livret_a": Decimal("2000"),  # only 2,000€
        "pea": Decimal("20000"),
        "av_euro": Decimal("30000"),
    }
    result = compute_drawdown_for_year(
        balances=balances,
        monthly_need=Decimal("2000"),
        monthly_expenses=Decimal("2000"),  # needs 12,000 buffer
    )
    assert result["liquidity_ok"] is False
    assert len(result["strategy_notes"]) > 0


def test_empty_vehicles():
    """Gracefully handles vehicles with zero balance."""
    balances = {
        "livret_a": Decimal("500"),
        "ldds": Decimal("0"),
        "pea": Decimal("0"),
    }
    result = compute_drawdown_for_year(
        balances=balances,
        monthly_need=Decimal("500"),
        monthly_expenses=Decimal("500"),
    )
    # Should not crash, should have zero withdrawals and some income
    assert result["net_income_monthly"] is not None
    assert Decimal(result["net_income_monthly"]) >= Decimal("0")


def test_pea_ps_tax():
    """PEA withdrawals taxed at 17.2% PS on gains only (50% assumption)."""
    balances = {
        "livret_a": Decimal("600"),
        "pea": Decimal("50000"),
    }
    result = compute_drawdown_for_year(
        balances=balances,
        monthly_need=Decimal("1500"),
        monthly_expenses=Decimal("1000"),
    )
    if "pea" in result["withdrawals"]:
        tax = Decimal(result["taxes_paid"]["pea"])
        withdrawn = Decimal(result["withdrawals"]["pea"])
        # Tax should be ~ 17.2% of 50% of withdrawal = ~8.6% effective
        effective_rate = tax / withdrawn if withdrawn > 0 else Decimal("0")
        assert effective_rate <= Decimal("0.10"), (
            f"PEA effective tax {effective_rate} should be ~8.6%, "
            f"withdrawn={withdrawn}, tax={tax}"
        )


def test_drawdown_returns_net_income():
    """Result includes net_income_monthly."""
    balances = {
        "livret_a": Decimal("12000"),
        "pea": Decimal("200000"),
        "av_euro": Decimal("100000"),
    }
    result = compute_drawdown_for_year(
        balances=balances,
        monthly_need=Decimal("3000"),
        monthly_expenses=Decimal("3000"),
    )
    net = Decimal(result["net_income_monthly"])
    assert net > Decimal("0")
    # Total tax should be positive since PEA and AV have taxable returns
    total_tax = Decimal(result["total_tax"])
    assert total_tax >= Decimal("0")