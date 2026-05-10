# TASK-6.9: Smart Lifecycle Alerts

**Status:** TODO
**Sprint:** 6
**Priority:** P2 (medium — builds on other tasks)
**Est. effort:** 2 hr
**Dependencies:** TASK-6.3, TASK-6.4, TASK-5.4

## Context

The projection engine knows exactly when major financial events happen: the mortgage ends in 2035, Saoirse finishes études in 2041, the Xsara needs replacement next year, the Livret A hits its ceiling in 2029. Each of these creates an opportunity or a risk. The insights engine (Task 5.4) provides general recommendations, but lifecycle alerts are time-specific, event-driven notifications tied to exact years in the projection.

These alerts transform the Runway page from a static projection into a proactive advisor: "In 2035, your mortgage ends. Here's what to do with the freed 500€/month."

## Requirements

### Alert Types

1. **Loan termination alert:**
   - Trigger: loan end_date within projection period
   - Alert: "En {year}, votre {label} se termine. Les {monthly}€/mois libérés pourraient être redirigés vers votre PEA (+{impact}k€ au patrimoine final)."
   - Action: link to savings allocation + scenario comparison

2. **Kid independence alert:**
   - Trigger: kid's last cost event ends
   - Alert: "En {year}, {name} termine ses études. Vos dépenses diminuent de ~{amount}€/mois."
   - Multi-kid: "Entre {year1} et {year2}, vos 3 enfants deviennent indépendants. Vos dépenses enfants passent de {peak}€/mois à 0€."

3. **Car replacement due:**
   - Trigger: replacement event within 2 years
   - Alert: "Remplacement de votre {name} prévu en {year} (~{cost}€). Assurez-vous d'avoir les fonds disponibles."

4. **Investment ceiling approaching:**
   - Trigger: projected balance > 90% of ceiling within 3 years
   - Alert: "Votre Livret A atteindra son plafond de 22 950€ en {year}. Prévoyez une réallocation vers LDDS ou AV."

5. **Status change optimal window:**
   - Trigger: projected CA crosses the AE→SASU breakeven point
   - Alert: "En {year}, votre CA projeté de {ca}€ rend le passage en SASU avantageux (économie estimée: {savings}€/an)."

6. **Retirement countdown:**
   - Trigger: 10, 5, 3, 1 years before target retirement age
   - Alert: "Plus que {n} ans avant votre objectif de retraite. Bilan : patrimoine projeté {wealth}€, revenu passif {passive}€/mois."

7. **Pet end-of-life:**
   - Trigger: pet's last cost event approaching (2 years)
   - Alert: "Les coûts pour {name} se terminent vers {year}. Souhaitez-vous prévoir un nouvel animal ?" (delicate — offer, don't push)

8. **Expense peak year:**
   - Trigger: year with highest total expenses in the projection
   - Alert: "L'année {year} sera votre pic de dépenses ({total}€/mois) — {reason}. Anticipez avec un fonds de trésorerie."

### Backend

9. **Extend insights engine** to generate lifecycle alerts:
   ```python
   def generate_lifecycle_alerts(
       projection: list[YearProjection],
       loans: list[dict],
       life_entities: list[dict],
       allocations: dict,
       profile: ProjectionInput,
   ) -> list[LifecycleAlert]:
   ```

10. **Alert schema:**
    ```python
    @dataclass
    class LifecycleAlert:
        id: str
        alert_type: str        # "loan_end", "kid_independence", "car_replacement", etc.
        year: int
        age: int
        severity: str          # "info" | "action" | "warning"
        title: str
        description: str
        impact_monthly: Decimal | None
        impact_wealth: Decimal | None
        action_label: str | None
        action_link: str | None    # Section to navigate to
    ```

### Frontend

11. **Lifecycle timeline** on Runway page:
    - Chronological list of alerts, grouped by year
    - Color-coded by type: loans (amber), kids (purple), cars (sky), investments (teal), retirement (emerald)
    - Each alert: icon + year + title + description + action button
    - Collapsible by year (show next 5 years expanded, rest collapsed)

12. **Alert badges in sidebar navigation:**
    - Show a small badge count on relevant sections (e.g., "Vie: 2 alertes")
    - Helps guide the user to sections that need attention

## Acceptance Criteria

- [ ] At least 6 alert types implemented
- [ ] Alerts generated from projection + loans + life entities
- [ ] Alerts include specific years, amounts, and suggested actions
- [ ] Frontend renders chronological timeline
- [ ] Action buttons link to relevant sections
- [ ] No alert spam — max 3-4 alerts per year, prioritized by impact
- [ ] Sensitive alerts (pet EOL) handled delicately
- [ ] Unit tests for each alert type
- [ ] LEARNINGS.md updated
