#!/bin/bash
# =============================================================================
# ProjectXY Backend Entrypoint
# Sequence: dependencies ready → schema preflight → uvicorn
# =============================================================================
set -euo pipefail

echo "╔═══════════════════════════════════════════════════╗"
echo "║        ProjectXY Cognitive Shield — Boot          ║"
echo "╚═══════════════════════════════════════════════════╝"

case "${1:-}" in
    migrate)
        shift || true
        python /app/scripts/startup_preflight.py --migrate
        exit 0
        ;;
    seed)
        shift || true
        python /app/scripts/startup_preflight.py --check-only
        python /app/scripts/seed.py
        exit 0
        ;;
esac

wait_for_tcp() {
    local host="$1"
    local port="$2"
    local label="$3"

    echo "[BOOT] Waiting for ${label} at ${host}:${port}..."
    until (echo > /dev/tcp/${host}/${port}) >/dev/null 2>&1; do
        echo "[BOOT] ${label} not ready — retrying in 3s..."
        sleep 3
    done
    echo "[BOOT] ✅ ${label} ready."
}

is_enabled() {
    local value="${1:-}"
    value="$(echo "${value}" | tr '[:upper:]' '[:lower:]')"
    [[ "${value}" == "1" || "${value}" == "true" || "${value}" == "yes" || "${value}" == "on" ]]
}

wait_for_tcp "postgres" "5432" "PostgreSQL"
wait_for_tcp "redis" "6379" "Redis"

if is_enabled "${ENABLE_GRAPH_DB:-true}"; then
    wait_for_tcp "neo4j" "7687" "Neo4j"
else
    echo "[BOOT] Skipping Neo4j wait (ENABLE_GRAPH_DB=false)."
fi

if is_enabled "${ENABLE_KAFKA:-true}"; then
    wait_for_tcp "kafka" "29092" "Kafka"
else
    echo "[BOOT] Skipping Kafka wait (ENABLE_KAFKA=false)."
fi

if is_enabled "${ENABLE_OLLAMA:-false}"; then
    wait_for_tcp "ollama" "11434" "Ollama"
else
    echo "[BOOT] Skipping Ollama wait (ENABLE_OLLAMA=false)."
fi

if [ -f "/app/scripts/startup_preflight.py" ]; then
    if [ "${AUTO_APPLY_MIGRATIONS:-false}" = "true" ]; then
        python /app/scripts/startup_preflight.py --migrate
    else
        python /app/scripts/startup_preflight.py --check-only
    fi
fi

if [ "${RUN_SEEDERS_ON_BOOT:-false}" = "true" ] && [ -f "/app/scripts/seed.py" ]; then
    echo "[BOOT] Running conditional seeders after schema validation..."
    python /app/scripts/seed.py
fi

# ── Start Uvicorn ────────────────────────────────────────────────────────────
echo "[BOOT] 🚀 Launching ProjectXY API on :8000"
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 2 \
    --log-level info \
    --access-log