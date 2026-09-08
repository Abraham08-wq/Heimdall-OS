
from typing import Any, List
from fastapi import APIRouter, Depends
from app.api import deps
from app.models import models
from app.services.ai.sentinel import sentinel_service
from app.services.ai.nemesis import nemesis_service
from app.services.ai_advisor import ai_advisor
from pydantic import BaseModel
from sqlalchemy.orm import Session

class OracleChatRequest(BaseModel):
    prompt: str
    context: str = "defensive"
    role: str = "analyst"

router = APIRouter()

@router.get("/sentinel/status")
def get_sentinel_status(
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get Blue Team AI status and system health.
    """
    return sentinel_service.analyze_system_health()

@router.post("/sentinel/feedback")
def sentinel_feedback(
    alert_id: str,
    false_positive: bool,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Provide feedback to improve Sentinel accuracy.
    """
    return sentinel_service.learn_feedback(alert_id, false_positive)

@router.post("/nemesis/generate-scenario")
def generate_red_team_scenario(
    difficulty: str = "HARD",
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Generate a new Red Team attack scenario.
    """
    return nemesis_service.generate_scenario(difficulty)

@router.get("/feed/merged")
async def get_tactical_feed(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
) -> List[Any]:
    """
    Get a merged feed of AI insights, threats, and system events.
    """
    from app.models.models import AuditLog
    
    recent_events = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(10).all()
    
    feed = []
    for event in recent_events:
        feed.append({
            "timestamp": event.timestamp.isoformat(),
            "source": f"ACTOR:{event.actor_id}",
            "type": event.resource_type or "SYSTEM",
            "message": f"Action: {event.action} on Resource ID: {event.resource_id}"
        })
        
    return feed

@router.post("/chat")
async def chat_with_oracle(
    request: OracleChatRequest,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Nexus Oracle unified chat interface for both Analyst and Hacker roles.
    """
    reply = await ai_advisor.process_chat_prompt(request.prompt, request.context, request.role)
    return {"reply": reply}
