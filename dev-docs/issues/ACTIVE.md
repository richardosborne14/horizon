# Active Issues

---

## [BUG] P2 — Income chart shows working salary + passive vs goal line (misleading cliff at retirement)
- **Found during:** Horizon Engine Audit (2026-05-18)
- **Severity:** P2 UX — the "am I on track?" visual compares goal against `total_monthly_income` which includes work salary. Creates a sharp cliff at retirement year that users interpret as "I'll be ruined at 67."
- **Fix:** Add a second "passive income only" line, or annotate the retirement year transition clearly as "salary stops here."
- **File:** Frontend runway `+page.svelte`, `incomeChartData` block
- **Deferred by:** Sprint 8.2 (2026-05-18) — frontend-only, P2, no-blocking

---

## [BUG] P2 — Drawdown module uses hardcoded 50% gains ratio for tax estimates
- **Found during:** Horizon Engine Audit (2026-05-18)
- **Severity:** P2 — `drawdown.py` line 142: `gains_ratio = Decimal("0.5")` is hardcoded. Actual tax on PEA/AV withdrawal depends on contribution vs gains split. New savers (95% contributions) pay ~1.7% effective; long-running savers (80% gains) pay ~13.8%. Hardcoded 50% gives ~8.6% for everyone.
- **Reproduction:** Call `compute_drawdown_for_year()` for a user with a single PEA with all-contribution balance → tax amount will be 8.6% of withdrawal not ~1.7%.
- **Suggested fix:** Track `contributions` per vehicle in `ProjectionInput.allocations` (`initial_balance + cumulative_monthly × years`). Even an estimate beats hardcoded 50%.
- **File:** `backend/app/calculations/drawdown.py` line 142
- **Deferred by:** Sprint 8.2 (2026-05-18) — medium complexity, requires schema change to allocations dict

---

## [RESOLVED] ~~Wealth = 0 throughout when no investment allocations configured~~
- **Found during:** Horizon Engine Audit (2026-05-18)
- **Resolved during:** Sprint 8.2, TASK-8.2.1 (2026-05-18)
- **Resolution:** Created virtual `savings_unallocated` bucket; removed `and inp.allocations` guard; `_SURPLUS_REINVESTMENT_FRACTION` set to 1.0 (was 0.5). 161 tests pass.

---

## [RESOLVED] ~~"Cotis." column in projection table excludes CFE (~300€/yr)~~
- **Found during:** Horizon Engine Audit (2026-05-18)
- **Resolved during:** Sprint 8.2, TASK-8.2.2 (2026-05-18)
- **Resolution:** `ae_rate` and `cfe` fields now exposed on `YearProjection`; frontend column updated.

---

## [RESOLVED] ~~`total_monthly_income` misses tax credits (CESU + charity)~~
- **Found during:** Horizon Engine Audit (2026-05-18)
- **Resolved during:** Sprint 8.2, TASK-8.2.3 (2026-05-18)
- **Resolution:** `tax_credits` added to `total_monthly` formula in `_compute_accumulation_year`.

---

## [RESOLVED] ~~`_compute_wealth_durability` hardcodes retirement age as 70~~
- **Found during:** Horizon Engine Audit (2026-05-18)
- **Resolved during:** Sprint 8.2, TASK-8.2.4 (2026-05-18)
- **Resolution:** Function now accepts `timeline` param and derives `retirement_start` from first `is_retirement=True` entry.

---

## [RESOLVED] ~~`_check_wealth_exhaustion` insight "extra monthly savings" formula wrong~~
- **Found during:** Horizon Engine Audit (2026-05-18)
- **Resolved during:** Sprint 8.2, TASK-8.2.3 (2026-05-18)
- **Resolution:** `working_years` now computed as `retirement_year - current_year` from timeline (not `current_age - 1`).

---

## [RESOLVED] ~~Surplus reinvestment 50% factor undisclosed, approximately halves projected wealth~~
- **Found during:** Horizon Engine Audit (2026-05-18)
- **Resolved during:** Sprint 8.2, TASK-8.2.1 (2026-05-18)
- **Resolution:** `_SURPLUS_REINVESTMENT_FRACTION = Decimal("1")`. Named constant with docstring.

---

## [RESOLVED] ~~AE cotisation rate frozen at 2026 for entire 28-year projection~~
- **Found during:** Horizon Engine Audit (2026-05-18)
- **Resolved during:** Sprint 8.2, TASK-8.2.5 (2026-05-18)
- **Resolution:** `AE_RATE_ANNUAL_GROWTH` dict in `constants.py`; `ProjectionInput.ae_rate_annual_growth`; router wires per-scale growth (optimistic=0%, moderate=+0.2pp/yr, pessimistic=+0.4pp/yr).

---

## [RESOLVED] ~~Legacy `AE_RATE_SCHEDULE` dict has duplicate 2024 entries~~
- **Found during:** Horizon Engine Audit (2026-05-18)
- **Resolved during:** Sprint 8.2, TASK-8.2.6 (2026-05-18)
- **Resolution:** H1 2024 baseline entry moved to `from_year: 2023` in the legacy dict. Projection engine tuple schedule unaffected.

---

## [RESOLVED] ~~Data not persisting — client-side API calls return 401~~
- **Found during:** Sprint 2 blank page fix verification
- **Resolved during:** Sprint 6 start (2026-05-09)
- **Resolution:** Issue no longer reproducible. Both direct backend auth (port 48002) and frontend proxy auth (port 48178) work correctly. Session cookie is properly set by the SvelteKit server action and forwarded by the hooks.server.ts API proxy.
