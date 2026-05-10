# Horizon Audit: richard@digitalbricks.io

**User**: Richard Osborne (richard@digitalbricks.io)  
**User ID**: `67b56986-89c3-4ff5-808e-d3177507d341`  
**Born**: 1986-02-28 (age 40)  
**Generated**: 2026-05-09  

---

## Section A: Raw Input Data

### A.1 Profile (`user_profiles`)

| Field | Value |
|-------|-------|
| Birth date | 1986-02-28 (age 40) |
| Target retirement age | 70 |
| Tax parts | 3.5 |
| Status | ae |
| AE activity type | bnc_non_reglementee |
| Versement libératoire | True |
| Monthly gross CA | 5600.00 € |
| Growth preset | ambitious (→ 6.0% / year) |
| CESU annual | 1400.00 € |
| Charity annual | 240.00 € |
| CAF override | none (auto-estimated) |
| Monthly revenue goal | 3000.00 € |
| World scale | pessimistic |
| Status change enabled | True |
| Status change year | null (never) |
| Status change target | sasu |
| Status change savings | null |

### A.2 Monthly Expenses (JSONB)

| Category | Amount (€) |
|----------|------------|
| abonnements | 100 |
| alimentation | 1500 |
| assurance | 0 |
| credit | 590 |
| divers | 0 |
| energie | 145 |
| impots | 140 |
| internet | 70 |
| loisirs | 200 |
| loyer | 500 |
| sante | 220 |
| transport | 240 |
| **TOTAL** | **3705.00** |

### A.3 Life Entities (`life_entities`, active only)

| # | Type | Name | Reference Date | Age at projection start | # Cost Events |
|---|------|------|----------------|------------------------|--------------|
| 1 | kid | Romy | N/A | 1 | 13 |
| 2 | kid | Ellie | N/A | 4 | 13 |
| 3 | kid | Saoirse | N/A | 8 | 13 |
| 4 | pet | Layla | N/A | 1 | 7 |
| 5 | tech | Macbook Air (2021) | N/A | 5 | 12 |
| 6 | tech | Macbook Air (2024) | N/A | 2 | 12 |
| 7 | car | Xsara (2010) | N/A | 15 | 7 |
| 8 | car | Peugeot (2006) | N/A | 19 | 7 |

#### A.3.1 Entity Ages at Key Projection Milestones

The projection Y-axis is `current_year + y` where `y` starts at 0 (2026).
Each entity's age during a given projection year = `entity_age_at_start + y`.

| Entity | Type | Age at y=0 (2026) | age at y=10 (2036) | age at y=30 (2056, retirement) | To_age max |
|--------|------|--------------------|--------------------|-------------------------------|------------|
| Romy | kid | 1 | 11 | 31 | 23 |
| Ellie | kid | 4 | 14 | 34 | 23 |
| Saoirse | kid | 8 | 18 | 38 | 23 |
| Layla | pet | 1 | 11 | 31 | 13 |
| Macbook Air (2021) | tech | 5 | 15 | 35 | 30 |
| Macbook Air (2024) | tech | 2 | 12 | 32 | 30 |
| Xsara (2010) | car | 15 | 25 | 45 | 8 |
| Peugeot (2006) | car | 19 | 29 | 49 | 8 |

#### A.3.2 Cost Events Detail

##### KID: Romy (age_at_start=1)

| ID | Label | From Age | To Age | Amount | Frequency | Active |
|----|-------|----------|--------|--------|-----------|--------|
| k-creche | Crèche / Garde d'enfant | 0 | 2 | 500€ | monthly | ✓ |
| k-cant-mat | Cantine maternelle | 3 | 5 | 100€ | monthly | ✓ |
| k-cant-prim | Cantine + périscolaire primaire | 6 | 11 | 150€ | monthly | ✓ |
| k-fourn-prim | Fournitures scolaires primaire | 6 | 11 | 200€ | annual | ✓ |
| k-cant-coll | Cantine collège | 11 | 15 | 150€ | monthly | ✓ |
| k-fourn-coll | Fournitures scolaires collège | 11 | 15 | 400€ | annual | ✓ |
| k-cant-lyc | Cantine lycée | 15 | 18 | 150€ | monthly | ✓ |
| k-fourn-lyc | Fournitures scolaires lycée | 15 | 18 | 600€ | annual | ✓ |
| k-camp | Camp d'été / Colonie | 6 | 17 | 800€ | annual | ✓ |
| k-extra | Activités extra-scolaires | 6 | 18 | 100€ | monthly | ✓ |
| k-permis | Permis de conduire | 18 | 18 | 1800€ | once | ✓ |
| k-voiture | Première voiture | 18 | 18 | 5000€ | once | ✓ |
| k-etudes | Études supérieures (logement, frais, vie) | 18 | 23 | 500€ | monthly | ✓ |

##### KID: Ellie (age_at_start=4)

| ID | Label | From Age | To Age | Amount | Frequency | Active |
|----|-------|----------|--------|--------|-----------|--------|
| k-creche | Crèche / Garde d'enfant | 0 | 2 | 500€ | monthly | ✓ |
| k-cant-mat | Cantine maternelle | 3 | 5 | 100€ | monthly | ✓ |
| k-cant-prim | Cantine + périscolaire primaire | 6 | 11 | 150€ | monthly | ✓ |
| k-fourn-prim | Fournitures scolaires primaire | 6 | 11 | 200€ | annual | ✓ |
| k-cant-coll | Cantine collège | 11 | 15 | 150€ | monthly | ✓ |
| k-fourn-coll | Fournitures scolaires collège | 11 | 15 | 400€ | annual | ✓ |
| k-cant-lyc | Cantine lycée | 15 | 18 | 150€ | monthly | ✓ |
| k-fourn-lyc | Fournitures scolaires lycée | 15 | 18 | 600€ | annual | ✓ |
| k-camp | Camp d'été / Colonie | 6 | 17 | 800€ | annual | ✓ |
| k-extra | Activités extra-scolaires | 6 | 18 | 100€ | monthly | ✓ |
| k-permis | Permis de conduire | 18 | 18 | 1800€ | once | ✓ |
| k-voiture | Première voiture | 18 | 18 | 5000€ | once | ✓ |
| k-etudes | Études supérieures (logement, frais, vie) | 18 | 23 | 500€ | monthly | ✓ |

##### KID: Saoirse (age_at_start=8)

| ID | Label | From Age | To Age | Amount | Frequency | Active |
|----|-------|----------|--------|--------|-----------|--------|
| k-creche | Crèche / Garde d'enfant | 0 | 2 | 500€ | monthly | ✓ |
| k-cant-mat | Cantine maternelle | 3 | 5 | 100€ | monthly | ✓ |
| k-cant-prim | Cantine + périscolaire primaire | 6 | 11 | 150€ | monthly | ✓ |
| k-fourn-prim | Fournitures scolaires primaire | 6 | 11 | 200€ | annual | ✓ |
| k-cant-coll | Cantine collège | 11 | 15 | 150€ | monthly | ✓ |
| k-fourn-coll | Fournitures scolaires collège | 11 | 15 | 400€ | annual | ✓ |
| k-cant-lyc | Cantine lycée | 15 | 18 | 150€ | monthly | ✓ |
| k-fourn-lyc | Fournitures scolaires lycée | 15 | 18 | 600€ | annual | ✓ |
| k-camp | Camp d'été / Colonie | 6 | 17 | 800€ | annual | ✓ |
| k-extra | Activités extra-scolaires | 6 | 18 | 100€ | monthly | ✓ |
| k-permis | Permis de conduire | 18 | 18 | 1800€ | once | ✓ |
| k-voiture | Première voiture | 18 | 18 | 5000€ | once | ✓ |
| k-etudes | Études supérieures (logement, frais, vie) | 18 | 23 | 500€ | monthly | ✓ |

##### PET: Layla (age_at_start=1)

| ID | Label | From Age | To Age | Amount | Frequency | Active |
|----|-------|----------|--------|--------|-----------|--------|
| p-food | Nourriture | 0 | 13 | 600€ | annual | ✓ |
| p-vacc-primo | Vaccins primo | 0 | 1 | 250€ | once | ✓ |
| p-vacc-rappel | Rappel vaccins | 1 | 13 | 80€ | annual | ✓ |
| p-steril | Stérilisation | 0 | 1 | 300€ | once | ✓ |
| p-vet | Vétérinaire annuel | 1 | 13 | 200€ | annual | ✓ |
| p-groom | Toilettage | 0 | 13 | 300€ | annual | ✓ |
| p-old | Soins vétérinaires renforcés (vieillesse) | 10 | 13 | 400€ | annual | ✓ |

##### TECH: Macbook Air (2021) (age_at_start=5)

