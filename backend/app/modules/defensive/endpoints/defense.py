from typing import Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.api import deps
from app.services.tripwire import tripwire_service

router = APIRouter()

class DecoyRequest(BaseModel):
    type: str = "env" # env, yaml
    path: str = "."

@router.post("/decoys/deploy", response_model=dict)
def deploy_decoy(
    request: DecoyRequest,
    current_user: Any = Depends(deps.get_current_active_user),
) -> Any:
    """
    Deploy a 'Honey-Token' file to the filesystem.
    Reference: MITRE ATT&CK T1003 (Credential Dumping protection)
    """
    try:
        path = tripwire_service.generate_decoy(request.type, request.path)
        return {
            "status": "active",
            "message": f"Decoy deployed at {path}. Monitoring sensors engaged.",
            "tripwire_id": "tw_" + str(hash(path))[:8]
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/alerts")
def get_defense_alerts(
    current_user: Any = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get active tripwire alerts.
    """
    return tripwire_service.alerts
