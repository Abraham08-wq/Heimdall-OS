"""
sensor_router.py — Endpoints the SENSOR AGENT itself calls.

Everything in this file is agent-authenticated (a per-device secret) or
token-gated for the one-time enrollment step -- NEVER human-JWT-authenticated.
Human-facing device management (list, queue a command, view command history)
lives in app/modules/misc/endpoints/devices.py, unchanged in spirit from what
already exists there.

Design constraint (explicit, from the product requirement): the agent never
decides to do anything on its own. It only ever reports status, and executes
the ONE command it's handed on a heartbeat, then reports back. All of the
actual decision-making happens in the dashboard, by a human.
"""
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.api.agent_deps import get_device_from_agent_auth, hash_agent_secret
from app.models.models import Device, DeviceCommand
from app.schemas import agent_schema
from app.infrastructure.cache.redis_manager import redis_cache

router = APIRouter(prefix="/sensor", tags=["Sensor Agent"])

ENROLLMENT_TOKEN_TTL_SECONDS = 24 * 3600  # single-use, expires if never redeemed


def _enrollment_key(token: str) -> str:
    return f"sensor:enrollment:{token}"


# ── Step 0 (human-authenticated, from your dashboard/admin flow) ────────────
# NOTE: this endpoint is intentionally ALSO exposed in devices.py under
# /devices/enrollment-tokens for discoverability alongside other device
# management actions -- both call the same logic. Pick one location; this
# duplication note is here so you don't end up with two divergent copies.


# ── Step 1: agent enrolls (no human auth -- gated by the one-time token) ────

@router.post("/enroll", response_model=agent_schema.AgentEnrollResponse)
async def enroll_agent(
    *,
    db: Session = Depends(deps.get_db),
    request: agent_schema.AgentEnrollRequest,
) -> Any:
    """
    Exchanges a one-time enrollment token (issued by a human operator after
    the legal agreement is signed) for a lasting device identity + secret.

    This is the ONLY endpoint the agent calls without already having a
    device-specific credential -- by design, the enrollment token is the sole
    gate here, so keep its distribution controlled (it's shown once to
    whoever issued it, and is single-use / time-limited).
    """
    key = _enrollment_key(request.enrollment_token)
    # redis_cache.redis_client is redis.asyncio — every call must be awaited.
    raw = await redis_cache.redis_client.get(key)
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Enrollment token invalid, expired, or already used.")

    payload = json.loads(raw)
    await redis_cache.redis_client.delete(key)  # single-use: burn it immediately, before creating anything

    device = Device(
        name=payload.get("device_name_hint") or request.hostname or "Unnamed device",
        hostname=request.hostname,
        ip=request.ip,
        os=request.os,
        type=payload.get("device_type") or "Server",
        status="online",
        tenant_id=payload.get("tenant_id"),
        organization_id=payload.get("organization_id"),
        deployment_mode=payload.get("deployment_mode", "endpoint"),
    )

    agent_secret = secrets.token_urlsafe(32)
    device.agent_secret_hash = hash_agent_secret(agent_secret)
    device.agent_enrolled_at = datetime.now(timezone.utc)
    device.last_heartbeat = datetime.now(timezone.utc)

    db.add(device)
    db.commit()
    db.refresh(device)

    return agent_schema.AgentEnrollResponse(
        device_id=device.id,
        agent_secret=agent_secret,  # shown exactly once -- only the hash is ever stored
        heartbeat_interval_seconds=60,
    )


# ── Step 2: agent heartbeats, may receive one pending command ───────────────

@router.post("/{device_id}/heartbeat", response_model=agent_schema.HeartbeatResponse)
def agent_heartbeat(
    *,
    db: Session = Depends(deps.get_db),
    device_id: UUID,
    request: agent_schema.HeartbeatRequest,
    device: Device = Depends(get_device_from_agent_auth),
) -> Any:
    """
    Called periodically by the agent. Updates presence/status, and hands back
    at most one pending command for the agent to execute locally -- never more
    than one per heartbeat, so the agent's execution model stays simple and
    every action is individually auditable via device_commands.
    """
    if device.id != device_id:
        # get_device_from_agent_auth already validated the secret against
        # `device_id` from the path, so this can only happen from a coding
        # error, not a real client -- kept as a defensive check.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Device/credential mismatch.")

    device.status = request.status
    device.last_heartbeat = datetime.now(timezone.utc)
    db.commit()

    pending = (
        db.query(DeviceCommand)
        .filter(DeviceCommand.device_id == device_id, DeviceCommand.status == "pending")
        .order_by(DeviceCommand.created_at.asc())
        .first()
    )

    command_out = None
    if pending:
        pending.status = "delivered"
        pending.delivered_at = datetime.now(timezone.utc)
        db.commit()
        command_out = agent_schema.PendingCommand(
            command_id=pending.id, action=pending.action, params=pending.params,
        )

    return agent_schema.HeartbeatResponse(acknowledged=True, next_heartbeat_seconds=60, command=command_out)


# ── Step 3: agent reports the result of the one command it was given ───────

@router.post("/{device_id}/commands/{command_id}/result")
def report_command_result(
    *,
    db: Session = Depends(deps.get_db),
    device_id: UUID,
    command_id: UUID,
    request: agent_schema.CommandResultRequest,
    device: Device = Depends(get_device_from_agent_auth),
) -> Any:
    command = (
        db.query(DeviceCommand)
        .filter(DeviceCommand.id == command_id, DeviceCommand.device_id == device_id)
        .first()
    )
    if not command:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Command not found for this device.")
    if command.status not in ("delivered", "pending"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"Command already in terminal state: {command.status}")

    command.status = request.status
    command.result = request.result
    command.completed_at = datetime.now(timezone.utc)
    db.commit()

    return {"command_id": str(command_id), "status": command.status}


# ── ADDED: mobile-only. Registers/updates the FCM token used to wake the app ─
# for prompt command delivery (see app/services/push_service.py). Desktop/
# server agents never call this -- they're always reachable via their own
# process's heartbeat loop, with no equivalent "OS suspended me" problem.

@router.post("/{device_id}/push-token")
def register_push_token(
    *,
    db: Session = Depends(deps.get_db),
    device_id: UUID,
    request: agent_schema.PushTokenRequest,
    device: Device = Depends(get_device_from_agent_auth),
) -> Any:
    """
    Called by the mobile app after enrollment, and again whenever Firebase
    rotates its token (this happens periodically and after reinstalls -- the
    app should re-register on every app start, not just once, since a stale
    token silently fails to deliver pushes with no error visible to the user).
    """
    device.push_token = request.push_token
    device.push_platform = request.platform
    db.commit()
    return {"acknowledged": True}