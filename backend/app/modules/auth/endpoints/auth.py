import logging
from datetime import timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core import security
from app.core.config import settings
from app.models import models
from app.api import deps
from app.core.rate_limit import get_rate_limit_dependency

logger = logging.getLogger(__name__)
router = APIRouter()


class CurrentUserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    tenant_id: Optional[str] = None
    org_id: Optional[str] = None


def _set_session_cookie(response: Response, access_token: str, expires: timedelta) -> None:
    """
    Sets the session token cookie.
    Configured with 'none' samesite rules to allow port 3000 to port 8000 cross-origin transmission.
    """
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=int(expires.total_seconds()),
        httponly=True,
        secure=str(settings.FRONTEND_URL).startswith("https://"),
        samesite="none" if str(settings.FRONTEND_URL).startswith("https://") else "lax",
        path="/",
    )



@router.post("/access-token", response_model=dict)
async def login_access_token(
        response: Response,  # Fixed: Forced explicit parameter injection ensures cookies are dropped!
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: Session = Depends(deps.get_db),
        _rl=Depends(get_rate_limit_dependency(times=5, seconds=60))
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    if settings.AUTH_BYPASS_ENABLED:
        logger.warning("[DEV] Auth bypass active. Minting an operator token without credential checks.")
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = security.create_access_token(
            subject=form_data.username,
            tenant_id="org_dev_local",
            role="admin",
            expires_delta=access_token_expires,
        )
        _set_session_cookie(response, access_token, access_token_expires)
        return {
            "access_token": access_token,
            "token_type": "bearer",
        }

    # 1. Fetch User
    user = db.query(models.User).filter(models.User.email == form_data.username).first()

    # 2. Validate
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        # Publish auth failure to Kafka → SIEM
        try:
            from app.infrastructure.kafka import kafka_streamer
            import time
            await kafka_streamer.publish("auth_events", {
                "event_type": "AUTH_FAILURE",
                "username": form_data.username,
                "timestamp": int(time.time()),
                "reason": "invalid_credentials",
            })
        except Exception as e:
            logger.error(f"Failed to publish auth failure event to Kafka: {e}")

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        logger.warning(f"Authentication attempt from inactive user: {user.email}")
        raise HTTPException(status_code=400, detail="Inactive user")

    # 3. Mint Token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Ensure tenant_id is always a non-None string in the token.
    # If the user has no tenant linked (e.g., freshly seeded without a Tenant row),
    # fall back to the canonical default org UUID so the JWT guard never rejects the token.
    tenant_id_for_token = str(user.tenant_id) if user.tenant_id else settings.DEFAULT_ORG_ID

    access_token = security.create_access_token(
        subject=user.email,
        tenant_id=tenant_id_for_token,
        role=user.role,  # Directly use user.role, which has a DB-level default
        expires_delta=access_token_expires,
    )

    # Sets the secure httpOnly cookie value on the client browser frame seamlessly
    _set_session_cookie(response, access_token, access_token_expires)

    # Publish auth success to Kafka → SIEM
    try:
        from app.infrastructure.kafka import kafka_streamer
        import time
        await kafka_streamer.publish("auth_events", {
            "event_type": "AUTH_SUCCESS",
            "user_id": str(user.id),
            "email": user.email,
            "role": user.role,
            "tenant_id": tenant_id_for_token,
            "timestamp": int(time.time()),
        })
    except Exception as e:
        logger.error(f"Failed to publish auth success event to Kafka: {e}")

    logger.info(f"User '{user.email}' logged in successfully. Tenant: {tenant_id_for_token}")
    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.get("/me", response_model=CurrentUserResponse)
async def read_current_user(current_user: models.User = Depends(deps.get_current_user)) -> CurrentUserResponse:
    # org_id is not a direct column on the User model, so getattr is appropriate here.
    org_id = getattr(current_user, "org_id", None)
    tenant_id = str(current_user.tenant_id) if current_user.tenant_id else None

    return CurrentUserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
        tenant_id=tenant_id,
        org_id=str(org_id) if org_id else None,
    )


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(key="access_token", path="/")
    logger.info("User logged out successfully.")
    return {"status": "ok"}

