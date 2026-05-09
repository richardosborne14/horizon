# Horizon

Moteur patrimonial multi-décennal pour freelances français. Simulez vos revenus, charges, épargne et investissements sur 30 ans pour visualiser votre chemin vers la liberté financière.

## Stack

| Layer | Tech |
|-------|------|
| Frontend | SvelteKit (Node.js) |
| Backend | FastAPI (Python) |
| Database | PostgreSQL 16 + pgvector |
| Auth | JWT (bcrypt) |
| Reverse Proxy | Caddy |
| Hosting | Hetzner Cloud (DE) |

## Local Development

```bash
docker compose up -d
```

| Service | Port |
|---------|------|
| Frontend | http://localhost:47178 |
| Backend API | http://localhost:47002 |
| Database | localhost:47432 |

## Architecture

See `dev-docs/ARCHITECTURE.md` for system design, DB schema, and route architecture.

## Phase

**Sprint 0 — Fork & Strip.** Forked from Communauté Coiffure (ComCoi) V2 codebase. Stripping salon-specific domain to create a clean Horizon shell.