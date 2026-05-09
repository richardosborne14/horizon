# TASK-3.1: Investment Vehicles & Allocation Model

**Status:** BACKLOG
**Sprint:** 3
**Priority:** P0 (critical)
**Est. effort:** 1.5 hr
**Dependencies:** TASK-1.1

## Context

French investment vehicles each have distinct tax treatment, ceilings, risk profiles, and historical return rates. The user needs to see all their options, allocate monthly contributions, and track existing balances. The projection engine (Sprint 4) compounds these balances over 30 years.

Seven vehicles cover the spectrum from zero-risk (Livret A) to medium-risk (PEA, SCPI) to retirement-locked (PER). Each vehicle's specs are constants (like AE rates); the user data is balances and monthly contributions.

## Requirements

1. Create `backend/app/calculations/vehicles.py` — vehicle specs as constants:

```python
from decimal import Decimal

VEHICLE_SPECS: dict[str, dict] = {
    "livret_a": {
        "label": "Livret A",
        "description": "Épargne réglementée, capital garanti. Disponible à tout moment.",
        "rate": Decimal("0.025"),
        "tax_free": True,
        "tax_rate": Decimal("0"),
        "ceiling": Decimal("22950"),
        "risk": "Aucun",
        "color": "#22d3ee",
        "liquidity": "Immédiate",
    },
    "ldds": {
        "label": "LDDS",
        "description": "Comme le Livret A, plafonné plus bas. Capital garanti.",
        "rate": Decimal("0.025"),
        "tax_free": True,
        "tax_rate": Decimal("0"),
        "ceiling": Decimal("12000"),
        "risk": "Aucun",
        "color": "#06b6d4",
        "liquidity": "Immédiate",
    },
    "av_euro": {
        "label": "Assurance Vie (fonds €)",
        "description": "Capital garanti sur le fonds euros. Rendement faible mais sûr. Fiscalité avantageuse après 8 ans.",
        "rate": Decimal("0.027"),
        "tax_free": False,
        "tax_rate": Decimal("0.172"),  # PFU 17.2% prélèvements sociaux (after 8yr + 4600€ abattement)
        "ceiling": None,
        "risk": "Très faible",
        "color": "#a78bfa",
        "liquidity": "Quelques jours",
    },
    "av_uc": {
        "label": "Assurance Vie (UC)",
        "description": "Unités de compte — actions, obligations, immobilier. Rendement potentiel plus élevé, capital non garanti.",
        "rate": Decimal("0.060"),
        "tax_free": False,
        "tax_rate": Decimal("0.172"),
        "ceiling": None,
        "risk": "Moyen",
        "color": "#8b5cf6",
        "liquidity": "Quelques jours",
    },
    "pea": {
        "label": "PEA",
        "description": "Plan d'Épargne en Actions. Exonéré d'IR après 5 ans (17,2% PS uniquement). Actions européennes.",
        "rate": Decimal("0.070"),
        "tax_free": False,
        "tax_rate": Decimal("0.172"),
        "ceiling": Decimal("150000"),
        "risk": "Moyen-élevé",
        "color": "#f59e0b",
        "liquidity": "5 ans pour avantage fiscal",
    },
    "scpi": {
        "label": "SCPI",
        "description": "Pierre-papier. Revenus immobiliers sans gestion. Rendement régulier, liquidité limitée.",
        "rate": Decimal("0.045"),
        "tax_free": False,
        "tax_rate": Decimal("0.300"),  # IR + PS on revenus fonciers
        "ceiling": None,
        "risk": "Moyen",
        "color": "#10b981",
        "liquidity": "Plusieurs mois",
    },
    "per": {
        "label": "PER (Plan Épargne Retraite)",
        "description": "Versements déductibles du revenu imposable. Bloqué jusqu'à la retraite (sauf exceptions). Fiscalisé à la sortie.",
        "rate": Decimal("0.040"),
        "tax_free": False,
        "tax_rate": Decimal("0.172"),
        "ceiling": None,
        "risk": "Faible-moyen",
        "color": "#ec4899",
        "liquidity": "Bloqué jusqu'à la retraite",
        "tax_deductible": True,
    },
}
```

