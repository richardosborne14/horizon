"""
Tests for TASK-2.11.12: Service type split (Forfaits / À la carte).

Key behaviour:
  - ServiceCreate with type='carte' coerces addon_minutes to 0 regardless of input.
  - ServiceCreate with type='forfait' preserves addon_minutes as supplied.
  - ServiceUpdate with type='carte' coerces addon_minutes to 0.
  - ServiceUpdate with type='forfait' and no type change does NOT coerce.

These are pure Pydantic schema tests — no DB required.
"""

import pytest
from app.schemas.service import ServiceCreate, ServiceUpdate


class TestServiceCreateAddonCoercion:
    """TASK-2.11.12 — backend coercion of addon_minutes by service type."""

    def test_carte_with_addon_coerced_to_zero(self):
        """
        À la carte services must always have addon_minutes = 0.
        WHY: addon time (accueil, vestiaire, encaissement…) is a forfait concept.
        Billing extra time on a single à-la-carte service would be incorrect.
        """
        svc = ServiceCreate(
            name="Coupe homme",
            type="carte",
            duration_minutes=20,
            addon_minutes=10,  # should be coerced to 0
        )
        assert svc.addon_minutes == 0, (
            "addon_minutes must be coerced to 0 for carte services"
        )

    def test_carte_without_addon_stays_zero(self):
        """Carte with addon_minutes=0 (or default) stays 0."""
        svc = ServiceCreate(name="Coupe homme", type="carte", duration_minutes=20)
        assert svc.addon_minutes == 0

    def test_forfait_addon_preserved(self):
        """
        Forfait services preserve addon_minutes as supplied.
        WHY: the user explicitly set this value — it represents real time
        spent on accueil, finitions, etc. We must not override it.
        """
        svc = ServiceCreate(
            name="Forfait couleur",
            type="forfait",
            duration_minutes=75,
            addon_minutes=10,
        )
        assert svc.addon_minutes == 10

    def test_forfait_addon_zero_preserved(self):
        """Forfait with explicit addon_minutes=0 stays 0 — no auto-defaulting."""
        svc = ServiceCreate(
            name="Forfait coupe express",
            type="forfait",
            duration_minutes=30,
            addon_minutes=0,
        )
        assert svc.addon_minutes == 0

    def test_forfait_default_addon_is_zero(self):
        """
        When addon_minutes is not provided for a forfait, Pydantic default is 0.
        WHY: the frontend pre-fills 10 min by convention, but the backend must
        not force a value — if the frontend omits addon_minutes, 0 is correct.
        """
        svc = ServiceCreate(
            name="Forfait brushing",
            type="forfait",
            duration_minutes=30,
        )
        assert svc.addon_minutes == 0


class TestServiceUpdateAddonCoercion:
    """TASK-2.11.12 — coercion in ServiceUpdate when type changes to carte."""

    def test_update_to_carte_coerces_addon_to_zero(self):
        """
        When updating an existing service to type='carte', force addon_minutes=0.
        WHY: mirrors ServiceCreate behaviour — must be consistent at all entry points.
        """
        upd = ServiceUpdate(type="carte", addon_minutes=15)
        assert upd.addon_minutes == 0

    def test_update_to_forfait_preserves_addon(self):
        """Updating to forfait does not coerce addon_minutes."""
        upd = ServiceUpdate(type="forfait", addon_minutes=10)
        assert upd.addon_minutes == 10

    def test_update_addon_only_no_type_not_coerced(self):
        """
        Updating addon_minutes without changing type does NOT coerce.
        WHY: the validator only runs when type == 'carte'. If type is None
        (no type change), coercion must not happen — we don't know the current
        type from the update payload alone.
        """
        upd = ServiceUpdate(addon_minutes=5)
        assert upd.addon_minutes == 5

    def test_update_carte_no_explicit_addon_sets_zero(self):
        """
        Update to carte without explicit addon field: addon is coerced to 0.
        WHY: when a user changes a service type from forfait → carte, any existing
        addon time must be zeroed regardless of whether they included addon_minutes
        in the payload. The validator sees type=='carte' and coerces. The service
        layer uses model_dump(exclude_none=True), so addon_minutes=0 IS written.
        This is intentional — it's the whole point of the coercion.
        """
        upd = ServiceUpdate(type="carte", name="Retouche racines")
        # addon_minutes not sent → coerced to 0 because type == 'carte'
        assert upd.addon_minutes == 0

    def test_update_fields_independent(self):
        """ServiceUpdate with no type or addon change leaves both as None."""
        upd = ServiceUpdate(name="Forfait coupe femme modifié")
        assert upd.type is None
        assert upd.addon_minutes is None
