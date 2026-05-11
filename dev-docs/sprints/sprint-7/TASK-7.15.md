# TASK-7.15: Prescriptive Life-Phase Intelligence

**Status:** TODO
**Sprint:** 7
**Priority:** P2 (medium)
**Est. effort:** 2 hr
**Dependencies:** TASK-6.6, TASK-6.9

---

## Context

The existing lifecycle alerts (TASK-6.9) detect events ("mortgage ends in 2035") and the expense evolution timeline (TASK-6.6) shows how expenses change. But neither is prescriptive — they don't tell the user what to DO about it. This task adds specific, actionable advice triggered by life-phase transitions: "When your mortgage ends in 2035, redirect the 590€/mois to PEA — this adds 127k€ to your retirement wealth."

---

## Step-by-Step Instructions

### Step 1: Create the advice engine

Create `backend/app/calculations/advice.py`:

```python
"""Prescriptive advice engine — rule-based recommendations.

Scans the projection timeline and lifecycle events to generate
specific, actionable advice with quantified impact.

NOT an LLM. Pure rule-based. Each rule has:
  - trigger condition
  - advice text template
  - impact calculation (optional)
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass
class Advice:
    id: str
    category: str         # savings, expenses, income, status, retirement
    priority: int          # 1=critical, 2=important, 3=nice-to-have
    title: str
    description: str
    impact_text: str       # "Ajoute ~127k€ au patrimoine final"
    action_text: str       # "Configurez un virement PEA de 590€/mois à partir de mars 2035"
    trigger_year: int | None
    link_to: str | None    # section to navigate to (e.g. "/savings")


def generate_advice(
    timeline: list[Any],
    lifecycle_alerts: list[dict],
    expense_events: list[dict],
    profile: dict,
    investments: dict,
    sensitivity: list[dict] | None = None,
) -> list[Advice]:
    """Generate prescriptive advice from all available data."""
    advice_list: list[Advice] = []

    # ── Rule 1: Redirect freed loan payments ─────────────────────────
    for event in expense_events:
        if event.get("category") == "loan_end":
            monthly_freed = abs(Decimal(str(event.get("impact_monthly", "0"))))
            if monthly_freed >= 100:
                # Estimate impact: monthly_freed × 12 × years_remaining × ~5% compound
                years_left = profile.get("target_retirement_age", 70) - event.get("year", 2035) + 30
                rough_impact = monthly_freed * 12 * years_left * Decimal("1.5")  # Very rough
                advice_list.append(Advice(
                    id=f"redirect_loan_{event['year']}",
                    category="savings",
                    priority=1,
                    title=f"Redirigez {monthly_freed}€/mois quand le prêt se termine",
                    description=f"En {event['year']}, votre prêt se termine. Ces {monthly_freed}€/mois libérés peuvent être redirigés vers l'épargne.",
                    impact_text=f"Impact estimé : +{rough_impact:,.0f}€ sur le patrimoine final",
                    action_text=f"Configurez un virement automatique de {monthly_freed}€/mois vers votre PEA ou AV à partir de {event['year']}.",
                    trigger_year=event["year"],
                    link_to="/savings",
                ))

    # ── Rule 2: Kids becoming independent → reduce expenses target ───
    for event in expense_events:
        if "indépendant" in event.get("event", "").lower():
            advice_list.append(Advice(
                id=f"kid_independent_{event['year']}",
                category="expenses",
                priority=3,
                title=f"Dépenses enfant réduites en {event['year']}",
                description=f"{event['event']} — vos dépenses mensuelles baissent.",
                impact_text=f"Économie : {event.get('impact_monthly', '?')}€/mois",
                action_text="Réévaluez votre budget et redirigez le surplus vers l'épargne.",
                trigger_year=event["year"],
                link_to="/expenses",
            ))

    # ── Rule 3: Livret A at ceiling → redirect to PEA/AV ────────────
    livret_balance = Decimal(str(investments.get("livret_a", {}).get("existing_balance", "0")))
    livret_ceiling = Decimal("22950")
    if livret_balance >= livret_ceiling * Decimal("0.9"):
        livret_monthly = Decimal(str(investments.get("livret_a", {}).get("monthly_contribution", "0")))
        if livret_monthly > 0:
            advice_list.append(Advice(
                id="livret_a_ceiling",
                category="savings",
                priority=1,
                title=f"Livret A proche du plafond — redirigez {livret_monthly}€/mois",
                description=f"Votre Livret A est à {livret_balance}€ (plafond {livret_ceiling}€). L'argent au-delà ne rapporte rien.",
                impact_text="Un PEA rapporte ~7%/an vs 2.5% au Livret A",
                action_text=f"Redirigez vos {livret_monthly}€/mois de Livret A vers un PEA ou une AV.",
                trigger_year=None,
                link_to="/savings",
            ))

    # ── Rule 4: No PEA allocation → biggest missed opportunity ──────
    pea_monthly = Decimal(str(investments.get("pea", {}).get("monthly_contribution", "0")))
    total_savings = sum(
        Decimal(str(v.get("monthly_contribution", "0")))
        for v in investments.values() if isinstance(v, dict)
    )
    if pea_monthly == 0 and total_savings > 200:
        advice_list.append(Advice(
            id="no_pea",
            category="savings",
            priority=1,
            title="Ouvrez un PEA — le véhicule le plus efficace",
            description=f"Vous épargnez {total_savings}€/mois mais rien en PEA. Le PEA offre ~7%/an net après 5 ans (vs 2.5% Livret A).",
            impact_text="Redirecteur 50% de votre épargne vers un PEA pourrait ajouter 100k€+ au patrimoine",
            action_text="Allouez au moins 50% de votre épargne mensuelle au PEA.",
            trigger_year=None,
            link_to="/savings",
        ))

    # ── Rule 5: High expense ratio vs income ─────────────────────────
    if timeline and len(timeline) > 0:
        first = timeline[0]
        expense_ratio = Decimal(str(first.total_outgoing)) / max(Decimal(str(first.total_income)), Decimal("1"))
        if expense_ratio > Decimal("0.9"):
            advice_list.append(Advice(
                id="high_expense_ratio",
                category="expenses",
                priority=2,
                title="Vos dépenses absorbent >90% de vos revenus",
                description="Il reste très peu pour l'épargne. Identifiez 2-3 postes à réduire.",
                impact_text="Même 200€/mois de plus d'épargne fait une différence énorme sur 30 ans",
                action_text="Passez en revue vos dépenses sur la page Charges et identifiez des économies.",
                trigger_year=None,
                link_to="/expenses",
            ))

    # ── Rule 6: CC opportunity not used ──────────────────────────────
    status = profile.get("status", "ae")
    has_spouse = profile.get("has_spouse", False)
    spouse_is_cc = profile.get("spouse_is_cc", False)
    if status in ("eirl", "eurl") and has_spouse and not spouse_is_cc:
        advice_list.append(Advice(
            id="cc_opportunity",
            category="status",
            priority=2,
            title="Conjoint(e) collaborateur/trice — droits retraite gratuits",
            description="Votre conjoint(e) pourrait cotiser comme conjoint(e) collaborateur/trice et acquérir des droits retraite.",
            impact_text="Génère des trimestres et une pension complémentaire pour le conjoint",
            action_text="Activez l'option sur la page Identité → Conjoint(e).",
            trigger_year=None,
            link_to="/identity",
        ))

    # Sort by priority
    advice_list.sort(key=lambda a: a.priority)
    return advice_list
```

