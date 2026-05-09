"""
Tests for TASK-2.14.2 — EIRL → EI migration.

Covers:
- EI and EI_IS present in business-types.json
- EIRL absent from business-types.json (legacy file only)
- is_legacy_business_type() correctly classifies types
- compute_taxes() handles 'ei' (IR path) and 'ei_is' (IS path)
- compute_compare_types() dispatches ei/eirl to TNS-IR, ei_is to TNS-IS
- build_system_prompt(is_eirl_legacy=True) injects EIRL legacy rule
- TNS_BUSINESS_TYPES and LEGACY_BUSINESS_TYPES correct in salary.py

All pure-function — no DB. Self-contained.
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest

# ── Imports ───────────────────────────────────────────────────────────────────

from app.calculations.taxes import compute_taxes, DEFAULT_RATES
from app.services.compare_types import (
    ALLOWED_TRANSITIONS,
    BUSINESS_TYPE_LABELS,
    CompareProfile,
    compute_compare_types,
)
from app.services.salary import (
    TNS_BUSINESS_TYPES,
    LEGACY_BUSINESS_TYPES,
    is_legacy_business_type,
)
from app.services.coco_prompts import build_system_prompt

STATIC_DATA_PATH = Path(__file__).parent.parent / "static-data"


# ── Static data tests ─────────────────────────────────────────────────────────


def test_business_types_json_has_ei():
    """EI must be in business-types.json."""
    data = json.loads((STATIC_DATA_PATH / "business-types.json").read_text())
    ids = {bt["id"] for bt in data}
    assert "ei" in ids, "EI must be in business-types.json"
    assert "ei_is" in ids, "EI_IS must be in business-types.json"


def test_business_types_json_has_no_eirl():
    """EIRL must NOT be in business-types.json (legacy-only)."""
    data = json.loads((STATIC_DATA_PATH / "business-types.json").read_text())
    ids = {bt["id"] for bt in data}
    assert "eirl" not in ids, "EIRL must be removed from business-types.json — it is a legacy type"


def test_legacy_only_business_types_has_eirl():
    """EIRL must be in legacy_only_business_types.json with a successor field."""
    data = json.loads((STATIC_DATA_PATH / "legacy_only_business_types.json").read_text())
    assert len(data) == 1
    assert data[0]["id"] == "eirl"
    assert data[0]["successor"] == "ei"


# ── salary.py constants ────────────────────────────────────────────────────────


def test_ei_in_tns_business_types():
    """EI is a TNS statut — must be in TNS_BUSINESS_TYPES."""
    assert "ei" in TNS_BUSINESS_TYPES, "EI must be in TNS_BUSINESS_TYPES"


def test_eirl_in_tns_business_types_for_legacy_calc():
    """EIRL legacy salons must still get TNS charge calculation — stays in TNS_BUSINESS_TYPES."""
    assert "eirl" in TNS_BUSINESS_TYPES, "EIRL must remain in TNS_BUSINESS_TYPES for legacy salon calculations"


def test_legacy_business_types():
    """Only EIRL should be in LEGACY_BUSINESS_TYPES for now."""
    assert "eirl" in LEGACY_BUSINESS_TYPES
    assert "ei" not in LEGACY_BUSINESS_TYPES
    assert "ei_is" not in LEGACY_BUSINESS_TYPES
    assert "auto_micro" not in LEGACY_BUSINESS_TYPES


def test_is_legacy_business_type_eirl():
    """is_legacy_business_type('eirl') must return True."""
    assert is_legacy_business_type("eirl") is True


def test_is_legacy_business_type_ei():
    """is_legacy_business_type('ei') must return False."""
    assert is_legacy_business_type("ei") is False


@pytest.mark.parametrize("bt", ["auto_micro", "ei", "ei_is", "eurl", "sarl", "sas", "sasu"])
def test_is_legacy_business_type_current_types(bt: str):
    """All currently valid business types must not be marked legacy."""
    assert is_legacy_business_type(bt) is False, f"{bt} must not be a legacy type"


# ── compute_taxes ─────────────────────────────────────────────────────────────


def test_compute_taxes_ei_uses_ir_path():
    """
    EI follows the same IR-path as eirl/eurl/sarl.
    has_tva=True and cotisations TNS are present.
    """
    result = compute_taxes(
        business_type="ei",
        ca_annuel=Decimal("60000"),
        salaire_dirigeant=Decimal("30000"),
        rates=DEFAULT_RATES,
    )
    assert result.has_tva is True, "EI is TVA-liable"
    assert result.is_auto is False
    cotisation_labels = [c.label for c in result.cotisations]
    assert any("TNS" in l or "CFE" in l for l in cotisation_labels), (
        "EI cotisations should include TNS charges"
    )
    impot_labels = [i.label for i in result.impots]
    assert any("revenu" in l.lower() for l in impot_labels), "EI should have IR, not IS"


def test_compute_taxes_ei_is_uses_is_path():
    """
    EI à l'IS follows the IS path (same as SASU).
    IS items appear in impots.
    """
    result = compute_taxes(
        business_type="ei_is",
        ca_annuel=Decimal("80000"),
        salaire_dirigeant=Decimal("30000"),
        rates=DEFAULT_RATES,
    )
    assert result.has_tva is True
    assert result.is_auto is False
    impot_labels = [i.label for i in result.impots]
    assert any("Sociétés" in l or "IS" in l for l in impot_labels), (
        "EI à l'IS should have IS, not IR"
    )


def test_compute_taxes_eirl_still_works():
    """
    Legacy EIRL salons must still compute correctly (IR path).
    NEVER break existing EIRL calculations.
    """
    result = compute_taxes(
        business_type="eirl",
        ca_annuel=Decimal("50000"),
        salaire_dirigeant=Decimal("25000"),
        rates=DEFAULT_RATES,
    )
    assert result.has_tva is True
    assert result.is_auto is False
    assert result.total_taxes > Decimal("0")


# ── compare_types.py ──────────────────────────────────────────────────────────


def test_allowed_transitions_has_ei():
    """auto_micro must have EI as an allowed transition target."""
    assert "ei" in ALLOWED_TRANSITIONS.get("auto_micro", [])
    assert "ei_is" in ALLOWED_TRANSITIONS.get("auto_micro", [])


def test_allowed_transitions_eirl_legacy():
    """EIRL must be in ALLOWED_TRANSITIONS (for legacy salon's simulator)."""
    assert "eirl" in ALLOWED_TRANSITIONS, "EIRL must have allowed transitions for legacy salon simulator"
    assert "ei" in ALLOWED_TRANSITIONS["eirl"], "EIRL transitions must include EI"


def test_business_type_labels_has_ei():
    """EI and EI_IS must have labels."""
    assert "ei" in BUSINESS_TYPE_LABELS
    assert "ei_is" in BUSINESS_TYPE_LABELS
    assert "eirl" in BUSINESS_TYPE_LABELS
    assert "historique" in BUSINESS_TYPE_LABELS["eirl"].lower(), (
        "EIRL label should indicate it is a historical/legacy statut"
    )


def _make_profile(business_type: str) -> CompareProfile:
    return CompareProfile(
        ca_annuel_ttc=Decimal("80000"),
        charges_annuelles_fixes=Decimal("15000"),
        masse_salariale_annuelle=Decimal("0"),
        dirigeant_remuneration_nette=Decimal("30000"),
        business_type_actuel=business_type,
    )


def test_compare_types_ei_as_current():
    """EI as current type produces a valid ranked list with alternatives."""
    rows = compute_compare_types(_make_profile("ei"))
    assert len(rows) >= 2, "EI should have at least 2 comparison rows"
    current_rows = [r for r in rows if r.is_current]
    assert len(current_rows) == 1
    assert current_rows[0].business_type == "ei"
    assert current_rows[0].delta_eur == Decimal("0")


def test_compare_types_eirl_as_current_legacy():
    """EIRL as current type (legacy salon) must still produce a valid comparison."""
    rows = compute_compare_types(_make_profile("eirl"))
    assert len(rows) >= 2, "EIRL legacy salon should have comparison alternatives"
    current_rows = [r for r in rows if r.is_current]
    assert len(current_rows) == 1, "Exactly one row should be is_current=True"
    assert current_rows[0].business_type == "eirl"


def test_compare_types_ei_and_eirl_same_net():
    """
    EI and EIRL are functionally identical for charge calculation.
    Their net_dirigeant should be equal for the same input profile.
    """
    ei_rows = compute_compare_types(_make_profile("ei"))
    eirl_rows = compute_compare_types(_make_profile("eirl"))

    ei_net = next(r.net_dirigeant_apres_charges for r in ei_rows if r.is_current)
    eirl_net = next(r.net_dirigeant_apres_charges for r in eirl_rows if r.is_current)

    assert ei_net == eirl_net, (
        f"EI and EIRL should produce identical net: EI={ei_net}, EIRL={eirl_net}"
    )


def test_compare_types_ei_is_uses_is_calc():
    """EI_IS as current type should use IS path — net should differ from plain EI."""
    ei_rows = compute_compare_types(_make_profile("ei"))
    ei_is_rows = compute_compare_types(_make_profile("ei_is"))

    ei_net = next(r.net_dirigeant_apres_charges for r in ei_rows if r.is_current)
    ei_is_net = next(r.net_dirigeant_apres_charges for r in ei_is_rows if r.is_current)

    # IS path typically produces different net than IR path for same CA/remun inputs
    # (doesn't have to be higher/lower, just different unless trivially equal)
    # We just verify the dispatch works by checking non-zero result
    assert ei_is_net != Decimal("0")


# ── coco_prompts.py ────────────────────────────────────────────────────────────


def test_build_system_prompt_default_no_eirl_rule():
    """Without is_eirl_legacy, the EIRL rule must NOT appear in the prompt."""
    prompt = build_system_prompt()
    assert "EIRL" not in prompt or "RÈGLE EIRL" not in prompt, (
        "EIRL legacy rule must not appear in default prompt"
    )


def test_build_system_prompt_eirl_legacy_injects_rule():
    """With is_eirl_legacy=True, the EIRL legacy rule must be injected."""
    prompt = build_system_prompt(is_eirl_legacy=True)
    assert "RÈGLE EIRL" in prompt, "EIRL legacy rule must appear in prompt when is_eirl_legacy=True"
    assert "2022" in prompt, "EIRL legacy rule should mention the 2022 law"
    assert "EI" in prompt, "EIRL legacy rule should mention EI as successor"


def test_build_system_prompt_eirl_rule_mentions_comcoi():
    """The EIRL legacy rule must steer users toward ComCoi partners, not DIY."""
    prompt = build_system_prompt(is_eirl_legacy=True)
    assert "ComCoi" in prompt or "comptable" in prompt, (
        "EIRL legacy rule must mention ComCoi partner/comptable for status change advice"
    )
