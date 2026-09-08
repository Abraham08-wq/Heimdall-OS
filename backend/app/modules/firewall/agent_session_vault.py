"""
agent_session_vault.py — ProjectXY Cognitive Shield: Layer 2 (Session Vault)
==============================================================================
Mission-scoped permission vault for AI agents.

Each agent session is issued a MissionContext stored in Redis with TTL
equal to the mission duration. The vault:
  - Grants agents a scoped token containing their allowed tool classes,
    data classes, and mission phase
  - Validates that incoming agent calls match the vault's scope
  - Revokes old scope when mission state changes
  - Integrates with existing revoke_agent_tokens() in core/security.py

Redis Key Schema:
  agent_vault:{tenant_id}:{agent_id}  →  JSON(MissionContext)  TTL=mission_duration
  agent_vault:index:{tenant_id}       →  SET of active agent_ids
"""

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

import redis.asyncio as aioredis

from app.modules.firewall.opa_policy_bridge import AgentContext

logger = logging.getLogger("projectxy.firewall.vault")

# ---------------------------------------------------------------------------
# Mission Context Dataclass
# ---------------------------------------------------------------------------

@dataclass
class MissionContext:
    """
    Scope granted to an agent for a specific mission.
    Stored in Redis — must be JSON serializable.
    """
    mission_id: str
    agent_id: str
    tenant_id: str
    role: str
    clearance_level: int                  # 1-4
    mission_phase: str                    # RECON | EXPLOITATION | POST_EX | CLEANUP
    allowed_tool_classes: List[str]       # DATA | EXEC | CONFIG | AUDIT | AGENT | NETWORK
    allowed_data_classes: List[str]       # Public | Internal | Confidential | Secret
    allowed_intents: List[str]            # READ | WRITE | EXECUTE | DELETE
    mfa_verified: bool = False
    risk_ceiling: float = 0.7             # Max tolerable threat score for this agent
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    expires_at: str = field(
        default_factory=lambda: (
            datetime.now(timezone.utc) + timedelta(hours=8)
        ).isoformat()
    )
    session_token: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_agent_context(self) -> AgentContext:
        """Convert to AgentContext for OPA policy evaluation."""
        return AgentContext(
            agent_id=self.agent_id,
            tenant_id=self.tenant_id,
            role=self.role,
            mission_id=self.mission_id,
            mission_phase=self.mission_phase,
            clearance_level=self.clearance_level,
            mfa_verified=self.mfa_verified,
        )

    def is_expired(self) -> bool:
        expires = datetime.fromisoformat(self.expires_at)
        return datetime.now(timezone.utc) >= expires


# ---------------------------------------------------------------------------
# Default Scope Templates (by role)
# ---------------------------------------------------------------------------

DEFAULT_SCOPES: Dict[str, Dict[str, Any]] = {
    "viewer": {
        "allowed_tool_classes": ["DATA"],
        "allowed_data_classes": ["Public", "Internal"],
        "allowed_intents": ["READ"],
        "clearance_level": 1,
        "risk_ceiling": 0.3,
    },
    "analyst": {
        "allowed_tool_classes": ["DATA", "AUDIT", "NETWORK"],
        "allowed_data_classes": ["Public", "Internal", "Confidential"],
        "allowed_intents": ["READ", "WRITE"],
        "clearance_level": 2,
        "risk_ceiling": 0.5,
    },
    "operator": {
        "allowed_tool_classes": ["DATA", "EXEC", "CONFIG", "AUDIT", "NETWORK"],
        "allowed_data_classes": ["Public", "Internal", "Confidential"],
        "allowed_intents": ["READ", "WRITE", "EXECUTE"],
        "clearance_level": 3,
        "risk_ceiling": 0.7,
    },
    "admin": {
        "allowed_tool_classes": ["DATA", "EXEC", "CONFIG", "AUDIT", "AGENT", "NETWORK"],
        "allowed_data_classes": ["Public", "Internal", "Confidential", "Secret"],
        "allowed_intents": ["READ", "WRITE", "EXECUTE", "DELETE", "ADMIN"],
        "clearance_level": 4,
        "risk_ceiling": 0.9,
    },
}

