from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from app.modules.recon.omni_probe import omni_probe

router = APIRouter()

class ScanRequest(BaseModel):
    target_cidr: str
    scan_type: str = "FULL_SPECTRUM"

@router.post("/scan", tags=["Absolute Reconnaissance - Omni-Probe"])
async def trigger_mass_scan(request: ScanRequest):
    """
    Tier 2: The Omni-Probe.
    Fires off a massive, highly concurrent scanning engine against a CIDR block.
    This creates absolute visibility into the designated network segment.
    """
    try:
        # Pass the subnet to the engine
        scan_results = await omni_probe.launch_mass_scan(
            target_cidr=request.target_cidr,
            scan_type=request.scan_type
        )
        return scan_results
    except Exception as e:
        print(f"[THE SYNAPSE] Omni-Probe engine failure: {e}")
        raise HTTPException(status_code=500, detail="Mass Reconnaissance encountered an error.")
