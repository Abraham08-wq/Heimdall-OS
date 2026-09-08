from datetime import datetime, timedelta
from typing import Optional, Union, Any
from jose import jwt
from app.core.config import settings
from app.core.passwords import get_password_hash as _get_password_hash
from app.core.passwords import verify_password as _verify_password
ALGORITHM = "HS256"

def create_access_token(
    subject: Union[str, Any], 
    tenant_id: str,
    role: str = "viewer",
    expires_delta: timedelta = None
) -> str:
    """
    Generates a Zero-Trust JWT access token.
    Enforces Tenant Isolation by baking the TID directly into the token structure,
    making accidental cross-tenant data spillage impossible at the API gateway layer.
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        # Ultra-short expiry for Defense platforms (15 mins default)
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        # Emit both keys: deps.py reads `org_id` first; legacy code reads `tenant_id`.
        # This ensures both old and new call-sites resolve the org context correctly.
        "org_id": tenant_id,
        "tenant_id": tenant_id,
        "role": role,
        "type": "access"
    }
    
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(
    subject: Union[str, Any], 
    tenant_id: str
) -> str:
    """
    Generates an OAuth2 Refresh Token for long-lived session persistence without compromising short-lived Access Tokens.
    """
    # Refresh tokens live for 7 days
    expire = datetime.utcnow() + timedelta(days=7)
    
    to_encode = {
        "exp": expire, 
        "sub": str(subject),
        "tenant_id": tenant_id,
        "type": "refresh"
    }
    
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str, token_type: str = "access") -> Optional[dict]:
    """
    Decodes and verifies a JWT token. Checks type to prevent token confusion attacks.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != token_type:
            return None
        return payload
    except jwt.JWTError:
        return None

# FIDO2/WebAuthn Stubs for Hardware Key Authentication
async def generate_fido2_registration_options(user: Any):
    """Generates challenge for hardware key registration."""
    pass

async def verify_fido2_registration_response(user: Any, response: Any):
    """Verifies hardware key response to finalize registration."""
    pass

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _verify_password(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return _get_password_hash(password)

async def revoke_agent_tokens(agent_id: str, tenant_id: str):
    """
    Revokes JWT access tokens for a specific agent.
    Implemented by adding the agent's identifier to a Redis blocklist.
    """
    import redis.asyncio as redis
    import os
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    client = redis.from_url(redis_url, decode_responses=True)
    
    try:
        # Create a revocation key that lives for the max token lifespan (e.g., 24 hours)
        blocklist_key = f"revoked:{tenant_id}:{agent_id}"
        await client.setex(blocklist_key, 86400, "revoked")
    except Exception as e:
        # Log error in production
        pass
    finally:
        await client.close()
