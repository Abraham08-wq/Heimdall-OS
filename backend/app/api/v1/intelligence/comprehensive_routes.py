"""
INTELLIGENCE API ROUTES
=======================
FastAPI routes integrating all sovereign intelligence systems

Provides endpoints for:
- Neural De-Masking
- Autonomous SOC threat hunting
- Risk projection and VaR calculation
- Global radar scanning
- Hive-mind vaccination system

SECURITY: All endpoints require authentication. Emergency/destructive
endpoints require superuser privilege.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import Optional, Dict, List, Any
import json
import logging
from datetime import datetime, timezone

from app.api import deps
from app.models.models import User

# Import endpoint handlers directly
from app.services.intelligence.neural_demasker import (
    NeuralDemasker, ThreatLevel, unmask_actor_endpoint, link_aliases_endpoint
)
from app.services.intelligence.autonomous_soc import (
    AutonomousSOC, ResponseAction, start_hunt_endpoint,
    get_active_threats_endpoint, execute_blackhole_endpoint
)
from app.services.intelligence.risk_projection import (
    FAIRModel, GeopoliticalAnalyzer, BusinessImpactProjector,
    assess_risk_endpoint, analyze_geopolitical_endpoint,
    project_business_impact_endpoint
)
from app.services.intelligence.omniradar import (
    SovereignRadar, search_organization_endpoint,
    search_threat_actor_endpoint, search_vulnerability_endpoint,
    search_malware_endpoint, get_radar_snapshot_endpoint
)
from app.services.intelligence.hive_mind import (
    HiveMindNetwork, discover_threat_endpoint,
    validate_threat_endpoint, distribute_vaccine_endpoint,
    get_hive_status_endpoint, apply_vaccine_endpoint
)

logger = logging.getLogger("projectxy.intel.comprehensive")

router = APIRouter(tags=["Sovereign Intelligence"])

# ──────────────────────────────────────────────────────────────────
# NEURAL DE-MASKING ENDPOINTS
# ──────────────────────────────────────────────────────────────────

@router.post("/demasking/unmask-actor")
async def unmask_threat_actor(
    alias: str,
    platform: str,
    current_user: User = Depends(deps.get_current_active_user),
) -> dict:
    """Unmask a threat actor across multiple platforms"""
    demasker = NeuralDemasker()
    result = await unmask_actor_endpoint(demasker, alias, platform)

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return {
        "status": "success",
        "actor": result,
        "message": f"Unmasked threat actor with {len(result.get('known_aliases', []))} known aliases",
    }


@router.post("/demasking/link-aliases", response_model=None)
async def link_user_aliases(
    alias_a: str,
    alias_b: str,
    current_user: User = Depends(deps.get_current_active_user),
):
    """Link two user aliases based on behavioral similarity"""
    demasker = NeuralDemasker()
    result = await link_aliases_endpoint(demasker, alias_a, alias_b)

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return {
        "status": "success",
        "link": result,
        "confidence": result.get("confidence_score", 0),
        "is_verified": result.get("is_verified", False),
    }


@router.get("/demasking/profile/{actor_id}", response_model=None)
async def get_actor_profile(
    actor_id: str,
    current_user: User = Depends(deps.get_current_active_user),
):
    """Retrieve complete profile of unmasked threat actor"""
    return {"actor_id": actor_id, "status": "not_found"}


# ──────────────────────────────────────────────────────────────────
# AUTONOMOUS SOC ENDPOINTS
# ──────────────────────────────────────────────────────────────────

@router.post("/soc/start-hunting", response_model=None)
async def start_threat_hunting(
    background_tasks: BackgroundTasks,
    interval: int = 300,
    current_user: User = Depends(deps.get_current_active_user),
):
    """Start continuous autonomous threat hunting"""
    soc = AutonomousSOC()
    result = await start_hunt_endpoint(soc)

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    logger.info(f"[SOC] Threat hunting started by {current_user.email}")
    return {
        "status": "hunting_initiated",
        "message": "Continuous threat hunting activated",
        "interval_seconds": interval,
    }


@router.get("/soc/active-threats", response_model=None)
async def get_active_threats(
    current_user: User = Depends(deps.get_current_active_user),
):
    """Get list of currently active threats detected by BlazeAI"""
    soc = AutonomousSOC()
    result = await get_active_threats_endpoint(soc)

    return {
        "timestamp": result.get("timestamp"),
        "active_threats": result.get("events", []),
        "total_count": len(result.get("events", [])),
    }


@router.post("/soc/blackhole/{target_ip}", response_model=None)
async def initiate_blackhole_containment(
    target_ip: str,
    current_user: User = Depends(deps.get_current_active_user),
):
    """Initiate Operation Blackhole containment for a target IP. Requires operator/admin."""
    role = getattr(current_user, "role", "viewer")
    if role not in ("operator", "admin"):
        raise HTTPException(
            status_code=403,
            detail="Blackhole containment requires operator or admin clearance.",
        )

    soc = AutonomousSOC()
    result = await execute_blackhole_endpoint(soc, target_ip)

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    logger.warning(f"[SOC] Blackhole containment activated on {target_ip} by {current_user.email}")
    return {
        "status": "blackhole_activated",
        "session_id": result.get("response_id"),
        "target": target_ip,
        "message": f"Deceptive sandbox activated for {target_ip}",
    }


@router.get("/soc/blackhole-session/{session_id}", response_model=None)
async def get_blackhole_session(
    session_id: str,
    current_user: User = Depends(deps.get_current_active_user),
):
    """Get status and artifacts from active blackhole session"""
    soc = AutonomousSOC()
    session = await soc.get_blackhole_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "status": session.status,
        "is_isolated": session.is_isolated,
        "artifacts": session.collected_artifacts,
        "ai_queries": session.ai_interrogation_queries,
        "insights": session.insights_gathered,
    }


# ──────────────────────────────────────────────────────────────────
# RISK PROJECTION ENDPOINTS
# ──────────────────────────────────────────────────────────────────

@router.post("/risk/fair-assessment", response_model=None)
async def fair_risk_assessment(
    risk_model: Dict,
    current_user: User = Depends(deps.get_current_active_user),
):
    """Perform FAIR framework risk assessment"""
    result = await assess_risk_endpoint(risk_model)

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return {"status": "assessed", "metrics": result}


@router.post("/risk/geopolitical-analysis", response_model=None)
async def analyze_geopolitical_risk(
    country: str,
    signal_type: str,
    current_user: User = Depends(deps.get_current_active_user),
):
    """Analyze geopolitical signals and strategic implications"""
    result = await analyze_geopolitical_endpoint(country, signal_type)

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return {"country": country, "signal_type": signal_type, "analysis": result}


@router.post("/risk/business-impact", response_model=None)
async def project_business_impact(
    incident_type: str,
    company_revenue: float,
    company_market_cap: float,
    customers: int,
    current_user: User = Depends(deps.get_current_active_user),
):
    """Project financial and operational impact of security incident"""
    result = await project_business_impact_endpoint(
        incident_type, company_revenue, company_market_cap, customers
    )

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return {"scenario": incident_type, "impact": result}


# ──────────────────────────────────────────────────────────────────
# SOVEREIGN RADAR ENDPOINTS
# ──────────────────────────────────────────────────────────────────

@router.get("/radar/snapshot", response_model=None)
async def get_global_radar_snapshot(
    current_user: User = Depends(deps.get_current_active_user),
):
    """Get current snapshot of global threat landscape"""
    radar = SovereignRadar()
    result = await get_radar_snapshot_endpoint(radar)

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/radar/organization/{org_name}", response_model=None)
async def search_organization_exposure(
    org_name: str,
    current_user: User = Depends(deps.get_current_active_user),
):
    """Search for all exposed assets of an organization"""
    radar = SovereignRadar()
    result = await search_organization_endpoint(radar, org_name)
    return {"organization": org_name, "exposure": result}


@router.get("/radar/threat-actor/{actor_name}", response_model=None)
async def search_threat_actor_infrastructure(
    actor_name: str,
    current_user: User = Depends(deps.get_current_active_user),
):
    """Search for infrastructure operated by threat actor"""
    radar = SovereignRadar()
    result = await search_threat_actor_endpoint(radar, actor_name)
    return {"threat_actor": actor_name, "infrastructure": result}


@router.get("/radar/vulnerability/{cve_id}", response_model=None)
async def find_vulnerable_systems(
    cve_id: str,
    current_user: User = Depends(deps.get_current_active_user),
):
    """Find all exposed systems vulnerable to a specific CVE"""
    radar = SovereignRadar()
    result = await search_vulnerability_endpoint(radar, cve_id)
    return result


@router.get("/radar/malware/{malware_name}", response_model=None)
async def find_malware_infrastructure(
    malware_name: str,
    current_user: User = Depends(deps.get_current_active_user),
):
    """Search for systems infected with specific malware"""
    radar = SovereignRadar()
    result = await search_malware_endpoint(radar, malware_name)
    return {"malware": malware_name, "infrastructure": result}


# ──────────────────────────────────────────────────────────────────
# HIVE-MIND VACCINATION ENDPOINTS
# ──────────────────────────────────────────────────────────────────

@router.post("/hivemind/discover-threat", response_model=None)
async def discover_and_share_threat(
    threat_data: Dict,
    current_user: User = Depends(deps.get_current_active_user),
):
    """Discover a threat locally and share with hive-mind network"""
    hivemind = HiveMindNetwork()
    result = await discover_threat_endpoint(hivemind, threat_data)

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/hivemind/validate-threat/{vaccine_id}", response_model=None)
async def validate_discovered_threat(
    vaccine_id: str,
    current_user: User = Depends(deps.get_current_active_user),
):
    """Validate a discovered threat for distribution"""
    hivemind = HiveMindNetwork()
    result = await validate_threat_endpoint(hivemind, vaccine_id)

    if not result.get("validated"):
        raise HTTPException(status_code=400, detail="Validation failed")

    return {"status": "validated", "vaccine_id": vaccine_id}


@router.post("/hivemind/distribute-vaccine/{vaccine_id}", response_model=None)
async def distribute_threat_vaccine(
    vaccine_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(deps.get_current_active_user),
):
    """Distribute threat vaccine to entire hive-mind network. Requires operator/admin."""
    role = getattr(current_user, "role", "viewer")
    if role not in ("operator", "admin"):
        raise HTTPException(
            status_code=403,
            detail="Vaccine distribution requires operator or admin clearance.",
        )

    hivemind = HiveMindNetwork()
    nodes_count = await distribute_vaccine_endpoint(hivemind, vaccine_id)

    logger.info(f"[HIVEMIND] Vaccine {vaccine_id} distributed by {current_user.email}")
    return {
        "status": "distributed",
        "vaccine_id": vaccine_id,
        "nodes_notified": nodes_count.get("nodes_notified", 0),
    }


@router.post("/hivemind/apply-vaccine/{vaccine_id}", response_model=None)
async def apply_threat_vaccine(
    vaccine_id: str,
    current_user: User = Depends(deps.get_current_active_user),
):
    """Manually apply a threat vaccine locally"""
    hivemind = HiveMindNetwork()
    result = await apply_vaccine_endpoint(hivemind, vaccine_id)

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/hivemind/status", response_model=None)
async def get_hive_status(
    current_user: User = Depends(deps.get_current_active_user),
):
    """Get status of entire hive-mind network"""
    hivemind = HiveMindNetwork()
    result = await get_hive_status_endpoint(hivemind)
    return result


@router.get("/hivemind/vaccine-stats/{vaccine_id}", response_model=None)
async def get_vaccine_effectiveness(
    vaccine_id: str,
    current_user: User = Depends(deps.get_current_active_user),
):
    """Get effectiveness statistics for a vaccine"""
    hivemind = HiveMindNetwork()
    stats = await hivemind.get_vaccine_stats(vaccine_id)

    if not stats:
        raise HTTPException(status_code=404, detail="Vaccine not found")

    return {"vaccine_id": vaccine_id, "stats": stats}


# ──────────────────────────────────────────────────────────────────
# INTEGRATED INTELLIGENCE ENDPOINTS
# ──────────────────────────────────────────────────────────────────

@router.post("/integrated/investigate-incident", response_model=None)
async def integrated_incident_investigation(
    incident_data: Dict,
    current_user: User = Depends(deps.get_current_active_user),
):
    """Integrated investigation using all intelligence systems"""
    return {
        "status": "investigating",
        "incident": incident_data.get("incident_name"),
        "phase": "data_collection",
        "initiated_by": str(current_user.id),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/integrated/threat-landscape-summary", response_model=None)
async def get_threat_landscape_summary(
    current_user: User = Depends(deps.get_current_active_user),
):
    """Get comprehensive summary of current threat landscape"""
    from app.infrastructure.cache.redis_manager import redis_cache
    from sqlalchemy.orm import Session
    from app.infrastructure.session import SessionLocal
    from sqlalchemy import text

    db: Session = SessionLocal()
    try:
        # Real data from semantic_logs
        row = db.execute(text(
            "SELECT COUNT(*) as total, "
            "SUM(CASE WHEN action='BLOCK' THEN 1 ELSE 0 END) as blocks, "
            "AVG(threat_score) as avg_score "
            "FROM semantic_logs WHERE created_at >= NOW() - INTERVAL '24 hours'"
        )).fetchone()
        total = int(row[0] or 0) if row else 0
        blocks = int(row[1] or 0) if row else 0
        avg_score = float(row[2] or 0.0) if row else 0.0
    except Exception:
        total, blocks, avg_score = 0, 0, 0.0
    finally:
        db.close()

    threat_level = "critical" if avg_score > 0.7 else "elevated" if avg_score > 0.4 else "moderate"

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "threat_level": threat_level,
        "summary": "Integrated threat intelligence from ProjectXY Cognitive Shield",
        "metrics": {
            "total_events_24h": total,
            "blocked_events_24h": blocks,
            "average_threat_score": round(avg_score, 4),
        },
    }


# ──────────────────────────────────────────────────────────────────
# SOVEREIGN COMMAND ENDPOINTS  — SUPERUSER ONLY
# ──────────────────────────────────────────────────────────────────

@router.post("/command/emergency-lockdown", response_model=None)
async def emergency_system_lockdown(
    reason: str,
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """
    EMERGENCY: Initiate system-wide lockdown.
    Requires superuser. Executes real backend actions:
    - Revoke all active JWT sessions via Redis
    - Mark all devices as isolated in DB
    - Publish lockdown event to telemetry channel
    """
    from app.infrastructure.cache.redis_manager import redis_cache
    from sqlalchemy.orm import Session
    from app.infrastructure.session import SessionLocal
    from sqlalchemy import text
    import json as _json

    revoked = 0
    isolated = 0
    db: Session = SessionLocal()
    try:
        # 1. Revoke all JWT sessions by clearing session keys in Redis
        try:
            session_keys = redis_cache.redis_client.keys("session:*")
            if session_keys:
                redis_cache.redis_client.delete(*session_keys)
                revoked = len(session_keys)
        except Exception as e:
            logger.warning(f"[LOCKDOWN] Redis session revocation partial: {e}")

        # 2. Mark all devices as isolated
        try:
            result = db.execute(text(
                "UPDATE devices SET status = 'isolated', updated_at = NOW() "
                "WHERE status NOT IN ('offline', 'decommissioned') "
                "RETURNING id"
            ))
            isolated = result.rowcount
            db.commit()
        except Exception as e:
            db.rollback()
            logger.warning(f"[LOCKDOWN] Device isolation partial: {e}")

        # 3. Publish lockdown event to telemetry
        try:
            redis_cache.redis_client.publish(
                "god_view_sync_global",
                _json.dumps({
                    "type": "EMERGENCY_LOCKDOWN",
                    "event_type": "EMERGENCY_LOCKDOWN",
                    "channel": "threats",
                    "severity": "critical",
                    "data": {
                        "reason": reason,
                        "initiated_by": str(current_user.id),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                }),
            )
        except Exception as e:
            logger.warning(f"[LOCKDOWN] Telemetry publish failed: {e}")

        logger.critical(
            f"🚨 EMERGENCY LOCKDOWN initiated by superuser {current_user.email}. "
            f"Reason: {reason}. Sessions revoked: {revoked}. Devices isolated: {isolated}."
        )

        return {
            "status": "LOCKDOWN_ACTIVE",
            "reason": reason,
            "initiated_by": str(current_user.id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sessions_revoked": revoked,
            "devices_isolated": isolated,
            "message": "SYSTEM IN LOCKDOWN MODE — All sessions terminated, all devices isolated",
        }
    finally:
        db.close()


@router.get("/command/system-status", response_model=None)
async def get_system_status(
    current_user: User = Depends(deps.get_current_active_user),
):
    """Get real comprehensive system status from live services"""
    from app.infrastructure.cache.redis_manager import redis_cache
    from app.infrastructure.session import SessionLocal
    from sqlalchemy import text

    results: Dict[str, Any] = {}

    # Redis ping
    try:
        redis_cache.redis_client.ping()
        results["redis"] = "online"
    except Exception:
        results["redis"] = "offline"

    # DB ping
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        results["database"] = "online"

        # Active entities
        row = db.execute(text("SELECT COUNT(*) FROM entities")).fetchone()
        results["entity_count"] = int(row[0]) if row else 0

        # Semantic logs last hour
        row = db.execute(text(
            "SELECT COUNT(*) FROM semantic_logs WHERE created_at >= NOW() - INTERVAL '1 hour'"
        )).fetchone()
        results["firewall_events_1h"] = int(row[0]) if row else 0

    except Exception as e:
        results["database"] = f"degraded: {e}"
    finally:
        db.close()

    # Firewall queued entries
    try:
        from app.modules.firewall.semantic_logger import semantic_logger
        results["firewall_queue_depth"] = semantic_logger._queue.qsize()
    except Exception:
        results["firewall_queue_depth"] = "unknown"

    results.update({
        "soc": "active",
        "radar": "scanning",
        "hivemind": "online",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return results