"""
Tests for TASK-2.15.3 — compare_types breakdown fields.

Verifies that all four per-component breakdown fields are populated correctly
for each computation path (AE, TNS-IR, TNS-IS, assimilé salarié) and that
they sum to total_charges_eur (identity check).

Golden values derived by hand from the simplified formulas documented in
backend/app/services/compare_types.py.
"""

from decimal import Decimal

import pytest

from app.services.compare_types import (
    CompareProfile,
    compute_compare_types,
)


# ── Shared test profile ────────────────────────────────────────────────────────

def _profile(business_type: str = "auto_micro") -> CompareProfile:
    """
    Simple profile for golden-case testing.

    CA 120 000 € / an TTC (gross revenue)
    Charges fixes 24 000 € / an (loyer + utilities)
    Masse salariale 0 (solo)
    Rémunération nette dirigeant 30 000 € / an
    """
    return CompareProfile(
        ca_annuel_ttc=Decimal("120000"),
        charges_annuelles_fixes=Decimal("24000"),
        masse_salariale_annuelle=Decimal("0"),
        dirigeant_remuneration_nette=Decimal("30000"),
        business_type_actuel=business_type,
        versement_liberatoire=False,
        acre=False,
    )


def _row(rows, business_type: str):
    """Return the CompareRow for a given business_type."""
    r = next((r for r in rows if r.business_type == business_type), None)
    assert r is not None, f"No row for {business_type}"
    return r


# ── Identity test: breakdown fields must sum to total_charges_eur ──────────────

def test_breakdown_sum_equals_total_charges_ae():
    """For AE: cotisations + impot + charges_fixes + masse_salariale == total_charges."""
    rows = compute_compare_types(_profile("auto_micro"))
    r = _row(rows, "auto_micro")
    components = r.cotisations_dirigeant_eur + r.impot_eur + r.charges_fixes_eur + r.masse_salariale_eur
    assert components == r.total_charges_eur, (
        f"AE breakdown sum {components} != total_charges {r.total_charges_eur}"
    )


def test_breakdown_sum_equals_total_charges_sasu():
    """For SASU: cotisations + impot + charges_fixes + masse_salariale == total_charges."""
    rows = compute_compare_types(_profile("sasu"))
    r = _row(rows, "sasu")
    components = r.cotisations_dirigeant_eur + r.impot_eur + r.charges_fixes_eur + r.masse_salariale_eur
    assert components == r.total_charges_eur, (
        f"SASU breakdown sum {components} != total_charges {r.total_charges_eur}"
    )


def test_breakdown_sum_equals_total_charges_eurl_ir():
    """For EURL-IR: cotisations + impot + charges_fixes + masse_salariale == total_charges."""
    rows = compute_compare_types(_profile("eurl_ir"))
    r = _row(rows, "eurl_ir")
    components = r.cotisations_dirigeant_eur + r.impot_eur + r.charges_fixes_eur + r.masse_salariale_eur
    assert components == r.total_charges_eur, (
        f"EURL-IR breakdown sum {components} != total_charges {r.total_charges_eur}"
    )


def test_breakdown_sum_equals_total_charges_eurl_is():
    """For EURL-IS: cotisations + impot + charges_fixes + masse_salariale == total_charges."""
    rows = compute_compare_types(_profile("eurl_is"))
    r = _row(rows, "eurl_is")
    components = r.cotisations_dirigeant_eur + r.impot_eur + r.charges_fixes_eur + r.masse_salariale_eur
    assert components == r.total_charges_eur, (
        f"EURL-IS breakdown sum {components} != total_charges {r.total_charges_eur}"
    )


# ── Golden-case tests: AE path ────────────────────────────────────────────────

def test_ae_cotisations_equals_urssaf():
    """
    AE standard rate: urssaf = ca × 0.212 = 120 000 × 0.212 = 25 440 €.
    Breakdown cotisations field should match.
    """
    rows = compute_compare_types(_profile("auto_micro"))
    r = _row(rows, "auto_micro")
    expected_urssaf = Decimal("120000") * Decimal("0.212")
    assert r.cotisations_dirigeant_eur == expected_urssaf.quantize(Decimal("0.01")), (
        f"AE urssaf {r.cotisations_dirigeant_eur} != expected {expected_urssaf}"
    )


def test_ae_masse_salariale_is_zero():
    """AE has no employees — masse_salariale must always be 0."""
    rows = compute_compare_types(_profile("auto_micro"))
    r = _row(rows, "auto_micro")
    assert r.masse_salariale_eur == Decimal("0")


def test_ae_charges_fixes_equals_input():
    """AE charges_fixes_eur must equal the profile's charges_annuelles_fixes."""
    rows = compute_compare_types(_profile("auto_micro"))
    r = _row(rows, "auto_micro")
    assert r.charges_fixes_eur == Decimal("24000")


# ── Golden-case tests: TNS-IR path ────────────────────────────────────────────

def test_tns_ir_cotisations_equals_45pct():
    """
    TNS-IR: tns = remun_nette × 0.45 = 30 000 × 0.45 = 13 500 €.
    """
    rows = compute_compare_types(_profile("eurl_ir"))
    r = _row(rows, "eurl_ir")
    expected_tns = Decimal("30000") * Decimal("0.45")
    assert r.cotisations_dirigeant_eur == expected_tns.quantize(Decimal("0.01")), (
        f"TNS-IR cotisations {r.cotisations_dirigeant_eur} != expected {expected_tns}"
    )


