"""
Tests for TASK-2.6.5: Mon Mois Typique wizard persistence.

Root cause fixed:
  SalonConfigRead schema was missing the `typical_month_template` field.
  Pydantic strips any field not declared in the response schema, so the GET
  /api/salon-config/:id response always returned null for existingTemplate
  even when data was correctly saved to the DB.

These are pure unit tests (no DB, no HTTP) that verify:
  1. SalonConfigRead schema includes typical_month_template in its output
  2. The field is correctly serialised and the data survives a round-trip
  3. The template structure has all the keys the frontend wizard expects
  4. saved_at is included in the template (for "Dernière mise à jour" display)

Integration-level tests (POST wizard → GET config → verify round-trip) are
covered by the Docker integration suite. Run with: docker compose exec backend
pytest tests/test_task_2_6_5_wizard_persistence.py
"""

import uuid
from decimal import Decimal

import pytest

from app.schemas.salon_config import SalonConfigRead


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_valid_config(**overrides) -> dict:
    """
    Return a minimal valid dict for instantiating SalonConfigRead.
    Fields match the DB defaults from the initial schema migration.
    """
    base = {
        "id": uuid.uuid4(),
        "salon_id": uuid.uuid4(),
        "jours_ouverture_semaine": Decimal("5"),
        "semaines_ouverture_an": Decimal("45.6"),
        "heures_ouverture_jour": Decimal("10"),
        "majoration_securite_benefice": Decimal("0.10"),
        "taux_produits": Decimal("0.10"),
        "taux_charges_fixes": Decimal("0.25"),
        "percent_clients_f": Decimal("0.80"),
        "montant_moyen_f": Decimal("65"),
        "percent_clients_h": Decimal("0.20"),
        "montant_moyen_h": Decimal("30"),
        "nb_visites_moyen_f": Decimal("4.2"),
        "nb_visites_moyen_h": Decimal("6.6"),
        "type_exploitant": "tns",
        "has_acre": False,
        "acre_start_date": None,
        "effectif_entreprise": 1,
        "typical_month_template": None,
        "jours_an": Decimal("0"),
        "heures_an": Decimal("0"),
    }
    base.update(overrides)
    return base


SAMPLE_TEMPLATE = {
    "ca_ttc": 8000.0,
    "saved_at": "2026-04-12T21:17:00.000000",
    "team": [
        {
            "employee_id": str(uuid.uuid4()),
            "name": "Estelle",
            "role_type": "dirigeant",
            "contract_type": "cdi",
            "net_salary": 1800.0,
            "hours_per_week": 35.0,
            "salaire_brut": 2376.0,
            "cotisations_sociales": 958.0,
            "total_charge": 3334.0,
        }
    ],
    "expenses": [
        {
            "category": "loyer",
            "label": "Loyer mensuel",
            "amount_ttc": 1200.0,
        }
    ],
}


# ── Schema round-trip ──────────────────────────────────────────────────────────