| ID | Label | From Age | To Age | Amount | Frequency | Active |
|----|-------|----------|--------|--------|-----------|--------|
| t-accessories | Accessoires / Réparations | 0 | 30 | 100€ | annual | ✓ |
| t-insurance | Assurance / Garantie étendue | 0 | 3 | 100€ | annual | ✓ |
| t-replace-1 | Remplacement laptop (tous les 3 ans) | 3 | 3 | 1200€ | once | ✓ |
| t-replace-2 | Remplacement laptop (tous les 3 ans) | 6 | 6 | 1200€ | once | ✓ |
| t-replace-3 | Remplacement laptop (tous les 3 ans) | 9 | 9 | 1200€ | once | ✓ |
| t-replace-4 | Remplacement laptop (tous les 3 ans) | 12 | 12 | 1200€ | once | ✓ |
| t-replace-5 | Remplacement laptop (tous les 3 ans) | 15 | 15 | 1200€ | once | ✓ |
| t-replace-6 | Remplacement laptop (tous les 3 ans) | 18 | 18 | 1200€ | once | ✓ |
| t-replace-7 | Remplacement laptop (tous les 3 ans) | 21 | 21 | 1200€ | once | ✓ |
| t-replace-8 | Remplacement laptop (tous les 3 ans) | 24 | 24 | 1200€ | once | ✓ |
| t-replace-9 | Remplacement laptop (tous les 3 ans) | 27 | 27 | 1200€ | once | ✓ |
| t-replace-10 | Remplacement laptop (tous les 3 ans) | 30 | 30 | 1200€ | once | ✓ |

##### TECH: Macbook Air (2024) (age_at_start=2)

| ID | Label | From Age | To Age | Amount | Frequency | Active |
|----|-------|----------|--------|--------|-----------|--------|
| t-accessories | Accessoires / Réparations | 0 | 30 | 100€ | annual | ✓ |
| t-insurance | Assurance / Garantie étendue | 0 | 3 | 100€ | annual | ✓ |
| t-replace-1 | Remplacement laptop (tous les 3 ans) | 3 | 3 | 1200€ | once | ✓ |
| t-replace-2 | Remplacement laptop (tous les 3 ans) | 6 | 6 | 1200€ | once | ✓ |
| t-replace-3 | Remplacement laptop (tous les 3 ans) | 9 | 9 | 1200€ | once | ✓ |
| t-replace-4 | Remplacement laptop (tous les 3 ans) | 12 | 12 | 1200€ | once | ✓ |
| t-replace-5 | Remplacement laptop (tous les 3 ans) | 15 | 15 | 1200€ | once | ✓ |
| t-replace-6 | Remplacement laptop (tous les 3 ans) | 18 | 18 | 1200€ | once | ✓ |
| t-replace-7 | Remplacement laptop (tous les 3 ans) | 21 | 21 | 1200€ | once | ✓ |
| t-replace-8 | Remplacement laptop (tous les 3 ans) | 24 | 24 | 1200€ | once | ✓ |
| t-replace-9 | Remplacement laptop (tous les 3 ans) | 27 | 27 | 1200€ | once | ✓ |
| t-replace-10 | Remplacement laptop (tous les 3 ans) | 30 | 30 | 1200€ | once | ✓ |

##### CAR: Xsara (2010) (age_at_start=15)

| ID | Label | From Age | To Age | Amount | Frequency | Active |
|----|-------|----------|--------|--------|-----------|--------|
| c-insurance | Assurance auto | 0 | 8 | 600€ | annual | ✓ |
| c-fuel | Carburant / Énergie | 0 | 8 | 1200€ | annual | ✓ |
| c-maintenance | Entretien courant (révisions, pneus, freins) | 0 | 8 | 400€ | annual | ✓ |
| c-ct-1 | Contrôle technique à 4 ans | 4 | 4 | 80€ | once | ✓ |
| c-ct-2 | Contrôle technique à 6 ans | 6 | 6 | 80€ | once | ✓ |
| c-ct-3 | Contrôle technique à 8 ans | 8 | 8 | 80€ | once | ✓ |
| c-replace | Remplacement véhicule | 8 | 8 | 18000€ | once | ✓ |

##### CAR: Peugeot (2006) (age_at_start=19)

| ID | Label | From Age | To Age | Amount | Frequency | Active |
|----|-------|----------|--------|--------|-----------|--------|
| c-insurance | Assurance auto | 0 | 8 | 600€ | annual | ✓ |
| c-fuel | Carburant / Énergie | 0 | 8 | 1200€ | annual | ✓ |
| c-maintenance | Entretien courant (révisions, pneus, freins) | 0 | 8 | 400€ | annual | ✓ |
| c-ct-1 | Contrôle technique à 4 ans | 4 | 4 | 80€ | once | ✓ |
| c-ct-2 | Contrôle technique à 6 ans | 6 | 6 | 80€ | once | ✓ |
| c-ct-3 | Contrôle technique à 8 ans | 8 | 8 | 80€ | once | ✓ |
| c-replace | Remplacement véhicule | 8 | 8 | 18000€ | once | ✓ |

### A.4 Recurring Expenses

*(None — no recurring expenses configured)*

### A.5 Investment Allocations

| Vehicle | Existing Balance (€) | Monthly Contribution (€) |
|---------|---------------------|---------------------------|
| av_euro | 250.00 | 250.00 |
| livret_a | 500.00 | 500.00 |
| **TOTAL** | **750.00** | **750.00** |

### A.6 Projects

| # | Type | Label | Year | Cost (€) |
|---|------|-------|------|----------|
| | event | Renovation grange | 2028 | 20000.0 |
| | event | Renovation sdb extérieur | 2030 | 10000.0 |

---
## Section B: Formula Reference

### B.1 Revenue

```
gross_annual = monthly_gross_ca × 12 × (1 + growth_rate)^y
  = 5600.00 × 12 × (1 + 0.06)^y
charges = gross_annual × AE_rate(activity_type, year)
  AE_rate for bnc_non_reglementee:
    2025: 24.20%, 2026-2030: 24.60%, 2031+: 26.10%
  With versement libératoire: add ~1.0-2.2% depending on income bracket
cfe = get_cfe_estimate(year, inflation_rate)
  CFE base ~250-550€, scaled by inflation
```

### B.2 Expenses

```
base_expenses = monthly_expenses_total × 12 × (1 + cost_living_rate)^y
  = 3705.00 × 12 × (1 + cost_living_rate)^y

Life entity cost per event:
  if entity_age_at_start + y in [from_age, to_age]:
    amount × (1 + inflation_rate)^y  (once cost: fires only at from_age)
    monthly costs × 12 to get annual

Recurring expenses:
  if from_year <= year <= to_year:
    annual_amount × (1 + inflation_rate)^y

Projects:
  'event' type: event_cost in event_year only
  'invest' type: purchase_cost in start_year, then annual_income - annual_expenses - tax
```

### B.3 CAF & Tax Credits

```
CAF: auto-estimated from number of kids under 20, reference_year, household_income
  If caf_override_monthly is set: caf_override × 12 × 1.015^y (only while kids < 20)
CESU credit: min(cesu_annual × (1+inflation)^y × 0.50, 6000€)
Charity credit: min(charity_annual × (1+inflation)^y × 0.66, 20000€)
```

### B.4 Investments

```
For each vehicle vk:
  contrib = monthly × 12
  returns = balance × effective_rate
  effective_rate = max(0.005, nominal_rate - inflation × 0.25)
    Regulated vehicles (livret_a, ldds, av_euro):
      pessimist: use nominal_rate
      others: max(nominal_rate, inflation)
  Tax on returns: see B.4.1 below
  Ceilings: nominal (not inflation-adjusted)
    livret_a: 22950€, ldds: 12000€
  Overflow: livret_a → ldds, ldds → av_euro
```

### B.4.1 Tax by Holding Period (TASK-5.10)

| Vehicle | Pre-maturity | Post-maturity | Existing balance |
|---------|-------------|---------------|-----------------|
| PEA | PFU 30% (< 5yr) | PS only 17.2% (≥ 5yr) | Treated as mature |
| AV (euro/UC) | PFU 30% (< 8yr) | PS only 17.2% (≥ 8yr) | Treated as mature |
| SCPI | PFU 30% (always) | — | PFU 30% |
| PER | ~20% flat (exit tax) | — | ~20% |
| Livret A / LDDS | Tax-free | — | Tax-free |

### B.5 Post-Retirement (Phase 2)

```
gross = 0 (no work income)
pension_annual = pension_monthly × 12
charges = 0, cfe = 0, caf = 0, tax_credits = 0
Investment returns continue (no new contributions)
shortfall = total_outgoing - total_income
if shortfall > 0: withdraw from savings (liquid first)
  Priority: livret_a → ldds → av_euro → av_uc → pea → scpi → per
```

### B.6 Derived Fields

```
net_annual = total_income - total_outgoing + status_bonus
total_wealth = sum(all vehicle balances)
passive_monthly = total_wealth × 4% / 12
total_monthly_income = (gross + project_income + caf + pension) / 12 + passive
retirement_monthly_income = passive + (project_income + pension) / 12
goal_reached = retirement_monthly_income >= monthly_revenue_goal
```

---
## Section C: Projection Results

### C.1 Scale: **optimistic**

