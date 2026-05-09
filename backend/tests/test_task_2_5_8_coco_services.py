"""
Tests for Task 2.5.8 — CoCo Service Recommendations.

Tests cover:
  - service_recommender.load_partner_services()
  - service_recommender.get_service_by_id()
  - service_recommender.evaluate_service_triggers() — all trigger conditions
  - coco_prompts.build_system_prompt() with relevant_services injection
  - coco_prompts._build_services_section()
  - coco_tools.TOOL_DEFINITIONS has get_services entry
  - coco_tools.TOOL_UI_LABELS has get_services entry

WHY these tests: trigger evaluation is pure business logic — no DB, no HTTP.
All tests are synchronous except the tool executor test which uses pytest-asyncio.
"""

import pytest

from app.services.service_recommender import (
    evaluate_service_triggers,
    get_service_by_id,
    load_partner_services,
)
from app.services.coco_prompts import build_system_prompt, _build_services_section
from app.services.coco_tools import TOOL_DEFINITIONS, TOOL_UI_LABELS


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def base_financial_data() -> dict:
    """Minimal financial data for a healthy salon — no triggers should fire."""
    return {
        "ca_ttc": 10_000.0,
        "marge_nette_pct": 0.18,      # 18% — above coaching/low-profitability threshold
        "has_employees": False,
        "employee_count": 0,
        "business_type": "auto_entrepreneur",
        "charges_by_category": {
            "energie_fluides": 300.0,      # 3% of CA — below trigger
            "assurance_pro": 100.0,        # has insurance
            "marketing_communication": 250.0,  # 2.5% of CA — above trigger
            "frais_generaux": 1400.0,      # 14% of CA — below trigger
        },
        "has_typical_month": True,
        "months_this_year": 6,
    }


# ── load_partner_services ─────────────────────────────────────────────────────

class TestLoadPartnerServices:
    """Tests for load_partner_services()."""

    def test_returns_list(self):
        """Should return a list of service dicts."""
        services = load_partner_services()
        assert isinstance(services, list)
        assert len(services) > 0

    def test_all_have_required_fields(self):
        """Every service should have id, name, category, triggers."""
        services = load_partner_services()
        for svc in services:
            assert "id" in svc, f"Service missing 'id': {svc}"
            assert "name" in svc, f"Service missing 'name': {svc}"
            assert "category" in svc, f"Service missing 'category': {svc}"
            assert "triggers" in svc, f"Service missing 'triggers': {svc}"

    def test_only_active_services(self):
        """All returned services should be is_active == True."""
        services = load_partner_services()
        for svc in services:
            assert svc.get("is_active", True) is True

    def test_expected_service_ids_present(self):
        """Key services from the catalog should be present."""
        services = load_partner_services()
        ids = {s["id"] for s in services}
        expected = {
            "compta_noly", "bulletin_salaire", "coaching",
            "assurance", "formation", "gestion_factures",
        }
        assert expected.issubset(ids), f"Missing IDs: {expected - ids}"


# ── get_service_by_id ─────────────────────────────────────────────────────────

class TestGetServiceById:
    """Tests for get_service_by_id()."""

    def test_known_id_returns_service(self):
        """Should return full service dict for a known ID."""
        svc = get_service_by_id("compta_noly")
        assert svc is not None
        assert svc["id"] == "compta_noly"
        assert "name" in svc

    def test_unknown_id_returns_none(self):
        """Should return None for an ID that doesn't exist."""
        svc = get_service_by_id("this_does_not_exist")
        assert svc is None

    def test_empty_id_returns_none(self):
        """Should return None for empty string."""
        svc = get_service_by_id("")
        assert svc is None


# ── evaluate_service_triggers ─────────────────────────────────────────────────

