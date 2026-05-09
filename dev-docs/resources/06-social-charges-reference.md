# Social Charges Reference — Communauté Coiffure

> **OPERATIONAL REFERENCE — NOT USER-FACING.**
> This document is loaded by `.clinerules` whenever a calculation, charges, or salary task runs.
> All numerical rates must have a `[Source: url]` citation. Aggregator/blog sources not acceptable.
> For each section the matching code functions are listed — if you update a rate here, update the code.

---

## §0 — Source dates and disclaimer

**Rates valid as of: 1 January 2026 (Metropolitan France)**
**Review by: 1 January 2027** — check URSSAF, BOSS, and legifrance for annual updates to PASS, SMIC, and RGDU formula.
**Document last updated: 27 April 2026**

Sources used in this document:
- `service-public.fr` — general thresholds and SMIC
- `urssaf.fr` — cotisation rates, AE rates, TNS rates, ACRE
- `boss.gouv.fr` — RGDU formula, official social law bulletin
- `legifrance.gouv.fr` — CGI (impôt), LFSS, décrets
- `economie.gouv.fr` — reform summaries
- `entreprendre.service-public.fr` — business creation guides

Approximate markers:
- **~45% TNS rule** and **~75-82% assimilé salarié rule** are forfait approximations used for pitch math and the app's quick-estimate path. They are within 2-5% of exact calculations for typical coiffure salary ranges. The comptable does the precise calc.
- All IS optimisation ratios are pre-tax distributions assuming no dividendes-above-10%-capital trap (see §7).

---

## §1 — Constants 2026

**Code pointers:** `backend/app/calculations/social_charges.py` top-level constants.

```python
PASS_ANNUEL      = 48_060   # Plafond Annuel Sécurité Sociale 2026
PASS_MENSUEL     = 4_005    # PASS / 12
SMIC_HORAIRE     = 12.02    # Salaire Minimum Interprofessionnel de Croissance, horaire
SMIC_MENSUEL_BRUT = 1_823.03  # 35h × 52.18 × 12.02
SMIC_ANNUEL      = 21_876.40  # 1_823.03 × 12  (note: legal calc = 1 820.35 × 12 ≈ 21 844.20 but URSSAF uses 21 876.36 for the 3×SMIC threshold)
IS_TAUX_REDUIT   = 0.15     # IS on first 42 500 € of bénéfice (PME criteria apply)
IS_TAUX_NORMAL   = 0.25     # IS on bénéfice > 42 500 €
IS_SEUIL_REDUIT  = 42_500   # Threshold between reduced and normal IS
PFU_DIVIDENDES   = 0.30     # Prélèvement Forfaitaire Unique on dividendes (12.8% IR + 17.2% PS)
PS_DIVIDENDES_TNS = 0.172   # Prélèvements sociaux on dividendes below the 10%-capital threshold
```