- **Inflation rate**: 1.8% / year
- **Cost of living rate**: 2.0% / year
- **Years projected**: 34
- **Projection range**: 2026 (age 40) → 2059 (age 73)

#### Timeline (Year-by-Year)

| Year | Age | Phase | Gross Annual | Charges | CFE | Base Exp | Kid Exp | Pet Exp | Car Exp | Tech Exp | Rec Exp | Proj Exp | Proj Inc | CAF | Tax Credits | Status Bonus | Pension | Total Income | Total Outgoing | Net Annual | Year Invested | Year Returns | Total Wealth | Passive/mo | Goal? |
|------|-----|-------|-------------|---------|-----|----------|---------|---------|---------|----------|---------|----------|----------|-----|-------------|-------------|---------|-------------|----------------|------------|--------------|-------------|-------------|-----------|-------|
| 2026 | 40 | ACC | 67200.00 | 17606.40 | 300.00 | 44460.00 | 11200.00 | 1180.00 | 0.00 | 300.00 | 0.00 | 0.00 | 0.00 | 4056.00 | 858.40 | 0.00 | 0.00 | 72114.40 | 75046.40 | -2932.00 | 9000.00 | 17.16 | 9767.16 | 32.56 |  |
| 2027 | 41 | ACC | 71232.00 | 19090.18 | 305.40 | 45349.20 | 11401.60 | 1201.24 | 0.00 | 2748.60 | 0.00 | 0.00 | 0.00 | 4116.84 | 873.85 | 0.00 | 0.00 | 76222.69 | 80096.22 | -3873.52 | 9000.00 | 223.45 | 18990.60 | 63.30 |  |
| 2028 | 42 | ACC | 75505.92 | 20764.13 | 310.90 | 46256.18 | 9534.18 | 1222.86 | 0.00 | 207.26 | 0.00 | 20000.00 | 0.00 | 4178.64 | 889.58 | 0.00 | 0.00 | 80574.14 | 98295.52 | -17721.38 | 9000.00 | 434.54 | 28425.14 | 94.75 |  |
| 2029 | 43 | ACC | 80036.28 | 22009.98 | 316.49 | 47181.31 | 12026.75 | 1244.87 | 0.00 | 211.00 | 0.00 | 0.00 | 0.00 | 4241.28 | 905.59 | 0.00 | 0.00 | 85183.15 | 82990.39 | 2192.75 | 9000.00 | 650.54 | 38075.68 | 126.92 |  |
| 2030 | 44 | ACC | 84838.45 | 24178.96 | 322.19 | 48124.93 | 10095.29 | 1267.28 | 0.00 | 2792.32 | 0.00 | 10000.00 | 0.00 | 4304.88 | 921.89 | 0.00 | 0.00 | 90065.23 | 96780.97 | -6715.75 | 9000.00 | 808.65 | 47884.33 | 159.61 |  |
| 2031 | 45 | ACC | 89928.76 | 25629.70 | 327.99 | 49087.43 | 13338.25 | 1290.09 | 0.00 | 218.66 | 0.00 | 0.00 | 0.00 | 4369.44 | 938.49 | 0.00 | 0.00 | 95236.69 | 89892.12 | 5344.57 | 9000.00 | 868.92 | 57753.25 | 192.51 |  |
| 2032 | 46 | ACC | 95324.48 | 27167.48 | 333.89 | 50069.18 | 13578.33 | 1313.31 | 0.00 | 222.60 | 0.00 | 0.00 | 0.00 | 4434.96 | 955.38 | 0.00 | 0.00 | 100714.82 | 92684.80 | 8030.03 | 9000.00 | 930.30 | 67683.55 | 225.61 |  |
| 2033 | 47 | ACC | 101043.95 | 28797.53 | 339.90 | 51070.56 | 19034.60 | 1336.95 | 0.00 | 2945.83 | 0.00 | 0.00 | 0.00 | 4501.56 | 972.58 | 0.00 | 0.00 | 106518.09 | 103525.38 | 2992.71 | 9000.00 | 992.84 | 77676.39 | 258.92 |  |
| 2034 | 48 | ACC | 107106.59 | 30525.38 | 346.02 | 52091.98 | 14532.92 | 1361.02 | 0.00 | 230.68 | 0.00 | 0.00 | 0.00 | 4569.00 | 990.08 | 0.00 | 0.00 | 112665.67 | 99087.99 | 13577.68 | 9000.00 | 1056.54 | 87732.92 | 292.44 |  |
| 2035 | 49 | ACC | 113532.99 | 33492.23 | 352.25 | 53133.82 | 14794.51 | 1855.18 | 0.00 | 234.83 | 0.00 | 0.00 | 0.00 | 4637.64 | 1007.91 | 0.00 | 0.00 | 119178.53 | 103862.82 | 15315.71 | 9000.00 | 1121.42 | 97854.34 | 326.18 |  |
| 2036 | 50 | ACC | 120344.97 | 35501.76 | 358.59 | 54196.49 | 32034.10 | 1888.58 | 0.00 | 3107.79 | 0.00 | 0.00 | 0.00 | 4707.12 | 1026.05 | 0.00 | 0.00 | 126078.13 | 127087.31 | -1009.18 | 9000.00 | 1187.51 | 108041.86 | 360.14 |  |
| 2037 | 51 | ACC | 127565.66 | 37631.87 | 365.05 | 55280.42 | 20442.54 | 1922.57 | 0.00 | 243.36 | 0.00 | 0.00 | 0.00 | 4777.80 | 1044.52 | 0.00 | 0.00 | 133387.98 | 115885.81 | 17502.17 | 9000.00 | 1254.84 | 118296.69 | 394.32 |  |
| 2038 | 52 | ACC | 135219.60 | 39889.78 | 371.62 | 56386.03 | 18085.32 | 1957.18 | 0.00 | 247.74 | 0.00 | 0.00 | 0.00 | 4849.44 | 1063.32 | 0.00 | 0.00 | 141132.36 | 116937.67 | 24194.69 | 9000.00 | 1323.42 | 128620.11 | 428.73 |  |
| 2039 | 53 | ACC | 143332.78 | 42283.17 | 378.31 | 57513.75 | 18410.86 | 0.00 | 0.00 | 3278.65 | 0.00 | 0.00 | 0.00 | 2155.32 | 1082.46 | 0.00 | 0.00 | 146570.56 | 121864.73 | 24705.83 | 9000.00 | 1393.27 | 139013.38 | 463.38 |  |
| 2040 | 54 | ACC | 151932.75 | 44820.16 | 385.11 | 58664.03 | 37227.76 | 0.00 | 0.00 | 256.74 | 0.00 | 0.00 | 0.00 | 2187.60 | 1101.94 | 0.00 | 0.00 | 155222.29 | 141353.80 | 13868.49 | 9000.00 | 1464.43 | 149477.81 | 498.26 |  |
| 2041 | 55 | ACC | 161048.71 | 47509.37 | 392.05 | 59837.31 | 21431.89 | 0.00 | 0.00 | 261.36 | 0.00 | 0.00 | 0.00 | 2220.36 | 1121.78 | 0.00 | 0.00 | 164390.85 | 129431.98 | 34958.87 | 9000.00 | 1536.91 | 160014.72 | 533.38 |  |
| 2042 | 56 | ACC | 170711.63 | 50359.93 | 399.10 | 61034.05 | 13835.59 | 0.00 | 0.00 | 3458.90 | 0.00 | 0.00 | 0.00 | 0.00 | 1141.97 | 0.00 | 0.00 | 171853.60 | 129087.58 | 42766.02 | 9000.00 | 1610.75 | 170625.47 | 568.75 |  |
| 2043 | 57 | ACC | 180954.33 | 53381.53 | 406.29 | 62254.73 | 30336.13 | 0.00 | 0.00 | 270.86 | 0.00 | 0.00 | 0.00 | 0.00 | 1162.52 | 0.00 | 0.00 | 182116.86 | 146649.54 | 35467.31 | 9000.00 | 1685.96 | 181311.43 | 604.37 |  |
| 2044 | 58 | ACC | 191811.59 | 56584.42 | 413.60 | 63499.83 | 16544.03 | 0.00 | 0.00 | 275.73 | 0.00 | 0.00 | 0.00 | 0.00 | 1183.45 | 0.00 | 0.00 | 192995.04 | 137317.61 | 55677.43 | 9000.00 | 1762.57 | 192073.99 | 640.25 |  |
| 2045 | 59 | ACC | 203320.29 | 59979.48 | 421.05 | 64769.82 | 16841.82 | 0.00 | 0.00 | 3649.06 | 0.00 | 0.00 | 0.00 | 0.00 | 1204.75 | 0.00 | 0.00 | 204525.04 | 145661.24 | 58863.80 | 9000.00 | 1840.60 | 202914.60 | 676.38 |  |
| 2046 | 60 | ACC | 215519.50 | 63578.25 | 428.62 | 66065.22 | 8572.49 | 0.00 | 0.00 | 285.75 | 0.00 | 0.00 | 0.00 | 0.00 | 1226.44 | 0.00 | 0.00 | 216745.94 | 138930.34 | 77815.61 | 9000.00 | 1920.10 | 213834.69 | 712.78 |  |
| 2047 | 61 | ACC | 228450.67 | 67392.95 | 436.34 | 67386.53 | 8726.79 | 0.00 | 0.00 | 290.89 | 0.00 | 0.00 | 0.00 | 0.00 | 1248.51 | 0.00 | 0.00 | 229699.19 | 144233.50 | 85465.69 | 9000.00 | 2001.07 | 224835.76 | 749.45 |  |
| 2048 | 62 | ACC | 242157.71 | 71436.53 | 444.19 | 68734.26 | 8883.87 | 0.00 | 0.00 | 3849.68 | 0.00 | 0.00 | 0.00 | 0.00 | 1270.99 | 0.00 | 0.00 | 243428.70 | 153348.53 | 90080.17 | 9000.00 | 2083.55 | 235919.31 | 786.40 |  |
| 2049 | 63 | ACC | 256687.18 | 75722.72 | 452.19 | 70108.94 | 0.00 | 0.00 | 0.00 | 301.46 | 0.00 | 0.00 | 0.00 | 0.00 | 1293.86 | 0.00 | 0.00 | 257981.04 | 146585.31 | 111395.73 | 9000.00 | 2167.57 | 247086.87 | 823.62 |  |
| 2050 | 64 | ACC | 272088.41 | 80266.08 | 460.33 | 71511.12 | 0.00 | 0.00 | 0.00 | 306.89 | 0.00 | 0.00 | 0.00 | 0.00 | 1317.15 | 0.00 | 0.00 | 273405.56 | 152544.41 | 120861.15 | 9000.00 | 2253.15 | 258340.02 | 861.13 |  |
| 2051 | 65 | ACC | 288413.71 | 85082.05 | 468.61 | 72941.34 | 0.00 | 0.00 | 0.00 | 4061.33 | 0.00 | 0.00 | 0.00 | 0.00 | 1340.86 | 0.00 | 0.00 | 289754.57 | 162553.33 | 127201.25 | 9000.00 | 2340.33 | 269680.35 | 898.93 |  |
| 2052 | 66 | ACC | 305718.54 | 90186.97 | 477.05 | 74400.17 | 0.00 | 0.00 | 0.00 | 159.02 | 0.00 | 0.00 | 0.00 | 0.00 | 1365.00 | 0.00 | 0.00 | 307083.53 | 165223.20 | 141860.33 | 9000.00 | 2429.13 | 281109.48 | 937.03 |  |
| 2053 | 67 | ACC | 324061.65 | 95598.19 | 485.64 | 75888.17 | 0.00 | 0.00 | 0.00 | 161.88 | 0.00 | 0.00 | 0.00 | 0.00 | 1389.57 | 0.00 | 0.00 | 325451.21 | 172133.87 | 153317.34 | 9000.00 | 2519.58 | 292629.06 | 975.43 |  |
| 2054 | 68 | ACC | 343505.35 | 101334.08 | 494.38 | 77405.94 | 0.00 | 0.00 | 0.00 | 2142.30 | 0.00 | 0.00 | 0.00 | 0.00 | 1414.58 | 0.00 | 0.00 | 344919.93 | 181376.70 | 163543.23 | 9000.00 | 2611.72 | 304240.78 | 1014.14 |  |
| 2055 | 69 | ACC | 364115.67 | 107414.12 | 503.28 | 78954.05 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 1440.04 | 0.00 | 0.00 | 365555.71 | 186871.45 | 178684.26 | 9000.00 | 2705.58 | 315946.36 | 1053.15 |  |
| 2056 | 70 | RET | 0.00 | 0.00 | 0.00 | 80533.14 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 80533.14 | 0.00 | 0.00 | 6253.32 | 241666.55 | 805.56 |  |
| 2057 | 71 | RET | 0.00 | 0.00 | 0.00 | 82143.80 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 82143.80 | 0.00 | 0.00 | 4726.42 | 164249.17 | 547.50 |  |
| 2058 | 72 | RET | 0.00 | 0.00 | 0.00 | 83786.67 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 83786.67 | 0.00 | 0.00 | 3135.12 | 83597.61 | 278.66 |  |
| 2059 | 73 | RET | 0.00 | 0.00 | 0.00 | 85462.41 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 85462.41 | -307.37 | 0.00 | 1557.42 | 0.00 | 0.00 |  |

