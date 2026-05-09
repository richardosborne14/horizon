# TASK-1.3: Inflation Scales & Growth Presets

**Status:** BACKLOG
**Sprint:** 1
**Priority:** P1 (high)
**Est. effort:** 30 min
**Dependencies:** None

## Context

Two sets of constants used throughout Horizon 30: economic scenario scales (optimistic/moderate/pessimistic inflation assumptions) and revenue growth presets (conservative/moderate/ambitious). Both are reference data served via API so the frontend can render selector UIs and preview calculations, and the backend projection engine uses them for computation.

## Requirements

1. Create `backend/app/calculations/constants.py`:

```python
from decimal import Decimal

INFLATION_SCALES = {
    "optimistic": {
        "label": "Optimiste",
        "emoji": "☀️",
        "inflation": Decimal("0.018"),      # general inflation
        "cost_living": Decimal("0.020"),     # cost of living growth (slightly higher)
        "description": "Inflation maîtrisée, économie stable. Scénario le plus favorable.",
    },
    "moderate": {
        "label": "Modéré",
        "emoji": "⛅",
        "inflation": Decimal("0.025"),
        "cost_living": Decimal("0.030"),
        "description": "Inflation moyenne historique. Le scénario par défaut.",
    },
    "pessimistic": {
        "label": "Pessimiste",
        "emoji": "🌧️",
        "inflation": Decimal("0.035"),
        "cost_living": Decimal("0.045"),
        "description": "Inflation élevée, coût de la vie en hausse. Si le monde part en vrille.",
    },
}

GROWTH_PRESETS = {
    "conservative": {
        "label": "Prudent",
        "rate": Decimal("0.01"),
        "description": "Stabilité. Vous gardez vos clients existants, pas de gros changements.",
    },
    "moderate": {
        "label": "Modéré",
        "rate": Decimal("0.03"),
        "description": "Croissance naturelle : bouche à oreille, légère augmentation des tarifs chaque année.",
    },
    "ambitious": {
        "label": "Ambitieux",
        "rate": Decimal("0.06"),
        "description": "Nouveaux services, prospection active, montée en gamme. Demande un effort constant.",
    },
    "custom": {
        "label": "Personnalisé",
        "rate": None,
        "description": "Vous définissez votre propre taux de croissance annuel.",
    },
}

def get_growth_rate(preset: str, custom_rate: Decimal | None = None) -> Decimal:
    """Resolve the effective growth rate from a preset key."""
    if preset == "custom":
        return custom_rate or Decimal("0.03")
    p = GROWTH_PRESETS.get(preset)
    return p["rate"] if p and p["rate"] is not None else Decimal("0.03")
```

2. Create API endpoints in `backend/app/routers/constants.py`:
   - `GET /api/constants/scales` — returns all 3 inflation scales
   - `GET /api/constants/growth-presets` — returns all 4 growth presets
   - No auth required (public reference data)
   - JSON serializes Decimal as string (Pydantic handles this)

3. Unit tests: `get_growth_rate` returns correct values for each preset, custom fallback works.

## Technical Approach

### Files to Create
- `backend/app/calculations/constants.py`
- `backend/app/routers/constants.py`
- `backend/tests/test_constants.py`
- `backend/app/main.py` — mount router

## Acceptance Criteria

- [ ] `GET /api/constants/scales` returns 3 scales with all fields
- [ ] `GET /api/constants/growth-presets` returns 4 presets with descriptions
- [ ] `get_growth_rate("moderate")` returns `Decimal("0.03")`
- [ ] `get_growth_rate("custom", Decimal("0.05"))` returns `Decimal("0.05")`
- [ ] `get_growth_rate("custom", None)` returns `Decimal("0.03")` (safe fallback)
- [ ] All values are Decimal, never float
- [ ] Tests pass

## Notes

- These constants are the foundation for TASK-1.6 (growth preset cards), TASK-1.7 (inflation preview), and TASK-4.1 (projection engine).
- Descriptions are in French — they're displayed directly in the UI via API response, not i18n keys. This is intentional: these are financial reference descriptions, not UI chrome.
