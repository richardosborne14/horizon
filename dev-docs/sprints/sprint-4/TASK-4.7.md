# TASK-4.7: Cross-Section Navigation Polish

**Status:** BACKLOG
**Sprint:** 4
**Priority:** P2 (medium)
**Est. effort:** 1 hr
**Dependencies:** TASK-4.6

## Context

Now that all 7 sections are built (Identity, Revenue, Expenses, Life, Savings, Projects, Runway), this task ensures the navigation between them is smooth and the "configure then live on Runway" workflow feels natural. It adds contextual links from the Runway back to configuration sections, ensures the sidebar active state is correct, and adds a "completeness" indicator so users know what they've filled in.

This is a polish task — the app works without it, but it makes the experience noticeably better.

## Requirements

### Contextual Back-Links

1. On the Runway page, when insights suggest an action, make them clickable:
   - "Augmentez votre épargne mensuelle" → link to `/savings`
   - "Ajoutez un projet immobilier" → link to `/projects`
   - "Changez de statut juridique" → link to `/projects` (scrolls to status section)
   - "Renseignez votre date de naissance" → link to `/identity`

2. On the Runway error states (no birth_date, no CA), the links to Identity/Revenue should work and be clearly styled.

### Sidebar Active State

3. Verify the sidebar nav highlights the correct section on every page. The active state (`bg-zinc-800/60 text-white`) should match the current route. SvelteKit's `$page.url.pathname` drives this.

4. **Sidebar animation:** Subtle transition when switching sections. CSS only — `transition: background-color 150ms, color 150ms`.

### Completeness Indicator

5. Add subtle completion dots to sidebar nav items:
   - Green dot: section has data (profile has CA, expenses have at least 1 non-zero value, life has at least 1 entity, savings has at least 1 allocation > 0, projects has at least 1 project)
   - No dot: section is empty (user hasn't configured it yet)
   - Data source: the profile summary endpoint (TASK-1.8) extended with section completeness flags

6. Extend `GET /api/profile/summary` to include:
   ```json
   {
     "completeness": {
       "identity": true,    // birth_date is set
       "revenue": true,     // monthly_gross > 0
       "expenses": true,    // at least 1 expense > 0
       "life": false,       // at least 1 life entity
       "savings": true,     // at least 1 allocation > 0
       "projects": false,   // at least 1 project
       "runway": true       // always true if identity + revenue are set
     }
   }
   ```

7. Sidebar renders small dots next to completed sections:
   ```svelte
   <button class="...nav-item...">
     <span class="text-[10px] w-4 text-center opacity-60">{s.icon}</span>
     {$t(`nav.${s.id}`)}
     {#if completeness[s.id]}
       <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 ml-auto" />
     {/if}
   </button>
   ```

### Runway as Default Landing

8. After login, redirect to `/runway` if the user has a complete profile (birth_date + CA set). Otherwise redirect to `/identity` for initial setup. This makes the Runway the "home" screen for returning users.

9. Update `(app)/+layout.server.ts` to check profile completeness and set the initial redirect.

## Technical Approach

### Files to Modify
- `frontend/src/routes/(app)/+layout.svelte` — sidebar dots, active state
- `frontend/src/routes/(app)/+layout.server.ts` — completeness check, initial redirect
- `backend/app/routers/profile.py` — extend summary endpoint
- `frontend/src/lib/components/runway/InsightCards.svelte` — make suggestions clickable
- `frontend/src/routes/(app)/runway/+page.svelte` — error state links

### Redirect Logic
```javascript
// +layout.server.ts
if (url.pathname === '/') {
  const hasProfile = summary.completeness.identity && summary.completeness.revenue;
  throw redirect(302, hasProfile ? '/runway' : '/identity');
}
```

## Acceptance Criteria

- [ ] Insight suggestions link to correct sections
- [ ] Error state links navigate correctly
- [ ] Sidebar highlights correct section on every page
- [ ] Sidebar transitions are smooth (no flash)
- [ ] Completeness dots appear for sections with data
- [ ] Completeness dots disappear for empty sections
- [ ] After login with complete profile → lands on Runway
- [ ] After login with no profile → lands on Identity
- [ ] Back/forward browser navigation works correctly with sidebar state
- [ ] All text via i18n keys
- [ ] LEARNINGS.md updated

## Notes

- The completeness indicator is a gentle nudge, not a blocker. Users should be able to view the Runway even with incomplete data — the projection will just be inaccurate or missing components.
- The "Runway as home" redirect is the UX shift that makes this app feel different from a configuration tool. After initial setup, you open the app and see your 30-year runway immediately. Configuration lives in the sidebar — visit when you need to change something.
- Don't over-invest in this task. It's polish. If the redirect logic or completeness check adds unexpected complexity, ship without them and add in a later sprint.
