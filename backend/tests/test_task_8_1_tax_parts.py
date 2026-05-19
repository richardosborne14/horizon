"""
Unit tests for TASK-8.1 — Auto-calculate quotient familial.

Covers Article 194 CGI rules:
- Couple + 0 kids = 2.0
- Couple + 1 kid = 2.5
- Couple + 2 kids = 3.0
- Couple + 3 kids = 4.0
- Single + 2 kids = 2.5
- Single + 0 kids = 1.0
- Widowed + 1 kid = 2.0
"""
from datetime import date

from app.calculations.tax_parts import compute_auto_tax_parts


def test_couple_no_kids():
    assert compute_auto_tax_parts("married", [], 2026) == 2.0
    assert compute_auto_tax_parts("pacs", [], 2026) == 2.0


def test_couple_one_kid():
    kids = [{"birth_date": date(2020, 6, 15), "is_studying": True}]
    assert compute_auto_tax_parts("married", kids, 2026) == 2.5


def test_couple_two_kids():
    kids = [
        {"birth_date": date(2018, 1, 1), "is_studying": True},
        {"birth_date": date(2020, 6, 15), "is_studying": True},
    ]
    assert compute_auto_tax_parts("married", kids, 2026) == 3.0


def test_couple_three_kids():
    """Richard's scenario: married + 3 children = 4.0 parts."""
    kids = [
        {"birth_date": date(2016, 1, 15), "is_studying": True},  # Ellie, 10
        {"birth_date": date(2018, 5, 10), "is_studying": True},  # Saoirse, 8
        {"birth_date": date(2025, 1, 1), "is_studying": True},  # Romy, 1
    ]
    assert compute_auto_tax_parts("married", kids, 2026) == 4.0


def test_single_no_kids():
    assert compute_auto_tax_parts("single", [], 2026) == 1.0
    assert compute_auto_tax_parts("divorced", [], 2026) == 1.0
    assert compute_auto_tax_parts("widowed", [], 2026) == 1.0


def test_single_two_kids():
    """Single parent + 2 kids = 2.5 parts (1.0 base + 1.0 first kid + 0.5 second)."""
    kids = [
        {"birth_date": date(2018, 1, 1), "is_studying": True},
        {"birth_date": date(2020, 6, 15), "is_studying": True},
    ]
    assert compute_auto_tax_parts("single", kids, 2026) == 2.5


def test_single_one_kid():
    kids = [{"birth_date": date(2020, 6, 15), "is_studying": True}]
    assert compute_auto_tax_parts("single", kids, 2026) == 2.0


def test_widowed_one_kid():
    kids = [{"birth_date": date(2020, 6, 15), "is_studying": True}]
    assert compute_auto_tax_parts("widowed", kids, 2026) == 2.0


def test_kid_over_18_not_studying_not_counted():
    """20-year-old not studying should not count as dependent."""
    kids = [{"birth_date": date(2006, 1, 1), "is_studying": False}]
    assert compute_auto_tax_parts("married", kids, 2026) == 2.0


def test_kid_under_25_studying_counted():
    """22-year-old studying should still count as dependent."""
    kids = [{"birth_date": date(2004, 1, 1), "is_studying": True}]
    assert compute_auto_tax_parts("married", kids, 2026) == 2.5


def test_kid_over_25_studying_not_counted():
    """26-year-old should not count, even if studying."""
    kids = [{"birth_date": date(2000, 1, 1), "is_studying": True}]
    assert compute_auto_tax_parts("married", kids, 2026) == 2.0


def test_mixed_age_children():
    """Only eligible children count toward parts."""
    kids = [
        {"birth_date": date(2016, 1, 15), "is_studying": True},  # 10 — eligible
        {"birth_date": date(2004, 1, 1), "is_studying": True},  # 22 — eligible
        {"birth_date": date(2005, 8, 15), "is_studying": False},  # 20 — NOT eligible
    ]
    # Couple + 2 eligible kids = 3.0
    assert compute_auto_tax_parts("married", kids, 2026) == 3.0


def test_null_birth_date_skipped():
    kids = [{"birth_date": None, "is_studying": True}]
    assert compute_auto_tax_parts("married", kids, 2026) == 2.0


def test_unknown_marital_status():
    assert compute_auto_tax_parts("unknown_status", [], 2026) == 1.0


def test_couple_four_kids():
    """Couple + 4 kids = 2.0 + 0.5 + 0.5 + 1.0 + 1.0 = 5.0."""
    kids = [
        {"birth_date": date(2016, 1, 1), "is_studying": True},
        {"birth_date": date(2018, 1, 1), "is_studying": True},
        {"birth_date": date(2020, 1, 1), "is_studying": True},
        {"birth_date": date(2022, 1, 1), "is_studying": True},
    ]
    assert compute_auto_tax_parts("married", kids, 2026) == 5.0