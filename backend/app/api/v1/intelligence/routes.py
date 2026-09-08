"""
Intelligence API Routes (Phase 3)

REST endpoints for:
- Attacker profiling (De-Masking)
- Payload translation (Linguistic Mesh)
- System snapshots (Digital Twin)
- Detection gap analysis (Purple Team)
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.services.intelligence import (
    NeuralDeMaskingEngine,
    ExecutionSignature,
    AttackerProfile,
    LinguisticMeshEngine,
    TranslatedPayload,
    TranslationConfig,
    Language,
    ObfuscationLevel,
    DigitalTwinEngine,
    SystemSnapshot,
    SnapshotDiff,
    PurpleTeamFeedbackEngine,
    PurpleTeamReport,
    DetectionGap,
)

import logging

logger = logging.getLogger(__name__)

# Router setup
router = APIRouter(prefix="/intelligence", tags=["Intelligence - Phase 3"])

# ============================================================================
# DEPENDENCY INJECTION
# ============================================================================

# Placeholder for engine instances (would be injected from main app)
demasking_engine: Optional[NeuralDeMaskingEngine] = None
translation_engine: Optional[LinguisticMeshEngine] = None
digital_twin_engine: Optional[DigitalTwinEngine] = None
purple_team_engine: Optional[PurpleTeamFeedbackEngine] = None


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ExtractSignatureRequest(BaseModel):
    """Request to extract attack signature from execution output"""
    execution_id: str
    script_id: str
    stdout: str
    stderr: str


class BuildProfileRequest(BaseModel):
    """Request to build attacker profile from signatures"""
    signature_ids: List[str]
    description: Optional[str] = None


class TranslatePayloadRequest(BaseModel):
    """Request to translate a payload"""
    code: str
    source_language: Language
    target_language: Language
    obfuscation_level: ObfuscationLevel = ObfuscationLevel.MEDIUM
    polymorphic_variations: int = 1


class SnapshotRequest(BaseModel):
    """Request to create a pre-execution snapshot"""
    execution_id: str
    risk_level: int
    description: Optional[str] = None


class PurpleTeamReportRequest(BaseModel):
    """Request to generate Purple Team report"""
    period_hours: int = 24
    include_recommendations: bool = True


# ============================================================================
# NEURAL DE-MASKING ENDPOINTS (Phase 3A)
# ============================================================================

@router.post("/demasking/extract-signature")
async def extract_attack_signature(request: ExtractSignatureRequest):
    """
    Extract attack signature from execution output.
    
    Detects:
    - MITRE ATT&CK TTPs
    - Known hacker tools
    - Indicators of Compromise (IoCs)
    - Suspicious behaviors
    - Risk score assessment
    
    Returns: ExecutionSignature with detected TTPs and risk metrics
    """
    if not demasking_engine:
        raise HTTPException(status_code=503, detail="De-Masking engine not initialized")

    try:
        signature = demasking_engine.extract_signature(
            execution_id=request.execution_id,
            script_id=request.script_id,
            stdout=request.stdout,
            stderr=request.stderr,
        )

        return {
            "execution_id": signature.execution_id,
            "detected_ttps": [ttp.value for ttp in signature.detected_ttps],
            "detected_tools": signature.detected_tools,
            "indicators_of_compromise": signature.indicators_of_compromise,
            "suspicious_behaviors": signature.suspicious_behaviors,
            "risk_score": signature.risk_score,
            "extraction_confidence": signature.extraction_confidence,
        }

    except Exception as e:
        logger.error(f"Error extracting signature: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/demasking/build-profile")
async def build_attacker_profile(request: BuildProfileRequest):
    """
    Build comprehensive attacker profile from multiple execution signatures.
    
    Performs:
    - TTP aggregation
    - Tool fingerprinting
    - Threat actor attribution (ML-based)
    - Behavioral clustering
    
    Returns: AttackerProfile with confidence scores and linked campaigns
    """
    if not demasking_engine:
        raise HTTPException(status_code=503, detail="De-Masking engine not initialized")

    try:
        # Retrieve signatures
        signatures = [
            demasking_engine.execution_signatures.get(sig_id)
            for sig_id in request.signature_ids
        ]
        signatures = [s for s in signatures if s]

        if not signatures:
            raise HTTPException(status_code=404, detail="No signatures found")

        # Build profile
        profile = demasking_engine.build_attacker_profile(signatures)

        # Store in Neo4j if available
        demasking_engine.store_profile_in_graph(profile)

        return {
            "actor_id": profile.actor_id,
            "display_name": profile.display_name,
            "confidence_score": profile.confidence_score,
            "ttps": [ttp.value for ttp in profile.ttps],
            "tools_used": profile.tools_used,
            "target_industries": profile.target_industries,
            "techniques_count": profile.techniques_count,
            "last_activity": profile.last_activity.isoformat(),
            "similarity_to_known_actors": profile.similarity_to_known_actors,
            "linked_campaigns": profile.linked_campaigns,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error building attacker profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/demasking/profiles")
async def list_attacker_profiles():
    """List all tracked attacker profiles"""
    if not demasking_engine:
        raise HTTPException(status_code=503, detail="De-Masking engine not initialized")

    try:
        profiles = demasking_engine.get_all_profiles()
        return [
            {
                "actor_id": p.actor_id,
                "display_name": p.display_name,
                "confidence_score": p.confidence_score,
                "tools_count": len(p.tools_used),
                "ttps_count": len(p.ttps),
                "last_activity": p.last_activity.isoformat(),
            }
            for p in profiles
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/demasking/profiles/{actor_id}")
async def get_attacker_profile(actor_id: str):
    """Get detailed attacker profile"""
    if not demasking_engine:
        raise HTTPException(status_code=503, detail="De-Masking engine not initialized")

    try:
        profile = demasking_engine.get_profile(actor_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        return {
            "actor_id": profile.actor_id,
            "display_name": profile.display_name,
            "confidence_score": profile.confidence_score,
            "ttps": [ttp.value for ttp in profile.ttps],
            "tools_used": profile.tools_used,
            "target_industries": profile.target_industries,
            "target_countries": profile.target_countries,
            "techniques_count": profile.techniques_count,
            "last_activity": profile.last_activity.isoformat(),
            "activity_patterns": profile.activity_patterns,
            "linked_campaigns": profile.linked_campaigns,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/demasking/correlations")
async def get_profile_correlations():
    """Find correlations between tracked attacker profiles"""
    if not demasking_engine:
        raise HTTPException(status_code=503, detail="De-Masking engine not initialized")

    try:
        correlations = demasking_engine.correlate_profiles()
        return {"correlations": correlations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# LINGUISTIC MESH TRANSLATION ENDPOINTS (Phase 3B)
# ============================================================================

@router.post("/translation/translate")
async def translate_payload(request: TranslatePayloadRequest):
    """
    Translate attack payload between languages with obfuscation.
    
    Supports:
    - Language conversion (Python ↔ Bash ↔ PowerShell)
    - Variable renaming obfuscation
    - Base64/Hex/XOR encoding
    - Polymorphic code generation
    - Signature evasion
    
    Returns: TranslatedPayload with variations and evasion score
    """
    if not translation_engine:
        raise HTTPException(status_code=503, detail="Translation engine not initialized")

    try:
        config = TranslationConfig(
            source_language=request.source_language,
            target_language=request.target_language,
            obfuscation_level=request.obfuscation_level,
            polymorphic_variations=request.polymorphic_variations,
        )

        payload = translation_engine.translate(request.code, config)

        return {
            "translated_code": payload.translated_code,
            "source_language": payload.source_language.value,
            "target_language": payload.target_language.value,
            "obfuscation_level": payload.obfuscation_level.value,
            "estimated_detection_evasion": payload.estimated_detection_evasion,
            "variations": payload.variations,
            "translation_chain": payload.translation_chain,
            "hash_signature": payload.hash_signature,
        }

    except Exception as e:
        logger.error(f"Error translating payload: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/translation/recommend-strategy")
async def recommend_translation_strategy(
    code: str, defensive_measures: List[str] = Query(...)
):
    """
    Recommend optimal translation strategy based on observed defensive measures.
    
    Analyzes:
    - Signature-based detection
    - Behavior-based detection
    - Sandboxing / VM detection
    
    Returns: Recommended TranslationConfig
    """
    if not translation_engine:
        raise HTTPException(status_code=503, detail="Translation engine not initialized")

    try:
        config = translation_engine.recommend_translation_strategy(code, defensive_measures)

        return {
            "source_language": config.source_language.value,
            "target_language": config.target_language.value,
            "obfuscation_level": config.obfuscation_level.value,
            "encoding_method": config.encoding_method.value,
            "add_junk_code": config.add_junk_code,
            "polymorphic_variations": config.polymorphic_variations,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/translation/history")
async def get_translation_history():
    """Get history of all payload translations"""
    if not translation_engine:
        raise HTTPException(status_code=503, detail="Translation engine not initialized")

    try:
        history = translation_engine.get_translation_history()
        return {
            "total_translations": len(history),
            "translations": [
                {
                    "created_at": p.created_at.isoformat(),
                    "source_language": p.source_language.value,
                    "target_language": p.target_language.value,
                    "evasion_score": p.estimated_detection_evasion,
                    "hash": p.hash_signature,
                }
                for p in history[-100:]  # Last 100
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# DIGITAL TWIN SNAPSHOT ENDPOINTS (Phase 3C)
# ============================================================================

@router.post("/snapshots/create-pre-execution")
async def create_pre_execution_snapshot(request: SnapshotRequest):
    """
    Create snapshot before executing risky operation.
    
    Captures:
    - Database state (PostgreSQL dump)
    - Filesystem state (directory snapshot)
    - Application state
    
    Returns: SnapshotMetadata with recovery point reference
    """
    if not digital_twin_engine:
        raise HTTPException(status_code=503, detail="Digital Twin engine not initialized")

    try:
        snapshot = digital_twin_engine.create_pre_execution_snapshot(
            execution_id=request.execution_id,
            risk_level=request.risk_level,
            created_by="system",  # Would come from auth context
            recovery_strategy="automatic_rollback",
        )

        return {
            "snapshot_id": snapshot.metadata.snapshot_id,
            "execution_id": snapshot.metadata.execution_id,
            "risk_level": snapshot.metadata.risk_level,
            "size_mb": snapshot.metadata.size_bytes / 1024 / 1024,
            "created_at": snapshot.metadata.created_at.isoformat(),
            "recovery_point_id": [rp for rp in digital_twin_engine.recovery_points if rp.startswith(
                f"rp_{snapshot.metadata.snapshot_id}"
            )][0] if digital_twin_engine.recovery_points else None,
        }

    except Exception as e:
        logger.error(f"Error creating snapshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapshots/{snapshot_id}")
async def get_snapshot_details(snapshot_id: str):
    """Get details of a specific snapshot"""
    if not digital_twin_engine:
        raise HTTPException(status_code=503, detail="Digital Twin engine not initialized")

    try:
        snapshot = digital_twin_engine.snapshots.get(snapshot_id)
        if not snapshot:
            raise HTTPException(status_code=404, detail="Snapshot not found")

        return {
            "snapshot_id": snapshot.metadata.snapshot_id,
            "execution_id": snapshot.metadata.execution_id,
            "type": snapshot.metadata.snapshot_type.value,
            "created_at": snapshot.metadata.created_at.isoformat(),
            "size_mb": snapshot.metadata.size_bytes / 1024 / 1024,
            "checksum": snapshot.metadata.checksum,
            "recovery_strategy": snapshot.metadata.recovery_strategy.value,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/snapshots/{before_id}/compare/{after_id}")
async def compare_snapshots(before_id: str, after_id: str):
    """
    Compare two snapshots and identify changes.
    
    Returns: SnapshotDiff with database and filesystem changes
    """
    if not digital_twin_engine:
        raise HTTPException(status_code=503, detail="Digital Twin engine not initialized")

    try:
        diff = digital_twin_engine.compare_snapshots(before_id, after_id)
        if not diff:
            raise HTTPException(status_code=404, detail="Could not compare snapshots")

        return {
            "before_snapshot_id": diff.before_snapshot_id,
            "after_snapshot_id": diff.after_snapshot_id,
            "timestamp": diff.timestamp.isoformat(),
            "database_changes": diff.database_changes,
            "filesystem_changes": diff.filesystem_changes,
            "affected_tables": diff.affected_tables,
            "affected_files": diff.affected_files,
            "summary": diff.summary,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/snapshots/{snapshot_id}/rollback")
async def rollback_to_snapshot(snapshot_id: str):
    """
    Perform rollback to a previous snapshot.
    
    Restores database and filesystem state.
    """
    if not digital_twin_engine:
        raise HTTPException(status_code=503, detail="Digital Twin engine not initialized")

    try:
        success = digital_twin_engine.rollback_to_snapshot(snapshot_id)
        if not success:
            raise HTTPException(status_code=400, detail="Rollback failed")

        return {
            "status": "success",
            "snapshot_id": snapshot_id,
            "message": "Successfully rolled back to snapshot",
        }

    except Exception as e:
        logger.error(f"Error performing rollback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapshots")
async def list_snapshots(
    execution_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=1000),
):
    """List available snapshots with optional filtering"""
    if not digital_twin_engine:
        raise HTTPException(status_code=503, detail="Digital Twin engine not initialized")

    try:
        snapshots = digital_twin_engine.snapshots.values()

        if execution_id:
            snapshots = [s for s in snapshots if s.metadata.execution_id == execution_id]

        return [
            {
                "snapshot_id": s.metadata.snapshot_id,
                "execution_id": s.metadata.execution_id,
                "created_at": s.metadata.created_at.isoformat(),
                "size_mb": s.metadata.size_bytes / 1024 / 1024,
            }
            for s in list(snapshots)[:limit]
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# PURPLE TEAM FEEDBACK ENDPOINTS (Phase 3D)
# ============================================================================

@router.post("/purple-team/generate-report")
async def generate_purple_team_report(request: PurpleTeamReportRequest):
    """
    Generate comprehensive Purple Team analysis report.
    
    Analyzes:
    - Red Team attack success rates
    - Blue Team detection rates
    - Detection gaps and severity
    - Recommended defensive measures
    
    Returns: PurpleTeamReport with full analysis
    """
    if not purple_team_engine:
        raise HTTPException(status_code=503, detail="Purple Team engine not initialized")

    try:
        report = purple_team_engine.generate_purple_team_report(
            period_hours=request.period_hours
        )

        return {
            "report_id": report.report_id,
            "generated_at": report.generated_at.isoformat(),
            "period_hours": request.period_hours,
            "red_team_count": report.red_team_count,
            "blue_team_count": report.blue_team_count,
            "red_success_rate": report.red_success_rate,
            "detection_rate": report.detection_rate,
            "detection_accuracy": report.detection_accuracy,
            "identified_gaps": len(report.identified_gaps),
            "gap_details": [
                {
                    "gap_id": g.gap_id,
                    "technique_name": g.technique_name,
                    "severity": g.severity.value,
                    "detection_rate": g.detection_rate,
                    "missed_count": g.missed_count,
                }
                for g in report.identified_gaps
            ],
            "recommendations": report.recommendations,
            "executive_summary": report.executive_summary,
        }

    except Exception as e:
        logger.error(f"Error generating Purple Team report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/purple-team/gaps")
async def list_detection_gaps(
    severity: Optional[str] = Query(None),
    limit: int = Query(50),
):
    """List identified detection gaps"""
    if not purple_team_engine:
        raise HTTPException(status_code=503, detail="Purple Team engine not initialized")

    try:
        gaps = list(purple_team_engine.gaps.values())

        if severity:
            gaps = [g for g in gaps if g.severity.value == severity]

        return [
            {
                "gap_id": g.gap_id,
                "technique_id": g.technique_id,
                "technique_name": g.technique_name,
                "severity": g.severity.value,
                "detection_rate": g.detection_rate,
                "missed_count": g.missed_count,
                "last_missed": g.last_missed.isoformat(),
                "recommendations": g.recommendations,
            }
            for g in gaps[:limit]
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/purple-team/gaps/{gap_id}/trends")
async def get_gap_trends(gap_id: str, days: int = Query(30)):
    """Analyze trends for a specific detection gap"""
    if not purple_team_engine:
        raise HTTPException(status_code=503, detail="Purple Team engine not initialized")

    try:
        gap = purple_team_engine.gaps.get(gap_id)
        if not gap:
            raise HTTPException(status_code=404, detail="Gap not found")

        trends = purple_team_engine.get_gap_trends(gap.technique_id, days=days)
        return trends

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/purple-team/recommendations")
async def list_recommendations(
    gap_id: Optional[str] = Query(None),
    priority_min: int = Query(1, ge=1, le=10),
):
    """List recommended defensive measures"""
    if not purple_team_engine:
        raise HTTPException(status_code=503, detail="Purple Team engine not initialized")

    try:
        recommendations = list(purple_team_engine.recommendations.values())

        if gap_id:
            recommendations = [
                r for r in recommendations if gap_id in r.affected_gap_ids
            ]

        recommendations = [
            r for r in recommendations if r.priority >= priority_min
        ]

        return [
            {
                "recommendation_id": r.recommendation_id,
                "title": r.title,
                "description": r.description,
                "priority": r.priority,
                "implementation_effort": r.implementation_effort,
                "coverage_increase": r.estimated_coverage_increase,
                "affected_gaps": len(r.affected_gap_ids),
                "steps": r.implementation_steps,
            }
            for r in recommendations
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# HEALTH & STATUS ENDPOINTS
# ============================================================================

@router.get("/status")
async def intelligence_status():
    """Get status of all intelligence engines"""
    return {
        "demasking_active": demasking_engine is not None,
        "translation_active": translation_engine is not None,
        "digital_twin_active": digital_twin_engine is not None,
        "purple_team_active": purple_team_engine is not None,
        "timestamp": datetime.utcnow().isoformat(),
    }
