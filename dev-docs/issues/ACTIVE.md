# Active Issues

## [BUG] Data not persisting — client-side API calls return 401
- **Found during:** Sprint 2 blank page fix verification
- **Severity:** P1 (serious — revenue, life entities, and other user data not saving)
- **Description:** After login, client-side fetch calls to `/api/profile`, `/api/life-entities`, etc. return 401 Unauthorized. SSR requests (via `+page.server.ts`) work correctly. Session cookie is set by the login page server action and forwarded correctly, but subsequent browser-side API requests don't carry a valid session.
- **Observed in backend logs:**
  - `GET /api/profile HTTP/1.1 401 Unauthorized`
  - `PUT /api/profile HTTP/1.1 401 Unauthorized`
  - `GET /api/life-entities HTTP/1.1 401 Unauthorized`
- **Hypothesis:** Cookie forwarding from FastAPI → SvelteKit → browser may have a mismatch. The session cookie is set by the SvelteKit server action (login) which forwards the FastAPI `Set-Cookie` header, but the cookie domain/path/SameSite may not match what the browser includes on subsequent fetch requests. Or the Vite dev proxy strips cookies on API calls.
- **Suggested investigation:**
  1. Check if the `session_token` cookie is visible in browser DevTools → Application → Cookies
  2. Verify the cookie's `path`, `SameSite`, and `domain` attributes
  3. Check if the Vite dev proxy in `vite.config.ts` preserves cookies on proxied requests
  4. Test a direct fetch to `http://localhost:48002/api/...` with the cookie header