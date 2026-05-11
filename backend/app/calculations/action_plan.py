"""Monthly action plan generator (TASK-7.17).

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
    """Generate this month's action plan.

    Args:
        profile: Dict with keys: cesu_annual, status.
        investments: Dict of vehicle_key → {existing_balance, monthly_contribution}.
        income_sources: List of dicts with: id, label, amount, frequency,
            end_date, confidence, is_active.
        loans: List of dicts with: id, label, monthly_payment, end_date.
        advice: Reserved for cross-referencing advice engine output.
        current_date: Override date for testability.

    Returns:
        List of up to 10 MonthlyAction objects sorted by priority.
    """
    today = current_date or date.today()
    actions: list[MonthlyAction] = []

    # ── 1: Savings redirect if Livret A at ceiling ───────────────────
    livret_data = investments.get("livret_a", {})
    livret_bal = Decimal(str(livret_data.get("existing_balance", "0")))
    livret_monthly = Decimal(str(livret_data.get("monthly_contribution", "0")))
    if livret_bal >= Decimal("22950") and livret_monthly > 0:
        actions.append(MonthlyAction(
            id="redirect_livret_a",
            priority=1,
            category="savings",
            title=f"Redirigez {livret_monthly:.0f}€ du Livret A vers PEA",
            detail=f"Votre Livret A est au plafond ({livret_bal:.0f}€). Les {livret_monthly:.0f}€/mois n'y rapportent plus rien. Ouvrez ou alimentez un PEA.",
            amount=livret_monthly,
            link_to="/savings",
        ))

    # ── 2: Client ending soon — start prospecting ────────────────────
    for src in income_sources:
        if not src.get("end_date"):
            continue
        try:
            end = date.fromisoformat(src["end_date"])
        except (ValueError, TypeError):
            continue
        months_left = (end.year - today.year) * 12 + (end.month - today.month)
        if 0 < months_left <= 3:
            amount_str = str(src.get("amount", "0"))
            freq = src.get("frequency", "monthly")
            monthly = (
                Decimal(amount_str)
                if freq == "monthly"
                else Decimal(amount_str) / Decimal("12")
            )
            actions.append(MonthlyAction(
                id=f"client_ending_{src.get('id', 0)}",
                priority=1,
                category="income",
                title=f"Contrat « {src.get('label', '')} » se termine dans {months_left} mois",
                detail=f"Vous perdrez {monthly:.0f}€/mois. Commencez à prospecter maintenant pour trouver un remplacement.",
                amount=monthly,
                link_to="/revenue",
            ))

    # ── 3: Loan ending soon — plan redirect ──────────────────────────
    for loan in loans:
        if not loan.get("end_date"):
            continue
        try:
            end = date.fromisoformat(loan["end_date"])
        except (ValueError, TypeError):
            continue
        months_left = (end.year - today.year) * 12 + (end.month - today.month)
        if 0 < months_left <= 6:
            monthly = Decimal(str(loan.get("monthly_payment", "0")))
            actions.append(MonthlyAction(
                id=f"loan_ending_{loan.get('id', '')}",
                priority=2,
                category="savings",
                title=f"Prêt « {loan.get('label', 'Prêt')} » se termine dans {months_left} mois",
                detail=f"Planifiez un virement automatique de {monthly:.0f}€/mois vers votre PEA ou AV à partir de la fin du prêt.",
                amount=monthly,
                link_to="/savings",
            ))

    # ── 4: No savings allocation — critical gap ──────────────────────
    total_savings = sum(
        Decimal(str(v.get("monthly_contribution", "0")))
        for v in investments.values()
        if isinstance(v, dict)
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
            amount_str = str(src.get("amount", "0"))
            freq = src.get("frequency", "monthly")
            monthly = (
                Decimal(amount_str)
                if freq == "monthly"
                else Decimal("0")
            )
            if monthly > 500:
                actions.append(MonthlyAction(
                    id=f"secure_income_{src.get('id', 0)}",
                    priority=2,
                    category="income",
                    title=f"Sécurisez « {src.get('label', '')} » ({monthly:.0f}€/mois)",
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
        per_data = investments.get("per", {})
        per_monthly = Decimal(str(per_data.get("monthly_contribution", "0")))
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