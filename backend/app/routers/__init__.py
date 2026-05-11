"""
Router registry — all API routers registered here.

Imported by app/main.py which includes this as the main api_router.
"""
from fastapi import APIRouter

# Main API router — all sub-routers mount here
api_router = APIRouter()

# Auth
from app.routers.auth import router as auth_router
from app.routers.auth import users_router

api_router.include_router(auth_router)
api_router.include_router(users_router)

# Rates (public reference data — no auth required)
from app.routers.rates import router as rates_router
api_router.include_router(rates_router)

# Constants (public reference data — no auth required)
from app.routers.constants import router as constants_router
api_router.include_router(constants_router)

# Profile (auth required — user financial profile)
from app.routers.profile import router as profile_router
api_router.include_router(profile_router)

# Life Entities (Sprint 2 — kids, pets, cars, tech)
from app.routers.life_entities import router as life_entities_router
api_router.include_router(life_entities_router)

# Recurring Expenses (Sprint 2 — time-bounded annual expenses)
from app.routers.recurring_expenses import router as recurring_expenses_router
api_router.include_router(recurring_expenses_router)

# Investments (Sprint 3 — vehicle allocation tracking)
from app.routers.investments import router as investments_router
api_router.include_router(investments_router)

# Projects (Sprint 3 — investments and life events)
from app.routers.projects import router as projects_router
api_router.include_router(projects_router)

# Projection (Sprint 4 — 30-year wealth projection engine)
from app.routers.projection import router as projection_router
api_router.include_router(projection_router)

# Loans (Sprint 6 — structured loan tracking with end dates)
from app.routers.loans import router as loans_router
api_router.include_router(loans_router)

# Career History (Sprint 6 — professional career tracking for pension)
from app.routers.career import router as career_router
api_router.include_router(career_router)

# Net Worth (Sprint 6 — TASK-6.5)
from app.routers.net_worth import router as net_worth_router
api_router.include_router(net_worth_router)

# Income Sources (Sprint 7 — TASK-7.5)
from app.routers.income_sources import router as income_sources_router
api_router.include_router(income_sources_router)

# Spouse (Sprint 7 — TASK-7.4)
from app.routers.spouse import router as spouse_router
api_router.include_router(spouse_router)

# PDF Export (TASK-5.9)
from app.routers.export import router as export_router
api_router.include_router(export_router)

# Stripe webhooks not yet mounted — will be re-added when Horizon has payment flows
