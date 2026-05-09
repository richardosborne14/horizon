# TASK-0.2: Strip Salon Domain — Backend

**Status:** DONE ✅ (2026-05-08)
**Sprint:** 0
**Priority:** P0 (critical)
**Est. effort:** 2 hr
**Dependencies:** TASK-0.1

## Context

The ComCoi backend has ~20 domain-specific models (salons, employees, monthly reports, payslips, services, calculations, CoCo AI). Horizon 30 needs none of this — it has its own domain. This task strips everything salon-specific and leaves a clean backend with: auth, user model, admin_config, Stripe webhook handling, and a working migration chain.

This is the most delicate task in Sprint 0. The risk is broken imports — removing a model that another model or service references. The approach is to work from the leaves inward: remove the most-dependent files first, then the things they depended on.

## Requirements

1. **Remove these SQLAlchemy models** (and their corresponding files in `backend/app/models/`):
   - `salon.py` (Salon, SalonConfig)
   - `employee.py` (Employee)
   - `monthly_report.py` (MonthlyReport, MonthlyExpense, MonthlySalary, MonthlyService, BrandPurchase)
   - `service.py` (Service)
   - `payslip.py` (PayslipForm, PayslipWalletTransaction, PayslipCreditBalance, StripeEventProcessed) — **KEEP StripeEventProcessed**, move it to a `stripe.py` model file
   - `coco.py` (CocoConversation, CocoUserProfile)
   - `calculation_history.py` (CalculationHistory, Scenario, ScenarioCalculation)

2. **Remove these routers** (`backend/app/routers/`):
   - Everything except `auth.py` and `stripe_webhooks.py` (if exists)
   - This includes: `salons.py`, `salon_config.py`, `employees.py`, `monthly_reports.py`, `services.py`, `payslips.py`, `coco.py`, `calculators.py`, `dashboard.py`, `admin.py` (keep admin if it has generic config endpoints)

3. **Remove these services** (`backend/app/services/`):
   - Everything except `auth.py` and any Stripe-related services
   - This includes: `typical_month.py`, `monthly_report.py`, `salary.py`, `coco_tools.py`, `compare_types.py`, `savings_engine.py`, etc.

4. **Remove entire directories:**
   - `backend/app/calculations/` — will be rebuilt from scratch
   - `backend/app/coco/` — Horizon 30 will have its own AI layer later
   - `backend/static-data/` — salon-specific JSON data files

5. **Update `backend/app/models/__init__.py`** — remove all deleted model imports, keep User and StripeEventProcessed

6. **Update `backend/app/routers/__init__.py`** (or `main.py` where routers are mounted) — remove all deleted router mounts

7. **Create a fresh Alembic migration:**
   - Drop all salon-specific tables
   - Keep: `users`, `admin_config`, `stripe_events_processed`
   - The migration should be a single "reset to clean slate" migration
   - Consider: nuke existing migration chain and create a single `initial_horizon30.py` migration that creates only the 3 tables we need

8. **Verify:** `docker compose up -d --build backend` starts without import errors

## Technical Approach

Work in this order to avoid cascading import errors:
1. First: delete the CoCo layer (`coco/` directory, `coco.py` model)
2. Second: delete services that import models (services/)
3. Third: delete routers that import services (routers/)
4. Fourth: delete models
5. Fifth: update `__init__.py` files and `main.py`
6. Sixth: create fresh Alembic migration
7. Seventh: test

### Files to Create/Modify
- `backend/app/models/__init__.py` — strip imports
- `backend/app/routers/__init__.py` or `backend/app/main.py` — strip router mounts
- `backend/app/models/stripe.py` — new file, StripeEventProcessed only
- `backend/alembic/versions/` — new migration
- Delete: ~15-20 files across models/, routers/, services/, calculations/, coco/

## Acceptance Criteria

- [ ] `docker compose up -d --build backend` starts without errors
- [ ] `docker compose logs backend --tail=30` shows clean startup
- [ ] `alembic upgrade head` runs and creates only: users, admin_config, stripe_events_processed
- [ ] `POST /api/auth/register` works (create test user)
- [ ] `POST /api/auth/login` works (get token)
- [ ] No Python import errors in any remaining file
- [ ] No references to salon, employee, monthly_report, payslip, coco in remaining backend code
- [ ] Unit tests for auth still pass (if any exist)
- [ ] LEARNINGS.md updated with any gotchas

## Notes

- **Don't delete `backend/app/schemas/auth.py`** — it's needed for auth endpoints
- **Don't delete middleware** (CORS, auth middleware) — still needed
- **Keep the Pydantic base classes** if they exist (BaseSchema, etc.)
- **Keep `backend/app/utils/`** — formatting helpers, etc. may be reusable
- The `admin_config` table is useful for storing app-wide settings (rates, thresholds) — keep it
- If stuck on a circular import, check `models/__init__.py` — that's usually the culprit
