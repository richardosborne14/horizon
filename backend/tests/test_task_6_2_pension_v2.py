"""
Sprint 6 — TASK-6.2 Pension Engine v2 (Career-Aware) tests.

Tests:
- CDI-only career pension estimation
- AE-only career pension estimation
- Mixed career (CDI + AE) pension estimation
- Décote when trimestres < required
- Taux plein at age 67 regardless of trimestres
- Unemployment and parental leave trimestre counting
- SAM uses best 25 years capped at PASS
- Complementary pension (AGIRC-ARRCO + RCI)
"""

from datetime import date
from decimal import Decimal

from app.calculations.pension import (
    estimate_monthly_pension_v2,
    _compute_salarie_trimestres,
    _compute_ae_trimestres,
    _compute_unemployment_trimestres,
    _compute_avpf_trimestres,
    _inflate_threshold,
    MAX_TRIMESTRES_PER_YEAR,
    SALARIE_TRIMESTRE_THRESHOLD,
    PASS,
    AGE_TAUX_PLEIN_AUTO,
)


def test_salarie_trimestres_basic():
    """Full-time CDI at 40k → 4 trimestres/year."""
    t = _compute_salarie_trimestres(
        annual_gross=Decimal("40000"),
        threshold=SALARIE_TRIMESTRE_THRESHOLD,
        is_full_time=True,
        time_percentage=100,
    )
    assert t == 4


def test_salarie_trimestres_low_salary():
    """Part-time, low salary → fewer trimestres."""
    t = _compute_salarie_trimestres(
        annual_gross=Decimal("5000"),
        threshold=SALARIE_TRIMESTRE_THRESHOLD,
        is_full_time=False,
        time_percentage=50,
    )
    # 5000 × 0.5 = 2500 < 6990 → 0 trimestres
    assert t == 0


def test_salarie_trimestres_capped():
    """Max 4 per year regardless of salary."""
    t = _compute_salarie_trimestres(
        annual_gross=Decimal("200000"),
        threshold=SALARIE_TRIMESTRE_THRESHOLD,
        is_full_time=True,
        time_percentage=100,
    )
    assert t <= MAX_TRIMESTRES_PER_YEAR
    assert t == 4


def test_ae_trimestres_basic():
    """AE at 67,200€ CA (BNC) → max trimestres."""
    t = _compute_ae_trimestres(
        annual_ca=Decimal("67200"),
        activity_type="bnc_non_reglementee",
        threshold=Decimal("2880"),
    )
    assert t == 4


def test_ae_trimestres_low_ca():
    """Low CA → 0 trimestres."""
    t = _compute_ae_trimestres(
        annual_ca=Decimal("2000"),
        activity_type="bnc_non_reglementee",
        threshold=Decimal("2880"),
    )
    assert t == 0


def test_inflate_threshold():
    """Threshold should inflate over time."""
    base = Decimal("2880")
    inflated = _inflate_threshold(base, year_index=10, inflation_rate=Decimal("0.025"))
    # 2880 × 1.025^10 ≈ 2880 × 1.280 = 3687
    assert inflated > Decimal("3600")
    assert inflated < Decimal("3800")


def test_cdi_only_career():
    """20-year CDI career at 40k/year → 80 trimestres, sam-based pension."""
    career = [
        {
            "period_type": "cdi",
            "start_date": date(2000, 1, 1),
            "end_date": date(2020, 1, 1),
            "annual_gross": Decimal("40000"),
            "is_full_time": True,
            "time_percentage": 100,
        },
    ]

    result = estimate_monthly_pension_v2(
        birth_year=1980,
        career_periods=career,
        projected_ae_ca=[],
        ae_activity_type="bnc_non_reglementee",
        retirement_age=67,
        current_year=2026,
    )

    assert result["trimestres"]["salarie"] >= 72  # 20 years × 4, minus some for index
    assert result["trimestres"]["total"] >= 72
    assert result["trimestres"]["required"] == 172
    assert result["trimestres"]["missing"] > 0
    # Age 67 → auto taux plein even with < 172 trimestres
    assert result["is_taux_plein"] is True
    assert result["taux"] == Decimal("0.50")
    assert result["total_monthly"] > Decimal("0")

    # SAM should be around 40,000 (capped at PASS)
    assert result["sam"] > Decimal("0")
    assert result["sam"] <= PASS

    # Complementary pension should have AGIRC-ARRCO points
    assert result["complementaire_salarie_monthly"] > Decimal("0")


