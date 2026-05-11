"""Prescriptive advice engine — rule-based recommendations (TASK-7.15).

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
    """Generate prescriptive advice from all available data.

    Args:
        timeline: Projection timeline (list of YearProjection dataclasses).
        lifecycle_alerts: List of lifecycle alert dicts.
        expense_events: List of expense event dicts with keys:
            category, event, impact_monthly, year.
        profile: Dict with keys: status, target_retirement_age, has_spouse, spouse_is_cc.
        investments: Dict of vehicle_key → {existing_balance, monthly_contribution}.
        sensitivity: Optional sensitivity analysis results.

    Returns:
        List of Advice objects sorted by priority.
    """
    advice_list: list[Advice] = []

    # ── Rule 1: Redirect freed loan payments ─────────────────────────
    for event in expense_events:
        if event.get("category") == "loan_end":
            impact_str = event.get("impact_monthly", "0")
            monthly_freed = abs(Decimal(str(impact_str)))
            if monthly_freed >= Decimal("100"):
                # Rough impact: monthly_freed × 12 × years_remaining × ~1.5
                years_left = max(1, profile.get("target_retirement_age", 70) - event.get("year", 2035) + 30)
                rough_impact = monthly_freed * Decimal("12") * Decimal(str(years_left)) * Decimal("1.5")
                advice_list.append(Advice(
                    id=f"redirect_loan_{event.get('year', 0)}",
                    category="savings",
                    priority=1,
                    title=f"Redirigez {monthly_freed:.0f}€/mois quand le prêt se termine",
                    description=f"En {event['year']}, votre prêt se termine. Ces {monthly_freed:.0f}€/mois libérés peuvent être redirigés vers l'épargne.",
                    impact_text=f"Impact estimé : +{rough_impact:,.0f}€ sur le patrimoine final",
                    action_text=f"Configurez un virement automatique de {monthly_freed:.0f}€/mois vers votre PEA ou AV à partir de {event['year']}.",
                    trigger_year=event.get("year"),
                    link_to="/savings",
                ))

    # ── Rule 2: Kids becoming independent ────────────────────────────
    for event in expense_events:
        category = event.get("category", "")
        event_name = event.get("event", "")
        if category == "kid_independence" or "indépendant" in event_name.lower():
            impact_str = str(abs(Decimal(str(event.get("impact_monthly", "0")))))
            advice_list.append(Advice(
                id=f"kid_independent_{event.get('year', 0)}",
                category="expenses",
                priority=3,
                title=f"Dépenses enfant réduites en {event.get('year')}",
                description=f"{event.get('event', 'Enfant indépendant')} — vos dépenses mensuelles baissent.",
                impact_text=f"Économie : {impact_str}€/mois",
                action_text="Réévaluez votre budget et redirigez le surplus vers l'épargne.",
                trigger_year=event.get("year"),
                link_to="/expenses",
            ))

    # ── Rule 3: Livret A at ceiling → redirect to PEA/AV ────────────
    livret_data = investments.get("livret_a", {})
    livret_balance = Decimal(str(livret_data.get("existing_balance", "0")))
    livret_ceiling = Decimal("22950")
    if livret_balance >= livret_ceiling * Decimal("0.9"):
        livret_monthly = Decimal(str(livret_data.get("monthly_contribution", "0")))
        if livret_monthly > 0:
            advice_list.append(Advice(
                id="livret_a_ceiling",
                category="savings",
                priority=1,
                title=f"Livret A proche du plafond — redirigez {livret_monthly:.0f}€/mois",
                description=f"Votre Livret A est à {livret_balance:.0f}€ (plafond {livret_ceiling}€). L'argent au-delà ne rapporte rien.",
                impact_text="Un PEA rapporte ~7%/an vs 2.5% au Livret A",
                action_text=f"Redirigez vos {livret_monthly:.0f}€/mois de Livret A vers un PEA ou une AV.",
                trigger_year=None,
                link_to="/savings",
            ))

    # ── Rule 4: No PEA allocation ────────────────────────────────────
    pea_data = investments.get("pea", {})
    pea_monthly = Decimal(str(pea_data.get("monthly_contribution", "0")))
    total_savings = sum(
        Decimal(str(v.get("monthly_contribution", "0")))
        for v in investments.values()
        if isinstance(v, dict)
    )
    if pea_monthly == 0 and total_savings > 200:
        advice_list.append(Advice(
            id="no_pea",
            category="savings",
            priority=1,
            title="Ouvrez un PEA — le véhicule le plus efficace",
            description=f"Vous épargnez {total_savings:.0f}€/mois mais rien en PEA. Le PEA offre ~7%/an net après 5 ans (vs 2.5% Livret A).",
            impact_text="Rediriger 50% de votre épargne vers un PEA pourrait ajouter 100k€+ au patrimoine",
            action_text="Allouez au moins 50% de votre épargne mensuelle au PEA.",
            trigger_year=None,
            link_to="/savings",
        ))

    # ── Rule 5: High expense ratio vs income ─────────────────────────
    if timeline and len(timeline) > 0:
        first = timeline[0]
        total_inc = Decimal(str(getattr(first, "total_income", "1")))
        total_out = Decimal(str(getattr(first, "total_outgoing", "0")))
        if total_inc > 0:
            expense_ratio = total_out / total_inc
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