2. Create `backend/app/models/investment.py`:

```python
class InvestmentAllocation(Base):
    __tablename__ = "investment_allocations"

    id                   = Column(UUID, primary_key=True, default=uuid4)
    user_id              = Column(UUID, ForeignKey("users.id"), nullable=False, index=True)
    vehicle_key          = Column(String(20), nullable=False)  # livret_a, ldds, av_euro, etc.
    existing_balance     = Column(Numeric(12, 2), nullable=False, server_default="0")
    monthly_contribution = Column(Numeric(10, 2), nullable=False, server_default="0")
    created_at           = Column(DateTime(timezone=True), server_default=func.now())
    updated_at           = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "vehicle_key", name="uq_user_vehicle"),
    )
```

3. Pydantic schemas:
   - `VehicleSpec` — read-only, from constants
   - `AllocationRead` — vehicle_key, existing_balance, monthly_contribution, plus embedded VehicleSpec
   - `AllocationWrite` — existing_balance, monthly_contribution (both >= 0)
   - `AllAllocationsRead` — list of all 7 vehicles with user's allocation (0 defaults for unset)

4. Router `backend/app/routers/investments.py`:
   - `GET /api/investments` — returns all 7 vehicles with user's allocations. Creates default rows (balance=0, contrib=0) for any vehicle the user hasn't set yet (upsert pattern).
   - `PUT /api/investments/{vehicle_key}` — update balance and/or contribution for one vehicle
   - `PUT /api/investments` — batch update all allocations at once
   - `GET /api/investments/vehicles` — returns just the vehicle specs (no auth needed, reference data)

5. Validation:
   - `existing_balance >= 0`, `monthly_contribution >= 0`
   - `vehicle_key` must be one of the 7 valid keys
   - Ceiling warning: if `existing_balance > ceiling` (for vehicles with ceilings), return a warning field (not an error — user may be modeling a future scenario)

6. Alembic migration

7. Unit tests: CRUD, validation, ceiling warning, batch update

## Technical Approach

### Files to Create
- `backend/app/calculations/vehicles.py`
- `backend/app/models/investment.py`
- `backend/app/schemas/investment.py`
- `backend/app/routers/investments.py`
- `backend/alembic/versions/xxxx_add_investment_allocations.py`
- `backend/tests/test_investments.py`

### Design Decision: Per-Row vs JSONB
Each vehicle is a separate row (not JSONB on the profile) because:
1. The projection engine queries individual vehicles to compound balances
2. Future features (transaction history, rebalancing alerts) need per-vehicle rows
3. The unique constraint prevents duplicate vehicle entries per user

### Upsert Pattern
`GET /api/investments` ensures all 7 rows exist for the user. On first access, it creates 7 rows with zero balances. This means the frontend always gets a complete set — no null handling needed.

## Acceptance Criteria

- [ ] `GET /api/investments/vehicles` returns 7 vehicle specs with all fields
- [ ] `GET /api/investments` returns 7 allocations (creates missing ones with zeros)
- [ ] `PUT /api/investments/pea` updates PEA balance and contribution
- [ ] Batch `PUT /api/investments` updates multiple vehicles at once
- [ ] Validation rejects negative values
- [ ] Ceiling warning returned when balance > ceiling (Livret A > 22 950€)
- [ ] `vehicle_key` validated against known keys
- [ ] Unit tests pass
- [ ] LEARNINGS.md updated

## Notes

- The rates in VEHICLE_SPECS are historical averages, not guarantees. The projection engine may apply a "real return" adjustment (rate - inflation × factor) to be conservative. That logic lives in Sprint 4.
- PER `tax_deductible: True` means contributions reduce taxable income. The projection engine should model this as a tax credit (contribution × marginal IR rate). Complex to do precisely — for MVP, note the benefit but don't compute the exact IR reduction.
- The tax rates are simplified. AV after 8 years has a 4 600€ abattement; PEA after 5 years is IR-free (only 17.2% PS). These nuances matter for precise tax planning but the 30-year projection uses average effective rates. Document this simplification in the vehicle description.