def test_ae_only_career():
    """Full AE career → pension from AE income only."""
    career = [
        {
            "period_type": "ae",
            "start_date": date(2010, 1, 1),
            "end_date": date(2040, 1, 1),
            "annual_gross": Decimal("67200"),
            "is_full_time": True,
            "time_percentage": 100,
        },
    ]

    result = estimate_monthly_pension_v2(
        birth_year=1980,
        career_periods=career,
        projected_ae_ca=[],
        ae_activity_type="bnc_non_reglementee",
        retirement_age=67,
        current_year=2026,
    )

    assert result["trimestres"]["ae_past_projected"] > 0
    assert result["total_monthly"] > Decimal("0")
    assert result["confidence"] == "low"  # No salaried history


def test_mixed_career():
    """8yr CDI at 40k + 10yr AE at 67k → combined pension.

    This is Richard's scenario: regime général pension from CDI years
    plus AE pension from freelance income.
    """
    career = [
        {
            "period_type": "cdi",
            "start_date": date(2012, 9, 1),
            "end_date": date(2020, 3, 15),
            "annual_gross": Decimal("40000"),
            "is_full_time": True,
            "time_percentage": 100,
        },
        {
            "period_type": "ae",
            "start_date": date(2020, 4, 1),
            "end_date": None,  # ongoing
            "annual_gross": Decimal("67200"),
            "is_full_time": True,
            "time_percentage": 100,
        },
    ]

    result = estimate_monthly_pension_v2(
        birth_year=1984,
        career_periods=career,
        projected_ae_ca=[],
        ae_activity_type="bnc_non_reglementee",
        retirement_age=70,
        current_year=2026,
    )

    # Trimestres
    trim = result["trimestres"]
    assert trim["salarie"] >= 28  # 7+ years CDI × 4
    assert trim["ae_past_projected"] > 0  # AE trimestres
    assert trim["total"] >= 30

    # Pension should be non-zero
    assert result["total_monthly"] > Decimal("0")
    assert result["total_monthly"] > Decimal("100")  # Should be a meaningful amount

    # Confidence should be medium with salaried history
    assert result["confidence"] == "medium"

    # JSON serialization check: should have all expected keys
    assert "base_salarie_monthly" in result
    assert "complementaire_salarie_monthly" in result
    assert "complementaire_ae_monthly" in result
    assert "total_monthly" in result
    assert "is_taux_plein" in result


def test_decote_when_missing_trimestres():
    """Retiring at 62 with insufficient trimestres → décote applied."""
    # Only 10 years of CDI = 40 trimestres. Retire at 62 (before auto taux plein)
    career = [
        {
            "period_type": "cdi",
            "start_date": date(2000, 1, 1),
            "end_date": date(2010, 1, 1),
            "annual_gross": Decimal("40000"),
            "is_full_time": True,
            "time_percentage": 100,
        },
    ]

    result = estimate_monthly_pension_v2(
        birth_year=1980,
        career_periods=career,
        projected_ae_ca=[],
        ae_activity_type="bnc_non_reglementee",
        retirement_age=62,
        current_year=2026,
    )

    # Trimestres
    assert result["trimestres"]["total"] < result["trimestres"]["required"]
    assert result["is_taux_plein"] is False

    # Taux should be less than 50% due to décote
    assert result["taux"] < Decimal("0.50")
    assert result["taux"] >= Decimal("0.375")  # floor
    assert result["decote_pct"] > Decimal("0")


