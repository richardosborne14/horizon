"""
Simplified French income tax (IR) calculation.

Uses the 2024 barème progressif with quotient familial.
This is a first approximation:
- Does not model prélèvement à la source mechanics
- Does not model specific deductions beyond standard 10%
- Does not model micro-BIC/BNC abattement interaction with IR
- DOES model quotient familial correctly (divide by parts, apply barème, multiply back)
- DOES model plafonnement du quotient familial

Sprint 7 (TASK-7.12): First tax accuracy layer for the projection engine.
"""

from decimal import Decimal, ROUND_HALF_UP


# ── 2024 IR barème (tranches marginales) ──────────────────────────────────────

IR_TRANCHES_2024 = [
    (Decimal("11294"), Decimal("0")),       # 0% up to 11,294€
    (Decimal("28797"), Decimal("0.11")),     # 11% from 11,294 to 28,797€
    (Decimal("82341"), Decimal("0.30")),     # 30% from 28,797 to 82,341€
    (Decimal("177106"), Decimal("0.41")),    # 41% from 82,341 to 177,106€
    (None, Decimal("0.45")),                 # 45% above 177,106€
]

# AE micro-fiscal abattements (forfaitaires)
AE_ABATTEMENTS = {
    "bic_vente": Decimal("0.71"),     # 71% abattement
    "bic_service": Decimal("0.50"),   # 50%
    "bic_heberg": Decimal("0.50"),    # 50%
    "bnc": Decimal("0.34"),           # 34%
    "bnc_non_reglementee": Decimal("0.34"),  # same as bnc
}

# Standard 10% deduction for salaries (frais professionnels)
SALARY_DEDUCTION_RATE = Decimal("0.10")
SALARY_DEDUCTION_MIN = Decimal("495")
SALARY_DEDUCTION_MAX = Decimal("14171")

# Plafonnement du quotient familial: max advantage per half-part above 2 parts
MAX_ADVANTAGE_PER_HALF_PART = Decimal("1759")

# CESU: 50% credit, capped at 6,000€
CESU_CREDIT_RATE = Decimal("0.50")
CESU_CREDIT_CAP = Decimal("6000")

# Charity: 66% reduction on donations (within limits)
CHARITY_RATE = Decimal("0.66")


# ── Public API ────────────────────────────────────────────────────────────────


