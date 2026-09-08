"""
agent_proxy.py — ProjectXY Cognitive Shield: Layer 2 API
==========================================================
FastAPI router for the Agentic Orchestration Proxy.

Routes:
  POST /api/v1/agent/proxy/evaluate — Evaluate an agent tool call
  POST /api/v1/agent/proxy/session  — Issue a mission-scoped session
  DELETE /api/v1/agent/proxy/session/{agent_id} — Revoke a session
  PUT /api/v1/agent/proxy/session/{agent_id}/phase — Advance mission phase
  GET /api/v1/agent/proxy/sessions  — List active agent sessions
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_active_user
from app.modules.firewall.agent_intent_rbac import AgentIntentRBAC, get_intent_rbac
from app.modules.firewall.agent_session_vault import (
    AgentSessionVault, MissionContext, get_agent_session_vault
)
from app.modules.firewall.compliance_ledger import (
    AgentActionType, ComplianceEvent, compliance_ledger
)

logger = logging.getLogger("projectxy.api.agent_proxy")
router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response Schemas
# ---------------------------------------------------------------------------

class AgentEvaluateRequest(BaseModel):
    agent_id: str = Field(..., description="The AI agent identifier.")
    tenant_id: str = Field(..., description="Tenant scope for the agent.")
    tool_name: str = Field(..., description="The tool or API being invoked.")
    payload: Optional[Dict[str, Any]] = Field(
        default=None, description="Tool invocation payload (for intent classification)."
    )
    explicit_intent: Optional[str] = Field(
        default=None, description="Caller-specified intent: READ|WRITE|EXECUTE|DELETE|ADMIN"
    )
    target_tenant_id: Optional[str] = Field(
        default=None, description="Target resource tenant (for cross-tenant checks)."
    )


class AgentEvaluateResponse(BaseModel):
    allowed: bool
    agent_id: str
    tool_name: str
    intent: str
    resource_class: str
    deny_reason: Optional[str] = None
    mission_phase: Optional[str] = None
    policy_name: Optional[str] = None
    audit_trail: List[str] = []


class IssueSessionRequest(BaseModel):
    agent_id: str = Field(..., description="Unique agent identifier.")
    tenant_id: str = Field(..., description="Tenant scope.")
    role: str = Field(default="operator", description="Agent role: viewer|analyst|operator|admin")
    mission_id: str = Field(..., description="Active mission identifier.")
    mission_phase: str = Field(default="RECON", description="Initial mission phase.")
    mfa_verified: bool = Field(default=False, description="Whether MFA was completed.")
    duration_hours: int = Field(default=8, ge=1, le=24, description="Session duration in hours.")
    overrides: Optional[Dict[str, Any]] = Field(
        default=None, description="Scope overrides (must be subset of role defaults)."
    )


class AdvancePhaseRequest(BaseModel):
    tenant_id: str
    new_phase: str = Field(
        ...,
        description="New mission phase: RECON|EXPLOITATION|POST_EX|CLEANUP"
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "/evaluate",
    response_model=AgentEvaluateResponse,
    summary="Evaluate an agent tool call against Intent RBAC policies",
    tags=["Agentic Orchestration Proxy"],
)
async def evaluate_agent_call(
    request: AgentEvaluateRequest,
    rbac: AgentIntentRBAC = Depends(get_intent_rbac),
    current_user=Depends(get_current_active_user),
) -> AgentEvaluateResponse:
    """
    Evaluate whether an AI agent is permitted to invoke a tool.

    This is the core Layer 2 gateway — all agent-to-tool calls should
    pass through this endpoint before execution.

    Returns 200 with `allowed=true/false`.
    Returns 403 if the caller doesn't have permission to evaluate.
    """
    decision = await rbac.evaluate(
        agent_id=request.agent_id,
        tenant_id=request.tenant_id,
        tool_name=request.tool_name,
        payload=request.payload,
        explicit_intent=request.explicit_intent,
        target_tenant_id=request.target_tenant_id,
    )

    # Record compliance event
    compliance_event = ComplianceEvent(
        tenant_id=request.tenant_id,
        entity_id=request.agent_id,
        agent_id=request.agent_id,
        action_type=(
            AgentActionType.POLICY_DENY if not decision.allowed
            else AgentActionType.TOOL_INVOKE
        ),
        intent_classification=decision.intent,
        tool_name=request.tool_name,
        resource_class=decision.resource_class,
        policy_decision="DENY" if not decision.allowed else "ALLOW",
        policy_name=(
            decision.policy_decision.policy_name
            if decision.policy_decision else None
        ),
        policy_reasons=(
            decision.policy_decision.reasons
            if decision.policy_decision else []
        ),
        mission_id=(
            decision.mission_context.mission_id
            if decision.mission_context else None
        ),
        mission_phase=(
            decision.mission_context.mission_phase
            if decision.mission_context else None
        ),
    )
    try:
        await compliance_ledger.record(compliance_event)
    except Exception as exc:
        logger.error(f"[AGENT_PROXY] Compliance record failed: {exc}")

    if not decision.allowed:
        logger.warning(
            f"[AGENT_PROXY] DENY agent={request.agent_id} "
            f"tool={request.tool_name} reason={decision.deny_reason}"
        )

    return AgentEvaluateResponse(
        allowed=decision.allowed,
        agent_id=decision.agent_id,
        tool_name=decision.tool_name,
        intent=decision.intent,
        resource_class=decision.resource_class,
        deny_reason=decision.deny_reason,
        mission_phase=(
            decision.mission_context.mission_phase if decision.mission_context else None
        ),
        policy_name=(
            decision.policy_decision.policy_name if decision.policy_decision else None
        ),
        audit_trail=decision.audit_trail,
    )


@router.post(
    "/session",
    summary="Issue a mission-scoped agent session",
    tags=["Agentic Orchestration Proxy"],
)
async def issue_agent_session(
    request: IssueSessionRequest,
    vault: AgentSessionVault = Depends(get_agent_session_vault),
    current_user=Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Issue a new mission-scoped session for an AI agent.
    Grants the agent a tool class and intent scope based on role + phase.
    Revokes any existing session for this agent.
    """
    try:
        ctx = await vault.issue_session(
            agent_id=request.agent_id,
            tenant_id=request.tenant_id,
            role=request.role,
            mission_id=request.mission_id,
            mission_phase=request.mission_phase,
            mfa_verified=request.mfa_verified,
            duration_hours=request.duration_hours,
            overrides=request.overrides,
        )

        await compliance_ledger.record(ComplianceEvent(
            tenant_id=request.tenant_id,
            entity_id=request.agent_id,
            agent_id=request.agent_id,
            action_type=AgentActionType.SESSION_ISSUE,
            mission_id=request.mission_id,
            mission_phase=request.mission_phase,
            policy_decision="ALLOW",
        ))

        return {
            "status": "issued",
            "session_token": ctx.session_token,
            "agent_id": ctx.agent_id,
            "mission_id": ctx.mission_id,
            "mission_phase": ctx.mission_phase,
            "allowed_tool_classes": ctx.allowed_tool_classes,
            "allowed_intents": ctx.allowed_intents,
            "expires_at": ctx.expires_at,
            "risk_ceiling": ctx.risk_ceiling,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to issue session: {str(exc)}"
        )


