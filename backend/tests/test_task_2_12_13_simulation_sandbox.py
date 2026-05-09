"""
Unit tests for TASK-2.12.13 — Simulation sandbox calculation engine.

Tests cover:
  - Zero deltas when simulated inputs == baseline inputs
  - CA +10% increases bénéfice net correctly
  - Statut change (SASU → EURL) changes charges sociales appropriately
  - TVA rate change recomputes TVA à reverser correctly
  - AE path uses URSSAF on CA, no dirigeant cost
  - Baseline extraction from a typical_month_template dict
  - Edge cases: zero TVA, zero inputs
"""

from __future__ import annotations

import pytest

from app.services.simulation_sandbox import (
    SandboxInputs,
    compute_deltas,
    compute_sandbox,
    extract_sandbox_inputs_from_template,
)


# ── Fixtures ────────────────────────────────────────────────────────────────────


def _baseline_inputs() -> SandboxInputs:
    """A realistic set of baseline inputs for a SASU coiffeur."""
    return SandboxInputs(
        ca_services_ttc=15_000.0,
        ca_revente_ttc=2_000.0,
        masse_salariale_brute=5_000.0,
        remuneration_dirigeant_nette=2_500.0,
        charges_fixes_ttc=3_000.0,
        achats_marchandises_ttc=1_500.0,
        taux_tva_pct=10.0,
        statut_juridique="sasu",
    )


# ── compute_sandbox tests ─────────────────────────────────────────────────────


class TestComputeSandbox:
    def test_ca_ht_computed_correctly(self) -> None:
        """CA HT = CA TTC / 1.10 when TVA = 10%."""
        inputs = SandboxInputs(ca_services_ttc=11_000.0, taux_tva_pct=10.0)
        results = compute_sandbox(inputs)
        assert abs(results.ca_total_ht - 10_000.0) < 0.01

    def test_tva_collectee_is_ca_ttc_minus_ht(self) -> None:
        """TVA collectée = CA TTC − CA HT."""
        inputs = SandboxInputs(ca_services_ttc=11_000.0, taux_tva_pct=10.0)
        results = compute_sandbox(inputs)
        assert abs(results.tva_collectee - 1_000.0) < 0.01

    def test_tva_reverser_positive_when_collectee_gt_deductible(self) -> None:
        """TVA à reverser > 0 when more TVA collected than deducted."""
        inputs = SandboxInputs(
            ca_services_ttc=11_000.0,
            charges_fixes_ttc=1_100.0,
            taux_tva_pct=10.0,
        )
        results = compute_sandbox(inputs)
        # Collectée: 1000 €; Déductible: 100 €; Reverser: 900 €
        assert results.tva_a_reverser > 0

    def test_tva_reverser_zero_when_all_inputs_zero(self) -> None:
        """All zeros in → all zeros out (no NaN/exceptions)."""
        results = compute_sandbox(SandboxInputs())
        assert results.ca_total_ht == 0.0
        assert results.tva_a_reverser == 0.0
        assert results.benefice_net == 0.0

    def test_sasu_dirigeant_cost_uses_assimile_ratio(self) -> None:
        """SASU dirigeant total cost = net × 2.0."""
        inputs = SandboxInputs(
            remuneration_dirigeant_nette=1_000.0,
            statut_juridique="sasu",
        )
        results = compute_sandbox(inputs)
        # Only dirigeant cost, no team → charges_sociales = 0 + 2000 = 2000
        assert abs(results.charges_sociales_total - 2_000.0) < 0.01

    def test_eurl_dirigeant_cost_uses_tns_ratio(self) -> None:
        """EURL dirigeant total cost = net × 1.45."""
        inputs = SandboxInputs(
            remuneration_dirigeant_nette=1_000.0,
            statut_juridique="eurl",
        )
        results = compute_sandbox(inputs)
        # charges_sociales = 0 (no team) + 1000 × 1.45 = 1450
        assert abs(results.charges_sociales_total - 1_450.0) < 0.01

    def test_ae_no_dirigeant_cost_urssaf_on_ca(self) -> None:
        """AE has no dirigeant salary cost; URSSAF is applied on CA HT."""
        inputs = SandboxInputs(
            ca_services_ttc=10_000.0,
            remuneration_dirigeant_nette=2_000.0,  # ignored for AE
            statut_juridique="ae",
            taux_tva_pct=0.0,  # AE is TVA-exempt
        )
        results = compute_sandbox(inputs)
        # Dirigeant cost = 0 for AE
        assert results.charges_sociales_total == 0.0
        # Bénéfice should be reduced by URSSAF (21.2% on 10 000 = 2120)
        assert results.benefice_avant_impots < 10_000.0

    def test_point_mort_equals_total_costs(self) -> None:
        """Point mort = sum of all costs HT (break-even CA)."""
        inputs = _baseline_inputs()
        results = compute_sandbox(inputs)
        # Point mort is the CA HT needed to cover all costs
        assert results.point_mort == pytest.approx(
            results.charges_sociales_total
            + (inputs.charges_fixes_ttc / 1.10)
            + (inputs.achats_marchandises_ttc / 1.10),
            abs=10.0,
        )

    def test_benefice_net_positive_when_ca_above_point_mort(self) -> None:
        """Bénéfice net > 0 when CA HT > point mort."""
        inputs = SandboxInputs(
            ca_services_ttc=30_000.0,
            taux_tva_pct=10.0,
            statut_juridique="sasu",
        )
        results = compute_sandbox(inputs)
        assert results.benefice_net > 0.0

    def test_impot_zero_for_ae(self) -> None:
        """AE impôt estimate = 0 (VL/IF handled separately)."""
        inputs = SandboxInputs(
            ca_services_ttc=20_000.0,
            statut_juridique="ae",
            taux_tva_pct=0.0,
        )
        results = compute_sandbox(inputs)
        assert results.impot_estime == 0.0

    def test_is_estimated_for_sasu(self) -> None:
        """SASU IS estimate > 0 when bénéfice > 0."""
        inputs = SandboxInputs(
            ca_services_ttc=50_000.0,
            taux_tva_pct=10.0,
            statut_juridique="sasu",
        )
        results = compute_sandbox(inputs)
        assert results.impot_estime > 0.0


