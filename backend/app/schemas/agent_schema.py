"""
agent.py — Pydantic schemas for the sensor agent protocol, Organizations,
and the organization agent protocol.

The sensor agent (installed on a client device or server, after a signed legal
agreement) is a MONITORING AND REMOTE-HANDS-ONLY component. It never decides to
take action on its own. It:
  1. Enrolls once, using a one-time enrollment token you issue after the legal
     agreement is signed, and receives back a long-lived per-device secret.
  2. Heartbeats periodically using that secret, reporting basic status.
  3. On each heartbeat, may receive exactly one pending command (queued by a
     human operator clicking an action in BlueSOC) to execute locally, then
     reports the result back on its next call.

The organization agent follows the exact same protocol, but represents a
server/network-level install protecting a whole Organization rather than a
single Device. A Device may optionally be grouped under an Organization
(organization_id, nullable) -- both still belong directly to a Tenant.

This file is new. It sits alongside backend/app/schemas/device.py and follows
the same style.
"""
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


# ── Tenants (this project's existing "which company/client is this" model —
#    exposed here under friendly "/organizations" URL naming for the
#    dashboard, but operating on the real Tenant class, not a separate one) ──

class TenantCreate(BaseModel):
    name: str
    domain: Optional[str] = None
    subscription_tier: str = "starter"
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    legal_agreement_signed_at: Optional[datetime] = Field(
        None, description="When the legal monitoring agreement was signed. "
                          "Enrollment tokens should generally not be issued before this is set."
    )
    legal_agreement_reference: Optional[str] = Field(
        None, description="Contract ID, document link, or similar reference for audit purposes."
    )
    notes: Optional[str] = None


class Tenant(TenantCreate):
    id: UUID
    is_active: bool = True
    created_at: Optional[datetime] = None
    device_count: Optional[int] = Field(None, description="Populated by the list endpoint; not stored.")

    model_config = {"from_attributes": True}


# ── Enrollment (one-time, human-authenticated) ───────────────────────────────
# Called from your own dashboard/admin flow -- NOT by the agent itself -- to
# generate the enrollment token you then hand to whoever is installing the
# agent on the client's device/server.

class EnrollmentTokenRequest(BaseModel):
    tenant_id: Optional[UUID] = Field(
        None, description="Attach the resulting device to this tenant/client organization. "
                          "Leave unset for a standalone/personal device."
    )
    organization_id: Optional[UUID] = Field(
        None, description="Optionally group the resulting device under this Organization."
    )
    deployment_mode: str = Field(
        "endpoint", description="'endpoint' for a single device, 'gateway' for a server-room "
                                "install that will discover and report on its whole internal network."
    )
    device_name_hint: Optional[str] = Field(None, description="Optional friendly name to pre-fill.")


class EnrollmentTokenResponse(BaseModel):
    enrollment_token: str = Field(..., description="Give this to the person installing the agent. Single-use.")
    expires_at: datetime


# ── Agent-side: enroll (exchanges the one-time token for a lasting secret) ──

class AgentEnrollRequest(BaseModel):
    enrollment_token: str
    hostname: Optional[str] = None
    os: Optional[str] = None
    ip: Optional[str] = None


class AgentEnrollResponse(BaseModel):
    device_id: UUID
    agent_secret: str = Field(..., description="Store this locally (e.g. config file, OS keychain). "
                                               "It is shown ONLY this once and cannot be recovered -- "
                                               "re-enrollment would be required if lost.")
    heartbeat_interval_seconds: int = 60


# ── Agent-side: heartbeat ────────────────────────────────────────────────────

class HeartbeatRequest(BaseModel):
    status: str = Field(
        "online",
        description="online | quarantined -- matches Device's existing status vocabulary "
                    "(device_schema.py). 'offline' is inferred from a missed heartbeat, "
                    "never reported by the agent itself.",
    )
    # Left intentionally minimal for v1 per the "get registration + heartbeat
    # working first, expand later" decision. Extend this model (not a parallel
    # one) when richer telemetry is added, so old and new agents both validate.
    metadata: Optional[Dict[str, Any]] = None


class PendingCommand(BaseModel):
    command_id: UUID
    action: str
    params: Optional[Dict[str, Any]] = None


class HeartbeatResponse(BaseModel):
    acknowledged: bool = True
    next_heartbeat_seconds: int = 60
    command: Optional[PendingCommand] = Field(
        None, description="At most one pending command per heartbeat, by design -- "
                          "keeps the agent's execution model simple and auditable."
    )


class CommandResultRequest(BaseModel):
    status: str = Field(..., description="completed | failed")
    result: Optional[Dict[str, Any]] = None


