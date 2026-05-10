# TASK-6.1: Career History Model & API

**Status:** TODO
**Sprint:** 6
**Priority:** P0 (critical — foundation for pension accuracy)
**Est. effort:** 2.5 hr
**Dependencies:** None

## Context

The pension engine (Task 5.3) currently estimates retirement income based solely on projected AE revenue. But most freelancers didn't start as freelancers. Richard had an 8-year CDI before going independent. Those 8 years of full-time salaried employment represent 32 validated trimestres at a significantly higher salary base than AE income — which dramatically changes the pension calculation.

Without career history, the pension estimate is systematically wrong. A freelancer with 20 years of CDI history could have 80+ trimestres already banked, putting them on a completely different trajectory than someone who's been AE since age 22.

This task builds the data model for storing past employment periods and feeding them into the pension engine.

## Requirements

### Data Model

1. **Create `backend/app/models/career_period.py`:**

   ```python
   class CareerPeriod(Base):
       __tablename__ = "career_periods"

       id = Column(UUID, primary_key=True, default=uuid4)
       user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

       # Period type
       period_type = Column(String(20), nullable=False)
       # "cdi", "cdd", "interim", "ae", "eirl", "eurl", "sasu",
       # "apprenticeship", "internship", "unemployment", "parental_leave",
       # "education", "foreign", "other"

       # Dates
       start_date = Column(Date, nullable=False)
       end_date = Column(Date, nullable=True)  # null = ongoing (current period)

       # Employment details
       employer_name = Column(String(200), nullable=True)  # Optional, for user reference
       job_title = Column(String(200), nullable=True)

       # Salary / Revenue — for pension calculation
       # CDI/CDD: gross annual salary (used for SAM calculation)
       # AE: annual CA (used for trimestre validation)
       # Unemployment: daily allocation (for trimestre validation)
       annual_gross = Column(Numeric(12, 2), nullable=True)
       is_full_time = Column(Boolean, nullable=False, server_default="true")
       # Part-time percentage (100 = full time, 80 = 4/5ths)
       time_percentage = Column(Integer, nullable=False, server_default="100")

       # Pension regime
       # CDI/CDD → "general" (CNAV regime général)
       # AE → "ae" (micro-entrepreneur, was RSI, now CNAV since 2020)
       # CIPAV professions → "cipav"
       # Foreign → "foreign" (no French trimestres)
       pension_regime = Column(String(20), nullable=True)

       # Metadata
       notes = Column(String(500), nullable=True)
       sort_order = Column(Integer, nullable=False, server_default="0")
       is_active = Column(Boolean, nullable=False, server_default="true")
       created_at = Column(DateTime(timezone=True), server_default=func.now())
       updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
   ```

2. **Derived fields** (computed, not stored):
   - `duration_years`: `(end_date - start_date).days / 365.25`
   - `trimestres_estimated`: depends on period_type and annual_gross (see pension engine)
   - `overlaps_with`: detect overlapping periods (validation warning)

### Pydantic Schemas

3. **`CareerPeriodCreate`:**
   ```python
   class CareerPeriodCreate(BaseModel):
       period_type: Literal["cdi", "cdd", "interim", "ae", "eirl", "eurl",
                           "sasu", "apprenticeship", "internship",
                           "unemployment", "parental_leave",
                           "education", "foreign", "other"]
       start_date: date
       end_date: date | None = None
       employer_name: str | None = None
       job_title: str | None = None
       annual_gross: Decimal | None = None
       is_full_time: bool = True
       time_percentage: int = Field(default=100, ge=10, le=100)
       pension_regime: str | None = None  # Auto-derived if not set
       notes: str | None = None
   ```

4. **`CareerPeriodRead`** — adds computed fields:
   ```python
   class CareerPeriodRead(CareerPeriodCreate):
       id: UUID
       duration_years: float
       trimestres_estimated: int
       pension_regime: str
       # ... timestamps
   ```

### API Router

5. **Create `backend/app/routers/career.py`:**
   - `GET /api/career` — list all periods, ordered by start_date
   - `POST /api/career` — create a new period
   - `PUT /api/career/{id}` — update
   - `DELETE /api/career/{id}` — soft delete
   - `GET /api/career/summary` — returns:
     ```json
     {
       "total_periods": 3,
       "total_years_worked": 18.5,
       "total_trimestres_estimated": 74,
       "trimestres_required": 172,
       "trimestres_remaining": 98,
       "current_period": { "type": "ae", "since": "2020-03-01" },
       "pension_regimes": ["general", "ae"],
       "timeline": [
         { "year": 2012, "type": "cdi", "trimestres": 4, "salary": 35000 },
         { "year": 2013, "type": "cdi", "trimestres": 4, "salary": 37000 },
         ...
       ]
     }
     ```