# Mission phase → allowed tool class progression
PHASE_TOOL_MAP: Dict[str, List[str]] = {
    "RECON":        ["DATA", "NETWORK"],
    "EXPLOITATION": ["DATA", "NETWORK", "EXEC"],
    "POST_EX":      ["DATA", "NETWORK", "EXEC", "CONFIG"],
    "CLEANUP":      ["DATA", "CONFIG", "AUDIT"],
}


# ---------------------------------------------------------------------------
# Agent Session Vault
# ---------------------------------------------------------------------------

class AgentSessionVault:
    """
    Redis-backed mission-scoped permission vault.

    Usage:
        vault = AgentSessionVault(redis_url)
        await vault.connect()

        ctx = await vault.issue_session(
            agent_id="agt_001", tenant_id="tenant_alpha", role="operator",
            mission_id="mission_42", mission_phase="RECON"
        )

        # Later, validate a call:
        mission_ctx = await vault.get_session(agent_id, tenant_id)
    """

    VAULT_TTL_SECONDS = 8 * 3600  # 8 hours default

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self._redis_url = redis_url
        self._redis: Optional[aioredis.Redis] = None

    async def connect(self):
        try:
            self._redis = aioredis.from_url(
                self._redis_url, encoding="utf-8", decode_responses=True
            )
            await self._redis.ping()
            logger.info("[VAULT] Agent Session Vault connected to Redis.")
        except Exception as exc:
            logger.warning(f"[VAULT] Redis unavailable: {exc}. Vault operating in degraded mode.")

    async def issue_session(
        self,
        agent_id: str,
        tenant_id: str,
        role: str,
        mission_id: str,
        mission_phase: str = "RECON",
        mfa_verified: bool = False,
        duration_hours: int = 8,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> MissionContext:
        """
        Issue a new mission-scoped session for an agent.
        Revokes any existing session for this agent.
        """
        # Revoke old session if exists
        await self.revoke_session(agent_id, tenant_id)

        # Build scope from role template
        scope = dict(DEFAULT_SCOPES.get(role, DEFAULT_SCOPES["viewer"]))

        # Intersect with mission phase allowed tools
        phase_tools = set(PHASE_TOOL_MAP.get(mission_phase, ["DATA"]))
        scope["allowed_tool_classes"] = [
            t for t in scope["allowed_tool_classes"] if t in phase_tools
        ]

        # Apply caller overrides (must be subset of role scope)
        if overrides:
            if "allowed_tool_classes" in overrides:
                scope["allowed_tool_classes"] = [
                    t for t in overrides["allowed_tool_classes"]
                    if t in scope["allowed_tool_classes"]
                ]
            if "allowed_intents" in overrides:
                scope["allowed_intents"] = [
                    i for i in overrides["allowed_intents"]
                    if i in scope["allowed_intents"]
                ]

        expires_at = (
            datetime.now(timezone.utc) + timedelta(hours=duration_hours)
        ).isoformat()

        ctx = MissionContext(
            mission_id=mission_id,
            agent_id=agent_id,
            tenant_id=tenant_id,
            role=role,
            clearance_level=scope["clearance_level"],
            mission_phase=mission_phase,
            allowed_tool_classes=scope["allowed_tool_classes"],
            allowed_data_classes=scope["allowed_data_classes"],
            allowed_intents=scope["allowed_intents"],
            mfa_verified=mfa_verified,
            risk_ceiling=scope["risk_ceiling"],
            expires_at=expires_at,
        )

        if self._redis:
            try:
                vault_key = f"agent_vault:{tenant_id}:{agent_id}"
                index_key = f"agent_vault:index:{tenant_id}"
                await self._redis.setex(
                    vault_key,
                    duration_hours * 3600,
                    json.dumps(asdict(ctx))
                )
                await self._redis.sadd(index_key, agent_id)
                await self._redis.expire(index_key, duration_hours * 3600)
                logger.info(
                    f"[VAULT] Session issued: agent={agent_id} tenant={tenant_id} "
                    f"mission={mission_id} phase={mission_phase} role={role}"
                )
            except Exception as exc:
                logger.error(f"[VAULT] Failed to persist session: {exc}")

        return ctx

    async def get_session(
        self, agent_id: str, tenant_id: str
    ) -> Optional[MissionContext]:
        """Retrieve and validate an active session from the vault."""
        if not self._redis:
            return None
        try:
            vault_key = f"agent_vault:{tenant_id}:{agent_id}"
            raw = await self._redis.get(vault_key)
            if not raw:
                return None
            data = json.loads(raw)
            ctx = MissionContext(**data)
            if ctx.is_expired():
                await self.revoke_session(agent_id, tenant_id)
                return None
            return ctx
        except Exception as exc:
            logger.error(f"[VAULT] get_session error: {exc}")
            return None

    async def revoke_session(self, agent_id: str, tenant_id: str) -> bool:
        """Revoke an agent session. Also adds to the existing blocklist."""
        if not self._redis:
            return False
        try:
            vault_key = f"agent_vault:{tenant_id}:{agent_id}"
            index_key = f"agent_vault:index:{tenant_id}"
            await self._redis.delete(vault_key)
            await self._redis.srem(index_key, agent_id)

            # Also add to the existing security.py revocation blocklist
            blocklist_key = f"revoked:{tenant_id}:{agent_id}"
            await self._redis.setex(blocklist_key, 86400, "revoked")
            logger.info(f"[VAULT] Session revoked: agent={agent_id} tenant={tenant_id}")
            return True
        except Exception as exc:
            logger.error(f"[VAULT] revoke_session error: {exc}")
            return False

    async def advance_mission_phase(
        self, agent_id: str, tenant_id: str, new_phase: str
    ) -> Optional[MissionContext]:
        """
        Advance the mission phase for an agent.
        Re-issues the session with updated tool class scope.
        """
        existing = await self.get_session(agent_id, tenant_id)
        if not existing:
            return None

        return await self.issue_session(
            agent_id=agent_id,
            tenant_id=tenant_id,
            role=existing.role,
            mission_id=existing.mission_id,
            mission_phase=new_phase,
            mfa_verified=existing.mfa_verified,
        )

    async def list_active_agents(self, tenant_id: str) -> List[Dict[str, Any]]:
        """List all active agent sessions for a tenant."""
        if not self._redis:
            return []
        try:
            index_key = f"agent_vault:index:{tenant_id}"
            agent_ids: Set[str] = await self._redis.smembers(index_key)
            result = []
            for agent_id in agent_ids:
                ctx = await self.get_session(agent_id, tenant_id)
                if ctx:
                    result.append({
                        "agent_id": ctx.agent_id,
                        "mission_id": ctx.mission_id,
                        "mission_phase": ctx.mission_phase,
                        "role": ctx.role,
                        "clearance_level": ctx.clearance_level,
                        "allowed_tool_classes": ctx.allowed_tool_classes,
                        "expires_at": ctx.expires_at,
                        "risk_ceiling": ctx.risk_ceiling,
                    })
            return result
        except Exception as exc:
            logger.error(f"[VAULT] list_active_agents error: {exc}")
            return []

    async def update_mfa_status(
        self, agent_id: str, tenant_id: str, mfa_verified: bool
    ) -> bool:
        """Update MFA verification status without revoking the session."""
        ctx = await self.get_session(agent_id, tenant_id)
        if not ctx:
            return False
        ctx.mfa_verified = mfa_verified
        if self._redis:
            try:
                vault_key = f"agent_vault:{tenant_id}:{agent_id}"
                ttl = await self._redis.ttl(vault_key)
                if ttl > 0:
                    await self._redis.setex(vault_key, ttl, json.dumps(asdict(ctx)))
            except Exception as exc:
                logger.error(f"[VAULT] update_mfa_status error: {exc}")
        return True


# ---------------------------------------------------------------------------
# Module-level singleton factory
# ---------------------------------------------------------------------------

import os

_vault_instance: Optional[AgentSessionVault] = None


async def get_agent_session_vault() -> AgentSessionVault:
    """FastAPI dependency — returns the singleton vault."""
    global _vault_instance
    if _vault_instance is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _vault_instance = AgentSessionVault(redis_url=redis_url)
        await _vault_instance.connect()
    return _vault_instance