#### Summary Statistics

| Statistic | Value |
|-----------|-------|
| Total years | 34 |
| Final wealth | 0.00 € |
| Final passive/month | 0.00 € |
| Total invested | 270000.00 € |
| Total returns | 60868.68 € |
| Goal reached? | NO |
| Wealth exhaustion age | 73 |
| Retirement monthly income | 0.00 € |
| Retirement monthly gap | -6711.10 € |

#### Wealth Milestones

| Threshold | Year | Age |
|-----------|------|-----|
| 100k€ | 2036 | 50 |
| 250k€ | 2050 | 64 |

#### Insights & Recommendations

| # | ID | Category | Severity | Title | Impact (€) | Action |
|---|----|----------|----------|-------|------------|--------|
| 1 | wealth_exhaustion | savings | critical | Patrimoine épuisé à 73 ans | -331926.02 | Augmentez votre épargne mensuelle de 709€ |
| 2 | negative_net | expenses | critical | Dépenses > revenus en 2026 | -50000.00 | Vérifiez vos charges et votre CA prévisionnel |
| 3 | savings_allocation_unbalanced | allocation | warning | Épargne trop prudente | 30000.00 | Redirigez une partie vers PEA ou AV unités de compte |
| 4 | no_goal_reached | savings | warning | Objectif non atteint | 0.00 | Augmentez l'épargne ou ajoutez des projets de revenus |
| 5 | one_more_year | income | opportunity | Une année de plus ferait la différence | 11705.58 | Envisagez de repousser votre âge de retraite d'un an |

**Insight #1: Patrimoine épuisé à 73 ans** (critical)
- **Rule**: `wealth_exhaustion`
- **Description**: Votre épargne ne couvre que 3 ans de retraite. Pour tenir jusqu'à 95 ans, épargnez 709€/mois de plus.
- **Impact on wealth**: -331926.02 €
- **Action**: Augmentez votre épargne mensuelle de 709€

**Insight #2: Dépenses > revenus en 2026** (critical)
- **Rule**: `negative_net`
- **Description**: Vos dépenses dépassent vos revenus en 2026 (âge 40 ans). Votre épargne fond au lieu de croître.
- **Impact on wealth**: -50000.00 €
- **Action**: Vérifiez vos charges et votre CA prévisionnel

**Insight #3: Épargne trop prudente** (warning)
- **Rule**: `savings_allocation_unbalanced`
- **Description**: Plus de 80% de vos versements sont sur des supports à faible rendement (Livret A, LDDS, fonds euros). Diversifier vers AV UC ou PEA augmenterait votre patrimoine final.
- **Impact on wealth**: 30000.00 €
- **Action**: Redirigez une partie vers PEA ou AV unités de compte

**Insight #4: Objectif non atteint** (warning)
- **Rule**: `no_goal_reached`
- **Description**: Votre objectif de revenu n'est pas atteint à la retraite. Actuellement 0€/mois de passif projeté.
- **Impact on wealth**: 0.00 €
- **Action**: Augmentez l'épargne ou ajoutez des projets de revenus

**Insight #5: Une année de plus ferait la différence** (opportunity)
- **Rule**: `one_more_year`
- **Description**: Repousser la retraite d'un an ajouterait environ 11 705€ à votre patrimoine tout en réduisant la durée de retrait.
- **Impact on wealth**: 11705.58 €
- **Action**: Envisagez de repousser votre âge de retraite d'un an

#### Readiness Score

- **Score**: 15/100
- **Band**: Fragile (rose)
- **Summary**: Votre situation est fragile. Concentrez-vous sur la constitution d'un fonds d'urgence et l'augmentation de votre épargne.

| Component | Score | Weight |
|-----------|-------|--------|
| goal_coverage | 0 | 30% |
| wealth_durability | 0 | 25% |
| savings_rate | 0 | 15% |
| diversification | 50 | 10% |
| growth_trajectory | 100 | 10% |
| buffer_adequacy | 0 | 10% |

---

### C.2 Scale: **moderate**

- **Inflation rate**: 2.5% / year
- **Cost of living rate**: 3.0% / year
- **Years projected**: 33
- **Projection range**: 2026 (age 40) → 2058 (age 72)

#### Timeline (Year-by-Year)

