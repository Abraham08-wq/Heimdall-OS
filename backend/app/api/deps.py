import logging
from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlalchemy.orm import Session
from app.core import security
from app.core.config import settings
from app.models.models import User
from app.infrastructure.session import get_db
from app.modules.zero_trust.zero_trust import zero_trust_engine

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/access-token", auto_error=False)
logger = logging.getLogger(__name__)


def _extract_access_token(request: Request, token: Optional[str]) -> str:
    if token:
        return token

    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()

    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token.removeprefix("Bearer ").strip()

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )

def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme)
) -> User:

# ── [EXPLICIT DEV BYPASS MODE] ─────────────────────────────────────────
    if settings.AUTH_BYPASS_ENABLED:
        logger.warning("[DEV] Auth bypass active. Injecting admin developer context.")
        import uuid as _uuid
        dev_user = User(
            id=_uuid.UUID("00000000-0000-0000-0000-000000000000"),
            email="dev@projectxy.local",
            role="admin",
            is_active=True
        )
        dev_user.org_id = settings.DEFAULT_ORG_ID
        dev_user.dynamic_role = "admin"
        dev_user.billing_tier = "ADVANCED"
        return dev_user
    # ──────────────────────────────────────────────────────────────────────
    """Validate the JWT, resolve the user, and bind the trusted org context."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        access_token = _extract_access_token(request, token)
        payload = jwt.decode(access_token, settings.JWT_SECRET_KEY, algorithms=[security.ALGORITHM])
        email: str = payload.get("sub")
        # Accept either `org_id` (canonical) or `tenant_id` (legacy alias — both emitted by security.py).
        org_id = payload.get("org_id") or payload.get("tenant_id") or settings.DEFAULT_ORG_ID
        if email is None:
            raise credentials_exception
        # org_id is always populated now (DEFAULT_ORG_ID fallback above), so no None check needed.
    except (JWTError, ValidationError):
        raise credentials_exception
        
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception

    user.org_id = str(org_id)
        
    # [ZERO TRUST MULTI-FACTOR EVALUATION (Phase 7)]
    client_ip = request.client.host if request.client else "127.0.0.1"
    device_fingerprint = request.headers.get("X-Device-Fingerprint", "unknown")
    
    try:
        zt_eval = zero_trust_engine.evaluate_session_context(
            user_id=str(user.id),
            client_ip=client_ip,
            device_fingerprint=device_fingerprint,
            expected_role=user.role
        )
    except Exception as zt_exc:
        # ZT engine failure must not lock out all users — degrade gracefully.
        logger.warning(f"[ZERO-TRUST] Engine evaluation failed, defaulting to authorized: {zt_exc}")
        zt_eval = {"is_authorized": True, "dynamic_role": user.role, "reason": "zt_engine_degraded"}
    
    if not zt_eval.get("is_authorized"):
        raise HTTPException(
            status_code=403,
            detail=f"Zero Trust Policy Violation: {zt_eval.get('reason')}"
        )
        
    # [ENTERPRISE SAAS TIER ENFORCEMENT (Phase 11)]
    from app.modules.misc.services.enterprise import saas_manager
    # In production, fetch subscription tier from tenant table. Mocking 'ADVANCED' for demo.
    billing_tier = "ADVANCED" 
    
    # We could restrict login here entirely if the path requires a specific feature, 
    # but normally this is handled via a dedicated @requires_feature() dependency.
    user.billing_tier = billing_tier
        
    # Dynamically override the object role safely in memory (Does not commit to DB)
    user.dynamic_role = zt_eval.get("dynamic_role", user.role)
    
    return user

def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def get_current_active_superuser(current_user: User = Depends(get_current_active_user)) -> User:
    # Use dynamically assessed role from Zero Trust Engine
    active_role = getattr(current_user, "dynamic_role", current_user.role)
    if active_role != "admin":
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges (Dynamic Eval failed)"
        )
    return current_user


# ─────────────────────────────────────────────────────────────────────────────
# Intelligence Services DI Factories (org-scoped)
# ─────────────────────────────────────────────────────────────────────────────

def get_org_id_from_request(request: Request) -> str:
    """Extract the trusted org_id from the verified JWT payload."""
    token = _extract_access_token(request, None)
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[security.ALGORITHM])
    org_id = payload.get("org_id") or payload.get("tenant_id")
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing org context",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return str(org_id)


def get_attribution_engine(
    current_user: User = Depends(get_current_active_user),
    request: Request = None
):
    """
    Returns an org-scoped AttributionEngine instance for threat actor correlation.
    
    Usage in endpoint:
        @router.post("/correlate")
        async def correlate(indicators: List[str], engine = Depends(get_attribution_engine)):
            return await engine.correlate_indicators(indicators)
    """
    from app.core.intelligence_di import get_di_container
    
    container = get_di_container()
    org_id = getattr(current_user, "org_id", str(current_user.tenant_id) if current_user.tenant_id else "default_org")
    
    engine = container.get_attribution_engine(org_id=org_id)
    return engine


def get_microseg_service(
    current_user: User = Depends(get_current_active_user),
    request: Request = None
):
    """
    Returns an org-scoped MicrosegmentationService for automated containment.
    
    Usage in endpoint:
        @router.post("/isolate")
        async def isolate(host: str, service = Depends(get_microseg_service)):
            return await service.isolate_host(...)
    """
    from app.core.intelligence_di import get_di_container
    
    container = get_di_container()
    org_id = getattr(current_user, "org_id", str(current_user.tenant_id) if current_user.tenant_id else "default_org")
    
    service = container.get_microseg_service(org_id=org_id)
    return service


def get_request_orchestrator(
    current_user: User = Depends(get_current_active_user),
    request: Request = None
):
    """
    Returns an org-scoped DistributedRequestOrchestrator for resilient API queries.
    
    Usage in endpoint:
        @router.post("/query")
        async def query(url: str, orchestrator = Depends(get_request_orchestrator)):
            return await orchestrator.request("GET", url)
    """
    from app.core.intelligence_di import get_di_container
    
    container = get_di_container()
    org_id = getattr(current_user, "org_id", str(current_user.tenant_id) if current_user.tenant_id else "default_org")
    
    orchestrator = container.get_request_orchestrator(org_id=org_id)
    return orchestrator

