# TASK-7.4: Spouse/Partner Data Model & API

**Status:** TODO
**Sprint:** 7
**Priority:** P1 (high — foundation for couple mode)
**Est. effort:** 3 hr
**Dependencies:** None

---

## Context

Horizon currently models one person. This task adds a spouse/partner entity with: identity, professional status, conjointe collaboratrice (CC) option, and revenue. The spouse is a 1:1 relationship off the user — not a separate login. CC is only available under EIRL/EURL when married or PACSed.

---

## Step-by-Step Instructions

### Step 1: Create the Spouse model

Create file `backend/app/models/spouse.py`:

```python
"""Spouse model — partner financial identity for household projection."""
from uuid import uuid4
from sqlalchemy import (
    Column, String, Date, Boolean, Integer, Numeric,
    ForeignKey, DateTime, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Spouse(Base):
    __tablename__ = "spouses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        unique=True, nullable=False,
    )

    # ── Identity ───────────────────────────────────────────────────────
    first_name = Column(String(100), nullable=True)
    birth_date = Column(Date, nullable=True)

    # ── Relationship ───────────────────────────────────────────────────
    relationship_type = Column(String(20), nullable=False, server_default="married")
    # Values: married, pacsed, concubinage

    # ── Professional status ────────────────────────────────────────────
    status = Column(String(20), nullable=False, server_default="cdi")
    # Values: cdi, cdd, ae, eirl, eurl, sasu, unemployed, retired,
    #         inactive, conjointe_collaboratrice
    ae_activity_type = Column(String(20), nullable=True)
    # Only when status=ae: bic_vente, bic_service, bnc, bic_heberg
    versement_liberatoire = Column(Boolean, nullable=False, server_default="false")

    # ── Revenue (simple field — detailed via income_sources table) ─────
    monthly_gross_income = Column(Numeric(10, 2), nullable=True)
    growth_preset = Column(String(20), nullable=False, server_default="moderate")
    growth_rate_custom = Column(Numeric(5, 4), nullable=True)

    # ── Conjointe collaboratrice ───────────────────────────────────────
    is_conjointe_collaboratrice = Column(Boolean, nullable=False, server_default="false")
    cc_cotisation_option = Column(String(30), nullable=True)
    # Values: tiers_plafond, moitie_plafond, tiers_revenu, moitie_revenu

    # ── Timestamps ─────────────────────────────────────────────────────
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", backref="spouse")
```

### Step 2: Create Alembic migration

```bash
cd backend && alembic revision --autogenerate -m "add spouses table"
alembic upgrade head
```

### Step 3: Create Pydantic schemas

Create file `backend/app/schemas/spouse.py`:

```python
"""Pydantic schemas for spouse CRUD."""
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SpouseCreate(BaseModel):
    first_name: Optional[str] = Field(None, max_length=100)
    birth_date: Optional[date] = None
    relationship_type: str = Field(default="married", pattern="^(married|pacsed|concubinage)$")
    status: str = Field(default="cdi")
    ae_activity_type: Optional[str] = None
    versement_liberatoire: bool = False
    monthly_gross_income: Optional[Decimal] = Field(None, ge=0)
    growth_preset: str = "moderate"
    growth_rate_custom: Optional[Decimal] = None
    is_conjointe_collaboratrice: bool = False
    cc_cotisation_option: Optional[str] = None


class SpouseUpdate(BaseModel):
    first_name: Optional[str] = Field(None, max_length=100)
    birth_date: Optional[date] = None
    relationship_type: Optional[str] = None
    status: Optional[str] = None
    ae_activity_type: Optional[str] = None
    versement_liberatoire: Optional[bool] = None
    monthly_gross_income: Optional[Decimal] = None
    growth_preset: Optional[str] = None
    growth_rate_custom: Optional[Decimal] = None
    is_conjointe_collaboratrice: Optional[bool] = None
    cc_cotisation_option: Optional[str] = None


class SpouseRead(BaseModel):
    id: UUID
    user_id: UUID
    first_name: Optional[str] = None
    birth_date: Optional[date] = None
    relationship_type: str
    status: str
    ae_activity_type: Optional[str] = None
    versement_liberatoire: bool
    monthly_gross_income: Optional[Decimal] = None
    growth_preset: str
    growth_rate_custom: Optional[Decimal] = None
    is_conjointe_collaboratrice: bool
    cc_cotisation_option: Optional[str] = None
    current_age: Optional[int] = None  # Computed from birth_date

    model_config = {"from_attributes": True}
```

### Step 4: Create router

Create file `backend/app/routers/spouse.py`:

CRUD endpoints:
- `POST /api/spouse` → create (enforce max 1 per user via unique constraint)
- `GET /api/spouse` → get (return 404 if none)
- `PUT /api/spouse` → update (partial — only send changed fields)
- `DELETE /api/spouse` → delete

Plus:
- `GET /api/spouse/cc-estimate` → returns estimated annual CC cotisations for all 4 options

**CC cotisation calculation logic:**

```python
PLAFOND_SS_ANNUEL = Decimal("46368")  # 2024 value

def estimate_cc_cotisations(user_ca_annual: Decimal) -> dict:
    """Estimate annual cotisations for each CC option.
    
    CC cotisation rate is ~28% (retraite base ~17.75% + complémentaire ~7% + invalidité ~3%).
    Applied to the chosen base.
    """
    CC_RATE = Decimal("0.28")
    bases = {
        "tiers_plafond": PLAFOND_SS_ANNUEL / 3,
        "moitie_plafond": PLAFOND_SS_ANNUEL / 2,
        "tiers_revenu": user_ca_annual / 3,
        "moitie_revenu": user_ca_annual / 2,
    }
    return {
        option: {
            "base_annuelle": str(base.quantize(Decimal("0.01"))),
            "cotisation_annuelle": str((base * CC_RATE).quantize(Decimal("0.01"))),
            "cotisation_mensuelle": str((base * CC_RATE / 12).quantize(Decimal("0.01"))),
        }
        for option, base in bases.items()
    }
```

### Step 5: Register router

File: `backend/app/routers/__init__.py`

Add:
```python
from app.routers.spouse import router as spouse_router
api_router.include_router(spouse_router)
```

### Step 6: Unit tests

Create `backend/tests/test_spouse.py`:
- Test create spouse (success, duplicate fails)
- Test get spouse (exists, 404)
- Test update spouse (partial update)
- Test delete spouse
- Test CC estimate returns 4 options with reasonable values
- Test CC is only valid when user status is EIRL/EURL and relationship is married/pacsed

---

## SCOPE BOUNDARY

- DO NOT build the frontend for this task. Frontend is TASK-7.9.
- DO NOT modify the projection engine. That's TASK-7.8.
- DO NOT add career history for the spouse. That's TASK-7.7.
- DO NOT add income sources for the spouse. That's handled by TASK-7.5's `earner` field.
- The CC cotisation rate of 28% is a simplification. DO NOT model the exact breakdown of each sub-cotisation.
- DO NOT add a tax parts auto-adjustment endpoint. The frontend will handle the prompt.

## DONE WHEN

- [ ] Migration creates `spouses` table with unique constraint on `user_id`
- [ ] `POST /api/spouse` creates a spouse, second POST returns 409
- [ ] `GET /api/spouse` returns spouse data or 404
- [ ] `PUT /api/spouse` updates only sent fields
- [ ] `DELETE /api/spouse` removes the spouse
- [ ] `GET /api/spouse/cc-estimate` returns 4 options with amounts
- [ ] CC fields are validated (only when conditions met)
- [ ] All tests pass