### Step 2: API endpoint

File: `backend/app/routers/projection.py`

```python
@router.get("/advice")
async def get_advice(
    scale: str = Query(default="moderate"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate prescriptive advice based on the user's projection and financial data."""
    inp = await _assemble_input(str(current_user.id), scale, db)
    timeline = project_timeline(inp)
    
    # Get lifecycle alerts and expense events (reuse existing logic)
    expense_events = _detect_expense_events(timeline)
    
    # Get investment data
    investments = await _load_investments(str(current_user.id), db)
    
    # Check spouse
    spouse = await db.execute(select(Spouse).where(Spouse.user_id == str(current_user.id)))
    spouse_data = spouse.scalar_one_or_none()
    
    profile_context = {
        "status": inp.status,
        "target_retirement_age": inp.target_age,
        "has_spouse": spouse_data is not None,
        "spouse_is_cc": spouse_data.is_conjointe_collaboratrice if spouse_data else False,
    }
    
    advice_list = generate_advice(timeline, [], expense_events, profile_context, investments)
    
    return {
        "advice": [
            {
                "id": a.id,
                "category": a.category,
                "priority": a.priority,
                "title": a.title,
                "description": a.description,
                "impact_text": a.impact_text,
                "action_text": a.action_text,
                "trigger_year": a.trigger_year,
                "link_to": a.link_to,
            }
            for a in advice_list
        ],
        "count": len(advice_list),
    }
```

### Step 3: Frontend — Advice section on Runway page

Add an "Actions recommandées" section on the Runway page:

```svelte
{#if adviceList.length > 0}
  <div class="bg-zinc-800/30 border border-zinc-800/40 rounded-xl p-4">
    <p class="text-xs font-semibold text-zinc-300 mb-3">🎯 Actions recommandées</p>
    <div class="space-y-2">
      {#each adviceList as advice}
        <div class="p-3 bg-zinc-900/40 border border-zinc-700/30 rounded-lg">
          <div class="flex items-start gap-2">
            <span class="text-sm mt-0.5">
              {advice.priority === 1 ? '🔴' : advice.priority === 2 ? '🟡' : '🟢'}
            </span>
            <div class="flex-1">
              <p class="text-xs text-zinc-200 font-medium">{advice.title}</p>
              <p class="text-[10px] text-zinc-500 mt-0.5">{advice.description}</p>
              <p class="text-[10px] text-teal-400 mt-1">{advice.impact_text}</p>
              <p class="text-[10px] text-zinc-400 mt-0.5 italic">{advice.action_text}</p>
            </div>
            {#if advice.link_to}
              <a href={advice.link_to} class="text-[10px] text-teal-400 hover:text-teal-300 whitespace-nowrap">
                Configurer →
              </a>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  </div>
{/if}
```

---

## SCOPE BOUNDARY

- DO NOT use an LLM for advice generation. All rules are hardcoded templates.
- DO NOT add more than 8 rules in this task. Start with the 6 above. More can be added incrementally.
- DO NOT make advice dismissable/persistable. They regenerate on each page load.
- DO NOT add advice-specific i18n keys — the text is in the Python templates. Localization can come later.
- Impact calculations are rough estimates, NOT full projection reruns. Use simple formulas.
- Expected: ~120 lines advice module, ~30 lines router, ~40 lines frontend.

## DONE WHEN

- [ ] `GET /api/projection/advice` returns a list of actionable advice
- [ ] At least 5 rule types triggering correctly
- [ ] Each advice has: title, description, impact estimate, action text, link
- [ ] Priority sorting (critical first)
- [ ] Frontend renders advice cards on Runway page
- [ ] "Configurer →" links navigate to the right section
- [ ] Advice regenerates on page load (not cached client-side)
