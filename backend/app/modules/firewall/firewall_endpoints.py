"""
firewall_endpoints.py — ProjectXY AI Firewall REST Endpoints
=============================================================
Exposes the LLM Firewall as a FastAPI router.

Routes:
  POST /api/v1/firewall/check          — Run a prompt through all defence vectors
  POST /api/v1/firewall/proxy          — Full LLM proxy (check then forward)
  GET  /api/v1/firewall/stats          — Live threat statistics
  GET  /api/v1/firewall/threats/recent — Last 50 blocked threats
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from app.modules.firewall.llm_firewall import get_firewall, LLMFirewall, FirewallVerdict
from app.api.deps import get_current_active_user

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response Schemas
# ---------------------------------------------------------------------------

class FirewallCheckRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=8192, description="The user prompt to inspect.")
    tenant_id: str = Field(default="default", description="Multi-tenant identifier.")
    entity_id: str = Field(default="anonymous", description="User or session entity ID.")
    target_model: str = Field(default="unknown", description="Target LLM being protected.")


class FirewallProxyRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=8192)
    tenant_id: str = "default"
    entity_id: str = "anonymous"
    # LLM forwarding config (only used if firewall passes)
    forward_to: Optional[str] = Field(None, description="URL to forward the (scrubbed) prompt to.")
    forward_headers: Optional[Dict[str, str]] = None
    forward_body_template: Optional[Dict[str, Any]] = None


class VerdictResponse(BaseModel):
    action: str
    threat_score: float
    reasons: List[str]
    pii_types_detected: List[str]
    semantic_similarity: float
    matched_threat_category: Optional[str]
    latency_ms: float
    prompt_hash: str
    scrubbed_prompt: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/check",
    response_model=VerdictResponse,
    summary="Run prompt through AI Firewall",
    description="""
Executes all three defensive vectors simultaneously:

1. **Semantic Anomaly Detection** — pgvector cosine similarity against real threat corpus
2. **PII/DLP Scrubbing** — NER-based masking of IDs, cards, phone numbers
3. **Malicious Payload Detection** — Regex + Base64/Hex obfuscation scanning

Returns a **FirewallVerdict** with action: `PASS | BLOCK | SCRUB_AND_PASS`.
""",
    tags=["AI Firewall — Sovereign Guardrail"],
)
async def firewall_check(
    payload: FirewallCheckRequest,
    firewall: LLMFirewall = Depends(get_firewall),
    current_user=Depends(get_current_active_user),
):
    verdict: FirewallVerdict = await firewall.check(
        prompt=payload.prompt,
        tenant_id=payload.tenant_id,
        entity_id=payload.entity_id,
        target_model=payload.target_model,
    )
    return VerdictResponse(
        action=verdict.action,
        threat_score=verdict.threat_score,
        reasons=verdict.reasons,
        pii_types_detected=verdict.pii_types_detected,
        semantic_similarity=verdict.semantic_similarity,
        matched_threat_category=verdict.matched_threat_category,
        latency_ms=verdict.latency_ms,
        prompt_hash=verdict.prompt_hash,
        scrubbed_prompt=verdict.scrubbed_prompt if verdict.action == "SCRUB_AND_PASS" else None,
    )


@router.post(
    "/proxy",
    summary="Firewall-Protected LLM Proxy",
    description="""
Full LLM proxy endpoint. The prompt is first screened by the firewall.

