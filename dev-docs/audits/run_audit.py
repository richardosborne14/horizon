"""
Audit script for richard@digitalbricks.io — runs the projection engine
identically to the API and produces a comprehensive input/output document.
"""
import json
import os
import sys
from datetime import date
from decimal import Decimal

# Ensure backend is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))

from app.calculations.constants import INFLATION_SCALES, get_growth_rate
from app.calculations.projection import (
    ProjectionInput,
    project_timeline,
    compute_summary,
    compute_milestones,
    find_goal_year,
    find_wealth_exhaustion_age,
)
from app.calculations.insights import generate_insights
from app.calculations.readiness import compute_readiness_score

USER_ID = "67b56986-89c3-4ff5-808e-d3177507d341"
USER_EMAIL = "richard@digitalbricks.io"
USER_NAME = "Richard Osborne"
USER_BORN = date(1986, 2, 28)
TODAY = date.today()

# ── Compute current age ─────────────────────────────────────────────
current_age = TODAY.year - USER_BORN.year
if (TODAY.month, TODAY.day) < (USER_BORN.month, USER_BORN.day):
    current_age -= 1

# ── Profile data ────────────────────────────────────────────────────
profile = {
    "birth_date": "1986-02-28",
    "current_age": current_age,
    "target_retirement_age": 70,
    "tax_parts": Decimal("3.5"),
    "status": "ae",
    "ae_activity_type": "bnc_non_reglementee",
    "has_versement_liberatoire": True,
    "monthly_gross_ca": Decimal("5600.00"),
    "growth_preset": "ambitious",
    "growth_rate_custom": None,
    "cesu_annual": Decimal("1400.00"),
    "charity_annual": Decimal("240.00"),
    "caf_override_monthly": None,
    "monthly_expenses": {
        "loyer": "500", "sante": "220", "credit": "590",
        "divers": "0", "impots": "140", "energie": "145",
        "loisirs": "200", "internet": "70", "assurance": "0",
        "transport": "240", "abonnements": "100", "alimentation": "1500",
    },
    "monthly_revenue_goal": Decimal("3000.00"),
    "world_scale": "pessimistic",
    "status_change_enabled": True,
    "status_change_year": None,
    "status_change_target": "sasu",
    "status_change_savings": None,
}

# Compute monthly expenses total
monthly_expenses_total = sum(Decimal(str(v)) for v in profile["monthly_expenses"].values())

# ── Growth rate ─────────────────────────────────────────────────────
growth_rate = get_growth_rate(profile["growth_preset"], profile["growth_rate_custom"])

