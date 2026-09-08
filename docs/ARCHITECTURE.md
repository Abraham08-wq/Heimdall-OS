# ProjectXY — Architecture Reference

> Last updated: 2026-07

---

## Overview

ProjectXY is a **sovereign cyber-intelligence platform** — a full-stack, multi-tenant system designed for enterprise security operations, threat intelligence, and autonomous incident response.

```
Browser
  │
  ▼
Traefik (reverse proxy, :80)
  ├── /           → Next.js Frontend (SSR + React)
  └── /api/v1/*   → FastAPI Backend
                        ├── PostgreSQL (relational data + pgvector embeddings)
                        ├── Neo4j (entity relationship graph)
                        ├── Redis (session cache, Ghost Shell state)
                        ├── Kafka (async event streaming)
                        └── Ollama (local LLM inference)
```

---

## 1 · Request Flow

```
User Browser
    │  HTTP/WS
    ▼
Traefik (traefik:v3.1)
    │  routes by Host/PathPrefix
    ├──► /api/v1/*  → backend:8000  (FastAPI)
    └──► /*         → frontend:3000 (Next.js)
                         │
                         │  Server-side fetch to backend:8000
                         │  (container-to-container, no public port)
                         ▼
                    FastAPI (uvicorn, async)
                         │
                         ├── PostgreSQL (asyncpg driver)
                         ├── Neo4j     (bolt driver)
                         ├── Redis     (aioredis)
                         └── Kafka     (aiokafka producer)
```

> [!IMPORTANT]
> All browser-originated API calls **must** use the `/api/v1` proxy path through Next.js — never port 8000 directly. The backend port is not exposed to the host.

---

## 2 · Technology Stack

### Infrastructure

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Reverse Proxy | Traefik v3.1 | TLS termination, routing |
| Orchestration | Docker Compose | Local/self-hosted deployment |
| Container Registry | — | Build locally |

### Backend

| Component | Technology |
|-----------|-----------|
| Runtime | Python 3.11+, FastAPI, Uvicorn |
| ORM | SQLAlchemy 2.x (async) |
| Migrations | Alembic |
| Auth | JWT (HS256), Passlib + Bcrypt |
| Relational DB | PostgreSQL 15 + pgvector |
| Graph DB | Neo4j 5.x |
| Cache / KV | Redis 7.2 |
| Messaging | Apache Kafka (Confluent) |
| Local LLM | Ollama (llama3 / mistral) |
| HTTP client | httpx (async) |
| DNS | stdlib `socket` + dnspython (optional) |

### Frontend

| Component | Technology |
|-----------|-----------|
| Framework | Next.js 14 (App Router, SSR) |
| Language | TypeScript (strict mode) |
| Styling | Vanilla CSS + CSS custom properties |
| State | Zustand |
| Animations | Framer Motion |
| Charts | Recharts |
| Icons | Lucide React |
| API client | `src/lib/api.ts` singleton (fetch wrapper) |

---

## 3 · Backend Module Map

```
backend/app/
├── api/v1/endpoints/        # FastAPI routers
│   ├── auth.py              # JWT login / register
│   ├── config.py            # device-types, simulation-types, playbooks
│   ├── devices.py           # Device CRUD with type/status filters
│   ├── entities.py          # Entity + IOC management
│   ├── intelligence.py      # Threat intelligence feed
│   ├── missions.py          # Async OSINT mission runner
│   └── ...
│
├── core/
│   ├── config.py            # Pydantic Settings (reads .env.local)
│   └── security.py          # JWT helpers
│
├── infrastructure/
│   ├── session.py           # SQLAlchemy AsyncSession factory
│   └── graph.py             # Neo4j driver wrapper
│
├── models/
│   ├── models.py            # SQLAlchemy ORM models
│   └── config_model.py      # ConfigEntry (dynamic config table)
│
├── modules/
│   ├── recon/
│   │   └── osint_engine.py  # Passive OSINT: DNS, HTTP headers, Shodan
│   ├── sandbox/             # Twin-sandbox for threat simulation
│   ├── ghost/               # Ghost Shell deception lattice (Redis-backed)
│   └── warroom/             # WarRoom attribution + containment
│
└── services/
    ├── response_orchestrator.py  # Automated response (loads playbooks from DB)
    ├── combat.py                 # WebSocket broadcast hub
    ├── audit.py                  # Immutable audit log
    └── security/
        └── vaccine.py            # Hive-mind threat inoculation
```

