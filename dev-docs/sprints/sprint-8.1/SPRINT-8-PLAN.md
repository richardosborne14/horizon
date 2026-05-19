# Sprint 8 — Accuracy, Compliance & Savings Intelligence

**Sprint goal:** Fix all confirmed calculation bugs, update to 2026-correct French rates,
add career history intelligence, and deliver a comprehensive savings education + projection layer.

**Execution model:** DeepSeek V4 PRO via Cline, tasks run sequentially, one file at a time.

---

## Task list

| Task | Title | Type | Priority |
|------|-------|------|----------|
| TASK-8.1 | Auto-calculate quotient familial from marital status + children | Bug fix | 🔴 Critical |
| TASK-8.2 | Fix 4% passive income rule: investments only, not primary residence | Bug fix | 🔴 Critical |
| TASK-8.3 | Update AE BNC cotisation rate schedule to 2026-correct values | Bug fix | 🔴 Critical |
| TASK-8.4 | Apply income tax to retirement phase (pensions are taxable) | Bug fix | 🔴 Critical |
| TASK-8.5 | Fix Livret A / LDDS rates: government-set, not inflation-derived | Bug fix | 🟠 High |
| TASK-8.6 | Fix assurance-vie abattement: €9,200 for married couples | Bug fix | 🟠 High |
| TASK-8.7 | Fix income growth rate: null → preset fallback + AE CA ceiling alert | Bug fix | 🟠 High |
| TASK-8.8 | Career history enhancements: chômage, paid internship, SASU type, gap detector | Feature | 🟠 High |
| TASK-8.9 | Enhanced savings tab: all French vehicles, rules panel, balance projection | Feature | 🟡 Medium |
| TASK-8.10 | Property classification: primary residence vs rental in net worth + projects | Feature | 🟡 Medium |
| TASK-8.11 | Fix car entity: sync replace_cost metadata with cost events on save | Bug fix | 🟡 Medium |
| TASK-8.12 | AE pension: use projected income from income_sources, not static career period | Bug fix | 🟠 High |

---

## Key confirmed French numbers for 2026

### AE BNC cotisations (SSI / non-CIPAV) — URSSAF official
| Period | Rate |
|--------|------|
| Before July 2024 | 21.1% |
| July–Dec 2024 | 23.1% |
| 2025 | 24.6% |
| 2026 (1 Jan 2026, decree n°2025-943) | **25.6%** |
| 2027+ | 25.6% (stable — 3-year schedule complete) |

### Regulated savings rates (as of 1 Feb 2026, official government decree)
| Vehicle | Rate | Notes |
|---------|------|-------|
| Livret A | **1.5%** | Revised every 6 months; formula: avg(inflation, €STER) |
| LDDS | **1.5%** | Always equals Livret A |
| LEP | **2.5%** | Income-restricted (RFR ≤ €21,393 single / more for households) |
| PEL (new 2026) | ~2.0% gross | Government-set; subject to 30% PFU on interest |
| CEL | 1.0% | Indexé Livret A × 2/3 |

### AE micro-BNC CA ceiling 2026–2028
- **83,600 €/year** — above this, mandatory switch to régime réel (EURL, SASU, EI réel)

### Assurance-vie annual abattement
- **€4,600** single / **€9,200** married couple (CGI Art. 125-0 A)

---

## Critical context notes for agent

- User (Richard) is at **€79,200/yr CA** — within 4,400€ of the AE BNC ceiling. Income growth modeling must warn when this approaches.
- User has 3 children (Ellie 10, Saoirse 8, Romy 1) → quotient familial = 4.0, not 3.5.
- Primary residence (€320,000) must NOT be included in the 4% rule passive income calculation.
- Livret A and LDDS rates are set by government decree twice yearly — they are NOT simple inflation multiples.
- Pension income is subject to standard IR brackets with a 10% abattement (cap ~€3,812/year/household, split across incomes).

---

## Definition of done for the sprint
- [ ] All 🔴 critical tasks complete and verified in local dev environment
- [ ] All 🟠 high tasks complete
- [ ] TASK-8.9 savings tab renders with all 8 French vehicle types, their rules panel, and the balance projection chart
- [ ] TASK-8.10 net worth form has residence type selector
- [ ] No new regressions in projection unit tests
