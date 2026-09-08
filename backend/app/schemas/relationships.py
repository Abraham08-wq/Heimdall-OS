from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field

class LinkType(str, Enum):
    OWNS = "OWNS"          # Person -> Email/Phone
    WORKS_AT = "WORKS_AT"  # Person -> Organization
    HOSTS = "HOSTS"        # IP -> Domain
    LINKED_TO = "LINKED_TO" # Generic connection

class Relationship(BaseModel):
    source_id: str
    target_id: str
    type: LinkType
    confidence: float = Field(..., ge=0.0, le=1.0)
    
    # Explainability
    evidence_ids: List[str] = []
    discovery_method: str = Field(..., description="Algorithm used: 'determininstic', 'jaro-winkler', 'time-overlap'")
    
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def is_strong(self) -> bool:
        return self.confidence > 0.8
