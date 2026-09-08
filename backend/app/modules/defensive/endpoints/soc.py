from fastapi import APIRouter, Depends, HTTPException
from typing import Any
from app.api import deps
from app.models.models import User
from app.modules.defensive.services.intelligence import soc_engine
from app.modules.defensive.services.ai_predictor import threat_predictor
from app.modules.defensive_ai.ai_defense import ai_defense_gateway

router = APIRouter()

@router.get("/alerts")
def get_alerts(current_user: User = Depends(deps.get_current_active_user)) -> Any:
    """Retrieve all active real-time alerts from the engine."""
    return {"alerts": soc_engine.get_active_alerts()}

@router.post("/predict/{compromised_node}")
def predict_threat(compromised_node: str, current_user: User = Depends(deps.get_current_active_superuser)) -> Any:
    """Predict breach pathways using the AI engine protected by the Adversarial Gateway."""
    
    # [AI DEFENSE] Strip Prompt Injections and overrides
    sanitation = ai_defense_gateway.sanitize_input(compromised_node)
    if not sanitation.get("is_safe"):
        raise HTTPException(
            status_code=400, 
            detail=f"SECURITY_ALERT: Payload rejected by Adversarial Defense Layer. Reason: {sanitation.get('reason')}"
        )
        
    safe_node = sanitation.get("sanitized_prompt")
    prediction = threat_predictor.predict_breach_path(safe_node)
    
    # [AI DEFENSE] Verify output structural schema
    is_valid = ai_defense_gateway.validate_output_schema(
        prediction, 
        expected_fields=["source_node", "predicted_path", "confidence_score", "explainable_scoring"]
    )
    
    if not is_valid:
        raise HTTPException(status_code=500, detail="AI produced malformed or unsafe structural schema.")
        
    return {"prediction": prediction}

from app.modules.defensive.services.exfiltration import exfiltration_engine

@router.get("/risk-projection")
def get_business_risk(node_name: str = "core_financial_db", severity: str = "HIGH", assets: int = 50, current_user: User = Depends(deps.get_current_active_superuser)) -> Any:
    """Generate executive business risk projections including downtime and data loss dollar values."""
    projection = exfiltration_engine.simulate_impact(
        node_name=node_name, 
        assets_at_risk=assets, 
        threat_severity=severity
    )
    return {"business_risk_projection": projection}
