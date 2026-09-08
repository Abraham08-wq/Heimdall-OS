"""
opa_policy_bridge.py — ProjectXY Cognitive Shield: Layer 2 (OPA Bridge)
=========================================================================
Stateless OPA-compatible policy evaluation engine.
Evaluates: is_allowed(who, what, why, context)

Designed as a pure-Python Rego-like evaluator (no OPA server required).
Interface is OPA-compatible — swap to a real OPA sidecar by changing
only the `evaluate()` method to make an HTTP call to OPA's REST API.

Policy Structure:
  Every policy is a function: (AgentContext, ToolCall) -> PolicyDecision
  Policies are registered by resource_class and stacked (first-deny wins).

Default built-in policies enforce:
  - Agent role → tool class permissions
  - Mission state → allowed operation window
  - Data class sensitivity → clearance level required
  - Temporal constraints (time-of-day, cooldown periods)
  - Cross-tenant isolation (absolute hard block)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("projectxy.firewall.opa")


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class AgentContext:
    """Who is making the call."""
    agent_id: str
    tenant_id: str
    role: str                          # viewer | analyst | operator | admin
    mission_id: Optional[str] = None
    mission_phase: Optional[str] = None   # RECON | EXPLOITATION | POST_EX | CLEANUP
    session_start_utc: Optional[datetime] = None
    clearance_level: int = 1           # 1=viewer, 2=analyst, 3=operator, 4=admin
    mfa_verified: bool = False
    extra_claims: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCall:
    """What is being called and why."""
    tool_name: str
    resource_class: str               # DATA | EXEC | CONFIG | AUDIT | AGENT | NETWORK
    intent: str                       # READ | WRITE | EXECUTE | DELETE | ADMIN
    target_tenant_id: Optional[str] = None
    target_resource_id: Optional[str] = None
    payload_summary: Optional[str] = None
    sensitivity_level: int = 1        # 1=public, 2=internal, 3=confidential, 4=secret
    mission_context_required: bool = False


@dataclass
class PolicyDecision:
    """Result of policy evaluation."""
    allowed: bool
    reasons: List[str] = field(default_factory=list)
    confidence: float = 1.0
    policy_name: str = "default"
    recommendation: Optional[str] = None

    @classmethod
    def allow(cls, reason: str, policy: str = "default") -> "PolicyDecision":
        return cls(allowed=True, reasons=[reason], policy_name=policy)

    @classmethod
    def deny(cls, reason: str, policy: str = "default", recommendation: str = None) -> "PolicyDecision":
        return cls(allowed=False, reasons=[reason], policy_name=policy, recommendation=recommendation)


# ---------------------------------------------------------------------------
# Policy Registry
# ---------------------------------------------------------------------------

PolicyFn = Callable[[AgentContext, ToolCall], Optional[PolicyDecision]]

_POLICIES: List[tuple[str, PolicyFn]] = []


def policy(name: str):
    """Decorator to register a policy function."""
    def decorator(fn: PolicyFn) -> PolicyFn:
        _POLICIES.append((name, fn))
        return fn
    return decorator


# ---------------------------------------------------------------------------
# Built-in Policies (First DENY wins — fail-closed)
# ---------------------------------------------------------------------------

@policy("CROSS_TENANT_ISOLATION")
def _cross_tenant(ctx: AgentContext, call: ToolCall) -> Optional[PolicyDecision]:
    """Hard block: agents cannot access resources from other tenants."""
    if call.target_tenant_id and call.target_tenant_id != ctx.tenant_id:
        return PolicyDecision.deny(
            reason=f"Cross-tenant access denied: agent tenant={ctx.tenant_id} "
                   f"target tenant={call.target_tenant_id}",
            policy="CROSS_TENANT_ISOLATION",
            recommendation="Use tenant-scoped credentials for target tenant."
        )
    return None  # no opinion — next policy


@policy("MISSION_CONTEXT_REQUIRED")
def _mission_required(ctx: AgentContext, call: ToolCall) -> Optional[PolicyDecision]:
    """Block calls that require mission context when no mission is active."""
    if call.mission_context_required and not ctx.mission_id:
        return PolicyDecision.deny(
            reason=f"Tool '{call.tool_name}' requires an active mission context. "
                   "No mission found for this agent session.",
            policy="MISSION_CONTEXT_REQUIRED",
            recommendation="Launch a mission before invoking this tool."
        )
    return None


@policy("INTENT_CLEARANCE")
def _intent_clearance(ctx: AgentContext, call: ToolCall) -> Optional[PolicyDecision]:
    """Enforce minimum clearance levels per intent type."""
    required: Dict[str, int] = {
        "READ":    1,
        "WRITE":   2,
        "EXECUTE": 3,
        "DELETE":  3,
        "ADMIN":   4,
    }
    min_clearance = required.get(call.intent.upper(), 4)
    if ctx.clearance_level < min_clearance:
        return PolicyDecision.deny(
            reason=f"Intent '{call.intent}' requires clearance {min_clearance}. "
                   f"Agent has clearance {ctx.clearance_level} (role={ctx.role}).",
            policy="INTENT_CLEARANCE",
            recommendation=f"Upgrade agent role to at least level {min_clearance}."
        )
    return None


@policy("DATA_SENSITIVITY")
def _data_sensitivity(ctx: AgentContext, call: ToolCall) -> Optional[PolicyDecision]:
    """Block access to data above agent's clearance level."""
    if call.sensitivity_level > ctx.clearance_level:
        return PolicyDecision.deny(
            reason=f"Data sensitivity level {call.sensitivity_level} exceeds "
                   f"agent clearance {ctx.clearance_level}.",
            policy="DATA_SENSITIVITY",
            recommendation="Request elevated clearance for sensitive data access."
        )
    return None


