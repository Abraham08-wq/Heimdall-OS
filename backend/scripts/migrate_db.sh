#!/bin/bash
set -e

echo "[*] Migrating DB layer to Infrastructure and Models..."

APP_DIR="/home/ibraah/myfolder/ProjectXY-main/backend/app"

# Move files
mv $APP_DIR/db/models.py $APP_DIR/models/ || true
mv $APP_DIR/db/session.py $APP_DIR/infrastructure/ || true
mv $APP_DIR/db/graph.py $APP_DIR/infrastructure/ || true
mv $APP_DIR/db/genesis.py $APP_DIR/infrastructure/ || true

# Init files
touch $APP_DIR/models/__init__.py
touch $APP_DIR/infrastructure/__init__.py

# Find all python files and replace imports
find /home/ibraah/myfolder/ProjectXY-main/backend -type f -name "*.py" -exec sed -i 's/from app\.db\.models/from app.models.models/g' {} +
find /home/ibraah/myfolder/ProjectXY-main/backend -type f -name "*.py" -exec sed -i 's/import app\.db\.models/import app.models.models/g' {} +
find /home/ibraah/myfolder/ProjectXY-main/backend -type f -name "*.py" -exec sed -i 's/from app\.db import models/from app.models import models/g' {} +

find /home/ibraah/myfolder/ProjectXY-main/backend -type f -name "*.py" -exec sed -i 's/app\.db\.session/app.infrastructure.session/g' {} +
find /home/ibraah/myfolder/ProjectXY-main/backend -type f -name "*.py" -exec sed -i 's/app\.db\.graph/app.infrastructure.graph/g' {} +
find /home/ibraah/myfolder/ProjectXY-main/backend -type f -name "*.py" -exec sed -i 's/app\.db\.genesis/app.infrastructure.genesis/g' {} +

# Clean up empty db folder if it exists
rm -rf $APP_DIR/db || true

echo "[+] Database separation complete."
