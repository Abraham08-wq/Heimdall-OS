
from typing import Any, List
from fastapi import APIRouter, Depends
from app.api import deps
from app.models import models
from app.services.connectors import connector_service

router = APIRouter()

@router.get("/osint/search")
async def search_osint(
    query: str,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Search public intelligence sources (OSINT).
    """
    return await connector_service.search_public_intel(query)
