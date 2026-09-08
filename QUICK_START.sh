#!/bin/bash
# Quick Start - ProjectXY Sovereign Command Center

set -e

echo "🚀 ProjectXY - Sovereign Command Center Quick Start"
echo "=================================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Check prerequisites
echo -e "${CYAN}Checking prerequisites...${NC}"
command -v docker &> /dev/null || { echo -e "${RED}❌ Docker not found${NC}"; exit 1; }
command -v awk &> /dev/null || { echo -e "${RED}❌ awk not found${NC}"; exit 1; }
command -v python3 &> /dev/null || { echo -e "${RED}❌ Python 3 not found${NC}"; exit 1; }
command -v node &> /dev/null || { echo -e "${RED}❌ Node.js not found${NC}"; exit 1; }
docker info >/dev/null 2>&1 || { echo -e "${RED}❌ Docker daemon is not running${NC}"; exit 1; }
echo -e "${GREEN}✓ All prerequisites found${NC}"
echo ""

# Setup backend
echo -e "${CYAN}Setting up backend...${NC}"
cd backend

# Create Python virtual environment
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install -q -r requirements.txt

# Setup environment
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cat > .env << 'EOF'
DATABASE_URL=postgresql://projectxy:projectxy@localhost:5432/projectxy
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-secret-key-change-in-production
DOCKER_HOST=unix:///var/run/docker.sock
EXECUTION_TIMEOUT_SECONDS=300
EXECUTION_MEMORY_MB=512
EXECUTION_CPU_QUOTA=1.0
EOF
    echo -e "${YELLOW}⚠️  .env created with defaults. Update SECRET_KEY for production!${NC}"
fi

cd ..
echo -e "${GREEN}✓ Backend setup complete${NC}"
echo ""

# Setup frontend
echo -e "${CYAN}Setting up frontend...${NC}"
cd frontend

# Install npm dependencies
if [ ! -d "node_modules" ]; then
    echo "Installing npm dependencies..."
    npm install -q
fi

cd ..
echo -e "${GREEN}✓ Frontend setup complete${NC}"
echo ""

# Docker services
echo -e "${CYAN}Starting lightweight Docker services...${NC}"
PROJECTXY_COMPOSE_FILE=docker-compose.lite.yml PROJECTXY_FOLLOW_LOGS=false ./start_services.sh
echo -e "${GREEN}✓ Services started${NC}"
echo ""

echo -e "${CYAN}Running database migrations...${NC}"
docker compose -f docker-compose.lite.yml exec -T backend alembic upgrade head 2>/dev/null || echo -e "${YELLOW}Note: Alembic migration skipped or not configured${NC}"
echo -e "${GREEN}✓ Migrations complete${NC}"
echo ""

echo -e "${CYAN}Stack status...${NC}"
docker compose ps
echo ""
echo -e "${GREEN}✅ ProjectXY is starting in lightweight mode.${NC}"
echo -e "${CYAN}Access the system:${NC}"
echo "  🌐 Frontend:  http://localhost:3000"
echo "  🔌 Backend:   http://localhost:8000"
echo "  📚 API Docs:  http://localhost:8000/api/v1/docs"
echo ""
echo -e "${YELLOW}Use ${NC}docker compose logs -f${YELLOW} to follow the stack, or set ${NC}PROJECTXY_COMPOSE_FILE=docker-compose.yml${YELLOW} for the full profile.${NC}"