# ── Life entities (only active ones: is_active = true) ──────────────
life_entities_raw = [
    # Active kids
    {"entity_type": "kid", "name": "Romy", "reference_date": date(2025, 4, 3),
     "cost_events": [
         {"id":"k-creche","label":"Crèche / Garde d'enfant","amount":500,"source":"default","to_age":2,"from_age":0,"frequency":"monthly","is_active":True},
         {"id":"k-cant-mat","label":"Cantine maternelle","amount":100,"source":"default","to_age":5,"from_age":3,"frequency":"monthly","is_active":True},
         {"id":"k-cant-prim","label":"Cantine + périscolaire primaire","amount":150,"source":"default","to_age":11,"from_age":6,"frequency":"monthly","is_active":True},
         {"id":"k-fourn-prim","label":"Fournitures scolaires primaire","amount":200,"source":"default","to_age":11,"from_age":6,"frequency":"annual","is_active":True},
         {"id":"k-cant-coll","label":"Cantine collège","amount":150,"source":"default","to_age":15,"from_age":11,"frequency":"monthly","is_active":True},
         {"id":"k-fourn-coll","label":"Fournitures scolaires collège","amount":400,"source":"default","to_age":15,"from_age":11,"frequency":"annual","is_active":True},
         {"id":"k-cant-lyc","label":"Cantine lycée","amount":150,"source":"default","to_age":18,"from_age":15,"frequency":"monthly","is_active":True},
         {"id":"k-fourn-lyc","label":"Fournitures scolaires lycée","amount":600,"source":"default","to_age":18,"from_age":15,"frequency":"annual","is_active":True},
         {"id":"k-camp","label":"Camp d'été / Colonie","amount":800,"source":"default","to_age":17,"from_age":6,"frequency":"annual","is_active":True},
         {"id":"k-extra","label":"Activités extra-scolaires","amount":100,"source":"default","to_age":18,"from_age":6,"frequency":"monthly","is_active":True},
         {"id":"k-permis","label":"Permis de conduire","amount":1800,"source":"default","to_age":18,"from_age":18,"frequency":"once","is_active":True},
         {"id":"k-voiture","label":"Première voiture","amount":5000,"source":"default","to_age":18,"from_age":18,"frequency":"once","is_active":True},
         {"id":"k-etudes","label":"Études supérieures (logement, frais, vie)","amount":500,"source":"default","to_age":23,"from_age":18,"frequency":"monthly","is_active":True},
     ]},
    {"entity_type": "kid", "name": "Ellie", "reference_date": date(2021, 7, 2),
     "cost_events": [
         {"id":"k-creche","label":"Crèche / Garde d'enfant","amount":500,"source":"default","to_age":2,"from_age":0,"frequency":"monthly","is_active":True},
         {"id":"k-cant-mat","label":"Cantine maternelle","amount":100,"source":"default","to_age":5,"from_age":3,"frequency":"monthly","is_active":True},
         {"id":"k-cant-prim","label":"Cantine + périscolaire primaire","amount":150,"source":"default","to_age":11,"from_age":6,"frequency":"monthly","is_active":True},
         {"id":"k-fourn-prim","label":"Fournitures scolaires primaire","amount":200,"source":"default","to_age":11,"from_age":6,"frequency":"annual","is_active":True},
         {"id":"k-cant-coll","label":"Cantine collège","amount":150,"source":"default","to_age":15,"from_age":11,"frequency":"monthly","is_active":True},
         {"id":"k-fourn-coll","label":"Fournitures scolaires collège","amount":400,"source":"default","to_age":15,"from_age":11,"frequency":"annual","is_active":True},
         {"id":"k-cant-lyc","label":"Cantine lycée","amount":150,"source":"default","to_age":18,"from_age":15,"frequency":"monthly","is_active":True},
         {"id":"k-fourn-lyc","label":"Fournitures scolaires lycée","amount":600,"source":"default","to_age":18,"from_age":15,"frequency":"annual","is_active":True},
         {"id":"k-camp","label":"Camp d'été / Colonie","amount":800,"source":"default","to_age":17,"from_age":6,"frequency":"annual","is_active":True},
         {"id":"k-extra","label":"Activités extra-scolaires","amount":100,"source":"default","to_age":18,"from_age":6,"frequency":"monthly","is_active":True},
         {"id":"k-permis","label":"Permis de conduire","amount":1800,"source":"default","to_age":18,"from_age":18,"frequency":"once","is_active":True},
         {"id":"k-voiture","label":"Première voiture","amount":5000,"source":"default","to_age":18,"from_age":18,"frequency":"once","is_active":True},
         {"id":"k-etudes","label":"Études supérieures (logement, frais, vie)","amount":500,"source":"default","to_age":23,"from_age":18,"frequency":"monthly","is_active":True},
     ]},
    {"entity_type": "kid", "name": "Saoirse", "reference_date": date(2018, 3, 25),
     "cost_events": [
         {"id":"k-creche","label":"Crèche / Garde d'enfant","amount":500,"source":"default","to_age":2,"from_age":0,"frequency":"monthly","is_active":True},
         {"id":"k-cant-mat","label":"Cantine maternelle","amount":100,"source":"default","to_age":5,"from_age":3,"frequency":"monthly","is_active":True},
         {"id":"k-cant-prim","label":"Cantine + périscolaire primaire","amount":150,"source":"default","to_age":11,"from_age":6,"frequency":"monthly","is_active":True},
         {"id":"k-fourn-prim","label":"Fournitures scolaires primaire","amount":200,"source":"default","to_age":11,"from_age":6,"frequency":"annual","is_active":True},
         {"id":"k-cant-coll","label":"Cantine collège","amount":150,"source":"default","to_age":15,"from_age":11,"frequency":"monthly","is_active":True},
         {"id":"k-fourn-coll","label":"Fournitures scolaires collège","amount":400,"source":"default","to_age":15,"from_age":11,"frequency":"annual","is_active":True},
         {"id":"k-cant-lyc","label":"Cantine lycée","amount":150,"source":"default","to_age":18,"from_age":15,"frequency":"monthly","is_active":True},
         {"id":"k-fourn-lyc","label":"Fournitures scolaires lycée","amount":600,"source":"default","to_age":18,"from_age":15,"frequency":"annual","is_active":True},
         {"id":"k-camp","label":"Camp d'été / Colonie","amount":800,"source":"default","to_age":17,"from_age":6,"frequency":"annual","is_active":True},
         {"id":"k-extra","label":"Activités extra-scolaires","amount":100,"source":"default","to_age":18,"from_age":6,"frequency":"monthly","is_active":True},
         {"id":"k-permis","label":"Permis de conduire","amount":1800,"source":"default","to_age":18,"from_age":18,"frequency":"once","is_active":True},
         {"id":"k-voiture","label":"Première voiture","amount":5000,"source":"default","to_age":18,"from_age":18,"frequency":"once","is_active":True},
         {"id":"k-etudes","label":"Études supérieures (logement, frais, vie)","amount":500,"source":"default","to_age":23,"from_age":18,"frequency":"monthly","is_active":True},
     ]},
    # Active pet
    {"entity_type": "pet", "name": "Layla", "reference_date": date(2025, 1, 25),
     "cost_events": [
         {"id":"p-food","label":"Nourriture","amount":600,"source":"default","to_age":13,"from_age":0,"frequency":"annual","is_active":True},
         {"id":"p-vacc-primo","label":"Vaccins primo","amount":250,"source":"default","to_age":1,"from_age":0,"frequency":"once","is_active":True},
         {"id":"p-vacc-rappel","label":"Rappel vaccins","amount":80,"source":"default","to_age":13,"from_age":1,"frequency":"annual","is_active":True},
         {"id":"p-steril","label":"Stérilisation","amount":300,"source":"default","to_age":1,"from_age":0,"frequency":"once","is_active":True},
         {"id":"p-vet","label":"Vétérinaire annuel","amount":200,"source":"default","to_age":13,"from_age":1,"frequency":"annual","is_active":True},
         {"id":"p-groom","label":"Toilettage","amount":300,"source":"default","to_age":13,"from_age":0,"frequency":"annual","is_active":True},
         {"id":"p-old","label":"Soins vétérinaires renforcés (vieillesse)","amount":400,"source":"default","to_age":13,"from_age":10,"frequency":"annual","is_active":True},
     ]},
    # Active tech (Macbook Air 2021)
    {"entity_type": "tech", "name": "Macbook Air (2021)", "reference_date": date(2021, 1, 1),
     "cost_events": [
         {"id":"t-accessories","label":"Accessoires / Réparations","amount":100,"source":"default","to_age":30,"from_age":0,"frequency":"annual","is_active":True},
         {"id":"t-insurance","label":"Assurance / Garantie étendue","amount":100,"source":"default","to_age":3,"from_age":0,"frequency":"annual","is_active":True},
         {"id":"t-replace-1","label":"Remplacement laptop (tous les 3 ans)","amount":1200,"source":"default","to_age":3,"from_age":3,"frequency":"once","is_active":True},
         {"id":"t-replace-2","label":"Remplacement laptop (tous les 3 ans)","amount":1200,"source":"default","to_age":6,"from_age":6,"frequency":"once","is_active":True},
         {"id":"t-replace-3","label":"Remplacement laptop (tous les 3 ans)","amount":1200,"source":"default","to_age":9,"from_age":9,"frequency":"once","is_active":True},
         {"id":"t-replace-4","label":"Remplacement laptop (tous les 3 ans)","amount":1200,"source":"default","to_age":12,"from_age":12,"frequency":"once","is_active":True},
         {"id":"t-replace-5","label":"Remplacement laptop (tous les 3 ans)","amount":1200,"source":"default","to_age":15,"from_age":15,"frequency":"once","is_active":True},
         {"id":"t-replace-6","label":"Remplacement laptop (tous les 3 ans)","amount":1200,"source":"default","to_age":18,"from_age":18,"frequency":"once","is_active":True},
         {"id":"t-replace-7","label":"Remplacement laptop (tous les 3 ans)","amount":1200,"source":"default","to_age":21,"from_age":21,"frequency":"once","is_active":True},
         {"id":"t-replace-8","label":"Remplacement laptop (tous les 3 ans)","amount":1200,"source":"default","to_age":24,"from_age":24,"frequency":"once","is_active":True},
         {"id":"t-replace-9","label":"Remplacement laptop (tous les 3 ans)","amount":1200,"source":"default","to_age":27,"from_age":27,"frequency":"once","is_active":True},
         {"id":"t-replace-10","label":"Remplacement laptop (tous les 3 ans)","amount":1200,"source":"default","to_age":30,"from_age":30,"frequency":"once","is_active":True},
     ]},
    # Active tech (Macbook Air 2024)
    {"entity_type": "tech", "name": "Macbook Air (2024)", "reference_date": date(2024, 1, 1),
     "cost_events": [
         {"id":"t-accessories","label":"Accessoires / Réparations","amount":100,"source":"default","to_age":30,"from_age":0,"frequency":"annual","is_active":True},
         {"id":"t-insurance","label":"Assurance / Garantie étendue","amount":100,"source":"default","to_age":3,"from_age":0,"frequency":"annual","is_active":True},
         {"id":"t-replace-1","label":"Remplacement laptop (tous les 3 ans)","amount":1200,"source":"default","to_age":3,"from_age":3,"frequency":"once","is_active":True},
         {"id":"t-replace-2","label":"Remplacement laptop (tous les 3 ans)","amount":1200,"source":"default","to_age":6,"from_age":6,"frequency":"once","is_active":True},
         {"id":"t-replace-3","label":"Remplacement laptop (tous les 3 ans)","amount":1200,"source":"default","to_age":9,"from_age":9,"frequency":"once","is_active":True},
         {"id":"t-replace-4","label":"Remplacement laptop (tous les 3 ans)","amount":1200,"source":"default","to_age":12,"from_age":12,"frequency":"once","is_active":True},
         {"id":"t-replace-5","label":"Remplacement laptop (tous les 3 ans)","amount":1200,"source":"default","to_age":15,"from_age":15,"frequency":"once","is_active":True},
         {"id":"t-replace-6","label":"Remplacement laptop (tous les 3 ans)","amount":1200,"source":"default","to_age":18,"from_age":18,"frequency":"once","is_active":True},
         {"id":"t-replace-7","label":"Remplacement laptop (tous les 3 ans)","amount":1200,"source":"default","to_age":21,"from_age":21,"frequency":"once","is_active":True},
         {"id":"t-replace-8","label":"Remplacement laptop (tous les 3 ans)","amount":1200,"source":"default","to_age":24,"from_age":24,"frequency":"once","is_active":True},
         {"id":"t-replace-9","label":"Remplacement laptop (tous les 3 ans)","amount":1200,"source":"default","to_age":27,"from_age":27,"frequency":"once","is_active":True},
         {"id":"t-replace-10","label":"Remplacement laptop (tous les 3 ans)","amount":1200,"source":"default","to_age":30,"from_age":30,"frequency":"once","is_active":True},
     ]},
    # Active car (Xsara, 2010) — NOTE: age 16 at projection start. cost_events end at age 8 → ALL COST EVENTS EXPIRED.
    {"entity_type": "car", "name": "Xsara (2010)", "reference_date": date(2010, 6, 1),
     "cost_events": [
         {"id":"c-insurance","label":"Assurance auto","amount":600,"source":"default","to_age":8,"from_age":0,"frequency":"annual","is_active":True},
         {"id":"c-fuel","label":"Carburant / Énergie","amount":1200,"source":"default","to_age":8,"from_age":0,"frequency":"annual","is_active":True},
         {"id":"c-maintenance","label":"Entretien courant (révisions, pneus, freins)","amount":400,"source":"default","to_age":8,"from_age":0,"frequency":"annual","is_active":True},
         {"id":"c-ct-1","label":"Contrôle technique à 4 ans","amount":80,"source":"default","to_age":4,"from_age":4,"frequency":"once","is_active":True},
         {"id":"c-ct-2","label":"Contrôle technique à 6 ans","amount":80,"source":"default","to_age":6,"from_age":6,"frequency":"once","is_active":True},
         {"id":"c-ct-3","label":"Contrôle technique à 8 ans","amount":80,"source":"default","to_age":8,"from_age":8,"frequency":"once","is_active":True},
         {"id":"c-replace","label":"Remplacement véhicule","amount":18000,"source":"default","to_age":8,"from_age":8,"frequency":"once","is_active":True},
     ]},
    # Active car (Peugeot, 2006) — NOTE: age 19 at projection start → ALL COST EVENTS EXPIRED.
    {"entity_type": "car", "name": "Peugeot (2006)", "reference_date": date(2006, 8, 1),
     "cost_events": [
         {"id":"c-insurance","label":"Assurance auto","amount":600,"source":"default","to_age":8,"from_age":0,"frequency":"annual","is_active":True},
         {"id":"c-fuel","label":"Carburant / Énergie","amount":1200,"source":"default","to_age":8,"from_age":0,"frequency":"annual","is_active":True},
         {"id":"c-maintenance","label":"Entretien courant (révisions, pneus, freins)","amount":400,"source":"default","to_age":8,"from_age":0,"frequency":"annual","is_active":True},
         {"id":"c-ct-1","label":"Contrôle technique à 4 ans","amount":80,"source":"default","to_age":4,"from_age":4,"frequency":"once","is_active":True},
         {"id":"c-ct-2","label":"Contrôle technique à 6 ans","amount":80,"source":"default","to_age":6,"from_age":6,"frequency":"once","is_active":True},
         {"id":"c-ct-3","label":"Contrôle technique à 8 ans","amount":80,"source":"default","to_age":8,"from_age":8,"frequency":"once","is_active":True},
         {"id":"c-replace","label":"Remplacement véhicule","amount":18000,"source":"default","to_age":8,"from_age":8,"frequency":"once","is_active":True},
     ]},
]

