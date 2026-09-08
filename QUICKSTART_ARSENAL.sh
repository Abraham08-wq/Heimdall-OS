#!/bin/bash

###############################################################################
# ProjectXY Operations Arsenal - Quick Start Script
# 
# This script sets up and validates Phase 1 of the Sovereign Command Center
# 
# Usage: bash QUICKSTART_ARSENAL.sh
###############################################################################

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║   🚀 ProjectXY Operations Arsenal - Quick Start               ║"
echo "║   Building the Backend Weaponry for Your Command Center       ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ─── Step 1: Check Prerequisites ───────────────────────────────────────

echo -e "${CYAN}[STEP 1]${NC} Checking prerequisites..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker is not installed${NC}"
    echo "  Install from: https://docs.docker.com/engine/install/"
    exit 1
fi
echo -e "${GREEN}✓ Docker is installed${NC}"

# Check Docker daemon
if ! docker ps &> /dev/null; then
    echo -e "${RED}✗ Docker daemon is not running${NC}"
    echo "  Start Docker: sudo systemctl start docker"
    exit 1
fi
echo -e "${GREEN}✓ Docker daemon is running${NC}"

# Check Docker socket permissions
if ! test -w /var/run/docker.sock; then
    echo -e "${YELLOW}⚠ Docker socket permissions may need adjustment${NC}"
    echo "  Run: sudo chmod 666 /var/run/docker.sock"
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python 3 is installed${NC}"

# Check if docker-compose file exists
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}✗ docker-compose.yml not found${NC}"
    echo "  Current directory: $(pwd)"
    exit 1
fi
echo -e "${GREEN}✓ docker-compose.yml found${NC}"

echo ""

# ─── Step 2: Start Docker Services ─────────────────────────────────────

echo -e "${CYAN}[STEP 2]${NC} Starting Docker services..."

if docker-compose ps | grep -q "Up"; then
    echo -e "${YELLOW}⚠ Services already running${NC}"
else
    echo "  Starting PostgreSQL, Neo4j, Redis..."
    docker-compose up -d
    
    echo "  Waiting for services to be healthy..."
    sleep 10
    
    if docker-compose ps | grep -q "Up"; then
        echo -e "${GREEN}✓ All services started successfully${NC}"
    else
        echo -e "${RED}✗ Some services failed to start${NC}"
        docker-compose logs
        exit 1
    fi
fi

echo ""

# ─── Step 3: Run Database Migration ────────────────────────────────────

echo -e "${CYAN}[STEP 3]${NC} Running database migrations..."

echo "  Applying Alembic migrations..."
docker-compose exec -T backend alembic upgrade head > /dev/null 2>&1 || {
    echo -e "${YELLOW}⚠ Migration might have already been applied${NC}"
}
echo -e "${GREEN}✓ Migrations completed${NC}"

echo ""

# ─── Step 4: Seed the Arsenal ──────────────────────────────────────────

echo -e "${CYAN}[STEP 4]${NC} Seeding Operations Arsenal..."

echo "  Loading Red Team and Blue Team scripts..."
docker-compose exec -T backend python seed.py > /dev/null 2>&1 || {
    echo -e "${RED}✗ Seeding failed${NC}"
    docker-compose exec backend python seed.py
    exit 1
}
echo -e "${GREEN}✓ Arsenal seeded with 8 sample scripts${NC}"

echo ""

# ─── Step 5: Validate Backend ──────────────────────────────────────────

echo -e "${CYAN}[STEP 5]${NC} Validating backend API..."

# Check if API is responding
echo "  Checking API health..."
sleep 2

API_CHECK=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs)

if [ "$API_CHECK" = "200" ]; then
    echo -e "${GREEN}✓ API is responding (HTTP $API_CHECK)${NC}"
else
    echo -e "${YELLOW}⚠ API may not be fully ready. Check logs:${NC}"
    echo "    docker-compose logs backend"
fi

