#!/usr/bin/env bash
# fix_login.sh — fixes the login/ERR_CONNECTION_REFUSED issue once, completely.
#
# Root cause (confirmed from console errors + compiled JS + build logs across this
# whole debugging session):
#   1. NEXT_PUBLIC_API_URL was an absolute URL (https://localhost/api/v1), which is
#      fragile, AND
#   2. frontend/Dockerfile likely isn't threading that build ARG into the actual
#      `next build` step correctly, so Docker's cache can silently reuse an old
#      build even when the value changes (exactly what happened in your last
#      `docker compose build frontend` — note the `CACHED [builder 5/5] RUN npm
#      run build` line that should NOT have been a cache hit).
#
# This script:
#   - backs up every file it touches to _login_fix_backup_<timestamp>/ (nothing deleted)
#   - sets NEXT_PUBLIC_API_URL=/api/v1 and NEXT_PUBLIC_WS_URL left as-is (ws needs
#     to stay absolute since it's a different protocol/scheme, not proxied the same way)
#   - rewrites frontend/Dockerfile with the ARG/ENV lines placed correctly, BEFORE
#     `RUN npm run build`, so Next.js actually inlines the value and Docker's layer
#     cache correctly invalidates whenever it changes
#   - rebuilds with --no-cache (guaranteed fresh, ignores any stale cache either way)
#   - brings the frontend back up
#
# Run from the project root:  bash fix_login.sh

set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f docker-compose.yml ] || [ ! -d frontend ]; then
  echo "ERROR: run this from the ProjectXY project root (the folder with docker-compose.yml and frontend/)."
  exit 1
fi

BACKUP="_login_fix_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP"
echo "Backups going to: $BACKUP/"

# ---------------------------------------------------------------------------
# 1. Fix NEXT_PUBLIC_API_URL in both .env.local and .env (they must match —
#    see the earlier "Docker Compose reads a literal .env for its own ${VAR}
#    substitution" fix from earlier in this session).
# ---------------------------------------------------------------------------
fix_env_file() {
  local f="$1"
  if [ -f "$f" ]; then
    cp "$f" "$BACKUP/$(basename "$f")"
    if grep -q "^NEXT_PUBLIC_API_URL=" "$f"; then
      sed -i.bak 's|^NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=/api/v1|' "$f" && rm -f "$f.bak"
    else
      echo "NEXT_PUBLIC_API_URL=/api/v1" >> "$f"
    fi
    echo "  fixed   $f"
  else
    echo "NEXT_PUBLIC_API_URL=/api/v1" > "$f"
    echo "  created $f"
  fi
}

echo ""
echo "=== Step 1: fixing NEXT_PUBLIC_API_URL to a relative path ==="
fix_env_file ".env.local"
fix_env_file ".env"

# ---------------------------------------------------------------------------
# 2. Patch frontend/Dockerfile: add the missing ARG/ENV lines for
#    NEXT_PUBLIC_API_URL and NEXT_PUBLIC_WS_URL. Confirmed root cause (by
#    reading your actual Dockerfile, not guessing): it declares ARG/ENV for
#    BACKEND_URL only. docker-compose.yml passes NEXT_PUBLIC_API_URL and
#    NEXT_PUBLIC_WS_URL as build args too, but with no matching ARG line in
#    the Dockerfile, Docker silently discards them at the build-stage
#    boundary — they never become environment variables, so `next build`
#    never sees them and webpack inlines `undefined`, which is exactly why
#    the compiled bundle falls back to the hardcoded localhost:8000 default.
#
#    This is an EXACT-TEXT-MATCH patch, not a full-file rewrite: it only
#    applies if your Dockerfile still has precisely this block. If you've
#    changed it since, the patch is skipped with a clear message rather than
#    silently corrupting something else — the original is backed up either way.
# ---------------------------------------------------------------------------
echo ""
echo "=== Step 2: patching frontend/Dockerfile (adding missing ARG/ENV lines) ==="

DOCKERFILE="frontend/Dockerfile"
if [ ! -f "$DOCKERFILE" ]; then
  echo "  ERROR: $DOCKERFILE not found. Skipping this step."
else
  cp "$DOCKERFILE" "$BACKUP/Dockerfile.original"
  echo "  backed up $DOCKERFILE -> $BACKUP/Dockerfile.original"

  OLD_BLOCK='ARG BACKEND_URL=http://backend:8000
ENV BACKEND_URL=${BACKEND_URL}
ENV NEXT_TELEMETRY_DISABLED=1
# Disable ESLint during Docker build to prevent lint-only warnings from failing
ENV NEXT_DISABLE_ESLINT=1'

  NEW_BLOCK='ARG BACKEND_URL=http://backend:8000
ENV BACKEND_URL=${BACKEND_URL}
ENV NEXT_TELEMETRY_DISABLED=1
# Disable ESLint during Docker build to prevent lint-only warnings from failing
ENV NEXT_DISABLE_ESLINT=1

