"""
devices.py — Device CRUD endpoint.

Devices are separated by type (Server, Workstation, Network, IoT, Mobile, OT/ICS, Cloud).
All mutations are reflected in both PostgreSQL and the Neo4j graph for unified telemetry.

ADDED: organization support, enrollment-token issuance for the sensor agent
(see app/routers/sensor_router.py for the agent's own side of that flow), and
the human-triggered command queue that BlueSOC's action buttons (Isolate,
etc.) write to. Everything below in this docstring's original scope is
unchanged from before; new endpoints are clearly marked "ADDED".
"""
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from uuid import UUID

from app.api import deps
from app.models.models import Device, Organization, DeviceCommand
from app.schemas import device as device_schema
from app.schemas import agent_schema
from app.infrastructure.graph import graph_db  # ← top-level import (prevents NameError)
from app.infrastructure.cache.redis_manager import redis_cache

router = APIRouter()

# ADDED: a second router for Organizations, included separately in api.py at
# its own prefix -- kept in this file since it's the same human-authenticated
# device-management surface, not a new module.
organizations_router = APIRouter()

ENROLLMENT_TOKEN_TTL_SECONDS = 24 * 3600


# ── List / Filter ──────────────────────────────────────────────────────────────

@router.get("/", response_model=List[device_schema.Device])
def read_devices(
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_active_user),
    skip: int = 0,
    limit: int = 200,
    type: Optional[str] = None,       # ?type=Server | Workstation | Network | IoT | Mobile | OT/ICS | Cloud
    status: Optional[str] = None,     # ?status=online | offline | quarantined
    risk_min: Optional[int] = None,   # ?risk_min=80
    department: Optional[str] = None, # ?department=Finance
    tag: Optional[str] = None,        # ?tag=critical (JSONB contains check)
    organization_id: Optional[UUID] = None,  # ADDED: ?organization_id=... to scope to one client org
) -> Any:
    """
    List devices with optional filters.  Devices are separated by type for clean
    per-category monitoring of logs and data.

    Query params:
        type        — exact match on device type (case-sensitive, matches Enum values)
        status      — online | offline | quarantined
        risk_min    — return only devices with risk_score >= risk_min
        department  — filter by owning department
        tag         — return devices that carry this tag in their JSONB tags array
        organization_id — ADDED: return only devices belonging to this organization
    """
    q = db.query(Device)

    if type:
        q = q.filter(Device.type == type)
    if status:
        q = q.filter(Device.status == status)
    if risk_min is not None:
        q = q.filter(Device.risk_score >= risk_min)
    if department:
        q = q.filter(Device.department == department)
    if tag:
        # PostgreSQL JSONB contains operator
        q = q.filter(Device.tags.contains([tag]))
    if organization_id is not None:
        q = q.filter(Device.organization_id == organization_id)

    devices = q.order_by(Device.last_seen.desc()).offset(skip).limit(limit).all()
    return devices


# ── Register (manual or OmniProbe discovery) ──────────────────────────────────

