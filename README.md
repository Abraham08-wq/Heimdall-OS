# ProjectXY — Sovereign Cyber Intelligence Platform

> **Production-grade multi-tenant threat intelligence, OSINT, and autonomous incident response.**

---

## What is ProjectXY?

ProjectXY is an enterprise security operations platform that provides:

- **Real-time threat intelligence** — graph-based entity correlation, IOC tracking, and live OSINT missions
- **Autonomous incident response** — SOAR playbooks loaded from the database, zero-trust auto-blocking
- **SOC operations** — simulation scenarios, watchlists, device inventory with risk scoring
- **Ghost Shell** — active deception lattice with Redis-backed session management
- **War Room** — global risk heatmaps, neural de-masking, breach archives, attribution engine
- **Nexus Terminal** — full-spectrum command console with mission control, exploit synthesis, and honeypot routing
- **AI Oracle** — context-aware analyst copilot backed by a local LLM (Ollama)

---

## Quick Start

```bash
# 1. Clone and configure
git clone <repo-url> ProjectXY && cd ProjectXY
cp .env.template .env.local
# → Edit .env.local with your secrets

# 2. Start the low-RAM stack
./start_services.sh

# Or use the setup helper, which always forces the lite profile
bash QUICK_START.sh

# Full stack (heavy services) when the machine can handle it
PROJECTXY_COMPOSE_FILE=docker-compose.yml ./start_services.sh

# Explicit shortcuts
bash start_lite_services.sh
bash start_full_services.sh

# 3. Migrate database
docker compose exec backend alembic upgrade head

# 4. Seed data + create admin
docker compose exec backend python scripts/seed.py
docker compose exec backend python scripts/seed_admin.py

# 5. Open
open http://localhost
```

**Full setup instructions → [docs/SETUP.md](docs/SETUP.md)**

---

## Architecture

```
Browser → Traefik (:80) → Next.js Frontend / FastAPI Backend
                               ↓
                    PostgreSQL + Neo4j + Redis + Kafka + Ollama
```

**Full architecture reference → [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**

---

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, TypeScript, Zustand, Framer Motion |
| Backend | FastAPI, SQLAlchemy 2 (async), Alembic |
| Databases | PostgreSQL 15 + pgvector, Neo4j 5, Redis 7 |
| Messaging | Apache Kafka |
| Local AI | Ollama (llama3 / mistral) |
| Proxy | Traefik v3.1 |
| Containers | Docker Compose |

---

## Project Structure

```
ProjectXY/
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── api/v1/         # Route handlers
│   │   ├── models/         # SQLAlchemy ORM + ConfigEntry
│   │   ├── modules/        # OSINT engine, Ghost Shell, sandbox, warroom
│   │   └── services/       # Response orchestrator, combat hub, audit log
│   ├── alembic/            # Database migrations
│   ├── scripts/            # Admin seed, migration utilities
│   └── seed.py             # Data seeder (config, APT actors, arsenal)
│
├── frontend/               # Next.js application
│   └── src/
│       ├── app/            # App Router pages
│       ├── components/     # Shared UI components
│       ├── modules/        # Dashboard feature modules
│       └── lib/api.ts      # Typed API client (single source of truth)
│
├── docs/
│   ├── SETUP.md            # Environment setup guide
│   └── ARCHITECTURE.md     # System architecture reference
│
├── docker-compose.yml      # Full stack definition
├── traefik.yml             # Reverse proxy config
└── .env.template           # Environment variable template
```

---

## Key Design Decisions

- **Proxy-only API access** — All frontend requests go through `/api/v1` (Next.js proxy). The backend port is never exposed directly.
- **Dynamic config** — Device types, simulation scenarios, and SOC playbooks are stored in the `config_entries` table, not hardcoded. Hot-reloadable without restart.
- **Typed API client** — `frontend/src/lib/api.ts` is the single point of contact between the frontend and backend. All methods are typed and validated.
- **TypeScript strict mode** — `ignoreBuildErrors: false` in `next.config.js`. Zero type errors required for build to succeed.
- **Live playbook loading** — `ResponseOrchestrator` reads tenant policies from DB on every invocation. No config restart needed.
- **Graceful OSINT degradation** — OSINT engine works without any API keys (falls back to safe placeholder data). Keys are additive.
- **Low-RAM local mode** — `docker-compose.lite.yml` starts only Postgres, Redis, backend, and frontend. Heavy graph/LLM/streaming services stay opt-in for stronger hardware or CI runners.
- **Automatic stack selection** — `start_services.sh` defaults to the lite profile on machines below roughly 6 GB RAM and warns before starting the full profile on small hosts.

---

## Scripts Reference

```bash
# Admin user creation (interactive or via env)
docker compose exec backend python scripts/seed_admin.py

# Run type check (frontend)
cd frontend && npx tsc --noEmit

# Apply new migration
docker compose exec backend alembic upgrade head

# Rebuild backend after Python changes
docker compose up -d --build backend

# View all logs
docker compose logs -f
```

---

## License

Proprietary — All rights reserved.
