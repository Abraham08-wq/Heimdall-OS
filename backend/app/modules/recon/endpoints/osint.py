from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any

from app.modules.recon.osint_engine import osint_global_engine
from app.modules.recon.intel_synthesis import ai_synthesizer
# Assuming we want to secure it, we'd import auth dependencies here
from app.api.deps import get_current_active_user
from app.models.models import User

router = APIRouter()

class GlobalReconRequest(BaseModel):
    target: str

@router.post("/scan", tags=["Global Reconnaissance - OSINT"])
async def trigger_global_osint(
    request: GlobalReconRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Kicks off a legal, passive Internet-wide OSINT footprinting sweep on the given target.
    Pipes the discovered intelligence into an AI engine to derive Red Team / Blue Team operations.
    """
    try:
        # Step 1: Execute massive concurrent OSINT data gathering
        raw_osint_data = await osint_global_engine.execute_full_recon(request.target)
        
        # Step 2: Pass data to AI for synthesis
        executive_report = ai_synthesizer.generate_executive_report(raw_osint_data)
        
        return {
            "status": "success",
            "message": "AI-Powered Advanced OSINT completed.",
            "report": executive_report
        }
    except Exception as e:
        print(f"[RECON ERROR] Failed to execute global osint: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete global reconnaissance run.")
