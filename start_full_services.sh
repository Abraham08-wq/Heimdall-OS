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