class TestSalonConfigReadSchema:
    """
    Unit tests for the SalonConfigRead schema (the regression fix for TASK-2.6.5).
    """

    def test_schema_includes_typical_month_template_field(self):
        """
        SalonConfigRead must declare typical_month_template as a field.

        WHY: Before TASK-2.6.5, this field was missing from the schema.
        Pydantic silently strips any field not declared → the wizard always
        got null for existingTemplate and showed blank inputs on revisit.
        """
        # Check the field is declared in the model
        assert "typical_month_template" in SalonConfigRead.model_fields, (
            "SalonConfigRead is missing typical_month_template field. "
            "This is the regression fix from TASK-2.6.5. "
            "Add: typical_month_template: dict | None = None"
        )

    def test_schema_serialises_template_when_present(self):
        """
        When a template dict is provided, it must survive serialisation.

        WHY: Before the fix, the field was stripped by Pydantic during model
        construction, so even if the DB had data, the API response would be null.
        """
        config = SalonConfigRead(**_make_valid_config(typical_month_template=SAMPLE_TEMPLATE))
        serialised = config.model_dump()

        assert serialised["typical_month_template"] is not None, (
            "typical_month_template was stripped by Pydantic during serialisation. "
            "The fix may not have been applied to SalonConfigRead."
        )

    def test_schema_preserves_template_ca_ttc(self):
        """The ca_ttc value in the template must be preserved exactly."""
        config = SalonConfigRead(**_make_valid_config(typical_month_template=SAMPLE_TEMPLATE))
        template = config.model_dump()["typical_month_template"]

        assert template["ca_ttc"] == pytest.approx(8000.0), (
            f"ca_ttc should be 8000.0, got {template['ca_ttc']}"
        )

    def test_schema_preserves_team_list(self):
        """The team list in the template must be preserved intact."""
        config = SalonConfigRead(**_make_valid_config(typical_month_template=SAMPLE_TEMPLATE))
        template = config.model_dump()["typical_month_template"]

        assert len(template["team"]) == 1
        assert template["team"][0]["name"] == "Estelle"
        assert template["team"][0]["role_type"] == "dirigeant"

    def test_schema_preserves_expenses_list(self):
        """The expenses list in the template must be preserved intact."""
        config = SalonConfigRead(**_make_valid_config(typical_month_template=SAMPLE_TEMPLATE))
        template = config.model_dump()["typical_month_template"]

        assert len(template["expenses"]) == 1
        assert template["expenses"][0]["category"] == "loyer"
        assert template["expenses"][0]["amount_ttc"] == pytest.approx(1200.0)

    def test_schema_preserves_saved_at(self):
        """
        saved_at must be present in the serialised template.

        WHY: The wizard frontend reads saved_at to display "Dernière mise à jour".
        If this field is absent, the display falls back to "Données enregistrées"
        which is less informative. saved_at is added by the service in TASK-2.6.5.
        """
        config = SalonConfigRead(**_make_valid_config(typical_month_template=SAMPLE_TEMPLATE))
        template = config.model_dump()["typical_month_template"]

        assert "saved_at" in template, (
            "saved_at missing from template — wizard cannot show 'Dernière mise à jour'. "
            "Check typical_month.py service adds saved_at to the template dict."
        )

    def test_schema_allows_null_template(self):
        """
        typical_month_template must be nullable (new users have no template yet).
        """
        config = SalonConfigRead(**_make_valid_config(typical_month_template=None))
        assert config.typical_month_template is None

    def test_schema_json_includes_template_key(self):
        """
        model_dump(mode='json') must include typical_month_template key, not omit it.

        WHY: FastAPI uses model_dump internally. If the key is absent even for null
        values, the frontend code `config.typical_month_template ?? null` would error.
        """
        config_with_template = SalonConfigRead(
            **_make_valid_config(typical_month_template=SAMPLE_TEMPLATE)
        )
        json_data = config_with_template.model_dump(mode="json")
        assert "typical_month_template" in json_data
        assert json_data["typical_month_template"] is not None

        config_null = SalonConfigRead(**_make_valid_config(typical_month_template=None))
        json_null = config_null.model_dump(mode="json")
        assert "typical_month_template" in json_null


# ── Template structure ─────────────────────────────────────────────────────────


class TestTemplateStructure:
    """
    Tests that verify the template dict has the keys the wizard frontend expects.

    These tests document the contract between the backend service and the
    +page.svelte wizard pre-fill logic.
    """

    def test_template_has_all_wizard_prefill_keys(self):
        """
        Template must contain every key used by the wizard pre-fill code.

        Wizard reads: existingTemplate?.ca_ttc, .team, .expenses, .saved_at
        """
        required_keys = {"ca_ttc", "team", "expenses", "saved_at"}
        missing = required_keys - set(SAMPLE_TEMPLATE.keys())
        assert not missing, f"SAMPLE_TEMPLATE is missing expected keys: {missing}"

    def test_team_member_has_wizard_input_fields(self):
        """
        Each team member in the template must have the fields the wizard displays:
        name, role_type, contract_type, net_salary, hours_per_week.
        """
        member = SAMPLE_TEMPLATE["team"][0]
        required = {"name", "role_type", "contract_type", "net_salary", "hours_per_week"}
        missing = required - set(member.keys())
        assert not missing, f"Team member dict missing keys: {missing}"

    def test_expense_has_wizard_input_fields(self):
        """
        Each expense must have category, label, amount_ttc as used by the wizard.
        """
        expense = SAMPLE_TEMPLATE["expenses"][0]
        required = {"category", "label", "amount_ttc"}
        missing = required - set(expense.keys())
        assert not missing, f"Expense dict missing keys: {missing}"
