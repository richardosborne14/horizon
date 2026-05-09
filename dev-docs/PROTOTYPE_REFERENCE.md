# Horizon — Prototype Reference & Design System

**Source:** `dev-docs/prototype/horizon30.jsx` (954-line React prototype)
**Purpose:** Canonical UX reference for all Horizon frontend work. Every section layout, card style, input pattern, dark theme token, and sidebar nav structure originates here.

---

## Section Mapping

| Prototype Section | Route | Key Components | Sprint | Description |
|---|---|---|---|---|
| Identity | `(app)/identity/` | ProfileForm, RateSchedulePreview | 1 | Âge, statut juridique (AE/EIRL/EURL/SASU), type d'activité, VL, parts fiscales, évolution des cotisations |
| Revenue | `(app)/revenue/` | GrossInput, GrowthPresets, TaxBreaks, CA5YearPreview | 1 | CA brut mensuel, croissance annuelle (4 presets + custom), CESU, dons caritatifs |
| Expenses | `(app)/expenses/` | ExpenseGrid, InflationPreview, CAFInput | 1 | 12 catégories de dépenses, projection inflation 3 scénarios, allocations familiales |
| Life | `(app)/life/` | KidCard, PetCard, CarCard, TechCard, RecurringList | 2 | Enfants (cycle de coûts 0→25 ans), animaux, véhicules, tech, dépenses récurrentes à durée limitée |
| Savings | `(app)/savings/` | VehicleCard (×7), AllocationSliders | 3 | 7 véhicules d'épargne (Livret A, LDDS, AV €, AV UC, PEA, SCPI, PER), allocation mensuelle |
| Projects | `(app)/projects/` | InvestmentPNL, LifeEventRow, StatusChangeSimulator | 3 | Investissements locatifs (PNL), événements ponctuels, changement de statut juridique |
| Runway | `(app)/runway/` | ScaleSelector, GoalInput, WealthChart, IncomeChart, MilestoneTimeline, ProjectionTable, InsightCards | 4 | Projection 30 ans, 3 scénarios économiques, objectif de revenu, jalons patrimoniaux, tableau détaillé |

---

## Design Patterns

### Card Component
```
border border-zinc-800/60 rounded-xl bg-zinc-900/40 overflow-hidden
```
- Optional `border-l-2` accent stripe (teal, amber, rose, purple, emerald, sky)
- Header: `px-5 py-3 border-b border-zinc-800/40` with icon + uppercase title in `text-xs font-semibold text-zinc-300`
- Body: `p-5`
- Used everywhere — every section uses cards as primary content containers

### Stat Card
```
bg-zinc-900/60 border border-zinc-800/40 rounded-lg p-3
```
- Label: `text-[9px] text-zinc-500 uppercase tracking-widest`
- Value: `text-lg font-mono font-bold` with accent color (teal/emerald/amber/rose/purple)
- Subtitle: `text-[10px] text-zinc-500`
- Used in: Revenue stats (CA, cotisations, net), Expenses totals, Savings stats, Runway endpoint stats

### Input Component (Inp)
```
w-full bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-2 text-white text-sm font-mono
focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/15
```
- Label: `text-[10px] font-semibold text-zinc-400 mb-1 uppercase tracking-wider`
- Suffix: absolute right-aligned `text-zinc-500 text-[10px] font-mono`
- Hint: `text-[10px] text-zinc-500 mt-0.5 leading-tight`
- `placeholder:text-zinc-600`
- Monospace for numeric inputs, regular for text inputs
- Spinner opacity: `input[type=number]::-webkit-inner-spin-button{opacity:.3}`

### Select Component (Sel)
```
w-full bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-2 text-white text-sm
focus:outline-none focus:border-teal-500/50
```
- Options have dark background: `select option{background:#18181b}`
- Same label pattern as Inp

