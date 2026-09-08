#!/bin/bash
set -e

echo "[*] Starting Backend Module Migration..."

APP_DIR="/home/bantu/Documents/ProjectXY/backend/app"

# Create root level module directories
mkdir -p $APP_DIR/modules/offensive/endpoints
mkdir -p $APP_DIR/modules/defensive/endpoints
mkdir -p $APP_DIR/modules/intelligence/endpoints
mkdir -p $APP_DIR/modules/auth/endpoints
mkdir -p $APP_DIR/modules/monitoring/endpoints

# Move api/v1/endpoints/ -> modules/
echo "[*] Moving API endpoints..."
mv $APP_DIR/api/v1/endpoints/offensive.py $APP_DIR/modules/offensive/endpoints/ || true
mv $APP_DIR/api/v1/endpoints/redteam.py $APP_DIR/modules/offensive/endpoints/ || true

mv $APP_DIR/api/v1/endpoints/defense.py $APP_DIR/modules/defensive/endpoints/ || true
mv $APP_DIR/api/v1/endpoints/guardian.py $APP_DIR/modules/defensive/endpoints/ || true

mv $APP_DIR/api/v1/endpoints/analysis.py $APP_DIR/modules/intelligence/endpoints/ || true
mv $APP_DIR/api/v1/endpoints/entities.py $APP_DIR/modules/intelligence/endpoints/ || true
mv $APP_DIR/api/v1/endpoints/ai_analyst.py $APP_DIR/modules/intelligence/endpoints/ || true
mv $APP_DIR/api/v1/endpoints/ai_tactical.py $APP_DIR/modules/intelligence/endpoints/ || true

mv $APP_DIR/api/v1/endpoints/auth.py $APP_DIR/modules/auth/endpoints/ || true

mv $APP_DIR/api/v1/endpoints/stats.py $APP_DIR/modules/monitoring/endpoints/ || true

# Any leftovers go to shared/misc for now
mkdir -p $APP_DIR/modules/misc/endpoints
mv $APP_DIR/api/v1/endpoints/*.py $APP_DIR/modules/misc/endpoints/ 2>/dev/null || true

# Init files for python module resolution
find $APP_DIR/modules -type d -exec touch {}/__init__.py \;

echo "[+] Endpoints moved."
