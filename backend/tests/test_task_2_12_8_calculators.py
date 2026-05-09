"""
Regression tests for TASK-2.12.8: Mes Prix + Calculators — Eric corrections.

The frontend changes (PaliersConfigModal extraction, "Configurer les paliers"
button, deficit-carry "plus" expansion, year-dropdown removal, inline editable
jours/CA cells) don't change backend behaviour. These tests pin the backend
contracts the modal *depends on* so a future refactor can't silently break them:

  1. ERIC_DEFAULT_BANDS still has the canonical 9 tiers Eric specified
     (the modal pre-fills these exact values per TASK-2.12.8 §13).
  2. The custom-band save round-trip via `materialise_bands` + `bands_to_snapshot`
     preserves rates exactly (the modal sends bands as {threshold, rate} pairs).
  3. `compute_prime_month` still applies deficit carry-forward correctly with the
     default bands (the in-page live preview mirrors this; if backend drifts the
     modal's preview will lie about per-month bonuses).

Run with:
  docker compose exec -w /app backend python -m pytest tests/test_task_2_12_8_calculators.py -v
"""

from decimal import Decimal

import pytest

from app.calculations.primes import (
    Band,
    ERIC_DEFAULT_BANDS,
    bands_to_snapshot,
    compute_bonus,
    compute_prime_month,
    materialise_bands,
    snapshot_to_bands,
    validate_bands,
)


# ── Item 13: Eric default bands (modal pre-fill) ──────────────────────────────


class TestEricDefaultsForModal:
    """The modal pre-fills these exact values when no custom barème is saved.
    Drift here would silently change every existing employee's primes, so we
    pin them explicitly per the spec table in TASK-2.12.8 §13.
    """

    EXPECTED = [
        # (from, to, rate)  — to=None means "et au-delà"
        (Decimal("0"), Decimal("600"), Decimal("0.10")),
        (Decimal("600"), Decimal("900"), Decimal("0.12")),
        (Decimal("900"), Decimal("1200"), Decimal("0.14")),
        (Decimal("1200"), Decimal("1500"), Decimal("0.16")),
        (Decimal("1500"), Decimal("1800"), Decimal("0.18")),
        (Decimal("1800"), Decimal("2100"), Decimal("0.20")),
        (Decimal("2100"), Decimal("2400"), Decimal("0.22")),
        (Decimal("2400"), Decimal("2700"), Decimal("0.24")),
        (Decimal("2700"), None, Decimal("0.28")),
    ]

    def test_count_is_nine(self):
        assert len(ERIC_DEFAULT_BANDS) == 9

    def test_bands_match_spec_exactly(self):
        for i, (from_amt, to_amt, rate) in enumerate(self.EXPECTED):
            band = ERIC_DEFAULT_BANDS[i]
            assert band.from_amount == from_amt, f"Band {i} from_amount drift"
            assert band.to_amount == to_amt, f"Band {i} to_amount drift"
            # Compare rates with Decimal precision, not float
            assert Decimal(str(band.rate)) == rate, f"Band {i} rate drift"

    def test_validate_passes(self):
        validate_bands(list(ERIC_DEFAULT_BANDS))


# ── Custom barème round-trip (modal "Enregistrer ce barème") ──────────────────


