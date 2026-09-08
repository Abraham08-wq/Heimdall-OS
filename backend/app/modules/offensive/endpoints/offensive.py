import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any

from app.modules.offensive.aeg_engine import aeg_core
from app.api import deps  # Bring in your active authentication profile dependencies
from app.models.models import User  # Use your target database User model representation

logger = logging.getLogger(__name__)
router = APIRouter()


class ExploitRequest(BaseModel):
    target_profile: Dict[str, Any]


@router.post("/aeg/synthesize", tags=["Offensive Security - The Spear"])
async def trigger_aeg(
        request: ExploitRequest,
        current_user: User = Depends(deps.get_current_user)  # Enforce live session token verification
):
    """
    Tier 5: Automated Exploit Generation.
    Feed the engine a target profile (IP, vulnerability, environment specifics)
    and the AI will autonomously synthesize a custom weaponized payload.
    This acts as the core of the active penetration testing suite.
    """
    # 🛡️ Real-Time Authorization Gate: Explicitly check for authorized roles
    user_role = getattr(current_user, "role", "viewer")
    if user_role not in ["operator", "admin"]:
        logger.warning(
            f"Unauthorized AEG attempt on target profile from account: {getattr(current_user, 'email', 'Unknown')} "
            f"with role: {user_role}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient operational security clearance to synthesize custom payloads on this engine."
        )

    try:
        # Pass the verified profile target straight to the active AI core engine worker
        payload = await aeg_core.synthesize_payload(request.target_profile)

        logger.warning(
            f"⚡ [THE SPEAR] AEG Engine successfully generated dynamic payload. "
            f"Triggered by Operator: {current_user.email} at {datetime.now(timezone.utc).isoformat()}"
        )

        return {
            "status": "PAYLOAD_SYNTHESIZED",
            "message": "Custom offensive capability ready for deployment.",
            "weaponized_package": payload,
            "orchestrator_metadata": {
                "operator_id": str(current_user.id),
                "tenant_isolation_boundary": getattr(current_user, "tenant_id", "default")
            }
        }
    except Exception as e:
        logger.error(f"[THE SPEAR] AEG Engine failure: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Automated Exploit Generation encountered an error."
        )
