# Active Issues

## [RESOLVED] ~~Data not persisting — client-side API calls return 401~~
- **Found during:** Sprint 2 blank page fix verification
- **Resolved during:** Sprint 6 start (2026-05-09)
- **Resolution:** Issue no longer reproducible. Both direct backend auth (port 48002) and frontend proxy auth (port 48178) work correctly. Session cookie is properly set by the SvelteKit server action and forwarded by the hooks.server.ts API proxy. Fix was likely part of Task 2.7 port sync overhaul (LEARNINGS #6, #7, api.ts refactor).
- **Verification:** curl tested: register → cookie set → GET /api/career returns 200 (not 401) through both ports.