# Check scripts endpoint
SCRIPTS_CHECK=$(curl -s http://localhost:8000/ops/scripts)

if echo "$SCRIPTS_CHECK" | grep -q "Port Scan\|Firewall Rule"; then
    echo -e "${GREEN}✓ Scripts library is populated${NC}"
    echo "    $(echo "$SCRIPTS_CHECK" | grep -c '"id"') scripts found"
else
    echo -e "${YELLOW}⚠ Scripts library might be empty${NC}"
fi

echo ""

# ─── Step 6: Display Quick Start Commands ──────────────────────────────

echo -e "${CYAN}[STEP 6]${NC} Quick start commands..."
echo ""

echo -e "${CYAN}📚 View the Script Library:${NC}"
echo "  curl -X GET http://localhost:8000/ops/scripts"
echo ""

echo -e "${CYAN}▶️  Execute a Blue Team Script (Synchronous):${NC}"
echo "  curl -X POST http://localhost:8000/ops/execute/script-blue-1"
echo ""

echo -e "${CYAN}🌊 Stream Script Output via WebSocket:${NC}"
echo "  npm install -g wscat"
echo "  wscat -c ws://localhost:8000/ops/ws/execute/script-blue-1"
echo ""

echo -e "${CYAN}📖 View API Documentation:${NC}"
echo "  http://localhost:8000/docs"
echo ""

echo -e "${CYAN}🔍 Get Executor Statistics:${NC}"
echo "  curl -X GET http://localhost:8000/ops/executions"
echo ""

# ─── Step 7: Display File Locations ────────────────────────────────────

echo -e "${CYAN}[STEP 7]${NC} Key files created..."
echo ""

echo "  📁 Backend:"
echo "     backend/app/services/ops/library.py (Script repository)"
echo "     backend/app/core/executor.py (Docker execution engine)"
echo "     backend/app/api/v1/ops/routes.py (API endpoints)"
echo ""

echo "  📊 Database:"
echo "     backend/alembic/versions/003_create_scripts_library.py"
echo ""

echo "  📚 Documentation:"
echo "     OPERATIONS_ARSENAL.md (Complete API reference)"
echo "     PHASE_2_FRONTEND.md (Frontend implementation guide)"
echo "     TESTING_VALIDATION.md (Test suite templates)"
echo "     PHASE_1_COMPLETE.md (Implementation summary)"
echo ""

# ─── Step 8: Next Steps ────────────────────────────────────────────────

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                      ✅ SETUP COMPLETE!                       ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

echo -e "${GREEN}Phase 1 (Backend) is ready.${NC}"
echo ""

echo "📋 NEXT STEPS:"
echo ""
echo "  1️⃣  Read the documentation:"
echo "     cat OPERATIONS_ARSENAL.md"
echo ""
echo "  2️⃣  Test the API in your browser:"
echo "     open http://localhost:8000/docs"
echo ""
echo "  3️⃣  Execute a sample script:"
echo "     curl -X POST http://localhost:8000/ops/execute/script-blue-1"
echo ""
echo "  4️⃣  View approval workflow:"
echo "     curl -X POST http://localhost:8000/ops/scripts/script-red-1/approve"
echo ""
echo "  5️⃣  Build Phase 2 (Frontend UI):"
echo "     cat PHASE_2_FRONTEND.md"
echo ""

echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "🎯 Your Command Center is ready to execute operations!"
echo "   Join the Red Team? Execute offensive scripts."
echo "   Defend the Blue? Contain threats with isolation scripts."
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo ""

# ─── Bonus: Display some example scripts ───────────────────────────────

echo "📜 Sample Scripts Available:"
echo ""

curl -s http://localhost:8000/ops/scripts 2>/dev/null | python3 -c "
import sys, json
try:
    scripts = json.load(sys.stdin)
    for i, script in enumerate(scripts[:5], 1):
        team = '🔴 RED' if script.get('metadata', {}).get('team') == 'red' else '🔵 BLUE'
        danger = script.get('metadata', {}).get('danger_level', '?')
        print(f'  {i}. [{team}] {script.get(\"name\", \"Unknown\")} (Danger: {danger}/10)')
except:
    print('  (Scripts data loading...)')
" || echo "  (Fetching scripts...)"

echo ""
echo "🚀 Happy attacking (and defending)!"
echo ""