| Year | Age | Phase | Gross Annual | Charges | CFE | Base Exp | Kid Exp | Pet Exp | Car Exp | Tech Exp | Rec Exp | Proj Exp | Proj Inc | CAF | Tax Credits | Status Bonus | Pension | Total Income | Total Outgoing | Net Annual | Year Invested | Year Returns | Total Wealth | Passive/mo | Goal? |
|------|-----|-------|-------------|---------|-----|----------|---------|---------|---------|----------|---------|----------|----------|-----|-------------|-------------|---------|-------------|----------------|------------|--------------|-------------|-------------|-----------|-------|
| 2026 | 40 | ACC | 67200.00 | 17606.40 | 300.00 | 44460.00 | 11200.00 | 1180.00 | 0.00 | 300.00 | 0.00 | 0.00 | 0.00 | 4056.00 | 858.40 | 0.00 | 0.00 | 72114.40 | 75046.40 | -2932.00 | 9000.00 | 16.80 | 9766.80 | 32.56 |  |
| 2027 | 41 | ACC | 71232.00 | 19090.18 | 307.50 | 45793.80 | 11480.00 | 1209.50 | 0.00 | 2767.50 | 0.00 | 0.00 | 0.00 | 4116.84 | 879.86 | 0.00 | 0.00 | 76228.70 | 80648.48 | -4419.78 | 9000.00 | 218.72 | 18985.52 | 63.29 |  |
| 2028 | 42 | ACC | 75505.92 | 20764.13 | 315.19 | 47167.61 | 9665.75 | 1239.74 | 0.00 | 210.12 | 0.00 | 20000.00 | 0.00 | 4178.64 | 901.86 | 0.00 | 0.00 | 80586.42 | 99362.54 | -18776.13 | 9000.00 | 425.30 | 28410.82 | 94.70 |  |
| 2029 | 43 | ACC | 80036.28 | 22009.98 | 323.07 | 48582.64 | 12276.55 | 1270.73 | 0.00 | 215.38 | 0.00 | 0.00 | 0.00 | 4241.28 | 924.40 | 0.00 | 0.00 | 85201.96 | 84678.35 | 523.61 | 9000.00 | 636.63 | 38047.44 | 126.82 |  |
| 2030 | 44 | ACC | 84838.45 | 24178.96 | 331.14 | 50040.12 | 10375.84 | 1302.50 | 0.00 | 2869.91 | 0.00 | 10000.00 | 0.00 | 4304.88 | 947.51 | 0.00 | 0.00 | 90090.84 | 99098.48 | -9007.63 | 9000.00 | 789.89 | 47837.34 | 159.46 |  |
| 2031 | 45 | ACC | 89928.76 | 25629.70 | 339.42 | 51541.33 | 13803.18 | 1335.06 | 0.00 | 226.28 | 0.00 | 0.00 | 0.00 | 4369.44 | 971.20 | 0.00 | 0.00 | 95269.40 | 92874.97 | 2394.43 | 9000.00 | 845.15 | 57682.49 | 192.27 |  |
| 2032 | 46 | ACC | 95324.48 | 27167.48 | 347.91 | 53087.57 | 14148.26 | 1368.44 | 0.00 | 231.94 | 0.00 | 0.00 | 0.00 | 4434.96 | 995.48 | 0.00 | 0.00 | 100754.93 | 96351.59 | 4403.34 | 9000.00 | 901.36 | 67583.85 | 225.28 |  |
| 2033 | 47 | ACC | 101043.95 | 28797.53 | 356.61 | 54680.19 | 19969.92 | 1402.65 | 0.00 | 3090.58 | 0.00 | 0.00 | 0.00 | 4501.56 | 1020.37 | 0.00 | 0.00 | 106565.88 | 108297.48 | -1731.60 | 9000.00 | 958.53 | 77542.38 | 258.47 |  |
| 2034 | 48 | ACC | 107106.59 | 30525.38 | 365.52 | 56320.60 | 15351.88 | 1437.72 | 0.00 | 243.68 | 0.00 | 0.00 | 0.00 | 4569.00 | 1045.88 | 0.00 | 0.00 | 112721.47 | 104244.77 | 8476.70 | 9000.00 | 1016.68 | 87559.06 | 291.86 |  |
| 2035 | 49 | ACC | 113532.99 | 33492.23 | 374.66 | 58010.22 | 15735.67 | 1973.20 | 0.00 | 249.77 | 0.00 | 0.00 | 0.00 | 4637.64 | 1072.02 | 0.00 | 0.00 | 119242.65 | 109835.76 | 9406.89 | 9000.00 | 1075.84 | 97634.89 | 325.45 |  |
| 2036 | 50 | ACC | 120344.97 | 35501.76 | 384.03 | 59750.52 | 34306.27 | 2022.53 | 0.00 | 3328.22 | 0.00 | 0.00 | 0.00 | 4707.12 | 1098.82 | 0.00 | 0.00 | 126150.91 | 135293.33 | -9142.42 | 9000.00 | 1136.01 | 107770.90 | 359.24 |  |
| 2037 | 51 | ACC | 127565.66 | 37631.87 | 393.63 | 61543.04 | 22043.06 | 2073.10 | 0.00 | 262.42 | 0.00 | 0.00 | 0.00 | 4777.80 | 1126.30 | 0.00 | 0.00 | 133469.76 | 123947.10 | 9522.65 | 9000.00 | 1197.21 | 117968.11 | 393.23 |  |
| 2038 | 52 | ACC | 135219.60 | 39889.78 | 403.47 | 63389.33 | 19635.38 | 2124.92 | 0.00 | 268.98 | 0.00 | 0.00 | 0.00 | 4849.44 | 1154.45 | 0.00 | 0.00 | 141223.50 | 125711.86 | 15511.64 | 9000.00 | 1259.46 | 128227.57 | 427.43 |  |
| 2039 | 53 | ACC | 143332.78 | 42283.17 | 413.55 | 65291.01 | 20126.26 | 0.00 | 0.00 | 3584.13 | 0.00 | 0.00 | 0.00 | 2155.32 | 1183.31 | 0.00 | 0.00 | 146671.41 | 131698.12 | 14973.29 | 9000.00 | 1322.79 | 138550.36 | 461.83 |  |
| 2040 | 54 | ACC | 151932.75 | 44820.16 | 423.89 | 67249.74 | 40976.24 | 0.00 | 0.00 | 282.59 | 0.00 | 0.00 | 0.00 | 2187.60 | 1212.90 | 0.00 | 0.00 | 155333.24 | 153752.63 | 1580.62 | 9000.00 | 1387.20 | 148937.56 | 496.46 |  |
| 2041 | 55 | ACC | 161048.71 | 47509.37 | 434.49 | 69267.23 | 23752.09 | 0.00 | 0.00 | 289.66 | 0.00 | 0.00 | 0.00 | 2220.36 | 1243.22 | 0.00 | 0.00 | 164512.29 | 141252.84 | 23259.45 | 9000.00 | 1452.72 | 159390.27 | 531.30 |  |
| 2042 | 56 | ACC | 170711.63 | 50359.93 | 445.35 | 71345.25 | 15438.86 | 0.00 | 0.00 | 3859.71 | 0.00 | 0.00 | 0.00 | 0.00 | 1274.30 | 0.00 | 0.00 | 171985.93 | 141449.10 | 30536.83 | 9000.00 | 1519.36 | 169909.64 | 566.37 |  |
| 2043 | 57 | ACC | 180954.33 | 53381.53 | 456.49 | 73485.61 | 34084.25 | 0.00 | 0.00 | 304.32 | 0.00 | 0.00 | 0.00 | 0.00 | 1306.16 | 0.00 | 0.00 | 182260.49 | 161712.19 | 20548.30 | 9000.00 | 1587.15 | 180496.79 | 601.66 |  |
| 2044 | 58 | ACC | 191811.59 | 56584.42 | 467.90 | 75690.17 | 18715.90 | 0.00 | 0.00 | 311.93 | 0.00 | 0.00 | 0.00 | 0.00 | 1338.81 | 0.00 | 0.00 | 193150.40 | 151770.33 | 41380.07 | 9000.00 | 1656.11 | 191152.90 | 637.18 |  |
| 2045 | 59 | ACC | 203320.29 | 59979.48 | 479.60 | 77960.88 | 19183.80 | 0.00 | 0.00 | 4156.49 | 0.00 | 0.00 | 0.00 | 0.00 | 1372.28 | 0.00 | 0.00 | 204692.57 | 161760.25 | 42932.32 | 9000.00 | 1726.25 | 201879.14 | 672.93 |  |
| 2046 | 60 | ACC | 215519.50 | 63578.25 | 491.58 | 80299.71 | 9831.70 | 0.00 | 0.00 | 327.72 | 0.00 | 0.00 | 0.00 | 0.00 | 1406.59 | 0.00 | 0.00 | 216926.09 | 154528.97 | 62397.13 | 9000.00 | 1797.59 | 212676.73 | 708.92 |  |
| 2047 | 61 | ACC | 228450.67 | 67392.95 | 503.87 | 82708.70 | 10077.49 | 0.00 | 0.00 | 335.92 | 0.00 | 0.00 | 0.00 | 0.00 | 1441.75 | 0.00 | 0.00 | 229892.43 | 161018.93 | 68873.50 | 9000.00 | 1870.16 | 223546.89 | 745.16 |  |
| 2048 | 62 | ACC | 242157.71 | 71436.53 | 516.47 | 85189.96 | 10329.43 | 0.00 | 0.00 | 4476.09 | 0.00 | 0.00 | 0.00 | 0.00 | 1477.80 | 0.00 | 0.00 | 243635.51 | 171948.47 | 71687.04 | 9000.00 | 1943.98 | 234490.87 | 781.64 |  |
| 2049 | 63 | ACC | 256687.18 | 75722.72 | 529.38 | 87745.66 | 0.00 | 0.00 | 0.00 | 352.92 | 0.00 | 0.00 | 0.00 | 0.00 | 1514.74 | 0.00 | 0.00 | 258201.92 | 164350.68 | 93851.24 | 9000.00 | 2019.06 | 245509.93 | 818.37 |  |
| 2050 | 64 | ACC | 272088.41 | 80266.08 | 542.62 | 90378.03 | 0.00 | 0.00 | 0.00 | 361.75 | 0.00 | 0.00 | 0.00 | 0.00 | 1552.61 | 0.00 | 0.00 | 273641.02 | 171548.47 | 102092.55 | 9000.00 | 2095.44 | 256605.36 | 855.35 |  |
| 2051 | 65 | ACC | 288413.71 | 85082.05 | 556.18 | 93089.37 | 0.00 | 0.00 | 0.00 | 4820.25 | 0.00 | 0.00 | 0.00 | 0.00 | 1591.43 | 0.00 | 0.00 | 290005.14 | 183547.85 | 106457.29 | 9000.00 | 2173.12 | 267778.48 | 892.59 |  |
| 2052 | 66 | ACC | 305718.54 | 90186.97 | 570.09 | 95882.05 | 0.00 | 0.00 | 0.00 | 190.03 | 0.00 | 0.00 | 0.00 | 0.00 | 1631.21 | 0.00 | 0.00 | 307349.75 | 186829.13 | 120520.61 | 9000.00 | 2252.14 | 279030.63 | 930.10 |  |
| 2053 | 67 | ACC | 324061.65 | 95598.19 | 584.34 | 98758.51 | 0.00 | 0.00 | 0.00 | 194.78 | 0.00 | 0.00 | 0.00 | 0.00 | 1671.99 | 0.00 | 0.00 | 325733.64 | 195135.82 | 130597.82 | 9000.00 | 2332.52 | 290363.15 | 967.88 |  |
| 2054 | 68 | ACC | 343505.35 | 101334.08 | 598.95 | 101721.26 | 0.00 | 0.00 | 0.00 | 2595.44 | 0.00 | 0.00 | 0.00 | 0.00 | 1713.79 | 0.00 | 0.00 | 345219.14 | 206249.73 | 138969.40 | 9000.00 | 2414.28 | 301777.44 | 1005.92 |  |
| 2055 | 69 | ACC | 364115.67 | 107414.12 | 613.92 | 104772.90 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 1756.64 | 0.00 | 0.00 | 365872.30 | 212800.95 | 153071.36 | 9000.00 | 2497.45 | 313274.89 | 1044.25 |  |
| 2056 | 70 | RET | 0.00 | 0.00 | 0.00 | 107916.09 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 107916.09 | 0.00 | 0.00 | 5690.50 | 211049.30 | 703.50 |  |
| 2057 | 71 | RET | 0.00 | 0.00 | 0.00 | 111153.57 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 111153.57 | 0.00 | 0.00 | 3770.62 | 103666.35 | 345.55 |  |
| 2058 | 72 | RET | 0.00 | 0.00 | 0.00 | 114488.18 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 114488.18 | -9040.74 | 0.00 | 1781.09 | 0.00 | 0.00 |  |

