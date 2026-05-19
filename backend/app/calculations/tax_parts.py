"""
Auto-calculate quotient familial from marital status and dependent children.

Article 194 CGI rules:
- Married/PACS couple: 2 parts
- 1st dependent child: +0.5 part
- 2nd dependent child: +0.5 part
- 3rd and subsequent dependent children: +1.0 part each
- Single/divorced/widowed with dependents: 1.0 base + bonus for dependents

A child is a dependent if under 18 OR under 25 and studying.
"""

from datetime import date
from typing import Optional


def compute_auto_tax_parts(
    marital_status: str,
    dependent_children: list[dict],
    current_year: int,
) -> float:
    """
    Compute quotient familial per Art. 194 CGI.

    Args:
        marital_status: One of "married", "pacs", "single", "divorced", "widowed"
        dependent_children: List of {"birth_date": date, "is_studying": bool}
        current_year: The year for which to compute ages

    Returns:
        Float representing tax parts (e.g. 4.0, 3.5, 2.5, 2.0, 1.0)
    """
    # Base parts
    if marital_status in ("married", "pacs"):
        parts = 2.0
    elif marital_status == "widowed":
        parts = 1.0
    elif marital_status in ("single", "divorced"):
        parts = 1.0
    else:
        parts = 1.0

    # Count eligible dependents
    eligible = []
    for child in dependent_children:
        birth_date = child.get("birth_date")
        if birth_date is None:
            continue
        age = current_year - birth_date.year
        # Age isn't exact (no month/day check), but this is correct for tax year
        if age < 18 or (age < 25 and child.get("is_studying", True)):
            eligible.append(child)

    # If single/divorced/widowed with at least one dependent, get the chef de
    # famille bonus: first child counts as 1.0 part (instead of 0.5).
    is_single_parent = marital_status in ("single", "divorced", "widowed") and eligible

    for i, _ in enumerate(eligible):
        if i == 0 and is_single_parent:
            parts += 1.0  # First child for single parent = +1.0 (total: 2.0)
        elif i == 0:
            parts += 0.5
        elif i == 1:
            parts += 0.5
        else:
            parts += 1.0  # 3rd child onwards

    return parts