# ── compute_deltas tests ──────────────────────────────────────────────────────


class TestComputeDeltas:
    def test_zero_deltas_when_inputs_identical(self) -> None:
        """When simulated inputs == baseline inputs, all deltas are 0."""
        inputs = _baseline_inputs()
        baseline = compute_sandbox(inputs)
        simulated = compute_sandbox(inputs)  # same inputs
        deltas = compute_deltas(baseline, simulated)

        for field, delta in deltas.items():
            assert delta.abs == 0.0, f"Expected zero delta for {field}, got {delta.abs}"
            assert delta.pct == 0.0, f"Expected zero pct delta for {field}, got {delta.pct}"

    def test_ca_increase_raises_benefice(self) -> None:
        """CA +10% should increase bénéfice net (positive delta)."""
        baseline_inputs = _baseline_inputs()
        simulated_inputs = SandboxInputs(
            **{**baseline_inputs.model_dump(), "ca_services_ttc": 15_000.0 * 1.10}
        )
        baseline = compute_sandbox(baseline_inputs)
        simulated = compute_sandbox(simulated_inputs)
        deltas = compute_deltas(baseline, simulated)

        assert deltas["benefice_net"].abs > 0
        assert deltas["benefice_net"].pct > 0

    def test_ca_increase_raises_ca_ht(self) -> None:
        """CA +10% → CA HT delta ≈ +10%."""
        baseline_inputs = _baseline_inputs()
        simulated_inputs = SandboxInputs(
            **{**baseline_inputs.model_dump(), "ca_services_ttc": 15_000.0 * 1.10}
        )
        baseline = compute_sandbox(baseline_inputs)
        simulated = compute_sandbox(simulated_inputs)
        deltas = compute_deltas(baseline, simulated)

        assert abs(deltas["ca_total_ht"].pct - 8.8) < 1.0  # ~8.8% (services only +10%)

    def test_statut_change_sasu_to_eurl_lowers_charges(self) -> None:
        """Switching SASU → EURL reduces dirigeant cost (TNS is cheaper)."""
        baseline_inputs = _baseline_inputs()  # statut_juridique = "sasu"
        simulated_inputs = SandboxInputs(
            **{**baseline_inputs.model_dump(), "statut_juridique": "eurl"}
        )
        baseline = compute_sandbox(baseline_inputs)
        simulated = compute_sandbox(simulated_inputs)
        deltas = compute_deltas(baseline, simulated)

        # SASU dirigeant: 2500 × 2.0 = 5000; EURL: 2500 × 1.45 = 3625 → delta = -1375
        assert deltas["charges_sociales_total"].abs < 0
        assert deltas["benefice_net"].abs > 0  # lower charges → higher net

    def test_tva_rate_change_affects_tva_reverser(self) -> None:
        """Raising TVA rate from 10% to 20% increases TVA à reverser."""
        baseline_inputs = _baseline_inputs()  # taux_tva_pct = 10.0
        simulated_inputs = SandboxInputs(
            **{**baseline_inputs.model_dump(), "taux_tva_pct": 20.0}
        )
        baseline = compute_sandbox(baseline_inputs)
        simulated = compute_sandbox(simulated_inputs)
        deltas = compute_deltas(baseline, simulated)

        assert deltas["tva_a_reverser"].abs > 0


