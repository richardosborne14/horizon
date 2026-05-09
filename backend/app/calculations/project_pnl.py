"""
Project P&L computation — investment project snapshot analysis.

Computes a mini income statement for investment-type projects:
gross annual → tax → net annual → yield % → monthly net.

The P&L is computed on every read (not stored) so changes to income,
expenses, or tax rate immediately reflect in the result.

Used by the projects router to enrich investment project responses.
The projection engine (Sprint 4) will use a more nuanced version
with growth rates and inflation adjustments.
"""

from decimal import Decimal

from app.schemas.project import ProjectPNL


def compute_pnl(
    annual_income: Decimal,
    annual_expenses: Decimal,
    tax_rate: Decimal,
    purchase_cost: Decimal,
) -> ProjectPNL:
    """Compute the P&L snapshot for an investment project.

    Args:
        annual_income: Gross annual revenue (EUR)
        annual_expenses: Annual operating costs (EUR)
        tax_rate: Effective tax rate (0.0 to 1.0)
        purchase_cost: Total acquisition cost (EUR)

    Returns:
        ProjectPNL with gross, tax, net, yield, and monthly net.

    Edge cases:
        - If expenses > income, gross is negative, tax = 0 (no negative tax)
        - If purchase_cost == 0, yield_pct is None
    """
    gross = annual_income - annual_expenses

    # Tax only applies to positive gross (no negative tax refund)
    if gross > Decimal("0"):
        tax = gross * tax_rate
    else:
        tax = Decimal("0")

    net = gross - tax

    if purchase_cost > Decimal("0"):
        yield_pct = net / purchase_cost
    else:
        yield_pct = None

    monthly_net = net / Decimal("12")

    return ProjectPNL(
        gross_annual=gross.quantize(Decimal("0.01")),
        tax_amount=tax.quantize(Decimal("0.01")),
        net_annual=net.quantize(Decimal("0.01")),
        yield_pct=(
            yield_pct.quantize(Decimal("0.000001"))
            if yield_pct is not None
            else None
        ),
        monthly_net=monthly_net.quantize(Decimal("0.01")),
    )