# Process life entities: compute entity_age_at_start
life_entities_processed = []
kids_birth_dates = []
for ent in life_entities_raw:
    ref_date = ent["reference_date"]
    entity_age = TODAY.year - ref_date.year
    if (TODAY.month, TODAY.day) < (ref_date.month, ref_date.day):
        entity_age -= 1
    if entity_age < 0:
        entity_age = -1

    life_entities_processed.append({
        "entity_type": ent["entity_type"],
        "entity_name": ent["name"],
        "entity_age_at_start": entity_age,
        "cost_events": ent["cost_events"],
    })

    if ent["entity_type"] == "kid":
        kids_birth_dates.append(ref_date)

# ── Recurring expenses (none active) ────────────────────────────────
recurring_expenses = []

# ── Investment allocations ──────────────────────────────────────────
allocations = {
    "av_euro": {"balance": Decimal("250.00"), "monthly": Decimal("250.00")},
    "livret_a": {"balance": Decimal("500.00"), "monthly": Decimal("500.00")},
}

# ── Projects ────────────────────────────────────────────────────────
projects = [
    {"type": "event", "label": "Renovation grange", "event_year": 2028, "event_cost": 20000.00},
    {"type": "event", "label": "Renovation sdb extérieur", "event_year": 2030, "event_cost": 10000.00},
]