### Scale Selector (3-button bar)
- 3 buttons in a row: Optimiste ☀️ / Modéré ⛅ / Pessimiste 🌧️
- Active: `border-zinc-600 bg-zinc-800 text-white`
- Inactive: `border-zinc-800/40 bg-zinc-900/30 text-zinc-500 hover:text-zinc-300`
- `flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-all border`
- Used in: Runway scenario selector

### Growth Presets (4-card grid)
- 4 cards in a `grid grid-cols-4 gap-2`
- Active: `border-teal-600/50 bg-teal-950/20`
- Inactive: `border-zinc-800/40 bg-zinc-900/30 hover:border-zinc-700`
- Each card: label, rate (mono bold), description (10px)
- `p-3 rounded-lg border text-left transition-all`
- Used in: Revenue → Croissance annuelle du CA

### Life Entity Cost Events (timeline rows)
- Each expense row for kids: flex row with colored dot indicator
  - Active (within age range): `bg-purple-950/20`, purple dot
  - Future (not yet started): grey dot `bg-zinc-600`
  - Past (beyond age range): `opacity-30`
- Dot: `w-1.5 h-1.5 rounded-full`
- Used in: Life → Enfants → each kid's expense list

### Add Button (dashed border)
- `w-full py-2 rounded-lg border border-dashed border-zinc-700 text-xs text-zinc-400`
- Hover: `hover:text-teal-300 hover:border-teal-800 transition-colors`
- Text: "+ Ajouter un/une..."
- Used in: Life entities (kids, pets, cars, tech, recurring), Projects (investments, events)

### SVG Area Chart (no chart library)
- Pure SVG: `<svg viewBox="0 0 400 {height}">` with preserveAspectRatio="none"
- Linear gradient fill (`define/linearGradient`): top at 25% opacity → bottom at 0%
- Polyline stroke: `strokeWidth="2"`
- Optional goal line: dashed amber line `strokeDasharray="6,4"`
- X-axis labels: `text-[9px] text-zinc-500 font-mono`, left (start year+age) / right (end year+age)
- Used in: Runway → WealthChart, IncomeChart

### Milestone Timeline
- Vertical line: `absolute left-[7px] w-px bg-zinc-800`
- Each milestone: colored circle icon (`w-4 h-4 rounded-full border-2`) with inner dot (`w-1.5 h-1.5`)
- Label: `text-sm font-mono font-bold` in milestone color
- Subtext: `text-xs text-zinc-500` with year and age
- Used in: Runway → milestones at 100k€, 250k€, 500k€, 1M€

### Info Box (contextual tips)
- Colored background border combo:
  - Teal: `bg-teal-950/20 border border-teal-900/30` for identity/configuration info
  - Sky: `bg-sky-950/20 border border-sky-900/30` for life entities intro
  - Purple: `bg-purple-950/15 border border-purple-900/20` for tax optimization tips
  - Emerald: `bg-emerald-950/15 border border-emerald-900/30` for goal reached
  - Amber: `bg-amber-950/15 border border-amber-900/30` for gap warnings
- Icons: 💡 (tip), 🎯 (goal), ⚠️ (warning), 🏆 (achievement), ⚖️ (disclaimer)
- Used: throughout all sections

### Projection Table
- `overflow-x-auto` container
- Header: `text-zinc-500 text-[9px] uppercase tracking-wider border-b border-zinc-800`
- Rows: `border-t border-zinc-800/30 hover:bg-zinc-800/10`
- Data font: JetBrains Mono `font-mono`, sizes 11px
- Shown every 5 years + final year
- Columns: An, Âge, CA brut, Cotis., Cotis.%, Vie, Enfants, Projets, Net, Patrimoine, Passif/m

### Sidebar Navigation
- `w-44 flex-shrink-0 border-r border-zinc-800/40 min-h-[calc(100vh-56px)] py-4 px-3 sticky top-14 self-start`
- Nav items: `w-full text-left px-3 py-2 rounded-lg text-xs font-medium transition-all flex items-center gap-2`
- Active: `bg-zinc-800/60 text-white`
- Inactive: `text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/20`
- Icon: `text-[10px] w-4 text-center opacity-60`

