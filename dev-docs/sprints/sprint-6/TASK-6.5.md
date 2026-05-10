# TASK-6.5: Net Worth Snapshot

**Status:** TODO
**Sprint:** 6
**Priority:** P1 (high)
**Est. effort:** 2 hr
**Dependencies:** None

## Context

The projection engine starts from investment balances (750€ total) but doesn't know about the user's complete financial picture: cash in current accounts, property value, outstanding debts beyond loans, or other assets. Without this, the "Patrimoine" figure is only investment wealth, not true net worth.

A freelancer who owns a house worth 200k€ with 72k€ remaining mortgage has a net property equity of 128k€ — that's a massive asset the tool doesn't know about. It doesn't need to generate income (unless rented), but it changes the user's actual financial position and potentially their strategy (sell and downsize at retirement?).

## Requirements

### Data Model

1. **Create `backend/app/models/net_worth.py`:**

   ```python
   class NetWorthSnapshot(Base):
       __tablename__ = "net_worth_snapshots"

       id = Column(UUID, primary_key=True, default=uuid4)
       user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

       # Liquid assets (not in investment vehicles)
       cash_current_accounts = Column(Numeric(12, 2), default=0)    # Compte courant
       cash_savings_other = Column(Numeric(12, 2), default=0)       # Other savings not in tracked vehicles

       # Property
       property_primary_value = Column(Numeric(12, 2), default=0)   # Résidence principale estimated value
       property_other_value = Column(Numeric(12, 2), default=0)     # Other property
       # Mortgage balance pulled from loans model (TASK-6.3)

       # Other assets
       business_value = Column(Numeric(12, 2), default=0)           # Valeur du fonds de commerce / clientèle
       vehicle_value = Column(Numeric(12, 2), default=0)            # Cars, estimated resale
       other_assets = Column(Numeric(12, 2), default=0)
       other_assets_label = Column(String(200), nullable=True)

       # Debts (beyond tracked loans)
       other_debts = Column(Numeric(12, 2), default=0)              # Family loans, tax debt, etc.
       other_debts_label = Column(String(200), nullable=True)

       snapshot_date = Column(Date, nullable=False)                  # When this was last updated
       created_at = Column(DateTime(timezone=True), server_default=func.now())
       updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
   ```

2. **Computed fields:**
   ```python
   total_assets = (cash_current_accounts + cash_savings_other +
                   investment_balances +  # from investment allocations
                   property_primary_value + property_other_value +
                   business_value + vehicle_value + other_assets)

   total_debts = (loan_balances +  # from loans model
                  other_debts)

   net_worth = total_assets - total_debts
   ```

### API

3. **`GET/PUT /api/net-worth`** — single snapshot per user (upsert pattern)
4. **`GET /api/net-worth/summary`** — computed net worth with breakdown

### Frontend

5. **New card on Runway page or a dedicated "Bilan" section:**
   - Donut chart: assets vs debts
   - Breakdown table: liquid / investments / property / other
   - Net worth headline number
   - "Last updated" with prompt to refresh quarterly

6. **Simple input form:**
   - Cash in current accounts
   - Property value (résidence principale)
   - Other assets
   - Other debts
   - Notes field

### Projection Integration

7. **Cash reserves as emergency buffer:**
   - The readiness score (Task 5.5) uses liquid savings for the "buffer adequacy" component
   - Cash in current accounts should be included alongside Livret A/LDDS

8. **Property equity as retirement option:**
   - Not modeled as income (would need a sale/downsize scenario)
   - But displayed in the net worth view to give the user the full picture
   - Future enhancement: "If you sell and downsize at retirement, the 128k€ equity extends your runway by X years"

## Acceptance Criteria

- [ ] Net worth snapshot saves and loads correctly
- [ ] Computed net worth includes investment balances and loan balances from other models
- [ ] Frontend renders net worth breakdown
- [ ] Cash reserves feed into readiness score buffer calculation
- [ ] API returns complete net worth summary
- [ ] Unit tests for computation
- [ ] LEARNINGS.md updated