# ── Run for all three scales ────────────────────────────────────────
def _fmt(v):
    """Format a Decimal as a euro string."""
    if isinstance(v, Decimal):
        return str(v.quantize(Decimal("0.01")))
    return str(v)

def run_scale(scale_name):
    inp = ProjectionInput(
        current_age=current_age,
        target_age=profile["target_retirement_age"],
        post_retirement_years=25,
        pension_monthly=Decimal("0"),
        monthly_gross=profile["monthly_gross_ca"],
        growth_rate=growth_rate,
        ae_activity_type=profile["ae_activity_type"],
        monthly_expenses_total=monthly_expenses_total,
        scale=scale_name,
        life_entities=life_entities_processed,
        recurring_expenses=recurring_expenses,
        allocations=allocations,
        projects=projects,
        kids_birth_dates=kids_birth_dates,
        caf_override_monthly=profile["caf_override_monthly"],
        household_income_for_caf=profile["monthly_gross_ca"],
        cesu_annual=profile["cesu_annual"],
        charity_annual=profile["charity_annual"],
        status_change_enabled=profile["status_change_enabled"],
        status_change_year=profile["status_change_year"],
        status_change_savings=profile["status_change_savings"],
        monthly_revenue_goal=profile["monthly_revenue_goal"],
    )
    timeline = project_timeline(inp)
    summary = compute_summary(timeline)

    # Insights
    allocations_list = [
        {"vehicle_key": vk, "balance": float(alloc.get("balance", Decimal("0"))),
         "monthly": float(alloc.get("monthly", Decimal("0")))}
        for vk, alloc in allocations.items()
    ]
    profile_data = {
        "monthly_gross": float(inp.monthly_gross),
        "growth_rate": float(inp.growth_rate),
        "target_age": inp.target_age,
        "current_age": inp.current_age,
    }
    insights = generate_insights(timeline, summary, profile_data, allocations_list)
    readiness = compute_readiness_score(timeline, summary, profile_data, allocations_list, inp.monthly_revenue_goal)

    return {
        "scale": scale_name,
        "inflation_rate": INFLATION_SCALES[scale_name]["inflation"],
        "cost_living_rate": INFLATION_SCALES[scale_name]["cost_living"],
        "timeline": timeline,
        "summary": summary,
        "insights": insights,
        "readiness": readiness,
        "input": inp,
    }

scales = ["optimistic", "moderate", "pessimistic"]
results = {s: run_scale(s) for s in scales}

# ── Generate Markdown output ────────────────────────────────────────

out = []
out.append(f"# Horizon Audit: {USER_EMAIL}")
out.append(f"")
out.append(f"**User**: {USER_NAME} ({USER_EMAIL})  ")
out.append(f"**User ID**: `{USER_ID}`  ")
out.append(f"**Born**: {USER_BORN} (age {current_age})  ")
out.append(f"**Generated**: {TODAY}  ")
out.append(f"")
out.append("---")
out.append("")

# ────────────────────────────────────────────────────────────────────
# SECTION A: Raw Input Data
# ────────────────────────────────────────────────────────────────────
out.append("## Section A: Raw Input Data")
out.append("")

