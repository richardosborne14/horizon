# TASK-8.4 — Apply Income Tax in Retirement Phase (Pensions Are Taxable)

## Problem
`_compute_retirement_year()` sets income tax to zero. In France, pension income is
subject to standard IR brackets with a 10% abattement (Art. 158-5-a CGI), capped at
€3,812/year per household. Investment returns drawn from taxable vehicles (AV after
8 years, SCPI, PER) are also subject to tax — but the drawdown module handles those.
This task is specifically about pension income tax.

Additionally, post-retirement investment returns (Livret A interest, PEA dividends,
SCPI yields) remain subject to their normal tax treatment. The return-on-investment
tax already runs through the vehicle tax logic. We are only adding pension IR here.

## SCOPE BOUNDARY — DO NOT
- DO NOT modify the drawdown module or vehicle return tax logic
- DO NOT apply AE-specific logic (VL, charges) in retirement
- DO NOT change any accumulation year logic
- DO NOT add complex retirement-phase IR with brackets — use the existing compute_ir()

---

## What changes

In `_compute_retirement_year(year_data, inp)`:

Currently:
```python
ir_annual = 0  # ← BUG: income tax not applied
```

Replace with:
```python
# Pensions are taxable income with 10% abattement (Art. 158-5-a CGI)
# Abattement: 10% of pension income, minimum €422, maximum €3,812 per household
PENSION_ABATTEMENT_RATE = 0.10
PENSION_ABATTEMENT_MIN = 422     # 2024 values, inflate over time
PENSION_ABATTEMENT_MAX = 3_812   # 2024 values, inflate over time

pension_gross = year_data["pension_annual"]  # user + spouse pensions combined
if pension_gross > 0:
    infl = (1 + inp.inflation_rate) ** y
    abattement_max = PENSION_ABATTEMENT_MAX * infl
    abattement_min = PENSION_ABATTEMENT_MIN * infl
    abattement = min(max(pension_gross * PENSION_ABATTEMENT_RATE, abattement_min), abattement_max)
    pension_imposable = pension_gross - abattement

    # Use compute_ir() with pension as salary-equivalent income
    # No AE CA, no VL, no charges
    ir_result = compute_ir(
        ae_ca=0,
        salary_income=pension_imposable,
        other_income=0,
        tax_parts=inp.tax_parts,
        cesu_annual=0,       # CESU stops at retirement
        charity_annual=inp.charity_annual * infl,
        versement_liberatoire=False,
        ae_activity_type=None,
        year=current_year,
    )
    ir_annual = ir_result["ir_annual"]
else:
    ir_annual = 0
```

## Impact estimate for Richard's situation

Estimated pension (both Richard + Caro): ~€1,600/month = €19,200/year
Abattement: min(€1,920, €3,812) = €1,920
Imposable: €19,200 - €1,920 = €17,280
Divided by 4 tax parts = €4,320 per part
At that income level, marginal rate ~11% bracket
IR estimate: ~€500–1,500/year depending on parts

Small but materially non-zero — and grows if pension estimates improve.

---

## DONE WHEN
- [ ] `_compute_retirement_year()` applies IR on pension income with 10% abattement
- [ ] Abattement min/max are inflated each year
- [ ] IR in retirement uses `compute_ir()` with ae_ca=0 and pension as salary_income
- [ ] Year drill-down for retirement years shows "Impôt sur les pensions: Xk€"
- [ ] Unit test: €20,000 pension, 4 parts → IR > 0 (currently returns 0 → bug confirmed)
