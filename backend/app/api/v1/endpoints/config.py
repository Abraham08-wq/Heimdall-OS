"""
config.py — Dynamic Configuration API Endpoints
Serves all values that were previously hardcoded constants in the frontend.
All values are backed by the config_entries table (seeded via seed.py).
"""
from typing import List, Dict, Any
from enum import Enum
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.models.config_model import ConfigEntry

router = APIRouter()


# ─── Device Types Enum (backend-authoritative) ────────────────────────────────
class DeviceTypeEnum(str, Enum):
    server = "Server"
    workstation = "Workstation"
    network = "Network"
    iot = "IoT"
    mobile = "Mobile"
    ot_ics = "OT/ICS"
    cloud = "Cloud"


@router.get(
    "/device-types",
    response_model=List[Dict[str, Any]],
    summary="Get all device type definitions",
    description="Returns the authoritative list of device types from the backend Enum, enriched with metadata from the config_entries table.",
)
def get_device_types(db: Session = Depends(deps.get_db)):
    """
    Returns device types as a flat list of objects with key, label, and metadata.
    The frontend should never hardcode this list.
    """
    # Merge Enum values with DB metadata (label, icon, color)
    db_entries = {
        e.key: e.to_dict()
        for e in db.query(ConfigEntry).filter(
            ConfigEntry.category == "device_types",
            ConfigEntry.is_active == True,
        ).all()
    }

    result = []
    for member in DeviceTypeEnum:
        db_meta = db_entries.get(member.name, {})
        result.append({
            "key": member.name,
            "label": member.value,
            "icon": db_meta.get("value", {}).get("icon", "Monitor") if db_meta else "Monitor",
            "color": db_meta.get("value", {}).get("color", "sky") if db_meta else "sky",
        })
    return result


@router.get(
    "/device-types/labels",
    response_model=List[str],
    summary="Get device type labels only",
    description="Returns just the label strings. Suitable for simple filter dropdowns.",
)
def get_device_type_labels():
    return [e.value for e in DeviceTypeEnum]


# ─── Simulation Types ─────────────────────────────────────────────────────────
@router.get(
    "/simulation-types",
    response_model=List[Dict[str, Any]],
    summary="Get all SOC simulation scenario types",
    description="Returns simulation types with MITRE ATT&CK mapping and severity levels.",
)
def get_simulation_types(db: Session = Depends(deps.get_db)):
    entries = db.query(ConfigEntry).filter(
        ConfigEntry.category == "simulation_types",
        ConfigEntry.is_active == True,
    ).order_by(ConfigEntry.label).all()

    if not entries:
        # Graceful fallback if not seeded yet
        return [
            {"key": "ransomware_detected",     "label": "Ransomware Detected",     "severity": "CRITICAL", "mitre": "T1486"},
            {"key": "lateral_movement",         "label": "Lateral Movement",         "severity": "HIGH",     "mitre": "T1021"},
            {"key": "credential_dump",          "label": "Credential Dump",          "severity": "HIGH",     "mitre": "T1003"},
            {"key": "c2_beacon",                "label": "C2 Beacon Detected",       "severity": "CRITICAL", "mitre": "T1071"},
            {"key": "data_exfiltration",        "label": "Data Exfiltration",        "severity": "HIGH",     "mitre": "T1041"},
            {"key": "privilege_escalation",     "label": "Privilege Escalation",     "severity": "CRITICAL", "mitre": "T1068"},
            {"key": "supply_chain_compromise",  "label": "Supply Chain Compromise",  "severity": "CRITICAL", "mitre": "T1195"},
        ]

    return [
        {
            "key": e.key,
            "label": e.label,
            "severity": e.value.get("severity", "MEDIUM") if e.value else "MEDIUM",
            "mitre": e.value.get("mitre", "") if e.value else "",
        }
        for e in entries
    ]


# ─── Offensive Tools ──────────────────────────────────────────────────────────
@router.get(
    "/offensive-tools",
    response_model=List[Dict[str, Any]],
    summary="Get all registered offensive tools",
    description="Returns the tools available in the offensive ops workbench.",
)
def get_offensive_tools(db: Session = Depends(deps.get_db)):
    entries = db.query(ConfigEntry).filter(
        ConfigEntry.category == "offensive_tools",
        ConfigEntry.is_active == True,
    ).order_by(ConfigEntry.label).all()

    return [
        {
            "key": e.key,
            "label": e.label,
            "category": e.value.get("category", "Unknown") if e.value else "Unknown",
            "risk": e.value.get("risk", "medium") if e.value else "medium",
        }
        for e in entries
    ]


# ─── SOC Playbooks ────────────────────────────────────────────────────────────
@router.get(
    "/soc-playbooks",
    response_model=List[Dict[str, Any]],
    summary="Get all SOC response playbooks",
    description="Returns structured SOAR playbooks for incident response.",
)
def get_soc_playbooks(db: Session = Depends(deps.get_db)):
    entries = db.query(ConfigEntry).filter(
        ConfigEntry.category == "soc_playbooks",
        ConfigEntry.is_active == True,
    ).order_by(ConfigEntry.label).all()

    return [
        {
            "key": e.key,
            "label": e.label,
            "steps": e.value.get("steps", []) if e.value else [],
            "auto_isolate": e.value.get("auto_isolate", False) if e.value else False,
        }
        for e in entries
    ]


# ─── Full Config Dump (Admin Only) ───────────────────────────────────────────
@router.get(
    "/all",
    response_model=Dict[str, List[Dict[str, Any]]],
    summary="Get all config entries grouped by category (admin only)",
)
def get_all_config(
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_active_user),
):
    if current_user.role not in ("admin", "operator"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    entries = db.query(ConfigEntry).filter(ConfigEntry.is_active == True).all()
    grouped: Dict[str, List] = {}
    for e in entries:
        grouped.setdefault(e.category, []).append(e.to_dict())
    return grouped