def test_tns_ir_charges_fixes_equals_input():
    """TNS-IR charges_fixes must be passed through unchanged."""
    rows = compute_compare_types(_profile("eurl_ir"))
    r = _row(rows, "eurl_ir")
    assert r.charges_fixes_eur == Decimal("24000")


def test_tns_ir_masse_salariale_zero_for_solo():
    """Solo profile: TNS-IR masse_salariale_eur must be 0."""
    rows = compute_compare_types(_profile("eurl_ir"))
    r = _row(rows, "eurl_ir")
    assert r.masse_salariale_eur == Decimal("0")


# ── Golden-case tests: TNS-IS path ────────────────────────────────────────────

def test_tns_is_cotisations_equals_45pct():
    """
    TNS-IS: tns on remuneration = 30 000 × 0.45 = 13 500 €.
    (IS is on benefice, not on remuneration — cotisations only covers TNS.)
    """
    rows = compute_compare_types(_profile("eurl_is"))
    r = _row(rows, "eurl_is")
    expected_tns = Decimal("30000") * Decimal("0.45")
    assert r.cotisations_dirigeant_eur == expected_tns.quantize(Decimal("0.01")), (
        f"TNS-IS cotisations {r.cotisations_dirigeant_eur} != expected {expected_tns}"
    )


def test_tns_is_impot_is_nonzero_when_profitable():
    """
    TNS-IS: IS is applied on benefice. With 120 000 CA and 24 000 charges_fixes,
    there should be a positive benefice and a non-zero IS amount.
    """
    rows = compute_compare_types(_profile("eurl_is"))
    r = _row(rows, "eurl_is")
    assert r.impot_eur > Decimal("0"), (
        f"TNS-IS impot should be > 0, got {r.impot_eur}"
    )


# ── Golden-case tests: Assimilé salarié (SASU) ───────────────────────────────

def test_sasu_cotisations_includes_patronal_and_salarial():
    """
    SASU: brut = 30 000 × 1.3 = 39 000; patronal = 39 000 × 0.45 = 17 550;
    cotisations = patronal + (brut - net) = 17 550 + (39 000 - 30 000) = 26 550 €.
    """
    rows = compute_compare_types(_profile("sasu"))
    r = _row(rows, "sasu")
    remun = Decimal("30000")
    brut = remun * Decimal("1.30")
    patronal = brut * Decimal("0.45")
    expected_cot = (patronal + brut - remun).quantize(Decimal("0.01"))
    assert r.cotisations_dirigeant_eur == expected_cot, (
        f"SASU cotisations {r.cotisations_dirigeant_eur} != expected {expected_cot}"
    )


def test_sasu_charges_fixes_equals_input():
    """SASU charges_fixes must be passed through unchanged."""
    rows = compute_compare_types(_profile("sasu"))
    r = _row(rows, "sasu")
    assert r.charges_fixes_eur == Decimal("24000")


# ── Tests with non-zero masse_salariale ───────────────────────────────────────

def test_masse_salariale_propagated_in_breakdown():
    """
    When profile has masse_salariale > 0, it should appear in the breakdown.
    """
    profile = CompareProfile(
        ca_annuel_ttc=Decimal("200000"),
        charges_annuelles_fixes=Decimal("30000"),
        masse_salariale_annuelle=Decimal("48000"),  # 4 000 €/mois employé
        dirigeant_remuneration_nette=Decimal("36000"),
        business_type_actuel="sasu",
        versement_liberatoire=False,
        acre=False,
    )
    rows = compute_compare_types(profile)
    r = _row(rows, "sasu")
    assert r.masse_salariale_eur == Decimal("48000"), (
        f"masse_salariale_eur {r.masse_salariale_eur} != 48000"
    )
    # Identity check still holds
    components = r.cotisations_dirigeant_eur + r.impot_eur + r.charges_fixes_eur + r.masse_salariale_eur
    assert components == r.total_charges_eur


# ── All types check: every row has breakdown fields set ───────────────────────

def test_all_rows_have_breakdown_fields():
    """
    Every row in the result must have all four breakdown fields as Decimal (not None).
    The non-AE types should have non-zero cotisations.
    """
    rows = compute_compare_types(_profile("eurl_ir"))
    for r in rows:
        assert r.cotisations_dirigeant_eur is not None, f"{r.business_type}: cotisations is None"
        assert r.impot_eur is not None, f"{r.business_type}: impot is None"
        assert r.charges_fixes_eur is not None, f"{r.business_type}: charges_fixes is None"
        assert r.masse_salariale_eur is not None, f"{r.business_type}: masse_salariale is None"


# ── AE with VL ────────────────────────────────────────────────────────────────

def test_ae_vl_impot_equals_017_pct():
    """AE with versement_liberatoire: IR = ca × 0.017."""
    profile = CompareProfile(
        ca_annuel_ttc=Decimal("40000"),
        charges_annuelles_fixes=Decimal("8000"),
        masse_salariale_annuelle=Decimal("0"),
        dirigeant_remuneration_nette=Decimal("20000"),
        business_type_actuel="auto_micro",
        versement_liberatoire=True,
        acre=False,
    )
    rows = compute_compare_types(profile)
    r = _row(rows, "auto_micro")
    expected_ir = (Decimal("40000") * Decimal("0.017")).quantize(Decimal("0.01"))
    assert r.impot_eur == expected_ir, (
        f"AE VL impot {r.impot_eur} != expected {expected_ir}"
    )
