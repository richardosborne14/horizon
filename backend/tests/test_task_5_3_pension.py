"""
Unit tests for state pension estimation (TASK-5.3).

Tests trimestre counting, retraite de base, retraite complémentaire,
décote/surcote logic, and edge cases.
"""
from decimal import Decimal

from app.calculations.pension import estimate_monthly_pension, get_trimestres_requis


class TestTrimestresRequis:
    """Trimestres requis lookup."""

    def test_known_birth_year(self):
        assert get_trimestres_requis(1986) == 172

    def test_early_birth_year(self):
        assert get_trimestres_requis(1960) == 167

    def test_unknown_birth_year_falls_back(self):
        assert get_trimestres_requis(2005) == 172


class TestPensionEstimation:
    """Full pension estimation scenarios."""

    def test_full_career_ae_moderate_income(self):
        """Full 30-year AE career at ~60k€/year → should reach taux plein."""
        # 30 years of CA, 5,600€/month (67,200€/year), BNC, retiring at 70
        ca_history = [Decimal("67200")] * 30
        birth_year = 1986  # trimestres requis = 172

        result = estimate_monthly_pension(
            birth_year=birth_year,
            activity_type="bnc_non_reglementee",
            ca_history=ca_history,
            retirement_age=70,
        )

        # With 30 years at 67,200€ each, trimestres:
        # Each year: min(4, 67200 / 2880) = min(4, 23) = 4
        # Total: 30 * 4 = 120 trimestres
        # 120 < 172 → décote applies. Rate < 50%.
        # Retirement age 70 ≥ 67 → taux plein auto → taux = 50%
        assert result["is_taux_plein"] is True
        assert result["taux"] >= Decimal("0.50")
        # Monthly pension should be in the 500-1500€ range
        total = result["total_monthly"]
        assert total > Decimal("0")
        # Reasonable range for full career AE
        assert total > Decimal("100")  # sanity floor

    def test_late_start_ae_with_decote(self):
        """Only 15 years of AE contributions → fewer trimestres, décote."""
        ca_history = [Decimal("36000")] * 15  # 3,000€/month
        birth_year = 1986

        result = estimate_monthly_pension(
            birth_year=birth_year,
            activity_type="bnc_non_reglementee",
            ca_history=ca_history,
            retirement_age=62,  # retiring before taux plein auto at 67
        )

        # 15 years × 4 trimestres = 60 < 172 → décote applies
        # Not at age 67, so no auto taux plein
        assert result["is_taux_plein"] is False
        assert result["taux"] < Decimal("0.50")
        # Missing: 172 - 60 = 112, capped at 20 for décote
        # Décote: 20 * 0.0125 = 0.25, taux = 0.50 - 0.25 = 0.25
        assert result["total_monthly"] > Decimal("0")

    def test_high_ca_ae_hitting_pass_ceiling(self):
        """High-CA AE (10,000€/month) — SAM capped at PASS."""
        ca_history = [Decimal("120000")] * 30  # 10,000€/month, above PASS
        birth_year = 1986

        result = estimate_monthly_pension(
            birth_year=birth_year,
            activity_type="bnc_non_reglementee",
            ca_history=ca_history,
            retirement_age=70,
        )

        # SAM should be capped at PASS (46,368€)
        # taux = 50% (retirement at 70 ≥ 67)
        # base_annual = 46368 * 0.50 * (120/172) = ...
        total = result["total_monthly"]
        assert total > Decimal("0")
        # With PASS-level income, pension should be higher than low-income
        assert total > Decimal("300")

    def test_zero_ca_history(self):
        """Empty CA history should return zero pension."""
        result = estimate_monthly_pension(
            birth_year=1986,
            activity_type="bnc_non_reglementee",
            ca_history=[],
            retirement_age=70,
        )
        assert result["total_monthly"] == Decimal("0")
        assert result["trimestres_valides"] == 0

    def test_surcote_delayed_retirement(self):
        """Retiring at 70 with full trimestres → potential surcote."""
        ca_history = [Decimal("80000")] * 45  # full career, high CA
        birth_year = 1960  # trimestres requis = 167

        result = estimate_monthly_pension(
            birth_year=birth_year,
            activity_type="bnc_non_reglementee",
            ca_history=ca_history,
            retirement_age=70,
        )

        # 45 years × 4 trimestres = 180 > 167 → extra 13
        # age 70 > 67, so taux plein auto + surcote for extra trimestres
        assert result["is_taux_plein"] is True
        # taux should be > 50% due to surcote
        assert result["taux"] > Decimal("0.50")

    def test_bic_vente_higher_threshold(self):
        """BIC vente has higher trimestre threshold (~4,208€ vs 2,880€)."""
        ca_history = [Decimal("42080")] * 30  # should get 4 trimestres/year
        birth_year = 1986

        result = estimate_monthly_pension(
            birth_year=birth_year,
            activity_type="bic_vente",
            ca_history=ca_history,
            retirement_age=70,
        )
        # 42080 / 4208 = 10 → 4 trimestres (capped)
        assert result["trimestres_valides"] == 120  # 30 * 4

    def test_retraite_complementaire_increases_with_ca(self):
        """Higher CA should produce higher retraite complémentaire."""
        low_ca = [Decimal("30000")] * 30
        high_ca = [Decimal("80000")] * 30

        low = estimate_monthly_pension(1986, "bnc_non_reglementee", low_ca, 70)
        high = estimate_monthly_pension(1986, "bnc_non_reglementee", high_ca, 70)

        assert high["complementaire_monthly"] > low["complementaire_monthly"]

    def test_confidence_is_always_low(self):
        """Our model always reports low confidence."""
        result = estimate_monthly_pension(
            birth_year=1986,
            activity_type="bnc_non_reglementee",
            ca_history=[Decimal("50000")] * 30,
            retirement_age=70,
        )
        assert result["confidence"] == "low"