out.append("### A.1 Profile (`user_profiles`)")
out.append("")
out.append("| Field | Value |")
out.append("|-------|-------|")
out.append(f"| Birth date | {profile['birth_date']} (age {current_age}) |")
out.append(f"| Target retirement age | {profile['target_retirement_age']} |")
out.append(f"| Tax parts | {profile['tax_parts']} |")
out.append(f"| Status | {profile['status']} |")
out.append(f"| AE activity type | {profile['ae_activity_type']} |")
out.append(f"| Versement libératoire | {profile['has_versement_liberatoire']} |")
out.append(f"| Monthly gross CA | {_fmt(profile['monthly_gross_ca'])} € |")
out.append(f"| Growth preset | {profile['growth_preset']} (→ {float(growth_rate)*100:.1f}% / year) |")
out.append(f"| CESU annual | {_fmt(profile['cesu_annual'])} € |")
out.append(f"| Charity annual | {_fmt(profile['charity_annual'])} € |")
out.append(f"| CAF override | {profile['caf_override_monthly'] or 'none (auto-estimated)'} |")
out.append(f"| Monthly revenue goal | {_fmt(profile['monthly_revenue_goal'])} € |")
out.append(f"| World scale | {profile['world_scale']} |")
out.append(f"| Status change enabled | {profile['status_change_enabled']} |")
out.append(f"| Status change year | {profile['status_change_year'] or 'null (never)'} |")
out.append(f"| Status change target | {profile['status_change_target']} |")
out.append(f"| Status change savings | {profile['status_change_savings'] or 'null'} |")
out.append("")

out.append("### A.2 Monthly Expenses (JSONB)")
out.append("")
out.append("| Category | Amount (€) |")
out.append("|----------|------------|")
for cat, amt in sorted(profile["monthly_expenses"].items()):
    out.append(f"| {cat} | {amt} |")
out.append(f"| **TOTAL** | **{_fmt(monthly_expenses_total)}** |")
out.append("")

out.append("### A.3 Life Entities (`life_entities`, active only)")
out.append("")
out.append("| # | Type | Name | Reference Date | Age at projection start | # Cost Events |")
out.append("|---|------|------|----------------|------------------------|--------------|")
for i, ent in enumerate(life_entities_processed):
    out.append(f"| {i+1} | {ent['entity_type']} | {ent['entity_name']} | {ent.get('ref_date_override', 'N/A')} | {ent['entity_age_at_start']} | {len(ent['cost_events'])} |")
out.append("")

out.append("#### A.3.1 Entity Ages at Key Projection Milestones")
out.append("")
out.append("The projection Y-axis is `current_year + y` where `y` starts at 0 (2026).")
out.append("Each entity's age during a given projection year = `entity_age_at_start + y`.")
out.append("")
out.append("| Entity | Type | Age at y=0 (2026) | age at y=10 (2036) | age at y=30 (2056, retirement) | To_age max |")
out.append("|--------|------|--------------------|--------------------|-------------------------------|------------|")
for ent in life_entities_processed:
    age0 = ent["entity_age_at_start"]
    to_age_max = max((e.get("to_age", 0) for e in ent["cost_events"]), default=0)
    out.append(f"| {ent['entity_name']} | {ent['entity_type']} | {age0} | {age0+10} | {age0+30} | {to_age_max} |")
out.append("")

out.append("#### A.3.2 Cost Events Detail")
out.append("")
for ent in life_entities_processed:
    out.append(f"##### {ent['entity_type'].upper()}: {ent['entity_name']} (age_at_start={ent['entity_age_at_start']})")
    out.append("")
    out.append("| ID | Label | From Age | To Age | Amount | Frequency | Active |")
    out.append("|----|-------|----------|--------|--------|-----------|--------|")
    for evt in ent["cost_events"]:
        active = "✓" if evt.get("is_active", True) else "✗"
        out.append(f"| {evt['id']} | {evt['label']} | {evt['from_age']} | {evt['to_age']} | {evt['amount']}€ | {evt['frequency']} | {active} |")
    out.append("")

out.append("### A.4 Recurring Expenses")
out.append("")
if recurring_expenses:
    out.append("| Label | Annual Amount | From Year | To Year |")
    out.append("|-------|---------------|-----------|---------|")
    for r in recurring_expenses:
        out.append(f"| {r['label']} | {r['annual_amount']}€ | {r['from_year']} | {r['to_year']} |")
else:
    out.append("*(None — no recurring expenses configured)*")
out.append("")

out.append("### A.5 Investment Allocations")
out.append("")
out.append("| Vehicle | Existing Balance (€) | Monthly Contribution (€) |")
out.append("|---------|---------------------|---------------------------|")
for vk, alloc in sorted(allocations.items()):
    out.append(f"| {vk} | {_fmt(alloc['balance'])} | {_fmt(alloc['monthly'])} |")
out.append(f"| **TOTAL** | **{_fmt(sum(a['balance'] for a in allocations.values()))}** | **{_fmt(sum(a['monthly'] for a in allocations.values()))}** |")
out.append("")

out.append("### A.6 Projects")
out.append("")
out.append("| # | Type | Label | Year | Cost (€) |")
out.append("|---|------|-------|------|----------|")
for p in projects:
    year_key = "event_year" if p["type"] == "event" else "start_year"
    cost_key = "event_cost" if p["type"] == "event" else "purchase_cost"
    out.append(f"| | {p['type']} | {p['label']} | {p[year_key]} | {p[cost_key]} |")
out.append("")