class TestEvaluateServiceTriggers:
    """Tests for evaluate_service_triggers() — one test per trigger condition."""

    def test_no_triggers_healthy_salon(self, base_financial_data):
        """A healthy salon with insurance and some marketing should not hit most triggers."""
        results = evaluate_service_triggers(base_financial_data)
        ids = {r["id"] for r in results}

        # These should NOT be triggered by base_financial_data
        assert "coaching" not in ids, "Coaching should not trigger for healthy salon"
        assert "bulletin_salaire" not in ids, "Payroll not needed with no employees"
        assert "assurance" not in ids, "Has insurance — should not trigger"
        assert "fournisseurs_energie" not in ids, "Energy below 4% threshold"

    def test_always_trigger(self):
        """Services with 'always' trigger should always appear."""
        results = evaluate_service_triggers({})
        ids = {r["id"] for r in results}
        # gestion_factures, formation, telephonie all have 'always' trigger
        always_services = [
            s for s in load_partner_services()
            if "always" in s.get("triggers", [])
        ]
        for svc in always_services:
            assert svc["id"] in ids, f"Service '{svc['id']}' with 'always' trigger missing"

    def test_has_employees_trigger(self):
        """has_employees trigger should fire for salons with employees."""
        data = {"has_employees": True, "employee_count": 2, "ca_ttc": 8000.0}
        results = evaluate_service_triggers(data)
        ids = {r["id"] for r in results}
        assert "bulletin_salaire" in ids

    def test_no_accountant_trigger(self):
        """no_accountant trigger fires when no accounting expense exists."""
        data = {
            "ca_ttc": 5000.0,
            "charges_by_category": {"loyer": 1000.0},  # No comptab key
        }
        results = evaluate_service_triggers(data)
        ids = {r["id"] for r in results}
        assert "compta_noly" in ids
        # Verify reason text is present and explains why
        compta = next(r for r in results if r["id"] == "compta_noly")
        assert "comptabilité" in compta["reason"].lower()

    def test_new_user_trigger(self):
        """new_user trigger fires when has_typical_month is False."""
        data = {"has_typical_month": False, "ca_ttc": 0.0}
        results = evaluate_service_triggers(data)
        ids = {r["id"] for r in results}
        # compta_retard has new_user trigger
        assert "compta_retard" in ids

    def test_high_frais_generaux_trigger(self):
        """frais_generaux_pct > 0.15 trigger fires when general expenses exceed 15%."""
        data = {
            "ca_ttc": 8000.0,
            "charges_by_category": {
                "frais_generaux": 1500.0,  # 18.75% — above 15%
            },
        }
        results = evaluate_service_triggers(data)
        ids = {r["id"] for r in results}
        assert "compta_noly" in ids
        compta = next(r for r in results if r["id"] == "compta_noly")
        assert "15%" in compta["reason"] or "frais généraux" in compta["reason"].lower()

    def test_frais_generaux_below_threshold_no_trigger(self):
        """frais_generaux_pct <= 0.15 should not trigger the accounting service."""
        data = {
            "ca_ttc": 10_000.0,
            "charges_by_category": {
                "frais_generaux": 1000.0,  # 10% — below threshold
                "comptab": 200.0,  # has accountant
            },
        }
        results = evaluate_service_triggers(data)
        ids = {r["id"] for r in results}
        # Should not fire high frais généraux trigger (accountant is there)
        # NOTE: compta_noly may still appear due to other triggers — just check reason
        if "compta_noly" in ids:
            compta = next(r for r in results if r["id"] == "compta_noly")
            assert "frais généraux" not in compta["reason"].lower() or "15%" not in compta["reason"]

    def test_high_energie_trigger(self):
        """energie_pct > 0.04 trigger fires when energy > 4% of CA."""
        data = {
            "ca_ttc": 5000.0,
            "charges_by_category": {"energie_fluides": 300.0},  # 6% — above 4%
        }
        results = evaluate_service_triggers(data)
        ids = {r["id"] for r in results}
        assert "fournisseurs_energie" in ids
        energie = next(r for r in results if r["id"] == "fournisseurs_energie")
        assert "énergie" in energie["reason"].lower()

    def test_low_marketing_trigger(self):
        """marketing_pct < 0.02 trigger fires when marketing < 2% of CA."""
        data = {
            "ca_ttc": 10_000.0,
            "charges_by_category": {"marketing": 100.0},  # 1% — below 2%
        }
        results = evaluate_service_triggers(data)
        ids = {r["id"] for r in results}
        assert "outils_marketing" in ids

    def test_low_profitability_trigger(self):
        """marge_nette_pct < 0.10 triggers coaching and low_profitability services."""
        data = {
            "ca_ttc": 8000.0,
            "marge_nette_pct": 0.06,  # 6% — below 10%
        }
        results = evaluate_service_triggers(data)
        ids = {r["id"] for r in results}
        assert "coaching" in ids
        coaching = next(r for r in results if r["id"] == "coaching")
        assert "marge" in coaching["reason"].lower() or "6%" in coaching["reason"]

    def test_no_insurance_trigger(self):
        """no_insurance_expense trigger fires when no assurance expense exists."""
        data = {
            "ca_ttc": 6000.0,
            "charges_by_category": {"loyer": 1000.0},  # No assurance key
        }
        results = evaluate_service_triggers(data)
        ids = {r["id"] for r in results}
        assert "assurance" in ids
        assurance = next(r for r in results if r["id"] == "assurance")
        assert "assurance" in assurance["reason"].lower()

    def test_insurance_present_no_trigger(self):
        """If assurance expense is present, no_insurance_expense should not trigger."""
        data = {
            "ca_ttc": 6000.0,
            "charges_by_category": {"assurance_pro": 150.0},
        }
        results = evaluate_service_triggers(data)
        ids = {r["id"] for r in results}
        assert "assurance" not in ids

    def test_societe_trigger(self):
        """business_type_is_societe triggers approbation_comptes for SARL/SAS/EURL."""
        for business_type in ("sarl", "sas", "eurl", "sasu"):
            data = {"business_type": business_type, "ca_ttc": 10_000.0}
            results = evaluate_service_triggers(data)
            ids = {r["id"] for r in results}
            assert "approbation_comptes" in ids, (
                f"approbation_comptes not triggered for {business_type}"
            )

    def test_non_societe_no_trigger(self):
        """auto_entrepreneur should NOT trigger approbation_comptes."""
        data = {"business_type": "auto_entrepreneur", "ca_ttc": 10_000.0}
        results = evaluate_service_triggers(data)
        ids = {r["id"] for r in results}
        assert "approbation_comptes" not in ids

    def test_cash_flow_issues_trigger(self):
        """Negative marge_nette_pct triggers cash flow issues service."""
        data = {
            "ca_ttc": 5000.0,
            "marge_nette_pct": -0.05,  # Negative margin
        }
        results = evaluate_service_triggers(data)
        ids = {r["id"] for r in results}
        assert "rapprochement_bancaire" in ids

    def test_employees_no_mutuelle_trigger(self):
        """has_employees AND no_mutuelle triggers mutuelle service."""
        data = {
            "ca_ttc": 8000.0,
            "has_employees": True,
            "employee_count": 1,
            "charges_by_category": {"salaires": 2000.0},  # No mutuelle key
        }
        results = evaluate_service_triggers(data)
        ids = {r["id"] for r in results}
        assert "mutuelle" in ids
        mutuelle = next(r for r in results if r["id"] == "mutuelle")
        assert "mutuelle" in mutuelle["reason"].lower()

    def test_employees_with_mutuelle_no_trigger(self):
        """If mutuelle expense exists, the trigger should not fire."""
        data = {
            "ca_ttc": 8000.0,
            "has_employees": True,
            "employee_count": 1,
            "charges_by_category": {
                "salaires": 2000.0,
                "mutuelle_entreprise": 150.0,  # Has mutuelle
            },
        }
        results = evaluate_service_triggers(data)
        ids = {r["id"] for r in results}
        assert "mutuelle" not in ids

    def test_result_has_reason_field(self, base_financial_data):
        """Every result dict must have a 'reason' key with non-empty French text."""
        # Use data that triggers at least one service
        data = {"ca_ttc": 5000.0, "charges_by_category": {}}  # No insurance → trigger
        results = evaluate_service_triggers(data)
        assert len(results) > 0
        for r in results:
            assert "reason" in r, f"Service {r['id']} missing 'reason' field"
            assert len(r["reason"]) > 10, f"Reason too short for {r['id']}: {r['reason']}"

    def test_conversation_only_triggers_not_auto_fired(self):
        """business_type_change_consideration and employee_issues never auto-fire."""
        # Check that creation_societe doesn't appear from auto-evaluation
        # (it only has business_type_change_consideration as trigger)
        data = {"ca_ttc": 10_000.0, "has_employees": True, "employee_count": 5}
        results = evaluate_service_triggers(data)
        ids = {r["id"] for r in results}
        # creation_societe and juridique have conversation-only triggers
        assert "creation_societe" not in ids, (
            "creation_societe should not auto-trigger (business_type_change_consideration only)"
        )

    def test_zero_ca_no_percentage_errors(self):
        """Zero CA should not cause ZeroDivisionError."""
        data = {"ca_ttc": 0.0, "marge_nette_pct": 0.0}
        # Should return without exception
        results = evaluate_service_triggers(data)
        assert isinstance(results, list)

    def test_results_sorted_by_sort_order(self):
        """Results should be sorted by sort_order from the JSON file."""
        data = {"ca_ttc": 5000.0, "charges_by_category": {}}  # Triggers many services
        results = evaluate_service_triggers(data)
        if len(results) >= 2:
            services = load_partner_services()
            id_to_order = {s["id"]: s.get("sort_order", 99) for s in services}
            orders = [id_to_order.get(r["id"], 99) for r in results]
            assert orders == sorted(orders), f"Results not sorted: {orders}"


