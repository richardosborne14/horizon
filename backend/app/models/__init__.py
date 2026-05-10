"""
Import all models here so Alembic can discover them via Base.metadata.

Order matters for circular import safety — user first, then auth, then admin.
All models must be imported before alembic autogenerate runs.
"""
from app.models.user import User
from app.models.auth import Session, PasswordResetToken
from app.models.admin import AdminConfig
from app.models.profile import UserProfile
from app.models.life_entity import LifeEntity
from app.models.recurring_expense import RecurringExpense
from app.models.investment import InvestmentAllocation
from app.models.project import Project
from app.models.career_period import CareerPeriod
from app.models.loan import Loan
from app.models.net_worth import NetWorthSnapshot

__all__ = [
    "User",
    "Session",
    "PasswordResetToken",
    "AdminConfig",
    "UserProfile",
    "LifeEntity",
    "RecurringExpense",
    "InvestmentAllocation",
    "Project",
    "CareerPeriod",
    "Loan",
    "NetWorthSnapshot",
]
