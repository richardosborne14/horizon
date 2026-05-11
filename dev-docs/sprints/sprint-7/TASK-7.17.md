# TASK-7.17: Monthly Action Plan Dashboard

**Status:** TODO
**Sprint:** 7
**Priority:** P2 (medium)
**Est. effort:** 3 hr
**Dependencies:** TASK-7.11, TASK-7.13

---

## Context

The projection thinks in years but people live in months. This task adds a "Ce mois-ci" dashboard that answers: "What should I do THIS MONTH to stay on track?" It bridges the gap between 30-year projections and daily financial decisions. Prioritized action items, specific amounts, and direct links to configure.

---

## Step-by-Step Instructions

### Step 1: Create the action plan engine

Create `backend/app/calculations/action_plan.py`:

```python
"""Monthly action plan generator.

Produces a prioritized list of actions for the current month based on
the user's financial state and projection. Each action is specific:
amounts, account names, and why.

Actions are rule-based, not LLM-generated.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass
class MonthlyAction:
    id: str
    priority: int          # 1=do now, 2=this week, 3=this month
    category: str          # savings, income, expenses, admin
    title: str
    detail: str
    amount: Decimal | None  # €, if applicable
    link_to: str | None


def generate_action_plan(
    profile: dict,
    investments: dict,
    income_sources: list[dict],
    loans: list[dict],
    advice: list[dict],
    current_date: date | None = None,
) -> list[MonthlyAction]:
    """Generate this month's action plan."""
    today = current_date or date.today()
    actions: list[MonthlyAction] = []

    # ── 1: Savings redirect if Livret A at ceiling ───────────────────
    livret_bal = Decimal(str(investments.get("livret_a", {}).get("existing_balance", "0")))
    livret_monthly = Decimal(str(investments.get("livret_a", {}).get("monthly_contribution", "0")))
    if livret_bal >= Decimal("22950") and livret_monthly > 0:
        actions.append(MonthlyAction(
            id="redirect_livret_a",
            priority=1,
            category="savings",
            title=f"Redirigez {livret_monthly}€ du Livret A vers PEA",
            detail=f"Votre Livret A est au plafond ({livret_bal}€). Les {livret_monthly}€/mois n'y rapportent plus rien. Ouvrez ou alimentez un PEA.",
            amount=livret_monthly,
            link_to="/savings",
        ))

    # ── 2: Client ending soon — start prospecting ────────────────────
    for src in income_sources:
        if not src.get("end_date"):
            continue
        end = date.fromisoformat(src["end_date"])
        months_left = (end.year - today.year) * 12 + (end.month - today.month)
        if 0 < months_left <= 3:
            monthly = Decimal(str(src["amount"])) if src["frequency"] == "monthly" else Decimal(str(src["amount"])) / 12
            actions.append(MonthlyAction(
                id=f"client_ending_{src['id']}",
                priority=1,
                category="income",
                title=f"Contrat « {src['label']} » se termine dans {months_left} mois",
                detail=f"Vous perdrez {monthly}€/mois. Commencez à prospecter maintenant pour trouver un remplacement.",
                amount=monthly,
                link_to="/revenue",
            ))

    # ── 3: Loan ending soon — plan redirect ──────────────────────────
    for loan in loans:
        if not loan.get("end_date"):
            continue
        end = date.fromisoformat(loan["end_date"])
        months_left = (end.year - today.year) * 12 + (end.month - today.month)
        if 0 < months_left <= 6:
            monthly = Decimal(str(loan.get("monthly_payment", "0")))
            actions.append(MonthlyAction(
                id=f"loan_ending_{loan.get('id', '')}",
                priority=2,
                category="savings",
                title=f"Prêt « {loan.get('label', 'Prêt')} » se termine dans {months_left} mois",
                detail=f"Planifiez un virement automatique de {monthly}€/mois vers votre PEA ou AV à partir de {end.strftime('%B %Y')}.",
                amount=monthly,
                link_to="/savings",
            ))

    # ── 4: No savings allocation — critical gap ──────────────────────
    total_savings = sum(
        Decimal(str(v.get("monthly_contribution", "0")))
        for v in investments.values() if isinstance(v, dict)
    )
    if total_savings == 0:
        actions.append(MonthlyAction(
            id="no_savings",
            priority=1,
            category="savings",
            title="Commencez à épargner — même 100€/mois",
            detail="Vous n'avez aucune épargne mensuelle configurée. Sur 30 ans, même 100€/mois à 5% = 83 000€.",
            amount=Decimal("100"),
            link_to="/savings",
        ))

    # ── 5: Income source with low confidence — secure it ─────────────
    for src in income_sources:
        if src.get("confidence") == "low" and src.get("is_active"):
            monthly = Decimal(str(src["amount"])) if src["frequency"] == "monthly" else Decimal("0")
            if monthly > 500:
                actions.append(MonthlyAction(
                    id=f"secure_income_{src['id']}",
                    priority=2,
                    category="income",
                    title=f"Sécurisez « {src['label']} » ({monthly}€/mois)",
                    detail="Cette source de revenu est marquée comme spéculative. Essayez de signer un contrat ou de diversifier.",
                    amount=monthly,
                    link_to="/revenue",
                ))

    # ── 6: CESU not used — easy tax savings ──────────────────────────
    cesu = Decimal(str(profile.get("cesu_annual", "0")))
    if cesu == 0:
        actions.append(MonthlyAction(
            id="cesu_opportunity",
            priority=3,
            category="admin",
            title="Utilisez le CESU pour du crédit d'impôt",
            detail="Aide ménagère, garde d'enfant, jardinage — 50% en crédit d'impôt, plafond 6 000€/an d'économie.",
            amount=None,
            link_to="/revenue",
        ))

    # ── 7: PER contribution before year-end (Oct-Dec only) ──────────
    if today.month >= 10:
        per_monthly = Decimal(str(investments.get("per", {}).get("monthly_contribution", "0")))
        if per_monthly == 0:
            actions.append(MonthlyAction(
                id="per_yearend",
                priority=2,
                category="savings",
                title="Versement PER avant le 31 décembre",
                detail="Les versements PER sont déductibles du revenu imposable. Un versement avant fin décembre réduit votre IR cette année.",
                amount=None,
                link_to="/savings",
            ))

    # Sort by priority
    actions.sort(key=lambda a: a.priority)
    return actions[:10]  # Cap at 10 actions
```

