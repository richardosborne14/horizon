# TASK-0.5: i18n Reset

**Status:** DONE ✅ (2026-05-08)
**Sprint:** 0
**Priority:** P1 (high)
**Est. effort:** 30 min
**Dependencies:** TASK-0.3

## Context

ComCoi's `fr.json` and `en.json` contain ~500+ keys for salon-specific UI (pilotage, mon-mois-typique, paramétrage, calculateurs, bulletin de salaire, CoCo prompts, etc.). Horizon 30 needs none of these. This task strips the locale files and seeds them with the initial Horizon 30 key structure.

The i18n infrastructure itself (loading mechanism, `$t()` helper, locale store) is kept intact — only the content changes.

## Requirements

1. **Clear `frontend/src/locales/fr.json`** — replace with Horizon 30 seed keys:

```json
{
  "app": {
    "name": "Horizon 30",
    "tagline": "Moteur patrimonial freelance",
    "age_range": "{age} → {target} ans • {years} ans de runway"
  },
  "nav": {
    "identity": "Identité",
    "revenue": "Revenus",
    "expenses": "Charges",
    "life": "Vie",
    "savings": "Épargne",
    "projects": "Projets",
    "runway": "Horizon"
  },
  "sidebar": {
    "overview": "Aperçu",
    "ca_month": "CA/mois",
    "children": "Enfants",
    "savings_month": "Épargne/m",
    "projects": "Projets"
  },
  "common": {
    "save": "Enregistrer",
    "cancel": "Annuler",
    "delete": "Supprimer",
    "add": "Ajouter",
    "edit": "Modifier",
    "confirm": "Confirmer",
    "per_month": "/mois",
    "per_year": "/an",
    "euros": "€",
    "years": "ans",
    "loading": "Chargement...",
    "no_data": "Aucune donnée",
    "coming_soon": "Bientôt disponible"
  },
  "auth": {
    "login": "Connexion",
    "register": "Créer un compte",
    "logout": "Déconnexion",
    "email": "Email",
    "password": "Mot de passe",
    "forgot_password": "Mot de passe oublié ?"
  },
  "placeholder": {
    "title": "Section en cours de développement",
    "sprint1": "Disponible dans le Sprint 1",
    "sprint2": "Disponible dans le Sprint 2",
    "sprint3": "Disponible dans le Sprint 3",
    "sprint4": "Disponible dans le Sprint 4"
  }
}
```

2. **Update `frontend/src/locales/en.json`** with English equivalents (same structure)

3. **Verify the i18n loading mechanism** still works:
   - Check `frontend/src/lib/i18n/` or wherever the locale loader lives
   - Ensure `$t('nav.identity')` returns "Identité"
   - Ensure fallback behavior works (missing key → key path shown)

4. **Update placeholder pages** (from TASK-0.3) to use i18n keys:
   - Section titles via `$t('nav.identity')` etc.
   - "Coming soon" text via `$t('placeholder.sprint1')` etc.

## Technical Approach

### Files to Create/Modify
- `frontend/src/locales/fr.json` — full replace
- `frontend/src/locales/en.json` — full replace
- 7 placeholder `+page.svelte` files — update to use `$t()` calls

### Key Structure Convention
Hierarchical, dot-separated, grouped by section:
- `nav.*` — navigation labels
- `identity.*` — identity section (Sprint 1)
- `revenue.*` — revenue section (Sprint 1)
- `expenses.*` — expenses section (Sprint 1)
- `life.*` — life entities section (Sprint 2)
- `savings.*` — savings section (Sprint 3)
- `projects.*` — projects section (Sprint 3)
- `runway.*` — runway section (Sprint 4)
- `common.*` — shared labels and actions
- `auth.*` — authentication

## Acceptance Criteria

- [ ] `fr.json` contains only Horizon 30 keys (no salon/ComCoi remnants)
- [ ] `en.json` mirrors `fr.json` structure with English translations
- [ ] `$t('nav.identity')` returns "Identité" in French locale
- [ ] `$t('app.name')` returns "Horizon 30"
- [ ] Sidebar nav labels render from i18n keys
- [ ] Placeholder pages use i18n keys for all visible text
- [ ] No hardcoded French strings in any Svelte component
- [ ] No console warnings about missing i18n keys
- [ ] LEARNINGS.md updated if gotchas discovered

## Notes

- ComCoi used a flat-ish key structure in some places and hierarchical in others. Horizon 30 should be consistently hierarchical from the start.
- The `auth` keys are kept minimal — the auth pages themselves may still have ComCoi-specific text in their templates. That's fine for Sprint 0; full auth page retheme is deferred.
- Sprint 1+ tasks will add their own i18n keys as they build each section. This task just seeds the structure.
