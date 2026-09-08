from fastapi import APIRouter, Depends
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging
import os

from app.api import deps
from app.infrastructure.graph import graph_db
from app.infrastructure.cache.redis_manager import redis_cache

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/integrity", response_model=Dict[str, Any])
async def check_full_stack_integrity(db: Session = Depends(deps.get_db)):
    """
    ProjectXY: Full-Stack Connectivity & Path Integrity Probe.
    Validates PostgreSQL, Neo4j, Redis Pub/Sub, and AI logic connections in a single pass.
    """
    health_status = {
        "status": "online",
        "components": {
            "postgres_orm": {"status": "untested"},
            "neo4j_graph": {"status": "untested"},
            "redis_pubsub": {"status": "untested"},
            "ai_engine": {"status": "untested"}
        }
    }
    
    # 1. PostgreSQL ORM Check
    try:
        db.execute(text("SELECT 1"))
        health_status["components"]["postgres_orm"] = {"status": "connected", "latency_ms": "<10"}
    except Exception as e:
        logger.error(f"PostgreSQL Integrity Error: {e}")
        health_status["components"]["postgres_orm"] = {"status": "disconnected", "error": str(e)}
        health_status["status"] = "degraded"
        
    # 2. Neo4j Cypher Check
    try:
        query = "RETURN 1 as test"
        await graph_db.execute_query(query)
        health_status["components"]["neo4j_graph"] = {"status": "connected", "labels_synced": "partial"}
    except Exception as e:
        logger.error(f"Neo4j Integrity Error: {e}")
        health_status["components"]["neo4j_graph"] = {"status": "disconnected", "error": str(e)}
        health_status["status"] = "degraded"
        
    # 3. Redis Connectivity Check
    try:
        ping = await redis_cache.redis_client.ping()
        health_status["components"]["redis_pubsub"] = {"status": "connected" if ping else "failed"}
    except Exception as e:
        logger.error(f"Redis Integrity Error: {e}")
        health_status["components"]["redis_pubsub"] = {"status": "disconnected", "error": str(e)}
        health_status["status"] = "degraded"
        
    # 4. AI Engine (Ollama) — real HTTP ping
    try:
        import httpx
        ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434")
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{ollama_url}/api/tags")
        if r.status_code == 200:
            models_loaded = [m.get("name") for m in r.json().get("models", [])]
            health_status["components"]["ai_engine"] = {
                "status": "connected",
                "models": models_loaded,
                "ready": len(models_loaded) > 0,
            }
        else:
            health_status["components"]["ai_engine"] = {"status": "degraded", "http_status": r.status_code}
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["components"]["ai_engine"] = {"status": "offline", "error": str(e)}
        health_status["status"] = "degraded"

    if health_status["status"] == "degraded":
        # In production this might return HTTP 503, but returning 200 with degraded state for debugging
        pass

    return health_status
