# TASK-8.1 — Auto-calculate Quotient Familial from Profile Data

## Problem
The user manually enters `tax_parts` (quotient familial) on their profile. This is fragile:
the user currently has `3.5` parts but the correct value given their family situation
(married couple + 3 children) is **4.0**. Every projection year's IR calculation is wrong.

French rules (Article 194 CGI):
- Married/PACS couple: **2 parts**
- 1st dependent child: **+0.5 part**
- 2nd dependent child: **+0.5 part**
- 3rd and subsequent dependent children: **+1.0 part each**
- Single parent (chef de famille): **1 part** base + **0.5** first child + standard above
- Child under 18 OR under 25 if studying = dependent

## Root cause
`tax_parts` is a free-entry float field. There is no derivation logic from `spouses`
and `life_entities` tables.

## SCOPE BOUNDARY — DO NOT
- DO NOT change the projection engine signature
- DO NOT remove the `tax_parts` field from the DB schema
- DO NOT change how `compute_ir()` uses `tax_parts` — it stays correct
- DO NOT touch any page except identity and the backend profile logic

---

## Implementation steps

### Step 1 — Backend: add `compute_auto_tax_parts()` utility

File: `backend/app/calculations/tax_parts.py` (new file, ~30 lines)

```python
def compute_auto_tax_parts(
    marital_status: str,  # "married", "pacs", "single", "divorced", "widowed"
    dependent_children: list[dict],  # list of {"birth_date": date, "is_studying": bool}
    current_year: int,
) -> float:
    """
    Compute quotient familial per Art. 194 CGI.
    Returns float (e.g. 4.0, 3.5, 2.5)
    """
    # Base parts
    if marital_status in ("married", "pacs"):
        parts = 2.0
    elif marital_status in ("single", "divorced"):
        parts = 1.0  # chef de famille if has kids, else 1.0
    elif marital_status == "widowed":
        parts = 1.0
    else:
        parts = 1.0

    # Count eligible dependents
    eligible = []
    for child in dependent_children:
        age = current_year - child["birth_date"].year
        if age < 18 or (age < 25 and child.get("is_studying", True)):
            eligible.append(child)

    # Parts per child rank
    for i, _ in enumerate(eligible):
        if i == 0:
            parts += 0.5
        elif i == 1:
            parts += 0.5
        else:
            parts += 1.0  # 3rd child onwards

    # Single parent gets +0.5 on first child (total: 1.5 for 1 child)
    if marital_status in ("single", "divorced", "widowed") and eligible:
        parts += 0.5  # chef de famille bonus

    return parts
```

### Step 2 — Backend: expose computed value on GET /api/profile

In `routers/profile.py`, when building the profile response, add:
```python
from app.calculations.tax_parts import compute_auto_tax_parts

# Fetch children from life_entities where entity_type='kid' and is_active=True
kid_entities = db.query(LifeEntity).filter_by(
    user_id=user.id, entity_type="kid", is_active=True
).all()

kids = [{"birth_date": k.reference_date, "is_studying": True} for k in kid_entities]

marital = "married" if spouse and spouse.relationship_type == "married" \
          else "pacs" if spouse and spouse.relationship_type == "pacs" \
          else "single"

computed_parts = compute_auto_tax_parts(marital, kids, date.today().year)

# Add to response
profile_response["computed_tax_parts"] = float(computed_parts)
profile_response["tax_parts_match"] = abs(profile.tax_parts - computed_parts) < 0.01
```

### Step 3 — Frontend: identity page shows computed value with inline correction

In `frontend/src/routes/(app)/identity/+page.svelte`:

Where the `tax_parts` input is rendered, add below it:

```svelte
{#if data.profile.computed_tax_parts !== null}
  {#if !data.profile.tax_parts_match}
    <div class="alert-inline warning">
      ⚠️ Votre quotient familial entré ({data.profile.tax_parts}) semble différent
      du calcul automatique ({data.profile.computed_tax_parts} parts).
      <button on:click={applyComputedParts}>Utiliser {data.profile.computed_tax_parts}</button>
    </div>
  {:else}
    <div class="alert-inline info">
      ✓ Quotient familial cohérent avec votre situation familiale.
    </div>
  {/if}
{/if}
```

The `applyComputedParts` handler sets the field value and submits the profile form.

### Step 4 — Backend: auto-set on profile creation

In the new user onboarding flow, after life entities and spouse are configured,
call `compute_auto_tax_parts()` and set `profile.tax_parts = computed_parts` automatically
if `tax_parts` has never been manually overridden. Add a boolean `tax_parts_manual_override`
column to `user_profiles` (default false). If the user accepts the computed value,
set `tax_parts_manual_override = false`. If they edit manually, set to `true`.

**Migration:**
```sql
ALTER TABLE user_profiles ADD COLUMN tax_parts_manual_override BOOLEAN DEFAULT FALSE;
```

---

## DONE WHEN
- [ ] `compute_auto_tax_parts()` exists and unit-tested with cases: couple+0 kids (2.0), couple+1 (2.5), couple+2 (3.0), couple+3 (4.0), single+2 (2.5)
- [ ] GET /api/profile returns `computed_tax_parts` and `tax_parts_match`
- [ ] Identity page shows warning banner when entered value ≠ computed value
- [ ] "Utiliser X.X" button updates and saves tax_parts in one click
- [ ] Richard's profile: computed value = 4.0, warning displays "votre quotient familial entré (3.5) semble différent"
- [ ] No regression in compute_ir() — it still uses whatever float is in tax_parts