- **BLOCK**: Returns 403 immediately.
- **SCRUB_AND_PASS**: Forwards the de-identified version to the target model.
- **PASS**: Forwards the original prompt to the target model.
""",
    tags=["AI Firewall — Sovereign Guardrail"],
)
async def firewall_proxy(
    payload: FirewallProxyRequest,
    firewall: LLMFirewall = Depends(get_firewall),
    current_user=Depends(get_current_active_user),
):
    verdict: FirewallVerdict = await firewall.check(
        prompt=payload.prompt,
        tenant_id=payload.tenant_id,
        entity_id=payload.entity_id,
    )

    if verdict.action == "BLOCK":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Prompt blocked by ProjectXY AI Firewall",
                "threat_score": verdict.threat_score,
                "reasons": verdict.reasons,
                "prompt_hash": verdict.prompt_hash,
            },
        )

    # Determine effective prompt
    effective_prompt = (
        verdict.scrubbed_prompt
        if verdict.action == "SCRUB_AND_PASS" and verdict.scrubbed_prompt
        else payload.prompt
    )

    # If no forward_to specified, just return the firewall verdict
    if not payload.forward_to:
        return {
            "firewall_verdict": verdict.action,
            "pii_removed": verdict.pii_types_detected,
            "effective_prompt": effective_prompt,
            "threat_score": verdict.threat_score,
            "latency_ms": verdict.latency_ms,
        }

    # Forward the (scrubbed) prompt to the actual LLM endpoint
    import httpx
    try:
        body = payload.forward_body_template or {"prompt": effective_prompt}
        # Inject effective prompt into template if provided
        if payload.forward_body_template:
            body = {k: effective_prompt if v == "{{prompt}}" else v
                    for k, v in payload.forward_body_template.items()}

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                payload.forward_to,
                json=body,
                headers=payload.forward_headers or {},
            )
            llm_response = response.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM upstream error: {exc}")

    return {
        "firewall_verdict": verdict.action,
        "pii_removed": verdict.pii_types_detected,
        "threat_score": verdict.threat_score,
        "firewall_latency_ms": verdict.latency_ms,
        "llm_response": llm_response,
    }


@router.get(
    "/stats",
    summary="Live Firewall Statistics",
    tags=["AI Firewall — Sovereign Guardrail"],
)
async def firewall_stats(
    firewall: LLMFirewall = Depends(get_firewall),
    current_user=Depends(get_current_active_user),
):
    """Returns live threat interception counts from Redis."""
    stats = {
        "status": "operational",
        "config": {
            "block_threshold": firewall._pg_pool is not None,
            "embedding_model": "all-MiniLM-L6-v2",
            "semantic_check_active": firewall._model is not None,
            "pii_nlp_active": firewall._spacy_nlp is not None,
            "kafka_streaming": firewall._kafka_producer is not None,
            "replay_cache_active": firewall._redis is not None,
        },
    }

    if firewall._redis:
        try:
            blocked = await firewall._redis.llen("firewall:blocked_log")
            replay_keys = len(await firewall._redis.keys("firewall:replay:*"))
            stats["redis_metrics"] = {
                "recent_blocks_in_log": blocked,
                "active_replay_blocks": replay_keys,
            }
        except Exception:
            pass

    return stats


# ── OPA Self-Learning Policy Management ─────────────────────────────────────

@router.get(
    "/policy/stats",
    summary="OPA Feedback Engine — Category Block Statistics",
    tags=["AI Firewall — Cognitive Shield L1/L3/L5"],
)
async def opa_policy_stats(
    tenant_id: str = "default",
    current_user=Depends(get_current_active_user),
):
    """Returns category-level block counts from the self-learning OPA engine."""
    from app.core.opa_feedback import opa_feedback
    stats = await opa_feedback.get_policy_stats(tenant_id)
    return {
        "tenant_id": tenant_id,
        "policy_engine": "opa_feedback_v1",
        "category_blocks": stats,
        "total_policies": sum(stats.values()),
    }


@router.delete(
    "/policy/hash/{hash_key}",
    summary="Revoke a false-positive OPA block",
    tags=["AI Firewall — Cognitive Shield L1/L3/L5"],
)
async def revoke_policy_hash(
    hash_key: str,
    current_user=Depends(get_current_active_user),
):
    """Remove a specific hash from the OPA block policy (false positive management)."""
    from app.core.opa_feedback import opa_feedback
    success = await opa_feedback.revoke_hash(hash_key)
    return {"hash": hash_key, "revoked": success}