def compute_ir(
    ae_ca_annual: Decimal,
    ae_activity_type: str,
    salary_annual: Decimal = Decimal("0"),
    other_income_annual: Decimal = Decimal("0"),
    tax_parts: Decimal = Decimal("1"),
    cesu_credit: Decimal = Decimal("0"),
    charity_reduction: Decimal = Decimal("0"),
    has_vl: bool = False,
) -> dict:
    """Compute annual IR for a household.

    Args:
        ae_ca_annual: Auto-entrepreneur CA brut annuel.
        ae_activity_type: bic_vente, bic_service, bnc, bic_heberg, bnc_non_reglementee.
        salary_annual: Spouse/partner salary brut annuel (if employed).
        other_income_annual: Dividends, rental, etc. (already net of deductions).
        tax_parts: Quotient familial parts (1=seul, 2=couple, +0.5/enfant, +1 au 3ème).
        cesu_credit: CESU tax credit to apply (50% of CESU expenses, max 6000€).
        charity_reduction: Charity tax reduction (66% of donations).
        has_vl: If True, AE income is already taxed via versement libératoire → exclude from IR.

    Returns:
        {
            "revenu_imposable": str — total taxable income,
            "ir_brut": str — IR before credits,
            "ir_net": str — IR after credits,
            "taux_effectif": str — effective rate as decimal,
            "taux_marginal": str — marginal rate as decimal,
            "monthly_ir": str — monthly IR amount,
        }
    """
    # Step 1: Compute revenu imposable

    # AE income: apply micro-fiscal abattement (unless VL)
    if has_vl:
        ae_taxable = Decimal("0")  # VL = already taxed at flat rate, excluded from IR
    else:
        abattement = AE_ABATTEMENTS.get(ae_activity_type, Decimal("0.34"))
        ae_taxable = ae_ca_annual * (Decimal("1") - abattement)

    # Salary income: 10% deduction with min/max
    if salary_annual > 0:
        salary_deduction = max(
            SALARY_DEDUCTION_MIN,
            min(salary_annual * SALARY_DEDUCTION_RATE, SALARY_DEDUCTION_MAX),
        )
        salary_taxable = max(Decimal("0"), salary_annual - salary_deduction)
    else:
        salary_taxable = Decimal("0")

    # Total revenu imposable
    revenu_imposable = ae_taxable + salary_taxable + other_income_annual

    # Step 2: Apply quotient familial
    if tax_parts <= 0:
        tax_parts = Decimal("1")
    revenu_par_part = revenu_imposable / tax_parts

    # Step 3: Apply barème to revenu_par_part
    ir_par_part = _apply_bareme(revenu_par_part)

    # Step 4: Multiply back by parts
    ir_brut = ir_par_part * tax_parts

    # Step 5: Apply plafonnement du quotient familial
    # Maximum advantage per half-part above 2 = 1,759€
    # For parts > 2: cap the advantage
    extra_half_parts = max(Decimal("0"), (tax_parts - Decimal("2")) * Decimal("2"))
    if extra_half_parts > 0:
        # IR with only 2 parts (couple sans enfants)
        ir_sans_enfants = _apply_bareme(revenu_imposable / Decimal("2")) * Decimal("2")
        advantage = ir_sans_enfants - ir_brut
        max_advantage = extra_half_parts * MAX_ADVANTAGE_PER_HALF_PART
        if advantage > max_advantage:
            ir_brut = ir_sans_enfants - max_advantage

    # Step 6: Apply credits and reductions
    ir_net = max(Decimal("0"), ir_brut - cesu_credit - charity_reduction)

    # Effective and marginal rates
    if revenu_imposable > 0:
        taux_effectif = (ir_net / revenu_imposable).quantize(Decimal("0.0001"))
    else:
        taux_effectif = Decimal("0")
    taux_marginal = _marginal_rate(revenu_par_part)

    return {
        "revenu_imposable": str(revenu_imposable.quantize(Decimal("0.01"))),
        "ir_brut": str(ir_brut.quantize(Decimal("0.01"))),
        "ir_net": str(ir_net.quantize(Decimal("0.01"))),
        "taux_effectif": str(taux_effectif),
        "taux_marginal": str(taux_marginal),
        "monthly_ir": str((ir_net / Decimal("12")).quantize(Decimal("0.01"))),
    }


# ── Internal helpers ──────────────────────────────────────────────────────────


def _apply_bareme(revenu_par_part: Decimal) -> Decimal:
    """Apply the progressive barème to income per part.

    Walks through the 2024 tranches, accumulating tax for each bracket.

    Args:
        revenu_par_part: Taxable income divided by quotient familial parts.

    Returns:
        Total IR (impôt brut) for one part.
    """
    ir = Decimal("0")
    prev_threshold = Decimal("0")

    for threshold, rate in IR_TRANCHES_2024:
        if threshold is None:
            # Top tranche: rate applies to everything above prev_threshold
            ir += (revenu_par_part - prev_threshold) * rate
            break
        elif revenu_par_part <= threshold:
            # Income falls within this tranche
            ir += (revenu_par_part - prev_threshold) * rate
            break
        else:
            # Income exceeds this tranche — tax the full bracket
            ir += (threshold - prev_threshold) * rate
            prev_threshold = threshold

    return ir


def _marginal_rate(revenu_par_part: Decimal) -> Decimal:
    """Return the marginal tax rate for the given income per part.

    Args:
        revenu_par_part: Taxable income divided by quotient familial parts.

    Returns:
        The marginal rate as a Decimal (e.g., Decimal("0.30") for 30%).
    """
    for threshold, rate in IR_TRANCHES_2024:
        if threshold is None or revenu_par_part <= threshold:
            return rate
    return Decimal("0.45")  # fallback: top rate