---

## 4 · Database Schema (Key Tables)

```
tenants              — Multi-tenant root table
users                — Auth users (role: admin | analyst | operator)
devices              — Network devices (typed: server | workstation | iot | ...)
entities             — Threat actors, IPs, domains (graph nodes)
ioc_records          — Indicators of Compromise (linked to entities)
threat_events        — SIEM events stream
missions             — Async OSINT mission state machine
config_entries       — Dynamic config (device_types, soc_playbooks, ...)
audit_logs           — Immutable action log
```

### ConfigEntry categories

| `category` | Purpose |
|------------|---------|
| `device_types` | UI device-type filter options |
| `simulation_types` | SOC simulation scenarios |
| `soc_playbooks` | Auto-response policy per tenant |
| `offensive_tools` | Arsenal capability registry |

---

## 5 · Authentication Flow

```
POST /api/v1/auth/login
    │  { email, password }
    ▼
FastAPI verifies bcrypt hash → issues JWT (30 min expiry)
    │
    ▼  Bearer <token> on every subsequent request
FastAPI JWTBearer dependency → decodes → injects current_user
```

All endpoints except `/auth/login` and `/auth/register` require a valid JWT.
Admin-only endpoints additionally check `current_user.role == "admin"`.

---

## 6 · Ghost Shell (Deception Lattice)

Ghost Shell is the active deception subsystem:
- **Sessions** are stored in Redis (`ghost:sessions:<id>`) with configurable TTL
- **Payloads** are generated on-demand and cached
- The frontend polls `/api/v1/ghost/sessions` and `/api/v1/ghost/payloads`
- WebSocket events broadcast deception triggers to the dashboard in real-time

---

## 7 · OSINT Mission State Machine

```
IDLE → RECON → ANALYZE → EXECUTE → PERSIST → COMPLETED
                                            ↘ FAILED
```

Each mission is a row in the `missions` table.
The frontend polls `GET /api/v1/missions/<id>` every 3s and renders the phase progression in OmniProbe.

---

## 8 · Response Orchestrator

The `ResponseOrchestrator` evaluates threat scores against tenant policies loaded **live from the DB** (`config_entries` where `category='soc_playbooks'`):

| Risk Score | Action |
|-----------|--------|
| ≥ 90 | Block IP (firewall API call) |
| ≥ 80 | Throttle ASN (rate-limit gateway) |
| ≥ 75 | Force MFA (deactivate sessions) |
| < 75 | Log only |

Policies are per-tenant and hot-reloadable — no restart required.

---

## 9 · Security Boundaries

| Boundary | Control |
|----------|---------|
| Inbound traffic | Traefik (single entry point) |
| Backend port | Not exposed to host (`expose:` not `ports:`) |
| Auth | JWT, bcrypt, minimum 32-char secret |
| SQL injection | SQLAlchemy parameterised queries only |
| Audit trail | Every action logged to `audit_logs` (immutable) |
| Multi-tenancy | All queries scoped by `tenant_id` |
| CORS | Explicit allowlist in `BACKEND_CORS_ORIGINS` |

---

## 10 · Adding a New API Endpoint

1. Create router in `backend/app/api/v1/endpoints/your_module.py`
2. Register it in `backend/app/api/v1/api.py`
3. Add typed methods to `frontend/src/lib/api.ts`
4. Use `api.yourMethod()` in the frontend component (never `fetch('/api/v1/...')` directly)
