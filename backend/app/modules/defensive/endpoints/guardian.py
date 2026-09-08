from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.api import deps
from app.services.iot_bridge import iot_service

router = APIRouter()

class IoTCommandRequest(BaseModel):
    device_id: str
    command: str

@router.post("/command", response_model=dict)
def send_iot_command(
    request: IoTCommandRequest,
    current_user: Any = Depends(deps.get_current_active_user),
) -> Any:
    """
    Send a physical control command to an IoT device.
    Examples: LOCK, UNLOCK, ALARM_ON
    """
    success = iot_service.send_command(request.device_id, request.command)
    if not success:
        raise HTTPException(status_code=404, detail="Device not found or unreachable")
    
    return {"status": "success", "message": f"Command {request.command} sent to {request.device_id}"}

@router.get("/devices")
def list_iot_devices(
    current_user: Any = Depends(deps.get_current_active_user),
) -> Any:
    """
    List all connected physical security devices.
    """
    return iot_service.connected_devices
