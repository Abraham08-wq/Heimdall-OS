"""
device.py — Pydantic schemas for the Device model.

These schemas are the contract between the FastAPI backend and the frontend.
They must stay in sync with:
  - backend/app/models/models.py  (Device ORM model)
  - frontend/src/lib/api.ts       (Device TypeScript interface)
"""
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


# ── Base (shared read/create fields) ─────────────────────────────────────────
class DeviceBase(BaseModel):
    name: str = Field(..., description="Friendly display name")
    hostname: Optional[str] = Field(None, description="FQDN or short hostname")
    ip: Optional[str] = Field(None, description="Primary IPv4/IPv6 address")
    mac: Optional[str] = Field(None, description="MAC address")

    # Categorisation
    type: Optional[str] = Field(None, description="Server | Workstation | Network | IoT | Mobile | OT/ICS | Cloud")
    os: Optional[str] = Field(None, description="OS name + version e.g. 'Ubuntu 22.04 LTS'")
    department: Optional[str] = Field(None, description="Owning department e.g. 'Finance'")
    tags: Optional[List[str]] = Field(None, description="Free-form labels e.g. ['critical', 'pci-scope']")

    # Posture
    risk_score: Optional[int] = Field(0, description="0–100 composite risk score")
    status: Optional[str] = Field("online", description="online | offline | quarantined")

    # Discovery data
    ports: Optional[List[int]] = Field(None, description="Open ports e.g. [22, 80, 443]")
    services: Optional[List[str]] = Field(None, description="Detected services e.g. ['sshd 8.9', 'nginx 1.23']")
    cves: Optional[List[str]] = Field(None, description="Known CVEs e.g. ['CVE-2023-38408']")

    # Geo
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accuracy_radius: Optional[float] = None


# ── Create (inbound from frontend / OmniProbe) ────────────────────────────────
class DeviceCreate(DeviceBase):
    owner_id: Optional[UUID] = None


# ── Update (PATCH — all fields optional) ─────────────────────────────────────
class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    hostname: Optional[str] = None
    ip: Optional[str] = None
    mac: Optional[str] = None
    type: Optional[str] = None
    os: Optional[str] = None
    department: Optional[str] = None
    tags: Optional[List[str]] = None
    risk_score: Optional[int] = None
    status: Optional[str] = None
    ports: Optional[List[int]] = None
    services: Optional[List[str]] = None
    cves: Optional[List[str]] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accuracy_radius: Optional[float] = None
    active_trace: Optional[bool] = None
    owner_id: Optional[UUID] = None


# ── Read (outbound to frontend) ───────────────────────────────────────────────
class Device(DeviceBase):
    id: UUID
    tenant_id: Optional[UUID] = None
    owner_id: Optional[UUID] = None
    active_trace: bool = False
    last_seen: datetime
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Location-only update (GPS pings from mobile agents) ──────────────────────
class DeviceLocationUpdate(BaseModel):
    latitude: float
    longitude: float
    accuracy_radius: Optional[float] = 10.0
