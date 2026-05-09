"""
Seed script: populates expense_categories, admin_config, and smoketest
fixture data for the dev smoke-test user (smoketest@comcoi.fr).

Uses upsert / idempotent logic — safe to run multiple times.

Usage (from project root):
    docker compose exec backend python scripts/seed.py

Or locally (with backend dependencies installed):
    cd backend && python scripts/seed.py
"""

import asyncio
import json
import sys
from decimal import Decimal
from pathlib import Path

# Ensure backend package is importable when run directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.database import AsyncSessionLocal
from app.models.financial import ExpenseCategory, MonthlyReport, Expense, MonthlySalary
from app.models.admin import AdminConfig
from app.models.salon import Salon, Employee, SalonConfig
from app.models.user import User


# ── Expense Categories ────────────────────────────────────────────────────────

async def seed_expense_categories(session) -> int:
    """
    Seed expense categories from static-data/expense-categories.json.

    Uses INSERT ... ON CONFLICT (i18n_key) DO UPDATE so existing rows
    are updated if the seed data changes.

    Returns the count of rows upserted.
    """
    data_file = Path(__file__).parent.parent / "static-data" / "expense-categories.json"
    categories = json.loads(data_file.read_text(encoding="utf-8"))

    for cat in categories:
        # Helper: parse nullable decimal from seed JSON
        def _d(v):
            return Decimal(str(v)) if v is not None else None

        stmt = pg_insert(ExpenseCategory).values(
            name=cat["name"],
            i18n_key=cat["i18n_key"],
            percent_ca_repere=_d(cat.get("percent_ca_repere")),
            percent_ca_ideal=_d(cat.get("percent_ca_ideal")),
            # Task 2.8.7: dual-threshold columns from Eric's 2026 benchmark grid
            percent_ca_seuil_alerte=_d(cat.get("percent_ca_seuil_alerte")),
            percent_ca_min=_d(cat.get("percent_ca_min")),
            description=cat["description"],
            sort_order=cat["sort_order"],
            is_system=True,
        ).on_conflict_do_update(
            # Conflict on i18n_key (which must be unique — enforced logically)
            index_elements=["i18n_key"],
            set_={
                "name": cat["name"],
                "percent_ca_repere": _d(cat.get("percent_ca_repere")),
                "percent_ca_ideal": _d(cat.get("percent_ca_ideal")),
                "percent_ca_seuil_alerte": _d(cat.get("percent_ca_seuil_alerte")),
                "percent_ca_min": _d(cat.get("percent_ca_min")),
                "description": cat["description"],
                "sort_order": cat["sort_order"],
            },
        )
        await session.execute(stmt)

    return len(categories)


# ── Admin Config ──────────────────────────────────────────────────────────────

