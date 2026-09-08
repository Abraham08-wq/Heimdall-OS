#!/usr/bin/env bash
# ============================================================================
#  ProjectXY AI Firewall Phase — Complete Setup Script
#  Installs all ML/AI/DB dependencies and initialises TimescaleDB
# ============================================================================
set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/backend"
VENV="$BACKEND_DIR/venv"
PYTHON="$VENV/bin/python"
PIP="$VENV/bin/pip"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   ProjectXY AI Firewall — Phase 3 & 4 Setup                ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# --- 1. Activate virtual environment ---
if [ -f "$VENV/bin/activate" ]; then
    source "$VENV/bin/activate"
    echo "[✓] Virtual environment activated: $VENV"
else
    echo "[!] No venv found at $VENV — using system Python"
    PYTHON="python3"
    PIP="pip3"
fi

# --- 2. Install AI Firewall requirements ---
echo ""
echo "[1/5] Installing AI Firewall ML dependencies..."
$PIP install --quiet --upgrade pip
$PIP install -r "$BACKEND_DIR/requirements_ai_firewall.txt" \
    --no-deps --ignore-installed 2>/dev/null || \
$PIP install -r "$BACKEND_DIR/requirements_ai_firewall.txt"

echo "[✓] Python packages installed."

# --- 3. Download spaCy NER model ---
echo ""
echo "[2/5] Downloading spaCy NER model (en_core_web_sm)..."
$PYTHON -m spacy download en_core_web_sm 2>/dev/null || echo "[!] spaCy model download skipped (network or version issue)"
echo "[✓] spaCy NER ready."

# --- 4. Pull TimescaleDB container (if Docker is running) ---
echo ""
echo "[3/5] Pulling TimescaleDB HA Docker image..."
if command -v docker &>/dev/null; then
    docker pull timescale/timescaledb-ha:pg15-latest 2>/dev/null || \
        echo "[!] Docker pull failed — start Docker first if needed."
    echo "[✓] TimescaleDB HA image ready."
else
    echo "[!] Docker not found — skipping image pull."
fi

# --- 5. Run TimescaleDB migration ---
echo ""
echo "[4/5] Running TimescaleDB migration (CBK compliance schema)..."
cd "$BACKEND_DIR"
if $PYTHON timescale_migration.py 2>&1; then
    echo "[✓] TimescaleDB migration complete."
else
    echo "[!] Migration failed — database may not be running. Run manually:"
    echo "    cd $BACKEND_DIR && python timescale_migration.py"
fi

# --- 6. Ingest real threat vectors ---
echo ""
echo "[5/5] Ingesting real HuggingFace threat vectors into pgvector..."
echo "      (This downloads ~100MB of adversarial prompt data on first run)"
if $PYTHON ingest_real_threats.py 2>&1; then
    echo "[✓] Threat vector ingestion complete."
else
    echo "[!] Ingestion failed — run manually: cd $BACKEND_DIR && python ingest_real_threats.py"
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   SETUP COMPLETE — ProjectXY AI Firewall Phase              ║"
echo "║                                                              ║"
echo "║   Next steps:                                               ║"
echo "║   1. python system_health.py   (verify all services)        ║"
echo "║   2. docker-compose up -d      (restart with TimescaleDB)   ║"
echo "║   3. curl http://localhost:8000/api/v1/firewall/stats        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
