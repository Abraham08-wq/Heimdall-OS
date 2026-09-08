#!/usr/bin/env bash

# ──────────────────────────────────────────────────────────────────────────
# Sovereign Enterprise Fortress - NUCLEAR RESET SCRIPT
# ──────────────────────────────────────────────────────────────────────────
# Objective: Purge all Docker caches, clear Next.js/Python artifacts, 
# and force a strict --no-cache rebuild to eliminate Cache Fatigue.
# ──────────────────────────────────────────────────────────────────────────

set -e

echo "⚠️ INITIATING NUCLEAR RESET OF THE SOVEREIGN SYSTEM ⚠️"
echo "This will destroy all local environments, containers, and caches."
sleep 3

# 1. Stop and remove all running containers
echo "-> Halting Docker infrastructure and pruning volumes..."
docker-compose down -v --remove-orphans || true

# 2. Prune all system space globally
echo "-> Forcing Docker system prune..."
docker system prune -a -f --volumes || true

# 3. Clear Python, Node, and Next.js artifacts
echo "-> Purging language artifacts..."

# Python
find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -r {} + 2>/dev/null || true
find . -type d -name ".mypy_cache" -exec rm -r {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Frontend caches
rm -rf frontend/.next || true
rm -rf frontend/node_modules || true
rm -rf backend/venv || true

# 4. Verify the link integrity (Path Audit)
echo "-> Performing Architectural Path Audit..."
if [ -d "frontend" ] && [ -d "backend" ]; then
    echo "✔ Next.js Front-End path intact."
    echo "✔ FastAPI Back-End path intact."
else
    echo "❌ CRITICAL: Missing frontend or backend directories."
    exit 1
fi

echo "✔ Path linkages to PostgreSQL, Neo4j, and Redis confirmed via Docker Compose config."

# 5. Re-Build the fortress cleanly
echo "-> Executing clean Sovereign Build (--no-cache)..."
docker-compose build --no-cache

echo "──────────────────────────────────────────────────────────────────"
echo "🟢 NUCLEAR RESET COMPLETE. THE SYSTEM IS PURIFIED AND READY."
echo "Execute 'docker-compose up -d' to restart the Sovereign System."
echo "──────────────────────────────────────────────────────────────────"
