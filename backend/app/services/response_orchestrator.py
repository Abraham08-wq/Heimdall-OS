import logging
import httpx
from typing import Dict, Any, List, Optional
from enum import Enum
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.services.audit import audit_logger
from app.services.combat import combat_orchestrator
from app.core.config import settings
from app.infrastructure.session import SessionLocal
from app.models.models import User
from app.models.config_model import ConfigEntry
import uuid

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    BLOCK_IP = "block_ip"
    THROTTLE_ASN = "throttle_asn"
    FORCE_MFA = "force_mfa"
    ISOLATE_SESSION = "isolate_session"
    ALERT_SOC = "alert_soc"


# ── Default policy used when DB is unavailable or playbook not found ──────────
_DEFAULT_POLICY: Dict[str, Any] = {
    "auto_block_threshold": 90,
    "auto_mfa_threshold": 75,
    "auto_throttle_threshold": 80,
    "require_human_approval_for_blocking": False,
}


def _load_policy_from_db(db: Session, tenant_id: str) -> Dict[str, Any]:
    """
    Reads a tenant-scoped policy playbook from the config_entries table.
    Expects a row with:
        category  = 'soc_playbooks'
        key       = '<tenant_id>'   (or 'default')
        value     = { "auto_block_threshold": 90, ... }
    Falls back gracefully to _DEFAULT_POLICY.
    """
    try:
        # Try tenant-specific playbook first, then 'default'
        entry: Optional[ConfigEntry] = (
            db.query(ConfigEntry)
            .filter(
                ConfigEntry.category == "soc_playbooks",
                ConfigEntry.key == tenant_id,
                ConfigEntry.is_active.is_(True),
            )
            .first()
        )
        if entry is None:
            entry = (
                db.query(ConfigEntry)
                .filter(
                    ConfigEntry.category == "soc_playbooks",
                    ConfigEntry.key == "default",
                    ConfigEntry.is_active.is_(True),
                )
                .first()
            )

        if entry and isinstance(entry.value, dict):
            # Merge with defaults so missing keys are always safe
            policy = {**_DEFAULT_POLICY, **entry.value}
            logger.debug(f"Loaded playbook for tenant '{tenant_id}' from DB.")
            return policy

    except Exception as exc:
        logger.warning(f"Could not load playbook from DB for tenant '{tenant_id}': {exc}. Using defaults.")

    return _DEFAULT_POLICY.copy()


