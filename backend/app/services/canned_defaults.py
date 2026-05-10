"""
Canned Defaults Service — pre-populate life entity cost events.

When a user creates a life entity, the system generates type-specific
default cost events based on French real-world lifecycle knowledge:

- Kids: French school system stages with the September entry rule
- Pets: type-specific (dog/cat) with vaccination, sterilisation, old-age care
- Cars: fuel-type costs, CT inspections at fixed intervals, replacement
- Tech: periodic replacement events with accessories/repairs

All generated events are labeled source="default" so the UI can
distinguish them from user-added events.

Design notes:
- Amounts are national French averages (deliberately round — users adjust).
- The September rule is simplified; covers 95% of cases.
- CT events are individual "once" events at specific ages for simpler projection.
- Tech replacement costs are at 2026 prices; projection engine inflates them.
"""

from datetime import date
from decimal import Decimal

from app.schemas.life_entity import CostEvent


# ── Kids ──────────────────────────────────────────────────────────────────────


def _maternelle_entry_age(birth_date: date) -> int:
    """
    Compute the age at which a child enters maternelle.

    French rule: children enter maternelle the September of the year they turn 3.
    - Born Jan-Aug → enters September same year they turn 3 (age ~3)
    - Born Sep-Dec → enters September next year (age ~4)

    For cost event purposes, the crèche bracket runs from age 0 to
    this entry age, and cantine/maternelle costs start at this age.
    """
    turns_3_year = birth_date.year + 3
    if birth_date.month >= 9:  # Sep-Dec birth → enters the following year
        entry_year = turns_3_year + 1
    else:  # Jan-Aug birth → enters the year they turn 3
        entry_year = turns_3_year

    entry_date = date(entry_year, 9, 1)
    age_at_entry = (entry_date - birth_date).days // 365
    return age_at_entry  # Will be 3 or 4


def get_kid_defaults(birth_date: date) -> list[CostEvent]:
    """
    Generate default cost events for a child born on birth_date.

    Covers the full French school lifecycle from crèche through études supérieures.
    Uses the September rule to determine the crèche→maternelle transition age.
    """
    entry_age = _maternelle_entry_age(birth_date)
    events = []

    # Crèche / Garde (birth → maternelle entry)
    events.append(CostEvent(
        id="k-creche",
        label="Crèche / Garde d'enfant",
        from_age=0,
        to_age=entry_age - 1,
        amount=Decimal("300.00"),
        frequency="monthly",
        source="default",
    ))

    # Maternelle cantine (entry age → 6)
    events.append(CostEvent(
        id="k-cant-mat",
        label="Cantine maternelle",
        from_age=entry_age,
        to_age=5,
        amount=Decimal("100.00"),
        frequency="monthly",
        source="default",
    ))

    # Primaire cantine + périscolaire (6 → 11)
    events.append(CostEvent(
        id="k-cant-prim",
        label="Cantine + périscolaire primaire",
        from_age=6,
        to_age=11,
        amount=Decimal("150.00"),
        frequency="monthly",
        source="default",
    ))

    # Fournitures primaire (6 → 11)
    events.append(CostEvent(
        id="k-fourn-prim",
        label="Fournitures scolaires primaire",
        from_age=6,
        to_age=11,
        amount=Decimal("200.00"),
        frequency="annual",
        source="default",
    ))

    # Collège cantine (11 → 15)
    events.append(CostEvent(
        id="k-cant-coll",
        label="Cantine collège",
        from_age=11,
        to_age=15,
        amount=Decimal("100.00"),
        frequency="monthly",
        source="default",
    ))

    # Collège fournitures (11 → 15)
    events.append(CostEvent(
        id="k-fourn-coll",
        label="Fournitures scolaires collège",
        from_age=11,
        to_age=15,
        amount=Decimal("400.00"),
        frequency="annual",
        source="default",
    ))

    # Lycée cantine (15 → 18)
    events.append(CostEvent(
        id="k-cant-lyc",
        label="Cantine lycée",
        from_age=15,
        to_age=18,
        amount=Decimal("100.00"),
        frequency="monthly",
        source="default",
    ))

    # Lycée fournitures (15 → 18)
    events.append(CostEvent(
        id="k-fourn-lyc",
        label="Fournitures scolaires lycée",
        from_age=15,
        to_age=18,
        amount=Decimal("600.00"),
        frequency="annual",
        source="default",
    ))

    # Camp d'été (6 → 17)
    events.append(CostEvent(
        id="k-camp",
        label="Camp d'été / Colonie",
        from_age=6,
        to_age=17,
        amount=Decimal("800.00"),
        frequency="annual",
        source="default",
    ))

    # Activités extra-scolaires (6 → 18)
    events.append(CostEvent(
        id="k-extra",
        label="Activités extra-scolaires",
        from_age=6,
        to_age=18,
        amount=Decimal("100.00"),
        frequency="monthly",
        source="default",
    ))

    # Permis de conduire (18 → 18, once)
    events.append(CostEvent(
        id="k-permis",
        label="Permis de conduire",
        from_age=18,
        to_age=18,
        amount=Decimal("1800.00"),
        frequency="once",
        source="default",
    ))

    # Première voiture (18 → 18, once)
    events.append(CostEvent(
        id="k-voiture",
        label="Première voiture",
        from_age=18,
        to_age=18,
        amount=Decimal("5000.00"),
        frequency="once",
        source="default",
    ))

    # Études supérieures (18 → 23)
    events.append(CostEvent(
        id="k-etudes",
        label="Études supérieures (logement, frais, vie)",
        from_age=18,
        to_age=23,
        amount=Decimal("500.00"),
        frequency="monthly",
        source="default",
    ))

    return events


