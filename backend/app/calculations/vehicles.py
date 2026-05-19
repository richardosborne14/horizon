"""
Investment vehicle specifications — constants serving as reference data.

Eleven French investment vehicles covering the spectrum from zero-risk
(Livret A, LEP) to medium-risk (PEA, SCPI) to retirement-locked (PER)
and taxable (CTO).

TASK-8.9 extends from 7 to 11 vehicles: adds LEP, PEL, CTO, PEE.

Each vehicle's specs are treated as constants (like AE rates). The user
data (balances and monthly contributions) lives in the InvestmentAllocation
model. The projection engine (Sprint 4) compounds these balances over
30 years using the rates defined here.

Rates are historical averages, not guarantees. The projection engine may
apply a "real return" adjustment (rate - inflation) to be conservative.
That logic lives in Sprint 4.
"""

from decimal import Decimal

# Display order for the savings tab — grouped by category:
#   liquid (Livret A → PEL)
#   assurance-vie
#   bourse (PEA, CTO)
#   immobilier (SCPI)
#   retraite (PER, PEE)
VEHICLE_ORDER: list[str] = [
    "livret_a",
    "ldds",
    "lep",
    "pel",
    "av_euro",
    "av_uc",
    "pea",
    "cto",
    "scpi",
    "per",
    "pee",
]