#### Summary Statistics

| Statistic | Value |
|-----------|-------|
| Total years | 33 |
| Final wealth | 0.00 € |
| Final passive/month | 0.00 € |
| Total invested | 270000.00 € |
| Total returns | 53767.11 € |
| Goal reached? | NO |
| Wealth exhaustion age | 72 |
| Retirement monthly income | 0.00 € |
| Retirement monthly gap | -8993.01 € |

#### Wealth Milestones

| Threshold | Year | Age |
|-----------|------|-----|
| 100k€ | 2036 | 50 |
| 250k€ | 2050 | 64 |

#### Insights & Recommendations

| # | ID | Category | Severity | Title | Impact (€) | Action |
|---|----|----------|----------|-------|------------|--------|
| 1 | wealth_exhaustion | savings | critical | Patrimoine épuisé à 72 ans | -333557.84 | Augmentez votre épargne mensuelle de 712€ |
| 2 | negative_net | expenses | critical | Dépenses > revenus en 2026 | -50000.00 | Vérifiez vos charges et votre CA prévisionnel |
| 3 | savings_allocation_unbalanced | allocation | warning | Épargne trop prudente | 30000.00 | Redirigez une partie vers PEA ou AV unités de compte |
| 4 | no_goal_reached | savings | warning | Objectif non atteint | 0.00 | Augmentez l'épargne ou ajoutez des projets de revenus |
| 5 | one_more_year | income | opportunity | Une année de plus ferait la différence | 11497.45 | Envisagez de repousser votre âge de retraite d'un an |

**Insight #1: Patrimoine épuisé à 72 ans** (critical)
- **Rule**: `wealth_exhaustion`
- **Description**: Votre épargne ne couvre que 2 ans de retraite. Pour tenir jusqu'à 95 ans, épargnez 712€/mois de plus.
- **Impact on wealth**: -333557.84 €
- **Action**: Augmentez votre épargne mensuelle de 712€

**Insight #2: Dépenses > revenus en 2026** (critical)
- **Rule**: `negative_net`
- **Description**: Vos dépenses dépassent vos revenus en 2026 (âge 40 ans). Votre épargne fond au lieu de croître.
- **Impact on wealth**: -50000.00 €
- **Action**: Vérifiez vos charges et votre CA prévisionnel

**Insight #3: Épargne trop prudente** (warning)
- **Rule**: `savings_allocation_unbalanced`
- **Description**: Plus de 80% de vos versements sont sur des supports à faible rendement (Livret A, LDDS, fonds euros). Diversifier vers AV UC ou PEA augmenterait votre patrimoine final.
- **Impact on wealth**: 30000.00 €
- **Action**: Redirigez une partie vers PEA ou AV unités de compte

**Insight #4: Objectif non atteint** (warning)
- **Rule**: `no_goal_reached`
- **Description**: Votre objectif de revenu n'est pas atteint à la retraite. Actuellement 0€/mois de passif projeté.
- **Impact on wealth**: 0.00 €
- **Action**: Augmentez l'épargne ou ajoutez des projets de revenus

**Insight #5: Une année de plus ferait la différence** (opportunity)
- **Rule**: `one_more_year`
- **Description**: Repousser la retraite d'un an ajouterait environ 11 497€ à votre patrimoine tout en réduisant la durée de retrait.
- **Impact on wealth**: 11497.45 €
- **Action**: Envisagez de repousser votre âge de retraite d'un an

#### Readiness Score

- **Score**: 15/100
- **Band**: Fragile (rose)
- **Summary**: Votre situation est fragile. Concentrez-vous sur la constitution d'un fonds d'urgence et l'augmentation de votre épargne.

| Component | Score | Weight |
|-----------|-------|--------|
| goal_coverage | 0 | 30% |
| wealth_durability | 0 | 25% |
| savings_rate | 0 | 15% |
| diversification | 50 | 10% |
| growth_trajectory | 100 | 10% |
| buffer_adequacy | 0 | 10% |

---

### C.3 Scale: **pessimistic**

- **Inflation rate**: 3.5% / year
- **Cost of living rate**: 4.5% / year
- **Years projected**: 32
- **Projection range**: 2026 (age 40) → 2057 (age 71)

#### Timeline (Year-by-Year)