# ────────────────────────────────────────────────────────────────────
# FORMULA REFERENCE
# ────────────────────────────────────────────────────────────────────
out.append("---")
out.append("## Section B: Formula Reference")
out.append("")
out.append("### B.1 Revenue")
out.append("")
out.append("```")
out.append("gross_annual = monthly_gross_ca × 12 × (1 + growth_rate)^y")
out.append(f"  = 5600.00 × 12 × (1 + {float(growth_rate)})^y")
out.append("charges = gross_annual × AE_rate(activity_type, year)")
out.append("  AE_rate for bnc_non_reglementee:")
out.append("    2025: 24.20%, 2026-2030: 24.60%, 2031+: 26.10%")
out.append("  With versement libératoire: add ~1.0-2.2% depending on income bracket")
out.append("cfe = get_cfe_estimate(year, inflation_rate)")
out.append("  CFE base ~250-550€, scaled by inflation")
out.append("```")
out.append("")

out.append("### B.2 Expenses")
out.append("")
out.append("```")
out.append("base_expenses = monthly_expenses_total × 12 × (1 + cost_living_rate)^y")
out.append(f"  = {_fmt(monthly_expenses_total)} × 12 × (1 + cost_living_rate)^y")
out.append("")
out.append("Life entity cost per event:")
out.append("  if entity_age_at_start + y in [from_age, to_age]:")
out.append("    amount × (1 + inflation_rate)^y  (once cost: fires only at from_age)")
out.append("    monthly costs × 12 to get annual")
out.append("")
out.append("Recurring expenses:")
out.append("  if from_year <= year <= to_year:")
out.append("    annual_amount × (1 + inflation_rate)^y")
out.append("")
out.append("Projects:")
out.append("  'event' type: event_cost in event_year only")
out.append("  'invest' type: purchase_cost in start_year, then annual_income - annual_expenses - tax")
out.append("```")
out.append("")

out.append("### B.3 CAF & Tax Credits")
out.append("")
out.append("```")
out.append("CAF: auto-estimated from number of kids under 20, reference_year, household_income")
out.append("  If caf_override_monthly is set: caf_override × 12 × 1.015^y (only while kids < 20)")
out.append("CESU credit: min(cesu_annual × (1+inflation)^y × 0.50, 6000€)")
out.append("Charity credit: min(charity_annual × (1+inflation)^y × 0.66, 20000€)")
out.append("```")
out.append("")

out.append("### B.4 Investments")
out.append("")
out.append("```")
out.append("For each vehicle vk:")
out.append("  contrib = monthly × 12")
out.append("  returns = balance × effective_rate")
out.append("  effective_rate = max(0.005, nominal_rate - inflation × 0.25)")
out.append("    Regulated vehicles (livret_a, ldds, av_euro):")
out.append("      pessimist: use nominal_rate")
out.append("      others: max(nominal_rate, inflation)")
out.append("  Tax on returns: see B.4.1 below")
out.append("  Ceilings: nominal (not inflation-adjusted)")
out.append("    livret_a: 22950€, ldds: 12000€")
out.append("  Overflow: livret_a → ldds, ldds → av_euro")
out.append("```")
out.append("")

out.append("### B.4.1 Tax by Holding Period (TASK-5.10)")
out.append("")
out.append("| Vehicle | Pre-maturity | Post-maturity | Existing balance |")
out.append("|---------|-------------|---------------|-----------------|")
out.append("| PEA | PFU 30% (< 5yr) | PS only 17.2% (≥ 5yr) | Treated as mature |")
out.append("| AV (euro/UC) | PFU 30% (< 8yr) | PS only 17.2% (≥ 8yr) | Treated as mature |")
out.append("| SCPI | PFU 30% (always) | — | PFU 30% |")
out.append("| PER | ~20% flat (exit tax) | — | ~20% |")
out.append("| Livret A / LDDS | Tax-free | — | Tax-free |")
out.append("")

out.append("### B.5 Post-Retirement (Phase 2)")
out.append("")
out.append("```")
out.append("gross = 0 (no work income)")
out.append("pension_annual = pension_monthly × 12")
out.append("charges = 0, cfe = 0, caf = 0, tax_credits = 0")
out.append("Investment returns continue (no new contributions)")
out.append("shortfall = total_outgoing - total_income")
out.append("if shortfall > 0: withdraw from savings (liquid first)")
out.append("  Priority: livret_a → ldds → av_euro → av_uc → pea → scpi → per")
out.append("```")
out.append("")

out.append("### B.6 Derived Fields")
out.append("")
out.append("```")
out.append("net_annual = total_income - total_outgoing + status_bonus")
out.append("total_wealth = sum(all vehicle balances)")
out.append("passive_monthly = total_wealth × 4% / 12")
out.append("total_monthly_income = (gross + project_income + caf + pension) / 12 + passive")
out.append("retirement_monthly_income = passive + (project_income + pension) / 12")
out.append("goal_reached = retirement_monthly_income >= monthly_revenue_goal")
out.append("```")
out.append("")

# ────────────────────────────────────────────────────────────────────
# SECTION C: Projection Output
# ────────────────────────────────────────────────────────────────────
out.append("---")
out.append("## Section C: Projection Results")
out.append("")

# Fix entity names with ref_date for table
for i, ent in enumerate(life_entities_processed):
    # Find raw entity
    for raw in life_entities_raw:
        if raw["name"] == ent["entity_name"] and raw["entity_type"] == ent["entity_type"]:
            ent["ref_date_override"] = str(raw["reference_date"])
            break

