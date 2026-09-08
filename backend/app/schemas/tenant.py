from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class Tier(str):
    FREE = "free"     # Basic limits, limited AI features
    PRO = "pro"       # Full AI features, standard limits
    ENTERPRISE = "enterprise" # Custom limits, dedicated clusters

class TenantBase(BaseModel):
    name: str = Field(..., description="Name of the Organization")
    domain: str = Field(..., description="Primary domain of the tenant")
    tier: Tier = Field(default=Tier.PRO)

class TenantCreate(TenantBase):
    admin_email: str

class Tenant(TenantBase):
    id: str = Field(..., description="Unique Tenant ID (TID) injected into every query")
    created_at: datetime
    is_active: bool = True
    
    # Monetization Quotas
    api_call_quota: int = 10000 
    enrichment_quota: int = 500
    ai_analysis_quota: int = 1000
    
    class Config:
        orm_mode = True

class TenantUsage(BaseModel):
    tenant_id: str
    api_calls_used: int = 0
    enrichments_used: int = 0
    ai_analysis_used: int = 0
    reset_date: datetime
