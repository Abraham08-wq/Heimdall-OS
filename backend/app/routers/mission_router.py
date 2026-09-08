"""
Mission Router — v2 (Power Upgrade)
─────────────────────────────────────
Upgrades:
  • GET /missions            — List all active missions (admin-only)
  • POST /missions/launch    — Launch async intelligence mission
  • GET  /missions/{id}      — Get mission status + progress
  • DELETE /missions/{id}    — Abort / cancel mission
  • POST /missions/{id}/escalate — Escalate mission severity
  • GET /missions/{id}/timeline  — Get reconstructed kill-chain timeline
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

from app.services.unified_chain import unified_cyber_pipeline
from app.schemas.mission import Mission
from app.api.deps import get_current_user

router = APIRouter(prefix="/missions", tags=["Unified Intelligence Chain"])


# ─── Request / Response schemas ───────────────────────────────────────────────

class MissionLaunchRequest(BaseModel):
    target: str
    mode: str = "full"           # full | recon | stealth
    priority: str = "MEDIUM"     # LOW | MEDIUM | HIGH | CRITICAL
    notify_on_complete: bool = True


class EscalateRequest(BaseModel):
    reason: str
    new_priority: str = "CRITICAL"


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/launch", response_model=Mission, status_code=status.HTTP_202_ACCEPTED)
async def launch_unified_mission(
    request: MissionLaunchRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """
    Initializes a new Unified Intelligence Chain mission.
    Returns mission ID immediately; execution proceeds asynchronously.
    Pipeline: Recon → Correlate → Analyze → Execute → Persist → Report
    """
    tenant_id = current_user.get("tenant_id", "default_tenant")

    if not request.target:
        raise HTTPException(status_code=400, detail="Target entity is required.")

    if request.priority == "CRITICAL" and current_user.get("role") not in {"admin", "analyst_tier2"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CRITICAL priority missions require Tier-2 analyst clearance."
        )

    mission = unified_cyber_pipeline.initiate_mission(
        target=request.target,
        tenant_id=tenant_id,
        mode=request.mode,
        priority=request.priority,
        background_tasks=background_tasks,
    )

    return mission


@router.get("", response_model=List[Mission])
async def list_missions(
    current_user: dict = Depends(get_current_user),
    status_filter: Optional[str] = None,
):
    """
    Lists all active and recently completed missions.
    Admins see all tenants; analysts see only their own tenant.
    """
    tenant_id = current_user.get("tenant_id", "default_tenant")
    is_admin = current_user.get("role") == "admin"

    all_missions = list(unified_cyber_pipeline.active_missions.values())

    if not is_admin:
        all_missions = [m for m in all_missions if m.tenant_id == tenant_id]

    if status_filter:
        all_missions = [m for m in all_missions if m.status == status_filter.upper()]

    return sorted(all_missions, key=lambda m: m.created_at, reverse=True)[:50]


@router.get("/{mission_id}", response_model=Mission)
async def get_mission_status(
    mission_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Retrieves the real-time state of an ongoing or completed mission."""
    mission = unified_cyber_pipeline.active_missions.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found.")

    tenant_id = current_user.get("tenant_id", "default_tenant")
    if mission.tenant_id != tenant_id and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Unauthorized to view this mission.")

    return mission


@router.delete("/{mission_id}", status_code=status.HTTP_200_OK)
async def abort_mission(
    mission_id: str,
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Aborts an active mission. Triggers rollback of any reversible actions.
    Requires analyst_tier2 or admin role.
    """
    role = current_user.get("role", "")
    if role not in {"admin", "analyst_tier2"}:
        raise HTTPException(status_code=403, detail="Insufficient clearance to abort mission.")

    mission = unified_cyber_pipeline.active_missions.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found.")

    if mission.status in {"COMPLETED", "ABORTED", "FAILED"}:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot abort mission in status: {mission.status}"
        )

    try:
        await unified_cyber_pipeline.abort_mission(mission_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Abort failed: {str(e)}")

    return {
        "mission_id": mission_id,
        "status": "ABORTED",
        "message": "Mission aborted. Reversible actions rolled back.",
        "operator": current_user.get("email"),
    }


@router.post("/{mission_id}/escalate", status_code=status.HTTP_200_OK)
async def escalate_mission(
    mission_id: str,
    request: EscalateRequest,
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Escalates mission priority. Triggers immediate resource reallocation
    and notifies the on-call analyst via the Hive-Mind alert mesh.
    """
    mission = unified_cyber_pipeline.active_missions.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found.")

    try:
        await unified_cyber_pipeline.escalate_mission(
            mission_id=mission_id,
            new_priority=request.new_priority,
            reason=request.reason,
            operator=current_user.get("email"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Escalation failed: {str(e)}")

    return {
        "mission_id":   mission_id,
        "new_priority": request.new_priority,
        "reason":       request.reason,
        "escalated_by": current_user.get("email"),
    }


@router.get("/{mission_id}/timeline")
async def get_mission_timeline(
    mission_id: str,
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Returns the reconstructed kill-chain event timeline for a mission.
    Pulls events from the Neo4j graph and orders them chronologically.
    """
    from app.services.correlation_engine import correlation_engine

    mission = unified_cyber_pipeline.active_missions.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found.")

    try:
        timeline = await correlation_engine.reconstruct_attack_timeline(mission_id)
        return {
            "mission_id":    mission_id,
            "target":        mission.target,
            "kill_chain":    timeline,
            "phases_active": timeline.get("phases_seen", []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Timeline reconstruction failed: {str(e)}")
