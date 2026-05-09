"""
Unit tests for the Task 2.9.4 primes calculation engine.

Tests cover:
  - compute_bonus() — pure function, all three model types
  - materialise_bands() — preset_eric / tranches_fixes / custom
  - validate_bands() — error conditions
  - bands_to_snapshot() / snapshot_to_bands() — round-trip
  - Deficit carry-forward via compute_prime_month()
  - Backward compatibility: calculate_tiered_prime() unchanged

All tests are pure (no DB, no HTTP).  Run with:
  docker compose exec -w /app backend python -m pytest tests/test_task_2_9_4_primes_engine.py -v
"""

import pytest
from decimal import Decimal

from app.calculations.primes import (
    # new API
    Band,
    BonusBandDetail,
    BonusBreakdown,
    ERIC_DEFAULT_BANDS,
    compute_bonus,
    materialise_bands,
    validate_bands,
    bands_to_snapshot,
    snapshot_to_bands,
    # legacy API
    PrimeTier,
    DEFAULT_PRIME_TIERS,
    calculate_tiered_prime,
    compute_prime_month,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def eric_bands() -> list[Band]:
    """Fresh copy of Eric's default 9-band table."""
    return ERIC_DEFAULT_BANDS[:]


@pytest.fixture
def tranches_3_bands() -> list[Band]:
    """tranches_fixes: width=500, rates=[0.10, 0.15, 0.20], 4 explicit + terminal."""
    return materialise_bands(
        model_type="tranches_fixes",
        tranche_width=Decimal("500"),
        rate_sequence=[0.10, 0.15, 0.20],
        n_tranches=4,
    )


# ── ERIC_DEFAULT_BANDS structure ───────────────────────────────────────────────

class TestEricDefaultBands:
    def test_has_nine_bands(self, eric_bands):
        assert len(eric_bands) == 9

    def test_starts_at_zero(self, eric_bands):
        assert eric_bands[0].from_amount == Decimal("0")

    def test_last_band_is_unbounded(self, eric_bands):
        assert eric_bands[-1].to_amount is None

    def test_bands_are_contiguous(self, eric_bands):
        """Each band's from must equal the previous band's to."""
        for i in range(1, len(eric_bands)):
            assert eric_bands[i].from_amount == eric_bands[i - 1].to_amount

    def test_rates_ascending(self, eric_bands):
        rates = [b.rate for b in eric_bands]
        assert rates == sorted(rates)

    def test_validate_passes(self, eric_bands):
        validate_bands(eric_bands)  # must not raise


# ── compute_bonus — Eric's tiers ───────────────────────────────────────────────

class TestComputeBonusEric:
    def test_zero_excess_returns_zero(self, eric_bands):
        result = compute_bonus(Decimal("0"), eric_bands)
        assert result.total_prime == Decimal("0")
        assert result.bands_used == []

    def test_negative_excess_returns_zero(self, eric_bands):
        result = compute_bonus(Decimal("-50"), eric_bands)
        assert result.total_prime == Decimal("0")

    def test_known_1145_91(self, eric_bands):
        """
        Eric's worked example from CALCULATION_FORMULAS.md:
          Band 0-600    @ 10% → 600.00 × 0.10 = 60.00
          Band 600-900  @ 12% → 300.00 × 0.12 = 36.00
          Band 900-1200 @ 14% → 245.91 × 0.14 = 34.43
          total = 130.43
        """
        result = compute_bonus(Decimal("1145.91"), eric_bands)
        assert result.total_prime == Decimal("130.43")
        assert len(result.bands_used) == 3
        assert result.bands_used[0].prime_amount == Decimal("60.00")
        assert result.bands_used[1].prime_amount == Decimal("36.00")
        assert result.bands_used[2].prime_amount == Decimal("34.43")

    def test_exact_band_boundary(self, eric_bands):
        """Excess exactly at 600 fills the first band, nothing more."""
        result = compute_bonus(Decimal("600"), eric_bands)
        assert result.total_prime == Decimal("60.00")
        assert len(result.bands_used) == 1

    def test_last_band_repeats_to_infinity(self, eric_bands):
        """
        Excess of 4000 exceeds 2700 (last explicit threshold).
        Extra 1300 beyond 2700 gets the final band rate (0.28).
          0-600    @ 10% = 60.00
          600-900  @ 12% = 36.00
          900-1200 @ 14% = 42.00
          1200-1500@ 16% = 48.00
          1500-1800@ 18% = 54.00
          1800-2100@ 20% = 60.00
          2100-2400@ 22% = 66.00
          2400-2700@ 24% = 72.00
          2700-4000@ 28% = 364.00
          total = 802.00
        """
        result = compute_bonus(Decimal("4000"), eric_bands)
        assert result.total_prime == Decimal("802.00")
        # Last band has to_amount=None
        assert result.bands_used[-1].to_amount is None

    def test_small_excess_stays_in_first_band(self, eric_bands):
        """100 @ 10% = 10.00."""
        result = compute_bonus(Decimal("100"), eric_bands)
        assert result.total_prime == Decimal("10.00")
        assert len(result.bands_used) == 1


# ── compute_bonus — tranches_fixes ─────────────────────────────────────────────

class TestComputeBonusTranches:
    def test_tranches_correct_structure(self, tranches_3_bands):
        """n_tranches=4 → 4 explicit + 1 terminal = 5 bands."""
        assert len(tranches_3_bands) == 5
        assert tranches_3_bands[-1].to_amount is None

    def test_excess_1600(self, tranches_3_bands):
        """
        width=500, rates=[0.10,0.15,0.20], excess=1600:
          0-500    @ 10% = 50.00
          500-1000 @ 15% = 75.00
          1000-1500@ 20% = 100.00
          1500-2000@ 20% = 100 × 0.20 = 20.00  (last rate repeats)
          total = 245.00
        """
        result = compute_bonus(Decimal("1600"), tranches_3_bands)
        assert result.total_prime == Decimal("245.00")
        assert len(result.bands_used) == 4

    def test_excess_within_first_band(self, tranches_3_bands):
        """300 is inside [0, 500] at 10% → 30.00."""
        result = compute_bonus(Decimal("300"), tranches_3_bands)
        assert result.total_prime == Decimal("30.00")

    def test_excess_fills_two_bands(self, tranches_3_bands):
        """700 spans first two bands: 500×0.10 + 200×0.15 = 50+30 = 80.00."""
        result = compute_bonus(Decimal("700"), tranches_3_bands)
        assert result.total_prime == Decimal("80.00")


# ── compute_bonus — custom ─────────────────────────────────────────────────────

class TestComputeBonusCustom:
    def _custom_bands(self) -> list[Band]:
        """Two-band custom schedule: 0-1000 @ 10%, 1000+ @ 20%."""
        return materialise_bands(
            model_type="custom",
            custom_bands=[
                {"threshold": 1000, "rate": 0.10},
                {"threshold": 9999, "rate": 0.20},   # last entry → unbounded
            ],
        )

    def test_within_first_band(self):
        bands = self._custom_bands()
        result = compute_bonus(Decimal("500"), bands)
        assert result.total_prime == Decimal("50.00")

    def test_spanning_both_bands(self):
        """1500: first 1000 @ 10% = 100, last 500 @ 20% = 100 → 200."""
        bands = self._custom_bands()
        result = compute_bonus(Decimal("1500"), bands)
        assert result.total_prime == Decimal("200.00")


# ── materialise_bands ──────────────────────────────────────────────────────────

class TestMaterialiseBands:
    def test_preset_eric_returns_9_bands(self):
        bands = materialise_bands("preset_eric")
        assert len(bands) == 9
        assert bands[-1].to_amount is None

    def test_tranches_fixes_n_plus_one(self):
        bands = materialise_bands(
            model_type="tranches_fixes",
            tranche_width=Decimal("300"),
            rate_sequence=[0.05, 0.10],
            n_tranches=3,
        )
        assert len(bands) == 4  # 3 explicit + 1 terminal
        assert bands[0].from_amount == Decimal("0")
        assert bands[0].to_amount == Decimal("300")
        assert bands[0].rate == Decimal("0.05")
        assert bands[1].rate == Decimal("0.10")  # second rate
        assert bands[2].rate == Decimal("0.10")  # last rate repeats
        assert bands[-1].to_amount is None

    def test_tranches_fixes_missing_width_raises(self):
        with pytest.raises(ValueError, match="positive tranche_width"):
            materialise_bands("tranches_fixes", tranche_width=None, rate_sequence=[0.10])

    def test_tranches_fixes_missing_rates_raises(self):
        with pytest.raises(ValueError, match="non-empty rate_sequence"):
            materialise_bands("tranches_fixes", tranche_width=Decimal("500"), rate_sequence=[])

    def test_custom_empty_raises(self):
        with pytest.raises(ValueError, match="non-empty custom_bands"):
            materialise_bands("custom", custom_bands=[])

    def test_custom_last_band_unbounded(self):
        bands = materialise_bands(
            model_type="custom",
            custom_bands=[
                {"threshold": 500, "rate": 0.08},
                {"threshold": 1000, "rate": 0.15},
            ],
        )
        assert len(bands) == 2
        assert bands[0].to_amount == Decimal("500")
        assert bands[1].from_amount == Decimal("500")
        assert bands[1].to_amount is None  # last entry is unbounded

    def test_unknown_model_type_raises(self):
        with pytest.raises(ValueError, match="Unknown model_type"):
            materialise_bands("bogus")


# ── validate_bands ─────────────────────────────────────────────────────────────

class TestValidateBands:
    def test_empty_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            validate_bands([])

    def test_rate_zero_raises(self):
        with pytest.raises(ValueError, match="rate must be in"):
            validate_bands([Band(Decimal("0"), None, Decimal("0"))])

    def test_rate_above_one_raises(self):
        with pytest.raises(ValueError, match="rate must be in"):
            validate_bands([Band(Decimal("0"), None, Decimal("1.01"))])

    def test_non_contiguous_raises(self):
        with pytest.raises(ValueError, match="from_amount"):
            validate_bands([
                Band(Decimal("0"),   Decimal("500"), Decimal("0.10")),
                Band(Decimal("600"), None,           Decimal("0.20")),  # gap 500→600
            ])

    def test_terminal_not_last_raises(self):
        with pytest.raises(ValueError, match="only the last band"):
            validate_bands([
                Band(Decimal("0"),   None,           Decimal("0.10")),  # terminal not last
                Band(Decimal("500"), Decimal("1000"), Decimal("0.20")),
            ])

    def test_zero_width_raises(self):
        with pytest.raises(ValueError, match="to_amount.*must be >"):
            validate_bands([
                Band(Decimal("0"), Decimal("0"), Decimal("0.10")),
            ])

    def test_single_unbounded_band_valid(self):
        validate_bands([Band(Decimal("0"), None, Decimal("0.10"))])


# ── Snapshot round-trip ────────────────────────────────────────────────────────

class TestSnapshot:
    def test_round_trip_eric(self, eric_bands):
        snapshot = bands_to_snapshot(eric_bands)
        restored = snapshot_to_bands(snapshot)
        for orig, rest in zip(eric_bands, restored):
            assert orig.from_amount == rest.from_amount
            assert orig.to_amount == rest.to_amount
            assert orig.rate == rest.rate

    def test_snapshot_null_for_last_band(self, eric_bands):
        snapshot = bands_to_snapshot(eric_bands)
        assert snapshot[-1]["to"] is None

    def test_snapshot_values_are_float(self, eric_bands):
        snapshot = bands_to_snapshot(eric_bands)
        for item in snapshot:
            assert isinstance(item["from"], float)
            if item["to"] is not None:
                assert isinstance(item["to"], float)
            assert isinstance(item["rate"], float)


# ── Deficit carry-forward ──────────────────────────────────────────────────────

class TestDeficitCarryForward:
    def test_deficit_increases_next_month_objectif(self):
        """
        Month 1: objectif=1000, resultat=800 → ecart=-200, prime=0
        Month 2: objectif_initial=1000, deficit=200 → objectif_final=1200
                 resultat=1800 → ecart=600 → prime=60.00 (600×10%)
        """
        bands = ERIC_DEFAULT_BANDS
        m1 = compute_prime_month(
            month=1, days_worked=20,
            resultat=Decimal("800"),
            objectif_jour=Decimal("50"),
            deficit_anterieur=Decimal("0"),
            bands=bands,
        )
        assert m1.ecart == Decimal("-200.00")
        assert m1.prime == Decimal("0.00")

        m2 = compute_prime_month(
            month=2, days_worked=20,
            resultat=Decimal("1800"),
            objectif_jour=Decimal("50"),
            deficit_anterieur=abs(m1.ecart),
            bands=bands,
        )
        assert m2.objectif_final == Decimal("1200.00")
        assert m2.ecart == Decimal("600.00")
        assert m2.prime == Decimal("60.00")

    def test_zero_deficit_when_objectif_met(self):
        """Surplus month — deficit for next month is 0."""
        m = compute_prime_month(
            month=1, days_worked=20,
            resultat=Decimal("1500"),
            objectif_jour=Decimal("50"),
            deficit_anterieur=Decimal("0"),
            bands=ERIC_DEFAULT_BANDS,
        )
        assert m.ecart > 0
        next_deficit = abs(m.ecart) if m.ecart < 0 else Decimal("0")
        assert next_deficit == Decimal("0")


# ── Backward compat: calculate_tiered_prime ────────────────────────────────────

class TestBackwardCompat:
    def test_default_tiers_unchanged(self):
        """
        The legacy calculate_tiered_prime() must return the same value as
        compute_bonus() with ERIC_DEFAULT_BANDS.
        """
        ecart = Decimal("1145.91")
        legacy = calculate_tiered_prime(ecart)
        new = compute_bonus(ecart, ERIC_DEFAULT_BANDS).total_prime
        assert legacy == new

    def test_zero_returns_zero(self):
        assert calculate_tiered_prime(Decimal("0")) == Decimal("0")

    def test_negative_returns_zero(self):
        assert calculate_tiered_prime(Decimal("-100")) == Decimal("0")

    def test_custom_tiers_still_work(self):
        """Custom PrimeTier list passed to legacy function."""
        tiers = [
            PrimeTier(Decimal("500"),  Decimal("0.10")),
            PrimeTier(Decimal("1000"), Decimal("0.20")),
        ]
        # 300: first band 0-500 @ 10% → 30.00
        assert calculate_tiered_prime(Decimal("300"), tiers) == Decimal("30.00")
        # 750: first band 500 @ 10% + 250 @ 20% → 50 + 50 = 100.00
        assert calculate_tiered_prime(Decimal("750"), tiers) == Decimal("100.00")
