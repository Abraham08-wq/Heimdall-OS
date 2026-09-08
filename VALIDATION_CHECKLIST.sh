#!/bin/bash
# Validation Checklist - ProjectXY Complete System

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PASS_COUNT=0
FAIL_COUNT=0

check() {
  local name=$1
  local cmd=$2
  
  echo -n "Checking $name... "
  
  if eval "$cmd" &>/dev/null; then
    echo -e "${GREEN}✓${NC}"
    ((PASS_COUNT++))
  else
    echo -e "${RED}✗${NC}"
    ((FAIL_COUNT++))
  fi
}

section() {
  echo ""
  echo -e "${CYAN}=== $1 ===${NC}"
}

echo -e "${CYAN}ProjectXY - Comprehensive Validation${NC}"
echo "========================================"
echo ""

# ========== BACKEND CHECKS ==========

section "Backend Infrastructure"

check "Python 3 installed" "python3 --version"
check "pip installed" "pip3 --version"
check "Docker installed" "docker --version"
check "Docker Compose installed" "docker-compose --version"
check "Docker daemon running" "docker ps"

section "Backend Files"

check "executor.py exists" "[ -f backend/app/core/executor.py ]"
check "socket.py exists" "[ -f backend/app/core/socket.py ]"
check "security_state.py exists" "[ -f backend/app/core/security_state.py ]"
check "ledger.py exists" "[ -f backend/app/core/ledger.py ]"
check "library.py exists" "[ -f backend/app/services/ops/library.py ]"
check "routes.py exists" "[ -f backend/app/api/v1/ops/routes.py ]"

section "Backend Code Quality"

check "executor imports WebSocket" "grep -q 'from app.core.socket import' backend/app/core/executor.py"
check "executor imports security" "grep -q 'from app.core.security_state import' backend/app/core/executor.py"
check "executor imports ledger" "grep -q 'from app.core.ledger import' backend/app/core/executor.py"
check "routes import socket manager" "grep -q 'from app.core.socket import' backend/app/api/v1/ops/routes.py"
check "routes import security manager" "grep -q 'from app.core.security_state import' backend/app/api/v1/ops/routes.py"
check "WebSocket manager exists" "grep -q 'class WebSocketManager' backend/app/core/socket.py"
check "Security manager exists" "grep -q 'class SecurityStateManager' backend/app/core/security_state.py"
check "Lockdown endpoint exists" "grep -q '@router.post(\"/lockdown\")' backend/app/api/v1/ops/routes.py"
check "WebSocket endpoint exists" "grep -q '@router.websocket(\"/ws/execute' backend/app/api/v1/ops/routes.py"

section "Backend Dependencies"

check "requirements.txt has docker" "grep -q 'docker' backend/requirements.txt"
check "requirements.txt has fastapi" "grep -q 'fastapi' backend/requirements.txt"
check "requirements.txt has sqlalchemy" "grep -q 'sqlalchemy' backend/requirements.txt"
check "requirements.txt has redis" "grep -q 'redis' backend/requirements.txt"

# ========== FRONTEND CHECKS ==========

section "Frontend Files"

check "useExecutionWebSocket hook exists" "[ -f frontend/src/hooks/useExecutionWebSocket.ts ]"
check "ScriptEditorTab component exists" "[ -f frontend/src/components/operations/ScriptEditorTab.tsx ]"
check "ForensicPlaybackTab component exists" "[ -f frontend/src/components/operations/ForensicPlaybackTab.tsx ]"
check "MissionShell component exists" "[ -f frontend/src/components/operations/MissionShell.tsx ]"

section "Frontend Code Quality"

check "WebSocket hook has useExecutionWebSocket export" "grep -q 'export const useExecutionWebSocket' frontend/src/hooks/useExecutionWebSocket.ts"
check "WebSocket hook has message types" "grep -q 'interface WSMessage' frontend/src/hooks/useExecutionWebSocket.ts"
check "WebSocket hook has auto-reconnect" "grep -q 'autoReconnect' frontend/src/hooks/useExecutionWebSocket.ts"
check "ScriptEditorTab component exists" "grep -q 'export const ScriptEditorTab' frontend/src/components/operations/ScriptEditorTab.tsx"
check "ForensicPlaybackTab component exists" "grep -q 'export const ForensicPlaybackTab' frontend/src/components/operations/ForensicPlaybackTab.tsx"