VEHICLE_SPECS: dict[str, dict] = {
    "livret_a": {
        "label": "Livret A",
        "description": (
            "Épargne réglementée, capital garanti. "
            "Disponible à tout moment."
        ),
        "tax_free": True,
        "tax_rate": Decimal("0"),
        "ceiling": Decimal("22950"),
        "overflow_target": "ldds",  # redirect excess to LDDS
        "risk": "Aucun",
        "color": "#22d3ee",
        "liquidity": "Immédiate",
        # Scale-based rates — government-set, revised biannually (1 Feb / 1 Aug).
        # Taux actuel : 1,5 % (depuis le 1er fév. 2026).
        # Pessimistic: near statutory floor. Moderate: current rate. Optimistic: high-inflation env.
        "rates_by_scale": {
            "pessimistic": Decimal("0.010"),
            "moderate": Decimal("0.015"),
            "optimistic": Decimal("0.025"),
        },
        "rate_note": (
            "Taux fixé par décret gouvernemental, révisé au 1er fév. et 1er août. "
            "Taux actuel : 1,5 % (depuis le 1er fév. 2026)."
        ),
    },
    "ldds": {
        "label": "LDDS",
        "description": (
            "Comme le Livret A, plafonné plus bas. Capital garanti."
        ),
        "tax_free": True,
        "tax_rate": Decimal("0"),
        "ceiling": Decimal("12000"),
        "overflow_target": "av_euro",  # redirect excess to AV euro
        "risk": "Aucun",
        "color": "#06b6d4",
        "liquidity": "Immédiate",
        # LDDS rate always equals Livret A rate (government decree).
        "rates_by_scale": {
            "pessimistic": Decimal("0.010"),
            "moderate": Decimal("0.015"),
            "optimistic": Decimal("0.025"),
        },
        "rate_note": (
            "Taux toujours identique au Livret A, fixé par décret gouvernemental. "
            "Taux actuel : 1,5 % (depuis le 1er fév. 2026)."
        ),
    },
    "lep": {
        "label": "LEP — Livret d'Épargne Populaire",
        "description": (
            "Meilleur taux garanti pour l'épargne de précaution. "
            "Soumis à conditions de revenus. Capital garanti."
        ),
        "tax_free": True,
        "tax_rate": Decimal("0"),
        "ceiling": Decimal("10000"),
        "overflow_target": "livret_a",
        "risk": "Aucun",
        "color": "#86efac",
        "liquidity": "Immédiate",
        "rate": Decimal("0.025"),
        "rate_note": (
            "Taux fixé par décret gouvernemental. "
            "Taux actuel : 2,5 % (depuis le 1er fév. 2025)."
        ),
        "income_restricted": True,
        "informational": True,
    },
    "pel": {
        "label": "PEL — Plan Épargne Logement",
        "description": (
            "Épargne bloquée 4 ans minimum avec taux garanti. "
            "Donne droit à un prêt épargne logement. "
            "Intérêts soumis au PFU 30 %."
        ),
        "tax_free": False,
        "tax_rate": Decimal("0.300"),
        "ceiling": Decimal("61200"),
        "risk": "Aucun",
        "color": "#fde68a",
        "liquidity": "Bloqué 4 ans minimum",
        "rate": Decimal("0.020"),
        "rate_note": (
            "Taux brut garanti pendant toute la durée du plan. "
            "Taux actuel : 2,0 % brut (~1,4 % net après PFU) pour les PEL ouverts en 2026."
        ),
        "lock_up_years": 4,
        "informational": True,
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
    "cto": {
        "label": "CTO — Compte-Titres Ordinaire",
        "description": (
            "Compte-titres classique sans plafond ni blocage. "
            "Accès à tous les marchés mondiaux. "
            "Dividendes et plus-values soumis au PFU 30 %."
        ),
        "rate": Decimal("0.070"),
        "tax_free": False,
        "tax_rate": Decimal("0.300"),
        "ceiling": None,
        "risk": "Moyen-élevé",
        "color": "#d4d4d8",
        "liquidity": "Totalement libre",
        "informational": True,
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
    "pee": {
        "label": "PEE — Plan Épargne Entreprise",
        "description": (
            "Épargne salariale avec abondement employeur. "
            "Bloqué 5 ans (sauf déblocages exceptionnels). "
            "Plus-values exonérées d'IR (CSG/CRDS uniquement)."
        ),
        "rate": Decimal("0.050"),
        "tax_free": False,
        "tax_rate": Decimal("0.172"),
        "ceiling": None,
        "risk": "Faible-moyen",
        "color": "#c084fc",
        "liquidity": "Bloqué 5 ans",
        "lock_up_years": 5,
        "informational": True,
    },
}

# ── Vehicle rules catalog (TASK-8.9.B) ─────────────────────────────────────────
# Per-vehicle rules panel data: rate, tax treatment, ceiling, liquidity,
# lock-up, best_for, watch_out, horizon, open_conditions.
# Exposed via GET /api/investments/catalog.

VEHICLE_RULES: dict[str, dict] = {
    "livret_a": {
        "label": "Livret A",
        "icon": "🏦",
        "current_rate": "1,5 % net (depuis fév. 2026)",
        "rate_by_scale": {
            "pessimiste": "1,0 %",
            "modéré": "1,5 %",
            "optimiste": "2,5 %",
        },
        "ceiling": "22 950 €",
        "tax": "Exonéré d'impôt sur le revenu et de prélèvements sociaux (17,2 %)",
        "liquidity": "Disponible à tout moment — aucun délai de retrait",
        "lock_up": None,
        "penalty": "Aucune pénalité",
        "best_for": (
            "Épargne de précaution (3–6 mois de dépenses). À remplir en priorité."
        ),
        "watch_out": (
            "Taux révisable deux fois par an — peut descendre sous l'inflation."
        ),
        "horizon": "Court terme (< 2 ans)",
        "open_conditions": "Accessible à tous — une seule ouverture par personne.",
    },
    "ldds": {
        "label": "LDDS",
        "icon": "🌱",
        "current_rate": "1,5 % net (identique Livret A)",
        "ceiling": "12 000 €",
        "tax": "Exonéré IR + PS",
        "liquidity": "Disponible à tout moment",
        "lock_up": None,
        "penalty": "Aucune",
        "best_for": (
            "Extension du Livret A une fois le plafond atteint."
        ),
        "watch_out": (
            "Même risque de baisse de taux que le Livret A."
        ),
        "horizon": "Court terme",
        "open_conditions": "Un seul par personne.",
    },
    "lep": {
        "label": "LEP — Livret d'Épargne Populaire",
        "icon": "💰",
        "current_rate": "2,5 % net (depuis fév. 2026)",
        "ceiling": "10 000 €",
        "tax": "Exonéré IR + PS",
        "liquidity": "Disponible à tout moment",
        "lock_up": None,
        "penalty": "Aucune",
        "best_for": (
            "Meilleur taux garanti disponible pour l'épargne de précaution."
        ),
        "watch_out": (
            "Soumis à conditions de revenus (RFR ≤ plafond annuel selon parts fiscales). "
            "À vérifier chaque année — droits peuvent être perdus si revenus augmentent."
        ),
        "horizon": "Court terme",
        "open_conditions": (
            "RFR ≤ 21 393 € pour 1 part (2026). "
            "Pour 4 parts fiscales : RFR ≤ ~35 000 € environ. À vérifier."
        ),
    },
    "pel": {
        "label": "PEL — Plan Épargne Logement",
        "icon": "🏠",
        "current_rate": (
            "2,0 % brut (~1,4 % net après PFU 30 %) pour les PEL ouverts en 2026"
        ),
        "ceiling": "61 200 €",
        "tax": "Intérêts soumis au PFU (30 %) dès la première année",
        "liquidity": "Bloqué pendant 4 ans minimum",
        "lock_up": (
            "4 ans minimum (sinon clôture automatique et perte des droits)"
        ),
        "penalty": (
            "Clôture avant 4 ans : perte des intérêts majorés et du droit au prêt PEL"
        ),
        "best_for": (
            "Constitution d'un apport immobilier à horizon 4–10 ans. "
            "Taux garanti pendant toute la durée du plan."
        ),
        "watch_out": (
            "Le prêt PEL adossé n'est plus compétitif par rapport aux taux de marché en 2026. "
            "L'intérêt principal est désormais la garantie du taux d'épargne, pas le prêt."
        ),
        "horizon": "Moyen terme (4–10 ans)",
        "open_conditions": "Un seul PEL par personne.",
    },
    "av_euro": {
        "label": "Assurance-Vie — Fonds en Euros",
        "icon": "📄",
        "current_rate": "~2,5–3,5 % brut en 2025 selon assureur",
        "ceiling": "Aucun plafond légal",
        "tax": (
            "Gains soumis au PFU (30 %) avant 8 ans. "
            "Après 8 ans : prélèvements sociaux (17,2 %) seulement, "
            "avec abattement annuel de 4 600 € (9 200 € pour un couple)."
        ),
        "liquidity": (
            "Disponible à tout moment, mais optimisation fiscale après 8 ans"
        ),
        "lock_up": None,
        "penalty": (
            "Aucune pénalité légale, mais rachat avant 8 ans = fiscalité PFU moins favorable. "
            "Certains contrats ont des frais de rachat."
        ),
        "best_for": (
            "Épargne long terme avec capital garanti (fonds €). "
            "Idéal pour la préparation retraite et transmission patrimoniale."
        ),
        "watch_out": (
            "Rendement des fonds € orienté à la baisse depuis 2010. "
            "Les frais de gestion annuels (0,5–1 %) réduisent le rendement réel. "
            "Ouvrir tôt pour faire courir l'horloge fiscale des 8 ans."
        ),
        "horizon": "Long terme (8 ans+)",
        "open_conditions": "Accessible à tous.",
    },
    "av_uc": {
        "label": "Assurance-Vie — Unités de Compte",
        "icon": "📈",
        "current_rate": (
            "Variable selon allocation (espérance ~4–7 % annuel long terme)"
        ),
        "ceiling": "Aucun plafond légal",
        "tax": (
            "Identique AV fonds € (PFU avant 8 ans, PS 17,2 % + abattement après 8 ans)"
        ),
        "liquidity": "Disponible à tout moment",
        "lock_up": None,
        "penalty": (
            "Frais de rachat possibles selon contrat. Risque de moins-value sur UC."
        ),
        "best_for": (
            "Exposition marchés dans une enveloppe fiscalement avantageuse."
        ),
        "watch_out": (
            "Capital non garanti — valeur peut baisser. Adaptée si horizon > 10 ans."
        ),
        "horizon": "Long terme (10 ans+)",
    },
    "pea": {
        "label": "PEA — Plan d'Épargne en Actions",
        "icon": "📊",
        "current_rate": (
            "Variable (actions européennes ~5–8 % historique long terme)"
        ),
        "ceiling": "150 000 € (PEA classique)",
        "tax": (
            "Avant 5 ans : PFU 30 % sur les retraits (+ clôture du plan). "
            "Après 5 ans : prélèvements sociaux uniquement (17,2 %). "
            "Dividendes et plus-values en dessous du plafond : exonérés d'IR dans le plan."
        ),
        "liquidity": (
            "Tout retrait avant 5 ans clôt le PEA. "
            "Après 5 ans : retraits libres sans clôture."
        ),
        "lock_up": (
            "5 ans pour bénéficier de l'exonération IR"
        ),
        "penalty": (
            "Retrait avant 5 ans = clôture + PFU 30 % sur l'ensemble des gains"
        ),
        "best_for": (
            "Meilleure enveloppe pour investissement en actions à long terme. "
            "Ouvrir dès que possible pour faire courir les 5 ans."
        ),
        "watch_out": (
            "Réservé aux titres de sociétés européennes (OPCVM éligibles inclus)."
        ),
        "horizon": "Long terme (5 ans minimum, idéalement 10 ans+)",
        "open_conditions": "Un seul PEA par adulte.",
    },
    "cto": {
        "label": "Compte-Titres Ordinaire (CTO)",
        "icon": "📉",
        "current_rate": "Variable (actions, ETF, obligations)",
        "ceiling": "Aucun",
        "tax": "PFU 30 % sur dividendes et plus-values (ou barème IR)",
        "liquidity": "Totalement libre — aucun blocage",
        "lock_up": None,
        "penalty": "Aucune",
        "best_for": (
            "Dépassement des plafonds PEA/AV. "
            "Accès à tous les marchés mondiaux (non limité aux actions européennes)."
        ),
        "watch_out": (
            "Fiscalité la moins avantageuse parmi les enveloppes — à utiliser en dernier."
        ),
        "horizon": "Tous horizons",
    },
    "scpi": {
        "label": "SCPI — Parts de Sociétés Civiles de Placement Immobilier",
        "icon": "🏢",
        "current_rate": (
            "~4–5 % rendement annuel (taux de distribution moyen 2024)"
        ),
        "ceiling": "Aucun plafond légal",
        "tax": (
            "Revenus fonciers soumis au PFU (30 %) ou au barème IR au choix"
        ),
        "liquidity": "Illiquide — délai de cession variable (semaines à mois)",
        "lock_up": "Aucun légal, mais recommandé horizon 8–10 ans",
        "penalty": (
            "Risque de décote en cas de revente rapide (marché secondaire)"
        ),
        "best_for": (
            "Diversification immobilière sans gestion locative directe."
        ),
        "watch_out": (
            "Valeur des parts peut baisser (2023-2024 : corrections -10 à -20 % sur certaines SCPI). "
            "Délai de revente non garanti. Frais de souscription élevés (~8-12 %)."
        ),
        "horizon": "Long terme (8–10 ans minimum)",
    },
    "per": {
        "label": "PER — Plan d'Épargne Retraite",
        "icon": "🎯",
        "current_rate": "Variable selon supports (mixte fonds € + UC)",
        "ceiling": "Aucun plafond de versement légal",
        "tax": (
            "Versements déductibles du revenu imposable (dans la limite des plafonds d'épargne retraite). "
            "Gains en phase d'accumulation non taxés. "
            "Sortie en capital ou en rente : imposition à l'IR (plus 17,2 % PS sur les gains)."
        ),
        "liquidity": (
            "Bloqué jusqu'à la retraite (sauf cas de déblocage anticipé)"
        ),
        "lock_up": (
            "Jusqu'à l'âge de la retraite. "
            "Déblocages exceptionnels : acquisition résidence principale, invalidité, "
            "décès du conjoint, surendettement, fin de droits au chômage."
        ),
        "penalty": (
            "Pas de pénalité légale, mais argent immobilisé jusqu'à la retraite. "
            "Avantage fiscal à l'entrée = imposition à la sortie."
        ),
        "best_for": (
            "Réduction d'impôt immédiate si tranche marginale élevée (30 %+). "
            "Complément de retraite avec sortie en capital ou rente."
        ),
        "watch_out": (
            "Avantage fiscal = différé d'imposition, pas exonération totale. "
            "Si tranche marginale à la retraite ≈ tranche active, gain fiscal limité. "
            "Pour AE avec versement libératoire, l'avantage est réduit."
        ),
        "horizon": "Très long terme (jusqu'à la retraite)",
    },
    "pee": {
        "label": "PEE — Plan Épargne Entreprise",
        "icon": "🏭",
        "current_rate": "Variable selon fonds proposés par l'entreprise",
        "ceiling": "Aucun plafond (hors limite des versements volontaires)",
        "tax": (
            "Plus-values exonérées d'IR après 5 ans. "
            "CSG/CRDS (9,7 %) uniquement sur les gains. "
            "Abondement employeur exonéré d'IR dans certaines limites."
        ),
        "liquidity": "Bloqué 5 ans (sauf déblocages exceptionnels)",
        "lock_up": (
            "5 ans minimum. Déblocages anticipés : mariage/PACS, "
            "naissance, divorce, achat RP, invalidité, décès, "
            "création d'entreprise, surendettement."
        ),
        "penalty": (
            "Retrait avant 5 ans = imposition des plus-values selon le régime applicable."
        ),
        "best_for": (
            "Si vous basculez vers un statut salarié : profitez de l'abondement employeur. "
            "L'argent investi est déduit de votre salaire brut (avantage social)."
        ),
        "watch_out": (
            "Seulement accessible aux salariés d'entreprises qui le proposent. "
            "Non pertinent pour les AE/EURL/SASU."
        ),
        "horizon": "Moyen-long terme (5 ans+)",
        "open_conditions": "Salarié d'une entreprise proposant un PEE.",
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


def get_vehicle_rules(vehicle_key: str) -> dict | None:
    """Return the rules panel data for a given vehicle key, or None if not found."""
    return VEHICLE_RULES.get(vehicle_key)


def get_av_abattement(is_couple: bool) -> Decimal:
    """Annual AV gain abattement after 8 years (Art. 125-0 A CGI).

    For AV contracts held > 8 years, gains are taxed at 17.2% PS
    with an annual abattement on the taxable gain:
      - €4,600 for a single person
      - €9,200 for a married couple or PACS filing jointly

    Args:
        is_couple: True if married/PACS, False if single.

    Returns:
        Annual abattement amount as Decimal.
    """
    return Decimal("9200") if is_couple else Decimal("4600")