#!/usr/bin/env bash
# =============================================================================
# ProjectXY — Automated Reconstruction Script
# Generated from a full read of the actual repo (zip uploaded to chat).
# Run this from the ProjectXY project root:
#   chmod +x reconstruct.sh && ./reconstruct.sh
#
# What this does:
#   1. Backs up every file it's about to change into ./_reconstruct_backup_<ts>/
#   2. Writes/overwrites the root-level docker + env setup files
#   3. Writes/overwrites the fixed frontend files (SituationRoom, DeviceRegistry, devices page)
#   4. Patches backend/app/main.py: removes a dead duplicate /health block with
#      orphaned code, and fixes CORS to validate against BACKEND_CORS_ORIGINS
#      instead of reflecting any request Origin header unconditionally
#   5. Creates .env.local from .env.template ONLY if .env.local doesn't already
#      exist — never touches your real secrets
#   6. Prints a summary of what changed and what to run next
#
# Nothing here is applied silently and irreversibly — every touched file gets
# a timestamped backup first. If anything looks wrong afterward, restore from
# $BACKUP_DIR.
# =============================================================================
set -euo pipefail

if [ ! -d "frontend" ] || [ ! -d "backend" ]; then
  echo "ERROR: run this from the ProjectXY project root (must contain frontend/ and backend/)." >&2
  exit 1
fi

BACKUP_DIR="./_reconstruct_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
echo "Backups will be written to $BACKUP_DIR"
echo ""

CHANGED=()
SKIPPED=()

echo "== [1/4] Root-level setup files =="
echo "  -> ./docker-compose.yml"
mkdir -p "$(dirname "./docker-compose.yml")"
if [ -f "./docker-compose.yml" ]; then cp "./docker-compose.yml" "$BACKUP_DIR/.__docker-compose.yml.bak"; fi
cat > "./docker-compose.yml" << 'PXY_RECONSTRUCT_EOF'
# =============================================================================
# ProjectXY — Sovereign Architecture Docker Compose  (FULL / heavy profile)
# Matches the architecture documented in README.md.
#
# IMPORTANT — env file scope:
# `env_file: .env.local` on a service only injects variables into that
# CONTAINER at runtime. It does NOT feed Compose's own ${VAR} interpolation
# (used below in frontend's build.args) — that only reads a file literally
# named `.env`, or the shell. Run this file with:
#   docker compose --env-file .env.local -f docker-compose.yml up -d
# (start_full_services.sh does this for you.)
#
# Per README's Quick Start, migrations and seeding are run manually AFTER the
# stack is up, via `docker compose exec backend ...` — see the bottom of this
# file for the exact commands. There are no automatic migrate/seed one-shot
# services here; that was a mismatch in an earlier draft of this file.
# =============================================================================