# ── Pets ──────────────────────────────────────────────────────────────────────


# Lifespan for old-age care bracket generation
PET_LIFESPAN = {
    "dog": 13,
    "cat": 18,
    "other": 12,
}


def get_pet_defaults(pet_type: str, birth_date: date) -> list[CostEvent]:
    """
    Generate default cost events for a pet.

    Type-specific:
    - Dog: gets toilettage (grooming), higher food cost
    - Cat: no toilettage, lower food cost
    - Other: generic defaults

    Old-age care bracket: (lifespan - 3) → lifespan
    """
    lifespan = PET_LIFESPAN.get(pet_type, 12)
    events = []

    # Nourriture (0 → lifespan)
    food_amount = {"dog": "600.00", "cat": "400.00", "other": "400.00"}.get(
        pet_type, "400.00"
    )
    events.append(CostEvent(
        id="p-food",
        label="Nourriture",
        from_age=0,
        to_age=lifespan,
        amount=Decimal(food_amount),
        frequency="annual",
        source="default",
    ))

    # Vaccins primo (0 → 1, once)
    events.append(CostEvent(
        id="p-vacc-primo",
        label="Vaccins primo",
        from_age=0,
        to_age=1,
        amount=Decimal("250.00"),
        frequency="once",
        source="default",
    ))

    # Rappel vaccins (1 → lifespan)
    events.append(CostEvent(
        id="p-vacc-rappel",
        label="Rappel vaccins",
        from_age=1,
        to_age=lifespan,
        amount=Decimal("80.00"),
        frequency="annual",
        source="default",
    ))

    # Stérilisation (0 → 1, once)
    steril_amount = {"dog": "300.00", "cat": "200.00", "other": "200.00"}.get(
        pet_type, "200.00"
    )
    events.append(CostEvent(
        id="p-steril",
        label="Stérilisation",
        from_age=0,
        to_age=1,
        amount=Decimal(steril_amount),
        frequency="once",
        source="default",
    ))

    # Vétérinaire annuel (1 → lifespan)
    events.append(CostEvent(
        id="p-vet",
        label="Vétérinaire annuel",
        from_age=1,
        to_age=lifespan,
        amount=Decimal("200.00"),
        frequency="annual",
        source="default",
    ))

    # Toilettage — dogs only
    if pet_type == "dog":
        events.append(CostEvent(
            id="p-groom",
            label="Toilettage",
            from_age=0,
            to_age=lifespan,
            amount=Decimal("300.00"),
            frequency="annual",
            source="default",
        ))

    # Soins vieux (lifespan - 3 → lifespan)
    if lifespan > 3:
        events.append(CostEvent(
            id="p-old",
            label="Soins vétérinaires renforcés (vieillesse)",
            from_age=lifespan - 3,
            to_age=lifespan,
            amount=Decimal("400.00"),
            frequency="annual",
            source="default",
        ))

    return events


# ── Cars ──────────────────────────────────────────────────────────────────────


# Annual fuel/energy costs by fuel type (2026 French averages)
CAR_FUEL_COSTS = {
    "petrol": "1200.00",
    "diesel": "1000.00",
    "electric": "400.00",
    "hybrid": "800.00",
}

# Annual maintenance costs by fuel type
CAR_MAINTENANCE_COSTS = {
    "petrol": "400.00",
    "diesel": "400.00",
    "electric": "200.00",
    "hybrid": "350.00",
}


