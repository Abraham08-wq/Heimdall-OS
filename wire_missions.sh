#!/usr/bin/env bash
# wire_missions.sh — fixes the Red Team Ops "Launch Mission" feature end to end.
#
# What was actually broken (confirmed by reading the real files from your
# project.zip, not guessed):
#   1. mission_router.py called unified_cyber_pipeline.initiate_mission() with
#      mode= and priority= kwargs that the method didn't accept -> TypeError,
#      500, on EVERY /missions/launch call. Nothing ever actually launched.
#   2. mission_router.py checked mission.status in two places, but Mission
#      only has a `phase` field -> AttributeError, 500, on every abort attempt
#      and on any list-with-filter call.
#   3. unified_chain.py had no abort_mission() or escalate_mission() methods
#      at all, though the router calls both -> AttributeError, 500, on both.
#   4. get_mission_timeline() read mission.target, but the field is actually
#      target_entity -> AttributeError, 500, on every timeline request.
#   5. The frontend (redteam/page.tsx) sent objective/techniques that
#      MissionLaunchRequest didn't declare -> silently discarded, not an
#      error, but the operator's actual input never reached the mission.
#   6. The frontend's missions table read m.id / m.target / m.status / m.risk
#      -- none of which exist on the real Mission object (mission_id /
#      target_entity exist; status/risk don't exist at all) -- so those
#      columns always rendered blank or a hardcoded fake value.
#
# This script backs up every file it touches to _mission_fix_backup_<ts>/
# before writing anything. Nothing is ever deleted.
#
# Run from the project root:  bash wire_missions.sh

set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d backend/app ] || [ ! -d frontend/src ]; then
  echo "ERROR: run this from the ProjectXY project root (needs backend/app/ and frontend/src/)."
  exit 1
fi

BACKUP="_mission_fix_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP"
echo "Backups going to: $BACKUP/"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

backup_and_copy() {
  local dest="$1"
  local src="$2"
  if [ -f "$dest" ]; then
    mkdir -p "$BACKUP/$(dirname "$dest")"
    cp "$dest" "$BACKUP/$dest"
    echo "  backed up  $dest"
  fi
  cp "$src" "$dest"
  echo "  wrote      $dest"
}

echo "=== Installing fixed backend files ==="
backup_and_copy "backend/app/schemas/mission.py"          "$SCRIPT_DIR/mission.py"
backup_and_copy "backend/app/services/unified_chain.py"   "$SCRIPT_DIR/unified_chain.py"
backup_and_copy "backend/app/routers/mission_router.py"   "$SCRIPT_DIR/mission_router.py"

echo ""
echo "=== Installing fixed frontend file ==="
backup_and_copy "frontend/src/app/redteam/page.tsx"       "$SCRIPT_DIR/redteam_page.tsx"

echo ""
echo "=== Verifying Python syntax ==="
if command -v python3 >/dev/null 2>&1; then
  python3 -m py_compile \
    backend/app/schemas/mission.py \
    backend/app/services/unified_chain.py \
    backend/app/routers/mission_router.py \
  && echo "  OK: all three backend files compile cleanly"
fi

echo ""
echo "=== Rebuilding and restarting backend + frontend ==="
docker compose --env-file .env.local build backend frontend
docker compose --env-file .env.local up -d backend frontend

echo ""
echo "Done. Test it:"
echo "  1. Open https://localhost/redteam"
echo "  2. Enter a target you're authorized to test (e.g. 127.0.0.1 or your own subnet)"
echo "  3. Click LAUNCH MISSION"
echo "  4. It should show a real mission ID (not 'ID pending') and appear in the table"
echo "     with a real ID and target -- not blank."
echo ""
echo "If it still fails, run:  docker compose logs backend --tail 80"
echo "and paste that plus whatever the browser console / network tab shows."
