"""
organization_router.py — Endpoints the ORGANIZATION AGENT itself calls
(the server/network-level install, as opposed to sensor_router.py's
per-device agent). Same design as sensor_router.py: agent-authenticated
(a per-organization secret) or token-gated for the one-time enrollment
step -- NEVER human-JWT-authenticated. Human-facing organization
management (create, list, queue a command) lives in
app/modules/misc/endpoints/organizations.py.

Design constraint (same as the device agent): the org agent never decides
to do anything on its own. It only reports status, executes the ONE
command it's handed on a heartbeat, then reports back.
"""
import json
import secrets
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.api.agent_deps import get_organization_from_agent_auth, hash_agent_secret
from app.models.models import Organization, OrganizationCommand
from app.schemas import agent_schema
from app.infrastructure.cache.redis_manager import redis_cache

router = APIRouter(prefix="/organization-agent", tags=["Organization Agent"])

ORG_ENROLLMENT_TOKEN_TTL_SECONDS = 24 * 3600


def _org_enrollment_key(token: str) -> str:
    return f"organization:enrollment:{token}"


# ── Step 1: agent enrolls (no human auth -- gated by the one-time token) ────

@router.post("/enroll", response_model=agent_schema.OrgAgentEnrollResponse)
def enroll_organization_agent(
    *,
    db: Session = Depends(deps.get_db),
    request: agent_schema.OrgAgentEnrollRequest,
) -> Any:
    """
    Exchanges a one-time enrollment token (issued by a human operator via
    POST /organizations/enrollment-tokens) for a lasting organization
    identity + secret. Sole gate is the enrollment token, same as device
    enrollment -- keep its distribution controlled.
    """
    key = _org_enrollment_key(request.enrollment_token)
    raw = redis_cache.redis_client.get(key)
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Enrollment token invalid, expired, or already used.")

    payload = json.loads(raw)
    redis_cache.redis_client.delete(key)  # single-use: burn it immediately

    org = Organization(
        name=payload.get("organization_name_hint") or request.hostname or "Unnamed organization",
        tenant_id=payload.get("tenant_id"),
        deployment_mode=payload.get("deployment_mode", "gateway"),
        status="online",
    )

    agent_secret = secrets.token_urlsafe(32)
    org.agent_secret_hash = hash_agent_secret(agent_secret)
    org.agent_enrolled_at = datetime.now(timezone.utc)
    org.last_heartbeat = datetime.now(timezone.utc)

    db.add(org)
    db.commit()
    db.refresh(org)

    return agent_schema.OrgAgentEnrollResponse(
        organization_id=org.id,
        agent_secret=agent_secret,  # shown exactly once
        heartbeat_interval_seconds=60,
    )


# ── Step 2: agent heartbeats, may receive one pending command ───────────────

@router.post("/{organization_id}/heartbeat", response_model=agent_schema.OrgHeartbeatResponse)
def organization_agent_heartbeat(
    *,
    db: Session = Depends(deps.get_db),
    organization_id: UUID,
    request: agent_schema.OrgHeartbeatRequest,
    organization: Organization = Depends(get_organization_from_agent_auth),
) -> Any:
    if organization.id != organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization/credential mismatch.")

    organization.status = request.status
    organization.last_heartbeat = datetime.now(timezone.utc)
    db.commit()

    pending = (
        db.query(OrganizationCommand)
        .filter(OrganizationCommand.organization_id == organization_id, OrganizationCommand.status == "pending")
        .order_by(OrganizationCommand.created_at.asc())
        .first()
    )

    command_out = None
    if pending:
        pending.status = "delivered"
        pending.delivered_at = datetime.now(timezone.utc)
        db.commit()
        command_out = agent_schema.PendingOrgCommand(
            command_id=pending.id, action=pending.action, params=pending.params,
        )

    return agent_schema.OrgHeartbeatResponse(acknowledged=True, next_heartbeat_seconds=60, command=command_out)


# ── Step 3: agent reports the result of the one command it was given ───────

@router.post("/{organization_id}/commands/{command_id}/result")
def report_organization_command_result(
    *,
    db: Session = Depends(deps.get_db),
    organization_id: UUID,
    command_id: UUID,
    request: agent_schema.OrgCommandResultRequest,
    organization: Organization = Depends(get_organization_from_agent_auth),
) -> Any:
    command = (
        db.query(OrganizationCommand)
        .filter(OrganizationCommand.id == command_id, OrganizationCommand.organization_id == organization_id)
        .first()
    )
    if not command:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Command not found for this organization.")
    if command.status not in ("delivered", "pending"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"Command already in terminal state: {command.status}")

    command.status = request.status
    command.result = request.result
    command.completed_at = datetime.now(timezone.utc)
    db.commit()

    return {"command_id": str(command_id), "status": command.status}