### Auto-Detection

6. **Auto-derive pension regime from period_type:**
   ```python
   REGIME_MAP = {
       "cdi": "general",
       "cdd": "general",
       "interim": "general",
       "ae": "ae",
       "eirl": "tns",
       "eurl": "tns",
       "sasu": "general",  # Salaried director
       "apprenticeship": "general",
       "internship": None,  # No trimestres unless > 2 months
       "unemployment": "general",  # Trimestres validés on allocation
       "parental_leave": "general",  # Trimestres from AVPF
       "education": None,
       "foreign": "foreign",
       "other": None,
   }
   ```

7. **Auto-detect current AE period:** If the user has a profile with AE status and no career periods, auto-suggest creating an AE period starting from the current year (or prompt the user for the actual start date).

### Frontend

8. **New section in Identity page** (or a dedicated "Parcours" sub-section):
   - Timeline visualization showing career periods as horizontal bars
   - Color-coded by period type (CDI = teal, AE = emerald, unemployment = amber, etc.)
   - "Add a period" button with a form: type, dates, salary, full/part-time
   - Summary card: "X trimestres validés sur Y requis" with a progress bar
   - Each period is editable (click to expand, modify, save)

9. **i18n keys under `career.*`:**
   ```json
   {
     "career": {
       "title": "Parcours professionnel",
       "intro": "Votre historique d'emploi alimente le calcul de votre retraite. Chaque période validée compte.",
       "add": "Ajouter une période",
       "period_types": {
         "cdi": "CDI (contrat à durée indéterminée)",
         "cdd": "CDD (contrat à durée déterminée)",
         "ae": "Auto-entrepreneur / Micro-entreprise",
         "sasu": "SASU (président salarié)",
         "unemployment": "Chômage (ARE)",
         "parental_leave": "Congé parental"
       },
       "summary": {
         "trimestres": "{validated} trimestres validés sur {required}",
         "years_worked": "{years} ans d'activité",
         "current": "Situation actuelle : {type} depuis {date}"
       }
     }
   }
   ```

### Validation Rules

10. **Period overlap detection:** Warn (don't block) if two periods overlap. Some overlap is legitimate (CDI + AE side activity during notice period).

11. **Future periods:** Allow end_date in the future for planned transitions (e.g., "I plan to switch to SASU in 2028" — this connects to the existing status change simulation).

12. **Minimum data:** period_type and start_date are required. Everything else is optional but improves pension accuracy. If annual_gross is missing, the pension engine uses SMIC as a floor estimate.

## Acceptance Criteria

- [ ] Migration creates `career_periods` table
- [ ] CRUD endpoints work with auth and user scoping
- [ ] Pension regime auto-derived from period type
- [ ] Career summary endpoint returns trimestre count and timeline
- [ ] Frontend timeline visualization renders periods chronologically
- [ ] Summary card shows trimestre progress bar
- [ ] Overlap detection warns but doesn't block
- [ ] "Add period" form validates dates and salary
- [ ] At least 5 period types working (CDI, CDD, AE, unemployment, parental leave)
- [ ] Unit tests for CRUD, overlap detection, trimestre estimation
- [ ] LEARNINGS.md updated

## Notes

- The career history is self-declared — we're not connecting to URSSAF or info-retraite.fr. The user tells us their history and we estimate from it. Always label pension calculations as "estimation indicative."
- For Richard's case: 8-year CDI at, say, 35–45k€/year = 32 trimestres at regime général + higher SAM contribution. Combined with projected AE trimestres from 2020 onward, the pension picture changes dramatically.
- Unemployment periods (ARE) also validate trimestres — one trimestre per 50 days of allocation. This matters for people who had gaps between jobs.
- Parental leave generates trimestres through AVPF (Assurance Vieillesse des Parents au Foyer) — up to 8 free trimestres per child.
- The career timeline becomes a powerful visualization: the user sees their entire working life at a glance, with the projection engine picking up where it left off.