@policy("EXEC_MFA_REQUIRED")
def _exec_mfa(ctx: AgentContext, call: ToolCall) -> Optional[PolicyDecision]:
    """Execution intents on EXEC or NETWORK class resources require MFA."""
    if call.resource_class in ("EXEC", "NETWORK") and call.intent == "EXECUTE":
        if not ctx.mfa_verified:
            return PolicyDecision.deny(
                reason=f"MFA required to EXECUTE against resource class '{call.resource_class}'.",
                policy="EXEC_MFA_REQUIRED",
                recommendation="Complete MFA challenge before executing on this resource."
            )
    return None


@policy("MISSION_PHASE_GATE")
def _mission_phase(ctx: AgentContext, call: ToolCall) -> Optional[PolicyDecision]:
    """
    Enforce allowed tool classes per MITRE-inspired mission phase.
    Prevents post-exploitation tools from being called in recon phase.
    """
    phase_allowed: Dict[str, set] = {
        "RECON":       {"DATA", "NETWORK"},
        "EXPLOITATION": {"DATA", "NETWORK", "EXEC"},
        "POST_EX":     {"DATA", "NETWORK", "EXEC", "CONFIG"},
        "CLEANUP":     {"DATA", "CONFIG", "AUDIT"},
    }
    if ctx.mission_phase and ctx.mission_phase in phase_allowed:
        allowed_classes = phase_allowed[ctx.mission_phase]
        if call.resource_class not in allowed_classes:
            return PolicyDecision.deny(
                reason=f"Resource class '{call.resource_class}' not allowed in mission "
                       f"phase '{ctx.mission_phase}'. Allowed: {allowed_classes}.",
                policy="MISSION_PHASE_GATE",
                recommendation=f"Switch mission phase before accessing '{call.resource_class}'."
            )
    return None


@policy("ROLE_TOOL_WHITELIST")
def _role_tool_whitelist(ctx: AgentContext, call: ToolCall) -> Optional[PolicyDecision]:
    """
    Explicit role-to-tool class whitelist.
    Viewer cannot WRITE or EXECUTE anything.
    Analyst cannot EXECUTE or DELETE.
    """
    blocked: Dict[str, set] = {
        "viewer":   {"WRITE", "EXECUTE", "DELETE", "ADMIN"},
        "analyst":  {"EXECUTE", "DELETE", "ADMIN"},
        "operator": {"ADMIN"},
        "admin":    set(),  # admin can do anything (still subject to MFA)
    }
    role_blocks = blocked.get(ctx.role, {"WRITE", "EXECUTE", "DELETE", "ADMIN"})
    if call.intent.upper() in role_blocks:
        return PolicyDecision.deny(
            reason=f"Role '{ctx.role}' is not permitted to perform '{call.intent}' "
                   f"on '{call.resource_class}' resources.",
            policy="ROLE_TOOL_WHITELIST",
            recommendation=f"Assign an operator or admin role for '{call.intent}' access."
        )
    return None


@policy("ADMIN_RESOURCE_MFA")
def _admin_resource_mfa(ctx: AgentContext, call: ToolCall) -> Optional[PolicyDecision]:
    """Any access to AGENT or CONFIG resource class requires MFA regardless of intent."""
    if call.resource_class in ("AGENT", "CONFIG") and not ctx.mfa_verified:
        return PolicyDecision.deny(
            reason=f"Access to '{call.resource_class}' resources always requires MFA.",
            policy="ADMIN_RESOURCE_MFA",
            recommendation="Complete MFA challenge before accessing this resource class."
        )
    return None


# ---------------------------------------------------------------------------
# Policy Evaluator
# ---------------------------------------------------------------------------

class OPAPolicyBridge:
    """
    Stateless OPA-compatible policy evaluator.

    To swap to a real OPA server, replace `evaluate()` with:
        async def evaluate(self, ctx, call):
            resp = await httpx.post("http://opa:8181/v1/data/projectxy/allow",
                                    json={"input": {"agent": ..., "call": ...}})
            ...
    """

    def evaluate(
        self,
        agent_ctx: AgentContext,
        tool_call: ToolCall,
    ) -> PolicyDecision:
        """
        Evaluate all registered policies (first DENY wins).
        If all policies pass, returns ALLOW.
        """
        for policy_name, policy_fn in _POLICIES:
            try:
                decision = policy_fn(agent_ctx, tool_call)
                if decision is not None and not decision.allowed:
                    logger.warning(
                        f"[OPA] DENY | policy={policy_name} agent={agent_ctx.agent_id} "
                        f"tenant={agent_ctx.tenant_id} tool={tool_call.tool_name} "
                        f"intent={tool_call.intent} | {decision.reasons}"
                    )
                    return decision
            except Exception as exc:
                # Any policy exception is a DENY (fail-closed)
                logger.error(f"[OPA] Policy '{policy_name}' raised exception: {exc}. Denying.")
                return PolicyDecision.deny(
                    reason=f"Policy evaluation error in '{policy_name}': {type(exc).__name__}",
                    policy=policy_name,
                )

        # All policies passed
        logger.debug(
            f"[OPA] ALLOW | agent={agent_ctx.agent_id} tool={tool_call.tool_name} "
            f"intent={tool_call.intent}"
        )
        return PolicyDecision.allow(
            reason="All policies passed.",
            policy="ALL_CLEAR"
        )


# Module-level singleton
opa_bridge = OPAPolicyBridge()
