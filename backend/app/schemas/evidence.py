from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl

class Reliability(str, Enum):
    A = "A - Completely Reliable"
    B = "B - Usually Reliable"
    C = "C - Fairly Reliable"
    D = "D - Not Usually Reliable"
    E = "E - Unreliable"
    F = "F - Reliability Cannot Be Judged"

class Evidence(BaseModel):
    """
    Represents a specific piece of proof (URL, File, API Response).
    Crucial for 'Explainable Intelligence'.
    """
    id: str = Field(..., description="Unique hash of the evidence content")
    source_url: Optional[HttpUrl] = None
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    reliability: Reliability = Field(default=Reliability.F, description="Admiralty Grading System")
    
    # Anti-Misinformation: Source must be declared
    provider: str = Field(..., description="Name of the data provider (e.g., 'Shodan', 'Manual Upload')")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "sha256:1234...",
                "source_url": "https://haveibeenpwned.com",
                "collected_at": "2024-01-01T12:00:00Z",
                "reliability": "A - Completely Reliable",
                "provider": "HaveIBeenPwned"
            }
        }