# ── coco_prompts integration ──────────────────────────────────────────────────

class TestCocoPromptsServicesIntegration:
    """Tests for services injection in build_system_prompt()."""

    def test_no_services_no_services_section(self):
        """build_system_prompt without relevant_services has no services block."""
        prompt = build_system_prompt()
        assert "Services ComCoi" not in prompt
        assert "Règles pour les recommandations" not in prompt

    def test_empty_services_list_no_section(self):
        """Empty list should not inject a services section."""
        prompt = build_system_prompt(relevant_services=[])
        assert "Services ComCoi" not in prompt

    def test_relevant_services_injects_section(self):
        """Non-empty relevant_services list should inject the services section."""
        services = [
            {
                "id": "coaching",
                "name": "Coaching salon",
                "short_desc": "Accompagnement personnalisé",
                "category": "accompagnement",
                "cta_url": "",
                "reason": "marge nette = 6% (la moyenne secteur coiffure est de 15-20%)",
            }
        ]
        prompt = build_system_prompt(relevant_services=services)
        assert "Services ComCoi" in prompt
        assert "Règles pour les recommandations" in prompt
        assert "Coaching salon" in prompt
        assert "marge nette = 6%" in prompt

    def test_services_section_shows_links(self):
        """Service section should include /services/{id} links."""
        services = [
            {
                "id": "assurance",
                "name": "Assurance professionnelle",
                "short_desc": "Comparez vos assurances",
                "category": "protection",
                "cta_url": "",
                "reason": "aucune assurance détectée",
            }
        ]
        prompt = build_system_prompt(relevant_services=services)
        assert "/services/assurance" in prompt

    def test_services_capped_at_five(self):
        """Only 5 services should appear in the prompt even if more are provided."""
        services = [
            {
                "id": f"service_{i}",
                "name": f"Service {i}",
                "short_desc": f"Desc {i}",
                "category": "test",
                "cta_url": "",
                "reason": f"reason {i}",
            }
            for i in range(10)
        ]
        prompt = build_system_prompt(relevant_services=services)
        # Check that service_5 through service_9 are NOT in the prompt
        for i in range(5, 10):
            assert f"Service {i}" not in prompt

    def test_services_section_coexists_with_profile(self):
        """Services section should appear alongside profile section without breaking."""
        profile = {"user_name": "Marie", "salon_name": "Salon Marie"}
        services = [
            {
                "id": "formation",
                "name": "Formation professionnelle",
                "short_desc": "Formation gratuite",
                "category": "accompagnement",
                "cta_url": "",
                "reason": "service disponible pour tous les salons",
            }
        ]
        prompt = build_system_prompt(user_profile=profile, relevant_services=services)
        assert "Marie" in prompt
        assert "Formation professionnelle" in prompt
        # Both sections should be separated by the ---
        assert "---" in prompt


