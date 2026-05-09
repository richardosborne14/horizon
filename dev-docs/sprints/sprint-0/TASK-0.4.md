# TASK-0.4: Dark Theme Design Tokens

**Status:** DONE ✅ (2026-05-08)
**Sprint:** 0
**Priority:** P1 (high)
**Est. effort:** 1 hr
**Dependencies:** TASK-0.3

## Context

ComCoi uses a warm light theme (warm white #FAFAF8, purple primary #6C5CE7, gold accent #D4A843) with Fraunces/DM Sans/DM Mono fonts. Horizon 30 uses a dark fintech theme with a completely different palette and font stack. This task replaces `design-tokens.css` and ensures the new tokens are applied throughout the app shell built in TASK-0.3.

## Requirements

1. **Replace `frontend/src/styles/design-tokens.css`** with Horizon 30 tokens:

   **Backgrounds:**
   - `--bg-primary`: #09090b (zinc-950)
   - `--bg-card`: rgba(24, 24, 27, 0.4) (zinc-900/40)
   - `--bg-card-hover`: rgba(39, 39, 42, 0.2) (zinc-800/20)
   - `--bg-input`: rgba(24, 24, 27, 0.6) (zinc-900/60)

   **Borders:**
   - `--border-default`: rgba(63, 63, 70, 0.4) (zinc-700/40)
   - `--border-card`: rgba(39, 39, 42, 0.6) (zinc-800/60)
   - `--border-focus`: rgba(45, 212, 191, 0.5) (teal-400/50)

   **Text:**
   - `--text-primary`: #ffffff
   - `--text-secondary`: #a1a1aa (zinc-400)
   - `--text-tertiary`: #71717a (zinc-500)
   - `--text-muted`: #52525b (zinc-600)

   **Accent colors:**
   - `--color-teal`: #2dd4bf (teal-400) — primary accent, active states, CTAs
   - `--color-amber`: #fbbf24 (amber-400) — warnings, caution
   - `--color-rose`: #fb7185 (rose-400) — negative values, errors
   - `--color-emerald`: #34d399 (emerald-400) — positive values, growth
   - `--color-purple`: #a78bfa (purple-400) — savings, investments
   - `--color-sky`: #38bdf8 (sky-400) — info, tech entities

   **Fonts:**
   - `--font-ui`: 'Inter', -apple-system, sans-serif
   - `--font-mono`: 'JetBrains Mono', 'SF Mono', 'Fira Code', monospace

   **Spacing / Radius:**
   - `--radius-sm`: 0.5rem (8px)
   - `--radius-md`: 0.75rem (12px)
   - `--radius-lg`: 1rem (16px)

2. **Add font loading** to `frontend/src/app.html` (or equivalent):
   ```html
   <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
   ```

3. **Update global styles** (reset / base styles file):
   - `body`: bg-zinc-950, text-white, font-family Inter
   - `input`, `select`: dark theme defaults matching tokens
   - Scrollbar: thin, zinc-700 thumb on transparent track
   - `::selection`: teal background

4. **Update the app layout** (from TASK-0.3) to use CSS custom properties instead of hardcoded Tailwind classes where it makes sense for future themability

5. **Verify:** no ComCoi purple/gold/warm-white remnants visible anywhere in the app

## Technical Approach

### Files to Create/Modify
- `frontend/src/styles/design-tokens.css` — full rewrite
- `frontend/src/app.html` — add Google Fonts link
- `frontend/src/styles/global.css` (or equivalent) — base styles
- `frontend/src/routes/(app)/+layout.svelte` — verify tokens applied

### Token Usage Pattern
Components should prefer Tailwind utility classes (zinc-950, teal-400, etc.) for most styling, with CSS custom properties used for:
- Semantic tokens that might change (--bg-card, --border-focus)
- Values referenced in multiple places
- Values that JavaScript might need to read

## Acceptance Criteria

- [ ] `design-tokens.css` contains all Horizon 30 tokens
- [ ] Inter and JetBrains Mono fonts load correctly
- [ ] App shell background is zinc-950 (#09090b)
- [ ] Sidebar nav uses correct dark theme colors
- [ ] No purple (#6C5CE7), gold (#D4A843), or warm white (#FAFAF8) visible anywhere
- [ ] Input fields have dark backgrounds with teal focus rings
- [ ] Scrollbar styled thin/dark
- [ ] No FOUT (flash of unstyled text) on page load — fonts load with `display=swap`
- [ ] LEARNINGS.md updated if gotchas discovered

## Notes

- ComCoi used Fraunces for hero numbers, DM Sans for body, DM Mono for numbers. Horizon 30 uses Inter for everything except financial data (JetBrains Mono). This is a deliberate simplification — two fonts instead of three.
- Tailwind's `zinc` scale is the backbone of the dark theme. Most components will use Tailwind classes directly. The CSS custom properties are for semantic layering.
- The `(auth)/` pages (login, register) will look visually broken after this task because they still use ComCoi light theme markup. That's acceptable — retheme them later or accept the mismatch for now.
