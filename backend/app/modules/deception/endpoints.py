from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict
from .honey_token_api import honey_token_ops
from .honeypot_generator import honeynet_ops

router = APIRouter()

class TokenRequest(BaseModel):
    campaign_name: str
    target_profile: str

class HoneynetRequest(BaseModel):
    campaign_id: str
    profile_type: str = "FINANCIAL_DB"

@router.post("/tokens/aws", tags=["Deception Engineering"])
async def create_honey_token_aws(request: TokenRequest):
    """
    Tier 1: Generate a tracking AWS credential to drop in the Labyrinth.
    """
    token = honey_token_ops.generate_aws_style_token(
        campaign_name=request.campaign_name,
        target_profile=request.target_profile
    )
    return {"status": "created", "honey_token": token}

@router.post("/honeynets/deploy", tags=["Deception Engineering"])
async def deploy_tailored_honeynet(request: HoneynetRequest, background_tasks: BackgroundTasks):
    """
    Tier 1: Dynamically spin up a high-interaction Docker honeypot designed for a specific threat actor.
    """
    # Run the deployment non-blocking
    background_tasks.add_task(
        honeynet_ops.spawn_tailored_honeypot,
        request.campaign_id,
        request.profile_type
    )
    return {"status": "deploying", "target_campaign": request.campaign_id, "profile": request.profile_type}
