"""
devices.py — Device CRUD endpoint.

Devices are separated by type (Server, Workstation, Network, IoT, Mobile, OT/ICS, Cloud).
All mutations are reflected in both PostgreSQL and the Neo4j graph for unified telemetry.
"""
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from uuid import UUID

from app.api import deps
from app.models.models import Device
from app.schemas import device as device_schema
from app.infrastructure.graph import graph_db  # ← top-level import (prevents NameError)

router = APIRouter()


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
