# TASK-7.3: Custom Expense Categories

**Status:** DONE — Already implemented. Backend model has custom_expenses JSONB column (profile.py:96-99). DB column exists. GET/PUT /api/profile/expenses handle custom_expenses. Inflation preview includes them. Projection input assembly sums them (projection.py:146-147). Frontend has full CRUD with add/remove/debounced save (expenses/+page.svelte).
**Sprint:** 7
**Priority:** P0 (critical — users can't represent their real expenses)
**Est. effort:** 2 hr
**Dependencies:** None

---

## Context

The Charges page has 12 hardcoded categories (loyer, énergie, internet, etc.). Users cannot add categories. Real budgets have expenses that don't fit: coworking, domestic help, therapy, professional subscriptions. The "divers" catch-all loses granularity.

---

## Step-by-Step Instructions

### Step 1: Backend — add `custom_expenses` column to UserProfile

File: `backend/app/models/profile.py`

Add a new JSONB column next to `monthly_expenses`:

```python
# ── Custom expenses (array of {id, label, amount}) ────────────────────
custom_expenses = Column(
    JSONB, nullable=False, server_default="[]"
)
```

Create an Alembic migration:
```bash
cd backend && alembic revision --autogenerate -m "add custom_expenses to user_profile"
```

Verify the migration SQL adds the column with default `'[]'::jsonb`. Apply: `alembic upgrade head`.

### Step 2: Backend — update expense endpoints

File: `backend/app/routers/profile.py`

**In the `PUT /api/profile/expenses` endpoint:**

Accept `custom_expenses` as an optional field in the request body. It's an array of objects:

```python
# Expected shape:
# { "loyer": "850", ..., "custom_expenses": [{"id": "ce_001", "label": "Coworking", "amount": "250"}, ...] }
```

Save `custom_expenses` to the profile alongside `monthly_expenses`.

**In the `GET /api/profile/expenses` endpoint:**

Return both `monthly_expenses` and `custom_expenses`:

```python
return {
    "expenses": profile.monthly_expenses or {},
    "custom_expenses": profile.custom_expenses or [],
    "labels": EXPENSE_LABELS,
    "total": str(total),  # Must include custom expenses in total
}
```

**Total calculation** — update the total computation to include custom expenses:

```python
base_total = sum(Decimal(str(v)) for v in (profile.monthly_expenses or {}).values())
custom_total = sum(Decimal(str(ce.get("amount", "0"))) for ce in (profile.custom_expenses or []))
total = base_total + custom_total
```

### Step 3: Backend — update inflation preview

File: wherever `GET /api/profile/expenses/inflation-preview` is handled.

The inflation preview must use the total including custom expenses. Find where `monthly_total` is computed and add the custom expenses sum.

### Step 4: Backend — update projection engine input assembly

File: `backend/app/routers/projection.py` → `_assemble_input()`

The `monthly_expenses_total` field in `ProjectionInput` must include custom expenses:

```python
base = sum(Decimal(str(v)) for v in (profile.monthly_expenses or {}).values())
custom = sum(Decimal(str(ce.get("amount", "0"))) for ce in (profile.custom_expenses or []))
monthly_expenses_total = base + custom
```

### Step 5: Frontend — add custom expenses section

File: `frontend/src/routes/(app)/expenses/+page.svelte`

After the 12-category grid, before the inflation preview, add:

```svelte
<!-- ── Custom expenses ─────────────────────────────────────────────── -->
<Card title="Autres dépenses mensuelles" icon="✚" accent="sky">
  <p class="text-xs text-zinc-500 mb-3">
    Dépenses qui ne rentrent pas dans les catégories ci-dessus : coworking, aide ménagère, abonnements pro, etc.
  </p>

  {#each customExpenses as expense, i (expense.id)}
    <div class="flex items-end gap-2 mb-2">
      <input type="text" bind:value={expense.label} placeholder="Description"
        on:input={() => onCustomChange()}
        class="flex-1 bg-zinc-900/60 border border-zinc-700/40 rounded px-2 py-1.5 text-xs text-zinc-200" />
      <div class="relative w-28">
        <input type="number" bind:value={expense.amount} min="0" step="10"
          on:input={() => onCustomChange()}
          class="w-full bg-zinc-900/60 border border-zinc-700/40 rounded px-2 py-1.5 text-xs text-zinc-200 pr-8" />
        <span class="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-zinc-500">€/m</span>
      </div>
      <button on:click={() => removeCustomExpense(i)}
        class="text-zinc-600 hover:text-rose-400 text-sm mb-1">✕</button>
    </div>
  {/each}

  <button on:click={addCustomExpense}
    class="w-full text-center text-xs text-zinc-500 hover:text-zinc-300 py-2 border border-dashed border-zinc-700/50 rounded-lg hover:border-sky-700/50 transition-colors mt-1">
    + Ajouter une dépense
  </button>
</Card>
```

### Step 6: Frontend — custom expense logic

In the `<script>` section of the same file, add:

```typescript
let customExpenses: Array<{id: string, label: string, amount: number}> = data.customExpenses ?? [];

function addCustomExpense() {
  customExpenses = [...customExpenses, {
    id: 'ce_' + Math.random().toString(36).slice(2, 8),
    label: '',
    amount: 0,
  }];
  onCustomChange();
}

function removeCustomExpense(index: number) {
  customExpenses = customExpenses.filter((_, i) => i !== index);
  onCustomChange();
}

let customDebounce: ReturnType<typeof setTimeout>;
function onCustomChange() {
  clearTimeout(customDebounce);
  customDebounce = setTimeout(() => saveCustomExpenses(), DEBOUNCE_MS);
}

async function saveCustomExpenses() {
  saveIndicator = 'saving';
  try {
    const res = await api.put('/profile/expenses', {
      ...expenses,
      custom_expenses: customExpenses.map(ce => ({
        id: ce.id,
        label: ce.label,
        amount: String(ce.amount),
      })),
    });
    total = res.total;
    saveIndicator = 'saved';
    setTimeout(() => { saveIndicator = 'idle'; }, 1500);
  } catch (err) {
    console.error('[expenses] Custom save failed:', err);
    saveIndicator = 'error';
  }
}
```

### Step 7: Frontend — update total display

The stats row `total` must already include custom expenses if the backend returns the combined total. Verify this works — the `total` variable is set from the API response.

### Step 8: Update page.server.ts

File: `frontend/src/routes/(app)/expenses/+page.server.ts`

Ensure `customExpenses` is passed to the page data from the API response.

---

## SCOPE BOUNDARY

- DO NOT add category grouping or icons for custom expenses.
- DO NOT add drag-and-drop reordering.
- DO NOT modify the 12 standard categories.
- DO NOT add per-category inflation rates (all expenses inflate uniformly).
- Maximum 10 custom expenses is fine — no need to enforce a hard limit in the UI, but cap at 20 in the backend validation if needed.
- Expected change: ~50 lines backend, ~60 lines frontend.

## DONE WHEN

- [ ] User can click "+ Ajouter une dépense" and a new row appears
- [ ] User can type a label and amount for each custom expense
- [ ] User can remove a custom expense with ✕
- [ ] Custom expenses auto-save with 800ms debounce
- [ ] Stats row total includes custom expenses
- [ ] Inflation preview includes custom expenses in its calculation
- [ ] Projection engine includes custom expenses in `monthly_expenses_total`
- [ ] Page refresh preserves custom expenses (data persisted)
- [ ] Alembic migration runs cleanly
- [ ] Existing tests pass
