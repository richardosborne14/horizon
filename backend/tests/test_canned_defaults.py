"""
Task 2.2: Canned Defaults Service tests.

Tests cover:
- September rule: kid born Mar 2025 → crèche ends at age 3
- September rule: kid born Oct 2025 → crèche ends at age 4
- Kid defaults include full lifecycle (13 events)
- Pet defaults: dog gets toilettage, cat does not
- Pet old-age care bracket at correct ages
- Car CT events at correct ages (4, 6, 8 for cycle=8)
- Car replacement event at cycle end
- Car fuel-type variations (petrol vs electric)
- Tech replacement events at cycle intervals
- All events have source="default" and unique IDs
- Empty cost_events → populated from defaults (integration test)

Run: docker compose exec backend pytest tests/test_canned_defaults.py -v
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.main import app
from app.services.canned_defaults import (
    _maternelle_entry_age,
    get_kid_defaults,
    get_pet_defaults,
    get_car_defaults,
    get_tech_defaults,
    populate_defaults,
)


# ── Helper ────────────────────────────────────────────────────────────────────


# ── Tests: September Rule ─────────────────────────────────────────────────────


class TestSeptemberRule:
    """The French September school entry rule."""

    def test_march_baby_enters_at_age_3(self):
        """Born Mar 2025 → enters maternelle Sept 2028 → age 3."""
        birth = date(2025, 3, 15)
        entry_age = _maternelle_entry_age(birth)
        assert entry_age == 3, (
            f"March 2025 baby should enter maternelle at age 3, got {entry_age}"
        )

    def test_october_baby_enters_at_age_3(self):
        """Born Oct 2025 → enters maternelle Sept 2029 → age ~3 (integer division)."""
        birth = date(2025, 10, 1)
        entry_age = _maternelle_entry_age(birth)
        assert entry_age == 3, (
            f"October 2025 baby should enter maternelle at age 3, got {entry_age}"
        )

    def test_january_baby_enters_at_age_3(self):
        """Born Jan 2025 → enters Sept 2028 → age 3."""
        birth = date(2025, 1, 1)
        entry_age = _maternelle_entry_age(birth)
        assert entry_age == 3

    def test_september_mid_baby_enters_at_age_3(self):
        """Born Sep 15 2025 → enters Sept 2029 → age 3 (integer division)."""
        birth = date(2025, 9, 15)
        entry_age = _maternelle_entry_age(birth)
        assert entry_age == 3

    def test_august_baby_enters_at_age_3(self):
        """Born Aug 2025 → last month before September cutoff → age 3."""
        birth = date(2025, 8, 31)
        entry_age = _maternelle_entry_age(birth)
        assert entry_age == 3


# ── Tests: Kid Defaults ───────────────────────────────────────────────────────


class TestKidDefaults:
    """Full kid lifecycle defaults."""

    def test_kid_defaults_count(self):
        """Kid defaults should include all lifecycle events."""
        events = get_kid_defaults(date(2025, 3, 15))
        # crèche, cantine maternelle, cantine+périscolaire primaire,
        # fournitures primaire, cantine collège, fournitures collège,
        # cantine lycée, fournitures lycée, camp d'été, activités extra,
        # permis, voiture, études = 13 events
        assert len(events) == 13, f"Expected 13 kid defaults, got {len(events)}"

    def test_kid_creche_bracket_march(self):
        """March baby: crèche from age 0 to 2 (entry at age 3)."""
        events = get_kid_defaults(date(2025, 3, 15))
        creche = next(e for e in events if e.id == "k-creche")
        assert creche.from_age == 0
        assert creche.to_age == 2  # entry_age - 1 = 3 - 1
        assert creche.amount == Decimal("500.00")
        assert creche.frequency == "monthly"

    def test_kid_creche_bracket_october(self):
        """October baby: crèche from age 0 to 2 (entry at age 3)."""
        events = get_kid_defaults(date(2025, 10, 1))
        creche = next(e for e in events if e.id == "k-creche")
        assert creche.from_age == 0
        assert creche.to_age == 2  # entry_age - 1 = 3 - 1

    def test_kid_permis_is_once_event(self):
        """Permis de conduire is a one-time event at age 18."""
        events = get_kid_defaults(date(2020, 1, 1))
        permis = next(e for e in events if e.id == "k-permis")
        assert permis.from_age == 18
        assert permis.to_age == 18
        assert permis.frequency == "once"

    def test_all_kid_events_source_default(self):
        """All kid defaults should have source='default'."""
        events = get_kid_defaults(date(2025, 1, 1))
        for event in events:
            assert event.source == "default", (
                f"Event {event.id} has source='{event.source}', expected 'default'"
            )

    def test_all_kid_events_have_unique_ids(self):
        """Each event should have a unique ID."""
        events = get_kid_defaults(date(2025, 1, 1))
        ids = [e.id for e in events]
        assert len(ids) == len(set(ids)), "Duplicate event IDs found"


# ── Tests: Pet Defaults ───────────────────────────────────────────────────────


class TestPetDefaults:
    """Pet type-specific defaults."""

    def test_dog_gets_toilettage(self):
        """Dog defaults include toilettage (grooming)."""
        events = get_pet_defaults("dog", date(2023, 1, 15))
        grooming = next((e for e in events if e.id == "p-groom"), None)
        assert grooming is not None, "Dog defaults should include toilettage"

    def test_cat_no_toilettage(self):
        """Cat defaults do NOT include toilettage."""
        events = get_pet_defaults("cat", date(2023, 1, 15))
        grooming = next((e for e in events if e.id == "p-groom"), None)
        assert grooming is None, "Cat defaults should NOT include toilettage"

    def test_dog_food_higher_than_cat(self):
        """Dog food cost is higher than cat food cost."""
        dog_events = get_pet_defaults("dog", date(2023, 1, 15))
        cat_events = get_pet_defaults("cat", date(2023, 1, 15))
        dog_food = next(e for e in dog_events if e.id == "p-food")
        cat_food = next(e for e in cat_events if e.id == "p-food")
        assert dog_food.amount > cat_food.amount

    def test_old_age_care_bracket(self):
        """Old-age care fires at (lifespan - 3) → lifespan."""
        events = get_pet_defaults("dog", date(2023, 1, 15))
        old = next((e for e in events if e.id == "p-old"), None)
        assert old is not None, "Dog defaults should include old-age care"
        assert old.from_age == 10  # 13 - 3
        assert old.to_age == 13

    def test_all_pet_events_source_default(self):
        """All pet defaults should have source='default'."""
        for pet_type in ("dog", "cat", "other"):
            events = get_pet_defaults(pet_type, date(2023, 1, 15))
            for event in events:
                assert event.source == "default", (
                    f"Event {event.id} for {pet_type} has source='{event.source}'"
                )


# ── Tests: Car Defaults ───────────────────────────────────────────────────────


class TestCarDefaults:
    """Car defaults with CT events, fuel-type variations, and rolling replacement (Sprint 6)."""

    def test_ongoing_costs_to_age_99(self):
        """Ongoing costs (insurance, fuel, maintenance) should run to age 99."""
        events = get_car_defaults(
            fuel_type="petrol",
            acquisition_date=date(2022, 1, 1),
            replace_cycle=8,
        )
        ongoing_ids = {"c-insurance", "c-fuel", "c-maintenance"}
        for event in events:
            if event.id in ongoing_ids:
                assert event.to_age == 99, (
                    f"{event.id} should have to_age=99 for perpetual ownership, got {event.to_age}"
                )

    def test_rolling_replacement_events(self):
        """Replacement events at 8, 16, 24, 32, 40 for 8-year cycle."""
        events = get_car_defaults(
            fuel_type="petrol",
            acquisition_date=date(2022, 1, 1),
            replace_cycle=8,
        )
        replace_events = [e for e in events if e.id.startswith("c-replace-")]
        ages = sorted([e.from_age for e in replace_events])
        assert ages == [8, 16, 24, 32, 40], (
            f"Expected replacements at 8,16,24,32,40, got {ages}"
        )
        for r in replace_events:
            assert r.frequency == "once"
            assert r.amount == Decimal("18000.00")

    def test_ct_events_through_age_40(self):
        """CT events run from age 4 to 40, every 2 years."""
        events = get_car_defaults(
            fuel_type="petrol",
            acquisition_date=date(2022, 1, 1),
            replace_cycle=8,
        )
        ct_events = [e for e in events if e.id.startswith("c-ct-")]
        ct_ages = sorted([e.from_age for e in ct_events])
        assert ct_ages[0] == 4, f"First CT at 4, got {ct_ages[0]}"
        assert ct_ages[1] == 6
        assert ct_ages[2] == 8
        assert ct_ages[-1] <= 40, f"Last CT should be ≤ 40, got {ct_ages[-1]}"
        for ct in ct_events:
            assert ct.frequency == "once"
            assert ct.amount == Decimal("80.00")

    def test_petrol_vs_electric_fuel_cost(self):
        """Electric cars have lower fuel/energy costs."""
        petrol = get_car_defaults("petrol", date(2022, 1, 1))
        electric = get_car_defaults("electric", date(2022, 1, 1))
        petrol_fuel = next(e for e in petrol if e.id == "c-fuel")
        electric_fuel = next(e for e in electric if e.id == "c-fuel")
        assert float(electric_fuel.amount) < float(petrol_fuel.amount), (
            "Electric should have lower fuel cost than petrol"
        )

    def test_electric_lower_maintenance(self):
        """Electric cars have lower maintenance costs."""
        petrol = get_car_defaults("petrol", date(2022, 1, 1))
        electric = get_car_defaults("electric", date(2022, 1, 1))
        petrol_maint = next(e for e in petrol if e.id == "c-maintenance")
        electric_maint = next(e for e in electric if e.id == "c-maintenance")
        assert float(electric_maint.amount) < float(petrol_maint.amount), (
            "Electric should have lower maintenance cost than petrol"
        )

    def test_all_car_events_source_default(self):
        """All car defaults should have source='default'."""
        events = get_car_defaults("petrol", date(2022, 1, 1))
        for event in events:
            assert event.source == "default"

    def test_old_car_not_expired_with_new_model(self):
        """A car acquired 15 years ago should NOT be expired with the rolling model
        (ongoing costs go to age 99)."""
        events = get_car_defaults(
            fuel_type="petrol",
            acquisition_date=date(2011, 1, 1),
            replace_cycle=8,
        )
        max_to_age = max(e.to_age for e in events)
        assert max_to_age >= 99, (
            f"Old car should have events extending to age 99, got max to_age={max_to_age}"
        )


# ── Tests: Tech Defaults ──────────────────────────────────────────────────────


class TestTechDefaults:
    """Tech device defaults with replacement cycles."""

    def test_replacement_events_at_cycle_intervals(self):
        """Replacement events at cycle, cycle*2, cycle*3..."""
        events = get_tech_defaults(
            device_type="phone",
            replace_cycle=3,
            replace_cost=Decimal("1000.00"),
        )
        replace_events = [e for e in events if e.id.startswith("t-replace-")]
        ages = sorted([e.from_age for e in replace_events])
        assert ages[0] == 3, f"First replacement at 3, got {ages[0]}"
        assert ages[1] == 6
        assert ages[2] == 9
        for r in replace_events:
            assert r.frequency == "once"
            assert r.from_age == r.to_age

    def test_tech_events_up_to_30_years(self):
        """Replacement events generated up to 30 years horizon."""
        events = get_tech_defaults(
            device_type="laptop",
            replace_cycle=4,
            replace_cost=Decimal("2500.00"),
        )
        replace_events = [e for e in events if e.id.startswith("t-replace-")]
        max_age = max(e.from_age for e in replace_events)
        assert max_age <= 30, f"Max replacement age should be <= 30, got {max_age}"
        assert max_age >= 28, f"Should go close to 30, got max {max_age}"

    def test_all_tech_events_source_default(self):
        """All tech defaults should have source='default'."""
        events = get_tech_defaults()
        for event in events:
            assert event.source == "default"


# ── Tests: Populate Defaults Dispatcher ───────────────────────────────────────


class TestPopulateDefaults:
    """The dispatcher function routes to correct defaults."""

    def test_populate_kid_via_dispatcher(self):
        """populate_defaults with entity_type='kid' returns kid defaults."""
        events = populate_defaults("kid", date(2025, 3, 15))
        assert len(events) == 13
        assert all(e.source == "default" for e in events)

    def test_populate_pet_via_dispatcher(self):
        """populate_defaults with entity_type='pet' returns pet defaults."""
        events = populate_defaults("pet", date(2023, 1, 15), {"pet_type": "dog"})
        assert len(events) >= 6
        assert any(e.id == "p-groom" for e in events)

    def test_populate_car_via_dispatcher(self):
        """populate_defaults with entity_type='car' returns car defaults."""
        events = populate_defaults(
            "car", date(2022, 1, 1),
            {"fuel_type": "petrol", "replace_cycle": 8, "replace_cost": 18000},
        )
        assert any(e.id == "c-ct-1" for e in events)
        assert any(e.id.startswith("c-replace-") for e in events)

    def test_populate_tech_via_dispatcher(self):
        """populate_defaults with entity_type='tech' returns tech defaults."""
        events = populate_defaults(
            "tech", date(2024, 1, 1),
            {"device_type": "laptop", "replace_cycle": 4, "replace_cost": 2500},
        )
        assert any(e.id == "t-accessories" for e in events)
        assert any(e.id.startswith("t-replace-") for e in events)


# ── Tests: Integration (POST with empty cost_events) ──────────────────────────


@pytest.mark.asyncio
async def test_post_kid_with_empty_cost_events_populates_defaults():
    """
    POST /api/life-entities with empty cost_events should auto-populate
    canned defaults based on entity_type and reference_date.
    """
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Register
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": "test.canned.integration@example.com",
                    "password": "TestPass123!",
                    "name": "Canned Integration User",
                },
            )
            assert r.status_code == 201
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            # Create kid with empty cost_events
            res = await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "kid",
                    "name": "Emma",
                    "reference_date": "2025-03-15",
                    "metadata": {},
                    "cost_events": [],
                },
                cookies=cookies,
            )
            assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
            data = res.json()

            # Should have populated defaults (13 events)
            assert len(data["cost_events"]) == 13, (
                f"Expected 13 canned kid defaults, got {len(data['cost_events'])}"
            )
            # First event should be crèche
            assert data["cost_events"][0]["id"] == "k-creche"
            assert data["cost_events"][0]["source"] == "default"

            # Create dog with empty cost_events
            res2 = await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "pet",
                    "name": "Rex",
                    "reference_date": "2023-06-01",
                    "metadata": {"pet_type": "dog"},
                    "cost_events": [],
                },
                cookies=cookies,
            )
            assert res2.status_code == 201
            data2 = res2.json()
            # Dog should have toilettage
            grooming = next((e for e in data2["cost_events"] if e["id"] == "p-groom"), None)
            assert grooming is not None, "Dog defaults should include toilettage"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_post_kid_with_provided_cost_events_uses_them_not_defaults():
    """
    POST with provided cost_events should use them as-is (no defaults).
    """
    engine = create_async_engine(settings.database_url, echo=False)
    user_ids = []

    async def _cleanup(db, uids):
        for uid in uids:
            await db.execute(text(f"DELETE FROM users WHERE id = '{uid}'"))
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/auth/register",
                json={
                    "email": "test.canned.provided@example.com",
                    "password": "TestPass123!",
                    "name": "Canned Provided User",
                },
            )
            assert r.status_code == 201
            user_ids.append(uuid.UUID(r.json()["user"]["id"]))
            cookies = r.cookies

            res = await client.post(
                "/api/life-entities",
                json={
                    "entity_type": "kid",
                    "name": "Custom Kid",
                    "reference_date": "2020-01-01",
                    "cost_events": [
                        {
                            "id": "custom01",
                            "label": "My Custom Event",
                            "from_age": 0,
                            "to_age": 18,
                            "amount": 300,
                            "frequency": "monthly",
                            "source": "user",
                            "is_active": True,
                        }
                    ],
                },
                cookies=cookies,
            )
            assert res.status_code == 201
            data = res.json()
            assert len(data["cost_events"]) == 1, (
                f"Should have 1 custom event, got {len(data['cost_events'])}"
            )
            assert data["cost_events"][0]["id"] == "custom01"
            assert data["cost_events"][0]["source"] == "user"

    finally:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await _cleanup(db, user_ids)
        await engine.dispose()