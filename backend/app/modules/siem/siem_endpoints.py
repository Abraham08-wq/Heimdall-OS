"""
siem_endpoints.py — ProjectXY Phase 4: SIEM & SOAR API Endpoints
=================================================================
Exposes SIEM threat intelligence and SOAR playbook controls via REST API.

Routes:
  GET  /api/v1/siem/threats/live       — Last 100 classified threats (TimescaleDB)
  GET  /api/v1/siem/threats/summary    — Daily aggregated threat summary
  GET  /api/v1/siem/apt-chains         — Detected multi-stage APT attacks
  POST /api/v1/siem/soar/block         — Manually trigger SOAR block
  POST /api/v1/siem/soar/unblock       — Lift a SOAR block
  GET  /api/v1/siem/dga/check          — Check domain against DGA detector
  POST /api/v1/siem/dga/batch          — Batch DGA domain check
"""
import json
from datetime import datetime, timezone
from typing import List, Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.infrastructure.session import get_db

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SIEMThreatResponse(BaseModel):
    id: str
    timestamp: str
    entity_id: str
    source_ip: Optional[str]
    risk_score: float
    soar_action: Optional[str]
    is_apt_chain: bool
    reasons: Optional[list]
    mitre_tactic: Optional[str]


class SOARBlockRequest(BaseModel):
    ip_address: str = Field(..., description="IP to block globally")
    entity_id: str = Field(..., description="Entity/session identifier")
    reason: str = Field(..., description="Human-readable reason")
    duration_hours: int = Field(default=24, ge=1, le=720)
    tenant_id: str = "default"


class DGACheckRequest(BaseModel):
    domain: str = Field(..., description="Domain name to check")


class DGABatchRequest(BaseModel):
    domains: List[str] = Field(..., min_items=1, max_items=500)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/threats/live",
    summary="Live SIEM Threat Feed",
    tags=["SIEM — Behavioral Analysis"],
)
async def get_live_threats(
    limit: int = Query(100, le=500),
    min_risk: float = Query(0.0, ge=0.0, le=100.0),
    apt_only: bool = Query(False),
    db=Depends(get_db),
):
    """
    Returns the most recent SIEM-classified threat events from TimescaleDB.
    Optimised via TimescaleDB chunk-exclusion for sub-millisecond response.
    """
    try:
        from sqlalchemy import text
        query = """
            SELECT id::text, timestamp, entity_id, source_ip, risk_score,
                   soar_action, is_apt_chain, reasons, mitre_tactic
            FROM siem_threat_events
            WHERE risk_score >= :min_risk
              AND (:apt_only = FALSE OR is_apt_chain = TRUE)
            ORDER BY timestamp DESC
            LIMIT :limit
        """
        result = db.execute(
            text(query),
            {"min_risk": min_risk, "limit": limit, "apt_only": apt_only}
        ).fetchall()

        return [
            {
                "id": row[0],
                "timestamp": row[1].isoformat() if row[1] else None,
                "entity_id": row[2],
                "source_ip": row[3],
                "risk_score": row[4],
                "soar_action": row[5],
                "is_apt_chain": row[6],
                "reasons": row[7] or [],
                "mitre_tactic": row[8],
            }
            for row in result
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/threats/summary",
    summary="Daily Threat Intelligence Summary",
    tags=["SIEM — Behavioral Analysis"],
)
async def get_threat_summary(
    days: int = Query(7, ge=1, le=90),
    db=Depends(get_db),
):
    """
    Daily aggregated threat summary from the TimescaleDB continuous aggregate view.
    Uses the `daily_siem_summary` materialized view for instant response.
    """
    try:
        from sqlalchemy import text
        result = db.execute(
            text("""
                SELECT bucket, soar_action,
                       event_count, avg_risk_score, max_risk_score, apt_chain_count
                FROM daily_siem_summary
                WHERE bucket >= NOW() - INTERVAL ':days days'
                ORDER BY bucket DESC
            """),
            {"days": days}
        ).fetchall()

        return [
            {
                "date": row[0].date().isoformat() if row[0] else None,
                "soar_action": row[1],
                "event_count": row[2],
                "avg_risk_score": round(float(row[3] or 0), 2),
                "max_risk_score": round(float(row[4] or 0), 2),
                "apt_chain_count": row[5],
            }
            for row in result
        ]
    except Exception as exc:
        # Graceful: table may not be populated yet
        return {"message": "Summary data not yet available. TimescaleDB aggregate running.", "error": str(exc)}