# ── coco_tools registration ───────────────────────────────────────────────────

class TestCocoToolsRegistration:
    """Tests that get_services is properly registered in coco_tools."""

    def test_get_services_in_tool_ui_labels(self):
        """get_services should have a French UI label."""
        assert "get_services" in TOOL_UI_LABELS
        assert "service" in TOOL_UI_LABELS["get_services"].lower()

    def test_get_services_in_tool_definitions(self):
        """get_services should be in TOOL_DEFINITIONS list."""
        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "get_services" in names

    def test_get_services_definition_structure(self):
        """get_services tool definition should have proper structure."""
        defn = next(t for t in TOOL_DEFINITIONS if t["name"] == "get_services")
        assert "description" in defn
        assert "input_schema" in defn
        schema = defn["input_schema"]
        assert "properties" in schema
        assert "service_id" in schema["properties"]
        assert "category" in schema["properties"]

    def test_total_tool_count(self):
        """Should have exactly 9 tools defined (8 existing + get_services)."""
        assert len(TOOL_DEFINITIONS) == 9, (
            f"Expected 9 tools, got {len(TOOL_DEFINITIONS)}: "
            f"{[t['name'] for t in TOOL_DEFINITIONS]}"
        )


# ── _tool_get_services executor (async) ──────────────────────────────────────
# WHY db=None: _tool_get_services is purely static (reads JSON, no DB).
# The AsyncSession parameter is part of the interface but not used here.