# Initial admin config entries
ADMIN_CONFIG_ENTRIES = [
    {
        "key": "tva_rate",
        "value": {"rate": "0.20", "label": "TVA 20%"},
        "description": "Taux TVA applicable (20% standard)",
    },
    {
        "key": "payslip_unit_price_cents",
        "value": {"price_cents": 2880, "label": "28,80 € TTC"},
        "description": "Prix unitaire d'une fiche de paie (en centimes)",
    },
    {
        "key": "auto_entrepreneur_thresholds",
        "value": {
            "services": 77700,
            "commerce": 188700,
            "description": "Seuils CA annuel 2024 auto-entrepreneur"
        },
        "description": "Seuils de chiffre d'affaires pour auto-entrepreneur",
    },
    {
        "key": "cotisations_auto_entrepreneur",
        "value": {
            "services_bic": "0.221",
            "services_bnc": "0.227",
            "commerce": "0.128",
            "liberal_cipav": "0.222",
            "description": "Taux cotisations auto-entrepreneur 2024"
        },
        "description": "Taux de cotisations sociales pour auto-entrepreneurs",
    },
    {
        "key": "prime_config_defaults",
        "value": {
            "tiers": [
                {"threshold": 600, "percent": "0.10"},
                {"threshold": 900, "percent": "0.12"},
                {"threshold": 1200, "percent": "0.14"},
                {"threshold": 1500, "percent": "0.16"},
                {"threshold": 1800, "percent": "0.18"},
                {"threshold": 2100, "percent": "0.20"},
                {"threshold": 2400, "percent": "0.22"},
                {"threshold": 2700, "percent": "0.24"},
                {"threshold": 3000, "percent": "0.28"},
            ],
            "description": "Paliers de primes par défaut (grille Eric)"
        },
        "description": "Configuration des paliers de primes employés par défaut",
    },
    # ── TASK-2.12.1: Savings Engine admin config ──────────────────────────────
    {
        "key": "COMCOI_PAYSLIP_UNIT_PRICE_HT_EUR",
        "value": 24,
        "description": "Prix unitaire fiche de paie ComCoi HT (€). Défaut: 24 €",
    },
    {
        "key": "COMCOI_PAYSLIP_DOSSIER_SETUP_HT_EUR",
        "value": 85,
        "description": "Frais de dossier d'ouverture ComCoi HT (€). Défaut: 85 €",
    },
    {
        "key": "COMCOI_CONTRAT_TRAVAIL_HT_EUR",
        "value": 50,
        "description": "Tarif contrat de travail ComCoi HT (€). Défaut: 50 €",
    },
    {
        "key": "COMCOI_SITE_WEB_HT_EUR",
        "value": 250,
        "description": "Tarif site web vitrine ComCoi HT (€). Défaut: 250 €",
    },
    {
        "key": "PRODUCTS_SAVINGS_MIN_SPEND_EUR",
        "value": 3000,
        "description": "Dépenses produits minimales (€/an) pour afficher les économies achats. Défaut: 3000 €",
    },
    {
        "key": "PRODUCTS_DEFAULT_DISCOUNT_PCT",
        "value": 0.10,
        "description": "Remise produits négociée par défaut (fraction, ex: 0.10 = 10%). Défaut: 10%",
    },
    {
        "key": "PRODUCTS_DISCOUNT_PCT_BY_BRAND",
        "value": {},
        "description": "Remises produits par marque (JSONB: {brand_key: discount_pct}). Ex: {\"loreal\": 0.12}",
    },
]


async def seed_admin_config(session) -> int:
    """
    Seed admin_config table with initial rate tables and configuration.

    Uses INSERT ... ON CONFLICT (key) DO NOTHING so manual edits in production
    are never overwritten by re-running the seed.
    """
    for entry in ADMIN_CONFIG_ENTRIES:
        stmt = pg_insert(AdminConfig).values(
            key=entry["key"],
            value=entry["value"],
            description=entry["description"],
        ).on_conflict_do_nothing(index_elements=["key"])
        await session.execute(stmt)

    return len(ADMIN_CONFIG_ENTRIES)


# ── Smoketest Fixture Data ────────────────────────────────────────────────────

# Social charge rates used for fixture salary rows (from 06-social-charges-reference.md)
# Salarié RGDU: 17.47% (employer charges on gross)
SALARIE_RGDU_RATE = Decimal("0.1747")
# Salarié approximate net: gross × (1 − 22% cotisations salariales)
SALARIE_NET_APPROX_RATE = Decimal("0.78")
# Dirigeant TNS: 45% on net remuneration
TNS_RATE = Decimal("0.45")


