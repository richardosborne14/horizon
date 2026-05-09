"""
Expense calculation helpers — inflation preview and projection utilities.

Expenses are stored as a flat JSONB dict on UserProfile with 12 categories.
The projection engine inflates these forward using cost-of-living rates.
This module provides the inflation preview for the frontend Expenses section.
"""

from decimal import Decimal


def preview_inflation(
    monthly_total: Decimal,
    scales: dict,
    horizons: list[int],
) -> dict:
    """Compute an inflation preview grid for the user's current expenses.

    Args:
        monthly_total: The user's current total monthly expenses.
        scales: The INFLATION_SCALES dict from constants.py.
        horizons: List of year horizons (e.g. [5, 10, 20, 30]).

    Returns:
        Dict mapping scale_key → {"{horizon}": str(amount)} for each horizon.
        Amounts are inflated monthly totals serialised as strings.

    Example:
        >>> preview_inflation(Decimal("800"), scales, [10])
        {"moderate": {"10": "1074.81"}}
        # 800 * (1.03)^10 = 1074.81
    """
    result = {}

    for scale_key, scale in scales.items():
        cost_living_rate = scale["cost_living"]
        scale_result = {}

        for horizon in horizons:
            inflated = monthly_total * (
                (Decimal("1") + cost_living_rate) ** horizon
            )
            scale_result[str(horizon)] = str(
                inflated.quantize(Decimal("0.01"))
            )

        result[scale_key] = scale_result

    return result