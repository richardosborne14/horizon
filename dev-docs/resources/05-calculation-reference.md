# Communauté Coiffure — Calculation Reference

> **Purpose**: This document describes every calculation used in Eric's Excel methodology. It is the single source of truth for implementing these formulas in the new SvelteKit/FastAPI application. All variable names use the original French labels from the spreadsheets.

---

## Table of Contents

1. [Cost-Per-Minute Pricing (Coût Minute)](#1-cost-per-minute-pricing)
2. [Salary Break-Even (Seuil de Rentabilité Salaire)](#2-salary-break-even)
3. [Tiered Commission / Bonus (Calcul des Primes)](#3-tiered-commission--bonus)
4. [Product Resale Pricing (Prix Revente)](#4-product-resale-pricing)
5. [Management Grid / Expense Benchmarks (Grille de Gestion)](#5-management-grid--expense-benchmarks)
6. [Profitability Dashboard (Rentabilité / Points Morts)](#6-profitability-dashboard)
7. [Client Volume Model (Nb de Clients)](#7-client-volume-model)
8. [Pricing Strategy Simulator (Baisse des Prix)](#8-pricing-strategy-simulator)
9. [Salary Variables Form (Variables Salaire — PDF)](#9-salary-variables-form)
10. [Employee Register (Registre Entrée-Sortie)](#10-employee-register)

---

## 1. Cost-Per-Minute Pricing

**Source**: `V1_calcul_du_cou_t_minute_.xlsx` → Sheet "Feuil1"

This is Eric's core methodology for setting service prices. It calculates how much each minute of salon operation costs, then uses that to price every service.

### Inputs (user-provided, yellow cells)

| Variable | Description | Example |
|---|---|---|
| `cout_total_fonctionnement` | Total annual salon operating cost (all expenses) | 240 000 € |
| `nb_jours_ouverture_an` | Days open per year | 260 |
| `nb_heures_ouverture_jour` | Hours open per day | 10 |

Per collaborator (up to N employees + the owner):

| Variable | Description | Example |
|---|---|---|
| `nom` | Employee name | "Jackie" |
| `nb_heures_contractuelles_semaine` | Weekly contracted hours | 35 |
| `nb_semaines_an` | Working weeks per year | 45.6 |
| `taux_occupation_reel` | Actual productivity rate (% of time spent on billable work) | 65% |

For the owner/dirigeant, different values apply (e.g. 45 h/week, 48 weeks, 70% occupancy).

### Calculations

```
# Per collaborator
nb_heures_an = nb_heures_contractuelles_semaine × nb_semaines_an
nb_minutes_an = nb_heures_an × 60
temps_travail_reel_mn = nb_minutes_an × taux_occupation_reel

# Aggregate across all collaborators
total_minutes_productives = SUM(temps_travail_reel_mn for each collaborator)

# Average occupancy rate (weighted)
taux_moyen_occupation = AVERAGE(taux_occupation_reel for each collaborator)

# Core cost-per-minute
cout_reel_minute = cout_total_fonctionnement / total_minutes_productives

# Add safety & profit margin
majoration_securite_benefice = 10%  (configurable)
cout_total_minute = cout_reel_minute × (1 + majoration_securite_benefice)
```

### Service Pricing

Each service has:
- `temps_execution` — execution time in minutes
- `temps_additionnel` — additional/setup time in minutes (applies to forfaits/packages only)

```
# Break-even price for a service
seuil_rentabilite = cout_reel_minute × (temps_execution + temps_additionnel)

# Selling price (with margin)
prix_vente_ttc = cout_total_minute × (temps_execution + temps_additionnel)
```

### Example Outputs (from spreadsheet)

| Service | Temps exec. | Temps add. | Seuil rentabilité | Prix vente TTC |
|---|---|---|---|---|
| Forfait coupe femme | 35 min | 10 min | 53.77 € | 59.15 € |
| Forfait coupe couleur femme | 65 min | 10 min | 89.62 € | 98.58 € |
| Forfait Homme | 25 min | 10 min | 41.82 € | 46.01 € |
| Soin (à la carte) | 10 min | — | 11.95 € | 13.14 € |
| Coloration (à la carte) | 30 min | — | 35.85 € | 39.43 € |

**Key insight**: Forfaits include `temps_additionnel` (10 min default for setup/shampoo/etc.), à-la-carte services do not.

---

## 2. Salary Break-Even

**Source**: `Classeur1_version_1.xlsx` → Sheet "seuil renta salaire"

Determines how much revenue (TTC) one employee must generate to cover their cost.

### Inputs

| Variable | Description | Example |
|---|---|---|
| `nom_salarie` | Employee name | "JULIE" |
| `nb_heures_semaine` | Contracted weekly hours | 35 |
| `salaire_brut` | Gross monthly salary | 2 200 € |
| `cotisations_patronales` | Employer social charges/month | 100 € |
| `pct_produits` | Product cost as % of revenue | 10% |
| `pct_charges_fixes` | Fixed charges as % of revenue | 25% |
| `pct_securite` | Safety margin % | 5% |
| `pct_benefice` | Profit margin % | 10% |
| `nb_jours_semaine` | Working days per week | 5 |
| `nb_semaines_an` | Working weeks per year | 45.6 |

### Calculations

```
# Monthly hours → for reference
heures_mois = nb_heures_semaine × 52 / 12   # e.g. 151.67

# Total employer cost
cout_total_mois = salaire_brut + cotisations_patronales   # 2 300 €
cout_total_annuel = cout_total_mois × 12                  # 27 600 €

# Available margin after products & fixed charges
marge_disponible = 1 - pct_produits - pct_charges_fixes   # 65%

# Annual break-even (how much CA TTC the employee must bring in)
seuil_rentabilite_annuel_ht = cout_total_annuel / marge_disponible      # 42 462 € HT
seuil_rentabilite_annuel_ttc = seuil_rentabilite_annuel_ht × 1.20       # 50 954 € TTC

# Add safety + profit margins
pct_supplement = pct_securite + pct_benefice   # 15%
objectif_minimum_ht = seuil_rentabilite_annuel_ht × (1 + pct_supplement)   # 48 831 € HT
objectif_minimum_ttc = objectif_minimum_ht × 1.20                          # 58 597 € TTC

# Gross profit
benefice_brut_ht = objectif_minimum_ht - seuil_rentabilite_annuel_ht      # 6 369 €

# Daily objective
nb_jours_travail_an = nb_jours_semaine × nb_semaines_an   # 228
objectif_jour_ttc = objectif_minimum_ttc / nb_jours_travail_an   # 257.00 €

# Monthly objective (full-time)
nb_jours_mois = nb_jours_travail_an / 12   # ~22.5 (configurable)
objectif_mois_ttc = objectif_jour_ttc × nb_jours_mois

# Monthly objective (part-time) — uses actual hours ratio
nb_heures_mois_partiel = 120   # user input
objectif_mois_partiel = objectif_jour_ttc × nb_jours_mois
# Also shows: objectif_mois / heures_mois = hourly target (€/h)
```

---

## 3. Tiered Commission / Bonus

**Source**: `Classeur1_version_1.xlsx` → Sheet "calcul des primes"

Calculates monthly bonuses for an employee based on a progressive tier system. Revenue above the break-even objective is rewarded at increasing percentages.

### Tier Structure (configurable)

| Surplus above objective | Bonus rate |
|---|---|
| 0 – 600 € | 10% |
| 600 – 900 € | 12% |
| 900 – 1 200 € | 14% |
| 1 200 – 1 500 € | 16% |
| 1 500 – 1 800 € | 18% |
| 1 800 – 2 100 € | 20% |
| 2 100 – 2 400 € | 22% |
| 2 400 – 2 700 € | 24% |
| 2 700+ € | 28% |

The tier thresholds and percentages are configurable per salon.

### Monthly Calculation Logic

For each month M:

```
# Step 1: Calculate this month's base objective
nb_jours_travailles = <user input for this month>
objectif_initial = objectif_jour_ttc × nb_jours_travailles

# Step 2: Carry forward any deficit from previous month
deficit_anterieur = MIN(surplus_previous_month, 0)
# If previous month had negative surplus, it becomes a deficit carried forward
# (uses SUMIF(surplus, "<0", surplus) — only negative values carry forward)

# Step 3: Adjusted objective
objectif = objectif_initial - deficit_anterieur
# (deficit is negative, so subtracting it INCREASES the objective)

# Step 4: Compare to actual result
resultat = <user input: actual CA TTC for this month>
surplus = resultat - objectif

# Step 5: Calculate tiered bonus on surplus (only if positive)
# For each tier bracket [lower, upper] with rate:
prime_bracket = MAX(MIN(surplus, upper) - lower, 0) × rate

# Total prime for the month
prime_totale = SUM(all bracket primes)
```

### Tier Bracket Formula (generic)

For bracket `i` with threshold `T[i]` and rate `R[i]`, where `T[0]=0`:

```
prime_bracket[0] = MAX(MIN(surplus, T[1]) × R[0], 0)
prime_bracket[i] = MAX((MIN(surplus, T[i+1]) - T[i]) × R[i], 0)   for i > 0
```

### Annual Totals

```
total_jours = SUM(nb_jours_travailles for all months)
total_objectif = SUM(objectif for all months)
total_resultat = SUM(resultat for all months)
total_surplus = total_resultat - total_objectif
total_primes = SUM(prime_totale for all months)
```

---

## 4. Product Resale Pricing

**Source**: `Classeur1_version_1.xlsx` → Sheet "prix revente"

Simple markup calculator for retail products.

### Inputs

| Variable | Description | Example |
|---|---|---|
| `prix_achat_ht` | Purchase price (excl. VAT) | 10.00 € |
| `coefficient` | Markup multiplier | 2.5 |

### Calculations

```
prix_vente_ht = prix_achat_ht × coefficient           # 25.00 €
prix_vente_ttc = prix_vente_ht × 1.20                  # 30.00 € (20% VAT)
marge_brute_ht = prix_vente_ht - prix_achat_ht         # 15.00 €
taux_marge = marge_brute_ht / prix_vente_ht             # 60%
```

### Competitor Comparison

Users can add competitor prices to see the differential:

```
ecart = prix_concurrent_ttc - prix_vente_ttc
```

Example comparisons:
| Concurrent | Prix TTC | Écart |
|---|---|---|
| Mon coiffeur.com | 28.00 € | -2.00 € |
| Bleu Libellule | 33.00 € | +3.00 € |
| Julie Coiffure | 34.00 € | +4.00 € |

---

## 5. Management Grid / Expense Benchmarks

**Source**: `Classeur1_version_1.xlsx` → Sheet "grille de gestion"

Reference table of ideal expense ratios as a percentage of CA (revenue). Used for the AI copilot "Analyse" feature.

| Poste de dépense | % du CA (Repère) | Idéal | Ce que cela comprend |
|---|---|---|---|
| Achats de marchandises | 10% | 8% | Produits techniques, bacs |
| Frais de Personnel | 50% | 40% | Salaires bruts + Charges patronales |
| Loyer et Immobilier | 8% | — | Loyer, charges copropriété, taxe foncière |
| Énergie et Fluides | 3% | — | Électricité, Eau, Gaz |
| Marketing et Com' | 3% | — | Réseaux sociaux, SMS, Vitrine, Pub locale |
| Frais Généraux | 5% | — | Assurances, Comptable, Logiciel, Frais TPE |
| Entretien et Divers | 1% | — | Blanchisserie, petit matériel, bureau |
| **Bénéfice (EBITDA)** | **20%** | — | Impôts, investissements, revenus du patron |

Additional reference:
- Honoraires comptables: no fixed %
- IS (Impôt société): Max 1 116 €/an
- IR (Impôt revenu): Max 756 €/an

---

## 6. Profitability Dashboard

**Source**: `Classeur1_version_1.xlsx` → Sheet "Rentabilité"

Monthly cash-flow / break-even tracking. A 12-month grid (Jan–Dec) with the following structure:

### Revenue Section

```
TOTAL_CA_REALISE_TTC[month]         # User input: actual revenue per month
SUBVENTIONS[month]                   # User input: any subsidies
```

### Section A — Staff Costs

```
# Per collaborator (up to 6):
salaire_net_collab[i][month]        # User input

sous_total_salaires[month] = SUM(salaire_net_collab[1..6][month])
cotisations_sociales[month]         # User input
TOTAL_SALAIRES_CHARGES[month] = sous_total_salaires[month] + cotisations_sociales[month]

# Annual % check:
pct_salaires = TOTAL_SALAIRES_CHARGES_annual / TOTAL_CA_annual
# Benchmarks: MY France = 55%, Idéal = 40%
```

### Section B — Operating Expenses (all TTC, monthly user inputs)

Categories: Achats produits, EDF/GDF, Honoraires comptable, Eau, Produits ménagés, TPE, Impôts & Taxes, Assurances, Presse, Tel/internet, Déplacements, Réceptions, Informatique, Marketing, Frais bancaire, Loyer charges comprises, Sacem, Boissons, Divers (×7 slots).

```
B_sous_total[month] = SUM(all B items for month)

# Annual % checks:
pct_achats_produits = achats_annual / CA_annual     # Benchmark: MY 9%, Idéal 6%
pct_sacem_row = sacem_annual / CA_annual            # Benchmark: MY 1.9%, Idéal 3%
pct_B_total = B_sous_total_annual / CA_annual       # Benchmark: MY 15%, Idéal 13%
# (same pattern for each row with benchmarks in cols O/P/Q)
```

### Totals and Break-Even

```
total_A_plus_B[month] = TOTAL_SALAIRES_CHARGES[month] + B_sous_total[month]

# VAT calculations
tva_payee_achats[month] = B_sous_total[month] - (B_sous_total[month] / 1.2)
remboursement_emprunt[month]    # User input

TOTAL_DECAISSEMENT[month] = total_A_plus_B[month] + tva_payee_achats[month] + remboursement_emprunt[month]

# Break-even point (salon only, excl. owner salary)
point_mort_salon[month] = TOTAL_SALAIRES_CHARGES[month] + B_sous_total[month] + remboursement_emprunt[month] + tva_a_payer[month]

# Owner salary
salaire_net_dirigeant[month]    # User input
cotisations_dirigeant[month] = salaire_net_dirigeant[month] × 0.45

# Break-even including owner
point_mort_dirigeant_inclus[month] = point_mort_salon[month] + salaire_net_dirigeant[month] + cotisations_dirigeant[month]

# Cash flow
cash_flow[month] = (TOTAL_CA_REALISE_TTC[month] + SUBVENTIONS[month]) - point_mort_dirigeant_inclus[month]

# VAT to pay
tva_encaissee[month] = TOTAL_CA_REALISE_TTC[month] - (TOTAL_CA_REALISE_TTC[month] / 1.2)
tva_a_payer[month] = tva_encaissee[month] - tva_payee_achats[month]
```

---

## 7. Client Volume Model

**Source**: `Classeur1_version_1.xlsx` → Sheet "Nb de clients"

Projects how many clients a salon needs to hit its revenue target.

### Inputs

| Variable | Description | Example |
|---|---|---|
| `objectif_annuel_ca_ttc` | Annual revenue target (TTC) | 240 000 € |
| `pct_clients_f` | % of visits that are women | 80% |
| `montant_my_f` | Average ticket — women (FM = fiche moyenne) | 65.00 € |
| `pct_clients_h` | % of visits that are men | 20% (auto: 1 - pct_f) |
| `montant_my_h` | Average ticket — men | 30.00 € |
| `nb_visit_my_f` | Average visits per year — women | 4.2 |
| `nb_visit_my_h` | Average visits per year — men | 6.6 |
| `nb_jours_semaine` | Open days per week | 6 |
| `nb_semaines_an` | Weeks per year | 52 |

### Calculations

```
# Blended average ticket (Fiche Moyenne Globale)
fmg = (pct_clients_f × montant_my_f) + (pct_clients_h × montant_my_h)
fmg_ht = fmg / 1.20

# Total visits needed per year
nb_total_visites_an = objectif_annuel_ca_ttc / fmg

# Split by gender
nb_visites_f = pct_clients_f × nb_total_visites_an
nb_visites_h = pct_clients_h × nb_total_visites_an

# Verify: should equal target
ca_total_check = (nb_visites_f × montant_my_f) + (nb_visites_h × montant_my_h)

# Unique clients needed (registered in file)
nb_clients_f = nb_visites_f / nb_visit_my_f
nb_clients_h = nb_visites_h / nb_visit_my_h
total_fichier = nb_clients_f + nb_clients_h

# Revenue split
ca_femmes = nb_visites_f × montant_my_f
ca_hommes = nb_visites_h × montant_my_h

# Daily metrics
nb_jours_ouverture_an = nb_jours_semaine × nb_semaines_an
nb_visites_f_jour = nb_visites_f / nb_jours_ouverture_an
nb_visites_h_jour = nb_visites_h / nb_jours_ouverture_an
nb_visites_total_jour = nb_total_visites_an / nb_jours_ouverture_an
ca_jour = objectif_annuel_ca_ttc / nb_jours_ouverture_an
```

### Monthly Distribution

Visits are distributed proportionally to the number of open days per month:

```
# Per month, given nb_jours_ouverture[month]:
nb_visites_f[month] = nb_visites_f_jour × nb_jours_ouverture[month]
nb_visites_h[month] = nb_visites_h_jour × nb_jours_ouverture[month]
total_visites[month] = nb_visites_f[month] + nb_visites_h[month]
```

Default open days per month: Jan=26, Feb=24, Mar=26, Apr=27, May=26, Jun=25, Jul=24, Aug=26, Sep=26, Oct=28, Nov=26, Dec=28 (total=312)

### Simulation (What-If: Average Ticket Increase)

```
# If average ticket increases by X%:
nouvelle_fm_f = montant_my_f × (1 + pct_augmentation_f)
delta_f = nouvelle_fm_f - montant_my_f
nouveau_ca_f = nouvelle_fm_f × nb_visites_f
gain_f = nouveau_ca_f - ca_femmes

# Same for men, then:
nouveau_ca_total = nouveau_ca_f + nouveau_ca_h
gain_total = nouveau_ca_total - objectif_annuel_ca_ttc
```

---

## 8. Pricing Strategy Simulator

**Source**: `Classeur1_version_1.xlsx` → Sheet "baisse des prix"

Conceptual model (currently text-based, no formulas) for demonstrating that lowering prices on bundled services can increase total margin.

### Business Logic

```
# Scenario: à la carte vs. forfait bundling

# Current state (à la carte)
nb_ventes_forfait = 2000
prix_forfait = 40 €
marge_forfait = 4 €
pct_ajout_soin = 15%                    # only 15% add a soin
nb_ventes_soin = nb_ventes_forfait × pct_ajout_soin   # 300
prix_soin = 10 €
marge_soin = 8 €
total_marge_actuelle = (nb_ventes_forfait × marge_forfait) + (nb_ventes_soin × marge_soin)
# = 8000 + 2400 = 10 400 €

# New strategy: bundle soin into forfait at a discount
prix_nouveau_forfait = 47 €             # instead of 40 + 10 = 50
marge_nouveau_forfait = marge_forfait + marge_soin - 3   # lose 3€ discount
pct_ajout_soin_nouveau = 50%            # bundling increases uptake
nb_ventes_avec_soin = nb_ventes_forfait × pct_ajout_soin_nouveau   # 1000
nb_ventes_sans_soin = nb_ventes_forfait - nb_ventes_avec_soin      # 1000

total_marge_nouvelle = (nb_ventes_sans_soin × marge_forfait) + (nb_ventes_avec_soin × (marge_forfait + marge_soin - 3))
# = 1000 × 4 + 1000 × 9 = 4000 + 9000  ... wait, let me recalc per Eric's example:
# = 1000 × 4€ + 1000 × 7€ = 11 000 €

gain = total_marge_nouvelle - total_marge_actuelle   # +600 €
```

The key insight: lowering prices via bundling increases uptake of high-margin add-ons, resulting in higher overall margin.

---

## 9. Salary Variables Form

**Source**: `variables.pdf`

A monthly form submitted per employee to generate payslips. Each form costs 28.80 € TTC (payslip processing fee).

### Form Fields

| Field | Type | Description |
|---|---|---|
| `periode` | Date | Pay period |
| `nom` | Text | Employee last name |
| `prenom` | Text | Employee first name |
| `prime_conventionnelle` | Percentage | Conventional bonus % |
| `ca_services_ht` | Currency (€) | Service revenue (excl. VAT) |
| `prime_revente` | Percentage | Resale bonus % |
| `ca_revente_ht` | Currency (€) | Product resale revenue (excl. VAT) |
| `absence_conges` | Date range | Paid leave (from–to inclusive) |
| `absence_maladie` | Date range | Sick leave (from–to inclusive) |
| `absence_non_justifiee` | Date range | Unjustified absence (from–to inclusive) |
| `commentaire` | Text | Free-form note |

### Billing Logic

```
nb_formulaires = nb_salaries
cout_par_bulletin = 28.80  # € TTC
total_requis = nb_formulaires × cout_par_bulletin

if solde_compte < total_requis:
    show_popup("Vous devez créditer votre compte")
else:
    send_to("contact@communauté-coiffure.com")
```

---

## 10. Employee Register

**Source**: `Classeur1_version_1.xlsx` → Sheet "registre entrée-sortie"

Legal employee register. Data model only (no calculations).

### Fields

| Field | Type |
|---|---|
| `nom_prenom` | Text |
| `nationalite` | Text |
| `date_naissance` | Date |
| `sexe` | M/F |
| `emploi` | Text (e.g. "Coiffeur", "Apprentie") |
| `qualification_professionnelle` | Text (e.g. "BP", "CAP") |
| `date_entree` | Date |
| `date_sortie` | Date (nullable) |
| `type_contrat` | Enum: CDI, CDD, Apprenti, Partiel |
| `type_document_etranger` | Text (nullable, e.g. "Titre de séjour") |
| `numero_document` | Text (nullable) |
| `temps_partiel` | Boolean |
| `temporaire` | Boolean |
| `nom_entreprise_interim` | Text (nullable) |

---

## Appendix: VAT Rules

All prices in the salon context use **20% French VAT**:

```
prix_ttc = prix_ht × 1.20
prix_ht = prix_ttc / 1.20
tva = prix_ttc - prix_ht   # equivalently: prix_ht × 0.20
```

## Appendix: Key Constants & Defaults

| Constant | Value | Notes |
|---|---|---|
| French VAT rate | 20% | Applied to all services and products |
| Default working weeks/year | 45.6 | Accounts for holidays |
| Owner working weeks/year | 48 | Less holiday |
| Default open days/week | 5–6 | Varies by salon |
| Payslip processing fee | 28.80 € TTC | Per employee per month |
| Default markup coefficient | 2.5 | For retail products |
| Default safety margin | 5% | On salary break-even |
| Default profit margin | 10% | On salary break-even |
| Default cost-per-minute margin | 10% | On service pricing |
