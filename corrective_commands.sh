#!/bin/bash
# ProjectXY Corrective Scripts

echo "[*] Fixing PostgreSQL Schema Drift..."
# Modify schema.sql to match multi-tenant models.py
sed -i 's/tenants/organizations/g' backend/database/postgres/init/schema.sql 2>/dev/null
sed -i 's/tenant_id/org_id/g' backend/database/postgres/init/schema.sql 2>/dev/null
sed -i 's/role VARCHAR/permission_level VARCHAR/g' backend/database/postgres/init/schema.sql 2>/dev/null

echo "[*] Fixing Redis Namespace Collision..."
# Prefix god_view_sync with the org_id to restore tenant isolation
sed -i 's/"god_view_sync"/f"god_view_sync_{org_id}"/g' backend/app/services/combat.py 2>/dev/null

echo "[*] Fixing docker-compose.yml Weaknesses..."
# Inject Healthchecks for Neo4j
cat << 'EOF' > patch_neo4j.sh
sed -i '/neo4j-net/i\    healthcheck:\n      test: ["CMD-SHELL", "wget --no-verbose --tries=1 --spider http://localhost:7474 || exit 1"]\n      interval: 10s\n      timeout: 5s\n      retries: 5' docker-compose.yml 2>/dev/null
EOF
sh patch_neo4j.sh && rm patch_neo4j.sh

# Add missing Redis dependency
cat << 'EOF' > patch_backend.sh
sed -i '/postgres:/a\      redis:\n        condition: service_started' docker-compose.yml 2>/dev/null
EOF
sh patch_backend.sh && rm patch_backend.sh

echo "[*] Phase Connectivity Hotfixes Deployed!"
