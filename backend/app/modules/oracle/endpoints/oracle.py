from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.modules.oracle.predictive_engine import predictive_oracle
from app.modules.oracle.vulnerability_hunter import neural_hunter

router = APIRouter()

class RegionRequest(BaseModel):
    region_name: str

class RepoRequest(BaseModel):
    repository_url: str

@router.post("/predict_threats", tags=["The Oracle - Predictive AI"])
async def predict_macro_threats(request: RegionRequest, background_tasks: BackgroundTasks):
    """
    Tier 7: Macro-Geopolitical Prediction.
    Forces the Oracle to query current OSINT and predict if a specific nation-state
    is preparing an offensive cyber campaign based on real-world events.
    """
    try:
        prediction = await predictive_oracle.predict_global_threats(request.region_name)
        
        # If the threat is high, autonomously harden the defense tiers
        if prediction.get("threat_probability", 0) > 0.75:
            background_tasks.add_task(
                predictive_oracle.harden_defenses,
                prediction
            )
            
        return {
            "status": "PREDICTION_COMPLETE",
            "findings": prediction,
            "action_taken": "Hardening internal Aegis defenses against predicted TTPs." if prediction.get("threat_probability", 0) > 0.75 else "No immediate action required."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Oracle macro-prediction failed.")

@router.post("/neural_hunt", tags=["The Oracle - Predictive AI"])
async def initiate_neural_code_hunt(request: RepoRequest):
    """
    Tier 7: Neural Source-Code Analysis.
    Points the deeply fine-tuned LLM Swarm at a specific Code Repository
    to find 0-day business logic flaws *before* deployment.
    """
    try:
        findings = await neural_hunter.hunt_for_flaws(request.repository_url)
        return {
            "status": "HUNT_COMPLETE",
            "repository": request.repository_url,
            "vulnerabilities_discovered": findings,
            "auto_remediation": "Pull requests with suggested patches have been generated in the CI/CD pipeline."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Neural Hunt failed.")
