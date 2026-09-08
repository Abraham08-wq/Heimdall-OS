from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any
from .vaccine_engine import catalyst_ops

router = APIRouter()

class VaccineRequest(BaseModel):
    threat_package: Dict[str, Any]

@router.post("/inoculate", tags=["Sentinel Catalyst"])
async def trigger_global_vaccine(request: VaccineRequest, background_tasks: BackgroundTasks):
    """
    Tier 4: The Ultimate Counter-Measure.
    Triggered by the AI Swarm Profiler once a Zero-Day is successfully dissected.
    Synthesizes a rule and deploys it to all internal endpoints globally via Kafka.
    """
    try:
        # Run deployment non-blocking
        background_tasks.add_task(
            catalyst_ops.deploy_global_vaccine,
            request.threat_package
        )
        
        return {
            "status": "VACCINE_DISPERSAL_INITIATED",
            "message": "Global endpoint inoculation sequence started. Monitoring Omni-Graph for uptake."
        }
        
    except Exception as e:
        print(f"[CATALYST] Vaccination failure: {e}")
        raise HTTPException(status_code=500, detail="Critical inoculation failure.")