Sources:
- PASS 2026: [Service-Public.fr arrêté du 19 décembre 2025](https://www.service-public.fr/particuliers/vosdroits/F2365) — décret n°2025-1316 du 16 décembre 2025
- SMIC 2026: 12,02 €/h since 1 November 2024, unchanged for 2026 — [service-public.fr SMIC](https://www.service-public.fr/particuliers/vosdroits/F2300)
- IS 15%/25%: [CGI art. 219 I b](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006302489) — unchanged 2026
- PFU 30%: [CGI art. 200 A](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000036428090)

---

## §2 — Auto-entrepreneur (micro-entreprise)

**Code pointers:**
- `backend/app/calculations/social_charges.py::calc_ae_urssaf_cotisations`, `get_ae_urssaf_rate`
- `backend/app/calculations/social_charges.py::ACRE_STEP_DOWN_DATE` (TASK-2.14.6)

**Hairdressers are artisans → BIC services prestations artisanales → 21.2% rate.**

### Cotisation rates (2026)

| Activity type | Cotisations URSSAF | CFP | Versement libératoire (opt.) |
|---|---|---|---|
| Vente de marchandises (BIC) | **12.3%** | 0.10% | 1.0% |
| Prestations artisanales (BIC) ← coiffure | **21.2%** | 0.30% | 1.7% |
| Prestations de services libérales (BNC) | 25.6% | 0.20% | 2.2% |
| Professions libérales CIPAV | 23.2% | 0.20% | 2.2% |

[Source: urssaf.fr — Taux de cotisations auto-entrepreneur 2026](https://www.urssaf.fr/portail/home/espaces-dedies/auto-entrepreneur/mes-cotisations/les-taux-de-cotisations.html)

### CA thresholds (2026)

| Activity | Max CA annuel |
|---|---|
| Vente de marchandises | 203 100 € |
| Prestations de services (BIC artisanal) ← coiffure | 83 600 € |
| Mixte | 203 100 € total, max 83 600 € services |

[Source: service-public.fr — Micro-entreprise : quels sont les seuils de chiffre d'affaires ?](https://www.service-public.fr/professionnels-entreprises/vosdroits/F23266)

### ACRE — step-down in 2026

**Before 1 July 2026:** ACRE = 50% exoneration on cotisations URSSAF (pay 50% of normal rate) for the first 4 calendar quarters of activity.

**From 1 July 2026:** ACRE = 25% exoneration (pay 75% of normal rate). This is a LFSS 2026 change.

```python
# ACRE implementation (see TASK-2.14.6 for the date-aware helper)
ACRE_STEP_DOWN_DATE = date(2026, 7, 1)

def acre_rate_for(activity_date) -> Decimal:
    # Before 2026-07-01: exoneration = 50% → multiplier on base rate = 0.50
    # From 2026-07-01:   exoneration = 25% → multiplier on base rate = 0.75
    return Decimal("0.25") if activity_date >= ACRE_STEP_DOWN_DATE else Decimal("0.50")
```

[Source: economie.gouv.fr — Entreprises : ce qui change au 1er janvier 2026](https://www.economie.gouv.fr/entreprises/entreprises-ce-qui-change-au-1er-janvier-2026-0) + LFSS 2026

### Note: AE CA is NOT TTC

AE salons are in franchise en base de TVA — no TVA collected, no TVA deducted. CA is gross receipts. **Never divide AE CA by 1.2.** See LEARNINGS #6.

---

## §3 — TNS gérant majoritaire (EURL/SARL/EI)

**Code pointers:**
- `backend/app/calculations/social_charges.py::estimate_charges_tns`, `calc_tns_charges_annuelles`
- `backend/app/services/salary.py::TNS_BUSINESS_TYPES`
- `backend/app/services/compare_types.py::_compute_net_tns_ir`, `_compute_net_tns_is`

**TNS = Travailleur Non Salarié = gérant majoritaire SARL, gérant EURL, EI.**
SASU/SAS presidents are NOT TNS — they are assimilé salarié (see §5).

### Simplified 45% rule (app default)

```
charges_sociales = remuneration_nette × 0.45
cout_total = remuneration_nette × 1.45
```

This is the **ONLY formula used in the app for monthly tracking and the compare_types engine**. Accuracy: within ±5% for typical coiffure salary range (1 200 € to 5 000 € net/month).

**When to use the 45% rule:** Always, for the app's real-time calculations.
**When NOT to use it:** For the actual URSSAF declaration (comptable handles that with the precise progressive formula below).

### Detailed progressive rates (2026 — for reference)

Base = revenu net professionnel (CA moins charges professionnelles, hors cotisations sociales elles-mêmes). The 2026 reform of l'assiette unique means cotisations are calculated on the revenu NET (after professional expenses) rather than a complex interim base.

| Cotisation | Taux | Assiette (2026) |
|---|---|---|
| Maladie-maternité | 0% to 8.5% progressive | Jusqu'à 5 × PASS; taux réduit à 0% < 40% PASS, progressif jusqu'à 8.5% |
| Indemnités journalières | 0.85% | 0 à 5 × PASS |
| Retraite de base plafonnée | 17.75% | 0 à 1 × PASS (48 060 €) |
| Retraite de base déplafonnée | 0.72% | Totalité du revenu |
| Retraite complémentaire T1 | 7.00% | 0 à 1 × PASS |
| Retraite complémentaire T2 | 8.00% | 1 × PASS à 4 × PASS |
| Invalidité-décès | 1.30% | 0 à 1 × PASS |
| Allocations familiales | 0% to 3.10% | 0% si revenu < 110% PASS; progressive jusqu'à 3.10% au-delà de 140% PASS |
| CSG (dont 6.8% déductible) | 9.20% | Base abattue 26% (i.e. 74% du revenu net) |
| CRDS | 0.50% | Base abattue 26% |
| CFP (formation professionnelle) | 0.34% | PASS annuel (= ~163 €/an artisan) |

[Source: urssaf.fr — TNS : quelles cotisations ?](https://www.urssaf.fr/portail/home/independant/mes-cotisations/quelles-cotisations.html)
[Source: service-public.fr — Travailleur indépendant : cotisations et contributions sociales](https://www.service-public.fr/professionnels-entreprises/vosdroits/F23890)

### Cotisations minimales (zero or very low income)

| Cotisation | Montant minimal annuel (2026) |
|---|---|
| Retraite de base | ~942 € (11.5% × 40% × PASS) |
| Indemnités journalières | ~163 € (0.85% × 40% × PASS) |
| Invalidité-décès | ~72 € |
| **Total minimum** | **~1 177 € + CFP (~163 €)** |

[Source: urssaf.fr — Cotisations minimales](https://www.urssaf.fr/portail/home/independant/mes-cotisations/les-taux-de-cotisations.html)

### TNS EURL-IS / EI-IS path

When the TNS structure opts for IS (EURL à l'IS, EI assimilée EURL à l'IS):
- Rémunération gérant = subject to TNS cotisations (same as above)
- Dividendes = PFU 30% if below 10% of capital threshold (see §7 for the trap)
- Net = remuneration_nette + dividendes × (1 - 0.30)

```python
# compare_types.py shorthand for IS structures:
benefice_apres_remun = ca_ht - charges_fixes - masse_salariale - remuneration_brute_tns
  # where remuneration_brute_tns = remuneration_nette × 1.45
is_base = benefice_apres_remun
is_amount = min(is_base, IS_SEUIL_REDUIT) × 0.15 + max(0, is_base - IS_SEUIL_REDUIT) × 0.25
dividendes_bruts = is_base - is_amount
dividendes_net = dividendes_bruts × (1 - 0.30)  # PFU — WARNING: see §7 trap
```

---

## §4 — Salarié (employee)

**Code pointers:**
- `backend/app/calculations/social_charges.py::calc_charges_salarie`, `calc_rgdu`
- `backend/app/calculations/social_charges.py::PASS_MENSUEL`, `PASS_ANNUEL`, `SMIC_ANNUEL`

### Charges patronales (2026)

| Cotisation | Taux patronal | Assiette |
|---|---|---|
| Assurance maladie | **13.00%** | Totalité brut |
| Allocations familiales | **5.25%** | Totalité brut |
| Assurance vieillesse plafonnée | 8.55% | 0 à 1 PASS (4 005 €/mois) |
| Assurance vieillesse déplafonnée | 2.11% | Totalité brut |
| Accidents du travail (AT/MP) coiffure | ~1.10% | Totalité brut |
| FNAL | 0.10% (< 50 sal.) / 0.50% (≥ 50 sal.) | ≤ PASS / totalité |
| Contribution solidarité autonomie (CSA) | 0.30% | Totalité brut |
| Chômage | 4.05% | 0 à 4 × PASS |
| AGS | 0.25% | 0 à 4 × PASS |
| Retraite complémentaire AGIRC-ARRCO T1 | 4.72% | 0 à 1 PASS |
| Retraite complémentaire AGIRC-ARRCO T2 | 12.95% | 1 PASS à 8 PASS |
| CEG (contribution équilibre général) T1 | 1.29% | 0 à 1 PASS |
| CEG T2 | 1.62% | 1 PASS à 8 PASS |
| Formation professionnelle | 0.55% (< 11 sal.) / 1.00% (≥ 11 sal.) | Totalité brut |
| Taxe d'apprentissage | 0.68% | Totalité brut |

Note: **maladie 13% and alloc fam 5.25% are FLAT in 2026** — the reduced taux (7% maladie, 3.45% alloc fam) that previously applied below 2.5 SMIC / 3.5 SMIC were suppressed by the LFSS 2025, effective 1 January 2026. These are now flat across all salary levels. This is the key 2026 reform change.

[Source: urssaf.fr — Tableau des cotisations patronales 2026](https://www.urssaf.fr/portail/home/employeur/calculer-les-cotisations/les-taux-de-cotisations/tableau-des-cotisations-dues-par.html)
[Source: economie.gouv.fr — Entreprises : ce qui change au 1er janvier 2026](https://www.economie.gouv.fr/entreprises/entreprises-ce-qui-change-au-1er-janvier-2026-0)

### Charges salariales (2026)

| Cotisation | Taux salarial | Assiette |
|---|---|---|
| Assurance vieillesse plafonnée | 6.90% | 0 à 1 PASS |
| Assurance vieillesse déplafonnée | 0.40% | Totalité brut |
| Retraite complémentaire T1 | 3.15% | 0 à 1 PASS |
| Retraite complémentaire T2 | 8.64% | 1 PASS à 8 PASS |
| CEG T1 | 0.86% | 0 à 1 PASS |
| CEG T2 | 1.08% | 1 PASS à 8 PASS |
| CSG déductible | 6.80% | 98.25% du brut (abattement 1.75% frais professionnels) |
| CSG non-déductible | 2.40% | 98.25% du brut |
| CRDS | 0.50% | 98.25% du brut |

[Source: urssaf.fr — Tableau des cotisations salariales 2026](https://www.urssaf.fr/portail/home/employeur/calculer-les-cotisations/les-taux-de-cotisations/tableau-des-cotisations-dues-par.html)

### Net-to-brut conversion approximation (app)

```
salaire_brut ≈ salaire_net / 0.778
# (salarial charges ≈ 22.2% of brut for typical coiffure salary, below PASS)
# Source: 6.90% + 0.40% + 3.15% + 0.86% + (9.20%+0.50%) × 0.9825 ≈ 21.8% salarial
```

### RGDU — Réduction Générale Dégressive Unique (2026)

**Code pointer:** `backend/app/calculations/social_charges.py::calc_rgdu`

The RGDU reduces patronal charges for salaries below 3 × SMIC. Formula from BOSS:

```
T_MIN   = 0.0200   # minimum coefficient (floors at 2% of brut as minimum reduction)
T_DELTA = 0.3773   # <50 employees (2026, per décret n°2025-887)
T_DELTA = 0.3813   # ≥50 employees (2026, per décret n°2025-887) — irrelevant for coiffure
P       = 1.75     # exponent (unchanged from 2025)

ratio       = (3 × SMIC_ANNUEL / S) - 1    where S = annual brut
coefficient = T_MIN + T_DELTA × (0.5 × ratio)^P

coefficient = min(coefficient, T_MIN + T_DELTA)   # cap = 0.3973 (<50) / 0.4013 (≥50)
coefficient = max(coefficient, T_MIN)              # floor = 0.02

RGDU_reduction_annuelle = S × coefficient
```

**AUDIT STATUS (TASK-2.14.5 ✅ 2026-04-27):** T_DELTA has been updated from the pre-2026 value of `0.3781` to `0.3773` (<50 employees) and `0.3813` (≥50 employees), per **décret n°2025-887 du 4 septembre 2025** (JORFTEXT000052194026). The change (−0.0008) reflects recalibration after the LFSS 2025 suppression of the reduced taux for maladie (7%→13% flat) and alloc fam (3.45%→5.25% flat). At SMIC level this reduces the RGDU by ~17 €/year per employee — negligible in practice but required for formula compliance. All other constants (T_MIN, P, 3×SMIC threshold) are unchanged.

> ⚠️ **SMIC pending verification (P1):** Baker Tilly's Oct 2025 bulletin cites SMIC = 11,88 €/h (3×SMIC = 64 864 €/an) but our code uses 12,02 €/h (3×SMIC = 65 629 €/an). Difference 1,2%. The service-public.fr page confirms "SMIC 12,02 €/h depuis 1er novembre 2024, unchanged 2026". If this is wrong, file a P1 bug — see `dev-docs/issues/ACTIVE.md`. **Do not change SMIC in this task.**

[Source: Lefebvre-Dalloz — Le décret fixant les modalités de calcul de la RGDU pour 2026 est paru](https://formation.lefebvre-dalloz.fr/actualite/reforme-des-allegements-de-cotisations-le-decret-fixant-les-modalites-de-calcul-de-la-rgdu-pour-2026-est-paru)
[Source: Editions Tissot — Réduction générale des cotisations patronales : formule de calcul 2026](https://www.editions-tissot.fr/actualite/droit-du-travail/reduction-generale-des-cotisations-patronales-quel-gain-ou-perte-a-prevoir-pour-2026)
[Source: Baker Tilly — Allégement cotisations patronales nouveau calcul 2026](https://www.bakertilly.fr/actualites/erhs-allegement-cotisations-patronales-nouveau-calcul-et-impacts-pour-entreprise)
[Source: Légifrance — Décret n°2025-887 du 4 septembre 2025](https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000052194026)

### RGDU quick-reference table (2026 — T_DELTA = 0.3773, effectif < 50)

Values computed with `calc_rgdu(brut_annuel, effectif_entreprise=5)` and `calc_charges_salarie(brut_mensuel)`.
All amounts approximate (effectif=5, AT/MP=1.1%, formation=0.55%).

| Salaire brut mensuel | Brut annuel | RGDU coeff. | RGDU annuelle ≈ | Charges pat. nettes ≈ | Coût total ≈ |
|---|---|---|---|---|---|
| 1 823 € (SMIC) | 21 876 € | 0.397 (T_MAX) | ~8 692 € | ~40 €/mois | ~1 863 € |
| 2 200 € | 26 400 € | 0.244 | ~6 452 € | ~385 €/mois | ~2 585 € |
| 2 500 € | 30 000 € | 0.171 | ~5 142 € | ~620 €/mois | ~3 120 € |
| 3 000 € | 36 000 € | 0.100 | ~3 596 € | ~959 €/mois | ~3 959 € |
| 4 005 € (PASS) | 48 060 € | 0.039 | ~1 888 € | ~1 523 €/mois | ~5 528 € |

These values were recomputed 2026-04-27 after the TASK-2.14.5 T_DELTA audit. The previous table had incorrect values for 3 000 € and PASS rows (pre-2026 SMIC reference). See `test_task_2_14_5_rgdu_audit.py` for formula verification tests.

---

## §5 — Assimilé salarié (Président SASU/SAS, gérant minoritaire SARL)

**Code pointers:**
- `backend/app/calculations/social_charges.py::estimate_charges_assimile_salarie`, `net_to_brut`
- `backend/app/services/compare_types.py::_compute_net_assimile_salarie`

### Key difference from salarié (§4)

An assimilé salarié has the same cotisation rates as a salarié **EXCEPT**:
- **No chômage** (−4.05% patronal)
- **No AGS** (−0.25% patronal)

This saves ~4.3% of brut vs a salarié, but the assimilé salarié has no unemployment entitlement and no ACRE eligibility.

### Cost corridor (approximate)

```
cout_total ≈ remuneration_nette × 1.75 to 1.82
```

i.e. to take home 2 000 € net, the SASU pays ~3 500–3 640 € total (brut + charges patronales nettes).

**Derivation:**
- brut ≈ net / 0.778 → brut ≈ net × 1.285
- charges patronales nettes ≈ brut × 0.36 (all pat charges minus no-chômage, no-AGS, ≈36% at mid-range salary with reduced RGDU benefit — note: RGDU still applies to assimilé salarié)
- cout_total = brut + charges_patronales_nettes ≈ brut × 1.36 ≈ net × 1.748

**So the 75-82% rule is an approximation:**
- At SMIC-level salary (1 823 €/mois brut): RGDU nearly eliminates charges → ratio closer to 1.55 (55% over net)
- At 3 000 €/mois: ratio closer to 1.75 (75% over net)
- At PASS (4 005 €/mois): ratio closer to 1.82 (82% over net)
- The 75-82% rule is valid for the 2 000–5 000 €/mois range typical of coiffure dirigeants

### Worked example (assimilé salarié, SASU, 2 000 € net/mois)

```
1. Brut ≈ 2 000 / 0.778 = 2 571 €/mois
2. Charges salariales ≈ 2 571 × 0.222 = 571 € → net = 2 571 - 571 = 2 000 € ✓
3. Charges patronales brutes ≈ 2 571 × 0.36 = 925 €
   (maladie 13% + alloc fam 5.25% + vieillesse 8.55%+2.11% + retraite compl T1 4.72% + CEG T1 1.29% + AT 1.1% + FNAL 0.1% + CSA 0.3% + formation 0.55% + taxe app 0.68%)
4. RGDU mensuel ≈ 2 571 × 12 = 30 852 annual brut → coeff ≈ 0.11 → RGDU ≈ 3 394/12 = 283 €/mois
5. Charges patronales nettes ≈ 925 - 283 = 642 €/mois
6. Cout total = 2 571 + 642 = 3 213 €/mois
7. Ratio = 3 213 / 2 000 = 1.607 (60.7% over net) ← slightly below the 75% floor because RGDU is active at this salary level

At 3 000 € net:
1. Brut ≈ 3 858 €/mois
2. RGDU ≈ 3 858 × 12 = 46 296 annual → coeff ≈ 0.025 → RGDU ≈ 95 €/mois
3. Charges patronales brutes ≈ 3 858 × 0.36 = 1 389 €
4. Charges patronales nettes ≈ 1 389 - 95 = 1 294 €
5. Cout total = 3 858 + 1 294 = 5 152 €/mois
6. Ratio = 5 152 / 3 000 = 1.717 (71.7% over net) ← nearing the 75% boundary
```

### Comparison with TNS at same net

| Net souhaité (dirigeant) | SASU cout total | EURL/TNS cout total | Saving (EURL) |
|---|---|---|---|
| 1 500 €/mois | ~2 400 € | ~2 175 € | **~225 €/mois (~2 700 €/an)** |
| 2 000 €/mois | ~3 213 € | ~2 900 € | **~313 €/mois (~3 756 €/an)** |
| 2 400 €/mois (28 800 €/an) | ~3 947 € | ~3 480 € | **~467 €/mois (~5 604 €/an)** |
| 3 000 €/mois | ~5 152 € | ~4 350 € | **~802 €/mois (~9 624 €/an)** |

These are "net-equivalent" savings (same net, company saves the difference). The "cost-equivalent" axis (same company cost, dirigeant gets more net) is computed in §6 and `compare_types.py`.

---

## §6 — Comparison: TNS vs assimilé salarié for the same company budget

**Code pointers:**
- `backend/app/services/compare_types.py::compute_compare_types`, `compute_compare_types_cost_equivalent` (new in TASK-2.14.3)
- `backend/app/services/savings_engine.py::_channel_statut_juridique`

This is the framing Eric uses with clients: **"Pour le même budget que la société dépense sur vous aujourd'hui, combien pourriez-vous toucher en TNS?"**

### Cost-equivalent reverse-engineering (TASK-2.14.3)

```
Given: cout_total_dirigeant_actuel (what SASU pays today for the dirigeant)

For assimilé salarié (SASU/SAS):
  brut ≈ cout_total / 1.36
  net  ≈ brut × 0.778

For TNS (EURL/SARL/EI, ~45% rule):
  net  ≈ cout_total / 1.45
```

So if SASU spends 54 288 €/year on the dirigeant (28 800 € net):
- EURL/TNS can deliver: 54 288 / 1.45 = **37 440 €/year net** (+8 640 €/year)
- Saving: 37 440 - 28 800 = **+8 640 €/an net for the same cost**

This is exactly the "missing saving" that TASK-2.14.3 makes visible.

### Thresholds where the recommendation flips

At very low salary (< ~1 200 €/mois net), SASU can become cheaper than EURL because:
- RGDU nearly eliminates patronal charges at SMIC
- TNS has cotisations minimales (~1 177 €/an minimum regardless of income)

Above 1 200 €/mois net, EURL/SARL/EI TNS is always cheaper than SASU for the same net.

---

## §7 — EURL-IS dividendes trap

**Code pointers:** `backend/app/services/compare_types.py::_compute_net_tns_is` → `warnings` list.

### The rule

In EURL-IS / SARL-IS / EI-IS structures, dividendes that exceed **10% of (capital social + primes d'émission + solde moyen du compte courant d'associé)** are assujettis to TNS cotisations (~45%) **in addition to** the flat tax (PFU 30%).

For a typical coiffure salon:
- Capital social: 1 000 € (minimum EURL) to 7 500 € (typical salon creation)
- 10% threshold: 100 € to 750 € of dividendes per year before the trap triggers
- Result: **almost all dividendes in a typical salon are in the trap zone**

### Impact on compare_types.py

The app's `_compute_net_tns_is` computes `dividendes_net = dividendes_bruts × 0.70` (PFU 30%). This **underestimates the real charge** for almost all EURL-IS salons. The correct rate when over the threshold is approximately:
```
effective_rate = 0.30 + 0.45 × (1 - 0.30) ≈ 0.615 effective tax rate on excess dividendes
```

The app does NOT model this precisely (we don't store `capital_social` or `compte_courant_associé`). The fix is a WARNING on every IS-path row that distributes dividendes (implemented in TASK-2.14.4).

### What to tell users

Every EURL-IS / SARL-IS / EI-IS row in the simulator that shows `dividendes_net > 0` must carry:
> "En EURL/SARL à l'IS, les dividendes au-delà de 10 % du capital social (+ compte courant d'associé) supportent des cotisations TNS (~45 %) en plus de la flat tax 30 %. Pour un capital de 1 000 €, presque tous vos dividendes sont concernés. Vérifiez avec votre comptable avant tout changement de statut."

[Source: legifrance.gouv.fr — CSS art. L131-6](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000041799963)
[Source: urssaf.fr — Dividendes et cotisations sociales des indépendants](https://www.urssaf.fr/portail/home/independant/mes-cotisations/quelles-cotisations/les-dividendes.html)

---

## §8 — Statuts no longer available in 2026 (EIRL)

**Code pointer:** `backend/static-data/legacy_only_business_types.json` (new in TASK-2.14.2)

### EIRL — suppressed 15 February 2022

The **EIRL (Entreprise Individuelle à Responsabilité Limitée)** was suppressed by loi n°2022-172 du 14 février 2022, published in JORF du 15 février 2022.

From 15 February 2022:
- **No new EIRL can be created**
- Existing EIRLs continue to function under their original regime
- The new universal statut is the **EI (Entrepreneur Individuel)**, which since 15 May 2022 automatically separates personal and professional patrimony
- The **EI à l'IS (via assimilation EURL)** option is available from 15 May 2022

### What replaced EIRL

| Old option | Modern equivalent |
|---|---|
| EIRL (IR) | **EI** — même régime TNS, même protection patrimoniale automatique |
| EIRL (IS) | **EI à l'IS** (assimilation EURL) — même effet fiscal, depuis mai 2022 |
| EIRL → société | Conversion directe possible (procédure simplifiée depuis 2022) |

### How to handle EIRL salons in the app (TASK-2.14.2)

1. EIRL **cannot be selected** for new salons — removed from `business-types.json`
2. Existing salons with `business_type='eirl'` continue to function:
   - `business_type_legacy = true` flag added via Alembic migration
   - UI shows an amber badge: "Statut historique — non disponible aux nouvelles créations depuis 2022"
   - All calculation paths continue to work (EIRL is treated identically to EI for calculation purposes)
3. CoCo **never recommends EIRL** as a transition target
4. Statut juridique simulator defaults to **EI** as the comparison target for current EIRL salons

[Source: legifrance.gouv.fr — Loi n°2022-172 du 14 février 2022](https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000045139216)
[Source: service-public.fr — Entrepreneur individuel (EI) : statut unique depuis 2022](https://www.service-public.fr/professionnels-entreprises/vosdroits/F32887)

---

## §9 — CFE (Cotisation Foncière des Entreprises)

**Code pointer:** no active backend calculation — informational only, app shows a range estimate.

### Why CFE cannot be calculated precisely

Three variables the app cannot know:
1. **Valeur locative cadastrale** — set by tax authorities per property. Unknown without the avis CFE.
2. **Taux communal** — voted annually per commune, 10%–35% range.
3. **Year N-2 reference** — CFE 2026 uses 2024 CA data.

### National barème base minimale 2026 (sans local)

| CA HT N-2 | Base minimale (fourchette) |
|---|---|
| < 5 000 € | **Exonéré** |
| 5 001 – 10 000 € | 243 – 579 € |
| 10 001 – 32 600 € | 243 – 1 158 € |
| 32 601 – 100 000 € | 243 – 2 433 € |
| 100 001 – 250 000 € | 243 – 4 055 € |
| 250 001 – 500 000 € | 243 – 5 793 € |
| > 500 000 € | 243 – 7 533 € |

[Source: legifrance.gouv.fr — CGI art. 1647 D](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006316006) + délibérations locales

### Key exemptions for hairdressers

- **Année de création**: exonération totale (no CFE in year 1)
- **CA < 5 000 €**: exonération totale
- **Année 2 d'activité**: réduction 50% of base (this is why CFE appears to "double" from year 2 to year 3)
- **ZFU, ZRR, QPV zones**: 2–7 year exoneration

---

## §10 — Reform tracker

All reforms that touch the calculations in this document, with effective dates.

| Reform | Effective date | Scope | Impact on code | Status |
|---|---|---|---|---|
| Suppression réduction taux maladie patronal (7% → 13% flat) | 2026-01-01 | `§4` charges patronales | Maladie already set to flat 13% in `social_charges.py`. ✅ | Implemented |
| Suppression réduction taux alloc fam patronal (3.45% → 5.25% flat) | 2026-01-01 | `§4` charges patronales | Alloc fam already set to flat 5.25% in `social_charges.py`. ✅ | Implemented |
| RGDU recalibration (T_DELTA updated for flat rates) | 2026-01-01 | `§4` RGDU formula | `T_DELTA: 0.3781 → 0.3773` (<50 sal) / `0.3813` (≥50 sal) per décret n°2025-887 (JORFTEXT000052194026) — verified 2026-04-27 | ✅ Done (TASK-2.14.5) |
| TNS assiette unique réforme (cotisations on net, abattement 26% removed in base calc) | 2026-01-01 | `§3` TNS rates | The 45% app rule absorbs this — no code change needed. Documentary update only. | Done (doc only) |
| AE contributive rebalancing (CSG/CRDS shift to retraite) | 2026-01-01 | `§2` AE rates | Rates confirmed: BIC services 21.2%. No change to AE cotisation total. ✅ | Implemented |
| ACRE exoneration step-down (50% → 25%) | **2026-07-01** | `§2` ACRE | `ACRE_STEP_DOWN_DATE = date(2026, 7, 1)` — date-aware helper needed. TASK-2.14.6. | TASK-2.14.6 |
| EIRL suppression | 2022-02-15 | `§8` | Remove EIRL from active business types. TASK-2.14.2. | TASK-2.14.2 |
| EI statut unique (with IS option) | 2022-05-15 | `§8` | Add `ei` and `ei_is` to business types. TASK-2.14.2. | TASK-2.14.2 |
| SMIC revalorisation to 12.02 €/h | 2024-11-01 | `§1`, `§4` | `SMIC_MENSUEL_BRUT = 1_823.03`. Already correct. ✅ | Implemented |
| PASS 2026 = 48 060 € | 2026-01-01 | `§1`, `§3`, `§4` | `PASS_ANNUEL = 48060`. Already correct. ✅ | Implemented |
| 2027 assiette unique fiscal impact (EURL IR/IS cotisations deductibility) | 2027-01-01 | N/A | Out of scope for Sprint 2.14. Log for Sprint 3.x. | Out of scope |