# FIXED (fix_login.sh): NEXT_PUBLIC_* variables are inlined into the compiled
# JavaScript at build time by Next.js — read from process.env while webpack is
# bundling, not at container runtime. docker-compose.yml already passes both
# of these as build args; without the ARG/ENV lines below to receive them, they
# were silently discarded at this build stage, so `next build` always saw
# `undefined` and every API call fell back to a hardcoded localhost:8000 URL.
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_WS_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_PUBLIC_WS_URL=${NEXT_PUBLIC_WS_URL}'

  if grep -q "ARG NEXT_PUBLIC_API_URL" "$DOCKERFILE"; then
    echo "  ok: NEXT_PUBLIC_API_URL ARG already present - patch already applied, skipping"
  elif grep -qzF "$OLD_BLOCK" "$DOCKERFILE"; then
    python3 - "$DOCKERFILE" << 'PYEOF'
import sys
path = sys.argv[1]
old = """ARG BACKEND_URL=http://backend:8000
ENV BACKEND_URL=${BACKEND_URL}
ENV NEXT_TELEMETRY_DISABLED=1
# Disable ESLint during Docker build to prevent lint-only warnings from failing
ENV NEXT_DISABLE_ESLINT=1"""
new = """ARG BACKEND_URL=http://backend:8000
ENV BACKEND_URL=${BACKEND_URL}
ENV NEXT_TELEMETRY_DISABLED=1
# Disable ESLint during Docker build to prevent lint-only warnings from failing
ENV NEXT_DISABLE_ESLINT=1

# FIXED (fix_login.sh): NEXT_PUBLIC_* variables are inlined into the compiled
# JavaScript at build time by Next.js -- read from process.env while webpack is
# bundling, not at container runtime. docker-compose.yml already passes both
# of these as build args; without the ARG/ENV lines below to receive them, they
# were silently discarded at this build stage, so `next build` always saw
# `undefined` and every API call fell back to a hardcoded localhost:8000 URL.
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_WS_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_PUBLIC_WS_URL=${NEXT_PUBLIC_WS_URL}"""
content = open(path, encoding="utf-8").read()
assert content.count(old) == 1, f"expected exactly 1 match, found {content.count(old)}"
content = content.replace(old, new, 1)
open(path, "w", encoding="utf-8").write(content)
print("  PATCHED: added NEXT_PUBLIC_API_URL / NEXT_PUBLIC_WS_URL ARG+ENV lines")
PYEOF
  else
    echo "  SKIP: the expected BACKEND_URL block text wasn't found exactly as expected."
    echo "        Your Dockerfile may have changed since this script was written."
    echo "        Nothing was modified. Original is safe at $BACKUP/Dockerfile.original"
    echo "        Send the current frontend/Dockerfile back for a precise fix."
  fi
fi

# ---------------------------------------------------------------------------
# 2b. Hygiene fix: frontend/.env.local has NEXT_PUBLIC_API_URL= (empty).
#     Confirmed excluded from the Docker build context by frontend/.dockerignore
#     (.env.* is ignored there), so it is NOT the cause of the Docker bug above --
#     but it WOULD silently apply if `npm run dev`/`npm run build` is ever run
#     directly on the host inside frontend/, outside Docker. Fixed for consistency.
# ---------------------------------------------------------------------------
if [ -f "frontend/.env.local" ]; then
  cp "frontend/.env.local" "$BACKUP/frontend.env.local.original"
  if grep -q "^NEXT_PUBLIC_API_URL=" "frontend/.env.local"; then
    sed -i.bak 's|^NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=/api/v1|' "frontend/.env.local" && rm -f "frontend/.env.local.bak"
    echo "  fixed   frontend/.env.local (was empty; harmless for Docker builds, matters for local npm run dev)"
  fi
fi


# ---------------------------------------------------------------------------
# 3. Clean rebuild — --no-cache guarantees this actually re-runs `next build`
#    with the corrected value, regardless of what was cached before.
# ---------------------------------------------------------------------------
echo ""
echo "=== Step 3: rebuilding frontend (--no-cache, this takes a minute) ==="
docker compose --env-file .env.local build --no-cache frontend

echo ""
echo "=== Step 4: restarting frontend ==="
docker compose --env-file .env.local up -d frontend

# ---------------------------------------------------------------------------
# 4. Verify the fix actually landed in the compiled bundle before declaring victory.
# ---------------------------------------------------------------------------
echo ""
echo "=== Step 5: verifying the fix landed in the built image ==="
sleep 3
if docker compose exec frontend sh -c "grep -rl 'localhost:8000' /app/.next 2>/dev/null" | grep -q .; then
  echo "  WARNING: 'localhost:8000' is STILL present in the built bundle."
  echo "           The Dockerfile fix alone did not resolve this — the actual"
  echo "           frontend/Dockerfile may differ from what this script assumed."
  echo "           Compare $BACKUP/Dockerfile.original against what was written"
  echo "           and send both back for a closer look."
else
  echo "  OK: no hardcoded localhost:8000 found in the built frontend bundle."
fi

echo ""
echo "Done. Open https://localhost/login and try logging in."
echo "If it still fails, run:  docker compose logs frontend --tail 50"
echo "and paste that plus whatever the browser console shows now."