services:

  # ── REVERSE PROXY ──────────────────────────────────────────────────────────
  traefik:
    # NOTE: README's stack table lists "Traefik v3.1", but any Traefik build
    # before v3.6.1 fails outright on Docker Engine 29+ (min API bumped to 1.44;
    # those builds hardcode API 1.24 -> "client version 1.24 is too old").
    # Pinned to v3.6 here so it actually runs; update docs/ARCHITECTURE.md and
    # this README line to v3.6 to match, or pin back to v3.1 if your hosts are
    # still on Docker Engine < 29.
    image: public.ecr.aws/docker/library/traefik:v3.6
    restart: unless-stopped
    command:
      - "--configFile=/etc/traefik/traefik.yml"
    ports:
      - "80:80"
      - "443:443"
      - "8080:8080"   # Traefik dashboard
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./traefik.yml:/etc/traefik/traefik.yml:ro
      - ./traefik_dynamic:/etc/traefik/dynamic:ro
      - ./certs:/certs:ro
    networks:
      - projectxy-net
    healthcheck:
      test: [ "CMD", "traefik", "healthcheck", "--ping" ]
      interval: 30s
      timeout: 5s
      retries: 3

  # ── POSTGRESQL + PGVECTOR ──────────────────────────────────────────────────
  postgres:
    # FIXED: plain postgres:15-alpine does not ship pgvector, but README's stack
    # table lists "PostgreSQL 15 + pgvector" — any migration/model relying on
    # `CREATE EXTENSION vector` would fail against the old image.
    image: pgvector/pgvector:pg15
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports:
      # ADDED: matches .env.local's DATABASE_URL_LOCAL (localhost:5433) for
      # host-side psql/DBeaver access. Remove this if you don't want Postgres
      # reachable outside the Docker network at all.
      - "5433:5432"
    volumes:
      - database_data:/var/lib/postgresql/data
      - ./database/postgres/init:/docker-entrypoint-initdb.d:ro
    networks:
      - projectxy-net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 15
      start_period: 30s
    mem_limit: 1g
    cpus: "1.0"

  # ── NEO4J GRAPH DATABASE ───────────────────────────────────────────────────
  neo4j:
    image: public.ecr.aws/docker/library/neo4j:5.16.0
    restart: unless-stopped
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
      NEO4J_server_memory_heap_initial__size: 512m
      NEO4J_server_memory_heap_max__size: 1G
      NEO4J_server_memory_pagecache_size: 512m
      NEO4J_dbms_security_procedures_unrestricted: "apoc.*"
      NEO4J_PLUGINS: '["apoc"]'
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
    networks:
      - projectxy-net
    healthcheck:
      test: ["CMD-SHELL", "wget -q --spider http://127.0.0.1:7474 || exit 1"]
      interval: 20s
      timeout: 10s
      retries: 10
      start_period: 90s
    mem_limit: 2g
    cpus: "1.5"

  # ── REDIS (Pub/Sub + Cache + Rate Limiting + Ghost Shell sessions) ─────────
  redis:
    image: public.ecr.aws/docker/library/redis:7.2-alpine
    restart: unless-stopped
    command: >
      redis-server
      --appendonly yes
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    networks:
      - projectxy-net
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
    mem_limit: 384m

  # ── ZOOKEEPER (Kafka dependency) ───────────────────────────────────────────
  zookeeper:
    # FIXED: public.ecr.aws/ubuntu/zookeeper:latest is a stale build using
    # Canonical's rock packaging, incompatible with the Confluent-style env
    # vars used here and by `kafka`. Using Confluent's images instead.
    image: confluentinc/cp-zookeeper:7.5.3
    restart: unless-stopped
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    networks:
      - projectxy-net
    healthcheck:
      test: ["CMD-SHELL", "bash -c 'echo > /dev/tcp/localhost/2181' 2>/dev/null && echo ok || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 30s
    mem_limit: 384m

  # ── KAFKA (Event Streaming) ────────────────────────────────────────────────
  kafka:
    image: confluentinc/cp-kafka:7.5.3
    restart: unless-stopped
    depends_on:
      zookeeper: { condition: service_healthy }
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"
      KAFKA_HEAP_OPTS: "-Xms512m -Xmx512m"
    networks:
      - projectxy-net
    healthcheck:
      test: ["CMD-SHELL", "bash -c 'echo > /dev/tcp/localhost/29092' 2>/dev/null && echo ok || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 20
      start_period: 90s
    mem_limit: 1g
    cpus: "1.0"

  # ── KAFKA TOPIC SETUP (one-shot) ───────────────────────────────────────────
  kafka-setup:
    image: confluentinc/cp-kafka:7.5.3
    restart: "no"
    depends_on:
      kafka: { condition: service_healthy }
    networks:
      - projectxy-net
    entrypoint: ["/bin/bash", "-c"]
    command:
      - |
        set -e
        echo '[KAFKA-SETUP] Creating required topics...'
        for topic in firewall_events compliance_events threat_feed infrastructure_telemetry ai_agent_telemetry mobile_session_events auth_events siem_alerts; do
          kafka-topics --bootstrap-server kafka:29092 --create --if-not-exists \
            --topic "$$topic" --partitions 3 --replication-factor 1
          echo "[KAFKA-SETUP] Topic: $$topic OK"
        done
        echo '[KAFKA-SETUP] All topics ready.'

  # ── OLLAMA (Local LLM — AI Oracle copilot) ─────────────────────────────────
  ollama:
    # FIXED: public.ecr.aws/as-images/ollama does not exist anywhere on ECR.
    image: ollama/ollama:latest
    restart: unless-stopped
    volumes:
      - ollama_models:/root/.ollama
    networks:
      - projectxy-net
    ports:
      - "11435:11434"
    healthcheck:
      test: [ "CMD-SHELL", "ollama list >/dev/null 2>&1 || exit 1" ]
      interval: 30s
      timeout: 15s
      retries: 10
      start_period: 120s
    mem_limit: 6g
    cpus: "3.0"

  # ── OLLAMA MODEL PULL (one-shot) ───────────────────────────────────────────
  # ADDED: the ollama image ships with no models; without this, the AI Oracle
  # module fails on first request. Watch progress with:
  #   docker compose logs -f ollama-pull
  ollama-pull:
    image: ollama/ollama:latest
    restart: "no"
    depends_on:
      ollama: { condition: service_healthy }
    environment:
      OLLAMA_HOST: ollama:11434
    entrypoint: ["/bin/sh", "-c"]
    command: ["ollama pull ${OLLAMA_MODEL:-llama3.2}"]
    networks:
      - projectxy-net

  # ── BACKEND (FastAPI) ──────────────────────────────────────────────────────
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: unless-stopped
    user: "root"
    env_file: .env.local
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      DATABASE_URL_SYNC: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: ${NEO4J_PASSWORD}
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      KAFKA_BOOTSTRAP_SERVERS: kafka:29092
      OLLAMA_BASE_URL: http://ollama:11434
      OLLAMA_MODEL: ${OLLAMA_MODEL:-llama3.2}
      ENABLE_OLLAMA: "true"
      PYTHONPATH: /app
      ENVIRONMENT: production
      AUTH_BYPASS_ENABLED: "false"
      LOG_LEVEL: INFO
      FORWARDED_ALLOW_IPS: "*"
      SECURE_PROXY_SSL_HEADER: "X-Forwarded-Proto"
      # BACKEND_CORS_ORIGINS comes from .env.local via env_file above — no
      # override here, so the explicit origin list actually reaches FastAPI.
    depends_on:
      postgres: { condition: service_healthy }
      neo4j: { condition: service_healthy }
      redis: { condition: service_healthy }
      kafka: { condition: service_healthy }
      ollama: { condition: service_healthy }
    networks:
      - projectxy-net
    mem_limit: 3g
    cpus: "2.0"
    # REMOVED: `ports: - "8001:8000"`. README's own "Key Design Decisions"
    # section states the backend port is never exposed directly — all access
    # goes through Traefik (which reaches this container over the internal
    # Docker network regardless of whether a host port is published) or
    # through the frontend's own API proxy. Publishing 8001:8000 let anyone on
    # the host bypass both of those and hit FastAPI directly.
    healthcheck:
      test: [ "CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5).read()\"" ]
      interval: 15s
      timeout: 5s
      retries: 10
      start_period: 5m
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=projectxy-net"

      # CORS is handled once, in FastAPI (BACKEND_CORS_ORIGINS in .env.local).
      # Do not also attach a Traefik CORS middleware to these routers — two
      # sets of Access-Control-* headers on one response is what causes
      # "multiple values" CORS errors in the browser console.

      - "traefik.http.routers.backend.rule=Host(`localhost`) && PathPrefix(`/api`)"
      - "traefik.http.routers.backend.entrypoints=web,websecure"
      - "traefik.http.routers.backend.tls=true"
      - "traefik.http.services.backend.loadbalancer.server.port=8000"

      - "traefik.http.routers.backend-ws.rule=Host(`localhost`) && PathPrefix(`/api/v1/ws`)"
      - "traefik.http.routers.backend-ws.entrypoints=web,websecure"
      - "traefik.http.routers.backend-ws.tls=true"
      - "traefik.http.routers.backend-ws.service=backend"

  # ── FRONTEND (Next.js) ─────────────────────────────────────────────────────
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        BACKEND_URL: http://backend:8000
        # These need `ARG NEXT_PUBLIC_API_URL` + `ENV NEXT_PUBLIC_API_URL=...`
        # in frontend/Dockerfile *before* `next build` — Next.js inlines
        # NEXT_PUBLIC_* vars at build time, so setting them only under
        # `environment:` below has no effect on an already-built image.
        NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL}
        NEXT_PUBLIC_WS_URL: ${NEXT_PUBLIC_WS_URL}
    restart: unless-stopped
    env_file: .env.local
    environment:
      BACKEND_URL: http://backend:8000
      NEXT_PUBLIC_DEV_MODE: "false"
      NEXT_PUBLIC_FAST_LOGIN: "true"
      NODE_ENV: production
    ports:
      - "3000:3000"
    depends_on:
      backend:
        condition: service_healthy
    networks:
      - projectxy-net
    mem_limit: 1g
    cpus: "1.0"
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.frontend.rule=Host(`localhost`)"
      - "traefik.http.routers.frontend.entrypoints=websecure"
      - "traefik.http.routers.frontend.tls=true"
      - "traefik.http.services.frontend.loadbalancer.server.port=3000"
      - "traefik.docker.network=projectxy-net"


# ── VOLUMES ─────────────────────────────────────────────────────────────────
volumes:
  database_data:
  neo4j_data:
  neo4j_logs:
  redis_data:
  ollama_models:


# ── NETWORKS ─────────────────────────────────────────────────────────────────
networks:
  projectxy-net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/24

# =============================================================================
# After `docker compose up -d`, per README's Quick Start:
#   docker compose exec backend alembic upgrade head
#   docker compose exec backend python scripts/seed.py
#   docker compose exec backend python scripts/seed_admin.py
# =============================================================================
PXY_RECONSTRUCT_EOF
CHANGED+=("./docker-compose.yml")
echo "  -> ./docker-compose.lite.yml"
mkdir -p "$(dirname "./docker-compose.lite.yml")"
if [ -f "./docker-compose.lite.yml" ]; then cp "./docker-compose.lite.yml" "$BACKUP_DIR/.__docker-compose.lite.yml.bak"; fi
cat > "./docker-compose.lite.yml" << 'PXY_RECONSTRUCT_EOF'
# =============================================================================
# ProjectXY — LITE profile
# Per README: "docker-compose.lite.yml starts only Postgres, Redis, backend,
# and frontend. Heavy graph/LLM/streaming services stay opt-in."
#
# CAVEAT (please verify): this assumes the backend can start and serve traffic
# without Neo4j, Kafka, or Ollama connections available — README only
# documents "Graceful OSINT degradation" for missing API keys, not graceful
# degradation for missing infrastructure. If backend/app/core/config.py or the
# module init code hard-fails when NEO4J_URI/KAFKA_BOOTSTRAP_SERVERS/
# OLLAMA_BASE_URL can't be reached, this profile will crash-loop the backend
# container. Share that file and I'll adjust this if so — e.g. an
# ENABLE_NEO4J=false / ENABLE_KAFKA=false toggle the app checks before
# connecting.
#
# No Traefik in this profile (per README) — frontend is reached directly.
# Run with:
#   docker compose --env-file .env.local -f docker-compose.lite.yml up -d
# =============================================================================

services:

  postgres:
    image: pgvector/pgvector:pg15
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports:
      - "5433:5432"
    volumes:
      - database_data_lite:/var/lib/postgresql/data
      - ./database/postgres/init:/docker-entrypoint-initdb.d:ro
    networks:
      - projectxy-net-lite
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 15
      start_period: 30s
    mem_limit: 512m
    cpus: "0.5"

  redis:
    image: public.ecr.aws/docker/library/redis:7.2-alpine
    restart: unless-stopped
    command: >
      redis-server
      --appendonly yes
      --maxmemory 128mb
      --maxmemory-policy allkeys-lru
      --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data_lite:/data
    networks:
      - projectxy-net-lite
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
    mem_limit: 192m

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: unless-stopped
    user: "root"
    env_file: .env.local
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      DATABASE_URL_SYNC: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      # Heavy services are absent in this profile — these toggles need to
      # exist and be honored in backend/app/core/config.py for lite mode to
      # actually work rather than error on startup.
      ENABLE_NEO4J: "false"
      ENABLE_KAFKA: "false"
      ENABLE_OLLAMA: "false"
      PYTHONPATH: /app
      ENVIRONMENT: development
      AUTH_BYPASS_ENABLED: "false"
      LOG_LEVEL: INFO
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
    networks:
      - projectxy-net-lite
    mem_limit: 1g
    cpus: "1.0"
    # No host port published — same "backend never exposed directly" rule as
    # the full profile. The frontend reaches it over the internal network via
    # BACKEND_URL and proxies browser requests itself.
    healthcheck:
      test: [ "CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5).read()\"" ]
      interval: 15s
      timeout: 5s
      retries: 10
      start_period: 3m

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        BACKEND_URL: http://backend:8000
        # No Traefik/TLS in lite mode — plain http, same-origin relative path
        # is safest so this works identically to the full profile's browser
        # code. Confirm against frontend/src/lib/api.ts.
        NEXT_PUBLIC_API_URL: /api/v1
        NEXT_PUBLIC_WS_URL: ${NEXT_PUBLIC_WS_URL_LITE:-ws://localhost:3000/api/v1}
    restart: unless-stopped
    env_file: .env.local
    environment:
      BACKEND_URL: http://backend:8000
      NEXT_PUBLIC_DEV_MODE: "true"
      NEXT_PUBLIC_FAST_LOGIN: "true"
      NODE_ENV: production
    ports:
      - "3000:3000"
    depends_on:
      backend:
        condition: service_healthy
    networks:
      - projectxy-net-lite
    mem_limit: 768m
    cpus: "0.5"


volumes:
  database_data_lite:
  redis_data_lite:

networks:
  projectxy-net-lite:
    driver: bridge
PXY_RECONSTRUCT_EOF
CHANGED+=("./docker-compose.lite.yml")
echo "  -> ./.env.template"
mkdir -p "$(dirname "./.env.template")"
if [ -f "./.env.template" ]; then cp "./.env.template" "$BACKUP_DIR/.__.env.template.bak"; fi
cat > "./.env.template" << 'PXY_RECONSTRUCT_EOF'
# ==============================================================================
# Project Heimdall — Sovereign Cyber Intelligence Platform Configuration Surface
# TEMPLATE — copy this to .env.local and fill in real secrets:
#   cp .env.template .env.local
# .env.local should be gitignored; this file should not contain real secrets.
# ==============================================================================

# ── SYSTEM CORE & TELEMETRY REGISTRY ──────────────────────────────────────────
ENVIRONMENT=development
LOG_LEVEL=INFO
TENANT_ID=REPLACE_WITH_UUID
ORGANIZATION_ID=REPLACE_WITH_UUID

# ── DATABASE STORAGE TIER ─────────────────────────────────────────────────────
POSTGRES_USER=postgres
POSTGRES_PASSWORD=REPLACE_ME
POSTGRES_DB=projectxy

DATABASE_URL=postgresql+asyncpg://postgres:REPLACE_ME@postgres:5432/projectxy
DATABASE_URL_SYNC=postgresql://postgres:REPLACE_ME@postgres:5432/projectxy
DATABASE_URL_LOCAL=postgresql+asyncpg://postgres:REPLACE_ME@localhost:5433/projectxy

# ── GRAPH DATABASE ENGINE [NEO4J] ──────────────────────────────────────────────
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=REPLACE_ME_8_CHARS_MIN
NEO4J_URI_LOCAL=bolt://localhost:7687

# ── CACHE & HIGH-THROUGHPUT PUB/SUB TIER ──────────────────────────────────────
REDIS_PASSWORD=REPLACE_ME
# Must match REDIS_PASSWORD above — Compose does not expand ${VARS} across
# lines within an env_file, so write the password out literally, not as ${..}.
REDIS_URL=redis://:REPLACE_ME@redis:6379/0

# ── BACKEND APPLICATION INTERFACE [FASTAPI] ────────────────────────────────────
PYTHONPATH=/app
# Generate independently, e.g. `openssl rand -hex 32` — do NOT reuse the same
# value for both.
JWT_SECRET_KEY=REPLACE_ME_RUN_OPENSSL_RAND_HEX_32
SECRET_KEY=REPLACE_ME_RUN_OPENSSL_RAND_HEX_32_DIFFERENT_VALUE
ACCESS_TOKEN_EXPIRE_MINUTES=60

FRONTEND_URL=http://localhost:3000
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://localhost:8001","http://127.0.0.1:3000"]

ADMIN_USER=admin@projectxy.com
ADMIN_PASSWORD=REPLACE_ME
AUTH_BYPASS_ENABLED=false
AI_ADVISOR_PASSWORD=REPLACE_ME
TEST_USER_PASSWORD=REPLACE_ME

# ── FRONTEND PORTAL MATRIX [NEXT.JS 14] ───────────────────────────────────────
# Full profile (via Traefik, TLS): https://localhost/api1 style below.
# Lite profile (no Traefik): use /api/v1 (relative) instead — see
# docker-compose.lite.yml. Verify both against frontend/src/lib/api.ts.
NEXT_PUBLIC_API_URL=https://localhost/api/v1
NEXT_PUBLIC_WS_URL=wss://localhost/api/v1

# ── OSINT INTELLIGENCE HARVESTER ENGINES ──────────────────────────────────────
# Optional — README: "OSINT engine works without any API keys (falls back to
# safe placeholder data). Keys are additive." Leave blank if you don't have them.
SHODAN_API_KEY=
CENSYS_API_ID=
CENSYS_API_SECRET=
INTEL_X_API_KEY=
ALIENVAULT_API_KEY=
LEAK_LOOKUP_API_KEY=

# ==============================================================================
#         SECURITY ENHANCEMENT CONFIG — East African Fintech Hardening
# ==============================================================================

CGNAT_SAFE_MODE=true
SIM_SWAP_VELOCITY_WINDOW_SECONDS=900
DLQ_MAX_RETRIES=4
DLQ_ALERT_DEPTH_THRESHOLD=100

FW_SIMILARITY_THRESHOLD=0.82
FW_WARN_THRESHOLD=0.70
FW_EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
FW_MAX_PROMPT_LENGTH=8192
FW_REPLAY_TTL_SECONDS=3600

SOAR_WEBHOOK_URL=
TELCO_API_WEBHOOK_SECRET=REPLACE_ME

# ── LOCAL LLM [OLLAMA] ─────────────────────────────────────────────────────────
OLLAMA_MODEL=llama3.2
PXY_RECONSTRUCT_EOF
CHANGED+=("./.env.template")

echo "== [1b/4] Startup scripts =="
echo "  -> ./start_services.sh"
mkdir -p "$(dirname "./start_services.sh")"
if [ -f "./start_services.sh" ]; then cp "./start_services.sh" "$BACKUP_DIR/.__start_services.sh.bak"; fi
cat > "./start_services.sh" << 'PXY_RECONSTRUCT_EOF'
#!/usr/bin/env bash
# Picks a profile and starts ProjectXY.
#
# - If PROJECTXY_COMPOSE_FILE is set, uses that file directly (README:
#   `PROJECTXY_COMPOSE_FILE=docker-compose.yml ./start_services.sh` forces
#   the full/heavy profile regardless of detected RAM).
# - Otherwise auto-detects total system RAM: below ~6 GiB -> lite profile,
#   at or above -> full profile. Warns (but still proceeds) if forced onto
#   the full profile on a low-RAM host.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

LITE_THRESHOLD_MB=6144

detect_total_ram_mb() {
  if [[ "$(uname -s)" == "Darwin" ]]; then
    # macOS: hw.memsize is in bytes
    echo $(( $(sysctl -n hw.memsize) / 1024 / 1024 ))
  elif [ -r /proc/meminfo ]; then
    awk '/MemTotal/ { printf "%d", $2/1024 }' /proc/meminfo
  else
    echo "0"   # unknown; caller decides what to do with 0
  fi
}

if [ -n "${PROJECTXY_COMPOSE_FILE:-}" ]; then
  ram_mb="$(detect_total_ram_mb)"
  if [ "$ram_mb" -gt 0 ] && [ "$ram_mb" -lt "$LITE_THRESHOLD_MB" ] && [ "$PROJECTXY_COMPOSE_FILE" = "docker-compose.yml" ]; then
    echo "[start_services] WARNING: PROJECTXY_COMPOSE_FILE=docker-compose.yml (full profile) forced," >&2
    echo "[start_services] but this host only reports ${ram_mb} MiB RAM (threshold: ${LITE_THRESHOLD_MB} MiB)." >&2
    echo "[start_services] Proceeding anyway since you set it explicitly — expect heavy services to be slow" >&2
    echo "[start_services] or to be OOM-killed. Ctrl+C now to abort, or wait 5s to continue." >&2
    sleep 5
  fi
  echo "[start_services] PROJECTXY_COMPOSE_FILE=${PROJECTXY_COMPOSE_FILE} set explicitly — using it."
  exec docker compose --env-file .env.local -f "${PROJECTXY_COMPOSE_FILE}" up -d
fi

ram_mb="$(detect_total_ram_mb)"

if [ "$ram_mb" -eq 0 ]; then
  echo "[start_services] Could not detect total RAM on this platform — defaulting to lite profile."
  echo "[start_services] Override with: PROJECTXY_COMPOSE_FILE=docker-compose.yml ./start_services.sh"
  exec ./start_lite_services.sh
fi

echo "[start_services] Detected ${ram_mb} MiB total RAM (lite threshold: ${LITE_THRESHOLD_MB} MiB)."

if [ "$ram_mb" -lt "$LITE_THRESHOLD_MB" ]; then
  echo "[start_services] Below threshold — starting lite profile."
  exec ./start_lite_services.sh
else
  echo "[start_services] Above threshold — starting full profile."
  exec ./start_full_services.sh
fi
PXY_RECONSTRUCT_EOF
chmod +x "./start_services.sh"
CHANGED+=("./start_services.sh")
echo "  -> ./start_lite_services.sh"
mkdir -p "$(dirname "./start_lite_services.sh")"
if [ -f "./start_lite_services.sh" ]; then cp "./start_lite_services.sh" "$BACKUP_DIR/.__start_lite_services.sh.bak"; fi
cat > "./start_lite_services.sh" << 'PXY_RECONSTRUCT_EOF'
#!/usr/bin/env bash
# Starts the lite (low-RAM) ProjectXY stack: Postgres, Redis, backend, frontend.
# No Traefik, Neo4j, Kafka, or Ollama — see docker-compose.lite.yml for caveats
# on features that depend on those services.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -f .env.local ]; then
  echo "[start_lite_services] .env.local not found."
  if [ -f .env.template ]; then
    cp .env.template .env.local
    echo "[start_lite_services] Created .env.local from .env.template — edit it with real secrets, then re-run."
  else
    echo "[start_lite_services] No .env.template found either. Create .env.local first."
  fi
  exit 1
fi

echo "[start_lite_services] Starting lite profile (docker-compose.lite.yml)..."
docker compose --env-file .env.local -f docker-compose.lite.yml up -d

cat <<'EOF'

[start_lite_services] Stack starting. Once containers report healthy
(check with: docker compose -f docker-compose.lite.yml ps), run:

  docker compose -f docker-compose.lite.yml exec backend alembic upgrade head
  docker compose -f docker-compose.lite.yml exec backend python scripts/seed.py
  docker compose -f docker-compose.lite.yml exec backend python scripts/seed_admin.py

Then open http://localhost:3000 (no TLS in lite mode — no Traefik in front).
EOF
PXY_RECONSTRUCT_EOF
chmod +x "./start_lite_services.sh"
CHANGED+=("./start_lite_services.sh")
echo "  -> ./start_full_services.sh"
mkdir -p "$(dirname "./start_full_services.sh")"
if [ -f "./start_full_services.sh" ]; then cp "./start_full_services.sh" "$BACKUP_DIR/.__start_full_services.sh.bak"; fi
cat > "./start_full_services.sh" << 'PXY_RECONSTRUCT_EOF'
#!/usr/bin/env bash
# Starts the full (heavy) ProjectXY stack: Traefik, Postgres, Neo4j, Redis,
# Kafka/Zookeeper, Ollama, backend, frontend.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -f .env.local ]; then
  echo "[start_full_services] .env.local not found."
  if [ -f .env.template ]; then
    cp .env.template .env.local
    echo "[start_full_services] Created .env.local from .env.template — edit it with real secrets, then re-run."
  else
    echo "[start_full_services] No .env.template found either. Create .env.local first."
  fi
  exit 1
fi

echo "[start_full_services] Starting full profile (docker-compose.yml)..."
docker compose --env-file .env.local -f docker-compose.yml up -d

cat <<'EOF'

[start_full_services] Stack starting. Once containers report healthy
(check with: docker compose -f docker-compose.yml ps), run:

  docker compose -f docker-compose.yml exec backend alembic upgrade head
  docker compose -f docker-compose.yml exec backend python scripts/seed.py
  docker compose -f docker-compose.yml exec backend python scripts/seed_admin.py

Then open https://localhost (self-signed cert — your browser will warn once).
EOF
PXY_RECONSTRUCT_EOF
chmod +x "./start_full_services.sh"
CHANGED+=("./start_full_services.sh")
echo "  -> ./QUICK_START.sh"
mkdir -p "$(dirname "./QUICK_START.sh")"
if [ -f "./QUICK_START.sh" ]; then cp "./QUICK_START.sh" "$BACKUP_DIR/.__QUICK_START.sh.bak"; fi
cat > "./QUICK_START.sh" << 'PXY_RECONSTRUCT_EOF'
#!/usr/bin/env bash
# One-command setup helper. Always forces the lite profile, regardless of
# host RAM — for first-time setup, demos, and CI. For the full stack, use
# start_full_services.sh or PROJECTXY_COMPOSE_FILE=docker-compose.yml ./start_services.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

echo "[QUICK_START] Setting up ProjectXY (lite profile)..."

if [ ! -f .env.local ]; then
  if [ ! -f .env.template ]; then
    echo "[QUICK_START] Neither .env.local nor .env.template exists. Cannot continue." >&2
    exit 1
  fi
  cp .env.template .env.local
  echo "[QUICK_START] Created .env.local from .env.template."
  echo "[QUICK_START] IMPORTANT: edit .env.local now and replace every REPLACE_ME value"
  echo "[QUICK_START] with a real secret before continuing (Ctrl+C to stop and edit)."
  sleep 5
fi

chmod +x start_lite_services.sh 2>/dev/null || true
./start_lite_services.sh

cat <<'EOF'

[QUICK_START] Done. Next:
  1. Wait for containers to report healthy: docker compose -f docker-compose.lite.yml ps
  2. Run migrations:  docker compose -f docker-compose.lite.yml exec backend alembic upgrade head
  3. Seed data:       docker compose -f docker-compose.lite.yml exec backend python scripts/seed.py
  4. Create admin:    docker compose -f docker-compose.lite.yml exec backend python scripts/seed_admin.py
  5. Open:            http://localhost:3000
EOF
PXY_RECONSTRUCT_EOF
chmod +x "./QUICK_START.sh"
CHANGED+=("./QUICK_START.sh")

echo "== [1c/4] .env.local (only created if missing — never overwrites real secrets) =="
if [ -f "./.env.local" ]; then
  echo "  .env.local already exists — leaving it untouched."
  SKIPPED+=("./.env.local (already exists)")
else
  cp "./.env.template" "./.env.local"
  echo "  Created ./.env.local from ./.env.template — EDIT IT NOW and replace every REPLACE_ME value."
  CHANGED+=("./.env.local (created from template)")
fi

echo ""
echo "== [2/4] Frontend files =="
echo "  -> ./frontend/src/components/devices/DeviceRegistry.tsx"
mkdir -p "$(dirname "./frontend/src/components/devices/DeviceRegistry.tsx")"
if [ -f "./frontend/src/components/devices/DeviceRegistry.tsx" ]; then cp "./frontend/src/components/devices/DeviceRegistry.tsx" "$BACKUP_DIR/.__frontend__src__components__devices__DeviceRegistry.tsx.bak"; fi
cat > "./frontend/src/components/devices/DeviceRegistry.tsx" << 'PXY_RECONSTRUCT_EOF'
'use client';

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { api } from '@/lib/api';
import {
  Monitor, Laptop, Network, Cpu, Shield, Search,
  Filter, AlertTriangle, ChevronRight, X, RefreshCw,
  Globe, Clock, Hash, Layers, Activity, Server,
  Lock, Unlock, ShieldAlert
} from 'lucide-react';

// ─── Types ────────────────────────────────────────────────────────────────────
interface Device {
  id: string;
  hostname: string;
  ip: string;
  mac?: string;
  os?: string;
  type?: string;
  risk_score?: number;
  last_seen?: string;
  ports?: number[];
  services?: string[];
  cves?: string[];
  tags?: string[];
  status?: string;
  department?: string;
}

type RiskLevel = 'all' | 'critical' | 'high' | 'medium' | 'low';

// ─── Helpers ──────────────────────────────────────────────────────────────────
function getRiskLevel(score: number): RiskLevel {
  if (score >= 80) return 'critical';
  if (score >= 50) return 'high';
  if (score >= 25) return 'medium';
  return 'low';
}

function riskStyle(score: number) {
  if (score >= 80) return { text: 'text-red-400', bg: 'bg-red-500', badge: 'bg-red-950/60 text-red-400 border-red-800/50' };
  if (score >= 50) return { text: 'text-amber-400', bg: 'bg-amber-500', badge: 'bg-amber-950/60 text-amber-400 border-amber-800/50' };
  if (score >= 25) return { text: 'text-yellow-400', bg: 'bg-yellow-500', badge: 'bg-yellow-950/60 text-yellow-400 border-yellow-800/50' };
  return { text: 'text-emerald-400', bg: 'bg-emerald-500', badge: 'bg-emerald-950/60 text-emerald-400 border-emerald-800/50' };
}

function TypeIcon({ type }: { type?: string }) {
  const cls = "shrink-0 text-sky-500";
  if (type === 'Server') return <Server size={14} className={cls} />;
  if (type === 'Workstation') return <Laptop size={14} className={cls} />;
  if (type === 'Network') return <Network size={14} className={cls} />;
  if (type === 'IoT') return <Cpu size={14} className={cls} />;
  return <Monitor size={14} className={cls} />;
}

// ─── Device Detail Panel ──────────────────────────────────────────────────────
// FIXED: was `fixed inset-y-0 right-0` — positioned relative to the browser
// viewport regardless of where this component is mounted. Embedding it inside
// a small dashboard panel meant this sidebar (and its backdrop below) covered
// the *entire screen*, including sibling panels, instead of staying inside its
// own container. Changed to `absolute inset-y-0 right-0`, which requires the
// component's outer wrapper (see DeviceRegistry below) to be `position: relative`.
function DeviceDetail({
  device, onClose, onIsolate, onRelease
}: {
  device: Device;
  onClose: () => void;
  onIsolate: (id: string) => Promise<void>;
  onRelease: (id: string) => Promise<void>;
}) {
  const style = riskStyle(device.risk_score ?? 0);
  const isIsolated = device.status === 'isolated' || device.status === 'quarantined';
  const [acting, setActing] = useState(false);

  const handleIsolate = async () => {
    setActing(true);
    try {
      if (isIsolated) await onRelease(device.id);
      else await onIsolate(device.id);
    } finally {
      setActing(false);
    }
  };

  return (
    <div className="absolute inset-y-0 right-0 w-full sm:w-[420px] bg-[#00091A] border-l border-sky-900/40 z-40 flex flex-col shadow-2xl overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-sky-900/30 bg-gradient-to-r from-sky-950/40 to-[#00091A]">
        <div className="flex items-center gap-2">
          <TypeIcon type={device.type} />
          <div>
            <p className="text-sm font-semibold text-sky-200">{device.hostname}</p>
            <p className="text-[10px] font-mono text-sky-700">{device.ip}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isIsolated && (
            <span className="text-[8px] font-black tracking-widest text-red-400 bg-red-950/60 border border-red-800 px-2 py-0.5 rounded animate-pulse">
              ISOLATED
            </span>
          )}
          <button onClick={onClose} className="text-sky-700 hover:text-sky-400 transition-colors p-1">
            <X size={18} />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        {/* Risk Score */}
        <div>
          <p className="text-[10px] font-mono text-sky-700 tracking-widest mb-2 uppercase">Risk Posture</p>
          <div className="flex items-center gap-3">
            <div className="flex-1 h-2 bg-sky-950 rounded-full overflow-hidden">
              <div className={`h-full rounded-full ${style.bg} transition-all duration-700`} style={{ width: `${device.risk_score ?? 0}%` }} />
            </div>
            <span className={`text-2xl font-black tabular-nums ${style.text}`}>{device.risk_score ?? '—'}</span>
          </div>
          <span className={`mt-1.5 inline-block text-[9px] px-2 py-0.5 rounded border font-mono tracking-widest ${style.badge}`}>
            {getRiskLevel(device.risk_score ?? 0).toUpperCase()}
          </span>
        </div>

        {/* Action Buttons */}
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={handleIsolate}
            disabled={acting}
            className={`flex items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-[11px] font-mono font-bold tracking-widest transition-all disabled:opacity-50 ${
              isIsolated
                ? 'border-emerald-800/60 bg-emerald-950/20 text-emerald-400 hover:bg-emerald-950/40'
                : 'border-red-800/60 bg-red-950/20 text-red-400 hover:bg-red-950/40'
            }`}
          >
            {acting ? (
              <RefreshCw size={12} className="animate-spin" />
            ) : isIsolated ? (
              <Unlock size={12} />
            ) : (
              <Lock size={12} />
            )}
            {isIsolated ? 'RELEASE' : 'ISOLATE'}
          </button>
          <button
            className="flex items-center justify-center gap-2 rounded-lg border border-sky-900/40 bg-sky-950/10 px-3 py-2.5 text-[11px] font-mono font-bold tracking-widest text-sky-600 hover:text-sky-400 hover:bg-sky-950/20 transition-all"
            onClick={() => {
              window.dispatchEvent(new CustomEvent('projectxy:toast', {
                detail: { msg: `Port scan queued for ${device.hostname}`, level: 'ok' }
              }));
            }}
          >
            <ShieldAlert size={12} />
            SCAN
          </button>
        </div>

        {/* Details Grid */}
        <div>
          <p className="text-[10px] font-mono text-sky-700 tracking-widest mb-2 uppercase">System Info</p>
          <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
            {[
              { label: 'MAC', value: device.mac ?? '—', icon: <Hash size={10} /> },
              { label: 'OS', value: device.os ?? '—', icon: <Layers size={10} /> },
              { label: 'Type', value: device.type ?? '—', icon: <Monitor size={10} /> },
              { label: 'Dept', value: device.department ?? '—', icon: <Globe size={10} /> },
              { label: 'Status', value: device.status ?? '—', icon: <Activity size={10} /> },
              { label: 'Last Seen', value: device.last_seen ?? '—', icon: <Clock size={10} /> },
            ].map(({ label, value, icon }) => (
              <div key={label} className="rounded-lg bg-sky-950/20 border border-sky-900/20 p-2.5">
                <div className="flex items-center gap-1 text-sky-700 mb-1">{icon}<span className="text-[9px] tracking-widest">{label}</span></div>
                <p className="text-sky-300 truncate">{value}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Open Ports */}
        {(device.ports?.length ?? 0) > 0 && (
          <div>
            <p className="text-[10px] font-mono text-sky-700 tracking-widest mb-2 uppercase">Open Ports ({device.ports!.length})</p>
            <div className="flex flex-wrap gap-1.5">
              {device.ports!.map(p => (
                <span key={p} className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-950/40 border border-sky-900/30 text-sky-400">{p}</span>
              ))}
            </div>
          </div>
        )}

        {/* Services */}
        {(device.services?.length ?? 0) > 0 && (
          <div>
            <p className="text-[10px] font-mono text-sky-700 tracking-widest mb-2 uppercase">Services</p>
            <div className="space-y-1">
              {device.services!.map(s => (
                <div key={s} className="text-[11px] font-mono text-sky-400 flex items-center gap-1.5 py-1 border-b border-sky-950/30">
                  <Activity size={10} className="text-sky-700" />{s}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* CVEs */}
        {(device.cves?.length ?? 0) > 0 && (
          <div>
            <p className="text-[10px] font-mono text-sky-700 tracking-widest mb-2 uppercase flex items-center gap-1.5">
              <AlertTriangle size={10} className="text-red-500" />
              CVEs ({device.cves!.length})
            </p>
            <div className="space-y-1">
              {device.cves!.map(cve => (
                <div key={cve} className="text-[10px] font-mono text-red-400 bg-red-950/20 px-2 py-1 rounded border border-red-900/20">{cve}</div>
              ))}
            </div>
          </div>
        )}

        {/* Last Activity */}
        {device.last_seen && (
          <div>
            <p className="text-[10px] font-mono text-sky-700 tracking-widest mb-2 uppercase">Last Activity</p>
            <p className="text-xs font-mono text-sky-500">{device.last_seen}</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Device Registry ────────────────────────────────────────────────────────
// Extracted from app/devices/page.tsx so it can be mounted two ways:
//   1. As the real /devices route, wrapped in <TeamShell> (full-page chrome).
//   2. Embedded inline in SituationRoom's SELF_MONITORING panel, with no
//      TeamShell (no min-h-screen) and no viewport-fixed overlays — this
//      component owns a `relative` root so the detail sidebar and its
//      backdrop stay confined to whatever container it's placed in.
export function DeviceRegistry() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [riskFilter, setRiskFilter] = useState<RiskLevel>('all');
  const [selected, setSelected] = useState<Device | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [deviceTypes, setDeviceTypes] = useState<string[]>(['all', 'Server', 'Workstation', 'Network', 'IoT', 'Mobile', 'Firewall', 'ICS/OT']);

  const fetchDevices = useCallback(async () => {
    try {
      setRefreshing(true);
      const [deviceData, configTypes] = await Promise.all([
        api.apiRequest<Device[]>('/devices/'),
        fetch('/api/v1/config/device-types')
          .then(r => r.ok ? r.json() : null)
          .catch(() => null),
      ]);
      setDevices(Array.isArray(deviceData) ? deviceData : []);
      if (configTypes && Array.isArray(configTypes) && configTypes.length > 0) {
        const typeValues: string[] = ['all', ...configTypes.map((t: any) => t.value || t.label || t)];
        setDeviceTypes(typeValues);
      }
      setError(null);
    } catch (e) {
      setError((e as Error).message);
      setDevices([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  const isolateDevice = useCallback(async (deviceId: string) => {
    try {
      await api.apiRequest(`/devices/${deviceId}`, {
        method: 'PUT',
        body: JSON.stringify({ status: 'isolated' }),
      });
      setDevices(prev => prev.map(d => d.id === deviceId ? { ...d, status: 'isolated' } : d));
      setSelected(prev => prev?.id === deviceId ? { ...prev, status: 'isolated' } : prev);
      window.dispatchEvent(new CustomEvent('projectxy:toast', {
        detail: { msg: `Device isolated: ${deviceId.slice(0, 8)}`, level: 'warn' }
      }));
    } catch (e) {
      window.dispatchEvent(new CustomEvent('projectxy:toast', {
        detail: { msg: `Isolation failed: ${(e as Error).message}`, level: 'error' }
      }));
    }
  }, []);

  const releaseDevice = useCallback(async (deviceId: string) => {
    try {
      await api.apiRequest(`/devices/${deviceId}`, {
        method: 'PUT',
        body: JSON.stringify({ status: 'online' }),
      });
      setDevices(prev => prev.map(d => d.id === deviceId ? { ...d, status: 'online' } : d));
      setSelected(prev => prev?.id === deviceId ? { ...prev, status: 'online' } : prev);
      window.dispatchEvent(new CustomEvent('projectxy:toast', {
        detail: { msg: `Device released: ${deviceId.slice(0, 8)}`, level: 'ok' }
      }));
    } catch (e) {
      window.dispatchEvent(new CustomEvent('projectxy:toast', {
        detail: { msg: `Release failed: ${(e as Error).message}`, level: 'error' }
      }));
    }
  }, []);

  useEffect(() => { fetchDevices(); }, [fetchDevices]);

  const filtered = useMemo(() => devices.filter(d => {
    const q = search.toLowerCase();
    const matchSearch = !q || d.hostname?.toLowerCase().includes(q) || d.ip?.includes(q) || d.mac?.toLowerCase().includes(q) || d.os?.toLowerCase().includes(q);
    const matchType = typeFilter === 'all' || d.type === typeFilter;
    const matchRisk = riskFilter === 'all' || getRiskLevel(d.risk_score ?? 0) === riskFilter;
    return matchSearch && matchType && matchRisk;
  }), [devices, search, typeFilter, riskFilter]);

  const RISK_LEVELS: RiskLevel[] = ['all', 'critical', 'high', 'medium', 'low'];

  const RISK_BADGE_COLORS: Record<RiskLevel, string> = {
    all: 'bg-sky-950 text-sky-500 border-sky-800',
    critical: 'bg-red-950/60 text-red-400 border-red-800/50',
    high: 'bg-orange-950/60 text-orange-400 border-orange-800/50',
    medium: 'bg-yellow-950/60 text-yellow-400 border-yellow-800/50',
    low: 'bg-emerald-950/60 text-emerald-400 border-emerald-800/50',
  };

  return (
    // FIXED: `relative` root — required so DeviceDetail's `absolute inset-y-0
    // right-0` and the backdrop below stay confined to this component instead
    // of the browser viewport. Also `h-full` so it fills whatever container
    // it's placed in (TeamShell's flex-1 area, or the dashboard's embedded panel).
    <div className="relative h-full overflow-y-auto">
      <div className="p-6 space-y-5">
        {/* Filter Bar */}
        <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
          <div className="relative flex-1 max-w-sm">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-sky-700" />
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search hostname, IP, OS…"
              className="w-full bg-sky-950/20 border border-sky-900/30 rounded-lg pl-9 pr-4 py-2 text-sm font-mono text-sky-300 placeholder-sky-900 focus:outline-none focus:border-sky-600/60 focus:ring-1 focus:ring-sky-600/20 transition-all"
            />
            {search && (
              <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-sky-700 hover:text-sky-400">
                <X size={13} />
              </button>
            )}
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <Filter size={13} className="text-sky-700" />
            {deviceTypes.map(t => (
              <button
                key={t}
                onClick={() => setTypeFilter(t)}
                className={`text-[10px] font-mono px-2.5 py-1 rounded border tracking-widest transition-all ${typeFilter === t ? 'bg-sky-900/60 text-sky-300 border-sky-700' : 'text-sky-700 border-sky-900/30 hover:border-sky-700/50'}`}
              >
                {t.toUpperCase()}
              </button>
            ))}
            <span className="w-px h-4 bg-sky-900/40" />
            {RISK_LEVELS.map(r => (
              <button
                key={r}
                onClick={() => setRiskFilter(r)}
                className={`text-[10px] font-mono px-2.5 py-1 rounded border tracking-widest transition-all ${riskFilter === r ? `${RISK_BADGE_COLORS[r]} opacity-100` : 'text-sky-800 border-sky-900/20 hover:border-sky-700/30'}`}
              >
                {r.toUpperCase()}
              </button>
            ))}
            <button
              onClick={fetchDevices}
              disabled={refreshing}
              className="ml-2 text-sky-700 hover:text-sky-400 transition-colors"
              title="Refresh"
            >
              <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
            </button>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 rounded-lg border border-red-900/50 bg-red-950/20 px-4 py-3">
            <AlertTriangle size={14} className="text-red-400 shrink-0" />
            <p className="text-xs font-mono text-red-400">{error}</p>
          </div>
        )}

        {!loading && (
          <div className="flex items-center gap-4 text-[10px] font-mono text-sky-700">
            <span className="text-sky-500">{filtered.length}</span> of {devices.length} devices
            {(['critical','high','medium','low'] as RiskLevel[]).map(lvl => {
              const cnt = devices.filter(d => getRiskLevel(d.risk_score ?? 0) === lvl).length;
              return cnt > 0 ? (
                <span key={lvl} className={`px-1.5 py-0.5 rounded border text-[9px] ${RISK_BADGE_COLORS[lvl]}`}>
                  {cnt} {lvl}
                </span>
              ) : null;
            })}
          </div>
        )}

        <div className="rounded-xl border border-sky-900/30 bg-[#00091A] overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="border-b border-sky-900/30 text-sky-700 text-[10px] tracking-widest uppercase">
                  <th className="px-4 py-3 text-left">Hostname</th>
                  <th className="px-4 py-3 text-left">IP Address</th>
                  <th className="px-4 py-3 text-left">MAC</th>
                  <th className="px-4 py-3 text-left">OS</th>
                  <th className="px-4 py-3 text-left">Type</th>
                  <th className="px-4 py-3 text-left">Risk</th>
                  <th className="px-4 py-3 text-left">Last Seen</th>
                  <th className="px-4 py-3 text-left"></th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i} className="border-b border-sky-950/30">
                      {Array.from({ length: 8 }).map((__, j) => (
                        <td key={j} className="px-4 py-3">
                          <div className="h-3 bg-sky-950 rounded animate-pulse" style={{ width: `${50 + Math.random() * 40}%` }} />
                        </td>
                      ))}
                    </tr>
                  ))
                ) : filtered.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-16 text-center">
                      <div className="flex flex-col items-center gap-3">
                        <Shield size={32} className="text-sky-900" />
                        <p className="text-sky-800 text-[11px] tracking-widest">
                          {devices.length === 0 ? 'NO DEVICES DISCOVERED' : 'NO DEVICES MATCH FILTER'}
                        </p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  filtered.map(device => {
                    const style = riskStyle(device.risk_score ?? 0);
                    const isSelected = selected?.id === device.id;
                    return (
                      <tr
                        key={device.id}
                        onClick={() => setSelected(isSelected ? null : device)}
                        className={`border-b border-sky-950/30 cursor-pointer transition-colors hover:bg-sky-950/20 ${isSelected ? 'bg-sky-950/30 border-sky-800/30' : ''}`}
                      >
                        <td className="px-4 py-3 text-sky-200 font-semibold">{device.hostname || '—'}</td>
                        <td className="px-4 py-3 text-sky-500 tabular-nums">{device.ip}</td>
                        <td className="px-4 py-3 text-sky-700 tabular-nums">{device.mac || '—'}</td>
                        <td className="px-4 py-3 text-sky-500">{device.os || '—'}</td>
                        <td className="px-4 py-3">
                          <span className="flex items-center gap-1.5 text-sky-400">
                            <TypeIcon type={device.type} />
                            {device.type || '—'}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <div className="w-12 h-1.5 bg-sky-950 rounded-full overflow-hidden">
                              <div className={`h-full rounded-full ${style.bg}`} style={{ width: `${device.risk_score ?? 0}%` }} />
                            </div>
                            <span className={`font-black tabular-nums ${style.text}`}>{device.risk_score ?? '—'}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-sky-700">{device.last_seen || '—'}</td>
                        <td className="px-4 py-3">
                          <ChevronRight size={14} className={`transition-transform ${isSelected ? 'text-sky-400 rotate-90' : 'text-sky-800'}`} />
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Detail Sidebar */}
      {selected && (
        <>
          {/* FIXED: was `fixed inset-0` — blacked out the entire browser
              window (including sibling dashboard panels) when embedded.
              `absolute inset-0` confines it to this component's `relative`
              root instead. */}
          <div className="absolute inset-0 bg-black/40 z-30" onClick={() => setSelected(null)} />
          <DeviceDetail
            device={selected}
            onClose={() => setSelected(null)}
            onIsolate={isolateDevice}
            onRelease={releaseDevice}
          />
        </>
      )}
    </div>
  );
}

export default DeviceRegistry;
PXY_RECONSTRUCT_EOF
CHANGED+=("./frontend/src/components/devices/DeviceRegistry.tsx")
echo "  -> ./frontend/src/app/devices/page.tsx"
mkdir -p "$(dirname "./frontend/src/app/devices/page.tsx")"
if [ -f "./frontend/src/app/devices/page.tsx" ]; then cp "./frontend/src/app/devices/page.tsx" "$BACKUP_DIR/.__frontend__src__app__devices__page.tsx.bak"; fi
cat > "./frontend/src/app/devices/page.tsx" << 'PXY_RECONSTRUCT_EOF'
'use client';

// The actual device-registry UI lives in DeviceRegistry (extracted so it can
// also be embedded, container-relative, inside SituationRoom's
// SELF_MONITORING panel without dragging TeamShell's `min-h-screen` and the
// viewport-fixed detail sidebar/backdrop along with it — see
// components/devices/DeviceRegistry.tsx for details on what changed and why).
import TeamShell from '@/components/Layout/TeamShell';
import { DeviceRegistry } from '@/components/devices/DeviceRegistry';

export default function DevicesPage() {
  return (
    <TeamShell
      team="blue"
      title="ASSET REGISTRY & DEVICE INVENTORY"
      subtitle="Network-wide device discovery — hostname, IP, OS, risk posture, service map"
    >
      <DeviceRegistry />
    </TeamShell>
  );
}
PXY_RECONSTRUCT_EOF
CHANGED+=("./frontend/src/app/devices/page.tsx")
echo "  -> ./frontend/src/modules/dashboard/SituationRoom.tsx"
mkdir -p "$(dirname "./frontend/src/modules/dashboard/SituationRoom.tsx")"
if [ -f "./frontend/src/modules/dashboard/SituationRoom.tsx" ]; then cp "./frontend/src/modules/dashboard/SituationRoom.tsx" "$BACKUP_DIR/.__frontend__src__modules__dashboard__SituationRoom.tsx.bak"; fi
cat > "./frontend/src/modules/dashboard/SituationRoom.tsx" << 'PXY_RECONSTRUCT_EOF'
'use client';

import React, {useState, useEffect, useRef, useCallback} from 'react';
import {useRouter} from 'next/navigation';
import {motion, AnimatePresence} from 'framer-motion';
import {api, buildAuthenticatedWsUrl} from '@/lib/api';
import {socketClient} from '@/lib/socket';
import {
    Shield, Activity, Cpu, Radar, Terminal, ChevronDown, AlertTriangle,
    BrainCircuit, Zap, Eye, Network, Lock, Globe, TrendingUp,
    CheckCircle2, XCircle, Clock, Radio, Target, Crosshair, Command as CommandIcon
} from 'lucide-react';
import {GodsEyeGraph} from '@/components/vanguard/GodsEyeGraph';
import {ActionTerminal} from './ActionTerminal';
import {GlobalOpsMap} from './GlobalOpsMap';
import {CommandCenter} from '@/components/CommandCenter';
import {GlassDossier, type EntityData} from '@/components/CommandCenter/GlassDossier';
import {clsx} from 'clsx';
import {DeviceRegistry} from '@/components/devices/DeviceRegistry';

// ─── Types ────────────────────────────────────────────────────────────────────

interface ThreatEvent {
    id: string;
    ts: string;
    text: string;
    confidence: number;
    severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';
    technique?: string;
    src_ip?: string;
}

interface LiveMetric {
    label: string;
    value: string | number;
    delta?: string;
    positive?: boolean;
    color: string;
    icon: React.ReactNode;
}

interface ActionStatus {
    label: string;
    state: 'pending' | 'success' | 'error';
    detail?: string;
}

// ─── Threat Severity Config ───────────────────────────────────────────────────

const SEV_CFG = {
    CRITICAL: {
        dot: 'bg-rose-500',
        text: 'text-rose-400',
        badge: 'bg-rose-950/50 border-rose-700 text-rose-400',
        glow: 'shadow-[0_0_8px_rgba(244,63,94,0.5)]'
    },
    HIGH: {
        dot: 'bg-orange-500',
        text: 'text-orange-400',
        badge: 'bg-orange-950/40 border-orange-700 text-orange-400',
        glow: ''
    },
    MEDIUM: {
        dot: 'bg-amber-500',
        text: 'text-amber-400',
        badge: 'bg-amber-950/30 border-amber-700 text-amber-400',
        glow: ''
    },
    LOW: {
        dot: 'bg-emerald-500',
        text: 'text-emerald-400',
        badge: 'bg-emerald-950/30 border-emerald-700 text-emerald-400',
        glow: ''
    },
    INFO: {
        dot: 'bg-slate-500',
        text: 'text-slate-400',
        badge: 'bg-slate-900 border-slate-700 text-slate-400',
        glow: ''
    },
};

// ─── Live ROE status bar ──────────────────────────────────────────────────────

const ROE_CFG = {
    PASSIVE: {
        color: 'text-slate-400',
        bg: 'bg-slate-800',
        border: 'border-slate-600',
        desc: 'Monitor only — no autonomous response',
        glow: ''
    },
    DEFENSIVE: {
        color: 'text-amber-400',
        bg: 'bg-amber-900/60',
        border: 'border-amber-600',
        desc: 'Isolate & contain — approval required for offensive action',
        glow: 'shadow-[0_0_12px_rgba(245,158,11,0.3)]'
    },
    AGGRESSIVE: {
        color: 'text-rose-400',
        bg: 'bg-rose-900/60',
        border: 'border-rose-600',
        desc: 'Full autonomous response — active counter-measures enabled',
        glow: 'shadow-[0_0_15px_rgba(244,63,94,0.4)]'
    },
};

// ─── Panel entrance animation presets ──────────────────────────────────────────
// Kept subtle and fast so the dashboard still reads as "live ops," not a
// marketing site — this is the only real "look" lever I changed without
// seeing the rest of the app's pages. Tell me if you want a bigger visual
// departure (new palette, new layout) rather than this polish pass.

const panelVariants = {
    hidden: {opacity: 0, y: 12},
    visible: (delay: number) => ({
        opacity: 1,
        y: 0,
        transition: {duration: 0.35, delay, ease: 'easeOut'},
    }),
};

// ─── Component ────────────────────────────────────────────────────────────────

const SituationRoom: React.FC = () => {
    // --- Clickable Popup Terminal Modal Feature States ---
    const [terminalOpen, setTerminalOpen] = useState(false);
    const [logs, setLogs] = useState<string[]>(["[SYSTEM]: Initializing Interactive Terminal Engine..."]);
    const [terminalInput, setTerminalInput] = useState("");

    // --- Tactical command menu (was declared with click-outside handling but
    // never actually rendered anywhere — no trigger button, no dropdown JSX.
    // Wired up below.) ---
    const [isMenuOpen, setIsMenuOpen] = useState(false);
    const [actionStatus, setActionStatus] = useState<ActionStatus | null>(null);

    const wsRef = useRef<WebSocket | null>(null);
    const scrollRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        if (terminalOpen && !wsRef.current) {
            const wsUrl = buildAuthenticatedWsUrl('/api/v1/ws/terminal');

            const ws = new WebSocket(wsUrl);
            wsRef.current = ws;

            ws.onmessage = (e) => setLogs((prev) => [...prev, e.data]);
            ws.onclose = () => {
                wsRef.current = null;
            };
            ws.onerror = (err) => console.error("WebSocket Pipeline Error Matrix:", err);
        }
        return () => {
            if (!terminalOpen && wsRef.current) {
                wsRef.current.close();
                wsRef.current = null;
            }
        };
    }, [terminalOpen]);

    useEffect(() => {
        scrollRef.current?.scrollIntoView({behavior: "smooth"});
    }, [logs]);

    const dispatchCommand = () => {
        if (!terminalInput.trim() || !wsRef.current) return;
        setLogs((prev) => [...prev, `$ ${terminalInput}`]);
        wsRef.current.send(terminalInput);
        setTerminalInput("");
    };

    const handleTerminalSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        dispatchCommand();
    };

    const router = useRouter();

    const [graphData, setGraphData] = useState<{ nodes: any[], links: any[] }>({nodes: [], links: []});
    const [selectedNode, setSelectedNode] = useState<any>(null);
    const [roeLevel, setRoeLevel] = useState<'PASSIVE' | 'DEFENSIVE' | 'AGGRESSIVE'>('PASSIVE');
    const [viewMode, setViewMode] = useState<'LOCAL' | 'GLOBAL' | 'SELF_MONITORING' | 'PERIMETER_RADAR'>('LOCAL');

    const [globalVaccines, setGlobalVaccines] = useState<{ ip: string; origin: string }[]>([]);

    const [threatFeed, setThreatFeed] = useState<ThreatEvent[]>([]);
    const [criticalCount, setCriticalCount] = useState(0);
    const [blockedCount, setBlockedCount] = useState(0);
    const [alertsToday, setAlertsToday] = useState(0);
    const [systemHealth, setSystemHealth] = useState(98);

    const feedRef = useRef<HTMLDivElement>(null);
    const menuRef = useRef<HTMLDivElement>(null);
    const globeRef = useRef<any>(null);

    const addThreat = useCallback((event: Omit<ThreatEvent, 'id' | 'ts'>) => {
        const entry: ThreatEvent = {
            ...event,
            id: `${Date.now()}-${Math.random()}`,
            ts: new Date().toLocaleTimeString(),
        };
        setThreatFeed(prev => [entry, ...prev].slice(0, 60));
    }, []);

    const fetchStats = useCallback(async () => {
        try {
            const stats = await api.getStats();
            setAlertsToday(stats.alerts_today || 0);
            setBlockedCount(stats.blocked_threats || 0);
            setCriticalCount(stats.critical_alerts || 0);
            setSystemHealth(stats.system_health || 98);
        } catch (err) {
            console.error('Failed to fetch stats', err);
        }
    }, []);

    useEffect(() => {
        const loadIntel = async () => {
            try {
                const gData = await api.getGraph();
                setGraphData(gData);

                fetchStats();

                const tacticalFeed = await api.getTacticalFeed();
                const formattedFeed = tacticalFeed.map((item: any) => ({
                    id: item.id || `${Date.now()}-${Math.random()}`,
                    ts: new Date(item.timestamp).toLocaleTimeString(),
                    text: item.message,
                    confidence: item.confidence,
                    severity: item.level,
                    technique: item.technique,
                    src_ip: item.src_ip,
                }));
                setThreatFeed(formattedFeed);

            } catch (err: any) {
                if (err?.status === 401 || String(err?.message).toLowerCase().includes('unauthorized')) {
                    router.push('/login');
                } else {
                    console.error('Error fetching initial data:', err);
                }
            }
        };
        loadIntel();
    }, [router, fetchStats]);

    useEffect(() => {
        const interval = setInterval(fetchStats, 5000);
        return () => clearInterval(interval);
    }, [fetchStats]);

    useEffect(() => {
        socketClient.connect();

        socketClient.subscribe('ALERT', (data: any) => addThreat({
            text: data.insight || data.message || 'Unknown alert',
            severity: data.level === 'CRITICAL' ? 'CRITICAL' : 'HIGH',
            confidence: Math.round(data.confidence || 85),
            technique: data.technique,
            src_ip: data.src_ip,
        }));

        socketClient.subscribe('THREAT_INTERCEPT', (data: any) => {
            addThreat({
                text: `AI intercept: ${data.message || 'Lateral movement blocked'}`,
                severity: 'CRITICAL',
                confidence: 95
            });
        });

        socketClient.subscribe('GLOBAL_INOCULATION_EVENT', (data: any) => {
            setGlobalVaccines(prev => [{ip: data.threat_ip, origin: data.origin}, ...prev].slice(0, 3));
            addThreat({
                text: `Hive-Mind vaccine deployed for ${data.threat_ip} (Origin: ${data.origin})`,
                severity: 'INFO',
                confidence: 100
            });
        });

        return () => {
            socketClient.unsubscribe('ALERT', () => {
            });
            socketClient.unsubscribe('THREAT_INTERCEPT', () => {
            });
            socketClient.unsubscribe('GLOBAL_INOCULATION_EVENT', () => {
            });
        };
    }, [addThreat]);

    useEffect(() => {
        const handle = (e: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(e.target as Node)) setIsMenuOpen(false);
        };
        document.addEventListener('mousedown', handle);
        return () => document.removeEventListener('mousedown', handle);
    }, []);

    // FIXED: was a bare `console.log`, so clicking a node's deep-scan action did
    // nothing visible and never touched the backend. api.investigateEntity()
    // already existed in api.ts and was unused.
    const handleDeepScan = useCallback(async (nodeId: string) => {
        setActionStatus({label: 'DEEP SCAN', state: 'pending'});
        addThreat({text: `Deep scan initiated on node ${nodeId}`, severity: 'INFO', confidence: 100});
        try {
            const result = await api.investigateEntity(nodeId);
            setActionStatus({label: 'DEEP SCAN', state: 'success'});
            addThreat({
                text: `Deep scan complete on ${nodeId}: ${result?.summary || 'analysis returned'}`,
                severity: 'INFO',
                confidence: 100,
            });
        } catch (err: any) {
            setActionStatus({label: 'DEEP SCAN', state: 'error', detail: err?.message});
            addThreat({text: `Deep scan on ${nodeId} failed: ${err?.message || 'unknown error'}`, severity: 'HIGH', confidence: 100});
        } finally {
            setTimeout(() => setActionStatus(null), 4000);
        }
    }, [addThreat]);

    // TODO: I don't have ActionTerminal.tsx, so I can't see what command
    // strings/payloads it actually sends. Right now this only writes a local
    // fake log line and never reaches the backend — send me that file and
    // I'll route these through the matching api.ts methods (isolateWarRoomHost,
    // blackholeIp, quarantineNode, etc. all already exist and are unused here).
    const handleExecuteAction = (command: string) => {
        addThreat({text: `Operator override: ${command}`, severity: 'INFO', confidence: 100});
    };

    const roe = ROE_CFG[roeLevel];

    const liveMetrics: LiveMetric[] = [
        {
            label: 'THREATS DETECTED',
            value: alertsToday,
            color: 'text-rose-400',
            delta: '+' + alertsToday,
            positive: false,
            icon: <AlertTriangle size={14} className="text-rose-500"/>
        },
        {
            label: 'THREATS BLOCKED',
            value: blockedCount,
            color: 'text-emerald-400',
            delta: '+' + blockedCount,
            positive: true,
            icon: <Shield size={14} className="text-emerald-500"/>
        },
        {
            label: 'CRITICAL ALERTS',
            value: criticalCount,
            color: 'text-orange-400',
            delta: '',
            positive: false,
            icon: <Zap size={14} className="text-orange-500"/>
        },
        {
            label: 'SYSTEM HEALTH',
            value: `${systemHealth}%`,
            color: systemHealth > 85 ? 'text-emerald-400' : 'text-amber-400',
            delta: '',
            positive: true,
            icon: <Activity size={14} className="text-cyan-500"/>
        },
    ];

    // ─── Cyber command menu ─────────────────────────────────────────────────
    // FIXED: this array existed alongside isMenuOpen/menuRef/the click-outside
    // handler above, but nothing ever rendered a trigger button or the dropdown
    // itself — the six actions below were completely unreachable. Three map
    // directly onto api.ts methods that already existed and were never called
    // from anywhere (generatePQCKeys, predictThreats, scanOmniProbe). The other
    // three don't have a matching backend endpoint yet, so they surface a clear
    // error in the threat feed instead of silently pretending to work.

    const cyberMenuItems = [
        {
            icon: <Shield size={13}/>,
            label: 'GHOST PROTOCOL',
            desc: 'Deploy honeypots & deceptive lattice',
            action: 'ENGAGE GHOST PROTOCOL',
        },
        {
            icon: <Activity size={13}/>,
            label: 'PULSE TRACE',
            desc: 'Kinetic network motion tracking',
            action: 'PULSE_TRACE --subnet ALL',
        },
        {
            icon: <Terminal size={13} className="text-rose-500"/>,
            label: 'THE SPEAR (AEG)',
            desc: 'Autonomous Exploit Generation',
            action: 'SPEAR-AEG --mode AUTO',
        },
        {
            icon: <Cpu size={13} className="text-amber-500"/>,
            label: 'THE FORGE (PQC)',
            desc: 'Generate quantum-resistant keys',
            action: 'FORGE-PQC',
        },
        {
            icon: <Radar size={13} className="text-purple-500"/>,
            label: 'THE ORACLE',
            desc: 'Predictive threat forecasting',
            action: 'ORACLE-PREDICT',
        },
        {
            icon: <Globe size={13} className="text-cyan-500"/>,
            label: 'OMNI-PROBE',
            desc: 'Launch full-spectrum network scan',
            action: 'SCAN --target LOCAL_SUBNET',
        },
    ] as const;

    const runTacticalAction = useCallback(async (item: (typeof cyberMenuItems)[number]) => {
        setIsMenuOpen(false);
        setActionStatus({label: item.label, state: 'pending'});
        addThreat({text: `Dispatch: ${item.action}`, severity: 'INFO', confidence: 100});

        try {
            let resultSummary: string;
            switch (item.label) {
                case 'THE FORGE (PQC)': {
                    const result = await api.generatePQCKeys();
                    resultSummary = result?.key_id || result?.status || 'keys generated';
                    break;
                }
                case 'THE ORACLE': {
                    const result = await api.predictThreats();
                    resultSummary = Array.isArray(result?.predictions)
                        ? `${result.predictions.length} forecasts returned`
                        : 'forecast returned';
                    break;
                }
                case 'OMNI-PROBE': {
                    // TODO: hardcoded target CIDR — wire this to an operator
                    // input or the currently selected subnet instead.
                    const result = await api.scanOmniProbe('0.0.0.0/24');
                    resultSummary = result?.hosts_found != null
                        ? `${result.hosts_found} hosts found`
                        : 'scan queued';
                    break;
                }
                default:
                    // GHOST PROTOCOL / PULSE TRACE / THE SPEAR don't have a
                    // matching backend endpoint in api.ts yet.
                    throw new Error(`No backend endpoint wired for "${item.label}" yet`);
            }
            setActionStatus({label: item.label, state: 'success'});
            addThreat({text: `${item.label} complete: ${resultSummary}`, severity: 'INFO', confidence: 100});
        } catch (err: any) {
            setActionStatus({label: item.label, state: 'error', detail: err?.message});
            addThreat({text: `${item.label} failed: ${err?.message || 'unknown error'}`, severity: 'HIGH', confidence: 100});
        } finally {
            setTimeout(() => setActionStatus(null), 4000);
        }
    }, [addThreat]);

    return (
        <div className="grid grid-cols-12 w-full h-full bg-[#050505] text-slate-300 font-mono overflow-hidden">

            {/* ── LEFT PANEL: Threat Intelligence Feed ── */}
            <motion.div
                custom={0}
                initial="hidden"
                animate="visible"
                variants={panelVariants}
                className="col-span-3 h-full flex flex-col border-r border-slate-800/60"
            >
                <div className="grid grid-cols-2 border-b border-slate-800/60 shrink-0">
                    {liveMetrics.map((m, i) => (
                        <div key={i}
                             className={clsx("flex flex-col items-center py-3 border-r border-b border-slate-800/60 last:border-r-0", i >= 2 && "border-b-0")}>
                            <div className="flex items-center gap-1 mb-0.5">{m.icon}</div>
                            <span className={clsx("text-xl font-bold font-mono", m.color)}>{m.value}</span>
                            <span
                                className="text-[8px] text-slate-700 tracking-wider text-center leading-tight">{m.label}</span>
                        </div>
                    ))}
                </div>

                <div
                    className="flex items-center justify-between px-3 py-2 border-b border-slate-800/60 bg-[#0a0a0a] shrink-0">
                    <div className="flex items-center gap-2">
                        <BrainCircuit size={12} className="text-indigo-400 animate-pulse"/>
                        <span
                            className="text-[9px] font-bold text-indigo-400 tracking-widest">AI THREAT INTELLIGENCE</span>
                    </div>
                    <span className="text-[8px] text-slate-600">{threatFeed.length} events</span>
                </div>

                <div ref={feedRef} className="flex-1 overflow-y-auto custom-scrollbar">
                    <AnimatePresence initial={false}>
                        {threatFeed.map((ev) => {
                            const sev = SEV_CFG[ev.severity];
                            return (
                                <motion.div
                                    key={ev.id}
                                    initial={{opacity: 0, x: -8}}
                                    animate={{opacity: 1, x: 0}}
                                    transition={{duration: 0.2}}
                                    className={clsx(
                                        "px-3 py-2 border-b border-slate-900/80 hover:bg-slate-900/30 transition-colors",
                                        ev.severity === 'CRITICAL' && 'bg-rose-950/10'
                                    )}>
                                    <div className="flex items-center gap-2 mb-1">
                                        <span
                                            className={clsx("w-1.5 h-1.5 rounded-full shrink-0", sev.dot, ev.severity === 'CRITICAL' && 'animate-pulse')}/>
                                        <span
                                            className={clsx("text-[8px] font-bold px-1 py-0.5 rounded border", sev.badge)}>{ev.severity}</span>
                                        {ev.technique && (
                                            <span
                                                className="text-[8px] bg-slate-900 border border-slate-700 text-slate-500 px-1 rounded font-bold">{ev.technique}</span>
                                        )}
                                        <span className="text-[8px] text-slate-700 ml-auto shrink-0">{ev.ts}</span>
                                    </div>
                                    <p className={clsx("text-[10px] leading-relaxed", sev.text)}>{ev.text}</p>
                                    {ev.src_ip && (
                                        <p className="text-[8px] text-slate-700 mt-0.5">SRC: <span
                                            className="text-slate-500 font-mono">{ev.src_ip}</span></p>
                                    )}
                                    {ev.confidence > 0 && (
                                        <div className="flex items-center gap-1 mt-1.5">
                                            <div className="h-0.5 flex-1 bg-slate-900 rounded-full overflow-hidden">
                                                <div
                                                    className={clsx("h-full rounded-full transition-all", ev.confidence > 90 ? 'bg-rose-500' : ev.confidence > 70 ? 'bg-amber-500' : 'bg-emerald-500')}
                                                    style={{width: `${ev.confidence}%`}}/>
                                            </div>
                                            <span className="text-[8px] text-slate-600">{ev.confidence}%</span>
                                        </div>
                                    )}
                                </motion.div>
                            );
                        })}
                    </AnimatePresence>
                    {threatFeed.length === 0 && (
                        <div
                            className="flex flex-col items-center justify-center h-full text-slate-700 opacity-50 gap-2">
                            <BrainCircuit size={24}/>
                            <p className="text-[10px] tracking-widest">Initializing neural engine...</p>
                        </div>
                    )}
                </div>
            </motion.div>

            {/* ── CENTER: Command Center ── */}
            <motion.div
                custom={0.08}
                initial="hidden"
                animate="visible"
                variants={panelVariants}
                className="col-span-6 h-full flex flex-col relative"
            >
                <CommandCenter
                    selectedNode={selectedNode}
                    onNodeSelect={(node) => setSelectedNode(node)}
                    onDeepScan={handleDeepScan}
                >
                    <div className="w-full h-full relative overflow-hidden">

                        {/* Uses the scan-line keyframe already defined in tailwind.config.ts
                            but never applied anywhere — a free bit of "maintain animation." */}
                        <div
                            className="pointer-events-none absolute inset-x-0 h-px bg-primary/50 animate-scan-line z-10"/>

                        {viewMode !== 'SELF_MONITORING' && viewMode !== 'PERIMETER_RADAR' && (
                            viewMode === 'LOCAL' ? (
                                <GodsEyeGraph/>
                            ) : (
                                <GlobalOpsMap
                                    globeRef={globeRef}
                                    graphData={{nodes: [], links: []}}
                                    attackArcs={[]}
                                    onNavigateToDevices={() => router.push('/devices')}
                                />
                            )
                        )}

                        {viewMode !== 'SELF_MONITORING' && viewMode !== 'PERIMETER_RADAR' && (
                            <div className="absolute bottom-3 left-3 flex items-center gap-2 pointer-events-none z-10">
                                <div className="relative w-3 h-3">
                                    <div className="absolute inset-0 rounded-full bg-cyan-500/30 animate-ping"/>
                                    <div className="w-3 h-3 rounded-full bg-cyan-500"/>
                                </div>
                                <span className="text-[9px] text-cyan-600 tracking-widest">SCANNING</span>
                            </div>
                        )}

                        {viewMode !== 'SELF_MONITORING' && viewMode !== 'PERIMETER_RADAR' && (
                            <motion.button
                                whileHover={{scale: 1.04}}
                                whileTap={{scale: 0.96}}
                                onClick={() => router.push('/devices')}
                                className="absolute top-3 right-3 z-20 bg-red-600/20 hover:bg-red-600/40 border border-red-700/50 text-red-500 px-3 py-1.5 rounded text-[10px] font-bold tracking-widest transition-colors flex items-center gap-1.5">
                                ASSET RECOVERY
                            </motion.button>
                        )}

                        {viewMode === 'SELF_MONITORING' && (
                            <div
                                className="absolute inset-0 top-24 w-full h-[calc(100%-96px)] overflow-hidden p-2 rounded-xl border border-zinc-900 bg-zinc-950/40 z-30">
                                <div
                                    className="absolute top-4 left-4 z-40 bg-black/80 backdrop-blur px-2 py-0.5 rounded border border-cyan-500/30 text-[9px] font-bold tracking-widest text-cyan-400 uppercase font-mono">
                                    ● SYSTEM SELF-MONITORING // LIVE INFRASTRUCTURE
                                </div>
                                {/* FIXED: was <AssetRecoveryPage/>, importing the /devices route's
                                    page.tsx directly. That page wraps its content in TeamShell
                                    (min-h-screen) and used fixed-positioned overlays, so embedding
                                    it here blew out of this panel and covered the whole dashboard
                                    when a device row was clicked. DeviceRegistry is the same UI
                                    extracted into a container-relative component instead. */}
                                <DeviceRegistry/>
                            </div>
                        )}

                        {viewMode === 'PERIMETER_RADAR' && (
                            <div
                                className="absolute inset-0 top-24 w-full h-[calc(100%-96px)] overflow-hidden p-2 rounded-xl border border-zinc-900 bg-zinc-950/40 z-30">
                                <div
                                    className="absolute top-4 left-4 z-40 bg-black/80 backdrop-blur px-2 py-0.5 rounded border border-red-500/30 text-[9px] font-bold tracking-widest text-red-500 uppercase font-mono">
                                    ● PERIMETER THREAT RADAR // BATTLEFIELD TOPOLOGY
                                </div>
                                <GodsEyeGraph/>
                            </div>
                        )}

                        <div className="absolute top-16 left-0 right-0 flex border-b border-slate-800/60 shrink-0 px-4">
                            <button onClick={() => setViewMode('SELF_MONITORING')}
                                    className={clsx("flex-1 py-1.5 text-[9px] font-bold tracking-widest transition-colors flex items-center justify-center gap-1.5",
                                        viewMode === 'SELF_MONITORING' ? 'text-cyan-400 bg-cyan-950/20 border-b-2 border-cyan-500' : 'text-slate-600 hover:text-slate-400')}>
                                LOCAL AEGIS VAULT
                            </button>
                            <button onClick={() => setViewMode('PERIMETER_RADAR')}
                                    className={clsx("flex-1 py-1.5 text-[9px] font-bold tracking-widest transition-colors flex items-center justify-center gap-1.5",
                                        viewMode === 'PERIMETER_RADAR' ? 'text-purple-400 bg-purple-950/20 border-b-2 border-purple-500' : 'text-slate-600 hover:text-slate-400')}>
                                GLOBAL OMNI-MAP
                            </button>
                        </div>

                    </div>
                </CommandCenter>
            </motion.div>

            {/* ── RIGHT PANEL: Action Terminal ── */}
            <motion.div
                custom={0.16}
                initial="hidden"
                animate="visible"
                variants={panelVariants}
                className="col-span-3 h-full flex flex-col border-l border-slate-800/60"
            >
                <ActionTerminal selectedNode={selectedNode} onExecuteAction={handleExecuteAction}/>
            </motion.div>

            {/* --- Action status toast (feedback for the newly-wired backend calls) --- */}
            <AnimatePresence>
                {actionStatus && (
                    <motion.div
                        initial={{opacity: 0, y: 16}}
                        animate={{opacity: 1, y: 0}}
                        exit={{opacity: 0, y: 16}}
                        className={clsx(
                            "fixed bottom-24 left-1/2 -translate-x-1/2 z-[99998] px-4 py-2 rounded-lg border text-[11px] font-bold tracking-wide flex items-center gap-2",
                            actionStatus.state === 'pending' && 'bg-slate-900/95 border-slate-700 text-slate-300',
                            actionStatus.state === 'success' && 'bg-emerald-950/95 border-emerald-700 text-emerald-400',
                            actionStatus.state === 'error' && 'bg-rose-950/95 border-rose-700 text-rose-400',
                        )}
                    >
                        {actionStatus.state === 'pending' && <span className="animate-pulse">●</span>}
                        {actionStatus.state === 'success' && <CheckCircle2 size={14}/>}
                        {actionStatus.state === 'error' && <XCircle size={14}/>}
                        <span>{actionStatus.label}: {actionStatus.state}{actionStatus.detail ? ` — ${actionStatus.detail}` : ''}</span>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* --- FORCED FIXED PORTAL TERMINAL WINDOW OVERLAY --- */}
            <AnimatePresence>
                {terminalOpen && (
                    <motion.div
                        initial={{opacity: 0}}
                        animate={{opacity: 1}}
                        exit={{opacity: 0}}
                        className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4"
                        style={{zIndex: 999999}}
                    >
                        <motion.div
                            initial={{opacity: 0, scale: 0.96, y: 12}}
                            animate={{opacity: 1, scale: 1, y: 0}}
                            exit={{opacity: 0, scale: 0.96, y: 12}}
                            transition={{duration: 0.18}}
                            className="bg-[#0a0a0c] border border-zinc-800 rounded-xl w-full max-w-xl overflow-hidden shadow-[0_0_60px_rgba(0,0,0,0.95)] p-4 flex flex-col justify-between h-[340px] font-mono text-white"
                        >
                            <div
                                className="flex items-center justify-between border-b border-zinc-800 pb-2 mb-2 flex-shrink-0">
                                <div
                                    className="text-xs text-cyan-400 font-bold tracking-wider uppercase flex items-center gap-2">
                                    <span className="animate-pulse">●</span> Interactive Threat Mitigation Terminal
                                </div>
                                <button
                                    onClick={() => setTerminalOpen(false)}
                                    className="text-zinc-500 hover:text-white border border-zinc-800 hover:border-zinc-700 px-2 py-0.5 rounded text-[10px] transition-colors bg-zinc-900/40"
                                >
                                    Esc to close
                                </button>
                            </div>

                            <div
                                className="flex-1 overflow-y-auto space-y-1 mb-3 text-zinc-300 text-xs p-3 bg-[#020204] rounded border border-zinc-900/80 max-h-[160px] custom-scrollbar">
                                {logs.map((log, i) => (
                                    <pre key={i} className="whitespace-pre-wrap text-left leading-relaxed">{log}</pre>
                                ))}
                                <div ref={scrollRef}/>
                            </div>

                            <form onSubmit={handleTerminalSubmit}
                                  className="flex flex-col gap-2 border-t border-zinc-900 pt-3 flex-shrink-0">
                                <div
                                    className="flex items-center bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-1.5">
                                    <span className="text-cyan-500 font-bold text-xs mr-2 font-mono">#</span>
                                    <input
                                        type="text"
                                        value={terminalInput}
                                        onChange={(e) => setTerminalInput(e.target.value)}
                                        placeholder="Type a mitigation command here (e.g. 'help', 'lockdown')..."
                                        className="w-full bg-transparent text-white text-xs outline-none focus:ring-0 py-0.5"
                                    />
                                </div>

                                <motion.button
                                    whileHover={{scale: terminalInput.trim() ? 1.01 : 1}}
                                    whileTap={{scale: terminalInput.trim() ? 0.98 : 1}}
                                    type="submit"
                                    disabled={!terminalInput.trim()}
                                    className="w-full bg-cyan-600/20 hover:bg-cyan-600/40 border border-cyan-500/40 text-cyan-400 py-2 rounded-lg text-xs font-bold uppercase tracking-widest transition-colors disabled:opacity-30 disabled:pointer-events-none"
                                >
                                    Execute Command
                                </motion.button>
                            </form>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* --- Tactical command menu trigger + dropdown (previously dead code) --- */}
            <div ref={menuRef} className="fixed bottom-6 right-[168px]" style={{zIndex: 99999}}>
                <AnimatePresence>
                    {isMenuOpen && (
                        <motion.div
                            initial={{opacity: 0, y: 8, scale: 0.98}}
                            animate={{opacity: 1, y: 0, scale: 1}}
                            exit={{opacity: 0, y: 8, scale: 0.98}}
                            transition={{duration: 0.15}}
                            className="absolute bottom-full right-0 mb-2 w-64 bg-[#0a0a0c] border border-zinc-800 rounded-xl overflow-hidden shadow-[0_0_40px_rgba(0,0,0,0.9)]"
                        >
                            {cyberMenuItems.map((item) => (
                                <button
                                    key={item.label}
                                    onClick={() => runTacticalAction(item)}
                                    className="w-full flex items-start gap-2.5 px-3 py-2.5 hover:bg-zinc-900/70 border-b border-zinc-900 last:border-b-0 text-left transition-colors"
                                >
                                    <span className="mt-0.5 text-slate-400">{item.icon}</span>
                                    <span className="flex flex-col">
                                        <span className="text-[10px] font-bold tracking-widest text-slate-200">{item.label}</span>
                                        <span className="text-[9px] text-slate-500">{item.desc}</span>
                                    </span>
                                </button>
                            ))}
                        </motion.div>
                    )}
                </AnimatePresence>

                <motion.button
                    whileHover={{scale: 1.05}}
                    whileTap={{scale: 0.95}}
                    onClick={() => setIsMenuOpen((v) => !v)}
                    className="flex items-center gap-2 bg-gradient-to-r from-purple-950 to-zinc-900 hover:from-purple-900 hover:to-zinc-850 border-2 border-purple-400/80 text-purple-300 font-bold px-5 py-3.5 rounded-xl text-xs tracking-widest shadow-[0_0_30px_rgba(168,85,247,0.35)] uppercase"
                >
                    <CommandIcon size={14}/>
                    COMMAND
                    <ChevronDown size={12} className={clsx('transition-transform', isMenuOpen && 'rotate-180')}/>
                </motion.button>
            </div>

            {/* --- FIXED LAYOUT SYSTEM FLOATING TERMINAL TRIGGER --- */}
            <div
                className="fixed bottom-6 right-6"
                style={{zIndex: 99999, pointerEvents: 'auto'}}
            >
                <motion.button
                    whileHover={{scale: 1.05}}
                    whileTap={{scale: 0.95}}
                    onClick={() => setTerminalOpen(true)}
                    className="flex items-center gap-2 bg-gradient-to-r from-cyan-950 to-zinc-900 hover:from-cyan-900 hover:to-zinc-850 border-2 border-cyan-400/80 text-cyan-400 font-bold px-6 py-3.5 rounded-xl text-xs tracking-widest shadow-[0_0_30px_rgba(34,211,238,0.4)] uppercase"
                >
                    Terminal
                </motion.button>
            </div>

        </div>
    );
};
export default SituationRoom;
PXY_RECONSTRUCT_EOF
CHANGED+=("./frontend/src/modules/dashboard/SituationRoom.tsx")

echo ""
echo "== [3/4] Backend patch: backend/app/main.py =="
echo "  This does two things, and only applies if the exact known-broken text"
echo "  is still present (won't corrupt a file that's since changed):"
echo "    a) Removes a dead, duplicate '/health' route containing ~45 lines of"
echo "       unreachable code left over from a botched refactor (references an"
echo "       undefined 'websocket' name, but never executes since it sits after"
echo "       a return statement — harmless at runtime, just dead weight)."
echo "    b) Fixes CORS: the middleware was reflecting ANY request's Origin"
echo "       header back with Access-Control-Allow-Credentials: true — meaning"
echo "       literally any website could make credentialed requests to your"
echo "       API. BACKEND_CORS_ORIGINS (from .env.local) was parsed but never"
echo "       actually consulted anywhere. Patched so only origins in the"
echo "       allow-list (including BACKEND_CORS_ORIGINS) are ever reflected."

cp "backend/app/main.py" "$BACKUP_DIR/backend__app__main.py.bak"

python3 << 'PXY_PY_PATCH_EOF'
import sys

path = "backend/app/main.py"
with open(path, "r") as f:
    content = f.read()

changed = False

# --- Patch A: CORS origin validation (stop reflecting any origin) ---
# NOTE: these inner literals use double-triple-quotes because this whole
# python-patch block is itself embedded inside a single-triple-quoted string
# one level up (in the script that generated this file) — mixing delimiters
# avoids premature termination.
old_cors = """allowed_origins = [
    \"http://localhost:3000\",
    \"http://localhost:3001\",
    \"http://127.0.0.1:3000\",
    \"http://127.0.0.1:3001\",
    \"https://localhost\",
    \"https://localhost:443\",
]


app.add_middleware(SecurityHeadersMiddleware)


# ── SECURITY MIDDLEWARE: SOVEREIGN DEFENSE MATRIX ───────────────────────────
@app.middleware(\"http\")
async def sovereign_defense_middleware(request: Request, call_next):
    # Determine the origin making the request
    origin = request.headers.get(\"origin\", \"http://localhost:3000\")
    """

new_cors = """allowed_origins = [
    \"http://localhost:3000\",
    \"http://localhost:3001\",
    \"http://127.0.0.1:3000\",
    \"http://127.0.0.1:3001\",
    \"https://localhost\",
    \"https://localhost:443\",
]
# FIXED: settings.BACKEND_CORS_ORIGINS (populated from .env.local's
# BACKEND_CORS_ORIGINS) was parsed by pydantic but never consulted anywhere in
# this file. Merged in here so that setting is finally meaningful.
allowed_origins = list(dict.fromkeys(
    allowed_origins + [str(o) for o in settings.BACKEND_CORS_ORIGINS]
))


app.add_middleware(SecurityHeadersMiddleware)


# ── SECURITY MIDDLEWARE: SOVEREIGN DEFENSE MATRIX ───────────────────────────
@app.middleware(\"http\")
async def sovereign_defense_middleware(request: Request, call_next):
    # FIXED: was `origin = request.headers.get(\"origin\", \"http://localhost:3000\")`,
    # then reflected back on every response with Access-Control-Allow-Credentials:
    # true regardless of what it was — meaning literally any origin on the
    # internet could make credentialed requests to this API. Now only an origin
    # actually present in allowed_origins is ever reflected; anything else gets
    # a non-matching Access-Control-Allow-Origin, which browsers reject.
    request_origin = request.headers.get(\"origin\", \"\")
    origin = request_origin if request_origin in allowed_origins else allowed_origins[0]
    """

if old_cors in content:
    content = content.replace(old_cors, new_cors, 1)
    changed = True
    print("  [OK] CORS origin-validation patch applied.")
else:
    print("  [SKIP] CORS block text didn't match exactly — main.py may have already changed. No edit made.")

# --- Patch B: remove dead duplicate /health block ---
dead_block_start = """@app.get(\"/health\")
async def health():
    return {\"status\": \"active\", \"timestamp\": datetime.utcnow()}

# ── CORS POLICY — Proxy-First Architecture ──────────────────────────────────
# The frontend Next.js proxy handles all browser → backend calls.
# Direct browser access only happens in local dev (not Docker).

    \"\"\"
    Active browser terminal gateway. Validates the browser session before accepting
    interactive control connections.

    ASGI CONTRACT: websocket.accept() MUST be called before websocket.close().
    Calling close() on an unaccepted WebSocket causes an AssertionError in uvicorn
    that the browser receives as an abrupt drop, triggering the infinite reconnect loop.
    \"\"\"
    token = websocket.query_params.get(\"token\")
    if not token:
        authorization = websocket.headers.get(\"authorization\", \"\")
        if authorization.startswith(\"Bearer \"):
            token = authorization.removeprefix(\"Bearer \").strip()

    if not token:
        token = websocket.cookies.get(\"access_token\")

    if not token:
        # Must accept before close — ASGI protocol requirement.
        await websocket.accept()
        await websocket.send_text(
            json.dumps({\"type\": \"SYSTEM_DISCONNECT\", \"reason\": \"Authentication required\", \"code\": 4003})
        )
        await websocket.close(code=4003)
        return

    payload = verify_token(token)
    if not payload or not payload.get(\"sub\"):
        await websocket.accept()
        await websocket.send_text(
            json.dumps({\"type\": \"SYSTEM_DISCONNECT\", \"reason\": \"Invalid or expired token\", \"code\": 4003})
        )
        await websocket.close(code=4003)
        return

    # Token valid — accept and notify
    await websocket.accept()
    log.info(\"Nexus Command Console connection established.\")
    await websocket.send_text(
        json.dumps({\"type\": \"SYSTEM_CONNECTED\", \"message\": \"[SYSTEM] Connected to ProjectXY Control Core.\"})
    )
    await websocket.close()

"""

replacement = """# Note: the duplicate dead /health route + ~45 lines of unreachable orphaned
# websocket-auth code that used to sit here (leftover from a botched refactor,
# referencing an undefined 'websocket' name — harmless since it followed a
# return statement and never executed) has been removed. The real /health
# route is immediately below.

"""

if dead_block_start in content:
    content = content.replace(dead_block_start, replacement, 1)
    changed = True
    print("  [OK] Dead duplicate /health block removed.")
else:
    print("  [SKIP] Dead-block text didn't match exactly — main.py may have already changed. No edit made.")

# --- Patch C: clean up the now-dangling final CORS comment (points at nothing) ---
old_tail = """# ── CORS POLICY — Proxy-First Architecture ──────────────────────────────────
# The frontend Next.js proxy handles all browser → backend calls.
# Direct browser access only happens in local dev (not Docker)."""

new_tail = """# CORS is implemented via sovereign_defense_middleware, defined near the top
# of this file — it validates the request Origin against allowed_origins
# (which includes settings.BACKEND_CORS_ORIGINS from .env.local) rather than
# reflecting any origin unconditionally."""

if content.rstrip().endswith(old_tail):
    content = content.rstrip()
    content = content[: -len(old_tail)] + new_tail
    changed = True
    print("  [OK] Dangling trailing CORS comment replaced with an accurate pointer.")
else:
    print("  [SKIP] Trailing comment text didn't match exactly — left as-is.")

if changed:
    with open(path, "w") as f:
        f.write(content)
    import py_compile
    try:
        py_compile.compile(path, doraise=True)
        print("  [OK] backend/app/main.py still compiles after patching.")
    except py_compile.PyCompileError as e:
        print(f"  [ERROR] main.py failed to compile after patching: {e}", file=sys.stderr)
        print(f"  Restore from $BACKUP_DIR if needed.", file=sys.stderr)
        sys.exit(1)
else:
    print("  No changes made to main.py (all patches skipped — see above).")
PXY_PY_PATCH_EOF

CHANGED+=("backend/app/main.py (see patch output above)")

echo ""
echo "== [4/4] Summary =="
echo ""
echo "Changed:"
for f in "${CHANGED[@]}"; do echo "  - $f"; done
if [ ${#SKIPPED[@]} -gt 0 ]; then
  echo ""
  echo "Skipped:"
  for f in "${SKIPPED[@]}"; do echo "  - $f"; done
fi
echo ""
echo "Backups saved to: $BACKUP_DIR"
echo ""
echo "Next steps:"
echo "  1. If .env.local was just created, edit it now and replace every REPLACE_ME value."
echo "  2. Verify the frontend compiles:  cd frontend && npx tsc --noEmit && cd .."
echo "  3. Verify the backend still imports cleanly: cd backend && python3 -c 'import app.main' && cd .."
echo "     (this will fail if backend deps aren't installed locally — that's expected"
echo "      if you only ever run it inside Docker; the py_compile check above already"
echo "      confirmed the syntax is valid)"
echo "  4. Start the stack:"
echo "       ./start_services.sh                    # auto-picks lite or full by RAM"
echo "       PROJECTXY_COMPOSE_FILE=docker-compose.yml ./start_services.sh   # force full"
echo "       ./QUICK_START.sh                       # always lite, first-time setup"
echo "  5. Run migrations + seed (README's documented steps):"
echo "       docker compose exec backend alembic upgrade head"
echo "       docker compose exec backend python scripts/seed.py"
echo "       docker compose exec backend python scripts/seed_admin.py"
echo ""
echo "Done."