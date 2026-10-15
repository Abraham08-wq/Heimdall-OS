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