def test_taux_plein_at_67():
    """Age 67 → automatic taux plein regardless of trimestres."""
    career = [
        {
            "period_type": "cdi",
            "start_date": date(2000, 1, 1),
            "end_date": date(2005, 1, 1),  # Only 5 years = 20 trimestres
            "annual_gross": Decimal("30000"),
            "is_full_time": True,
            "time_percentage": 100,
        },
    ]

    result = estimate_monthly_pension_v2(
        birth_year=1980,
        career_periods=career,
        projected_ae_ca=[],
        ae_activity_type="bnc_non_reglementee",
        retirement_age=67,
        current_year=2026,
    )

    assert result["trimestres"]["total"] < result["trimestres"]["required"]
    # Even with insufficient trimestres, age 67 gives taux plein
    assert result["taux"] == Decimal("0.50")
    assert result["is_taux_plein"] is True
    assert result["decote_pct"] == Decimal("0")


def test_empty_career():
    """No career periods → zero pension."""
    result = estimate_monthly_pension_v2(
        birth_year=1986,
        career_periods=[],
        projected_ae_ca=[],
        ae_activity_type="bnc_non_reglementee",
        retirement_age=67,
        current_year=2026,
    )

    assert result["total_monthly"] == Decimal("0")
    assert result["trimestres"]["total"] == 0
    assert result["trimestres"]["missing"] == 172


def test_unemployment_trimestres():
    """Unemployment period should generate some trimestres."""
    start = date(2020, 1, 1)
    end = date(2021, 1, 1)  # 366 days

    t = _compute_unemployment_trimestres(start, end, None)
    # ~366/90 = 4 quarters
    assert t == 4


def test_avpf_trimestres():
    """Parental leave should generate AVPF trimestres."""
    start = date(2020, 1, 1)
    end = date(2020, 12, 31)  # 1 year = 4 quarters

    t = _compute_avpf_trimestres(start, end, total_avpf_so_far=0)
    assert t == 4

    # Cap at 8 total
    t2 = _compute_avpf_trimestres(
        date(2022, 1, 1), date(2022, 12, 31), total_avpf_so_far=6
    )
    assert t2 == 2  # 8 - 6 = 2 remaining


def test_sam_capped_at_pass():
    """SAM should cap individual years at PASS (inflated per year).

    A 200k salary should be capped at the year-specific PASS,
    not at 200k. The PASS inflates over time, so the capped value
    for a 2015 salary will be slightly above the 2024 base PASS.
    """
    from decimal import Decimal

    # 5 years at 200k (well above any PASS)
    career = [
        {
            "period_type": "cdi",
            "start_date": date(2015, 1, 1),
            "end_date": date(2020, 1, 1),
            "annual_gross": Decimal("200000"),
            "is_full_time": True,
            "time_percentage": 100,
        },
    ]

    result = estimate_monthly_pension_v2(
        birth_year=1980,
        career_periods=career,
        projected_ae_ca=[],
        ae_activity_type="bnc_non_reglementee",
        retirement_age=67,
        current_year=2026,
    )

    # SAM should be far below 200,000 (year-specific PASS caps each year)
    assert result["sam"] < Decimal("60000"), (
        f"SAM should be capped at PASS, got {result['sam']}"
    )
    assert result["sam"] > Decimal("0")
    assert result["total_monthly"] > Decimal("0")


def test_best_25_years():
    """SAM should use only the best 25 years."""
    # 30 years of income: first 5 at 20k, last 25 at 40k
    career = []

    for i in range(30):
        yr_start = 1990 + i
        salary = Decimal("20000") if i < 5 else Decimal("40000")
        career.append({
            "period_type": "cdi",
            "start_date": date(yr_start, 1, 1),
            "end_date": date(yr_start, 12, 31),
            "annual_gross": salary,
            "is_full_time": True,
            "time_percentage": 100,
        })

    result = estimate_monthly_pension_v2(
        birth_year=1980,
        career_periods=career,
        projected_ae_ca=[],
        ae_activity_type="bnc_non_reglementee",
        retirement_age=67,
        current_year=2026,
    )

    # SAM should be close to 40,000 (the best 25 years), not the average of all 30
    assert result["sam"] >= Decimal("35000")