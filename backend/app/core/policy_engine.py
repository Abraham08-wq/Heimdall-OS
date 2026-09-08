from typing import Dict, Any, List
from fastapi import HTTPException, status
from pydantic import BaseModel

class ResourcePolicy(BaseModel):
    required_roles: List[str]
    allow_cross_tenant: bool = False
    requires_mfa: bool = False

class PolicyEngine:
    """
    Zero-Trust Policy Engine.
    Enforces RBAC, Tenant Isolation (Data Silos), and conditional MFA requirements
    before ANY business logic is executed.
    """
    
    def __init__(self):
        # Default strict policies for critical routes
        self.policies: Dict[str, ResourcePolicy] = {
            "view_situation_room": ResourcePolicy(required_roles=["admin", "analyst", "viewer"]),
            "execute_defensive_action": ResourcePolicy(required_roles=["admin", "analyst"], requires_mfa=True),
            "modify_tenant_config": ResourcePolicy(required_roles=["admin"], requires_mfa=True),
            "view_audit_logs": ResourcePolicy(required_roles=["admin", "auditor"])
        }

    def enforce_zero_trust(
        self, 
        action: str, 
        user_claims: Dict[str, Any], 
        target_tenant_id: str,
        user_mfa_verified: bool = False
    ) -> bool:
        """
        Evaluates the request against the strict Zero-Trust matrix.
        Raises HTTP 403 / 401 if unauthorized.
        """
        # 1. Identity & Claim Extraction
        user_id = user_claims.get("sub")
        user_role = user_claims.get("role", "viewer")
        user_tenant = user_claims.get("tenant_id")
        
        if not user_id or not user_tenant:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token structure: missing identity or tenant claims."
            )
            
        # 2. Strict Tenant Isolation (Data Silo Enforcement)
        policy = self.policies.get(action)
        if not policy:
            # Implicit Deny if no policy exists
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Action '{action}' is not explicitly permitted."
            )
            
        if not policy.allow_cross_tenant and user_tenant != target_tenant_id:
            # Cross-tenant data access attempt blocked
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant isolation violation: Access across boundaries prohibited."
            )
            
        # 3. Role-Based Access Control (RBAC)
        if user_role not in policy.required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user_role}' insufficient for action '{action}'."
            )
            
        # 4. Step-Up Authentication (MFA Check)
        if policy.requires_mfa and not user_mfa_verified:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Action requires active Multi-Factor Authentication (MFA) verification."
            )
            
        # If all checks pass, the action is authorized
        return True

policy_engine = PolicyEngine()