for scale_name in scales:
    r = results[scale_name]
    tl = r["timeline"]
    summary = r["summary"]
    insights = r["insights"]
    readiness = r["readiness"]

    out.append(f"### C.{scales.index(scale_name)+1} Scale: **{scale_name}**")
    out.append("")
    out.append(f"- **Inflation rate**: {float(r['inflation_rate'])*100:.1f}% / year")
    out.append(f"- **Cost of living rate**: {float(r['cost_living_rate'])*100:.1f}% / year")
    out.append(f"- **Years projected**: {len(tl)}")
    out.append(f"- **Projection range**: {tl[0].year} (age {tl[0].age}) → {tl[-1].year} (age {tl[-1].age})")
    out.append("")

    out.append("#### Timeline (Year-by-Year)")
    out.append("")
    out.append("| Year | Age | Phase | Gross Annual | Charges | CFE | Base Exp | Kid Exp | Pet Exp | Car Exp | Tech Exp | Rec Exp | Proj Exp | Proj Inc | CAF | Tax Credits | Status Bonus | Pension | Total Income | Total Outgoing | Net Annual | Year Invested | Year Returns | Total Wealth | Passive/mo | Goal? |")
    out.append("|------|-----|-------|-------------|---------|-----|----------|---------|---------|---------|----------|---------|----------|----------|-----|-------------|-------------|---------|-------------|----------------|------------|--------------|-------------|-------------|-----------|-------|")
    for t in tl:
        phase = "RET" if t.is_retirement else "ACC"
        goal = "✓" if t.goal_reached else ""
        out.append(
            f"| {t.year} | {t.age} | {phase} | {_fmt(t.gross_annual)} | {_fmt(t.charges)} | {_fmt(t.cfe)} | "
            f"{_fmt(t.base_expenses)} | {_fmt(t.kid_expenses)} | {_fmt(t.pet_expenses)} | "
            f"{_fmt(t.car_expenses)} | {_fmt(t.tech_expenses)} | {_fmt(t.recurring_expenses)} | "
            f"{_fmt(t.project_expenses)} | {_fmt(t.project_income)} | {_fmt(t.caf_annual)} | "
            f"{_fmt(t.tax_credits)} | {_fmt(t.status_bonus)} | {_fmt(t.pension_annual)} | "
            f"{_fmt(t.total_income)} | {_fmt(t.total_outgoing)} | {_fmt(t.net_annual)} | "
            f"{_fmt(t.year_invested)} | {_fmt(t.year_returns)} | {_fmt(t.total_wealth)} | "
            f"{_fmt(t.passive_monthly)} | {goal} |"
        )
    out.append("")

    out.append("#### Summary Statistics")
    out.append("")
    out.append("| Statistic | Value |")
    out.append("|-----------|-------|")
    out.append(f"| Total years | {summary['years']} |")
    out.append(f"| Final wealth | {summary['final_wealth']} € |")
    out.append(f"| Final passive/month | {summary['final_passive_monthly']} € |")
    out.append(f"| Total invested | {summary['total_invested']} € |")
    out.append(f"| Total returns | {summary['total_returns']} € |")
    goal_y = summary.get("goal_year")
    goal_str = f"{goal_y['year']} (age {goal_y['age']})" if goal_y else "NO"
    out.append(f"| Goal reached? | {goal_str} |")
    out.append(f"| Wealth exhaustion age | {summary.get('wealth_exhaustion_age') or 'NEVER'} |")
    out.append(f"| Retirement monthly income | {summary['retirement_monthly_income']} € |")
    out.append(f"| Retirement monthly gap | {summary['retirement_monthly_gap']} € |")
    out.append("")

    miles = summary.get("milestones", [])
    if miles:
        out.append("#### Wealth Milestones")
        out.append("")
        out.append("| Threshold | Year | Age |")
        out.append("|-----------|------|-----|")
        for m in miles:
            out.append(f"| {m['label']} | {m['year']} | {m['age']} |")
        out.append("")

    out.append("#### Insights & Recommendations")
    out.append("")
    if insights:
        out.append("| # | ID | Category | Severity | Title | Impact (€) | Action |")
        out.append("|---|----|----------|----------|-------|------------|--------|")
        for ins in insights:
            out.append(
                f"| {ins.priority} | {ins.id} | {ins.category} | {ins.severity} | "
                f"{ins.title} | {_fmt(ins.impact_wealth)} | {ins.action} |"
            )
        out.append("")
        for ins in insights:
            out.append(f"**Insight #{ins.priority}: {ins.title}** ({ins.severity})")
            out.append(f"- **Rule**: `{ins.id}`")
            out.append(f"- **Description**: {ins.description}")
            out.append(f"- **Impact on wealth**: {_fmt(ins.impact_wealth)} €")
            out.append(f"- **Action**: {ins.action}")
            out.append("")
    else:
        out.append("*(No insights generated)*")
        out.append("")

    out.append("#### Readiness Score")
    out.append("")
    out.append(f"- **Score**: {readiness.score}/100")
    out.append(f"- **Band**: {readiness.label} ({readiness.color})")
    out.append(f"- **Summary**: {readiness.summary}")
    out.append("")
    out.append("| Component | Score | Weight |")
    out.append("|-----------|-------|--------|")
    weights = {"goal_coverage": 30, "wealth_durability": 25, "savings_rate": 15,
               "diversification": 10, "growth_trajectory": 10, "buffer_adequacy": 10}
    for comp, score in readiness.components.items():
        w = weights.get(comp, 0)
        out.append(f"| {comp} | {score} | {w}% |")
    out.append("")

    out.append("---")
    out.append("")

# ────────────────────────────────────────────────────────────────────
# SECTION D: Cross-Scale Comparison
# ────────────────────────────────────────────────────────────────────
out.append("## Section D: Cross-Scale Comparison")
out.append("")
out.append("| Metric | Optimistic | Moderate | Pessimistic |")
out.append("|--------|-----------|----------|-------------|")
metrics = ["final_wealth", "final_passive_monthly", "total_invested", "total_returns",
           "retirement_monthly_income", "retirement_monthly_gap"]
metric_labels = {
    "final_wealth": "Final Wealth (€)",
    "final_passive_monthly": "Final Passive/mo (€)",
    "total_invested": "Total Invested (€)",
    "total_returns": "Total Returns (€)",
    "retirement_monthly_income": "Ret. Monthly Income (€)",
    "retirement_monthly_gap": "Ret. Monthly Gap (€)",
}
for m in metrics:
    vals = [results[s]["summary"][m] for s in scales]
    out.append(f"| {metric_labels[m]} | {vals[0]} | {vals[1]} | {vals[2]} |")

