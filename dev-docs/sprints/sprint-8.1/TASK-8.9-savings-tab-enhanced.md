# TASK-8.9 — Enhanced Savings Tab: All French Vehicles, Rules Panel, Balance Projection

## Goal
Transform the savings tab from a simple contribution-entry form into an intelligent
savings guide that:
1. Shows **all major French savings vehicles** (not just the current 6)
2. For each vehicle, shows a **rules panel** with rate, tax treatment, lock-up, ceiling,
   and when it makes sense
3. Shows a **balance projection chart** per vehicle over time, with life events and
   projects overlaid to show drawdown moments and their consequences

This is a substantial UI + backend task. Scope carefully.

---

## 8.9.A — Complete vehicle catalog

### Current vehicles (already in system)
- Livret A ✓
- LDDS ✓
- AV fonds € ✓
- AV unités de compte ✓
- PEA ✓
- SCPI ✓
- PER ✓

### Vehicles to add

| Key | Label | Why add |
|-----|-------|---------|
| `lep` | Livret d'Épargne Populaire | 2.5% rate, best guaranteed return, income-restricted |
| `pel` | Plan Épargne Logement | Guaranteed rate, useful for property purchase projects |
| `cto` | Compte-Titres Ordinaire | No ceiling, no lock-up, but fully taxable (PFU 30%) |
| `pee` | Plan Épargne Entreprise | Employer match, 5-year lock-up (relevant if switching to salaried role) |

These are added as **informational vehicles** (shown in the catalog with a rules panel)
and optionally added to the user's active allocation. They are NOT required for
the projection to run.

**DB: No schema change needed.** Vehicle keys are stored in `investment_allocations.vehicle_key`.
Simply add the new vehicle specs to `vehicles.py`.

---

## 8.9.B — Vehicle rules panel (per-vehicle accordion/tooltip)

For each vehicle in the savings tab, clicking an "ℹ️" button opens a rules panel.

### Panel data structure (from `vehicles.py` specs):

