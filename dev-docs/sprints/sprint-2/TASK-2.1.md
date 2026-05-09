# TASK-2.1: LifeEntity Model & CRUD API

**Status:** BACKLOG
**Sprint:** 2
**Priority:** P0 (critical)
**Est. effort:** 1.5 hr
**Dependencies:** TASK-1.1

## Context

The unified model for all "things in your life that cost money over time." Rather than separate tables for kids, pets, cars, and tech, we use a single `life_entities` table with an `entity_type` discriminator and a JSONB `cost_events` column. This keeps the schema flexible (easy to add "boat" or "horse" later) and the projection engine simple (it iterates one table, not four).

Each entity has a birth/acquisition date from which current age is derived, type-specific metadata in JSONB, and an ordered list of cost events with age brackets.

## Requirements

1. Create `backend/app/models/life_entity.py`:

```python
class LifeEntity(Base):
    __tablename__ = "life_entities"

    id          = Column(UUID, primary_key=True, default=uuid4)
    user_id     = Column(UUID, ForeignKey("users.id"), nullable=False, index=True)
    entity_type = Column(String(20), nullable=False)  # kid, pet, car, tech
    name        = Column(String(100), nullable=False)
    
    # Age derivation — birth date for kids/pets, acquisition date for cars/tech
    reference_date = Column(Date, nullable=False)
    
    # Type-specific metadata
    # kid: {} (no extra metadata needed)
    # pet: {"pet_type": "dog"|"cat"|"other"}
    # car: {"fuel_type": "petrol"|"diesel"|"electric"|"hybrid", "replace_cycle": 8, "replace_cost": 18000}
    # tech: {"device_type": "laptop"|"phone"|"tablet", "replace_cycle": 4, "replace_cost": 2500}
    metadata    = Column(JSONB, nullable=False, server_default='{}')
    
    # Cost events — the lifecycle
    # Array of: {
    #   "id": "uuid",
    #   "label": "Crèche",
    #   "from_age": 0, "to_age": 3,
    #   "amount": 500.00,
    #   "frequency": "monthly"|"annual"|"once",
    #   "source": "default"|"user"|"ai_suggested",
    #   "is_active": true
    # }
    cost_events = Column(JSONB, nullable=False, server_default='[]')
    
    is_active   = Column(Boolean, nullable=False, server_default="true")
    sort_order  = Column(Integer, nullable=False, server_default="0")
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

2. Create Pydantic schemas in `backend/app/schemas/life_entity.py`:

```python
class CostEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    label: str
    from_age: int = Field(ge=0)
    to_age: int = Field(ge=0)
    amount: Decimal = Field(ge=0)
    frequency: Literal["monthly", "annual", "once"]
    source: Literal["default", "user", "ai_suggested"] = "user"
    is_active: bool = True

class LifeEntityCreate(BaseModel):
    entity_type: Literal["kid", "pet", "car", "tech"]
    name: str = Field(max_length=100)
    reference_date: date
    metadata: dict = {}
    cost_events: list[CostEvent] = []  # empty = use canned defaults

class LifeEntityRead(BaseModel):
    id: UUID
    entity_type: str
    name: str
    reference_date: date
    current_age: int  # computed
    metadata: dict
    cost_events: list[CostEvent]
    is_active: bool

class LifeEntityUpdate(BaseModel):
    name: str | None = None
    reference_date: date | None = None
    metadata: dict | None = None
    cost_events: list[CostEvent] | None = None
    is_active: bool | None = None
```

3. Create CRUD router `backend/app/routers/life_entities.py`:
   - `GET /api/life-entities` — list all for authenticated user, ordered by entity_type then sort_order
   - `GET /api/life-entities?type=kid` — filter by type
   - `GET /api/life-entities/{id}` — single entity
   - `POST /api/life-entities` — create (if `cost_events` empty, populate from canned defaults — see TASK-2.2)
   - `PUT /api/life-entities/{id}` — update (partial)
   - `DELETE /api/life-entities/{id}` — soft delete (set `is_active = false`)
   - All endpoints require auth, scoped to current user

4. `current_age` computation in the Read schema: `(today - reference_date).days // 365`

5. Alembic migration for `life_entities` table

6. Register router in `main.py`

## Technical Approach

### Files to Create
- `backend/app/models/life_entity.py`
- `backend/app/schemas/life_entity.py`
- `backend/app/routers/life_entities.py`
- `backend/app/models/__init__.py` — add import
- `backend/app/main.py` — mount router
- `backend/alembic/versions/xxxx_add_life_entities.py`
- `backend/tests/test_life_entities.py`

### Design Decision: One Table vs Four
One table because:
1. The projection engine iterates all entities uniformly (cost_events have the same shape)
2. Adding new types (boat, motorcycle, rental property?) requires zero schema changes
3. The API surface is simpler (one CRUD set, filter by type)
4. The frontend "Vie" page queries one endpoint

The tradeoff: type-specific validation lives in Pydantic (metadata schema varies by type), not in the DB. That's fine — Pydantic is the validation layer.

## Acceptance Criteria

- [ ] Migration creates `life_entities` table with correct columns and indexes
- [ ] `POST /api/life-entities` creates entity and returns it with `current_age`
- [ ] `GET /api/life-entities` returns all entities for the user
- [ ] `GET /api/life-entities?type=kid` filters correctly
- [ ] `PUT /api/life-entities/{id}` updates partial fields (e.g. just cost_events)
- [ ] `DELETE /api/life-entities/{id}` soft-deletes (sets is_active=false)
- [ ] `current_age` computed correctly (kid born 2025-03-15, today is 2026-05-07 → age 1)
- [ ] Cost event validation: rejects negative amounts, invalid frequencies
- [ ] User A cannot access User B's entities
- [ ] Unit tests: create, read, update, delete, filter by type, age computation
- [ ] LEARNINGS.md updated

## Notes

- `cost_events` is a JSONB array, not a separate table. This means updates replace the entire array. For MVP this is fine — the array is small (5-10 events per entity). If we later need event-level history or audit trail, we'd normalize to a separate table.
- `sort_order` is for future drag-to-reorder on the frontend. Default 0, not used in MVP.
- The `source` field on cost events is important for the AI suggestions feature (Sprint 5) — it lets the UI distinguish "system suggested this" from "you added this."
- `from_age` and `to_age` are inclusive on both ends. A cost event with `from_age: 18, to_age: 18` fires once at age 18.
