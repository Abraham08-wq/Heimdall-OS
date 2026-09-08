#!/bin/bash
# Start Services & Live Log Stream

set -euo pipefail

echo "🚀 Starting all ProjectXY services..."
TOTAL_MEM_KB="$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)"
DEFAULT_COMPOSE_FILE="docker-compose.lite.yml"
if [[ "${TOTAL_MEM_KB}" -ge 6291456 ]]; then
	DEFAULT_COMPOSE_FILE="docker-compose.yml"
fi
COMPOSE_FILE="${PROJECTXY_COMPOSE_FILE:-${DEFAULT_COMPOSE_FILE}}"
ENV_FILE="${PROJECTXY_ENV_FILE:-.env.local}"
echo "Using compose file: ${COMPOSE_FILE}"
echo "Using env file: ${ENV_FILE}"
if [[ "${COMPOSE_FILE}" == "docker-compose.yml" && "${TOTAL_MEM_KB}" -lt 6291456 ]]; then
	echo "Warning: detected less than 6 GB RAM; full stack may freeze this machine."
fi

if [[ ! -f "${ENV_FILE}" ]]; then
	echo "Environment file ${ENV_FILE} not found. Create it before startup."
	exit 1
fi

if ! docker info >/dev/null 2>&1; then
	echo "Docker daemon is not running or not reachable. Start Docker Desktop / dockerd and retry."
	exit 1
fi

# For the lightweight profile, clear stale service containers before recreate.
if [[ "${COMPOSE_FILE}" == "docker-compose.lite.yml" ]]; then
	docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" rm -fsv >/dev/null 2>&1 || true
fi

# 1. Build and start containers in detached mode
# --build: Forces a build of the images from Dockerfiles
# --force-recreate: Ensures containers are recreated, which is good after a reset
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d --build --force-recreate --wait

echo "✅ Services started."
if [[ "${PROJECTXY_FOLLOW_LOGS:-true}" == "true" ]]; then
	echo "📡 Implementing Live Streaming Log System..."
	echo "Piping the 'AI Thinking Process' and all service logs directly to the terminal."
	echo "Press Ctrl+C to exit the log stream (the services will continue to run in the background)."

	# 2. Follow the logs of all services
	docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" logs -f
fi
