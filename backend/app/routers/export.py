"""
PDF export router (TASK-5.9) — generates a downloadable PDF of the user's projection.

Uses fpdf2 for lightweight, pure-Python PDF generation.
Three-page document: executive summary, detailed table, configuration summary.
"""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.calculations.constants import INFLATION_SCALES
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.routers.projection import _assemble_input
from app.calculations.projection import project_timeline, compute_summary
from app.calculations.readiness import compute_readiness_score
from app.calculations.insights import generate_insights

try:
    from fpdf import FPDF
    HAS_FPDF = True
except ImportError:
    HAS_FPDF = False

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projection", tags=["export"])


def _fmt_euro(value) -> str:
    """Format a value as euro string."""
    if isinstance(value, str):
        value = float(value)
    if isinstance(value, Decimal):
        value = float(value)
    n = int(value)
    if n < 0:
        return f"-{_format_abs(abs(n))}€"
    return _format_abs(n) + "€"


def _format_abs(n: int) -> str:
    s = f"{n}"
    result = ""
    for i, ch in enumerate(reversed(s)):
        if i > 0 and i % 3 == 0:
            result = " " + result
        result = ch + result
    return result


@router.get("/export")
async def export_projection_pdf(
    scale: str = Query(default="moderate"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Generate a downloadable PDF of the user's projection.

    Three pages:
      1. Executive summary with key metrics
      2. Detailed projection table (every 5 years)
      3. Configuration summary (savings, expenses, projects, insights)
    """
    if not HAS_FPDF:
        raise HTTPException(
            status_code=500,
            detail="PDF generation not available (fpdf2 not installed)",
        )

    # Get profile for user name and birth date
    from app.models.profile import UserProfile
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == str(current_user.id))
    )
    profile = profile_result.scalar_one_or_none()

    if profile is None or profile.birth_date is None:
        raise HTTPException(
            status_code=422,
            detail="Profil incomplet pour l'export",
        )

    # Compute projection
    try:
        inp = await _assemble_input(str(current_user.id), scale, db)
        timeline = project_timeline(inp)
        summary = compute_summary(timeline)
    except Exception as exc:
        logger.exception("Failed to compute projection for PDF export")
        raise HTTPException(status_code=500, detail="Erreur de calcul") from exc

    # Compute readiness and insights
    allocations_list = [
        {"vehicle_key": vk, "balance": float(a.get("balance", 0)),
         "monthly": float(a.get("monthly", 0))}
        for vk, a in inp.allocations.items()
    ]
    profile_data = {
        "monthly_gross": float(inp.monthly_gross),
        "growth_rate": float(inp.growth_rate),
        "target_age": inp.target_age,
        "current_age": inp.current_age,
    }
    insights = generate_insights(timeline, summary, profile_data, allocations_list)
    readiness = compute_readiness_score(
        timeline, summary, profile_data, allocations_list, inp.monthly_revenue_goal
    )

    # Build PDF
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # ── Page 1: Executive Summary ──────────────────────────────────
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "HORIZON — Projection Patrimoniale", ln=True, align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, f"Genere le {date.today().strftime('%d/%m/%Y')} — {current_user.email}", ln=True, align="C")
    pdf.ln(8)

    # Profile snapshot
    today = date.today()
    current_age = today.year - profile.birth_date.year
    if (today.month, today.day) < (profile.birth_date.month, profile.birth_date.day):
        current_age -= 1

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Profil", ln=True)
    pdf.set_font("Courier", "", 9)
    pdf.cell(0, 5, f"Age actuel: {current_age} ans", ln=True)
    pdf.cell(0, 5, f"Age de retraite cible: {profile.target_retirement_age} ans", ln=True)
    pdf.cell(0, 5, f"Statut: {profile.ae_activity_type or 'AE'}", ln=True)
    pdf.cell(0, 5, f"CA mensuel: {_fmt_euro(profile.monthly_gross_ca or 0)}", ln=True)
    pdf.cell(0, 5, f"Echelle: {scale}", ln=True)
    pdf.ln(6)

    # Key metrics
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Indicateurs Cles", ln=True)
    pdf.set_font("Courier", "B", 12)
    wealth = Decimal(summary.get("final_wealth", "0"))
    passive = Decimal(summary.get("final_passive_monthly", "0"))
    pdf.set_font("Courier", "", 10)
    pdf.cell(90, 7, f"Patrimoine a {profile.target_retirement_age} ans:", ln=0)
    pdf.set_font("Courier", "B", 10)
    pdf.cell(0, 7, _fmt_euro(wealth), ln=True)
    pdf.set_font("Courier", "", 10)
    pdf.cell(90, 7, "Revenu passif mensuel:", ln=0)
    pdf.set_font("Courier", "B", 10)
    pdf.cell(0, 7, _fmt_euro(passive) + "/mois", ln=True)
    pdf.set_font("Courier", "", 10)
    pdf.cell(90, 7, "Score de preparation retraite:", ln=0)
    pdf.set_font("Courier", "B", 10)
    pdf.cell(0, 7, f"{readiness.score}/100 — {readiness.label}", ln=True)
    exhaustion = summary.get("wealth_exhaustion_age")
    if exhaustion:
        pdf.set_font("Courier", "", 10)
        pdf.cell(90, 7, "Epuisement du patrimoine:", ln=0)
        pdf.set_font("Courier", "B", 10)
        pdf.cell(0, 7, f"A {exhaustion} ans", ln=True)
    pdf.ln(6)

    # Top 3 insights
    if insights:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Recommandations", ln=True)
        for ins in insights[:3]:
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 5, ins.title, ln=True)
            pdf.set_font("Helvetica", "", 8)
            pdf.multi_cell(0, 4, ins.description)
            pdf.ln(2)

    # ── Page 2: Detailed Projection Table ──────────────────────────
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Projection Detaillee", ln=True)
    pdf.ln(4)

    # Filter timeline for display (every 5 years + last)
    display_timeline = [t for i, t in enumerate(timeline) if i % 5 == 0 or i == len(timeline) - 1]

    # Table header
    pdf.set_font("Helvetica", "B", 7)
    col_w = [22, 14, 24, 24, 24, 24, 24]
    headers = ["An", "Age", "CA brut", "Cotis.", "Vie", "Net", "Patrim."]
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 5, h, border=1, align="C")
    pdf.ln()

    # Table rows
    pdf.set_font("Courier", "", 7)
    for t in display_timeline:
        # Extract values from YearProjection dataclass (or dict fallback)
        is_dict = isinstance(t, dict)
        def _v(field: str) -> str:
            raw = t.get(field, "0") if is_dict else getattr(t, field, "0")
            return str(raw) if raw is not None else "0"

        year = int(_v("year") or "0")
        age = int(_v("age") or "0")
        gross = _v("gross_annual")
        charges = _v("charges")
        base_exp = _v("base_expenses")
        net = _v("net_annual")
        wealth = _v("total_wealth")

        row = [
            str(year), str(age),
            _fmt_euro(gross), _fmt_euro(charges),
            _fmt_euro(base_exp), _fmt_euro(net), _fmt_euro(wealth)
        ]
        for i, val in enumerate(row):
            pdf.cell(col_w[i], 4, val[:12], border=1, align="R")
        pdf.ln()

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 7)
    pdf.cell(0, 4, f"Echelle: {scale} — Simulation, ne constitue pas un conseil financier", ln=True, align="C")

    # ── Page 3: Configuration Summary ─────────────────────────────
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Configuration", ln=True)
    pdf.ln(4)

    # Savings
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Epargne", ln=True)
    pdf.set_font("Courier", "", 8)
    from app.calculations.vehicles import VEHICLE_SPECS
    for vk, a in inp.allocations.items():
        spec = VEHICLE_SPECS.get(vk, {})
        label = spec.get("label", vk)
        bal = a.get("balance", Decimal("0"))
        mon = a.get("monthly", Decimal("0"))
        pdf.cell(0, 5, f"{label}: {_fmt_euro(bal)} (+ {_fmt_euro(mon)}/mois)", ln=True)
    pdf.ln(4)

    # Expenses
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Charges mensuelles", ln=True)
    pdf.set_font("Courier", "", 8)
    pdf.cell(0, 5, f"Total: {_fmt_euro(inp.monthly_expenses_total)}/mois", ln=True)
    pdf.ln(4)

    # Disclaimer footer
    pdf.set_y(-20)
    pdf.set_font("Helvetica", "I", 7)
    pdf.cell(0, 5, "Simulation genere par Horizon (horizonapp.fr) — Ne constitue pas un conseil financier,", ln=True, align="C")
    pdf.cell(0, 5, "fiscal ou juridique. Consultez un professionnel pour toute decision.", ln=True, align="C")

    # Output PDF
    pdf_bytes = pdf.output()
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=horizon-projection-{date.today().isoformat()}.pdf"
        },
    )