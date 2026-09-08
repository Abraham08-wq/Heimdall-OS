from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr
from app.schemas.evidence import Evidence

class EntityType(str, Enum):
    PERSON = "person"
    ORGANIZATION = "organization"
    DOMAIN = "domain"
    IP = "ip"
    THREAT_ACTOR = "threat-actor"
    MALWARE = "malware"

class AttributeType(str, Enum):
    EMAIL = "email"
    PHONE = "phone"
    USERNAME = "username"
    WALLET = "crypto_wallet"

class Attribute(BaseModel):
    value: str = Field(..., description="The value of the attribute (e.g., email address)")
    type: AttributeType
    is_hashed: bool = Field(default=False, description="Privacy flag: true if value is a hash")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score 0-1")
    
    # Link to Evidence (Traceability)
    evidence_refs: List[str] = Field(default_factory=list, description="IDs of evidence supporting this attribute")
    
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)

class EntityBase(BaseModel):
    canonical_name: str = Field(..., description="The main display name")
    type: EntityType
    risk_score: int = Field(default=0, ge=0, le=100)

class EntityCreate(EntityBase):
    attributes: List[Attribute] = []

from uuid import UUID

class Entity(EntityBase):
    id: UUID
    attributes: List[Attribute] = []
    created_at: datetime
    updated_at: datetime
    
    # Computed risk level
    @property
    def risk_level(self) -> str:
        if self.risk_score < 20: return "LOW"
        if self.risk_score < 60: return "MEDIUM"
        if self.risk_score < 80: return "HIGH"
        return "CRITICAL"
