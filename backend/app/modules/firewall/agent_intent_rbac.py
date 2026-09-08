"""
agent_intent_rbac.py — ProjectXY Cognitive Shield: Layer 2 (Intent RBAC)
=========================================================================
Core Intent-Based RBAC Engine.

Every agent-to-tool communication passes through this gateway:
1. Load the agent's MissionContext from the Session Vault
2. Classify the call intent from the request payload
3. Evaluate all OPA policies
4. Return ALLOW or DENY with full audit trail

Intent Classification:
  The IntentClassifier analyzes the tool name, resource class, and
  payload keywords to determine the likely intent (READ/WRITE/EXECUTE/etc.)
  This is what makes this "Intent-Based" vs simple role-based:
  the system understands WHY the call is being made.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.modules.firewall.opa_policy_bridge import (
    AgentContext, OPAPolicyBridge, PolicyDecision, ToolCall, opa_bridge
)
from app.modules.firewall.agent_session_vault import (
    AgentSessionVault, MissionContext, get_agent_session_vault
)

logger = logging.getLogger("projectxy.firewall.rbac")


# ---------------------------------------------------------------------------
# Intent Classification
# ---------------------------------------------------------------------------

# Keyword → Intent mappings (order matters: more specific first)
_INTENT_KEYWORDS: List[tuple[str, str]] = [
    # ADMIN intents
    (r'\b(admin|superuser|root|sudo|god.?mode|elevat)\b', 'ADMIN'),

    # DELETE intents
    (r'\b(delete|drop|purge|destroy|remove|wipe|erase|truncate)\b', 'DELETE'),

    # EXECUTE intents
    (r'\b(exec|execute|run|spawn|invoke|call|trigger|launch|deploy|shell)\b', 'EXECUTE'),

    # WRITE intents
    (r'\b(write|create|insert|update|patch|put|post|set|save|upload|push|send)\b', 'WRITE'),

    # READ intents (default fallback)
    (r'\b(read|get|fetch|list|search|query|select|retrieve|view|show|display)\b', 'READ'),
]

_COMPILED_INTENTS = [
    (re.compile(pattern, re.IGNORECASE), intent)
    for pattern, intent in _INTENT_KEYWORDS
]

# Tool name → resource class mapping
TOOL_RESOURCE_MAP: Dict[str, str] = {
    # Data tools
    "search": "DATA", "query": "DATA", "lookup": "DATA",
    "get_entity": "DATA", "list_entities": "DATA", "get_report": "DATA",
    "get_threats": "DATA", "get_events": "DATA", "get_logs": "DATA",

    # Execute tools
    "run_script": "EXEC", "execute_script": "EXEC", "spawn_container": "EXEC",
    "run_command": "EXEC", "exec": "EXEC", "docker_run": "EXEC",
    "exploit": "EXEC", "payload": "EXEC",

    # Config tools
    "update_config": "CONFIG", "set_policy": "CONFIG", "configure": "CONFIG",
    "modify_rule": "CONFIG", "update_firewall": "CONFIG",

    # Audit tools
    "get_audit_log": "AUDIT", "verify_chain": "AUDIT", "export_logs": "AUDIT",

    # Agent tools
    "create_agent": "AGENT", "revoke_agent": "AGENT", "list_agents": "AGENT",
    "issue_session": "AGENT", "vault_ops": "AGENT",

    # Network tools
    "scan": "NETWORK", "probe": "NETWORK", "recon": "NETWORK",
    "isolate": "NETWORK", "quarantine": "NETWORK", "firewall_rule": "NETWORK",
}


class IntentClassifier:
    """
    Classifies the likely intent of an agent tool call.

    Uses tool name + payload keyword analysis to determine:
      - WHAT the agent wants to do (READ/WRITE/EXECUTE/DELETE/ADMIN)
      - Against WHAT resource class (DATA/EXEC/CONFIG/AUDIT/AGENT/NETWORK)
      - The sensitivity level of the target resource
    """

    def classify(
        self,
        tool_name: str,
        payload: Optional[Dict[str, Any]] = None,
        explicit_intent: Optional[str] = None,
    ) -> ToolCall:
        """
        Returns a ToolCall with classified intent and resource class.
        If explicit_intent is provided, it overrides keyword analysis.
        """
        payload = payload or {}

        # Classify resource class
        resource_class = TOOL_RESOURCE_MAP.get(
            tool_name.lower(), self._infer_resource_class(tool_name, payload)
        )

        # Classify intent
        if explicit_intent:
            intent = explicit_intent.upper()
        else:
            intent = self._classify_intent(tool_name, payload)

        # Estimate sensitivity
        sensitivity = self._estimate_sensitivity(resource_class, payload)

        # Mission context required for sensitive operations
        mission_required = resource_class in ("EXEC", "AGENT", "CONFIG") or sensitivity >= 3

        return ToolCall(
            tool_name=tool_name,
            resource_class=resource_class,
            intent=intent,
            sensitivity_level=sensitivity,
            mission_context_required=mission_required,
            payload_summary=self._summarize_payload(payload),
        )

    def _classify_intent(
        self, tool_name: str, payload: Dict[str, Any]
    ) -> str:
        """Analyze tool name and payload keywords to determine intent."""
        text = f"{tool_name} {' '.join(str(v) for v in payload.values())}"
        for pattern, intent in _COMPILED_INTENTS:
            if pattern.search(text):
                return intent
        return "READ"  # safe default

    @staticmethod
    def _infer_resource_class(tool_name: str, payload: Dict[str, Any]) -> str:
        """Infer resource class from tool name when not in the whitelist."""
        tool_lower = tool_name.lower()
        if any(kw in tool_lower for kw in ["exec", "run", "spawn", "shell", "cmd"]):
            return "EXEC"
        if any(kw in tool_lower for kw in ["config", "policy", "rule", "setting"]):
            return "CONFIG"
        if any(kw in tool_lower for kw in ["audit", "log", "ledger", "trace"]):
            return "AUDIT"
        if any(kw in tool_lower for kw in ["agent", "session", "vault", "token"]):
            return "AGENT"
        if any(kw in tool_lower for kw in ["scan", "probe", "net", "network", "firewall", "vlan"]):
            return "NETWORK"
        return "DATA"  # safe default

    @staticmethod
    def _estimate_sensitivity(resource_class: str, payload: Dict[str, Any]) -> int:
        """
        Estimate data sensitivity level (1-4).
        Resource class takes precedence; payload keywords can elevate.
        """
        base = {
            "DATA":    2,
            "NETWORK": 2,
            "EXEC":    3,
            "CONFIG":  3,
            "AUDIT":   2,
            "AGENT":   4,
        }.get(resource_class, 2)

        # Elevate on sensitive payload keywords
        payload_text = ' '.join(str(v) for v in payload.values()).lower()
        if any(kw in payload_text for kw in ["secret", "password", "token", "key", "credential"]):
            base = max(base, 4)
        elif any(kw in payload_text for kw in ["pii", "personal", "patient", "medical", "mpesa"]):
            base = max(base, 3)
        return min(base, 4)

    @staticmethod
    def _summarize_payload(payload: Dict[str, Any]) -> str:
        """Create a safe, truncated summary of the payload for logging."""
        safe_keys = list(payload.keys())[:5]
        return f"keys={safe_keys}"


# ---------------------------------------------------------------------------
# Intent RBAC Gateway
# ---------------------------------------------------------------------------

@dataclass
class RBACDecision:
    """Final decision from the Intent RBAC gateway."""
    allowed: bool
    agent_id: str
    tenant_id: str
    tool_name: str
    intent: str
    resource_class: str
    policy_decision: Optional[PolicyDecision] = None
    mission_context: Optional[MissionContext] = None
    deny_reason: Optional[str] = None
    audit_trail: List[str] = field(default_factory=list)


class AgentIntentRBAC:
    """
    Intent-Based RBAC gateway for all agent-to-tool communications.

    This is the critical Layer 2 component. It answers:
    "Should agent X be allowed to do Y to resource Z, given mission M?"

    Fail-closed: Unknown agents, missing vault sessions, or policy
    evaluation errors all result in DENY.
    """

    def __init__(
        self,
        vault: Optional[AgentSessionVault] = None,
        opa: Optional[OPAPolicyBridge] = None,
    ):
        self._vault = vault
        self._opa = opa or opa_bridge
        self._classifier = IntentClassifier()

    async def evaluate(
        self,
        agent_id: str,
        tenant_id: str,
        tool_name: str,
        payload: Optional[Dict[str, Any]] = None,
        explicit_intent: Optional[str] = None,
        target_tenant_id: Optional[str] = None,
    ) -> RBACDecision:
        """
        Main evaluation entry point.
        Returns RBACDecision with allow/deny and full audit trail.
        """
        audit = []

        # --- Step 1: Load mission context from vault ---
        if not self._vault:
            self._vault = await get_agent_session_vault()

        mission_ctx = await self._vault.get_session(agent_id, tenant_id)

        if not mission_ctx:
            audit.append("DENY: No active mission session found in vault.")
            logger.warning(
                f"[RBAC] DENY (no vault session) | agent={agent_id} tenant={tenant_id} "
                f"tool={tool_name}"
            )
            return RBACDecision(
                allowed=False,
                agent_id=agent_id,
                tenant_id=tenant_id,
                tool_name=tool_name,
                intent=explicit_intent or "UNKNOWN",
                resource_class="UNKNOWN",
                deny_reason="No active mission session. Issue a session via the Agent Vault first.",
                audit_trail=audit,
            )

        audit.append(
            f"Mission session found: mission={mission_ctx.mission_id} "
            f"phase={mission_ctx.mission_phase} role={mission_ctx.role}"
        )

        # --- Step 2: Classify the tool call intent ---
        tool_call = self._classifier.classify(
            tool_name=tool_name,
            payload=payload,
            explicit_intent=explicit_intent,
        )
        tool_call.target_tenant_id = target_tenant_id or tenant_id
        audit.append(
            f"Intent classified: intent={tool_call.intent} "
            f"resource_class={tool_call.resource_class} "
            f"sensitivity={tool_call.sensitivity_level}"
        )

        # --- Step 3: Check intent against vault scope ---
        if tool_call.intent not in mission_ctx.allowed_intents:
            deny_reason = (
                f"Intent '{tool_call.intent}' not in vault scope {mission_ctx.allowed_intents} "
                f"for mission phase '{mission_ctx.mission_phase}'."
            )
            audit.append(f"DENY: {deny_reason}")
            return RBACDecision(
                allowed=False,
                agent_id=agent_id,
                tenant_id=tenant_id,
                tool_name=tool_name,
                intent=tool_call.intent,
                resource_class=tool_call.resource_class,
                mission_context=mission_ctx,
                deny_reason=deny_reason,
                audit_trail=audit,
            )

        if tool_call.resource_class not in mission_ctx.allowed_tool_classes:
            deny_reason = (
                f"Resource class '{tool_call.resource_class}' not in vault scope "
                f"{mission_ctx.allowed_tool_classes} for phase '{mission_ctx.mission_phase}'."
            )
            audit.append(f"DENY: {deny_reason}")
            return RBACDecision(
                allowed=False,
                agent_id=agent_id,
                tenant_id=tenant_id,
                tool_name=tool_name,
                intent=tool_call.intent,
                resource_class=tool_call.resource_class,
                mission_context=mission_ctx,
                deny_reason=deny_reason,
                audit_trail=audit,
            )

        # --- Step 4: Evaluate OPA policies ---
        agent_ctx = mission_ctx.to_agent_context()
        policy_decision = self._opa.evaluate(agent_ctx, tool_call)

        if not policy_decision.allowed:
            audit.append(f"DENY (OPA policy={policy_decision.policy_name}): {policy_decision.reasons}")
            return RBACDecision(
                allowed=False,
                agent_id=agent_id,
                tenant_id=tenant_id,
                tool_name=tool_name,
                intent=tool_call.intent,
                resource_class=tool_call.resource_class,
                mission_context=mission_ctx,
                policy_decision=policy_decision,
                deny_reason="; ".join(policy_decision.reasons),
                audit_trail=audit,
            )

        # --- ALLOW ---
        audit.append(f"ALLOW: All policies passed for tool={tool_name} intent={tool_call.intent}")
        logger.info(
            f"[RBAC] ALLOW | agent={agent_id} tenant={tenant_id} tool={tool_name} "
            f"intent={tool_call.intent} phase={mission_ctx.mission_phase}"
        )
        return RBACDecision(
            allowed=True,
            agent_id=agent_id,
            tenant_id=tenant_id,
            tool_name=tool_name,
            intent=tool_call.intent,
            resource_class=tool_call.resource_class,
            mission_context=mission_ctx,
            policy_decision=policy_decision,
            audit_trail=audit,
        )


# Module-level singleton (initialized lazily)
_rbac_instance: Optional[AgentIntentRBAC] = None


async def get_intent_rbac() -> AgentIntentRBAC:
    global _rbac_instance
    if _rbac_instance is None:
        vault = await get_agent_session_vault()
        _rbac_instance = AgentIntentRBAC(vault=vault, opa=opa_bridge)
    return _rbac_instance