class TestCustomBaremeRoundTrip:
    """The modal saves a custom barème by POSTing
        {model_type: 'custom', custom_bands: [{threshold, rate}, …]}
    The backend re-materialises via `materialise_bands(model_type='custom', …)`
    and persists the result via `bands_to_snapshot()` into the
    `bands_snapshot` JSONB column. The next page load reads back via
    `snapshot_to_bands`. A round-trip must preserve exactly what the user typed.
    """

    def test_custom_3_bands_roundtrip(self):
        # User-edited bands as the modal would send them — note the API uses
        # {threshold, rate}, where threshold is the upper bound of the band.
        # The last entry's threshold is implicitly +∞ (terminal unbounded band).
        custom_bands = [
            {"threshold": "500", "rate": "0.08"},
            {"threshold": "1500", "rate": "0.15"},
            {"threshold": "9999", "rate": "0.30"},  # last → unbounded
        ]
        materialised = materialise_bands(
            model_type="custom",
            custom_bands=custom_bands,
        )
        validate_bands(materialised)
        # Snapshot for storage in calculation_history payload
        snapshot = bands_to_snapshot(materialised)
        # Round-trip back into Band objects
        restored = snapshot_to_bands(snapshot)

        assert len(restored) == 3
        assert restored[0].from_amount == Decimal("0")
        assert restored[0].to_amount == Decimal("500")
        assert restored[0].rate == Decimal("0.08")
        assert restored[1].from_amount == Decimal("500")
        assert restored[1].to_amount == Decimal("1500")
        # Last band is unbounded regardless of the threshold sent
        assert restored[2].to_amount is None
        assert restored[2].rate == Decimal("0.30")

    def test_compute_bonus_with_custom_bands_matches_modal_preview(self):
        # The page's `computeBonusPreview` JS function must match this
        # backend computation exactly — otherwise the live "Bonus calculé"
        # column lies and the user is surprised on save.
        bands = materialise_bands(
            model_type="custom",
            custom_bands=[
                {"threshold": "500", "rate": "0.10"},
                {"threshold": "9999", "rate": "0.20"},  # last → unbounded
            ],
        )
        # Excess = 800 → 500 × 10% + 300 × 20% = 50 + 60 = 110 €
        result = compute_bonus(Decimal("800"), bands)
        assert result.total_prime == Decimal("110.00")


# ── Deficit carry-forward (item 11 "plus" explanation example) ────────────────


class TestDeficitCarryForwardExample:
    """The "plus" expandable in the primes page (item 11) shows this example:
        Objectif janvier 5 000 € TTC, réalisé 4 500 € → -500 €.
        Objectif février 5 000 € + 500 € (déficit antérieur) = 5 500 €.
    The Svelte live-preview computes the carry-forward client-side; the
    backend does the same in compute_prime_month. They MUST stay in sync.

    NB: the backend takes (objectif_jour, days_worked) and computes
    objectif_initial = jour × days. Using 250 €/jour × 20 jours = 5 000 €
    matches Eric's example exactly.
    """

    def test_january_deficit_carries_to_february_target(self):
        bands = list(ERIC_DEFAULT_BANDS)
        objectif_jour = Decimal("250")  # 250 × 20 = 5000
        days = 20

        # January: objectif_initial 5000, réalisé 4500 → écart -500, prime 0.
        jan = compute_prime_month(
            month=1,
            days_worked=days,
            resultat=Decimal("4500"),
            objectif_jour=objectif_jour,
            deficit_anterieur=Decimal("0"),
            bands=bands,
        )
        assert jan.objectif_initial == Decimal("5000.00")
        assert jan.objectif_final == Decimal("5000.00")
        assert jan.prime == Decimal("0")
        assert jan.ecart == Decimal("-500.00")

        # The frontend converts a negative écart into the next month's
        # deficit_anterieur (always >= 0). The Svelte page does:
        #   prevDeficit = ecart < 0 ? -ecart : 0
        deficit_carried = -jan.ecart if jan.ecart < 0 else Decimal("0")
        assert deficit_carried == Decimal("500.00")

        # February: objectif_initial 5000 + 500 carried = effective target 5500
        feb = compute_prime_month(
            month=2,
            days_worked=days,
            resultat=Decimal("5500"),  # exactly hitting the inflated target
            objectif_jour=objectif_jour,
            deficit_anterieur=deficit_carried,
            bands=bands,
        )
        assert feb.objectif_initial == Decimal("5000.00")
        assert feb.objectif_final == Decimal("5500.00")
        assert feb.ecart == Decimal("0.00")
        assert feb.prime == Decimal("0")