### Sidebar Quick Stats
- Separated by `border-t border-zinc-800/40 pt-4 mt-6`
- Header: `text-[9px] text-zinc-600 uppercase tracking-widest font-semibold`
- Row: `flex justify-between text-[10px] text-zinc-400`
- Value: `font-mono text-zinc-200` or `font-mono text-teal-400` (for savings)
- Shows: CA/mois, Enfants, Épargne/m, Projets

### Header Bar
- `border-b border-zinc-800/50 bg-zinc-950/95 backdrop-blur sticky top-0 z-50`
- Logo: `w-7 h-7 rounded-md bg-gradient-to-br from-teal-400 to-cyan-600` with "H" letter
- App name: `text-sm font-bold tracking-tight`
- Tagline: `text-[9px] text-zinc-500 tracking-widest uppercase`
- Age range: `text-[10px] text-zinc-600 font-mono`

### Page Transition
- `animate-in` class: `animation: si .25s ease-out`
- Keyframe: `from{opacity:0;transform:translateY(6px)} to{opacity:1}`

### Scrollbar
- `scrollbar-width:thin; scrollbar-color:#27272a transparent`

### Footer
- `border-t border-zinc-800/30 py-5 text-center`
- Disclaimer: `text-[9px] text-zinc-700`

---

## Color Semantics

| Color | Tailwind Class | Hex | Usage |
|---|---|---|---|
| Teal | `teal-400` | `#2dd4bf` | Primary accent, active nav, CTAs, positive net, wealth chart, teal info boxes, input focus rings |
| Emerald | `emerald-400` | `#34d399` | Growth, passive income, goal reached, positive values, investment returns |
| Amber | `amber-400` | `#fbbf24` | Warnings, cotisation rates, cost-of-living, goal line, CAF, caution info boxes |
| Rose | `rose-400` | `#fb7185` | Negative values, errors, charges, cotisation deductions |
| Purple | `purple-400` | `#a78bfa` | Savings, kids, investments, CAF, tax optimization, AV |
| Sky | `sky-400` | `#38bdf8` | Tech, information, life entities intro |
| Cyan | `cyan-600` | n/a | Logo gradient accent (paired with teal-400) |
| Zinc-950 | `zinc-950` | `#09090b` | Main background |
| Zinc-900 | `zinc-900` | `#18181b` | Card backgrounds, select options |
| Zinc-800 | `zinc-800` | `#27272a` | Borders, hover states, scrollbar |
| Zinc-700 | `zinc-700` | `#3f3f46` | Input borders |
| Zinc-600 | `zinc-600` | `#52525b` | Muted text, age range, empty states |
| Zinc-500 | `zinc-500` | `#71717a` | Tertiary text, hints, inactive nav, labels |
| Zinc-400 | `zinc-400` | `#a1a1aa` | Secondary text, input labels |
| Zinc-300 | `zinc-300` | `#d4d4d8` | Card titles, hover text |
| Zinc-200 | `zinc-200` | `#e5e5e5` | Data values in sidebar, emphasis |
| White | `white` | `#ffffff` | Primary text, active nav |

---

## Typography

