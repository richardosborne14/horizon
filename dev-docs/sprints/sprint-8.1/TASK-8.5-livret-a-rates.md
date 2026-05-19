# TASK-8.5 — Fix Livret A / LDDS Rates: Government-Decree Based, Not Inflation-Derived

## Problem
The current vehicle spec for Livret A uses `spec_rate = inflation_rate` (moderate scale
= 2.0%). This is wrong in two ways:
1. The actual current rate is **1.5%** (as of 1 Feb 2026) — lower than the assumed 2%
2. The Livret A rate is set by government decree, not by a simple inflation formula
   It tracks a complex formula (avg inflation + avg €STER), revised every 6 months
   The projection engine cannot predict this — but it should use realistic scale-based
   rate bands rather than pretending the rate = inflation

## Confirmed current rates (official government arrêté, 28 Jan 2026)
- Livret A: **1.5%** (1 Feb 2026)
- LDDS: **1.5%** (identical to Livret A)
- LEP: **2.5%** (income-restricted)
- PEL (new 2026): ~2.0% gross → ~1.4% net after PFU

## SCOPE BOUNDARY — DO NOT
- DO NOT model the Banque de France formula (too complex, unknowable)
- DO NOT change PEA, AV, SCPI, PER vehicle specs
- DO NOT add a LEP vehicle in this task (that's TASK-8.9)

---

## Implementation steps

### Step 1 — Update vehicle specs in `calculations/vehicles.py`

Current (broken):
```python
"livret_a": {
    "spec_rate": "inflation",   # ← wrong
    "regulated": True,
    ...
}
```

Replace with explicit rate bands per scale:

```python
"livret_a": {
    "regulated": True,
    "ceiling": 22_950,
    "tax_rate": 0.0,           # fully exempt (IR + PS)
    # Scale-based rates — government-set, revised biannually
    # Pessimistic: may fall to near floor (0.5% statutory minimum)
    # Moderate: tracks roughly inflation, but with lag and political smoothing
    # Optimistic: high inflation environment pushes rate up
    "rates_by_scale": {
        "pessimistic": 0.010,   # 1.0% — near-floor scenario
        "moderate":    0.015,   # 1.5% — current rate (Feb 2026)
        "optimistic":  0.025,   # 2.5% — high-inflation env (as seen 2023–2024)
    },
    "rate_note": (
        "Taux fixé par décret gouvernemental, révisé au 1er fév. et 1er août. "
        "Taux actuel : 1,5 % (depuis le 1er fév. 2026)."
    ),
    "ceiling_overflow_target": "ldds",
},
"ldds": {
    "regulated": True,
    "ceiling": 12_000,
    "tax_rate": 0.0,
    "rates_by_scale": {
        "pessimistic": 0.010,
        "moderate":    0.015,   # Always equals Livret A
        "optimistic":  0.025,
    },
    "ceiling_overflow_target": "av_euro",
},
```

### Step 2 — Update `get_vehicle_effective_rate()` to use `rates_by_scale`

In `vehicles.py`, the effective rate function currently does:
```python
if vehicle["regulated"]:
    return inflation_rate  # ← remove this branch
```

Replace with:
```python
if "rates_by_scale" in vehicle:
    return vehicle["rates_by_scale"].get(scale, vehicle["rates_by_scale"]["moderate"])
```

### Step 3 — Projection engine: pass `scale` to vehicle rate lookup

The projection engine already has `inp.growth_scale` (the "optimistic/moderate/pessimistic"
selector). Ensure this is passed to `get_vehicle_effective_rate()` when computing
Livret A and LDDS returns.

---

## DONE WHEN
- [ ] `get_vehicle_effective_rate("livret_a", scale="moderate", ...)` returns 0.015
- [ ] `get_vehicle_effective_rate("livret_a", scale="optimistic", ...)` returns 0.025
- [ ] `get_vehicle_effective_rate("livret_a", scale="pessimistic", ...)` returns 0.010
- [ ] LDDS returns same values as Livret A for each scale
- [ ] Livret A no longer uses inflation_rate as its return
- [ ] PEA, AV, PER rates are unchanged
- [ ] Savings tab shows "Taux actuel : 1,5 %" on the Livret A card (see TASK-8.9)