```python
VEHICLE_RULES = {
    "livret_a": {
        "label": "Livret A",
        "icon": "🏦",
        "current_rate": "1,5 % net (depuis fév. 2026)",
        "rate_by_scale": {"pessimiste": "1,0 %", "modéré": "1,5 %", "optimiste": "2,5 %"},
        "ceiling": "22 950 €",
        "tax": "Exonéré d'impôt sur le revenu et de prélèvements sociaux (17,2 %)",
        "liquidity": "Disponible à tout moment — aucun délai de retrait",
        "lock_up": None,
        "penalty": "Aucune pénalité",
        "best_for": "Épargne de précaution (3–6 mois de dépenses). À remplir en priorité.",
        "watch_out": "Taux révisable deux fois par an — peut descendre sous l'inflation.",
        "horizon": "Court terme (< 2 ans)",
        "open_conditions": "Accessible à tous — une seule ouverture par personne.",
    },
    "ldds": {
        "label": "LDDS",
        "icon": "🌱",
        "current_rate": "1,5 % net (identique Livret A)",
        "ceiling": "12 000 €",
        "tax": "Exonéré IR + PS",
        "liquidity": "Disponible à tout moment",
        "lock_up": None,
        "penalty": "Aucune",
        "best_for": "Extension du Livret A une fois le plafond atteint.",
        "watch_out": "Même risque de baisse de taux que le Livret A.",
        "horizon": "Court terme",
        "open_conditions": "Un seul par personne.",
    },
    "lep": {
        "label": "LEP — Livret d'Épargne Populaire",
        "icon": "💰",
        "current_rate": "2,5 % net (depuis fév. 2026)",
        "ceiling": "10 000 €",
        "tax": "Exonéré IR + PS",
        "liquidity": "Disponible à tout moment",
        "lock_up": None,
        "penalty": "Aucune",
        "best_for": "Meilleur taux garanti disponible pour l'épargne de précaution.",
        "watch_out": (
            "Soumis à conditions de revenus (RFR ≤ plafond annuel selon parts fiscales). "
            "À vérifier chaque année — droits peuvent être perdus si revenus augmentent."
        ),
        "horizon": "Court terme",
        "open_conditions": (
            "RFR ≤ 21 393 € pour 1 part (2026). "
            "Pour 4 parts fiscales : RFR ≤ ~35 000 € environ. À vérifier."
        ),
    },
    "pel": {
        "label": "PEL — Plan Épargne Logement",
        "icon": "🏠",
        "current_rate": "2,0 % brut (~1,4 % net après PFU 30 %) pour les PEL ouverts en 2026",
        "ceiling": "61 200 €",
        "tax": "Intérêts soumis au PFU (30 %) dès la première année",
        "liquidity": "Bloqué pendant 4 ans minimum",
        "lock_up": "4 ans minimum (sinon clôture automatique et perte des droits)",
        "penalty": "Clôture avant 4 ans : perte des intérêts majorés et du droit au prêt PEL",
        "best_for": (
            "Constitution d'un apport immobilier à horizon 4–10 ans. "
            "Taux garanti pendant toute la durée du plan."
        ),
        "watch_out": (
            "Le prêt PEL adossé n'est plus compétitif par rapport aux taux de marché en 2026. "
            "L'intérêt principal est désormais la garantie du taux d'épargne, pas le prêt."
        ),
        "horizon": "Moyen terme (4–10 ans)",
        "open_conditions": "Un seul PEL par personne.",
    },
    "av_euro": {
        "label": "Assurance-Vie — Fonds en Euros",
        "icon": "📄",
        "current_rate": "~2,5–3,5 % brut en 2025 selon assureur",
        "ceiling": "Aucun plafond légal",
        "tax": (
            "Gains soumis au PFU (30 %) avant 8 ans. "
            "Après 8 ans : prélèvements sociaux (17,2 %) seulement, "
            "avec abattement annuel de 4 600 € (9 200 € pour un couple)."
        ),
        "liquidity": "Disponible à tout moment, mais optimisation fiscale après 8 ans",
        "lock_up": None,
        "penalty": (
            "Aucune pénalité légale, mais rachat avant 8 ans = fiscalité PFU moins favorable. "
            "Certains contrats ont des frais de rachat."
        ),
        "best_for": (
            "Épargne long terme avec capital garanti (fonds €). "
            "Idéal pour la préparation retraite et transmission patrimoniale."
        ),
        "watch_out": (
            "Rendement des fonds € orienté à la baisse depuis 2010. "
            "Les frais de gestion annuels (0,5–1 %) réduisent le rendement réel. "
            "Ouvrir tôt pour faire courir l'horloge fiscale des 8 ans."
        ),
        "horizon": "Long terme (8 ans+)",
        "open_conditions": "Accessible à tous.",
    },
    "av_uc": {
        "label": "Assurance-Vie — Unités de Compte",
        "icon": "📈",
        "current_rate": "Variable selon allocation (espérance ~4–7 % annuel long terme)",
        "ceiling": "Aucun plafond légal",
        "tax": "Identique AV fonds € (PFU avant 8 ans, PS 17,2 % + abattement après 8 ans)",
        "liquidity": "Disponible à tout moment",
        "lock_up": None,
        "penalty": "Frais de rachat possibles selon contrat. Risque de moins-value sur UC.",
        "best_for": "Exposition marchés dans une enveloppe fiscalement avantageuse.",
        "watch_out": "Capital non garanti — valeur peut baisser. Adaptée si horizon > 10 ans.",
        "horizon": "Long terme (10 ans+)",
    },
    "pea": {
        "label": "PEA — Plan d'Épargne en Actions",
        "icon": "📊",
        "current_rate": "Variable (actions européennes ~5–8 % historique long terme)",
        "ceiling": "150 000 € (PEA classique)",
        "tax": (
            "Avant 5 ans : PFU 30 % sur les retraits (+ clôture du plan). "
            "Après 5 ans : prélèvements sociaux uniquement (17,2 %). "
            "Dividendes et plus-values en dessous du plafond : exonérés d'IR dans le plan."
        ),
        "liquidity": (
            "Tout retrait avant 5 ans clôt le PEA. "
            "Après 5 ans : retraits libres sans clôture."
        ),
        "lock_up": "5 ans pour bénéficier de l'exonération IR",
        "penalty": "Retrait avant 5 ans = clôture + PFU 30 % sur l'ensemble des gains",
        "best_for": (
            "Meilleure enveloppe pour investissement en actions à long terme. "
            "Ouvrir dès que possible pour faire courir les 5 ans."
        ),
        "watch_out": "Réservé aux titres de sociétés européennes (OPCVM éligibles inclus).",
        "horizon": "Long terme (5 ans minimum, idéalement 10 ans+)",
        "open_conditions": "Un seul PEA par adulte.",
    },
    "scpi": {
        "label": "SCPI — Parts de Sociétés Civiles de Placement Immobilier",
        "icon": "🏢",
        "current_rate": "~4–5 % rendement annuel (taux de distribution moyen 2024)",
        "ceiling": "Aucun plafond légal",
        "tax": "Revenus fonciers soumis au PFU (30 %) ou au barème IR au choix",
        "liquidity": "Illiquide — délai de cession variable (semaines à mois)",
        "lock_up": "Aucun légal, mais recommandé horizon 8–10 ans",
        "penalty": "Risque de décote en cas de revente rapide (marché secondaire)",
        "best_for": "Diversification immobilière sans gestion locative directe.",
        "watch_out": (
            "Valeur des parts peut baisser (2023-2024 : corrections -10 à -20 % sur certaines SCPI). "
            "Délai de revente non garanti. Frais de souscription élevés (~8-12 %)."
        ),
        "horizon": "Long terme (8–10 ans minimum)",
    },
    "per": {
        "label": "PER — Plan d'Épargne Retraite",
        "icon": "🎯",
        "current_rate": "Variable selon supports (mixte fonds € + UC)",
        "ceiling": "Aucun plafond de versement légal",
        "tax": (
            "Versements déductibles du revenu imposable (dans la limite des plafonds d'épargne retraite). "
            "Gains en phase d'accumulation non taxés. "
            "Sortie en capital ou en rente : imposition à l'IR (plus 17,2 % PS sur les gains)."
        ),
        "liquidity": "Bloqué jusqu'à la retraite (sauf cas de déblocage anticipé)",
        "lock_up": (
            "Jusqu'à l'âge de la retraite. "
            "Déblocages exceptionnels : acquisition résidence principale, invalidité, décès du conjoint, "
            "surendettement, fin de droits au chômage."
        ),
        "penalty": (
            "Pas de pénalité légale, mais argent immobilisé jusqu'à la retraite. "
            "Avantage fiscal à l'entrée = imposition à la sortie."
        ),
        "best_for": (
            "Réduction d'impôt immédiate si tranche marginale élevée (30 %+). "
            "Complément de retraite avec sortie en capital ou rente."
        ),
        "watch_out": (
            "Avantage fiscal = différé d'imposition, pas exonération totale. "
            "Si tranche marginale à la retraite ≈ tranche active, gain fiscal limité. "
            "Pour AE avec versement libératoire, l'avantage est réduit."
        ),
        "horizon": "Très long terme (jusqu'à la retraite)",
    },
    "cto": {
        "label": "Compte-Titres Ordinaire (CTO)",
        "icon": "📉",
        "current_rate": "Variable (actions, ETF, obligations)",
        "ceiling": "Aucun",
        "tax": "PFU 30 % sur dividendes et plus-values (ou barème IR)",
        "liquidity": "Totalement libre — aucun blocage",
        "lock_up": None,
        "penalty": "Aucune",
        "best_for": (
            "Dépassement des plafonds PEA/AV. "
            "Accès à tous les marchés mondiaux (non limité aux actions européennes)."
        ),
        "watch_out": "Fiscalité la moins avantageuse parmi les enveloppes — à utiliser en dernier.",
        "horizon": "Tous horizons",
    },
}
```