| Element | Font | Weight | Size | Color | Notes |
|---|---|---|---|---|---|
| App name (header) | Inter | 700 (bold) | 14px (sm) | white | tracking-tight |
| Tagline (header) | Inter | 400 | 9px | zinc-500 | tracking-widest uppercase |
| Age range (header) | JetBrains Mono | 400 | 10px | zinc-600 | monospace |
| Nav item | Inter | 500 (medium) | 12px (xs) | zinc-500 / white | Active = white |
| Nav icon | (unicode) | 400 | 10px | (inherits) | opacity-60 |
| Sidebar section header | Inter | 600 (semibold) | 9px | zinc-600 | uppercase tracking-widest |
| Sidebar stat label | Inter | 400 | 10px | zinc-400 | |
| Sidebar stat value | JetBrains Mono | 400 | 10px | zinc-200 / teal-400 | |
| Card title | Inter | 600 (semibold) | 12px (xs) | zinc-300 | uppercase tracking-wide |
| Input label | Inter | 600 (semibold) | 10px | zinc-400 | uppercase tracking-wider |
| Input value | JetBrains Mono | 400 | 14px (sm) | white | |
| Input suffix | JetBrains Mono | 400 | 10px | zinc-500 | |
| Input hint | Inter | 400 | 10px | zinc-500 | leading-tight |
| Stat label | Inter | 400 | 9px | zinc-500 | uppercase tracking-widest |
| Stat value | JetBrains Mono | 700 (bold) | 18px (lg) | accent color | |
| Stat subtitle | Inter | 400 | 10px | zinc-500 | |
| Button text (scale selector) | Inter | 500 (medium) | 12px (xs) | varies | |
| Growth preset label | Inter | 600 (semibold) | 12px (xs) | zinc-300 / teal-300 | |
| Growth preset rate | JetBrains Mono | 700 (bold) | 14px (sm) | zinc-200 | |
| Growth preset desc | Inter | 400 | 10px | zinc-500 | leading-tight |
| Cotisation schedule year | Inter | 400 | 9px | zinc-500 | |
| Cotisation schedule rate | JetBrains Mono | 700 (bold) | 12px (xs) | amber-400 | |
| Life entity label (input) | Inter | 400 | 12px (xs) | zinc-300 | |
| Life entity cost value | JetBrains Mono | 400 | 12px (xs) | white | text-right |
| Expense dot indicator | (div) | — | 6px | varies | w-1.5 h-1.5 rounded-full |
| Info box title | Inter | 700 (bold) | 12px (xs) | accent color | |
| Info box body | Inter | 400 | 10px-12px | zinc-300/80 | |
| Table header | Inter | 400 | 9px | zinc-500 | uppercase tracking-wider |
| Table cell | JetBrains Mono | 400-700 | 11px | varies by column | |
| Chart axis label | JetBrains Mono | 400 | 9px | zinc-500 | |
| Milestone label | JetBrains Mono | 700 (bold) | 14px (sm) | milestone color | |
| Milestone detail | Inter | 400 | 12px (xs) | zinc-500 | |
| Footer disclaimer | Inter | 400 | 9px | zinc-700 | |
| Add button | Inter | 400 | 12px (xs) | zinc-400 | hover:teal-300 |
| Checkbox label | Inter | 400 | 14px (sm) | zinc-300 | |
| Schedule/CAF projection header | Inter | 600 (semibold) | 10px | zinc-400 | uppercase tracking-wider |

---

## Font Stack

- **UI text:** `'Inter', -apple-system, BlinkMacSystemFont, sans-serif`
- **Financial data / numbers:** `'JetBrains Mono', 'SF Mono', 'Fira Code', monospace`
- **Loading:** `display=swap` via Google Fonts to prevent FOUT
- **Two fonts** instead of ComCoi's three (Fraunces + DM Sans + DM Mono) — deliberate simplification

---

## CSS Custom Properties (from design-tokens.css)

