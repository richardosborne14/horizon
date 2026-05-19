# Sprint 8.2 — Horizon Engine Audit Fixes

**Sprint goal:** Address all findings from `dev-docs/audits/HORIZON_ENGINE_AUDIT.md`.
Fix the P0 wealth-sink that breaks every no-allocation user, correct income/readiness/insight
calculations, add AE rate sensitivity to the projection, and clean up P2 data-quality issues.

**Audit source:** `HORIZON_ENGINE_AUDIT.md` (2026-05-18, auditor: Cline)  
**Execution model:** DeepSeek V4 PRO via Cline, tasks run sequentially.

---

## Task list

| Task | Audit findings | Priority | Status |
|------|----------------|----------|--------|
| TASK-8.2.1 | Wealth sink — no allocations discards all surplus | 🔴 P0 | [ ] |
| TASK-8.2.2 | Charges column excludes CFE in projection table | 🔴 P0 | [ ] |
| TASK-8.2.3 | total_monthly_income missing tax_credits; working_years bug; pension in goal_reached | 🟠 P1 | [ ] |
| TASK-8.2.4 | Readiness: hardcoded retirement=70; savings-rate denominator wrong | 🟠 P1 | [ ] |
| TASK-8.2.5 | AE rate frozen beyond 2026 — expose pessimistic sensitivity knob | 🟠 P1 | [ ] |
| TASK-8.2.6 | P2 polish: drawdown gains-ratio, legacy rate dict, income chart, timeline clip | 🟡 P2 | [ ] |

---

## Context

- URSSAF confirmed: 25.6% rate is final for the current 3-year schedule (2024 décret). No further
  increases published. Default remains 0 bp/yr growth; pessimistic scale exposes a +20 bp/yr knob.
- Default "unallocated" bucket: Livret A floor at 1.5% (per Sprint 8.1 TASK-8.5 corrected rate).
- Surplus reinvestment fraction: 1.0 (full surplus accumulates). Previous 0.5 was undocumented
  and halved everyone's wealth trajectory.

## Definition of done

- [ ] All P0 fixes deployed and smoke-tested at http://localhost:48178/runway
- [ ] richard@digitalbricks.io shows non-zero wealth on the Horizon page
- [ ] All existing projection tests still pass (`docker compose exec backend pytest`)
- [ ] New tests added for each fix
