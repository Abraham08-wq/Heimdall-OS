# ProjectXY — Setup Guide

> **Estimated setup time:** 15 minutes (with Docker)

---

## Prerequisites

| Tool | Minimum Version | Notes |
|------|----------------|-------|
| Docker | 24.x | With Compose v2 plugin |
| Docker Compose | 2.20+ | `docker compose` (not `docker-compose`) |
| Git | any | |
| Node.js | 18+ | For local frontend dev only |
| Python | 3.11+ | For running seed/admin scripts only |

---

## 1 · Clone & Configure

```bash
git clone <repo-url> ProjectXY
cd ProjectXY
```

### 1.1 Environment file

Copy the template and fill in your values:

```bash
cp .env.template .env.local
```

Open `.env.local` and set **all required fields**:

```env
# ── Security ───────────────────────────────────────────────
JWT_SECRET_KEY=<minimum 32 random chars — generate with: openssl rand -hex 32>

# ── Database ───────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/projectxy
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<strong password>
POSTGRES_DB=projectxy

# ── Neo4j ──────────────────────────────────────────────────
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<strong password>

# ── Redis ──────────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0

# ── Frontend (internal routing) ────────────────────────────
FRONTEND_URL=http://frontend:3000
NEXT_PUBLIC_API_URL=http://localhost/api/v1

# ── OSINT API keys (optional — system works without them) ──
SHODAN_API_KEY=
CENSYS_API_ID=
CENSYS_API_SECRET=
ALIENVAULT_API_KEY=
INTEL_X_API_KEY=
```

> [!IMPORTANT]
> Never commit `.env.local`. It is already in `.gitignore`.

---

## 2 · Start the Stack

```bash
./start_services.sh
```

This defaults to the low-RAM stack: Postgres, Redis, FastAPI backend, and Next.js frontend.

Use the full stack only when you have the memory headroom for Neo4j, Kafka, Ollama, and Traefik:

```bash
PROJECTXY_COMPOSE_FILE=docker-compose.yml ./start_services.sh
```

Explicit wrappers:

```bash
bash start_lite_services.sh
bash start_full_services.sh
```

`QUICK_START.sh` also forces the lite profile and runs the initial backend migration, which is the safest path for a 4 GB machine.

Full stack services (see [Architecture](ARCHITECTURE.md) for details):
- **Traefik** reverse proxy on `:80`
- **PostgreSQL** + pgvector on `:5432` (internal only)
- **Neo4j** on `:7687` / `:7474` (internal only)
- **Redis** (internal only)
- **Kafka** + Zookeeper (internal only)
- **FastAPI backend** (internal, exposed via proxy at `/api/v1`)
- **Next.js frontend** (internal, exposed via proxy at `/`)
- **Ollama** local LLM on `:11434` (internal only)

```bash
# Watch logs during startup
docker compose logs -f backend frontend
```

---

## 3 · Run Database Migrations

```bash
docker compose exec backend alembic upgrade head
```

---

## 4 · Seed Initial Data

### 4.1 Seed config + threat actors + arsenal

```bash
docker compose exec backend python seed.py
```

This populates:
- `config_entries` table (device types, simulation types, SOC playbooks)
- 8 real APT threat actors in `entities`
- Offensive tool records in the arsenal

### 4.2 Create the first admin user

```bash
docker compose exec backend python scripts/seed_admin.py
```

Or via environment variables (for CI/CD):

```bash
docker compose exec -e ADMIN_EMAIL=ciso@corp.com \
                   -e ADMIN_PASSWORD=MyStr0ngP@ss \
                   backend python scripts/seed_admin.py
```

---

## 5 · Access the System

| Service | URL | Default Credentials |
|---------|-----|---------------------|
| Dashboard | http://localhost | Set in step 4.2 |
| API Docs (Swagger) | http://localhost/api/v1/docs | — |
| Neo4j Browser | http://localhost:7474 | `neo4j` / `<NEO4J_PASSWORD>` |

---

## 6 · Local Development (without Docker)

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Export env vars
export $(grep -v '^#' ../.env.local | xargs)

# Run migrations
alembic upgrade head

# Start FastAPI
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev        # Starts on http://localhost:3000
```

> [!NOTE]
> In local dev mode the frontend proxies `/api/v1/*` to `http://localhost:8000` via `next.config.js`.

---

## 7 · Useful Commands

```bash
# Rebuild after code changes
docker compose up -d --build backend

# Apply a new DB migration
docker compose exec backend alembic revision --autogenerate -m "describe change"
docker compose exec backend alembic upgrade head

# Run the OSINT engine test
docker compose exec backend python -c "
import asyncio
from app.modules.recon.osint_engine import osint_global_engine
print(asyncio.run(osint_global_engine.resolve_dns_records('google.com')))
"

# Tail backend logs
docker compose logs -f --tail=100 backend

# Hard reset (destroys all data)
docker compose down -v
```

---

## 8 · Troubleshooting

| Symptom | Fix |
|---------|-----|
| `NS_ERROR_CONNECTION_REFUSED` in browser | Frontend is not running or Traefik not started. Run `docker compose ps`. |
| `alembic upgrade head` fails | Check `DATABASE_URL` in `.env.local`. Ensure PostgreSQL container is healthy. |
| Login returns 401 after seed | Ensure `JWT_SECRET_KEY` is the same in `.env.local` as when the token was issued. |
| Neo4j connection refused | Neo4j takes ~30s to initialise. Retry after a moment. |
| `SHODAN_API_KEY not configured` log | Expected. Shodan falls back to placeholder data. Add the key to `.env.local` to enable live lookups. |
