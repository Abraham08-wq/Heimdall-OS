"""
agent_deps.py — Authentication for the sensor agent (device-to-backend) and
the organization agent (server/network-to-backend), as distinct from human
user authentication in app/api/deps.py.

A human operator authenticates with a JWT (via get_current_active_user).
An agent (device or organization) authenticates with its own secret, issued
once at enrollment and never transmitted again in plaintext after that --
only its hash is stored, exactly like a password.
"""
from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional
from passlib.context import CryptContext

from app.api import deps
from app.models.models import Device, Organization

# Reuses the same hashing scheme this project already has available via
# passlib (already a dependency here for password hashing) -- bcrypt is a
# reasonable default; if your existing user-password hashing uses a specific
# CryptContext elsewhere (check app/core/security.py), prefer importing and
# reusing that one instead of this second instance, so there's only one
# hashing configuration to ever rotate.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_agent_secret(secret: str) -> str:
    return pwd_context.hash(secret)


def verify_agent_secret(secret: str, secret_hash: str) -> bool:
    return pwd_context.verify(secret, secret_hash)


def get_device_from_agent_auth(
    device_id: UUID,
    db: Session = Depends(deps.get_db),
    authorization: Optional[str] = Header(None),
) -> Device:
    """
    FastAPI dependency for agent-facing endpoints (heartbeat, command result).
    Expects `Authorization: Bearer <agent_secret>`, checked against the
    device's own stored hash -- NOT a human JWT, NOT get_current_active_user.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing agent credential.")
    secret = authorization.removeprefix("Bearer ").strip()

    device = db.query(Device).filter(Device.id == device_id).first()
    if not device or not device.agent_secret_hash:
        # Same error for "no such device" and "device never enrolled" --
        # avoids confirming which device IDs exist to an unauthenticated caller.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid device credential.")

    if not verify_agent_secret(secret, device.agent_secret_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid device credential.")

    return device


def get_organization_from_agent_auth(
    organization_id: UUID,
    db: Session = Depends(deps.get_db),
    authorization: Optional[str] = Header(None),
) -> Organization:
    """
    FastAPI dependency for organization-agent-facing endpoints (heartbeat,
    command result) -- the server/network-level counterpart to
    get_device_from_agent_auth above. Same shape: Authorization: Bearer
    <agent_secret>, checked against the organization's own stored hash.
    NOT a human JWT.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing agent credential.")
    secret = authorization.removeprefix("Bearer ").strip()

    organization = db.query(Organization).filter(Organization.id == organization_id).first()
    if not organization or not organization.agent_secret_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid organization credential.")

    if not verify_agent_secret(secret, organization.agent_secret_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid organization credential.")

    return organization