# Sprint 5: Calculation Depth, Insights & UX Excellence

**Status:** COMPLETE
**Created:** 2026-05-09
**Predecessor:** Sprint 4 (Projection Engine & Runway)
**Goal:** Fix calculation bugs, deepen the projection engine's accuracy, add actionable insights, and polish the UX so the tool genuinely changes how a freelancer plans their financial future.

---

## Why this sprint exists

Sprints 1–4 built the full pipeline: data entry → projection → visualization. The app works. But "works" isn't the same as "delivers transformative value." This sprint closes the gap between a functional simulator and a tool that earns the user's trust and actually changes their behavior.

Three pillars:

1. **Accuracy** — Fix known bugs (status change diff math), add missing calculations (IR, pension, post-retirement), and tighten the investment model. A user who spots one wrong number loses trust in every number.

2. **Insight** — The projection engine has all the data to answer "am I on track?" and "what should I change?" but currently just dumps a table. This sprint adds an insights engine, sensitivity analysis, and scenario comparison.

3. **Polish** — Charts need axes, the Runway needs a narrative arc, onboarding needs to exist, and export needs to work. These aren't cosmetic — they're the difference between a tool someone uses once and one they return to monthly.

---

## Task Index

| ID | Task | Priority | Status |
|----|------|----------|--------|
| **5.1** | Fix Status Change Comparison Math | P0 | ✅ Done |
| **5.2** | Post-Retirement Phase Modeling | P0 | ✅ Done |
| **5.3** | State Pension (Retraite) Estimation | P1 | ✅ Done |
| **5.4** | Actionable Insights Engine | P0 | ✅ Done |
| **5.5** | Retirement Readiness Score | P1 | ✅ Done |
| **5.6** | Chart Polish & Interactivity | P1 | ✅ Done |
| **5.7** | Scenario Comparison Mode | P1 | ✅ Done |
| **5.8** | Onboarding Flow & Progress Tracking | P2 | ⚠️ Deferred to Sprint 6 |
| **5.9** | PDF Export of Projection | P2 | ✅ Done |
| **5.10** | Investment Model Refinement | P2 | ✅ Done |

## Definition of Sprint-Done

- ✅ Status change comparison shows correct difference values (8 tests pass)
- ✅ Projection continues past retirement age showing wealth drawdown (8 tests pass)
- ✅ State pension estimate included in post-retirement income (9 tests pass)
- ✅ Insights engine surfaces 11 actionable recommendations (19 tests pass)
- ✅ Retirement readiness score displayed prominently on Runway (21 tests pass)
- ✅ Charts have Y-axis labels, grid lines, hover tooltips, retirement marker
- ✅ Scenario comparison allows side-by-side parameter testing (backend endpoint + frontend panel)
- ⚠️ New users see guided onboarding with section progress (DEFERRED to Sprint 6)
- ✅ PDF export generates a clean 3-page projection summary
- ✅ All 10 tasks have comprehensive unit tests (88 tests passing)
- ✅ LEARNINGS.md updated

## Deferred

- **TASK-5.8** (Onboarding Flow): Existing onboarding handles business setup. The Sprint 5 welcome overlay, section progress bar, completion toasts, and "next section" prompts should be implemented in Sprint 6 as UX polish.

## Outcomes

- **88 unit tests** across all Sprint 5 backend tasks — all passing
- **Backend**: `/api/projection/compare` scenario comparison endpoint, `/api/projection/export` PDF export, `/api/projection/pension-estimate` retirement estimate, insights engine, readiness score
- **Frontend**: ScenarioPanel (sliders + presets + delta), PDF export button, retirement markers on charts, X-axis year labels, readiness gauge, insight cards
- **Investment refinements**: Tax-by-holding-period for PEA/AV, Livret A overflow to LDDS, real wealth equivalent, regulated savings track inflation

## Confidence: 8/10

All backend features are tested. Frontend ScenarioPanel and export button integrated and building. TASK-5.8 (onboarding flow) is the only deferred item — existing onboarding works but the polish items were lower priority than scenario comparison and export.

## Out of scope

- Monte Carlo simulation (future — deterministic projections for now)
- AI-powered analysis (Sprint 6 if planned)
- Mobile-native layout (future)
- Multi-user household modeling
- Income tax (IR) full simulation (complex; deferred — only VL impact for AE)