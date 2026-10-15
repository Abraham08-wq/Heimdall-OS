#!/bin/bash
# ProjectXY Sync & Refresh Commands

echo "[*] Frontend Purge..."
rm -rf frontend/.next
rm -rf frontend/node_modules/.cache
echo "  -> Frontend build artifacts and caches cleared."

echo "[*] Database Hard Reset Migration..."
docker-compose exec -T backend alembic downgrade base
docker-compose exec -T backend alembic upgrade head
echo "  -> Database migrations reset and rebuilt."

echo "[*] Nuclear Command (Wipe all, Rebuild from scratch)..."
docker-compose down -v --rmi all --remove-orphans
docker-compose build --no-cache
docker-compose up -d --force-recreate
echo "  -> Environment completely nuked and restarted from zero with no cache."
