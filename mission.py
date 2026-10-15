from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class MissionPhase(str, Enum):
    IDLE = "IDLE"
    RECON = "RECON"       # Phase I
    ANALYZE = "ANALYZE"   # Phase II
    EXECUTE = "EXECUTE"   # Phase III
    PERSIST = "PERSIST"   # Phase IV
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    # ADDED: mission_router.py's abort_mission() checks for this value (and
    # sets it, via unified_chain.py's new abort_mission() method below), but it
    # never existed as a valid phase — every abort attempt would have compared
    # against a value the enum couldn't actually reach.
    ABORTED = "ABORTED"

class ExecutionStrategy(str, Enum):
    THROTTLE = "ADAPTIVE_THROTTLING"
    DECEPTION = "SHADOW_SANDBOX"
    LOCKDOWN = "INFRASTRUCTURE_LOCKDOWN"
    SIMULATE = "EXPLOIT_SIMULATION"

# --- Dossier Schemas ---

class DemaskingResult(BaseModel):
    fingerprint: Optional[str] = None
    status: str

class EnrichmentResult(BaseModel):
    # This can be fleshed out with the actual data structures from the enrichment service
    shodan: Optional[Dict[str, Any]] = None
    censys: Optional[Dict[str, Any]] = None
    intelx: Optional[List[Dict[str, Any]]] = None
    the_blacklight: Optional[Dict[str, Any]] = None
    babelx: Optional[List[Dict[str, Any]]] = None

class Dossier(BaseModel):
    """
    The Dossier Object contains all correlated intelligence gathered during the ANALYZE phase.
    It includes leaks, infrastructure, and de-masked identities.
    """
    enrichment: Optional[EnrichmentResult] = None
    demasking: Optional[DemaskingResult] = None
    
    # AI-generated summary/narrative can be added here later
    ai_narrative: Optional[str] = None
    recommended_strategy: Optional[ExecutionStrategy] = ExecutionStrategy.THROTTLE


class Mission(BaseModel):
    """
    The Unified Operational Pipeline State Object.
    A mission represents a single cohesive tracking/mitigation lifecycle against a target entity.
    """
    mission_id: str
    tenant_id: str
    target_entity: str
    phase: MissionPhase = Field(default=MissionPhase.RECON)

    # ADDED: MissionLaunchRequest (mission_router.py) already accepts and passes
    # `mode` and `priority` from the frontend, and escalate_mission() updates
    # priority -- but neither field previously existed on Mission itself, so
    # initiate_mission() couldn't accept or store them (a TypeError on every
    # single /missions/launch call, since the router always passes them).
    mode: str = Field(default="full")            # full | recon | stealth
    priority: str = Field(default="MEDIUM")      # LOW | MEDIUM | HIGH | CRITICAL

    # ADDED: the actual Red Team Ops UI (frontend/src/app/redteam/page.tsx)
    # lets the operator type a free-text objective and pick MITRE ATT&CK
    # techniques, and sends both in the launch request body -- but neither
    # field existed here, so Pydantic silently discarded them on every launch
    # (no error, just quietly lost operator input).
    objective: Optional[str] = None
    techniques: List[str] = Field(default_factory=list)

    # Context accumulated through the pipeline
    recon_data: Dict[str, Any] = Field(default_factory=dict)
    analysis_findings: Dossier = Field(default_factory=Dossier)
    execution_history: List[Dict[str, Any]] = Field(default_factory=list)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        orm_mode = True