# ── extract_sandbox_inputs_from_template tests ───────────────────────────────


class TestExtractBaseline:
    def test_extracts_ca_from_template(self) -> None:
        """CA values are extracted correctly from a typical_month_template dict."""
        template = {
            "ca_ttc": 15_000.0,
            "ca_services_ttc": 12_000.0,
            "ca_revente_ttc": 3_000.0,
            "team": [],
            "expenses": [],
        }
        inputs = extract_sandbox_inputs_from_template(template, "sasu")
        assert inputs.ca_services_ttc == 12_000.0
        assert inputs.ca_revente_ttc == 3_000.0

    def test_ca_total_used_when_no_breakdown(self) -> None:
        """When ca_services_ttc / ca_revente_ttc are absent, ca_ttc goes to services."""
        template = {"ca_ttc": 15_000.0, "team": [], "expenses": []}
        inputs = extract_sandbox_inputs_from_template(template, "sasu")
        assert inputs.ca_services_ttc == 15_000.0
        assert inputs.ca_revente_ttc == 0.0

    def test_extracts_masse_salariale_from_salary_brut(self) -> None:
        """salary_brut path is preferred over net_salary for team extraction."""
        template = {
            "ca_ttc": 10_000.0,
            "team": [
                {"salary_brut": 2_000.0, "net_salary": 1_600.0},
                {"salary_brut": 1_800.0, "net_salary": 1_400.0},
            ],
            "expenses": [],
        }
        inputs = extract_sandbox_inputs_from_template(template, "sasu")
        assert abs(inputs.masse_salariale_brute - 3_800.0) < 0.01

    def test_extracts_masse_salariale_from_net_salary_fallback(self) -> None:
        """Falls back to net_salary × 1.25 when salary_brut not set."""
        template = {
            "ca_ttc": 10_000.0,
            "team": [{"net_salary": 1_600.0}],
            "expenses": [],
        }
        inputs = extract_sandbox_inputs_from_template(template, "sasu")
        assert abs(inputs.masse_salariale_brute - 2_000.0) < 0.01  # 1600 × 1.25

    def test_extracts_achats_from_expenses(self) -> None:
        """Achats marchandises expenses are extracted to achats_marchandises_ttc."""
        template = {
            "ca_ttc": 10_000.0,
            "team": [],
            "expenses": [
                {"category": "expenses.achats_marchandises", "amount_ttc": 1_500.0},
                {"category": "expenses.loyer_immobilier", "amount_ttc": 1_200.0},
            ],
        }
        inputs = extract_sandbox_inputs_from_template(template, "sasu")
        assert inputs.achats_marchandises_ttc == 1_500.0
        assert inputs.charges_fixes_ttc == 1_200.0

    def test_ae_business_type_sets_tva_zero(self) -> None:
        """AE business type sets TVA to 0% (AE is TVA-exempt)."""
        template = {"ca_ttc": 10_000.0, "team": [], "expenses": []}
        inputs = extract_sandbox_inputs_from_template(template, "auto_micro")
        assert inputs.taux_tva_pct == 0.0
        assert inputs.statut_juridique == "ae"

    def test_sasu_business_type_maps_correctly(self) -> None:
        """SASU business type maps to 'sasu' statut_juridique."""
        template = {"ca_ttc": 10_000.0, "team": [], "expenses": []}
        inputs = extract_sandbox_inputs_from_template(template, "sasu")
        assert inputs.statut_juridique == "sasu"

    def test_remuneration_dirigeant_defaults_zero(self) -> None:
        """Dirigeant net remuneration defaults to 0 (not in wizard template)."""
        template = {"ca_ttc": 10_000.0, "team": [], "expenses": []}
        inputs = extract_sandbox_inputs_from_template(template, "eurl")
        assert inputs.remuneration_dirigeant_nette == 0.0
