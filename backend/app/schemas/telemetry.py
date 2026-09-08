from pydantic import BaseModel, IPvAnyAddress, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID, uuid4

class GeoIPData(BaseModel):
    country_code: Optional[str] = None
    city: Optional[str] = None
    asn: Optional[int] = None
    org: Optional[str] = None

class HoneypotTelemetryEvent(BaseModel):
    """
    Schema for incoming telemetry from our external global honeypot network.
    """
    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # The IP of the hostile actor striking our honeypot
    attacker_ip: IPvAnyAddress 
    attacker_geo: Optional[GeoIPData] = None
    
    # Information about the honeypot being targeted
    honeypot_name: str
    target_port: int
    protocol: str = Field(..., description="e.g., SSH, RDP, HTTP")
    
    # Payload or interaction details (e.g., attempted passwords, dropped malware hashes)
    interaction_type: str = Field(..., description="e.g., LOGIN_ATTEMPT, MALWARE_DROP")
    details: dict = Field(default_factory=dict, description="Arbitrary interaction metadata")
