# TASK-8.3 — Update AE BNC Cotisation Rates to 2026-Correct Schedule

## Problem
The projection engine uses a static rate of ~21.2% for BNC prestations de services.
This is wrong for every year from H2 2024 onwards. The correct rates (URSSAF official,
decree n°2024-484 and decree n°2025-943):

| Period | BNC SSI (non-CIPAV) | BNC CIPAV |
|--------|---------------------|-----------|
| Before 2024-07-01 | 21.1% | 21.2% |
| 2024-07-01 – 2024-12-31 | 23.1% | 23.2% |
| 2025-01-01 – 2025-12-31 | 24.6% | 23.2% |
| 2026-01-01+ | **25.6%** | **23.2%** |

Additionally the CA ceiling for BNC prestations de services is **83,600€** (2026-2028,
loi de finances 2026). When income exceeds this, the user MUST leave the micro-entreprise
regime. This needs to be modeled in projections.

## SCOPE BOUNDARY — DO NOT
- DO NOT change BIC activity type rates (they are stable at 12.3% / 21.2%)
- DO NOT break the `get_ae_rate(activity_type, year)` function signature
- DO NOT model the full EURL/SASU regime — only flag the threshold breach

---

## Implementation steps

### Step 1 — Update `get_ae_rate()` in `calculations/ae_rates.py`

```python
# BNC RATE SCHEDULE — URSSAF official (decree n°2024-484, decree n°2025-943)
BNC_SSI_RATE_SCHEDULE = [
    # (effective_from_year, effective_from_month, rate)
    (2026, 1, 0.256),   # 25.6% from 1 Jan 2026 (capped by decree n°2025-943)
    (2025, 1, 0.246),   # 24.6% from 1 Jan 2025
    (2024, 7, 0.231),   # 23.1% from 1 Jul 2024
    (2000, 1, 0.211),   # 21.1% baseline (pre-2024)
]

BNC_CIPAV_RATE_SCHEDULE = [
    (2024, 7, 0.232),   # 23.2% from 1 Jul 2024
    (2000, 1, 0.212),   # 21.2% baseline
]

def get_ae_rate(activity_type: str, year: int, month: int = 1) -> float:
    """Return AE cotisation rate for a given activity type and year."""
    if activity_type in ("bnc_non_reglementee", "bnc_reglementee_ssi"):
        schedule = BNC_SSI_RATE_SCHEDULE
    elif activity_type in ("bnc_reglementee_cipav",):
        schedule = BNC_CIPAV_RATE_SCHEDULE
    elif activity_type in ("bic_services", "bic_artisan"):
        return 0.212  # stable since Oct 2022
    elif activity_type in ("bic_vente",):
        return 0.123  # stable since Oct 2022
    else:
        return 0.256  # safe default: highest rate

    # Find applicable rate for (year, month)
    for (from_year, from_month, rate) in schedule:
        if (year, month) >= (from_year, from_month):
            return rate
    return schedule[-1][2]  # fallback to oldest
```

### Step 2 — Call with correct year in projection engine

In `_compute_accumulation_year()`, the call becomes:
```python
ae_rate = get_ae_rate(
    activity_type=inp.ae_activity_type,
    year=current_year,   # projection year (2026, 2027, etc.)
    month=1
)
```
Where `current_year = start_year + y` (the absolute calendar year). Previously it may
have passed the relative year offset `y` instead of the absolute year — verify and fix.

### Step 3 — Add AE CA ceiling check in accumulation loop

After computing `gross_ae_annual` for a year, add:

```python
AE_BNC_CEILING = 83_600  # 2026-2028, loi de finances 2026

if inp.ae_activity_type in ("bnc_non_reglementee", "bnc_reglementee_ssi"):
    ceiling = AE_BNC_CEILING * ((1 + inp.inflation_rate) ** y)  # inflate ceiling too
    if gross_ae_annual > ceiling:
        year_result["ae_ceiling_breach"] = True
        year_result["ae_ceiling_excess"] = gross_ae_annual - ceiling
    else:
        year_result["ae_ceiling_breach"] = False
```

### Step 4 — Surface ceiling breach as a lifecycle alert

In `calculations/alerts.py` (or wherever lifecycle alerts are generated), add:

```python
for y, yr in enumerate(timeline):
    if yr.get("ae_ceiling_breach"):
        alerts.append({
            "year": base_year + y,
            "age": user_age + y,
            "type": "ae_ceiling",
            "severity": "warning",
            "title": "Plafond micro-entreprise approché",
            "message": (
                f"En {base_year + y}, votre CA projeté dépasse le plafond "
                f"micro-BNC de {format_k(AE_BNC_CEILING)}€. "
                f"Vous devrez basculer en EI réel, EURL ou SASU. "
                f"Les cotisations et la fiscalité seront différentes."
            ),
            "action_link": "/identity"
        })
        break  # only first breach year
```

Also add an alert **2 years before** the projected breach year (early warning).

### Step 5 — Update constants documentation

Add a comment in `ae_rates.py` explaining the rate schedule source and when it may
next be revised (the 3-year adjustment period ends in 2026; future changes require
new legislation).

---

## DONE WHEN
- [ ] `get_ae_rate("bnc_non_reglementee", 2025)` returns 0.246
- [ ] `get_ae_rate("bnc_non_reglementee", 2026)` returns 0.256
- [ ] `get_ae_rate("bnc_non_reglementee", 2027)` returns 0.256
- [ ] `get_ae_rate("bnc_non_reglementee", 2024)` returns 0.231 (for H2 2024)
- [ ] `get_ae_rate("bic_vente", 2026)` still returns 0.123
- [ ] Projection year uses absolute calendar year, not relative offset
- [ ] AE ceiling breach is detected and produces a lifecycle alert
- [ ] Early-warning alert fires 2 years before projected breach
- [ ] Unit tests for all rate years above