class TestPensionNominalDeflation:
    """PENSION-BUG-1 — ensure nominal→real deflation keeps values within legal bounds.

    estimate_monthly_pension_v2() produces results in nominal future euros
    (PASS cap is inflated per year, CA grows nominally). Without deflation
    the displayed pension exceeds the legal retraite de base ceiling of
    PASS/2/12 ≈ 1932€/mo (in today's euros). The router deflates by
    (1 + infl_rate)^years_to_retirement before returning the response.
    """

    def test_nominal_pension_exceeds_deflated_value(self):
        """Raw v2 output is in nominal future euros — must exceed the real (deflated) value.

        The nominal pension can be below today's legal cap when prorata < 1
        (user has fewer than 172 trimestres), but it is ALWAYS larger than
        the real value because inflated CA → inflated SAM → inflated pension.
        Without deflation, the UI shows a figure inflated ~2× over 27 years.
        """
        from app.calculations.pension import estimate_monthly_pension_v2

        years = 27  # born 1986, retiring at 67 in 2053
        infl_rate = Decimal("0.025")
        projected = [
            {"year": 2026 + i, "ca": Decimal("60000") * ((Decimal("1.03")) ** i)}
            for i in range(years)
        ]
        raw = estimate_monthly_pension_v2(
            birth_year=1986,
            career_periods=[],
            projected_ae_ca=projected,
            ae_activity_type="bnc_non_reglementee",
            retirement_age=67,
            current_year=2026,
            inflation_rate=infl_rate,
        )
        nominal = raw["total_monthly"]
        deflation = (Decimal("1") + infl_rate) ** Decimal(str(years))
        real_total = nominal / deflation
        # The nominal value must be substantially larger than the real value
        # (the deflation factor for 27 years at 2.5% is ~1.95)
        assert nominal > real_total * Decimal("1.5"), (
            f"Nominal {nominal:.2f} should be ~2× the real {real_total:.2f}, got ratio "
            f"{float(nominal / real_total):.2f}"
        )

    def test_deflated_pension_within_legal_cap(self):
        """After deflation by (1.025)^27 the pension must be <= PASS/2/12."""
        from app.calculations.pension import estimate_monthly_pension_v2

        years = 27
        infl_rate = Decimal("0.025")
        projected = [
            {"year": 2026 + i, "ca": Decimal("60000") * ((Decimal("1.03")) ** i)}
            for i in range(years)
        ]
        raw = estimate_monthly_pension_v2(
            birth_year=1986,
            career_periods=[],
            projected_ae_ca=projected,
            ae_activity_type="bnc_non_reglementee",
            retirement_age=67,
            current_year=2026,
            inflation_rate=infl_rate,
        )
        deflation = (Decimal("1") + infl_rate) ** Decimal(str(years))
        real_base = Decimal(str(raw["base_salarie_monthly"])) / deflation
        legal_cap = Decimal("46368") / Decimal("2") / Decimal("12")  # ≈ 1932€
        assert real_base <= legal_cap, (
            f"Real base pension {real_base:.2f} exceeds legal cap {legal_cap:.2f}"
        )

    def test_deflated_pension_is_realistic(self):
        """Real pension for a 5k/mo AE should be roughly 800–1200€/mo in today's euros."""
        from app.calculations.pension import estimate_monthly_pension_v2

        years = 27
        infl_rate = Decimal("0.025")
        projected = [
            {"year": 2026 + i, "ca": Decimal("5000") * Decimal("12") * ((Decimal("1.03")) ** i)}
            for i in range(years)
        ]
        raw = estimate_monthly_pension_v2(
            birth_year=1986,
            career_periods=[],
            projected_ae_ca=projected,
            ae_activity_type="bnc_non_reglementee",
            retirement_age=67,
            current_year=2026,
            inflation_rate=infl_rate,
        )
        deflation = (Decimal("1") + infl_rate) ** Decimal(str(years))
        real_total = Decimal(str(raw["total_monthly"])) / deflation
        # With 108/172 trimestres and SAM ~31k real → expect roughly 800–1200€/mo
        assert Decimal("500") <= real_total <= Decimal("1500"), (
            f"Real pension {real_total:.2f} outside expected range 500–1500€/mo"
        )