### Step 2: API endpoint

File: `backend/app/routers/projection.py`

```python
@router.get("/action-plan")
async def get_action_plan(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate this month's prioritized action plan."""
    from app.calculations.action_plan import generate_action_plan
    
    profile = await _get_profile(str(current_user.id), db)
    investments = await _load_investments(str(current_user.id), db)
    sources = await _load_income_sources(str(current_user.id), db)
    loans = await _load_loans(str(current_user.id), db)
    
    actions = generate_action_plan(
        profile={
            "cesu_annual": str(profile.cesu_annual or 0),
            "status": profile.status,
        },
        investments=investments,
        income_sources=[
            {
                "id": str(s.id),
                "label": s.label,
                "amount": str(s.amount),
                "frequency": s.frequency,
                "end_date": s.end_date.isoformat() if s.end_date else None,
                "confidence": s.confidence,
                "is_active": s.is_active,
            }
            for s in sources
        ],
        loans=[
            {
                "id": str(l.id),
                "label": l.label,
                "monthly_payment": str(l.monthly_payment),
                "end_date": l.end_date.isoformat() if l.end_date else None,
            }
            for l in loans
        ],
        advice=[],
    )
    
    return {
        "month": date.today().strftime("%B %Y"),
        "actions": [
            {
                "id": a.id,
                "priority": a.priority,
                "category": a.category,
                "title": a.title,
                "detail": a.detail,
                "amount": str(a.amount) if a.amount else None,
                "link_to": a.link_to,
            }
            for a in actions
        ],
        "count": len(actions),
    }
```

### Step 3: Frontend — Action plan section on Runway page

Place this ABOVE the projection charts (it's the first thing the user should see):

```svelte
{#if actionPlan?.actions?.length > 0}
  <div class="bg-zinc-800/30 border border-teal-800/30 rounded-xl p-4 mb-5">
    <div class="flex items-center justify-between mb-3">
      <p class="text-xs font-semibold text-zinc-300">📋 Plan d'action — {actionPlan.month}</p>
      <span class="text-[9px] text-zinc-500">{actionPlan.count} action{actionPlan.count > 1 ? 's' : ''}</span>
    </div>
    <div class="space-y-2">
      {#each actionPlan.actions as action}
        <div class="flex items-start gap-3 p-2.5 bg-zinc-900/40 border border-zinc-700/20 rounded-lg">
          <span class="text-xs mt-0.5 flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center
            {action.priority === 1 ? 'bg-rose-900/40 text-rose-400' :
             action.priority === 2 ? 'bg-amber-900/40 text-amber-400' :
             'bg-zinc-800 text-zinc-400'}">
            {action.priority}
          </span>
          <div class="flex-1 min-w-0">
            <p class="text-xs text-zinc-200">{action.title}</p>
            <p class="text-[10px] text-zinc-500 mt-0.5">{action.detail}</p>
          </div>
          {#if action.amount}
            <span class="text-xs font-mono text-teal-400 whitespace-nowrap">{parseFloat(action.amount).toLocaleString('fr-FR')}€</span>
          {/if}
          {#if action.link_to}
            <a href={action.link_to} class="text-[10px] text-teal-400 hover:text-teal-300 whitespace-nowrap flex-shrink-0">→</a>
          {/if}
        </div>
      {/each}
    </div>
  </div>
{/if}
```

### Step 4: Data loading

File: `frontend/src/routes/(app)/runway/+page.server.ts`

Add action plan fetch alongside other data:
```typescript
const actionRes = await fetch(`${API}/projection/action-plan`, { headers });
const actionPlan = actionRes.ok ? await actionRes.json() : { actions: [], count: 0 };
return { ...existingData, actionPlan };
```

### Step 5: Unit tests

Create `backend/tests/test_action_plan.py`:
- Test Livret A at ceiling → redirect action
- Test client ending in 2 months → prospecting action
- Test no savings → critical action
- Test CESU unused → opportunity action
- Test PER in October → year-end action
- Test maximum 10 actions returned

---

## SCOPE BOUNDARY

- DO NOT make actions dismissable or completable (no state tracking).
- DO NOT add notifications or reminders.
- DO NOT add calendar integration.
- DO NOT generate more than 10 actions. Prioritize and cap.
- DO NOT use an LLM. All rules are templates.
- Each action must have a specific number (€/mois) where applicable — DO NOT be vague ("save more").
- Expected: ~120 lines action plan module, ~40 lines router, ~50 lines frontend.

## DONE WHEN

- [ ] `GET /api/projection/action-plan` returns prioritized actions
- [ ] At least 6 rule types implemented
- [ ] Actions sorted by priority (1=do now, 2=this week, 3=this month)
- [ ] Each action has specific amounts where applicable
- [ ] "Configurer →" links navigate to correct sections
- [ ] Action plan renders at top of Runway page
- [ ] Capped at 10 actions maximum
- [ ] Tests pass