@router.post("/", response_model=device_schema.Device)
def create_device(
    *,
    db: Session = Depends(deps.get_db),
    device_in: device_schema.DeviceCreate,
    current_user=Depends(deps.get_current_active_user),
) -> Any:
    """
    Register a new device.
    Called manually from the Device Registry UI or automatically by OmniProbe
    after a network scan completes.
    """
    device = Device(
        name=device_in.name,
        hostname=device_in.hostname or device_in.name,
        ip=device_in.ip,
        mac=device_in.mac,
        type=device_in.type,
        os=device_in.os,
        department=device_in.department,
        tags=device_in.tags,
        risk_score=device_in.risk_score or 0,
        status=device_in.status or "online",
        ports=device_in.ports,
        services=device_in.services,
        cves=device_in.cves,
        latitude=device_in.latitude,
        longitude=device_in.longitude,
        accuracy_radius=device_in.accuracy_radius,
        owner_id=device_in.owner_id,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


# ── Read Single ────────────────────────────────────────────────────────────────

@router.get("/{device_id}", response_model=device_schema.Device)
def read_device(
    *,
    db: Session = Depends(deps.get_db),
    device_id: UUID,
    current_user=Depends(deps.get_current_active_user),
) -> Any:
    """Get device by ID."""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


# ── Update ────────────────────────────────────────────────────────────────────

@router.put("/{device_id}", response_model=device_schema.Device)
async def update_device(
    *,
    db: Session = Depends(deps.get_db),
    device_id: UUID,
    device_in: device_schema.DeviceUpdate,
    current_user=Depends(deps.get_current_active_user),
) -> Any:
    """
    Update device metadata.  All fields are optional — only provided fields are changed.
    If active_trace is updated, the change is also propagated to the Neo4j graph.
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Apply all optional fields
    update_fields = [
        "name", "hostname", "ip", "mac", "type", "os",
        "department", "tags", "risk_score", "status",
        "ports", "services", "cves",
        "latitude", "longitude", "accuracy_radius",
        "owner_id",
    ]
    for field in update_fields:
        value = getattr(device_in, field, None)
        if value is not None:
            setattr(device, field, value)

    # active_trace — also sync to Neo4j
    if device_in.active_trace is not None:
        device.active_trace = device_in.active_trace
        try:
            await graph_db.execute_query(
                "MERGE (d:Device:Entity {id: $device_id}) SET d.active_trace = $active_trace",
                {"device_id": str(device_id), "active_trace": device_in.active_trace},
            )
        except Exception as e:
            # Non-fatal: Postgres is source of truth; graph sync is best-effort
            import logging
            logging.getLogger(__name__).warning(f"Graph active_trace sync failed: {e}")

    db.commit()
    db.refresh(device)
    return device


# ── GPS Update ────────────────────────────────────────────────────────────────

@router.post("/{device_id}/gps-update", response_model=device_schema.Device)
async def update_device_location(
    *,
    db: Session = Depends(deps.get_db),
    device_id: UUID,
    location_in: device_schema.DeviceLocationUpdate,
    background_tasks: BackgroundTasks,
    current_user=Depends(deps.get_current_active_user),
) -> Any:
    """
    Update device GPS location.
    Propagates to Neo4j graph and triggers a geofence check in the background.
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    device.latitude = location_in.latitude
    device.longitude = location_in.longitude
    device.accuracy_radius = location_in.accuracy_radius

    # Sync to Neo4j graph
    try:
        await graph_db.execute_query(
            """
            MERGE (d:Device:Entity {id: $device_id})
            SET d.latitude = $lat, d.longitude = $long
            MERGE (l:Location {lat: $lat, long: $long})
            MERGE (d)-[:LOCATED_AT]->(l)
            """,
            {"device_id": str(device_id), "lat": location_in.latitude, "long": location_in.longitude},
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Graph GPS sync failed: {e}")

    # Geofence check — runs asynchronously, doesn't block the response
    from app.services.spatial import check_geofence
    background_tasks.add_task(check_geofence, db, device.id, location_in.latitude, location_in.longitude)

    db.commit()
    db.refresh(device)
    return device


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{device_id}", status_code=204)
def delete_device(
    *,
    db: Session = Depends(deps.get_db),
    device_id: UUID,
    current_user=Depends(deps.get_current_active_user),
) -> None:
    """
    Deregister a device.  Admin/operator only.
    """
    if current_user.role not in ("admin", "operator"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    db.delete(device)
    db.commit()


# ══════════════════════════════════════════════════════════════════════════════
# ADDED — Sensor agent enrollment tokens (human-authenticated side)
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/enrollment-tokens", response_model=agent_schema.EnrollmentTokenResponse)
async def create_enrollment_token(
    *,
    request: agent_schema.EnrollmentTokenRequest,
    current_user=Depends(deps.get_current_active_user),
) -> Any:
    """
    Issue a one-time enrollment token to hand to whoever is installing the
    sensor agent on a device or in a client's server room -- AFTER the legal
    monitoring agreement is in place. The token is single-use and expires in
    24h if never redeemed.

    Admin/operator only, matching the same permission bar as deleting a device.
    """
    if current_user.role not in ("admin", "operator"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    token = secrets.token_urlsafe(24)
    payload = {
        # Attach the enrolling device to the issuing operator's own tenant, so
        # it belongs to the right client org and shows up under their scope.
        "tenant_id": str(current_user.tenant_id) if getattr(current_user, "tenant_id", None) else None,
        "organization_id": str(request.organization_id) if request.organization_id else None,
        "deployment_mode": request.deployment_mode,
        "device_name_hint": request.device_name_hint,
    }
    key = f"sensor:enrollment:{token}"
    # redis_cache.redis_client is redis.asyncio — the write must be awaited, or
    # the token is never actually stored (and enrollment later fails).
    await redis_cache.redis_client.setex(key, ENROLLMENT_TOKEN_TTL_SECONDS, json.dumps(payload))

    return agent_schema.EnrollmentTokenResponse(
        enrollment_token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=ENROLLMENT_TOKEN_TTL_SECONDS),
    )


# ══════════════════════════════════════════════════════════════════════════════
# ADDED — Command queue (BlueSOC action buttons write here; the agent, via
# sensor_router.py, is the only thing that ever reads/executes from it)
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/{device_id}/command", response_model=agent_schema.DeviceCommandOut)
def queue_device_command(
    *,
    db: Session = Depends(deps.get_db),
    device_id: UUID,
    request: agent_schema.QueueCommandRequest,
    current_user=Depends(deps.get_current_active_user),
) -> Any:
    """
    Queue a command for the device's sensor agent to execute on its next
    heartbeat. This is the ONLY way a command reaches a device -- the agent
    never acts without a human having clicked something that calls this.

    Admin/operator only: this is the same trust boundary as isolating or
    deleting a device, since 'isolate' is exactly the kind of action this
    queues.
    """
    if current_user.role not in ("admin", "operator"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if not device.agent_secret_hash:
        raise HTTPException(
            status_code=409,
            detail="This device has no sensor agent enrolled -- there is nothing to deliver this command to.",
        )

    command = DeviceCommand(
        device_id=device_id,
        action=request.action,
        params=request.params,
        status="pending",
        issued_by=getattr(current_user, "id", None),
    )
    db.add(command)
    db.commit()
    db.refresh(command)
    return command


@router.get("/{device_id}/commands", response_model=List[agent_schema.DeviceCommandOut])
def list_device_commands(
    *,
    db: Session = Depends(deps.get_db),
    device_id: UUID,
    current_user=Depends(deps.get_current_active_user),
    limit: int = 50,
) -> Any:
    """Command history for a device -- what was ever queued, delivered, and its result."""
    commands = (
        db.query(DeviceCommand)
        .filter(DeviceCommand.device_id == device_id)
        .order_by(DeviceCommand.created_at.desc())
        .limit(limit)
        .all()
    )
    return commands


# ══════════════════════════════════════════════════════════════════════════════
# ADDED — Organizations (separate router; include at its own prefix in api.py)
# ══════════════════════════════════════════════════════════════════════════════

@organizations_router.get("/", response_model=List[agent_schema.Organization])
def list_organizations(
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_active_user),
) -> Any:
    orgs = db.query(Organization).order_by(Organization.name.asc()).all()
    # device_count is computed here, not stored, so it's never stale.
    out = []
    for org in orgs:
        count = db.query(Device).filter(Device.organization_id == org.id).count()
        item = agent_schema.Organization.model_validate(org)
        item.device_count = count
        out.append(item)
    return out


@organizations_router.post("/", response_model=agent_schema.Organization)
def create_organization(
    *,
    db: Session = Depends(deps.get_db),
    org_in: agent_schema.OrganizationCreate,
    current_user=Depends(deps.get_current_active_user),
) -> Any:
    if current_user.role not in ("admin", "operator"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    org = Organization(**org_in.model_dump())
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@organizations_router.get("/{organization_id}", response_model=agent_schema.Organization)
def read_organization(
    *,
    db: Session = Depends(deps.get_db),
    organization_id: UUID,
    current_user=Depends(deps.get_current_active_user),
) -> Any:
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    count = db.query(Device).filter(Device.organization_id == organization_id).count()
    item = agent_schema.Organization.model_validate(org)
    item.device_count = count
    return item