| Token | Value | Notes |
|---|---|---|
| `--font-sans` | Inter, -apple-system, sans-serif | UI text |
| `--font-mono` | JetBrains Mono, SF Mono, monospace | Financial data |
| `--text-xs` | 0.6875rem (11px) | |
| `--text-sm` | 0.8125rem (13px) | |
| `--text-base` | 0.9375rem (15px) | |
| `--text-lg` | 1.125rem (18px) | |
| `--text-xl` | 1.5rem (24px) | |
| `--text-2xl` | 1.875rem (30px) | |
| `--text-3xl` | 2.25rem (36px) | |
| `--font-weight-normal` | 400 | |
| `--font-weight-medium` | 500 | |
| `--font-weight-semibold` | 600 | |
| `--font-weight-bold` | 700 | |
| `--color-teal` | #2dd4bf | Primary accent |
| `--color-amber` | #fbbf24 | Warnings, caution |
| `--color-rose` | #fb7185 | Negative values |
| `--color-emerald` | #34d399 | Positive values |
| `--color-purple` | #a78bfa | Savings, investments |
| `--color-sky` | #38bdf8 | Info, tech |
| `--bg-primary` | #09090b | Main background |
| `--bg-card` | rgba(24,24,27,0.4) | Card surfaces |
| `--bg-input` | rgba(24,24,27,0.6) | Input fields |
| `--border-default` | rgba(63,63,70,0.4) | Default borders |
| `--border-card` | rgba(39,39,42,0.6) | Card borders |
| `--border-focus` | rgba(45,212,191,0.5) | Focus rings |
| `--radius-sm` | 0.5rem (8px) | Small corners |
| `--radius-md` | 0.75rem (12px) | Card corners |
| `--radius-lg` | 1rem (16px) | Large corners |

---

## Prototype Default Values (Seed Data)

Used for initial state. Serves as reference for reasonable defaults.

```json
{
  "age": 40,
  "targetAge": 70,
  "taxParts": 2.5,
  "status": "ae",
  "aeType": "bnc_non_reglementee",
  "hasVL": true,
  "monthlyGross": 5000,
  "growthRate": 0.03,
  "growthPreset": "moderate",
  "cesu": 0,
  "charity": 0,
  "cafOvr": null,
  "expenses": {
    "loyer": 800, "energie": 120, "internet": 60, "assurance": 100,
    "transport": 200, "alimentation": 400, "sante": 50, "loisirs": 150,
    "abonnements": 50, "impots": 100, "credit": 0, "divers": 100
  },
  "kids": [
    { "name": "Aînée", "age": 10, "expenses": [...] },
    { "name": "Petit(e)", "age": 1, "expenses": [...] }
  ],
  "pets": [{ "name": "Le chien", "type": "dog", "age": 4, "cost": 900 }],
  "cars": [{ "name": "Voiture principale", "type": "petrol", "age": 5, "annual": 2400, "cycle": 8, "replace": 18000 }],
  "tech": [
    { "name": "MacBook Pro", "age": 2, "cycle": 4, "replace": 2500 },
    { "name": "iPhone", "age": 1, "cycle": 3, "replace": 1300 }
  ],
  "alloc": { "livret_a": 200, "ldds": 100, "av_euro": 200, "pea": 200, "per": 100, "scpi": 0, "av_uc": 150 },
  "assets": { "livret_a": 5000, "ldds": 2000 },
  "projects": [
    { "type": "invest", "label": "Petit gîte rural", "start": 2035, "cost": 80000, "income": 8000, "expenses": 2500, "tax": 0.30 },
    { "type": "event", "label": "Gros voyage famille", "year": 2030, "cost": 8000 }
  ],
  "statusChange": { "enabled": true, "year": 2028, "newStatus": "eirl", "savings": 3600 },
  "goal": 4000
}
```

---

## Projection Engine (Reference)

The prototype's `project()` function is the canonical calculation reference. Key behaviors:

- **Revenue:** `monthlyGross * 12 * (1 + growthRate)^year`, cotisations = `AE_SCHEDULES[aeType].rate` (progressive by year)
- **Expenses:** base expenses × inflation factor, kid expenses by age range, pet costs with lifecycle, car replacement every N years, tech replacement every N years
- **Savings:** Monthly allocation × 12, existing balance × (rate - inflation × 0.25), with cap for Livret A/LDDS
- **Passive income:** `wealth × 0.04 / 12` (4% rule)
- **Goal:** total monthly income >= goal → `goalHit: true`

See `dev-docs/prototype/horizon30.jsx` lines 68-193 for full implementation.