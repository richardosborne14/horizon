# TASK-6.3: Loan & Mortgage Lifecycle

**Status:** TODO
**Sprint:** 6
**Priority:** P0 (critical — the 590€/month "credit" is treated as permanent)
**Est. effort:** 2.5 hr
**Dependencies:** None

## Context

Richard's expenses include "Crédits en cours: 590€/mois" — a flat monthly expense treated as permanent across the entire 30-year projection. If this is a mortgage, it probably ends in 2032 or 2038 or whenever. When it does, 7,080€/year disappears from expenses overnight. That's one of the single largest financial events in the projection, and the tool completely ignores it.

This task replaces the flat "credit" expense category with a proper loan model. Each loan has a start date, end date (or remaining months), monthly payment, and optionally the original amount and rate. The projection engine knows when each loan terminates and drops the expense accordingly.

## Requirements

### Data Model

1. **Create `backend/app/models/loan.py`:**

   ```python
   class Loan(Base):
       __tablename__ = "loans"

       id = Column(UUID, primary_key=True, default=uuid4)
       user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

       # Loan identity
       label = Column(String(200), nullable=False)   # "Crédit immobilier", "Prêt auto", "Prêt étudiant"
       loan_type = Column(String(30), nullable=False)
       # "mortgage", "auto", "consumer", "student", "business", "other"

       # Financial terms
       monthly_payment = Column(Numeric(10, 2), nullable=False)  # What you pay per month
       start_date = Column(Date, nullable=False)
       end_date = Column(Date, nullable=True)         # null → compute from remaining_months
       remaining_months = Column(Integer, nullable=True) # Alternative to end_date
       original_amount = Column(Numeric(12, 2), nullable=True)   # Optional: total borrowed
       interest_rate = Column(Numeric(5, 4), nullable=True)      # Optional: annual rate
       remaining_balance = Column(Numeric(12, 2), nullable=True) # Optional: what's still owed

       # Insurance (assurance emprunteur) — common for French mortgages
       insurance_monthly = Column(Numeric(8, 2), nullable=True, server_default="0")

       # What happens when the loan ends
       # "freed" → payment stops, amount becomes available for savings
       # "refinanced" → payment continues at potentially different amount
       end_action = Column(String(20), nullable=False, server_default="'freed'")

       # Metadata
       notes = Column(String(500), nullable=True)
       is_active = Column(Boolean, nullable=False, server_default="true")
       created_at = Column(DateTime(timezone=True), server_default=func.now())
       updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
   ```

2. **Compute end_date** if not provided:
   ```python
   if end_date is None and remaining_months is not None:
       end_date = today + relativedelta(months=remaining_months)
   ```

### API

3. **Create `backend/app/routers/loans.py`:**
   - `GET /api/loans` — list all active loans
   - `POST /api/loans` — create
   - `PUT /api/loans/{id}` — update
   - `DELETE /api/loans/{id}` — soft delete
   - `GET /api/loans/summary` — returns:
     ```json
     {
       "total_monthly": 590,
       "total_remaining": 85000,
       "loans": [
         {
           "label": "Crédit immobilier",
           "monthly": 500,
           "ends": "2035-03-15",
           "years_remaining": 9,
           "remaining_balance": 72000
         },
         {
           "label": "Prêt auto",
           "monthly": 90,
           "ends": "2028-06-01",
           "years_remaining": 2,
           "remaining_balance": 2160
         }
       ],
       "timeline": [
         { "year": 2026, "total_monthly": 590 },
         { "year": 2028, "total_monthly": 500 },   // Auto loan ends
         { "year": 2035, "total_monthly": 0 }       // Mortgage ends
       ]
     }
     ```

### Projection Engine Integration