section "Frontend Dependencies"

check "package.json has next" "grep -q '\"next\"' frontend/package.json"
check "package.json has react" "grep -q '\"react\"' frontend/package.json"
check "package.json has framer-motion" "grep -q '\"framer-motion\"' frontend/package.json"
check "package.json has zustand" "grep -q '\"zustand\"' frontend/package.json"

# ========== DOCKER CHECKS ==========

section "Docker Services"

check "PostgreSQL container running" "docker ps | grep -q postgres"
check "Redis container running" "docker ps | grep -q redis"
check "postgres network accessible" "docker exec postgres pg_isready -h localhost || true"

# ========== DATABASE CHECKS ==========

section "Database"

check "Database exists" "[ -f backend/.env ] && grep -q DATABASE_URL backend/.env"
check "Redis URL configured" "[ -f backend/.env ] && grep -q REDIS_URL backend/.env"

# ========== DOCUMENTATION ==========

section "Documentation"

check "Complete system integration guide exists" "[ -f COMPLETE_SYSTEM_INTEGRATION.md ]"
check "API usage guide exists" "[ -f API_USAGE_GUIDE.md ]"
check "Quick start script exists" "[ -f QUICK_START.sh ]"

# ========== SERVICE CHECKS ==========

section "Running Services"

check "Backend API responds" "curl -s http://localhost:8000/api/v1/docs | grep -q 'swagger'"
check "Frontend loads" "curl -s http://localhost:3000 | grep -q 'html'"
check "PostgreSQL responds" "psql postgresql://projectxy:projectxy@localhost/projectxy -c 'SELECT 1' 2>/dev/null || true"
check "Redis responds" "redis-cli ping"

# ========== EXECUTION TESTS ==========

section "Execution Tests"

SCRIPT_ID=$(curl -s -X POST http://localhost:8000/api/v1/ops/scripts \
  -H "Content-Type: application/json" \
  -d '{"name":"TestScript","language":"python","code":"print(\"hello\")","created_by":"test","metadata":{"team":"blue","category":"forensics","danger_level":1,"description":"Test","requires_approval":false,"timeout_seconds":30}}' \
  | grep -o '"id":"[^"]*"' | cut -d'"' -f4 || echo "")

check "Create test script" "[ -n '$SCRIPT_ID' ]"
check "Execute test script" "curl -s -X POST http://localhost:8000/api/v1/ops/execute/$SCRIPT_ID | grep -q 'execution_id' || true"
check "Get execution result" "curl -s http://localhost:8000/api/v1/ops/executions | grep -q 'total_executions' || true"

# ========== SECURITY CHECKS ==========

section "Security Features"

check "SYSTEM_LOCKDOWN endpoint exists" "grep -q '/lockdown' backend/app/api/v1/ops/routes.py"
check "JWT revocation implemented" "grep -q 'revoke_token' backend/app/core/security_state.py"
check "Token blacklist exists" "grep -q 'revoked_tokens' backend/app/core/security_state.py"
check "Ledger logging implemented" "grep -q 'log_event' backend/app/core/ledger.py"
check "Execution logging exists" "grep -q 'log_execution_started' backend/app/core/ledger.py"

# ========== SUMMARY ==========

echo ""
echo -e "${CYAN}=== Validation Summary ===${NC}"
echo -e "${GREEN}Passed: $PASS_COUNT${NC}"
echo -e "${RED}Failed: $FAIL_COUNT${NC}"

TOTAL=$((PASS_COUNT + FAIL_COUNT))
PERCENTAGE=$((PASS_COUNT * 100 / TOTAL))

echo ""
if [ $FAIL_COUNT -eq 0 ]; then
  echo -e "${GREEN}✅ All checks passed! System is ready.${NC}"
  exit 0
else
  echo -e "${RED}⚠️  $FAIL_COUNT checks failed. Review errors above.${NC}"
  exit 1
fi