@router.delete(
    "/session/{agent_id}",
    summary="Revoke an agent session",
    tags=["Agentic Orchestration Proxy"],
)
async def revoke_agent_session(
    agent_id: str,
    tenant_id: str,
    vault: AgentSessionVault = Depends(get_agent_session_vault),
    current_user=Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Revoke an active agent session. Adds agent to blocklist."""
    success = await vault.revoke_session(agent_id=agent_id, tenant_id=tenant_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active session found for agent '{agent_id}'."
        )

    await compliance_ledger.record(ComplianceEvent(
        tenant_id=tenant_id,
        entity_id=agent_id,
        agent_id=agent_id,
        action_type=AgentActionType.SESSION_REVOKE,
        policy_decision="ALLOW",
    ))

    return {"status": "revoked", "agent_id": agent_id}


@router.put(
    "/session/{agent_id}/phase",
    summary="Advance agent mission phase",
    tags=["Agentic Orchestration Proxy"],
)
async def advance_mission_phase(
    agent_id: str,
    request: AdvancePhaseRequest,
    vault: AgentSessionVault = Depends(get_agent_session_vault),
    current_user=Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Advance the mission phase for an agent.
    Re-scopes the agent's tool class permissions to the new phase.
    """
    valid_phases = {"RECON", "EXPLOITATION", "POST_EX", "CLEANUP"}
    if request.new_phase not in valid_phases:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid phase '{request.new_phase}'. Valid: {valid_phases}"
        )

    ctx = await vault.advance_mission_phase(
        agent_id=agent_id,
        tenant_id=request.tenant_id,
        new_phase=request.new_phase,
    )

    if not ctx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active session for agent '{agent_id}'."
        )

    await compliance_ledger.record(ComplianceEvent(
        tenant_id=request.tenant_id,
        entity_id=agent_id,
        agent_id=agent_id,
        action_type=AgentActionType.PHASE_ADVANCE,
        mission_phase=request.new_phase,
        policy_decision="ALLOW",
    ))

    return {
        "status": "phase_advanced",
        "agent_id": agent_id,
        "new_phase": ctx.mission_phase,
        "allowed_tool_classes": ctx.allowed_tool_classes,
    }


@router.get(
    "/sessions",
    summary="List all active agent sessions for the current tenant",
    tags=["Agentic Orchestration Proxy"],
)
async def list_active_sessions(
    tenant_id: str,
    vault: AgentSessionVault = Depends(get_agent_session_vault),
    current_user=Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Returns all active mission-scoped agent sessions for a tenant."""
    sessions = await vault.list_active_agents(tenant_id)
    return {
        "tenant_id": tenant_id,
        "active_sessions": sessions,
        "count": len(sessions),
    }
