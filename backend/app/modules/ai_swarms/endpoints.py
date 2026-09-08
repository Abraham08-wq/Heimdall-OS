from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any
from .orchestrator import swarm_director

router = APIRouter()

class SwarmTriggerRequest(BaseModel):
    telemetry_id: str
    data_cluster: Dict[str, Any]

@router.post("/investigate", tags=["AI Analyst Swarms"])
async def trigger_swarm_investigation(request: SwarmTriggerRequest):
    """
    Tier 2: Triggers an autonomous multi-agent investigation.
    Pass a cluster of raw telemetry (e.g., from a honeypot hit).
    The swarm will deploy the OSINT Hunter, Reverse Engineer, and Profiler to determine attribution and mitigation.
    """
    try:
        # In a real deployed environment with heavy loads, this should be dispatched
        # to a Celery worker to prevent blocking the HTTP connection.
        # We await it here directly for architectural demonstration.
        threat_package = await swarm_director.investigate_threat_cluster(request.data_cluster)
        
        return {
            "status": "success",
            "telemetry_id": request.telemetry_id,
            "threat_package": threat_package
        }
    except Exception as e:
        print(f"Swarm failure: {e}")
        raise HTTPException(status_code=500, detail="AI Swarm encountered a critical failure.")
