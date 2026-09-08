from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.response_orchestrator import response_orchestrator
from app.api.deps import get_current_user

router = APIRouter(prefix="/actions", tags=["Manual Actions"])

class TrapRequest(BaseModel):
    ip: str
    reason: str = "Manual trap from Situation Room"

@router.post("/trap")
async def trap_ip(
    request: TrapRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Manually triggers a 'trap' (IP block) action from the command palette.
    """
    tenant_id = current_user.get("tenant_id", "default_tenant")
    
    if not request.ip:
        raise HTTPException(status_code=400, detail="IP address is required.")

    action_result = await response_orchestrator.execute_trap(
        tenant_id=tenant_id,
        ip=request.ip,
        reason=request.reason,
    )
    
    return action_result
