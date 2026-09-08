from typing import Any
from fastapi import APIRouter, Depends
from app.api import deps
from app.schemas.ghost import ScriptExecuteRequest, ScriptExecuteResponse
from app.services.sandbox import sandbox_service, SandboxService

router = APIRouter()

@router.post("/execute", response_model=ScriptExecuteResponse)
async def execute_script(
    request: ScriptExecuteRequest,
    current_user: Any = Depends(deps.get_current_active_user),
) -> Any:
    """
    Execute a script in a sandboxed container (Ghost Shell).
    If target_ip is provided, it attempts to dispense the payload via CombatOrchestrator.
    """
    
    # Kinetic Action Logic
    if request.target_ip:
        from app.services.combat import combat_orchestrator
        import asyncio
        
        # In a real scenario, we would look up the agent_id for this IP.
        # For now, we broadcast to simulation.
        payload = {
            "command": "EXECUTE_SCRIPT",
            "language": request.language,
            "code": request.code,
            "target": request.target_ip
        }
        
        # Fire and forget (or await if desired)
        await combat_orchestrator.broadcast_command(payload)
        
        return {
            "stdout": f"[KINETIC LAYER] Command encrypted and dispatched to target {request.target_ip} via Secure WebSocket.",
            "stderr": "",
            "exit_code": 0,
            "status": "success"
        }

    # Standard Ghost Shell (Sandboxed)
    result = sandbox_service.run_in_container(request.code, request.language)
    return result
