# TASK-0.1: Fork Repository & Rename

**Status:** DONE ✅ (2026-05-08)
**Sprint:** 0
**Priority:** P0 (critical)
**Est. effort:** 30 min
**Dependencies:** None

## Context

Horizon 30 is built as a fork of the Communauté Coiffure (ComCoi) codebase. This task creates the fork and renames all top-level references. The goal is a repo that builds and runs identically to ComCoi but with Horizon 30 branding. Nothing is deleted yet — that's TASK-0.2 and TASK-0.3.

## Requirements

1. Fork the ComCoi repo to a new GitHub repo named `horizon30`
2. Update `frontend/package.json`: name → `horizon30-frontend`
3. Update `backend/` if any package name references exist
4. Update `docker-compose.yml` and `docker-compose.override.yml`:
   - Service names: `h30-frontend`, `h30-backend`, `h30-db` (or keep generic `frontend`, `backend`, `db` — whichever is cleaner)
   - Container names updated
   - Keep all port mappings (47178, 47002, 47432)
5. Update `frontend/src/config/meta.json`:
   - App name: "Horizon 30"
   - Description: "Moteur patrimonial multi-décennal pour freelances"
   - Remove any ComCoi-specific URLs or social links
6. Update `README.md` with Horizon 30 context (brief — full README comes later)
7. Verify `docker compose up -d` builds and runs successfully
8. Verify login page loads (even if it still says ComCoi visually — that's fixed in 0.3)

## Technical Approach

This is a straightforward find-and-replace in config files. Do NOT rename internal code references (Python imports, Svelte component names) — that's premature and will cause cascading breakage. Only rename user-facing config and Docker infrastructure.

### Files to Create/Modify
- `frontend/package.json` — name field
- `docker-compose.yml` — service names if desired
- `docker-compose.override.yml` — match base file
- `frontend/src/config/meta.json` — app name, description
- `README.md` — replace content

## Acceptance Criteria

- [ ] Repo exists at new GitHub location
- [ ] `docker compose up -d` builds all 3 services without errors
- [ ] `docker compose logs frontend --tail=5` shows no errors
- [ ] `docker compose logs backend --tail=5` shows no errors
- [ ] Browser at localhost:47178 loads without 500 errors
- [ ] `meta.json` contains "Horizon 30"
- [ ] No linter warnings introduced
- [ ] LEARNINGS.md updated if any gotchas discovered during fork

## Notes

- Keep `.env` and `.env.example` files — they'll need the same Stripe/Anthropic keys
- Keep the deploy scripts (`deploy-demo.sh`, `deploy.sh`) — update later when we have hosting
- The existing ComCoi DB schema will be present after this task. That's fine — TASK-0.2 strips it.
- **CRITICAL: Do NOT push to GitHub until TASK-0.2 AND TASK-0.3 are complete** (backend + frontend stripping). ComCoi salon code must never appear in the public Horizon repo. Work stays local until the safety point is reached.
- **Git remote already configured (2026-05-07):** `comcoi` = original ComCoi repo (protected, never push), `origin` = `https://github.com/richardosborne14/horizon.git` (Horizon repo). The rename from "Horizon 30" to "Horizon" is already applied everywhere in task docs.