class TestToolGetServicesExecutor:
    """Tests for the _tool_get_services executor."""

    @pytest.mark.asyncio
    async def test_executor_returns_all_services(self):
        """Calling with no args should return all active services."""
        from app.services.coco_tools import _tool_get_services
        result = await _tool_get_services(
            {},
            db=None,
            user_id=None,
            screen_context=None,
        )
        assert result["found"] is True
        assert result["count"] > 0
        assert "services" in result

    @pytest.mark.asyncio
    async def test_executor_single_service(self):
        """Calling with service_id should return single service."""
        from app.services.coco_tools import _tool_get_services
        result = await _tool_get_services(
            {"service_id": "coaching"},
            db=None,
            user_id=None,
            screen_context=None,
        )
        assert result["found"] is True
        assert "service" in result
        assert result["service"]["id"] == "coaching"
        assert "/services/coaching" in result["service"]["page_url"]

    @pytest.mark.asyncio
    async def test_executor_unknown_service_id(self):
        """Unknown service_id should return found=False."""
        from app.services.coco_tools import _tool_get_services
        result = await _tool_get_services(
            {"service_id": "nonexistent_service"},
            db=None,
            user_id=None,
            screen_context=None,
        )
        assert result["found"] is False
        assert "reason" in result

    @pytest.mark.asyncio
    async def test_executor_category_filter(self):
        """Category filter should return only matching services."""
        from app.services.coco_tools import _tool_get_services
        result = await _tool_get_services(
            {"category": "comptabilite"},
            db=None,
            user_id=None,
            screen_context=None,
        )
        assert result["found"] is True
        for svc in result["services"]:
            assert svc["category"] == "comptabilite"

    @pytest.mark.asyncio
    async def test_executor_invalid_category(self):
        """Unknown category should return found=False with a helpful message."""
        from app.services.coco_tools import _tool_get_services
        result = await _tool_get_services(
            {"category": "categorie_qui_nexiste_pas"},
            db=None,
            user_id=None,
            screen_context=None,
        )
        assert result["found"] is False
        assert "Catégories disponibles" in result["reason"]