---

## 8.9.C — Per-vehicle balance projection chart

### What it shows
Below the rules panel for each vehicle (or in a combined view), show a line chart of:
- **Balance over time** (from now to retirement) — already computed by the projection engine
- **Lifecycle event overlays**: colored vertical bands at years when life events cause
  major expenses (kids at 18, house renovation, car replacement, etc.)
- **Drawdown moments** highlighted with annotations: "Votre grange en 2028 : -20 000 €.
  À cette date votre Livret A aura X€, votre PEA aura Y€. Le retrait impactera surtout..."

### Backend: expose per-vehicle balance timeline

The projection engine already computes per-vehicle balances in `year_drill_down`.
Add an endpoint: `GET /api/projection/vehicle-timeline` that returns:

```json
{
  "vehicles": {
    "livret_a": [
      {"year": 2026, "age": 40, "balance": 6000, "contributions": 6000, "returns": 0},
      {"year": 2027, "age": 41, "balance": 12090, "contributions": 6000, "returns": 90},
      ...
    ],
    "pea": [...],
    ...
  },
  "lifecycle_events": [
    {"year": 2028, "label": "Rénovation grange", "amount": -20000, "type": "project"},
    {"year": 2033, "label": "Ellie : études supérieures", "amount": -6000, "type": "kid"},
    ...
  ]
}
```

### Frontend: vehicle balance chart per vehicle

In the savings tab, each vehicle card shows a sparkline chart (small, not a full chart).
Clicking "Voir la projection" expands to a full chart with lifecycle overlays.

Use the existing SVG chart component from the runway page, parameterised for a single vehicle.

**Smart drawdown warning example:**
```
"Pour votre projet Rénovation grange en 2028, vous aurez besoin de 20 000 €.
À ce moment :
  • Livret A : ~18 000 € — couvrira presque tout
  • PEA : ~8 000 € mais le débloquer avant 5 ans clôt votre plan ! ⚠️
Conseil : conservez votre PEA. Le Livret A + 2 000 € d'AV suffisent."
```

This contextual advice should be computed backend-side and surfaced as strings in the
`lifecycle_events` array (add an `advice` field).

---

## DONE WHEN
- [ ] `VEHICLE_RULES` dict exists in `vehicles.py` with all 11 vehicles (7 existing + LEP, PEL, CTO, PEE)
- [ ] GET `/api/vehicles/catalog` returns full rules for all vehicles
- [ ] Savings tab shows all vehicles, even ones with 0 contribution (greyed out / "Ajouter")
- [ ] Each vehicle has an ℹ️ panel with: rate, tax treatment, lock-up, ceiling, best_for, watch_out
- [ ] GET `/api/projection/vehicle-timeline` returns per-vehicle balance arrays
- [ ] Each vehicle card shows a sparkline balance chart
- [ ] Lifecycle event overlays are shown on the chart (colored bands)
- [ ] At least one contextual drawdown warning is generated for Richard's renovation grange project
- [ ] LEP vehicle shows income-restriction note based on current household income
- [ ] PEA shows "5 ans à courir depuis..." if already opened (or "À ouvrir dès maintenant" if not)
- [ ] AV shows "Contrat ouvert depuis X ans — avantage fiscal {en cours / acquis}"
