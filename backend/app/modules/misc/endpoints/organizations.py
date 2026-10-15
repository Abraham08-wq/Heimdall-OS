"""
organizations.py — Human-facing (JWT-authenticated) endpoints for managing
Organizations: the tenant-owned, agent-monitored asset type representing a
whole protected company/network, as opposed to a single Device.

This is the counterpart to devices.py, but for Organizations specifically.
It replaces the old `organizations_router` block that used to live inside
devices.py (written against the earlier, now-retired shape of Organization
that duplicated Tenant's contact/legal fields) -- remove that block from
devices.py once this file is wired in, so there's exactly one place that
owns the /organizations/* routes.
"""
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.models.models import Organization, OrganizationCommand
from app.schemas import agent_schema
from app.infrastructure.cache.redis_manager import redis_cache

router = APIRouter(prefix="/organizations", tags=["Organizations"])

ORG_ENROLLMENT_TOKEN_TTL_SECONDS = 24 * 3600


def _org_enrollment_key(token: str) -> str:
    return f"organization:enrollment:{token}"


# ── CRUD (human-authenticated) ───────────────────────────────────────────────
# NOTE: swap `deps.get_current_user` below for whatever your project's real
# dependency name is if it differs -- check devices.py's own CRUD endpoints
# for the exact name it uses, and match it here so auth stays consistent.

@router.post("/", response_model=agent_schema.Organization)
def create_organization(
    *,
    db: Session = Depends(deps.get_db),
    payload: agent_schema.OrganizationCreate,
    current_user=Depends(deps.get_current_user),
) -> Any:
    org = Organization(
        tenant_id=payload.tenant_id,
        owner_id=getattr(current_user, "id", None),
        name=payload.name,
        domain=payload.domain,
        industry=payload.industry,
        notes=payload.notes,
        deployment_mode=payload.deployment_mode,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@router.get("/", response_model=List[agent_schema.Organization])
def list_organizations(
    *,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
) -> Any:
    return db.query(Organization).order_by(Organization.created_at.desc()).all()


@router.get("/{organization_id}", response_model=agent_schema.Organization)
def get_organization(
    *,
    db: Session = Depends(deps.get_db),
    organization_id: UUID,
    current_user=Depends(deps.get_current_user),
) -> Any:
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")
    return org


@router.delete("/{organization_id}")
def delete_organization(
    *,
    db: Session = Depends(deps.get_db),
    organization_id: UUID,
    current_user=Depends(deps.get_current_user),
) -> Any:
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")
    db.delete(org)
    db.commit()
    return {"deleted": True, "organization_id": str(organization_id)}


# ── Step 0: issue a one-time enrollment token (human-authenticated) ─────────
# Same pattern as device enrollment tokens -- generate here, hand the token
# to whoever is installing the agent on the organization's server.

@router.post("/enrollment-tokens", response_model=agent_schema.OrgEnrollmentTokenResponse)
def create_org_enrollment_token(
    *,
    payload: agent_schema.OrgEnrollmentTokenRequest,
    current_user=Depends(deps.get_current_user),
) -> Any:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ORG_ENROLLMENT_TOKEN_TTL_SECONDS)

    payload_to_store = {
        "tenant_id": str(payload.tenant_id) if payload.tenant_id else None,
        "deployment_mode": payload.deployment_mode,
        "organization_name_hint": payload.organization_name_hint,
    }
    redis_cache.redis_client.set(
        _org_enrollment_key(token),
        json.dumps(payload_to_store),
        ex=ORG_ENROLLMENT_TOKEN_TTL_SECONDS,
    )

    return agent_schema.OrgEnrollmentTokenResponse(enrollment_token=token, expires_at=expires_at)


# ── Command queueing (human clicks an action in the dashboard) ──────────────

@router.post("/{organization_id}/commands", response_model=agent_schema.OrganizationCommandOut)
def queue_organization_command(
    *,
    db: Session = Depends(deps.get_db),
    organization_id: UUID,
    payload: agent_schema.QueueOrgCommandRequest,
    current_user=Depends(deps.get_current_user),
) -> Any:
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")

    command = OrganizationCommand(
        organization_id=organization_id,
        action=payload.action,
        params=payload.params,
        issued_by=getattr(current_user, "id", None),
    )
    db.add(command)
    db.commit()
    db.refresh(command)
    return command


@router.get("/{organization_id}/commands", response_model=List[agent_schema.OrganizationCommandOut])
def list_organization_commands(
    *,
    db: Session = Depends(deps.get_db),
    organization_id: UUID,
    current_user=Depends(deps.get_current_user),
) -> Any:
    return (
        db.query(OrganizationCommand)
        .filter(OrganizationCommand.organization_id == organization_id)
        .order_by(OrganizationCommand.created_at.desc())
        .all()
    )