def get_car_defaults(
    fuel_type: str,
    acquisition_date: date,
    replace_cycle: int = 8,
    replace_cost: Decimal = Decimal("18000.00"),
) -> list[CostEvent]:
    """
    Generate default cost events for a car using the rolling replacement model.

    The entity represents "I own a car" (perpetual ownership) rather than
    "I own this specific car." Ongoing costs (insurance, fuel, maintenance)
    use to_age=99 so they never expire. Replacement events and CT inspections
    are pre-generated at replace_cycle intervals through entity age 40.

    Sprint 6 (TASK-6.4): Fixed the bug where to_age=replace_cycle caused cars
    older than the cycle to contribute zero to the projection.
    """
    fuel = CAR_FUEL_COSTS.get(fuel_type, "1000.00")
    maintenance = CAR_MAINTENANCE_COSTS.get(fuel_type, "400.00")
    events = []

    # Assurance (0 → 99 — perpetual ownership)
    events.append(CostEvent(
        id="c-insurance",
        label="Assurance auto",
        from_age=0,
        to_age=99,
        amount=Decimal("600.00"),
        frequency="annual",
        source="default",
    ))

    # Carburant (0 → 99)
    events.append(CostEvent(
        id="c-fuel",
        label="Carburant / Énergie",
        from_age=0,
        to_age=99,
        amount=Decimal(fuel),
        frequency="annual",
        source="default",
    ))

    # Entretien courant (0 → 99)
    events.append(CostEvent(
        id="c-maintenance",
        label="Entretien courant (révisions, pneus, freins)",
        from_age=0,
        to_age=99,
        amount=Decimal(maintenance),
        frequency="annual",
        source="default",
    ))

    # CT events — every 2 years starting at age 4, through age 40
    ct_age = 4
    ct_count = 1
    while ct_age <= 40:
        events.append(CostEvent(
            id=f"c-ct-{ct_count}",
            label=f"Contrôle technique à {ct_age} ans",
            from_age=ct_age,
            to_age=ct_age,
            amount=Decimal("80.00"),
            frequency="once",
            source="default",
        ))
        ct_age += 2
        ct_count += 1

    # Replacement events at replace_cycle intervals through age 40
    replacement_age = replace_cycle
    replacement_count = 1
    while replacement_age <= 40:
        events.append(CostEvent(
            id=f"c-replace-{replacement_count}",
            label=f"Remplacement véhicule (tous les {replace_cycle} ans)",
            from_age=replacement_age,
            to_age=replacement_age,
            amount=replace_cost,
            frequency="once",
            source="default",
        ))
        replacement_age += replace_cycle
        replacement_count += 1

    return events


# ── Tech ──────────────────────────────────────────────────────────────────────


def get_tech_defaults(
    device_type: str = "laptop",
    acquisition_date: date = None,
    replace_cycle: int = 3,
    replace_cost: Decimal = Decimal("1200.00"),
) -> list[CostEvent]:
    """
    Generate default cost events for a tech device.

    - Replacement events at cycle, cycle*2, cycle*3... (up to 30 years out)
    - Accessories/repairs annual budget
    - Insurance/AppleCare for the first cycle

    Device type is only used for labeling; the primary parameters are
    replace_cycle and replace_cost.
    """
    events = []

    # Accessories / réparations (0 → 30)
    acc_amount = {"phone": "50.00", "laptop": "100.00", "tablet": "75.00"}.get(
        device_type, "75.00"
    )
    events.append(CostEvent(
        id="t-accessories",
        label="Accessoires / Réparations",
        from_age=0,
        to_age=30,
        amount=Decimal(acc_amount),
        frequency="annual",
        source="default",
    ))

    # Assurance / AppleCare (0 → cycle)
    ins_amount = {"phone": "60.00", "laptop": "100.00", "tablet": "80.00"}.get(
        device_type, "80.00"
    )
    events.append(CostEvent(
        id="t-insurance",
        label="Assurance / Garantie étendue",
        from_age=0,
        to_age=replace_cycle,
        amount=Decimal(ins_amount),
        frequency="annual",
        source="default",
    ))

    # Replacement events at cycle intervals
    replacement_age = replace_cycle
    replacement_count = 1
    while replacement_age <= 30:
        events.append(CostEvent(
            id=f"t-replace-{replacement_count}",
            label=f"Remplacement {device_type} (tous les {replace_cycle} ans)",
            from_age=replacement_age,
            to_age=replacement_age,
            amount=replace_cost,
            frequency="once",
            source="default",
        ))
        replacement_age += replace_cycle
        replacement_count += 1

    return events


# ── Dispatcher ────────────────────────────────────────────────────────────────


def populate_defaults(
    entity_type: str,
    reference_date: date,
    metadata: dict | None = None,
) -> list[CostEvent]:
    """
    Dispatch to the correct defaults function based on entity_type.

    Called by the life_entities router when POST creates an entity
    with an empty cost_events list.

    Args:
        entity_type: "kid", "pet", "car", or "tech"
        reference_date: birth date or acquisition date
        metadata: type-specific metadata dict (pet_type, fuel_type, etc.)

    Returns:
        List of CostEvent objects with source="default"
    """
    meta = metadata or {}

    if entity_type == "kid":
        return get_kid_defaults(reference_date)

    elif entity_type == "pet":
        pet_type = meta.get("pet_type", "other")
        return get_pet_defaults(pet_type, reference_date)

    elif entity_type == "car":
        fuel_type = meta.get("fuel_type", "petrol")
        replace_cycle = meta.get("replace_cycle", 8)
        replace_cost = Decimal(str(meta.get("replace_cost", 18000)))
        return get_car_defaults(
            fuel_type=fuel_type,
            acquisition_date=reference_date,
            replace_cycle=replace_cycle,
            replace_cost=replace_cost,
        )

    elif entity_type == "tech":
        device_type = meta.get("device_type", "laptop")
        replace_cycle = meta.get("replace_cycle", 3)
        replace_cost = Decimal(str(meta.get("replace_cost", 1200)))
        return get_tech_defaults(
            device_type=device_type,
            acquisition_date=reference_date,
            replace_cycle=replace_cycle,
            replace_cost=replace_cost,
        )

    return []