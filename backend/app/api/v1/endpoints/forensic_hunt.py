"""
forensic_hunt.py — ProjectXY Cognitive Shield: Layer 4 API
===========================================================
REST endpoints for the Forensic AI Observability hunt system.

Routes:
  POST /api/v1/forensic/hunt/similarity  — Retroactive similarity search
  GET  /api/v1/forensic/hunt/entity/{entity_id} — Entity interaction timeline
  GET  /api/v1/forensic/hunt/stats       — Semantic logging statistics
  GET  /api/v1/forensic/hunt/patterns    — Attack pattern frequency
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_active_user
from app.modules.firewall.semantic_logger import SemanticLogger, semantic_logger

logger = logging.getLogger("projectxy.api.forensic_hunt")
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SimilarityHuntRequest(BaseModel):
    query_text: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Text to search for semantically similar historical interactions."
    )
    tenant_id: str = Field(..., description="Tenant scope for the hunt.")
    cosine_threshold: float = Field(
        default=0.80,
        ge=0.5,
        le=1.0,
        description="Minimum cosine similarity score (0.5–1.0)."
    )
    days_back: int = Field(
        default=30, ge=1, le=365,
        description="How many days back to search."
    )
    limit: int = Field(default=20, ge=1, le=100)


class SimilarityHuntResponse(BaseModel):
    query_text: str
    results: List[Dict[str, Any]]
    result_count: int
    cosine_threshold: float
    days_searched: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "/similarity",
    response_model=SimilarityHuntResponse,
    summary="Retroactive semantic similarity hunt",
    tags=["Forensic AI Observability"],
)
async def hunt_by_similarity(
    request: SimilarityHuntRequest,
    current_user=Depends(get_current_active_user),
) -> SimilarityHuntResponse:
    """
    Given a suspicious prompt or phrase, find all historically similar
    interactions in the semantic logs using pgvector cosine similarity.

    This enables retroactive threat hunting — if a zero-day is discovered
    today, operators can instantly check whether the same attacker
    probed the system in the past.
    """
    from app.modules.firewall.llm_firewall import get_firewall
    firewall = get_firewall()

    if not hasattr(firewall, '_model') or firewall._model is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Semantic model not loaded. Run setup_ai_firewall.sh first."
        )

    try:
        # Compute query embedding using the existing LLMFirewall model
        embedding = firewall._model.encode(request.query_text).tolist()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Embedding computation failed: {str(exc)}"
        )

    results = await semantic_logger.retroactive_hunt(
        query_embedding=embedding,
        tenant_id=request.tenant_id,
        limit=request.limit,
        cosine_threshold=request.cosine_threshold,
        days_back=request.days_back,
    )

    # Sanitize results (remove raw embedding vectors from API response)
    safe_results = [
        {k: v for k, v in r.items() if k != 'embedding'}
        for r in results
    ]

    return SimilarityHuntResponse(
        query_text=request.query_text,
        results=safe_results,
        result_count=len(safe_results),
        cosine_threshold=request.cosine_threshold,
        days_searched=request.days_back,
    )


@router.get(
    "/entity/{entity_id}",
    summary="Get interaction timeline for a specific entity",
    tags=["Forensic AI Observability"],
)
async def get_entity_timeline(
    entity_id: str,
    tenant_id: str = Query(..., description="Tenant scope."),
    limit: int = Query(default=100, ge=1, le=500),
    current_user=Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Returns the chronological interaction timeline for a specific entity.
    Useful for reconstructing multi-stage attack chains.
    """
    timeline = await semantic_logger.get_entity_timeline(
        entity_id=entity_id,
        tenant_id=tenant_id,
        limit=limit,
    )

    # Compute chain statistics
    blocks = sum(1 for e in timeline if e.get('action') == 'BLOCK')
    warns = sum(1 for e in timeline if e.get('action') == 'WARN')
    multi_stage = [e for e in timeline if e.get('multi_stage_flag')]
    avg_score = (
        sum(e.get('threat_score', 0) for e in timeline) / len(timeline)
        if timeline else 0.0
    )

    return {
        "entity_id": entity_id,
        "tenant_id": tenant_id,
        "total_interactions": len(timeline),
        "blocks": blocks,
        "warns": warns,
        "multi_stage_detections": len(multi_stage),
        "avg_threat_score": round(avg_score, 4),
        "timeline": timeline,
    }


@router.get(
    "/stats",
    summary="Semantic logging statistics for a tenant",
    tags=["Forensic AI Observability"],
)
async def get_forensic_stats(
    tenant_id: str = Query(...),
    current_user=Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Returns semantic logging statistics for a tenant over the last 24 hours.
    Includes queue depth, dropped entries, and threat distribution.
    """
    stats = await semantic_logger.get_stats(tenant_id=tenant_id)
    return {"tenant_id": tenant_id, **stats}


@router.get(
    "/health",
    summary="Check forensic observability system health",
    tags=["Forensic AI Observability"],
)
async def forensic_health() -> Dict[str, Any]:
    """
    Check the health of the forensic logging system.
    Returns queue depth and whether pgvector is reachable.
    """
    return {
        "status": "operational",
        "queue_depth": semantic_logger._queue.qsize(),
        "queue_max": semantic_logger._queue.maxsize,
        "dropped_entries": semantic_logger._dropped_count,
        "writer_running": semantic_logger._running,
        "model_loaded": semantic_logger._model is not None,
        "db_connected": semantic_logger._pool is not None,
        "log_threshold": semantic_logger.LOG_THRESHOLD if hasattr(semantic_logger, 'LOG_THRESHOLD') else 0.30,
        "sample_rate": semantic_logger._sample_rate,
    }
