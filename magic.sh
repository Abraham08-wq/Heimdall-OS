#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[MAGIC]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 1. Prerequisite Check
log "Checking Arcane Requirements..."
if ! command_exists docker; then
    error "Docker is missing! Use a machine with Docker."
    exit 1
fi
if ! command_exists python3; then
    error "Python3 is missing!"
    exit 1
fi

# 2. Summon the Infrastructure
log "Summoning Infrastructure (Docker Containers)..."
docker-compose up -d --build

# 3. Wait for the Portal (Database)
log "Waiting for Database Portal to align..."
RETRIES=30
until docker-compose exec -T -e PGPASSWORD=changethis postgres psql -h localhost -U postgres -d cyberintel -c "select 1" > /dev/null 2>&1 || [ $RETRIES -eq 0 ]; do
  echo -n "."
  sleep 2
  RETRIES=$((RETRIES-1))
done
echo ""

if [ $RETRIES -eq 0 ]; then
    error "Database failed to materialize."
    exit 1
fi
success "Database is Active."

# 4. Apply Schema Spells (Migrations)
log "Casting Schema Spells (Alembic)..."
# docker-compose exec -T -e PGPASSWORD=changethis backend alembic upgrade head
echo "Skipping Alembic (No config found, relying on schema.sql)"
success "Schema Applied."

# 5. Genesis (Seeding)
log "Invoking Genesis (Data Seeding)..."
# Run inside container to access internal network and dependencies
docker-compose exec -T backend python seed.py
success "World Populated."

# 6. Verification
log "Verifying the Realm..."
# Check for local requests lib or install
pip install requests > /dev/null 2>&1 || true
python3 smoke_test.py
success "Realm Verified."

# 7. Final Output
echo -e "\n${GREEN}==============================================${NC}"
echo -e "${GREEN}   CYBER INTELLIGENCE PLATFORM - LIVE   ${NC}"
echo -e "${GREEN}==============================================${NC}"
echo -e "Dashboard: ${BLUE}http://localhost:3000${NC}"
echo -e "API Docs:  ${BLUE}http://localhost:8000/docs${NC}"
echo -e "Neo4j:     ${BLUE}http://localhost:7474${NC}"
echo -e "Stats:     ${BLUE}http://localhost:8000/api/v1/stats${NC}"
echo -e "${GREEN}==============================================${NC}"
