"""
Insights engine (TASK-5.4) — analyzes a projection and produces ranked,
actionable recommendations with specific quantified impact.

Design:
  - Pure functions, no DB access. Testable standalone.
  - Each insight rule is a separate function returning Insight or None.
  - Impact is estimated analytically (no re-running the full engine).
  - Max 5 insights returned, sorted by |impact_wealth| descending.

Integration:
  - Called by the projection router after timeline + summary are computed.
  - Response includes insight list alongside timeline.

DO NOT give legal/tax advice. Recommending a professional is mandatory
for structural changes (status change, dividend optimisation, etc.).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


# ── Data structures ──────────────────────────────────────────────────────────


@dataclass
class Insight:
    """A single actionable insight with supporting data.

    Serialized via Pydantic in schemas/projection.py.
    """

    id: str  # stable identifier e.g. "low_savings_rate"
    category: str  # "savings" | "income" | "expenses" | "structure" | "allocation"
    severity: str  # "critical" | "warning" | "opportunity" | "positive"
    title: str  # short headline (i18n key prefix)
    description: str  # explanation with specific numbers (interpolated)
    impact_wealth: Decimal  # estimated € impact on final wealth
    action: str  # what to do (short directive)
    priority: int = 0  # set by ranking


# ── Public API ───────────────────────────────────────────────────────────────


def generate_insights(
    timeline: list[Any],  # list of YearProjection dataclass
    summary: dict[str, Any],
    profile_data: dict[str, Any],  # flat dict of profile values
    allocations: list[dict[str, Any]],  # vehicle allocations
) -> list[Insight]:
    """Analyze a projection and return ranked, actionable insights.

    Args:
        timeline: Full projection timeline (list of YearProjection).
        summary: Dict from compute_summary().
        profile_data: Flat dict of profile values (monthly_gross, growth_rate, etc.).
        allocations: List of allocation dicts with vehicle_key, monthly, balance.

    Returns:
        Up to 5 Insight objects, sorted by impact magnitude descending.
        Critical severity items always rank above others regardless of impact.
    """
    if not timeline:
        return []

    all_insights: list[Insight | None] = []

    # ── Critical: retirement at risk ──────────────────────────────────
    all_insights.append(
        _check_wealth_exhaustion(timeline, summary)
    )
    all_insights.append(
        _check_no_goal_reached(timeline, summary)
    )
    all_insights.append(
        _check_negative_net_any_year(timeline)
    )

    # ── Warning: sub-optimal ─────────────────────────────────────────
    all_insights.append(
        _check_low_savings_rate(timeline, summary, allocations)
    )
    all_insights.append(
        _check_unbalanced_allocations(allocations)
    )
    all_insights.append(
        _check_livret_a_near_ceiling(allocations)
    )

    # ── Opportunity: things that could improve ───────────────────────
    all_insights.append(
        _check_increase_ca_growth(timeline, summary, profile_data)
    )
    all_insights.append(
        _check_one_more_year(timeline, summary)
    )
    all_insights.append(
        _check_kid_peak_cost(timeline, profile_data)
    )

    # ── Positive: things going well ──────────────────────────────────
    all_insights.append(
        _check_goal_reached_early(timeline, summary)
    )
    all_insights.append(
        _check_good_savings_rate(timeline, summary, allocations)
    )

    # Filter and rank
    valid: list[Insight] = [i for i in all_insights if i is not None]

    # Sort: critical first, then by |impact_wealth| descending
    severity_order = {"critical": 0, "warning": 1, "opportunity": 2, "positive": 3}

    valid.sort(
        key=lambda i: (severity_order.get(i.severity, 99), -abs(float(i.impact_wealth)))
    )

    # Assign priorities, keep top 5
    for idx, ins in enumerate(valid[:5]):
        ins.priority = idx + 1

    return valid[:5]


# ── Critical rules ───────────────────────────────────────────────────────────


def _check_wealth_exhaustion(
    timeline: list[Any],
    summary: dict[str, Any],
) -> Insight | None:
    """Wealth runs out before age 90."""
    exhaustion_age = summary.get("wealth_exhaustion_age")
    if exhaustion_age is None:
        return None
    if exhaustion_age >= 90:
        return None

    # Roughly how much more per month needed?
    # Find total shortfall and divide by remaining working years
    retirement_start_idx = next(
        (i for i, t in enumerate(timeline) if getattr(t, "is_retirement", False)),
        None,
    )
    if retirement_start_idx is None:
        return None

    remaining_years = exhaustion_age - timeline[retirement_start_idx].age
    total_needed = abs(sum(
        (getattr(t, "total_outgoing", Decimal("0")) - getattr(t, "total_income", Decimal("0")))
        for t in timeline[retirement_start_idx:]
        if getattr(t, "age", 0) <= exhaustion_age
    )) or Decimal("1")

    # Approx extra monthly needed during working years to fill this gap
    working_years = max(1, getattr(timeline[0], "age", 40) - 1)  # roughly
    extra_monthly = total_needed / Decimal(str(max(1, working_years * 12)))
    # Impact is the total needed
    impact_wealth = -total_needed

    return Insight(
        id="wealth_exhaustion",
        category="savings",
        severity="critical",
        title=f"Patrimoine épuisé à {exhaustion_age} ans",
        description=(
            f"Votre épargne ne couvre que {exhaustion_age - timeline[retirement_start_idx].age} ans de retraite. "
            f"Pour tenir jusqu'à 95 ans, épargnez {_fmt_euro(extra_monthly)}/mois de plus."
        ),
        impact_wealth=impact_wealth,
        action=f"Augmentez votre épargne mensuelle de {_fmt_euro(extra_monthly)}",
    )


def _check_no_goal_reached(
    timeline: list[Any],
    summary: dict[str, Any],
) -> Insight | None:
    """Goal never reached in accumulation phase."""
    goal_year = summary.get("goal_year")
    if goal_year is not None:
        return None

    # Check if any goal_reached in timeline
    any_goal = any(
        getattr(t, "goal_reached", False) and not getattr(t, "is_retirement", False)
        for t in timeline
    )
    if any_goal:
        return None

    # No goal reached. If no goal was set, don't complain.
    last = timeline[-1] if timeline else None
    if last is None:
        return None

    passive_monthly = getattr(last, "passive_monthly", Decimal("0"))
    # Just report that goal is not reached
    return Insight(
        id="no_goal_reached",
        category="savings",
        severity="warning",
        title="Objectif non atteint",
        description=(
            f"Votre objectif de revenu n'est pas atteint à la retraite. "
            f"Actuellement {_fmt_euro(passive_monthly)}/mois de passif projeté."
        ),
        impact_wealth=Decimal("0"),
        action="Augmentez l'épargne ou ajoutez des projets de revenus",
    )


def _check_negative_net_any_year(timeline: list[Any]) -> Insight | None:
    """Net annual income goes negative."""
    negative_years = [
        t for t in timeline
        if getattr(t, "net_annual", Decimal("0")) < Decimal("0")
        and not getattr(t, "is_retirement", False)
    ]
    if not negative_years:
        return None

    first = negative_years[0]
    return Insight(
        id="negative_net",
        category="expenses",
        severity="critical",
        title=f"Dépenses > revenus en {first.year}",
        description=(
            f"Vos dépenses dépassent vos revenus en {first.year} (âge {first.age} ans). "
            "Votre épargne fond au lieu de croître."
        ),
        impact_wealth=Decimal("-50000"),  # rough estimate
        action="Vérifiez vos charges et votre CA prévisionnel",
    )


# ── Warning rules ────────────────────────────────────────────────────────────


def _check_low_savings_rate(
    timeline: list[Any],
    summary: dict[str, Any],
    allocations: list[dict[str, Any]],
) -> Insight | None:
    """Savings rate below 15% of net income."""
    if not timeline or not allocations:
        return None

    t0 = timeline[0]
    net_annual = getattr(t0, "net_annual", Decimal("0"))
    if net_annual <= 0:
        return None

    total_monthly_savings = sum(
        Decimal(str(a.get("monthly", 0))) for a in allocations
    )
    total_annual_savings = total_monthly_savings * Decimal("12")
    savings_rate = total_annual_savings / net_annual

    if savings_rate >= Decimal("0.15"):
        return None

    rate_pct = int(float(savings_rate * 100))
    target_pct = 20
    extra_monthly = (net_annual * Decimal("0.20") - total_annual_savings) / Decimal("12")

    # Approx impact: extra * 12 * years * compounding factor
    years = 30
    avg_return = Decimal("1.05") ** (years // 2)
    impact = extra_monthly * Decimal("12") * Decimal(str(years)) * avg_return

    return Insight(
        id="low_savings_rate",
        category="savings",
        severity="warning",
        title=f"Taux d'épargne faible ({rate_pct}%)",
        description=(
            f"Vous épargnez {rate_pct}% de votre net. "
            f"Visant 20%, {_fmt_euro(extra_monthly)}/mois de plus "
            f"ajouterait environ {_fmt_euro(impact)} à votre patrimoine."
        ),
        impact_wealth=impact,
        action=f"Augmentez vos versements de {_fmt_euro(extra_monthly)}/mois",
    )


def _check_unbalanced_allocations(
    allocations: list[dict[str, Any]],
) -> Insight | None:
    """>80% of monthly savings in low-return vehicles (Livret A, LDDS, AV euro)."""
    if not allocations:
        return None

    total_monthly = sum(
        Decimal(str(a.get("monthly", 0))) for a in allocations
    )
    if total_monthly <= 0:
        return None

    low_return = sum(
        Decimal(str(a.get("monthly", 0)))
        for a in allocations
        if a.get("vehicle_key") in ("livret_a", "ldds", "av_euro")
    )
    pct = low_return / total_monthly

    if pct <= Decimal("0.80"):
        return None

    return Insight(
        id="savings_allocation_unbalanced",
        category="allocation",
        severity="warning",
        title="Épargne trop prudente",
        description=(
            "Plus de 80% de vos versements sont sur des supports à faible rendement "
            "(Livret A, LDDS, fonds euros). Diversifier vers AV UC ou PEA augmenterait votre patrimoine final."
        ),
        impact_wealth=Decimal("30000"),  # rough
        action="Redirigez une partie vers PEA ou AV unités de compte",
    )


def _check_livret_a_near_ceiling(
    allocations: list[dict[str, Any]],
) -> Insight | None:
    """Livret A balance near 22,950€ ceiling."""
    for a in allocations:
        if a.get("vehicle_key") != "livret_a":
            continue
        balance = Decimal(str(a.get("balance", 0)))
        if balance < Decimal("18000"):
            return None
        return Insight(
            id="livret_a_near_ceiling",
            category="allocation",
            severity="warning",
            title="Livret A proche du plafond",
            description=(
                f"Votre Livret A ({_fmt_euro(balance)}) approche le plafond de 22 950€. "
                "Redirigez les prochains versements vers un support plus rentable."
            ),
            impact_wealth=Decimal("10000"),
            action="Ouvrez un PEA ou renforcez votre AV",
        )
    return None


# ── Opportunity rules ────────────────────────────────────────────────────────


def _check_increase_ca_growth(
    timeline: list[Any],
    summary: dict[str, Any],
    profile_data: dict[str, Any],
) -> Insight | None:
    """If growth rate is low, suggest increasing it."""
    growth_rate = profile_data.get("growth_rate", Decimal("0"))
    if isinstance(growth_rate, (int, float)):
        growth_rate = Decimal(str(growth_rate))
    if growth_rate >= Decimal("0.03"):
        return None

    # Roughly, 1% more growth = 1% more income each year compounded over 30 years
    final_wealth = Decimal(str(summary.get("final_wealth", "0")))
    extra = final_wealth * Decimal("0.10")  # ~10% more over 30 years

    return Insight(
        id="increase_ca_growth",
        category="income",
        severity="opportunity",
        title="Augmentez votre croissance de CA",
        description=(
            f"Passer d'une croissance prudente ({int(float(growth_rate) * 100)}%) "
            f"à 3% ajouterait environ {_fmt_euro(extra)} à votre patrimoine."
        ),
        impact_wealth=extra,
        action="Passez en croissance modérée ou optimiste dans Revenus",
    )


def _check_one_more_year(
    timeline: list[Any],
    summary: dict[str, Any],
) -> Insight | None:
    """Working one more year adds significant wealth."""
    # Find last accumulation year
    acc_years = [t for t in timeline if not getattr(t, "is_retirement", False)]
    if len(acc_years) < 2:
        return None

    last_acc = acc_years[-1]
    prev_acc = acc_years[-2]
    delta = last_acc.total_wealth - prev_acc.total_wealth

    if delta <= 0:
        return None

    return Insight(
        id="one_more_year",
        category="income",
        severity="opportunity",
        title="Une année de plus ferait la différence",
        description=(
            f"Repousser la retraite d'un an ajouterait environ {_fmt_euro(delta)} "
            "à votre patrimoine tout en réduisant la durée de retrait."
        ),
        impact_wealth=delta,
        action="Envisagez de repousser votre âge de retraite d'un an",
    )


def _check_kid_peak_cost(
    timeline: list[Any],
    profile_data: dict[str, Any],
) -> Insight | None:
    """Find the year where kid expenses peak."""
    kid_years = [
        (t, getattr(t, "kid_expenses", Decimal("0")))
        for t in timeline
        if getattr(t, "kid_expenses", Decimal("0")) > Decimal("0")
    ]
    if not kid_years:
        return None

    peak = max(kid_years, key=lambda x: x[1])
    t, amount = peak

    return Insight(
        id="kid_peak_cost_year",
        category="expenses",
        severity="opportunity",
        title=f"Pic de dépenses enfants en {t.year}",
        description=(
            f"Les coûts des enfants atteignent {_fmt_euro(amount)}/an en {t.year} "
            f"(âge {t.age} ans). Anticipez cette période."
        ),
        impact_wealth=Decimal("0"),
        action="Mettez de côté en prévision de cette période",
    )


# ── Positive rules ───────────────────────────────────────────────────────────


def _check_goal_reached_early(
    timeline: list[Any],
    summary: dict[str, Any],
) -> Insight | None:
    """Goal reached before retirement age."""
    goal_year = summary.get("goal_year")
    if goal_year is None:
        return None

    # Find retirement start year
    retirement_entry = next(
        (t for t in timeline if getattr(t, "is_retirement", False)), None
    )
    if retirement_entry is None:
        return None

    retirement_year = retirement_entry.year
    if goal_year["year"] >= retirement_year:
        return None

    return Insight(
        id="goal_reached_early",
        category="savings",
        severity="positive",
        title="Objectif atteint avant la retraite",
        description=(
            f"Félicitations ! Votre objectif est atteint dès {goal_year['year']} "
            f"(à {goal_year['age']} ans), soit {retirement_year - goal_year['year']} ans avant la retraite."
        ),
        impact_wealth=Decimal("0"),
        action="Continuez sur cette lancée",
    )


def _check_good_savings_rate(
    timeline: list[Any],
    summary: dict[str, Any],
    allocations: list[dict[str, Any]],
) -> Insight | None:
    """Savings rate above 25%."""
    if not timeline or not allocations:
        return None

    t0 = timeline[0]
    net_annual = getattr(t0, "net_annual", Decimal("0"))
    if net_annual <= 0:
        return None

    total_monthly_savings = sum(
        Decimal(str(a.get("monthly", 0))) for a in allocations
    )
    total_annual_savings = total_monthly_savings * Decimal("12")
    savings_rate = total_annual_savings / net_annual

    if savings_rate < Decimal("0.25"):
        return None

    rate_pct = int(float(savings_rate * 100))
    return Insight(
        id="good_savings_rate",
        category="savings",
        severity="positive",
        title=f"Excellent taux d'épargne ({rate_pct}%)",
        description=(
            f"Vous épargnez {rate_pct}% de votre revenu net — "
            "bien au-dessus des 20% recommandés. Continuez."
        ),
        impact_wealth=Decimal("0"),
        action="Maintenez le cap",
    )


# ── Helpers ──────────────────────────────────────────────────────────────────


def _fmt_euro(value: Decimal) -> str:
    """Format a Decimal as a French-locale euro string (e.g. '1 200€')."""
    if value == Decimal("0") or value == Decimal("0.00"):
        return "0€"
    n = int(float(value))
    if n < 0:
        return f"-{_format_abs(abs(n))}"
    return _format_abs(n)


def _format_abs(n: int) -> str:
    """Format a positive integer with French thousands separator."""
    s = f"{n}"
    result = ""
    for i, ch in enumerate(reversed(s)):
        if i > 0 and i % 3 == 0:
            result = "\u00a0" + result
        result = ch + result
    return result + "€"


# ── Lifecycle Alerts (TASK-6.9) ───────────────────────────────────────────────


@dataclass
class LifecycleAlert:
    """A time-specific alert tied to an exact year in the projection.

    Unlike general Insights, these are event-driven and tied to specific
    lifecycle moments: loan termination, kid independence, car replacement, etc.
    """

    id: str  # stable identifier e.g. "loan_end_2035"
    alert_type: str  # "loan_end" | "kid_independence" | "car_replacement" | "ceiling" | "status_change" | "retirement_countdown" | "pet_eol" | "expense_peak"
    year: int
    age: int
    severity: str  # "info" | "action" | "warning"
    title: str
    description: str
    impact_monthly: Decimal | None = None
    impact_wealth: Decimal | None = None
    action_label: str | None = None
    action_link: str | None = None  # section to navigate to


def generate_lifecycle_alerts(
    timeline: list[Any],
    summary: dict[str, Any],
    loans: list[dict[str, Any]],
    life_entities: list[dict[str, Any]],
    allocations: list[dict[str, Any]],
    profile_data: dict[str, Any],
) -> list[LifecycleAlert]:
    """Generate time-specific lifecycle alerts from projection data.

    Args:
        timeline: Full projection timeline.
        summary: Dict from compute_summary().
        loans: List of loan dicts from ProjectionInput.
        life_entities: List of life entity dicts from ProjectionInput.
        allocations: List of allocation dicts.
        profile_data: Dict with monthly_gross, growth_rate, target_age, current_age.

    Returns:
        List of LifecycleAlert sorted by year, max 3-4 per year.
    """
    if not timeline:
        return []

    current_year = getattr(timeline[0], "year", 2026)
    current_age = getattr(timeline[0], "age", 40)

    alerts: list[LifecycleAlert] = []

    # ── Loan termination alerts ──────────────────────────────────────
    for loan in loans:
        label = loan.get("label", "Crédit")
        monthly = Decimal(str(loan.get("monthly_payment", 0)))
        insurance = Decimal(str(loan.get("insurance_monthly", 0)))
        total_m = monthly + insurance
        if total_m <= Decimal("0"):
            continue

        end_date_str = loan.get("end_date")
        if end_date_str is None:
            continue

        if isinstance(end_date_str, str):
            end_date = __import__("datetime").date.fromisoformat(end_date_str)
        else:
            end_date = end_date_str

        end_year = end_date.year
        termination_year = end_year + 1

        if termination_year >= current_year and termination_year <= current_year + len(timeline):
            # Estimate impact on final wealth: freed cash invested over remaining years
            years_from_term = max(0, (current_year + len(timeline)) - termination_year)
            impact = total_m * Decimal("12") * Decimal(str(years_from_term)) * Decimal("0.07")

            alerts.append(
                LifecycleAlert(
                    id=f"loan_end_{termination_year}",
                    alert_type="loan_end",
                    year=termination_year,
                    age=current_age + (termination_year - current_year),
                    severity="action",
                    title=f"{label} se termine",
                    description=(
                        f"En {termination_year}, votre {label} se termine. "
                        f"Les {_fmt_euro(total_m)}/mois libérés pourraient être "
                        f"redirigés vers votre épargne (+~{_fmt_euro(impact)} au patrimoine final)."
                    ),
                    impact_monthly=total_m,
                    impact_wealth=impact,
                    action_label="Voir l'allocation d'épargne",
                    action_link="epargne",
                )
            )

    # ── Kid independence alerts ──────────────────────────────────────
    for entity in life_entities:
        if entity.get("entity_type") != "kid":
            continue
        name = entity.get("entity_name", "Enfant")
        cost_events = entity.get("cost_events", [])
        if not cost_events:
            continue

        max_to_age = max(int(evt.get("to_age", 0)) for evt in cost_events)
        entity_start_age = entity.get("entity_age_at_start", 0)
        last_cost_year_index = max_to_age - entity_start_age
        if last_cost_year_index < 0:
            continue

        independence_year = current_year + last_cost_year_index + 1

        if 0 <= last_cost_year_index < len(timeline):
            last_entry = timeline[last_cost_year_index]
            kid_annual = getattr(last_entry, "kid_expenses", Decimal("0"))
            kid_monthly = kid_annual / Decimal("12")
            if kid_monthly > Decimal("0"):
                alerts.append(
                    LifecycleAlert(
                        id=f"kid_indep_{name.lower()}_{independence_year}",
                        alert_type="kid_independence",
                        year=independence_year,
                        age=current_age + (independence_year - current_year),
                        severity="info",
                        title=f"{name} devient indépendant(e)",
                        description=(
                            f"En {independence_year}, {name} termine ses études. "
                            f"Vos dépenses enfants diminuent d'environ {_fmt_euro(kid_monthly)}/mois."
                        ),
                        impact_monthly=kid_monthly,
                        action_label="Voir l'évolution des dépenses",
                        action_link="charges",
                    )
                )

    # ── Car replacement due (within 2 years) ────────────────────────
    CAR_REPLACEMENT_THRESHOLD = Decimal("5000")
    for i, entry in enumerate(timeline):
        car_annual = getattr(entry, "car_expenses", Decimal("0"))
        if i > 0 and car_annual - getattr(timeline[i - 1], "car_expenses", Decimal("0")) > CAR_REPLACEMENT_THRESHOLD:
            year_diff = entry.year - current_year
            if 0 <= year_diff <= 2:
                extra = car_annual - getattr(timeline[i - 1], "car_expenses", Decimal("0"))
                alerts.append(
                    LifecycleAlert(
                        id=f"car_replace_{entry.year}",
                        alert_type="car_replacement",
                        year=entry.year,
                        age=getattr(entry, "age", current_age + year_diff),
                        severity="warning",
                        title="Remplacement de véhicule prévu",
                        description=(
                            f"Un remplacement de véhicule est prévu en {entry.year} "
                            f"(~{_fmt_euro(extra)}). Assurez-vous d'avoir les fonds disponibles."
                        ),
                        impact_monthly=extra / Decimal("12"),
                        action_label="Voir les véhicules",
                        action_link="vie",
                    )
                )

    # ── Investment ceiling approaching ───────────────────────────────
    for alloc in allocations:
        vehicle_key = alloc.get("vehicle_key", "")
        monthly = Decimal(str(alloc.get("monthly", 0)))
        balance = Decimal(str(alloc.get("balance", 0)))
        if monthly <= Decimal("0"):
            continue

        from app.calculations.vehicles import VEHICLE_SPECS
        spec = VEHICLE_SPECS.get(vehicle_key, {})
        ceiling_raw = spec.get("ceiling")
        ceiling = Decimal(str(ceiling_raw)) if ceiling_raw is not None else Decimal("0")
        if ceiling <= Decimal("0"):
            continue

        # Project when balance hits 90% of ceiling
        years_to_ceiling = Decimal("99")
        if monthly > Decimal("0"):
            gap = ceiling * Decimal("0.9") - balance
            if gap > Decimal("0"):
                years_to_ceiling = gap / (monthly * Decimal("12"))

        if years_to_ceiling <= Decimal("3"):
            ceiling_year = current_year + int(float(years_to_ceiling)) + 1
            alerts.append(
                LifecycleAlert(
                    id=f"ceiling_{vehicle_key}",
                    alert_type="ceiling",
                    year=ceiling_year,
                    age=current_age + int(float(years_to_ceiling)) + 1,
                    severity="info",
                    title=f"{spec.get('label', vehicle_key)} atteindra son plafond",
                    description=(
                        f"Votre {spec.get('label', vehicle_key)} atteindra son plafond "
                        f"de {_fmt_euro(ceiling)} vers {ceiling_year}. "
                        f"Prévoyez une réallocation vers un autre véhicule."
                    ),
                    action_label="Gérer l'épargne",
                    action_link="epargne",
                )
            )

    # ── Retirement countdown (10, 5, 3, 1 years) ─────────────────────
    target_age = profile_data.get("target_age", 65)
    retirement_year = current_year + (target_age - current_age)
    countdown_years = [10, 5, 3, 1]
    for cd in countdown_years:
        check_year = retirement_year - cd
        if check_year > current_year and check_year <= current_year + len(timeline):
            # Find checkpoint
            idx = check_year - current_year
            if 0 <= idx < len(timeline):
                entry = timeline[idx]
                wealth = getattr(entry, "total_wealth", Decimal("0"))
                passive = getattr(entry, "passive_monthly", Decimal("0"))
                alerts.append(
                    LifecycleAlert(
                        id=f"retirement_countdown_{cd}y",
                        alert_type="retirement_countdown",
                        year=check_year,
                        age=target_age - cd,
                        severity="info" if cd > 3 else "warning",
                        title=f"Plus que {cd} an{'s' if cd > 1 else ''} avant la retraite",
                        description=(
                            f"En {check_year}, plus que {cd} an{'s' if cd > 1 else ''} avant votre "
                            f"retraite. Patrimoine projeté : {_fmt_euro(wealth)}, "
                            f"revenu passif : {_fmt_euro(passive)}/mois."
                        ),
                        action_label="Voir la projection",
                        action_link="piste",
                    )
                )

    # ── Pet end-of-life (approaching, 2 years) ──────────────────────
    for entity in life_entities:
        if entity.get("entity_type") != "pet":
            continue
        name = entity.get("entity_name", "Animal")
        cost_events = entity.get("cost_events", [])
        if not cost_events:
            continue

        max_to_age = max(int(evt.get("to_age", 0)) for evt in cost_events)
        entity_start_age = entity.get("entity_age_at_start", 0)
        last_cost_year_index = max_to_age - entity_start_age
        if last_cost_year_index < 0:
            continue

        eol_year = current_year + last_cost_year_index + 1
        if 0 <= (eol_year - current_year) <= 2:
            alerts.append(
                LifecycleAlert(
                    id=f"pet_eol_{name.lower()}",
                    alert_type="pet_eol",
                    year=eol_year,
                    age=current_age + (eol_year - current_year),
                    severity="info",
                    title=f"{name} — fin de vie estimée",
                    description=(
                        f"Les coûts pour {name} se terminent vers {eol_year}. "
                        f"Souhaitez-vous prévoir un nouvel animal ?"
                    ),
                    action_label="Voir les entités",
                    action_link="vie",
                )
            )

    # ── Expense peak year ─────────────────────────────────────────────
    max_expense = Decimal("0")
    max_expense_year = current_year
    max_expense_age = current_age
    max_expense_idx = 0
    for i, entry in enumerate(timeline):
        expenses = (
            getattr(entry, "base_expenses", Decimal("0"))
            + getattr(entry, "loan_expenses", Decimal("0"))
            + getattr(entry, "kid_expenses", Decimal("0"))
            + getattr(entry, "pet_expenses", Decimal("0"))
            + getattr(entry, "car_expenses", Decimal("0"))
            + getattr(entry, "tech_expenses", Decimal("0"))
            + getattr(entry, "recurring_expenses", Decimal("0"))
        )
        if expenses > max_expense:
            max_expense = expenses
            max_expense_year = entry.year
            max_expense_age = entry.age
            max_expense_idx = i

    if max_expense > Decimal("0") and max_expense_year > current_year:
        total_monthly = max_expense / Decimal("12")
        # Find out why — check active life entities
        reasons = []
        entry = timeline[max_expense_idx]
        if getattr(entry, "kid_expenses", Decimal("0")) > Decimal("0"):
            reasons.append("enfants à charge")
        if getattr(entry, "loan_expenses", Decimal("0")) > Decimal("0"):
            reasons.append("crédits actifs")
        if getattr(entry, "car_expenses", Decimal("0")) > Decimal("5000"):
            reasons.append("remplacement véhicule")
        reason_str = " + ".join(reasons) if reasons else "dépenses courantes"

        alerts.append(
            LifecycleAlert(
                id=f"expense_peak_{max_expense_year}",
                alert_type="expense_peak",
                year=max_expense_year,
                age=max_expense_age,
                severity="info",
                title=f"Pic de dépenses en {max_expense_year}",
                description=(
                    f"L'année {max_expense_year} sera votre pic de dépenses "
                    f"({_fmt_euro(total_monthly)}/mois) — {reason_str}. "
                    f"Anticipez avec un fonds de trésorerie."
                ),
                impact_monthly=total_monthly,
                action_label="Voir les charges",
                action_link="charges",
            )
        )

    # Sort by year, no more than 3 per year
    alerts.sort(key=lambda a: (a.year, {"warning": 0, "action": 1, "info": 2}.get(a.severity, 3)))
    filtered: list[LifecycleAlert] = []
    year_counts: dict[int, int] = {}
    for alert in alerts:
        year_counts[alert.year] = year_counts.get(alert.year, 0) + 1
        if year_counts[alert.year] <= 3:
            filtered.append(alert)

    return filtered[:20]