4. **Replace the flat "credit" expense** in the projection engine:

   Currently, the "credit" field in monthly_expenses JSONB is included in `base_expenses` and inflated every year. This is wrong for loans — loan payments are fixed nominal amounts (they don't inflate).

   **New approach:**
   ```python
   # In the projection loop, for each year:
   
   # 1. Compute base expenses WITHOUT the "credit" category
   base_exp = (monthly_expenses_total - credit_monthly) * 12 * cost_factor
   
   # 2. Add loan payments separately (NOT inflation-adjusted)
   loan_exp = Decimal("0")
   for loan in inp.loans:
       if loan["start_date"] <= year_date <= loan["end_date"]:
           loan_exp += loan["monthly_payment"] * 12
       # Insurance might inflate slightly
       if loan.get("insurance_monthly"):
           loan_exp += loan["insurance_monthly"] * 12
   
   # 3. Total outgoing includes both
   total_outgoing = base_exp + loan_exp + kid_exp + ...
   ```

   This is a significant accuracy improvement: a 590€/month mortgage is 590€ in 2026 and 590€ in 2035 (nominal, fixed). The current model inflates it by cost_living_rate, making it 590 × 1.03^9 = 770€ by 2035. That's 2,160€/year of overestimated expenses.

5. **Loan termination event in the timeline:**
   - When a loan ends, the projection should record it as a "freed capacity" event
   - The insights engine (Task 5.4) should detect: "Your mortgage ends in 2035. Redirecting 500€/month to PEA from that point would add X€ to your patrimoine."

### Frontend

6. **New section: "Crédits & Emprunts"** — either as a sub-section of Charges or a separate card:
   - Each loan as a card with: label, monthly payment, end date, remaining balance
   - Visual timeline showing when each loan ends
   - Total monthly payment at the top
   - "Add a loan" button

7. **Migration path from flat "credit" field:**
   - If the user has a non-zero "credit" in monthly_expenses but no loans configured, show a prompt: "Vous avez 590€/mois de crédits. Détaillez vos emprunts pour une projection plus précise."
   - The prompt helps the user migrate from the flat field to structured loans
   - Don't break backwards compatibility — if no loans exist, fall back to the flat credit field (inflated, as before)

8. **Expense page update:**
   - The "Crédits en cours" field in the expense grid should show a note: "Détaillez vos emprunts ci-dessous pour plus de précision" with a link to the loans section
   - If loans are configured, the credit field should be grayed out with a note: "Géré via vos emprunts détaillés"

### Validation

9. **Sanity checks:**
   - `monthly_payment > 0`
   - `end_date > start_date` (if both provided)
   - `remaining_months > 0` (if provided)
   - Warn if `monthly_payment * remaining_months` differs significantly from `remaining_balance` (suggests inconsistent data)

## Acceptance Criteria

- [ ] Migration creates `loans` table
- [ ] CRUD endpoints work with auth
- [ ] Loan end dates computed correctly from remaining_months
- [ ] Projection engine uses loan data instead of flat "credit" field when loans exist
- [ ] Loan payments are NOT inflation-adjusted in the projection
- [ ] Loan payments drop to zero after end_date in projection timeline
- [ ] Loan summary endpoint returns monthly total and termination timeline
- [ ] Frontend renders loan cards with end dates
- [ ] Backward compatible: flat credit field used if no loans configured
- [ ] Migration prompt shown when credit > 0 and no loans exist
- [ ] Insight fires when a loan is about to end ("redirect freed capacity")
- [ ] Unit tests: loan active/ended per year, non-inflation behavior, summary
- [ ] LEARNINGS.md updated

## Notes

- For Richard: the 590€/mois is almost certainly a mix of mortgage + possibly a smaller loan. Splitting it into individual loans with end dates will dramatically change the projection from ~2032 onward. If the mortgage ends at age 49, that's 21 years of retirement planning with zero loan payments — a completely different picture.
- French mortgages typically have assurance emprunteur (borrower insurance) at 0.1–0.4% of the outstanding balance. This decreases over time as the balance drops. For MVP, model it as a flat monthly amount. A future enhancement could compute it from the outstanding balance.
- The insight about redirecting freed capacity is perhaps the single most actionable piece of advice the tool can give. "Your mortgage ends in 2035. If you redirect that 500€/mois to PEA, your patrimoine at 70 increases by 147,000€." That's a life-changing insight.
