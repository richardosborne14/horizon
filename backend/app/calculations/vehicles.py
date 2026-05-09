"""
Investment vehicle specifications — constants serving as reference data.

Seven French investment vehicles covering the spectrum from zero-risk
(Livret A) to medium-risk (PEA, SCPI) to retirement-locked (PER).

Each vehicle's specs are treated as constants (like AE rates). The user
data (balances and monthly contributions) lives in the InvestmentAllocation
model. The projection engine (Sprint 4) compounds these balances over
30 years using the rates defined here.

Rates are historical averages, not guarantees. The projection engine may
apply a "real return" adjustment (rate - inflation) to be conservative.
That logic lives in Sprint 4.
"""

from decimal import Decimal

VEHICLE_ORDER: list[str] = [
    "livret_a",
    "ldds",
    "av_euro",
    "av_uc",
    "pea",
    "scpi",
    "per",
]

VEHICLE_SPECS: dict[str, dict] = {
    "livret_a": {
        "label": "Livret A",
        "description": (
            "Épargne réglementée, capital garanti. "
            "Disponible à tout moment."
        ),
        "rate": Decimal("0.025"),
        "tax_free": True,
        "tax_rate": Decimal("0"),
        "ceiling": Decimal("22950"),
        "risk": "Aucun",
        "color": "#22d3ee",
        "liquidity": "Immédiate",
    },
    "ldds": {
        "label": "LDDS",
        "description": (
            "Comme le Livret A, plafonné plus bas. Capital garanti."
        ),
        "rate": Decimal("0.025"),
        "tax_free": True,
        "tax_rate": Decimal("0"),
        "ceiling": Decimal("12000"),
        "risk": "Aucun",
        "color": "#06b6d4",
        "liquidity": "Immédiate",
    },
    "av_euro": {
        "label": "Assurance Vie (fonds €)",
        "description": (
            "Capital garanti sur le fonds euros. Rendement faible mais sûr. "
            "Fiscalité avantageuse après 8 ans."
        ),
        "rate": Decimal("0.027"),
        "tax_free": False,
        "tax_rate": Decimal("0.172"),
        # PFU 17.2% prélèvements sociaux (after 8yr + 4600€ abattement)
        "ceiling": None,
        "risk": "Très faible",
        "color": "#a78bfa",
        "liquidity": "Quelques jours",
    },
    "av_uc": {
        "label": "Assurance Vie (UC)",
        "description": (
            "Unités de compte — actions, obligations, immobilier. "
            "Rendement potentiel plus élevé, capital non garanti."
        ),
        "rate": Decimal("0.060"),
        "tax_free": False,
        "tax_rate": Decimal("0.172"),
        "ceiling": None,
        "risk": "Moyen",
        "color": "#8b5cf6",
        "liquidity": "Quelques jours",
    },
    "pea": {
        "label": "PEA",
        "description": (
            "Plan d'Épargne en Actions. Exonéré d'IR après 5 ans "
            "(17,2% PS uniquement). Actions européennes."
        ),
        "rate": Decimal("0.070"),
        "tax_free": False,
        "tax_rate": Decimal("0.172"),
        "ceiling": Decimal("150000"),
        "risk": "Moyen-élevé",
        "color": "#f59e0b",
        "liquidity": "5 ans pour avantage fiscal",
    },
    "scpi": {
        "label": "SCPI",
        "description": (
            "Pierre-papier. Revenus immobiliers sans gestion. "
            "Rendement régulier, liquidité limitée."
        ),
        "rate": Decimal("0.045"),
        "tax_free": False,
        "tax_rate": Decimal("0.300"),
        # IR + PS on revenus fonciers
        "ceiling": None,
        "risk": "Moyen",
        "color": "#10b981",
        "liquidity": "Plusieurs mois",
    },
    "per": {
        "label": "PER (Plan Épargne Retraite)",
        "description": (
            "Versements déductibles du revenu imposable. "
            "Bloqué jusqu'à la retraite (sauf exceptions). "
            "Fiscalisé à la sortie."
        ),
        "rate": Decimal("0.040"),
        "tax_free": False,
        "tax_rate": Decimal("0.172"),
        "ceiling": None,
        "risk": "Faible-moyen",
        "color": "#ec4899",
        "liquidity": "Bloqué jusqu'à la retraite",
        "tax_deductible": True,
    },
}


def get_vehicle_spec(vehicle_key: str) -> dict | None:
    """Return the spec dict for a given vehicle key, or None if invalid."""
    return VEHICLE_SPECS.get(vehicle_key)


def get_all_vehicle_keys() -> list[str]:
    """Return all valid vehicle keys in display order."""
    return list(VEHICLE_ORDER)


def validate_vehicle_key(vehicle_key: str) -> bool:
    """Check whether a vehicle key is valid."""
    return vehicle_key in VEHICLE_SPECS