| Year | Age | Phase | Gross Annual | Charges | CFE | Base Exp | Kid Exp | Pet Exp | Car Exp | Tech Exp | Rec Exp | Proj Exp | Proj Inc | CAF | Tax Credits | Status Bonus | Pension | Total Income | Total Outgoing | Net Annual | Year Invested | Year Returns | Total Wealth | Passive/mo | Goal? |
|------|-----|-------|-------------|---------|-----|----------|---------|---------|---------|----------|---------|----------|----------|-----|-------------|-------------|---------|-------------|----------------|------------|--------------|-------------|-------------|-----------|-------|
| 2026 | 40 | ACC | 67200.00 | 17606.40 | 300.00 | 44460.00 | 11200.00 | 1180.00 | 0.00 | 300.00 | 0.00 | 0.00 | 0.00 | 4056.00 | 858.40 | 0.00 | 0.00 | 72114.40 | 75046.40 | -2932.00 | 9000.00 | 16.28 | 9766.28 | 32.55 |  |
| 2027 | 41 | ACC | 71232.00 | 19090.18 | 310.50 | 46460.70 | 11592.00 | 1221.30 | 0.00 | 2794.50 | 0.00 | 0.00 | 0.00 | 4116.84 | 888.44 | 0.00 | 0.00 | 76237.28 | 81469.18 | -5231.89 | 9000.00 | 211.98 | 18978.26 | 63.26 |  |
| 2028 | 42 | ACC | 75505.92 | 20764.13 | 321.37 | 48551.43 | 9855.27 | 1264.05 | 0.00 | 214.24 | 0.00 | 20000.00 | 0.00 | 4178.64 | 919.54 | 0.00 | 0.00 | 80604.10 | 100970.49 | -20366.39 | 9000.00 | 412.13 | 28390.38 | 94.63 |  |
| 2029 | 43 | ACC | 80036.28 | 22009.98 | 332.62 | 50736.25 | 12639.38 | 1308.29 | 0.00 | 221.74 | 0.00 | 0.00 | 0.00 | 4241.28 | 951.72 | 0.00 | 0.00 | 85229.28 | 87248.25 | -2018.97 | 9000.00 | 616.82 | 38007.21 | 126.69 |  |
| 2030 | 44 | ACC | 84838.45 | 24178.96 | 344.26 | 53019.38 | 10786.72 | 1354.08 | 0.00 | 2983.56 | 0.00 | 10000.00 | 0.00 | 4304.88 | 985.03 | 0.00 | 0.00 | 90128.37 | 102666.95 | -12538.58 | 9000.00 | 763.25 | 47770.45 | 159.23 |  |
| 2031 | 45 | ACC | 89928.76 | 25629.70 | 356.31 | 55405.25 | 14489.77 | 1401.47 | 0.00 | 237.54 | 0.00 | 0.00 | 0.00 | 4369.44 | 1019.51 | 0.00 | 0.00 | 95317.71 | 97520.03 | -2202.32 | 9000.00 | 811.44 | 57581.89 | 191.94 |  |
| 2032 | 46 | ACC | 95324.48 | 27167.48 | 368.78 | 57898.49 | 14996.91 | 1450.52 | 0.00 | 245.85 | 0.00 | 0.00 | 0.00 | 4434.96 | 1055.19 | 0.00 | 0.00 | 100814.64 | 102128.03 | -1313.39 | 9000.00 | 860.37 | 67442.26 | 224.81 |  |
| 2033 | 47 | ACC | 101043.95 | 28797.53 | 381.68 | 60503.92 | 21374.29 | 1501.29 | 0.00 | 3307.93 | 0.00 | 0.00 | 0.00 | 4501.56 | 1092.12 | 0.00 | 0.00 | 106637.64 | 115866.63 | -9229.00 | 9000.00 | 910.03 | 77352.29 | 257.84 |  |
| 2034 | 48 | ACC | 107106.59 | 30525.38 | 395.04 | 63226.59 | 16591.79 | 1553.83 | 0.00 | 263.36 | 0.00 | 0.00 | 0.00 | 4569.00 | 1130.35 | 0.00 | 0.00 | 112805.94 | 112556.00 | 249.93 | 9000.00 | 960.44 | 87312.73 | 291.04 |  |
| 2035 | 49 | ACC | 113532.99 | 33492.23 | 408.87 | 66071.79 | 17172.51 | 2153.38 | 0.00 | 272.58 | 0.00 | 0.00 | 0.00 | 4637.64 | 1169.91 | 0.00 | 0.00 | 119340.54 | 119571.35 | -230.82 | 9000.00 | 1011.62 | 97324.35 | 324.41 |  |
| 2036 | 50 | ACC | 120344.97 | 35501.76 | 423.18 | 69045.02 | 37804.05 | 2228.75 | 0.00 | 3667.56 | 0.00 | 0.00 | 0.00 | 4707.12 | 1210.86 | 0.00 | 0.00 | 126262.94 | 148670.31 | -22407.37 | 9000.00 | 1063.57 | 107387.93 | 357.96 |  |
| 2037 | 51 | ACC | 127565.66 | 37631.87 | 437.99 | 72152.05 | 24527.49 | 2306.75 | 0.00 | 291.99 | 0.00 | 0.00 | 0.00 | 4777.80 | 1253.24 | 0.00 | 0.00 | 133596.70 | 137348.15 | -3751.44 | 9000.00 | 1116.31 | 117504.23 | 391.68 |  |
| 2038 | 52 | ACC | 135219.60 | 39889.78 | 453.32 | 75398.89 | 22061.60 | 2387.49 | 0.00 | 302.21 | 0.00 | 0.00 | 0.00 | 4849.44 | 1297.10 | 0.00 | 0.00 | 141366.14 | 140493.30 | 872.85 | 9000.00 | 1169.84 | 127674.07 | 425.58 |  |
| 2039 | 53 | ACC | 143332.78 | 42283.17 | 469.19 | 78791.84 | 22833.76 | 0.00 | 0.00 | 4066.29 | 0.00 | 0.00 | 0.00 | 2155.32 | 1342.50 | 0.00 | 0.00 | 146830.60 | 148444.24 | -1613.64 | 9000.00 | 1224.18 | 137898.25 | 459.66 |  |
| 2040 | 54 | ACC | 151932.75 | 44820.16 | 485.61 | 82337.47 | 46942.14 | 0.00 | 0.00 | 323.74 | 0.00 | 0.00 | 0.00 | 2187.60 | 1389.49 | 0.00 | 0.00 | 155509.83 | 174909.12 | -19399.29 | 9000.00 | 1279.34 | 148177.59 | 493.93 |  |
| 2041 | 55 | ACC | 161048.71 | 47509.37 | 502.60 | 86042.66 | 27475.72 | 0.00 | 0.00 | 335.07 | 0.00 | 0.00 | 0.00 | 2220.36 | 1438.12 | 0.00 | 0.00 | 164707.19 | 161865.42 | 2841.77 | 9000.00 | 1335.33 | 158512.92 | 528.38 |  |
| 2042 | 56 | ACC | 170711.63 | 50359.93 | 520.20 | 89914.58 | 18033.45 | 0.00 | 0.00 | 4508.36 | 0.00 | 0.00 | 0.00 | 0.00 | 1488.45 | 0.00 | 0.00 | 172200.09 | 163336.52 | 8863.56 | 9000.00 | 1392.18 | 168905.10 | 563.02 |  |
| 2043 | 57 | ACC | 180954.33 | 53381.53 | 538.40 | 93960.73 | 40200.73 | 0.00 | 0.00 | 358.94 | 0.00 | 0.00 | 0.00 | 0.00 | 1540.55 | 0.00 | 0.00 | 182494.88 | 188440.33 | -5945.45 | 9000.00 | 1449.88 | 179354.97 | 597.85 |  |
| 2044 | 58 | ACC | 191811.59 | 56584.42 | 557.25 | 98188.97 | 22289.87 | 0.00 | 0.00 | 371.50 | 0.00 | 0.00 | 0.00 | 0.00 | 1594.47 | 0.00 | 0.00 | 193406.06 | 177992.00 | 15414.06 | 9000.00 | 1508.45 | 189863.42 | 632.88 |  |
| 2045 | 59 | ACC | 203320.29 | 59979.48 | 576.75 | 102607.47 | 23070.02 | 0.00 | 0.00 | 4998.50 | 0.00 | 0.00 | 0.00 | 0.00 | 1650.28 | 0.00 | 0.00 | 204970.56 | 191232.22 | 13738.34 | 9000.00 | 1567.91 | 200431.32 | 668.10 |  |
| 2046 | 60 | ACC | 215519.50 | 63578.25 | 596.94 | 107224.81 | 11938.73 | 0.00 | 0.00 | 397.96 | 0.00 | 0.00 | 0.00 | 0.00 | 1708.03 | 0.00 | 0.00 | 217227.54 | 183736.69 | 33490.85 | 9000.00 | 1628.26 | 211059.59 | 703.53 |  |
| 2047 | 61 | ACC | 228450.67 | 67392.95 | 617.83 | 112049.92 | 12356.59 | 0.00 | 0.00 | 411.89 | 0.00 | 0.00 | 0.00 | 0.00 | 1767.82 | 0.00 | 0.00 | 230218.49 | 192829.18 | 37389.31 | 9000.00 | 1689.53 | 221749.11 | 739.16 |  |
| 2048 | 62 | ACC | 242157.71 | 71436.53 | 639.45 | 117092.17 | 12789.07 | 0.00 | 0.00 | 5541.93 | 0.00 | 0.00 | 0.00 | 0.00 | 1829.69 | 0.00 | 0.00 | 243987.40 | 207499.15 | 36488.26 | 9000.00 | 1751.72 | 232500.84 | 775.00 |  |
| 2049 | 63 | ACC | 256687.18 | 75722.72 | 661.83 | 122361.32 | 0.00 | 0.00 | 0.00 | 441.22 | 0.00 | 0.00 | 0.00 | 0.00 | 1893.73 | 0.00 | 0.00 | 258580.91 | 199187.09 | 59393.82 | 9000.00 | 1814.86 | 243315.69 | 811.05 |  |
| 2050 | 64 | ACC | 272088.41 | 80266.08 | 685.00 | 127867.58 | 0.00 | 0.00 | 0.00 | 456.67 | 0.00 | 0.00 | 0.00 | 0.00 | 1960.01 | 0.00 | 0.00 | 274048.42 | 209275.32 | 64773.10 | 9000.00 | 1878.94 | 254194.63 | 847.32 |  |
| 2051 | 65 | ACC | 288413.71 | 85082.05 | 708.97 | 133621.62 | 0.00 | 0.00 | 0.00 | 6144.44 | 0.00 | 0.00 | 0.00 | 0.00 | 2028.61 | 0.00 | 0.00 | 290442.32 | 225557.07 | 64885.25 | 9000.00 | 1944.00 | 265138.63 | 883.80 |  |
| 2052 | 66 | ACC | 305718.54 | 90186.97 | 733.79 | 139634.59 | 0.00 | 0.00 | 0.00 | 244.60 | 0.00 | 0.00 | 0.00 | 0.00 | 2099.61 | 0.00 | 0.00 | 307818.15 | 230799.94 | 77018.21 | 9000.00 | 2010.04 | 276148.67 | 920.50 |  |
| 2053 | 67 | ACC | 324061.65 | 95598.19 | 759.47 | 145918.15 | 0.00 | 0.00 | 0.00 | 253.16 | 0.00 | 0.00 | 0.00 | 0.00 | 2173.10 | 0.00 | 0.00 | 326234.74 | 242528.96 | 83705.79 | 9000.00 | 2077.07 | 287225.74 | 957.42 |  |
| 2054 | 68 | ACC | 343505.35 | 101334.08 | 786.05 | 152484.46 | 0.00 | 0.00 | 0.00 | 3406.22 | 0.00 | 0.00 | 0.00 | 0.00 | 2249.16 | 0.00 | 0.00 | 345754.50 | 258010.81 | 87743.69 | 9000.00 | 2145.12 | 298370.87 | 994.57 |  |
| 2055 | 69 | ACC | 364115.67 | 107414.12 | 813.56 | 159346.26 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 2327.88 | 0.00 | 0.00 | 366443.54 | 267573.95 | 98869.60 | 9000.00 | 2214.20 | 309585.07 | 1031.95 |  |
| 2056 | 70 | RET | 0.00 | 0.00 | 0.00 | 166516.84 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 166516.84 | 0.00 | 0.00 | 4901.82 | 147970.05 | 493.23 |  |
| 2057 | 71 | RET | 0.00 | 0.00 | 0.00 | 174010.10 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 174010.10 | -23766.42 | 0.00 | 2273.63 | 0.00 | 0.00 |  |