out.append("| | | | |")
out.append("| Goal reached? | "
    f"{results['optimistic']['summary'].get('goal_year', {}).get('year', 'NO') if results['optimistic']['summary'].get('goal_year') else 'NO'} | "
    f"{results['moderate']['summary'].get('goal_year', {}).get('year', 'NO') if results['moderate']['summary'].get('goal_year') else 'NO'} | "
    f"{results['pessimistic']['summary'].get('goal_year', {}).get('year', 'NO') if results['pessimistic']['summary'].get('goal_year') else 'NO'} |")
out.append(f"| Wealth exhaustion? | "
    f"{results['optimistic']['summary'].get('wealth_exhaustion_age') or 'NEVER'} | "
    f"{results['moderate']['summary'].get('wealth_exhaustion_age') or 'NEVER'} | "
    f"{results['pessimistic']['summary'].get('wealth_exhaustion_age') or 'NEVER'} |")
out.append(f"| Readiness Score | "
    f"{results['optimistic']['readiness'].score} ({results['optimistic']['readiness'].label}) | "
    f"{results['moderate']['readiness'].score} ({results['moderate']['readiness'].label}) | "
    f"{results['pessimistic']['readiness'].score} ({results['pessimistic']['readiness'].label}) |")
out.append("")

# ────────────────────────────────────────────────────────────────────
# SECTION E: Key Findings & "Vie" Tab Audit
# ────────────────────────────────────────────────────────────────────
out.append("## Section E: 'Vie' Tab Audit — What's Included and What's Not")
out.append("")

out.append("### E.1 Kids (3 active)")
out.append("")
for ent in life_entities_processed:
    if ent["entity_type"] == "kid":
        age0 = ent["entity_age_at_start"]
        to_age_max = max((e.get("to_age", 0) for e in ent["cost_events"]), default=0)
        retirement_y = profile["target_retirement_age"] - current_age
        last_proj_age = age0 + retirement_y
        active_in_proj = "YES" if age0 + 30 <= to_age_max else f"Partially (last cost event ends at entity age {to_age_max})"
        if age0 > to_age_max:
            active_in_proj = "NO — all cost events expired before projection start"
        out.append(f"- **{ent['entity_name']}** (born {ent.get('ref_date_override', '?')}): "
                   f"Entity age {age0} at start, "
                   f"retires at entity age {last_proj_age if last_proj_age <= 50 else '50+'}."
                   f" All cost events from age 0-23. {active_in_proj}")

out.append("")
out.append("### E.2 Cars (2 active — BOTH EXPIRED)")
out.append("")
out.append("⚠️ **CRITICAL FINDING**: Both cars have cost events capped at `to_age: 8`.")
out.append("The Xsara (acquired 2010) is age 16 at projection start. ")
out.append("The Peugeot (acquired 2006) is age 19 at projection start. ")
out.append("**Zero car expenses appear in ANY projection year.**")
out.append("No replacement cycle is triggered because the existing cars already exceeded their replace cycle.")
out.append("The `replace_cost` metadata (18000€) is NEVER used — it's metadata only, the engine uses `cost_events`.")
out.append("")
for ent in life_entities_processed:
    if ent["entity_type"] == "car":
        age0 = ent["entity_age_at_start"]
        out.append(f"- **{ent['entity_name']}**: age {age0} at start, all cost events end at age 8 → **$0 contribution**")
out.append("")

out.append("### E.3 Tech (2 active)")
out.append("")
for ent in life_entities_processed:
    if ent["entity_type"] == "tech":
        age0 = ent["entity_age_at_start"]
        out.append(f"- **{ent['entity_name']}**: age {age0} at start. Annual accessories + replacements every 3 years up to entity age 30. Active throughout projection.")
out.append("")

out.append("### E.4 Pet (1 active)")
out.append("")
for ent in life_entities_processed:
    if ent["entity_type"] == "pet":
        age0 = ent["entity_age_at_start"]
        out.append(f"- **{ent['entity_name']}**: age {age0} at start. Cost events up to age 13. Active until entity age 13 (projection year ~{13-age0} from now).")
out.append("")

out.append("### E.5 Recurring Expenses")
out.append("")
out.append("**None configured.** No Vie-tab recurring expenses (loans, subscriptions, etc.) appear in any projection.")
out.append("")

out.append("---")
out.append("")

# ── Write output ────────────────────────────────────────────────────
output_path = os.path.join(os.path.dirname(__file__), "richard_digitalbricks_audit.md")
with open(output_path, "w") as f:
    f.write("\n".join(out))

print(f"✅ Audit written to: {output_path}")
print(f"   Scales: {scales}")
print(f"   User age: {current_age}, target age: {profile['target_retirement_age']}")
print(f"   Growth rate: {float(growth_rate)*100:.1f}%")
print(f"   Monthly expenses: {_fmt(monthly_expenses_total)}")
print(f"   Life entities: {len(life_entities_processed)} active")
print(f"   Recurring expenses: {len(recurring_expenses)}")
print(f"   Allocations: {len(allocations)} vehicles")
print(f"   Projects: {len(projects)}")
for s in scales:
    r = results[s]
    print(f"   [{s}] timeline years: {len(r['timeline'])}, "
          f"final wealth: {r['summary']['final_wealth']}, "
          f"goal: {r['summary'].get('goal_year')}, "
          f"exhaustion: {r['summary'].get('wealth_exhaustion_age')}, "
          f"readiness: {r['readiness'].score}/100 ({r['readiness'].label}), "
          f"insights: {len(r['insights'])}")