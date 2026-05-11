# TASK-7.16: Real Estate Appreciation Model

**Status:** TODO
**Sprint:** 7
**Priority:** P2 (medium)
**Est. effort:** 2 hr
**Dependencies:** TASK-6.5

---

## Context

For many French households, the primary residence is the retirement plan. Sprint 6 added net worth tracking (TASK-6.5) with a property value field, but it's a static snapshot. This task adds a simple appreciation model so the user can see: "At 65, your house is worth 450k€. If you downsize to a 200k€ apartment, that frees 250k€ of capital." This is a retirement strategy many French people actually use.

---

## Step-by-Step Instructions

### Step 1: Extend net worth model with appreciation

File: `backend/app/models/net_worth.py` (or wherever net worth is stored)

Add fields to the property entry:

```python
# If net worth uses a JSONB structure, add these fields to the property object:
# {
#   "property_value": 350000,
#   "property_label": "Résidence principale",
#   "appreciation_rate": 0.02,  # 2%/year (default)
#   "downsize_enabled": false,
#   "downsize_year": null,
#   "downsize_target_value": null,  # Value of replacement property
# }
```

If net worth uses a separate model, add columns. Follow whichever pattern TASK-6.5 established.

### Step 2: Property projection helper

Create `backend/app/calculations/property.py`:

```python
"""Property appreciation and downsizing model.

Simple compound appreciation with optional downsizing event.
"""
from decimal import Decimal


def project_property_value(
    current_value: Decimal,
    appreciation_rate: Decimal,
    years: int,
) -> Decimal:
    """Project property value with compound appreciation."""
    return current_value * (1 + appreciation_rate) ** years


def compute_downsize_capital(
    property_value_at_downsize: Decimal,
    replacement_value: Decimal,
    selling_costs_pct: Decimal = Decimal("0.08"),  # ~8% (agency + notaire)
    buying_costs_pct: Decimal = Decimal("0.08"),   # ~8% notaire on purchase
) -> Decimal:
    """Compute freed capital from downsizing.
    
    Freed capital = sale price - selling costs - replacement price - buying costs
    """
    net_sale = property_value_at_downsize * (1 - selling_costs_pct)
    gross_purchase = replacement_value * (1 + buying_costs_pct)
    return max(Decimal("0"), net_sale - gross_purchase)
```

### Step 3: Integrate into projection engine

File: `backend/app/calculations/projection.py`

Add property to `ProjectionInput`:

```python
# ── Property (TASK-7.16) ─────────────────────────────────────────
property_value: Decimal = Decimal("0")
property_appreciation_rate: Decimal = Decimal("0.02")
downsize_enabled: bool = False
downsize_year: int | None = None
downsize_target_value: Decimal = Decimal("0")
```

In the year loop, compute property value and handle downsizing:

```python
# Property appreciation
if inp.property_value > 0:
    years_from_start = year - start_year
    current_property = project_property_value(
        inp.property_value, inp.property_appreciation_rate, years_from_start
    )
    
    # Downsizing event
    if inp.downsize_enabled and inp.downsize_year and year == inp.downsize_year:
        freed_capital = compute_downsize_capital(
            current_property, inp.downsize_target_value
        )
        # Add freed capital to investments (distribute to AV or PEA)
        if "av_euro" in balances:
            balances["av_euro"] += freed_capital
        elif "pea" in balances:
            balances["pea"] += freed_capital
        else:
            balances["av_euro"] = freed_capital
        
        # Update property value to replacement
        current_property = inp.downsize_target_value
```

Add `property_value` and `freed_capital` to `YearProjection` dataclass:

```python
property_value: Decimal = Decimal("0")
downsize_freed: Decimal = Decimal("0")  # Non-zero only in downsize year
```

### Step 4: Frontend — Property section in net worth or Identity page

Add property fields wherever net worth is edited (TASK-6.5 page):

```svelte
<Card title="Résidence principale" icon="🏠" accent="emerald">
  <div class="grid grid-cols-2 gap-3">
    <Inp label="Valeur estimée" bind:value={property.value} type="number" suffix="€" />
    <Inp label="Appréciation annuelle" bind:value={property.appreciation_rate}
      type="number" step="0.5" suffix="%/an" />
  </div>

  <div class="mt-3 text-[10px] text-zinc-500">
    <p>Valeur projetée à {targetAge} ans : <span class="text-emerald-400 font-mono">
      {projectedPropertyValue.toLocaleString('fr-FR')}€
    </span></p>
  </div>

  <label class="flex items-center gap-2 mt-3 text-xs text-zinc-300">
    <input type="checkbox" bind:checked={property.downsize_enabled} on:change={save} />
    Simuler un déménagement / downsizing
  </label>

  {#if property.downsize_enabled}
    <div class="grid grid-cols-2 gap-3 mt-2">
      <Inp label="Année du déménagement" bind:value={property.downsize_year} type="number" />
      <Inp label="Valeur du nouveau bien" bind:value={property.downsize_target_value} type="number" suffix="€" />
    </div>
    <div class="mt-2 p-2 bg-emerald-950/20 border border-emerald-800/20 rounded text-[10px] text-emerald-300">
      Capital libéré estimé : <span class="font-mono font-bold">
        {freedCapitalEstimate.toLocaleString('fr-FR')}€
      </span>
      <span class="text-zinc-500"> (après frais de vente ~8% et frais de notaire ~8%)</span>
    </div>
  {/if}
</Card>
```

### Step 5: Include property in net worth display on Runway

In the Runway page wealth chart, property value can optionally be included or excluded. Add a small toggle: "Inclure la résidence principale dans le patrimoine."

### Step 6: Unit tests

Create `backend/tests/test_property.py`:
- Test appreciation: 350k at 2% for 20 years → ~519k
- Test downsizing: sell 450k, buy 200k, after costs → ~197k freed
- Test negative freed capital (buying more expensive → no capital freed)

---

## SCOPE BOUNDARY

- DO NOT model rental income from property (that's the existing projects/investment feature).
- DO NOT model multiple properties. One primary residence only.
- DO NOT model mortgage amortization here (that's the loans model from TASK-6.3).
- DO NOT add regional property price indices.
- The appreciation rate is a single user-input number. DO NOT fetch real market data.
- Selling costs 8% and buying costs 8% are hardcoded simplifications. DO NOT make them configurable.
- Expected: ~40 lines property module, ~20 lines engine, ~60 lines frontend.

## DONE WHEN

- [ ] Property value appreciates in the projection at the configured rate
- [ ] Downsizing event frees capital into investment accounts in the specified year
- [ ] Freed capital estimate shown with cost deductions
- [ ] Property section with appreciation rate input
- [ ] Downsizing toggle with year and target value inputs
- [ ] Tests pass for appreciation and downsizing math