async def seed_smoketest_fixtures(session) -> dict:
    """
    Seed a complete set of test fixtures for the smoketest user.

    Creates:
      - Salon "Salon Estelle" (EURL, Paris)
      - SalonConfig with Eric defaults (type_exploitant=tns)
      - 2 employees: Estelle (dirigeant) + Julie (salarie)
      - Monthly report for April 2026 with CA 12 500 €
      - 4 expense rows across different categories
      - 2 salary rows for the employees
      - remboursement_emprunt = 450 €

    Idempotent: skips creation if "Salon Estelle" already exists for this user.

    Returns dict summarising what was created / already existed.
    """
    SMOKETEST_EMAIL = "smoketest@comcoi.fr"

    # ── 1. Find the smoketest user ─────────────────────────────────────────────
    result = await session.execute(
        select(User).where(User.email == SMOKETEST_EMAIL)
    )
    user = result.scalar_one_or_none()
    if not user:
        print(f"  ⚠️  User {SMOKETEST_EMAIL!r} not found — skipping fixture data.")
        print("     Run the app first to register the user, then re-run seed.py.")
        return {"skipped": True}

    # WHY: Mark onboarding complete so the smoke test user lands on the dashboard
    # instead of the onboarding wizard after login. Without this, every fresh seed
    # requires manually completing onboarding before testing anything else.
    if not user.onboarding_completed:
        user.onboarding_completed = True

    # WHY: Promote to admin so the subscription gate (TASK-2.19.3) lets the
    # smoke test user access all CCPilot routes without needing a Stripe trial.
    if user.role != "admin":
        user.role = "admin"

    await session.flush()

    # ── 2. Idempotency check — skip if salon already exists ───────────────────
    existing = await session.execute(
        select(Salon).where(
            Salon.user_id == user.id,
            Salon.name == "Salon Estelle",
            Salon.deleted_at.is_(None),
        )
    )
    salon = existing.scalar_one_or_none()
    if salon:
        print(f"  ℹ️  Salon Estelle already exists (id={salon.id}) — skipping fixture data.")
        return {"skipped": True, "salon_id": str(salon.id)}

    # ── 3. Create Salon ────────────────────────────────────────────────────────
    # WHY: Use auto_micro so the AE URSSAF panel appears in the wizard by default.
    # Previously 'eurl' meant the smoke test user could never test AE features
    # without a manual DB UPDATE after every seed run.
    salon = Salon(
        user_id=user.id,
        name="Salon Estelle",
        business_type="auto_micro",
        ville="Paris",
        code_postal="75011",
        nb_employees=1,  # AE solo — no salaried staff, just Julie as prestataire
    )
    session.add(salon)
    await session.flush()  # get salon.id before FK references
    print(f"  ✅ Salon created: {salon.name} (id={salon.id})")

    # ── 4. Create SalonConfig (Eric defaults + ae_activity_type) ─────────────
    # WHY: ae_activity_type = 'bic_services' is correct for coiffure (services BIC).
    # This drives the 22.1% URSSAF rate in the AE calculation path.
    config = SalonConfig(
        salon_id=salon.id,
        jours_ouverture_semaine=Decimal("5"),
        semaines_ouverture_an=Decimal("45.6"),
        heures_ouverture_jour=Decimal("10"),
        majoration_securite_benefice=Decimal("0.10"),
        taux_produits=Decimal("0.10"),
        taux_charges_fixes=Decimal("0.25"),
        percent_clients_f=Decimal("0.80"),
        montant_moyen_f=Decimal("65"),
        percent_clients_h=Decimal("0.20"),
        montant_moyen_h=Decimal("30"),
        nb_visites_moyen_f=Decimal("4.2"),
        nb_visites_moyen_h=Decimal("6.6"),
        type_exploitant="ae",
        ae_activity_type="bic_services",
        has_acre=False,
        effectif_entreprise=1,
    )
    session.add(config)
    await session.flush()
    print(f"  ✅ SalonConfig created (type_exploitant=ae, ae_activity_type=bic_services)")

    # ── 5. Create Employees ────────────────────────────────────────────────────
    # WHY: AE users do not pay themselves a salary — their income is what's left
    # after URSSAF + expenses. No dirigeant employee row needed or appropriate.
    # Julie is kept as a prestataire to show the team step is usable for AE.

    # Julie Martin — prestataire (AE hires freelancers, not CDI staff typically)
    emp_salarie = Employee(
        salon_id=salon.id,
        name="Julie Martin",
        role_type="salarie",
        contract_type="cdi",
        hours_per_week=Decimal("35"),
        weeks_per_year=Decimal("45.6"),
        salary_brut=Decimal("1800.00"),
        cotisations_patronales=(Decimal("1800.00") * SALARIE_RGDU_RATE).quantize(Decimal("0.01")),  # 314.46
        taux_occupation=Decimal("0.65"),
        is_active=True,
    )
    session.add(emp_salarie)
    await session.flush()
    print(f"  ✅ Employee created: {emp_salarie.name} (prestataire)")

    # ── 6. Create Monthly Report — April 2026 ─────────────────────────────────
    report = MonthlyReport(
        salon_id=salon.id,
        year=2026,
        month=4,
        ca_realise_ttc=Decimal("12500.00"),
        subventions=Decimal("0.00"),
        remboursement_emprunt=Decimal("450.00"),
    )
    session.add(report)
    await session.flush()
    print(f"  ✅ Monthly report created: April 2026 (CA={report.ca_realise_ttc} €)")

    # ── 7. Get category IDs by i18n_key ───────────────────────────────────────
    # We need real UUIDs from the DB — must query after seed_expense_categories ran
    cat_keys = [
        "expenses.achats_marchandises",
        "expenses.loyer_immobilier",
        "expenses.energie_fluides",
        "expenses.frais_generaux",
    ]
    cat_map: dict[str, object] = {}
    for key in cat_keys:
        result = await session.execute(
            select(ExpenseCategory).where(ExpenseCategory.i18n_key == key)
        )
        cat = result.scalar_one_or_none()
        if cat:
            cat_map[key] = cat.id
        else:
            print(f"  ⚠️  Category {key!r} not found — run seed_expense_categories first")

    # ── 8. Create Expenses ─────────────────────────────────────────────────────
    # 4 expense rows covering different grille de gestion categories
    expense_data = [
        ("expenses.achats_marchandises", Decimal("850.00"), "Produits techniques et bacs avril"),
        ("expenses.loyer_immobilier",    Decimal("1200.00"), "Loyer local commercial"),
        ("expenses.energie_fluides",     Decimal("180.00"),  "EDF + eau"),
        ("expenses.frais_generaux",      Decimal("320.00"),  "Comptable + assurances"),
    ]
    for i18n_key, amount_ttc, notes in expense_data:
        if i18n_key not in cat_map:
            continue
        amount_ht = (amount_ttc / Decimal("1.2")).quantize(Decimal("0.01"))
        tva_amount = (amount_ttc - amount_ht).quantize(Decimal("0.01"))
        expense = Expense(
            monthly_report_id=report.id,
            category_id=cat_map[i18n_key],
            amount_ttc=amount_ttc,
            amount_ht=amount_ht,
            tva_amount=tva_amount,
            notes=notes,
        )
        session.add(expense)

    await session.flush()
    print(f"  ✅ Expenses created: {len(expense_data)} rows")

    # ── 9. Create Monthly Salaries ─────────────────────────────────────────────
    # WHY: No dirigeant salary row for AE — their income is revenue minus costs.
    # Julie — prestataire: cost = invoice amount (no employer charges on top)
    sal_salarie_brut = Decimal("1800.00")
    sal_salarie_cot = (sal_salarie_brut * SALARIE_RGDU_RATE).quantize(Decimal("0.01"))
    sal_salarie = MonthlySalary(
        monthly_report_id=report.id,
        employee_id=emp_salarie.id,
        salaire_brut=sal_salarie_brut,
        cotisations_sociales=sal_salarie_cot,
        total_charge=(sal_salarie_brut + sal_salarie_cot).quantize(Decimal("0.01")),
        salaire_net_approx=(sal_salarie_brut * SALARIE_NET_APPROX_RATE).quantize(Decimal("0.01")),
        charges_overridden=False,
    )
    session.add(sal_salarie)
    await session.flush()
    print(f"  ✅ Salary created: Julie ({sal_salarie.total_charge} €)")

    return {
        "created": True,
        "salon_id": str(salon.id),
        "employees": [str(emp_salarie.id)],
        "monthly_report_id": str(report.id),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    """Run all seed operations within a single transaction."""
    print("🌱 Starting seed...")

    async with AsyncSessionLocal() as session:
        try:
            n_cats = await seed_expense_categories(session)
            print(f"  ✅ Expense categories: {n_cats} upserted")

            n_config = await seed_admin_config(session)
            print(f"  ✅ Admin config: {n_config} entries seeded")

            result = await seed_smoketest_fixtures(session)
            if result.get("created"):
                print(f"  ✅ Smoketest fixtures: Salon Estelle (auto_micro) + 1 prestataire + April 2026 report created")
            elif result.get("skipped") and not result.get("salon_id"):
                print(f"  ⚠️  Smoketest fixtures: smoketest user not found — skipped")
            else:
                print(f"  ℹ️  Smoketest fixtures: already exist — skipped")

            await session.commit()
            print("✅ Seed complete.")
        except Exception as e:
            await session.rollback()
            print(f"❌ Seed failed: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
