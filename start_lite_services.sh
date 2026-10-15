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
