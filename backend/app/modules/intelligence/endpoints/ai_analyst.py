
from typing import Any, Dict
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.api import deps
from app.models import models
from app.services.ai.analyst import analyst_service

router = APIRouter()

class ChatRequest(BaseModel):
    entity_id: str
    question: str

@router.post("/chat", response_model=Dict[str, str])
def chat_with_analyst(
    request: ChatRequest,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Chat with the AI Analyst about a specific entity.
    """
    response = analyst_service.chat_with_analyst(request.entity_id, request.question)
    return {"entity_id": request.entity_id, "response": response}

@router.get("/investigate/{entity_id}")
async def investigate_entity(
    entity_id: str,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Trigger a deep-dive investigation.
    """
    # Mock context gathering
    context = {"name": entity_id, "artifacts": []} 
    report = await analyst_service.investigate_entity(entity_id, context)
    return report