#### Summary Statistics

| Statistic | Value |
|-----------|-------|
| Total years | 32 |
| Final wealth | 0.00 € |
| Final passive/month | 0.00 € |
| Total invested | 270000.00 € |
| Total returns | 46010.54 € |
| Goal reached? | NO |
| Wealth exhaustion age | 71 |
| Retirement monthly income | 0.00 € |
| Retirement monthly gap | -13876.40 € |

#### Wealth Milestones

| Threshold | Year | Age |
|-----------|------|-----|
| 100k€ | 2036 | 50 |
| 250k€ | 2050 | 64 |

#### Insights & Recommendations

| # | ID | Category | Severity | Title | Impact (€) | Action |
|---|----|----------|----------|-------|------------|--------|
| 1 | wealth_exhaustion | savings | critical | Patrimoine épuisé à 71 ans | -340526.94 | Augmentez votre épargne mensuelle de 727€ |
| 2 | negative_net | expenses | critical | Dépenses > revenus en 2026 | -50000.00 | Vérifiez vos charges et votre CA prévisionnel |
| 3 | savings_allocation_unbalanced | allocation | warning | Épargne trop prudente | 30000.00 | Redirigez une partie vers PEA ou AV unités de compte |
| 4 | no_goal_reached | savings | warning | Objectif non atteint | 0.00 | Augmentez l'épargne ou ajoutez des projets de revenus |
| 5 | one_more_year | income | opportunity | Une année de plus ferait la différence | 11214.20 | Envisagez de repousser votre âge de retraite d'un an |

**Insight #1: Patrimoine épuisé à 71 ans** (critical)
- **Rule**: `wealth_exhaustion`
- **Description**: Votre épargne ne couvre que 1 ans de retraite. Pour tenir jusqu'à 95 ans, épargnez 727€/mois de plus.
- **Impact on wealth**: -340526.94 €
- **Action**: Augmentez votre épargne mensuelle de 727€

**Insight #2: Dépenses > revenus en 2026** (critical)
- **Rule**: `negative_net`
- **Description**: Vos dépenses dépassent vos revenus en 2026 (âge 40 ans). Votre épargne fond au lieu de croître.
- **Impact on wealth**: -50000.00 €
- **Action**: Vérifiez vos charges et votre CA prévisionnel

**Insight #3: Épargne trop prudente** (warning)
- **Rule**: `savings_allocation_unbalanced`
- **Description**: Plus de 80% de vos versements sont sur des supports à faible rendement (Livret A, LDDS, fonds euros). Diversifier vers AV UC ou PEA augmenterait votre patrimoine final.
- **Impact on wealth**: 30000.00 €
- **Action**: Redirigez une partie vers PEA ou AV unités de compte

**Insight #4: Objectif non atteint** (warning)
- **Rule**: `no_goal_reached`
- **Description**: Votre objectif de revenu n'est pas atteint à la retraite. Actuellement 0€/mois de passif projeté.
- **Impact on wealth**: 0.00 €
- **Action**: Augmentez l'épargne ou ajoutez des projets de revenus

**Insight #5: Une année de plus ferait la différence** (opportunity)
- **Rule**: `one_more_year`
- **Description**: Repousser la retraite d'un an ajouterait environ 11 214€ à votre patrimoine tout en réduisant la durée de retrait.
- **Impact on wealth**: 11214.20 €
- **Action**: Envisagez de repousser votre âge de retraite d'un an

#### Readiness Score

- **Score**: 15/100
- **Band**: Fragile (rose)
- **Summary**: Votre situation est fragile. Concentrez-vous sur la constitution d'un fonds d'urgence et l'augmentation de votre épargne.

| Component | Score | Weight |
|-----------|-------|--------|
| goal_coverage | 0 | 30% |
| wealth_durability | 0 | 25% |
| savings_rate | 0 | 15% |
| diversification | 50 | 10% |
| growth_trajectory | 100 | 10% |
| buffer_adequacy | 0 | 10% |

---

## Section D: Cross-Scale Comparison

| Metric | Optimistic | Moderate | Pessimistic |
|--------|-----------|----------|-------------|
| Final Wealth (€) | 0.00 | 0.00 | 0.00 |
| Final Passive/mo (€) | 0.00 | 0.00 | 0.00 |
| Total Invested (€) | 270000.00 | 270000.00 | 270000.00 |
| Total Returns (€) | 60868.68 | 53767.11 | 46010.54 |
| Ret. Monthly Income (€) | 0.00 | 0.00 | 0.00 |
| Ret. Monthly Gap (€) | -6711.10 | -8993.01 | -13876.40 |
| | | | |
| Goal reached? | NO | NO | NO |
| Wealth exhaustion? | 73 | 72 | 71 |
| Readiness Score | 15 (Fragile) | 15 (Fragile) | 15 (Fragile) |

## Section E: 'Vie' Tab Audit — What's Included and What's Not

### E.1 Kids (3 active)

- **Romy** (born 2025-04-03): Entity age 1 at start, retires at entity age 31. All cost events from age 0-23. Partially (last cost event ends at entity age 23)
- **Ellie** (born 2021-07-02): Entity age 4 at start, retires at entity age 34. All cost events from age 0-23. Partially (last cost event ends at entity age 23)
- **Saoirse** (born 2018-03-25): Entity age 8 at start, retires at entity age 38. All cost events from age 0-23. Partially (last cost event ends at entity age 23)

### E.2 Cars (2 active — BOTH EXPIRED)

⚠️ **CRITICAL FINDING**: Both cars have cost events capped at `to_age: 8`.
The Xsara (acquired 2010) is age 16 at projection start. 
The Peugeot (acquired 2006) is age 19 at projection start. 
**Zero car expenses appear in ANY projection year.**
No replacement cycle is triggered because the existing cars already exceeded their replace cycle.
The `replace_cost` metadata (18000€) is NEVER used — it's metadata only, the engine uses `cost_events`.

- **Xsara (2010)**: age 15 at start, all cost events end at age 8 → **$0 contribution**
- **Peugeot (2006)**: age 19 at start, all cost events end at age 8 → **$0 contribution**

### E.3 Tech (2 active)

- **Macbook Air (2021)**: age 5 at start. Annual accessories + replacements every 3 years up to entity age 30. Active throughout projection.
- **Macbook Air (2024)**: age 2 at start. Annual accessories + replacements every 3 years up to entity age 30. Active throughout projection.

### E.4 Pet (1 active)

- **Layla**: age 1 at start. Cost events up to age 13. Active until entity age 13 (projection year ~12 from now).

### E.5 Recurring Expenses

**None configured.** No Vie-tab recurring expenses (loans, subscriptions, etc.) appear in any projection.

---