@router.get(
    "/threats/firewall",
    summary="AI Firewall Threat Events",
    tags=["AI Firewall — Sovereign Guardrail"],
)
async def get_firewall_events(
    limit: int = Query(50, le=200),
    action: Optional[str] = Query(None, description="Filter: BLOCK | SCRUB_AND_PASS | PASS"),
    db=Depends(get_db),
):
    """Recent AI Firewall decisions from TimescaleDB."""
    try:
        from sqlalchemy import text
        where = "WHERE action = :action" if action else ""
        result = db.execute(
            text(f"""
                SELECT id::text, timestamp, tenant_id, entity_id, action,
                       threat_score, semantic_similarity, matched_category,
                       pii_types_detected, reasons, latency_ms, prompt_hash
                FROM firewall_events
                {where}
                ORDER BY timestamp DESC
                LIMIT :limit
            """),
            {"action": action, "limit": limit}
        ).fetchall()

        return [
            {
                "id": row[0],
                "timestamp": row[1].isoformat() if row[1] else None,
                "tenant_id": row[2],
                "entity_id": row[3],
                "action": row[4],
                "threat_score": row[5],
                "semantic_similarity": row[6],
                "matched_category": row[7],
                "pii_types": row[8] or [],
                "reasons": row[9] or [],
                "latency_ms": row[10],
                "prompt_hash": row[11],
            }
            for row in result
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/soar/block",
    summary="Manual SOAR Block Execution",
    tags=["SOAR — Automated Response"],
)
async def soar_manual_block(payload: SOARBlockRequest):
    """Manually trigger the SOAR block playbook for a specific IP/entity."""
    try:
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

        block_data = json.dumps({
            "blocked_at": datetime.now(timezone.utc).isoformat(),
            "reason": payload.reason,
            "tenant_id": payload.tenant_id,
            "manual_block": True,
        })

        duration = payload.duration_hours * 3600
        await redis_client.setex(f"soar:blocked_ip:{payload.ip_address}", duration, block_data)
        await redis_client.setex(f"containment:isolated:{payload.entity_id}", duration, payload.reason)
        await redis_client.publish(
            "soar:ip_block_events",
            json.dumps({"ip": payload.ip_address, "action": "MANUAL_BLOCK", "tenant": payload.tenant_id})
        )
        await redis_client.aclose()

        return {
            "status": "BLOCKED",
            "ip_address": payload.ip_address,
            "entity_id": payload.entity_id,
            "duration_hours": payload.duration_hours,
            "expires_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/soar/unblock",
    summary="Lift SOAR Block",
    tags=["SOAR — Automated Response"],
)
async def soar_unblock(ip_address: str, entity_id: str):
    """Remove a SOAR block for an IP address and entity."""
    try:
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await redis_client.delete(f"soar:blocked_ip:{ip_address}")
        await redis_client.delete(f"containment:isolated:{entity_id}")
        await redis_client.publish(
            "soar:ip_block_events",
            json.dumps({"ip": ip_address, "action": "UNBLOCK"})
        )
        await redis_client.aclose()
        return {"status": "UNBLOCKED", "ip_address": ip_address, "entity_id": entity_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/dga/check",
    summary="DGA Domain Prediction",
    tags=["Offensive AI — DGA Detector"],
)
async def dga_check(domain: str = Query(..., description="Domain to check")):
    """Check whether a domain was generated by a DGA botnet algorithm."""
    from app.modules.offensive.dga_detector import dga_detector
    result = dga_detector.predict(domain)
    return result


@router.post(
    "/dga/batch",
    summary="Batch DGA Domain Check",
    tags=["Offensive AI — DGA Detector"],
)
async def dga_batch_check(payload: DGABatchRequest):
    """Batch-check up to 500 domains against the DGA predictor."""
    from app.modules.offensive.dga_detector import dga_detector
    results = [dga_detector.predict(d) for d in payload.domains]
    total_dga = sum(1 for r in results if r["is_dga"])
    return {
        "checked": len(results),
        "dga_detected": total_dga,
        "results": results,
    }


@router.get(
    "/soar/status",
    summary="SOAR Block Status",
    tags=["SOAR — Automated Response"],
)
async def soar_status(ip_address: str = Query(...)):
    """Check if an IP is currently blocked by SOAR."""
    try:
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        block_data = await redis_client.get(f"soar:blocked_ip:{ip_address}")
        ttl = await redis_client.ttl(f"soar:blocked_ip:{ip_address}")
        await redis_client.aclose()

        if block_data:
            return {
                "is_blocked": True,
                "ip_address": ip_address,
                "ttl_seconds": ttl,
                "block_data": json.loads(block_data),
            }
        return {"is_blocked": False, "ip_address": ip_address}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
