# TASK-1.1: UserProfile Model & API

**Status:** BACKLOG
**Sprint:** 1
**Priority:** P0 (critical)
**Est. effort:** 1.5 hr
**Dependencies:** TASK-0.2

## Context

The UserProfile is the central data model for Horizon 30 — everything else (life entities, investments, projections) hangs off it. It replaces ComCoi's Salon + SalonConfig with a single model that captures a French freelancer's financial identity. One user = one profile (1:1 relationship).

## Requirements

1. Create `backend/app/models/profile.py` with `UserProfile` model:

```python
class UserProfile(Base):
    __tablename__ = "user_profiles"

    id            = Column(UUID, primary_key=True, default=uuid4)
    user_id       = Column(UUID, ForeignKey("users.id"), unique=True, nullable=False)

    # Identity
    birth_date    = Column(Date, nullable=True)  # age derived; nullable for progressive onboarding
    target_retirement_age = Column(Integer, nullable=False, server_default="67")
    tax_parts     = Column(Numeric(3, 1), nullable=False, server_default="1.0")

    # Status
    status        = Column(String(20), nullable=False, server_default="ae")  # ae, eirl, eurl, sasu
    ae_activity_type = Column(String(50), nullable=False, server_default="bnc_non_reglementee")
    has_versement_liberatoire = Column(Boolean, nullable=False, server_default="true")

    # Revenue
    monthly_gross_ca = Column(Numeric(10, 2), nullable=True)  # null = not yet set
    growth_preset    = Column(String(20), nullable=False, server_default="moderate")
    growth_rate_custom = Column(Numeric(5, 4), nullable=True)  # only when preset=custom

    # Tax breaks
    cesu_annual    = Column(Numeric(10, 2), nullable=False, server_default="0")
    charity_annual = Column(Numeric(10, 2), nullable=False, server_default="0")

    # CAF
    caf_override_monthly = Column(Numeric(10, 2), nullable=True)  # null = auto-estimate

    # Monthly expenses (JSONB — flexible categories)
    monthly_expenses = Column(JSONB, nullable=False, server_default='{}')

    # Goal
    monthly_revenue_goal = Column(Numeric(10, 2), nullable=True)

    # World scenario
    world_scale = Column(String(20), nullable=False, server_default="moderate")

    # Status change simulation
    status_change_enabled = Column(Boolean, nullable=False, server_default="false")
    status_change_year    = Column(Integer, nullable=True)
    status_change_target  = Column(String(20), nullable=True)
    status_change_savings = Column(Numeric(10, 2), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

2. Create Pydantic schemas in `backend/app/schemas/profile.py`:
   - `ProfileRead` — all fields, plus computed `current_age: int | None` (from birth_date)
   - `ProfileWrite` — all writable fields
   - Validation: `tax_parts >= 1.0`, `target_retirement_age` between 50-85, `monthly_gross_ca >= 0`, expenses values all >= 0

3. Create router `backend/app/routers/profile.py`:
   - `GET /api/profile` — returns current user's profile (creates empty one if doesn't exist)
   - `PUT /api/profile` — updates profile fields (partial update — only send changed fields)
   - Both endpoints require auth token

4. Auto-create profile on first GET (upsert pattern) — don't require a separate "create profile" step

5. Alembic migration for `user_profiles` table

6. Register router in `main.py`

## Technical Approach

Follow ComCoi's pattern for SalonConfig: the profile is created lazily on first access. The GET endpoint does a `get_or_create` — if no profile exists for the authenticated user, create one with defaults and return it.

### Files to Create
- `backend/app/models/profile.py`
- `backend/app/schemas/profile.py`
- `backend/app/routers/profile.py`
- `backend/app/models/__init__.py` — add import
- `backend/app/main.py` — mount router
- `backend/alembic/versions/xxxx_add_user_profiles.py`

## Acceptance Criteria

- [ ] Migration creates `user_profiles` table
- [ ] `GET /api/profile` with auth token returns profile (creates if needed)
- [ ] `PUT /api/profile` updates fields and returns updated profile
- [ ] `current_age` computed correctly from `birth_date`
- [ ] Validation rejects: `tax_parts < 1`, `target_retirement_age > 85`, negative expense values
- [ ] Partial updates work (sending only `monthly_gross_ca` doesn't null out other fields)
- [ ] Unit tests: create, read, update, validation errors
- [ ] LEARNINGS.md updated if gotchas discovered

## Notes

- `monthly_expenses` is JSONB rather than separate columns because the categories may change. The Pydantic schema validates the structure.
- Status change fields live on the profile (not a separate model) because there's only ever one active simulation.
- `birth_date` is nullable for progressive onboarding — the user can start entering CA before filling in their birth date. The `current_age` field gracefully returns `None` when birth_date is null.
- The growth rate used in calculations is: `GROWTH_PRESETS[preset].rate` unless `preset == "custom"`, in which case use `growth_rate_custom`.