class PushTokenRequest(BaseModel):
    """Mobile-only. See sensor_router.py's register_push_token endpoint."""
    push_token: str
    platform: str = Field(..., description="ios | android")


# ── Human-side: queuing a command from BlueSOC ───────────────────────────────

class QueueCommandRequest(BaseModel):
    action: str = Field(..., description="e.g. 'isolate', 'unisolate', 'collect_logs'")
    params: Optional[Dict[str, Any]] = None


class DeviceCommandOut(BaseModel):
    id: UUID
    device_id: UUID
    action: str
    params: Optional[Dict[str, Any]] = None
    status: str
    issued_by: Optional[UUID] = None
    result: Optional[Dict[str, Any]] = None
    created_at: datetime
    delivered_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Organizations (standalone, tenant-owned, agent-monitored asset) ─────────
# Mirrors the Device schemas above, but for a server/network-level install
# that protects a whole organization. A Device may optionally be grouped
# under an Organization (see Device.organization_id), but both Organization
# and Device belong directly to a Tenant independently either way.

class OrganizationCreate(BaseModel):
    tenant_id: Optional[UUID] = Field(
        None, description="Tenant this organization is protected under."
    )
    name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    notes: Optional[str] = None
    deployment_mode: str = Field(
        "gateway", description="'gateway' for a server-room install reporting on the whole "
                               "internal network; use 'endpoint' only if this organization "
                               "is being monitored via a single always-on host."
    )


class Organization(OrganizationCreate):
    id: UUID
    owner_id: Optional[UUID] = None
    risk_score: int = 0
    status: str = "online"  # online | offline | quarantined
    agent_enrolled_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    created_at: Optional[datetime] = None
    device_count: Optional[int] = Field(None, description="Populated by the list/read endpoint; not stored.")

    model_config = {"from_attributes": True}


# ── Organization enrollment (one-time, human-authenticated) ─────────────────

class OrgEnrollmentTokenRequest(BaseModel):
    tenant_id: Optional[UUID] = Field(
        None, description="Attach the resulting organization to this tenant. "
                          "Leave unset for a standalone/personal setup."
    )
    deployment_mode: str = Field(
        "gateway", description="'gateway' for a server-room install representing the whole "
                               "organization's network; 'endpoint' if it's really just one host."
    )
    organization_name_hint: Optional[str] = Field(None, description="Optional friendly name to pre-fill.")


class OrgEnrollmentTokenResponse(BaseModel):
    enrollment_token: str = Field(..., description="Give this to whoever is installing the agent. Single-use.")
    expires_at: datetime


# ── Agent-side: enroll (exchanges the one-time token for a lasting secret) ──

class OrgAgentEnrollRequest(BaseModel):
    enrollment_token: str
    hostname: Optional[str] = None
    os: Optional[str] = None
    ip: Optional[str] = None


class OrgAgentEnrollResponse(BaseModel):
    organization_id: UUID
    agent_secret: str = Field(..., description="Store this locally. Shown ONLY this once -- "
                                               "re-enrollment is required if lost.")
    heartbeat_interval_seconds: int = 60


# ── Agent-side: heartbeat ────────────────────────────────────────────────────

class OrgHeartbeatRequest(BaseModel):
    status: str = Field(
        "online",
        description="online | quarantined -- 'offline' is inferred from a missed heartbeat, "
                    "never reported by the agent itself.",
    )
    metadata: Optional[Dict[str, Any]] = None


class PendingOrgCommand(BaseModel):
    command_id: UUID
    action: str
    params: Optional[Dict[str, Any]] = None


class OrgHeartbeatResponse(BaseModel):
    acknowledged: bool = True
    next_heartbeat_seconds: int = 60
    command: Optional[PendingOrgCommand] = Field(
        None, description="At most one pending command per heartbeat, same design as Device."
    )


class OrgCommandResultRequest(BaseModel):
    status: str = Field(..., description="completed | failed")
    result: Optional[Dict[str, Any]] = None


# ── Human-side: queuing a command from BlueSOC ───────────────────────────────

class QueueOrgCommandRequest(BaseModel):
    action: str = Field(..., description="e.g. 'isolate_network', 'collect_logs'")
    params: Optional[Dict[str, Any]] = None


class OrganizationCommandOut(BaseModel):
    id: UUID
    organization_id: UUID
    action: str
    params: Optional[Dict[str, Any]] = None
    status: str
    issued_by: Optional[UUID] = None
    result: Optional[Dict[str, Any]] = None
    created_at: datetime
    delivered_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}