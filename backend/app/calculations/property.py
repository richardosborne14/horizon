"""Property appreciation and downsizing model (TASK-7.16).

Simple compound appreciation with optional downsizing event.
All monetary values are Decimal for financial precision.
"""
from decimal import Decimal


def project_property_value(
    current_value: Decimal,
    appreciation_rate: Decimal,
    years: int,
) -> Decimal:
    """Project property value with compound appreciation.

    Args:
        current_value: Current estimated property value in €.
        appreciation_rate: Annual appreciation rate (e.g. 0.02 for 2%).
        years: Number of years to project forward.

    Returns:
        Projected property value in €.
    """
    return (current_value * (Decimal("1") + appreciation_rate) ** years).quantize(Decimal("0.01"))


def compute_downsize_capital(
    property_value_at_downsize: Decimal,
    replacement_value: Decimal,
    selling_costs_pct: Decimal = Decimal("0.08"),
    buying_costs_pct: Decimal = Decimal("0.08"),
) -> Decimal:
    """Compute freed capital from downsizing.

    Freed capital = sale price - selling costs - replacement price - buying costs.
    Hardcoded 8% for both selling (agency + notaire) and buying (notaire) as
    simplified defaults per TASK-7.16 spec.

    Args:
        property_value_at_downsize: Property value in the downsizing year.
        replacement_value: Value of replacement property.
        selling_costs_pct: Selling costs as decimal (default 0.08).
        buying_costs_pct: Buying costs on replacement (default 0.08).

    Returns:
        Freed capital in € (minimum 0 — negative means buying more expensive,
        which is a cash outflow, not freed capital).
    """
    net_sale = property_value_at_downsize * (Decimal("1") - selling_costs_pct)
    gross_purchase = replacement_value * (Decimal("1") + buying_costs_pct)
    freed = net_sale - gross_purchase
    return max(Decimal("0"), freed).quantize(Decimal("0.01"))