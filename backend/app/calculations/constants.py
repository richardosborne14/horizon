"""
Economic scenario constants — inflation scales and revenue growth presets.

These are reference data served via API so the frontend can render
selector UIs and preview calculations. The backend projection engine
uses these for computation.

All values are Decimal — never float.
"""

from decimal import Decimal


# ── Inflation scales ───────────────────────────────────────────────────────────
# Three economic scenarios: optimistic, moderate, pessimistic.
# inflation = general price inflation
# cost_living = cost of living growth (slightly higher, reflects lifestyle creep)
# Descriptions are in French — displayed directly in the UI.

INFLATION_SCALES: dict = {
    "optimistic": {
        "label": "Optimiste",
        "emoji": "☀️",
        "inflation": Decimal("0.018"),
        "cost_living": Decimal("0.020"),
        "description": "Inflation maîtrisée, économie stable. Scénario le plus favorable.",
        "color": "emerald",
    },
    "moderate": {
        "label": "Modéré",
        "emoji": "⛅",
        "inflation": Decimal("0.025"),
        "cost_living": Decimal("0.030"),
        "description": "Inflation moyenne historique. Le scénario par défaut.",
        "color": "amber",
    },
    "pessimistic": {
        "label": "Pessimiste",
        "emoji": "🌧️",
        "inflation": Decimal("0.035"),
        "cost_living": Decimal("0.045"),
        "description": "Inflation élevée, coût de la vie en hausse. Si le monde part en vrille.",
        "color": "rose",
    },
}

# ── Growth presets ─────────────────────────────────────────────────────────────
# Four revenue growth presets for the CA projection.
# conservative: 1%/yr — stability, no major changes
# moderate: 3%/yr — natural growth, word-of-mouth
# ambitious: 6%/yr — active prospecting, new services
# custom: user-defined rate

GROWTH_PRESETS: dict = {
    "conservative": {
        "label": "Prudent",
        "rate": Decimal("0.01"),
        "description": "Stabilité. Vous gardez vos clients existants, pas de gros changements.",
    },
    "moderate": {
        "label": "Modéré",
        "rate": Decimal("0.03"),
        "description": "Croissance naturelle : bouche à oreille, légère augmentation des tarifs chaque année.",
    },
    "ambitious": {
        "label": "Ambitieux",
        "rate": Decimal("0.06"),
        "description": "Nouveaux services, prospection active, montée en gamme. Demande un effort constant.",
    },
    "custom": {
        "label": "Personnalisé",
        "rate": None,
        "description": "Vous définissez votre propre taux de croissance annuel.",
    },
}


# ── Public functions ───────────────────────────────────────────────────────────

def get_growth_rate(preset: str, custom_rate: Decimal | None = None) -> Decimal:
    """Resolve the effective growth rate from a preset key.

    Args:
        preset: One of 'conservative', 'moderate', 'ambitious', 'custom'.
        custom_rate: Required when preset='custom'. Used as-is.

    Returns:
        The annual growth rate as a Decimal.

    Raises:
        ValueError: If preset is unknown.
    """
    if preset == "custom":
        return custom_rate if custom_rate is not None else Decimal("0.03")

    p = GROWTH_PRESETS.get(preset)
    if p is None or p["rate"] is None:
        raise ValueError(
            f"Unknown growth preset: {preset!r}. "
            f"Valid presets: {list(GROWTH_PRESETS.keys())}"
        )
    return Decimal(str(p["rate"]))


def get_inflation_scale(scale: str) -> dict:
    """Return a single inflation scale by key.

    Args:
        scale: 'optimistic', 'moderate', or 'pessimistic'.

    Returns:
        Dict with label, emoji, inflation, cost_living, description, color.

    Raises:
        ValueError: If scale is unknown.
    """
    s = INFLATION_SCALES.get(scale)
    if s is None:
        raise ValueError(
            f"Unknown inflation scale: {scale!r}. "
            f"Valid scales: {list(INFLATION_SCALES.keys())}"
        )
    return s