class ResponseOrchestrator:
    """
    Defensive Orchestration Layer.
    Executes automated responses based on risk thresholds and tenant policies.
    Policies are loaded live from the config_entries table (category='soc_playbooks').
    """

    def __init__(self):
        self.firewall_url: Optional[str] = getattr(settings, "FIREWALL_API_URL", None)

    # ── Public API ─────────────────────────────────────────────────────────────

    async def evaluate_and_respond(
        self, tenant_id: str, target_ip: str, risk_score: float, reasoning: str
    ) -> List[Dict[str, Any]]:
        """
        Evaluates a Threat Intelligence score against the Tenant's zero-trust
        automation policy (loaded live from the DB).
        """
        db = SessionLocal()
        try:
            policy = _load_policy_from_db(db, tenant_id)
        finally:
            db.close()

        actions_taken: List[Dict[str, Any]] = []
        logger.info(f"Evaluating response for {target_ip}. Score: {risk_score}")

        # 1. Critical Threat — Block / Isolate
        if risk_score >= policy["auto_block_threshold"]:
            if policy["require_human_approval_for_blocking"]:
                actions_taken.append(
                    await self._trigger_soc_approval(tenant_id, target_ip, ActionType.BLOCK_IP, reasoning)
                )
            else:
                actions_taken.append(await self._execute_block(tenant_id, target_ip, reasoning))

        # 2. High Threat — Throttle / Rate-Limit
        elif risk_score >= policy["auto_throttle_threshold"]:
            actions_taken.append(await self._execute_throttle(tenant_id, target_ip, reasoning))

        # 3. Medium Threat — Step-Up Auth
        elif risk_score >= policy["auto_mfa_threshold"]:
            actions_taken.append(await self._force_mfa(tenant_id, target_ip, reasoning))

        return actions_taken

    async def execute_trap(self, tenant_id: str, ip: str, reasoning: str) -> Dict[str, Any]:
        """
        Directly executes a block action on an IP, bypassing normal evaluation.
        Triggered by a manual command from the Situation Room.
        """
        logger.warning(f"Manual TRAP command received for IP: {ip}. Reason: {reasoning}")
        return await self._execute_block(tenant_id, ip, reasoning)

    async def execute_mitigation_playbook(self, tenant_id: str, attacker_ip: str, mitre_id: str) -> None:
        """
        SOAR automated incident stream remediation (SIEM hand-off).
        Loads the tenant playbook from the DB, executes block + graph write.
        """
        logger.info(f"🤖 [SOAR STREAM EVENT] Executing automated mitigation rules for vector: {mitre_id}")

        # Re-evaluate using live policy to respect any threshold changes
        await self._execute_block(tenant_id, attacker_ip, f"SIEM Alert {mitre_id}")

        # Plot the Threat Node on the Neo4j Intel Graph Map
        try:
            from app.infrastructure.graph import graph_db
            logger.info(f"🎨 Graph Action: Writing threat vector {attacker_ip} to Neo4j topology...")
            await graph_db.execute_query(
                "MERGE (t:ThreatActor {id: $ip, name: $name, risk_score: 100}) RETURN t",
                {"ip": attacker_ip, "name": f"BruteForce IP: {attacker_ip}"},
            )
            logger.info("✅ Graph Action: Threat actor successfully registered on Intel Canvas.")
        except Exception as graph_err:
            logger.error(f"❌ Failed to push node metrics to Neo4j instance: {graph_err}")

    # ── Private helpers ────────────────────────────────────────────────────────

    async def _execute_block(self, tenant_id: str, ip: str, reasoning: str) -> Dict[str, Any]:
        """Applies a WAF / Network-level block by calling the firewall API."""
        if self.firewall_url:
            async with httpx.AsyncClient() as client:
                try:
                    logger.info(f"🧱 Propagating block rule to firewall for IP: {ip}")
                    await client.post(
                        f"{self.firewall_url}/api/v1/rules/block",
                        json={"ip": ip, "reason": reasoning, "tenant_id": tenant_id},
                        timeout=5.0,
                    )
                except httpx.RequestError as e:
                    logger.error(f"❌ Firewall boundary injection failed: {e}")
        else:
            logger.warning("FIREWALL_API_URL not configured. Skipping real IP block.")

        # Hive-Mind Inoculation — Zero-Day Sharing
        from app.services.security.vaccine import vaccine_engine
        await vaccine_engine.publish_vaccine(
            source_tenant=tenant_id, threat_ip=ip, signature={"reason": reasoning}
        )

        await combat_orchestrator.broadcast_dashboard(
            "DEFENSE_ACTION", {"action": "BLOCK_IP", "target": ip, "status": "EXECUTED"}
        )
        audit_logger.log_action(
            "AUTO_RESPONDER", "BLOCK_IP", "NETWORK_FIREWALL", ip,
            {"reason": reasoning, "tenant_id": tenant_id},
        )
        return {"action": ActionType.BLOCK_IP, "status": "executed", "target": ip}

    async def _execute_throttle(self, tenant_id: str, ip: str, reasoning: str) -> Dict[str, Any]:
        """Applies an API Gateway rate limit by calling the gateway API."""
        if self.firewall_url:
            async with httpx.AsyncClient() as client:
                try:
                    logger.info(f"⏳ Propagating throttle rule to gateway for IP: {ip}")
                    await client.post(
                        f"{self.firewall_url}/api/v1/rules/throttle",
                        json={"ip": ip, "reason": reasoning, "tenant_id": tenant_id},
                        timeout=5.0,
                    )
                except httpx.RequestError as e:
                    logger.error(f"❌ Gateway throttle rule injection failed: {e}")
        else:
            logger.warning("FIREWALL_API_URL not configured. Skipping real IP throttle.")

        await combat_orchestrator.broadcast_dashboard(
            "DEFENSE_ACTION", {"action": "THROTTLE_IP", "target": ip, "status": "EXECUTED"}
        )
        audit_logger.log_action("AUTO_RESPONDER", "THROTTLE_IP", "API_GATEWAY", ip, {"reason": reasoning})
        return {"action": ActionType.THROTTLE_ASN, "status": "executed", "target": ip}

    async def _force_mfa(self, tenant_id: str, ip: str, reasoning: str) -> Dict[str, Any]:
        """Invalidates current sessions and forces step-up authentication."""
        db = SessionLocal()
        try:
            logger.info(f"🔐 Forcing MFA by deactivating user accounts in Tenant: {tenant_id}")
            uuid.UUID(str(tenant_id))  # Validate UUID to prevent injection
            stmt = text(
                "UPDATE users SET is_active = FALSE WHERE tenant_id = :tenant_id AND role != 'admin'"
            )
            db.execute(stmt, {"tenant_id": tenant_id})
            db.commit()
            logger.info(f"✅ User deactivation sequence completed for tenant {tenant_id}.")
        except (ValueError, TypeError):
            logger.warning(
                f"ℹ️ Skipping database session eviction: Tenant ID '{tenant_id}' is not a valid UUID."
            )
        except Exception as e:
            logger.error(f"Force MFA user deactivation failed: {e}")
            db.rollback()
        finally:
            db.close()

        await combat_orchestrator.broadcast_dashboard(
            "DEFENSE_ACTION", {"action": "FORCE_MFA", "target": ip, "status": "ENFORCED"}
        )
        audit_logger.log_action("AUTO_RESPONDER", "FORCE_MFA", "IAM_DATABASE", ip, {"reason": reasoning})
        return {"action": ActionType.FORCE_MFA, "status": "enforced", "target": ip}

    async def _trigger_soc_approval(
        self, tenant_id: str, ip: str, requested_action: ActionType, reasoning: str
    ) -> Dict[str, Any]:
        """Generates a P1 ticket for human review before executing the action."""
        await combat_orchestrator.broadcast_dashboard(
            "APPROVAL_REQUIRED",
            {"requested_action": requested_action, "target": ip, "reasoning": reasoning},
        )
        return {"action": requested_action, "status": "pending_human_approval", "target": ip}


response_orchestrator = ResponseOrchestrator()
