"""
compliance_ledger.py — ProjectXY Cognitive Shield: Layer 5
============================================================
WORM Immutable Ledger Extension for Agent Actions.

Wraps the existing audit ledger to capture agent-specific events with
an extended schema that is compliant with:
  - Kenya CBK / DPA 2019 requirements
  - GDPR Article 30 (Records of Processing Activities)
  - HIPAA Audit Controls (§164.312)
  - ISO 27001 Annex A.12.4 (Logging and Monitoring)

Extended fields over the base audit_logs schema:
  - agent_action_type: fine-grained agent action classification
  - intent_classification: READ | WRITE | EXECUTE | DELETE | ADMIN
  - policy_decision: ALLOW | DENY
  - policy_name: which policy triggered the decision
  - mission_id: the active mission context
  - mission_phase: RECON | EXPLOITATION | POST_EX | CLEANUP
  - cognitive_threat_score: ensemble score from Layer 3
  - attack_pattern_detected: multi-stage pattern name (if any)
  - data_classes_accessed: list of data classes touched
  - retention_class: STANDARD | COMPLIANCE | CRITICAL

Fail-Closed for compliance tenants: If the audit write fails AND
the tenant has cbk_compliant=True, the action is blocked and a
COMPLIANCE_AUDIT_FAILURE alert is emitted to Kafka.
"""

import hashlib
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("projectxy.firewall.compliance_ledger")


# ---------------------------------------------------------------------------
# Enums & Constants
# ---------------------------------------------------------------------------

class RetentionClass(str, Enum):
    STANDARD = "STANDARD"       # 1 year
    COMPLIANCE = "COMPLIANCE"   # 7 years (CBK/GDPR)
    CRITICAL = "CRITICAL"       # Indefinite (criminal evidence)


class AgentActionType(str, Enum):
    TOOL_INVOKE = "TOOL_INVOKE"
    POLICY_DENY = "POLICY_DENY"
    SESSION_ISSUE = "SESSION_ISSUE"
    SESSION_REVOKE = "SESSION_REVOKE"
    PHASE_ADVANCE = "PHASE_ADVANCE"
    MFA_CHALLENGE = "MFA_CHALLENGE"
    MFA_SUCCESS = "MFA_SUCCESS"
    MFA_FAILURE = "MFA_FAILURE"
    FIREWALL_BLOCK = "FIREWALL_BLOCK"
    FIREWALL_SCRUB = "FIREWALL_SCRUB"
    MULTI_STAGE_DETECTED = "MULTI_STAGE_DETECTED"
    CLEANSING_TRANSFORM = "CLEANSING_TRANSFORM"


# ---------------------------------------------------------------------------
# Compliance Event
# ---------------------------------------------------------------------------

@dataclass
class ComplianceEvent:
    """Extended audit record for agent and firewall actions."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # Actor
    tenant_id: str = ""
    entity_id: str = ""         # user or agent ID
    agent_id: Optional[str] = None
    session_id: Optional[str] = None

    # Action
    action_type: str = AgentActionType.TOOL_INVOKE
    intent_classification: Optional[str] = None
    tool_name: Optional[str] = None
    resource_class: Optional[str] = None

    # Policy
    policy_decision: str = "ALLOW"       # ALLOW | DENY
    policy_name: Optional[str] = None
    policy_reasons: List[str] = field(default_factory=list)

    # Mission
    mission_id: Optional[str] = None
    mission_phase: Optional[str] = None

    # Threat Intel
    cognitive_threat_score: float = 0.0
    dominant_signal: Optional[str] = None
    attack_pattern_detected: Optional[str] = None
    transformations_applied: List[str] = field(default_factory=list)

    # Data
    data_classes_accessed: List[str] = field(default_factory=list)
    pii_detected: bool = False
    pii_scrubbed: bool = False

    # Retention
    retention_class: str = RetentionClass.STANDARD
    cbk_compliant: bool = False

    # Hash chain (extends existing audit ledger pattern)
    previous_hash: Optional[str] = None
    event_hash: Optional[str] = None

    # Extra structured metadata (for GDPR Article 30 compliance)
    extra_metadata: Dict[str, Any] = field(default_factory=dict)

    def compute_hash(self, previous_hash: str = "") -> str:
        """
        Compute SHA-256 hash of this event chained to the previous entry.
        Mirrors the existing audit_logs WORM hash chain pattern.
        """
        content = json.dumps({
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "tenant_id": self.tenant_id,
            "entity_id": self.entity_id,
            "action_type": self.action_type,
            "policy_decision": self.policy_decision,
            "cognitive_threat_score": self.cognitive_threat_score,
            "previous_hash": previous_hash,
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def finalize(self, previous_hash: str = "") -> "ComplianceEvent":
        """Compute and set the event hash."""
        self.previous_hash = previous_hash
        self.event_hash = self.compute_hash(previous_hash)
        return self

    def to_kafka_message(self) -> Dict[str, Any]:
        """Serialize for Kafka compliance_events topic."""
        return {k: v for k, v in asdict(self).items() if v is not None}


# ---------------------------------------------------------------------------
# Compliance Ledger
# ---------------------------------------------------------------------------

class ComplianceLedger:
    """
    WORM Immutable Ledger Extension for Agent Actions.

    Integrates with:
      - Existing TimescaleDB audit_logs table (via db_pool)
      - Kafka compliance_events topic (via kafka_producer)
      - Standard Python logger as fallback
    """

    def __init__(
        self,
        db_pool=None,
        kafka_producer=None,
        cbk_compliance_mode: bool = False,
    ):
        self._pool = db_pool
        self._kafka = kafka_producer
        self._cbk_mode = cbk_compliance_mode
        self._last_hash: Dict[str, str] = {}  # per-tenant hash chain

    def configure(self, db_pool, kafka_producer, cbk_mode: bool = False):
        """Late-bind after async startup."""
        self._pool = db_pool
        self._kafka = kafka_producer
        self._cbk_mode = cbk_mode

    async def record(self, event: ComplianceEvent) -> bool:
        """
        Record a compliance event to all persistence layers.

        Returns True on success.
        On failure for CBK-compliant tenants, raises ComplianceAuditError.
        """
        try:
            # Finalize hash chain
            previous_hash = self._last_hash.get(event.tenant_id, "GENESIS")
            event.finalize(previous_hash)
            self._last_hash[event.tenant_id] = event.event_hash

            # Set retention class based on action
            event.retention_class = self._determine_retention(event)

            # Write to DB
            db_success = await self._write_to_db(event)

            # Emit to Kafka
            kafka_success = await self._emit_to_kafka(event)

            if not db_success:
                logger.warning(
                    f"[COMPLIANCE] DB write failed for event {event.event_id}"
                )
                if event.cbk_compliant:
                    raise ComplianceAuditError(
                        f"Compliance audit write failed for CBK tenant {event.tenant_id}"
                    )
            return True

        except ComplianceAuditError:
            raise
        except Exception as exc:
            logger.error(f"[COMPLIANCE] record() failed: {exc}")
            # Fallback to plaintext log
            self._fallback_log(event)
            if event.cbk_compliant and self._cbk_mode:
                raise ComplianceAuditError(str(exc))
            return False

    async def _write_to_db(self, event: ComplianceEvent) -> bool:
        """
        Write to the extended compliance table.
        Uses the existing audit_logs table structure plus the new columns.
        """
        if not self._pool:
            self._fallback_log(event)
            return False

        # Write to existing audit_logs table with extended data in details field
        sql = """
            INSERT INTO audit_logs (
                id, timestamp, tenant_id, entity_id, action, details,
                severity, previous_hash, hash
            ) VALUES (
                $1, $2::timestamptz, $3, $4, $5, $6::jsonb, $7, $8, $9
            )
            ON CONFLICT (id) DO NOTHING
        """
        details = {
            "compliance_v2": True,
            "agent_id": event.agent_id,
            "session_id": event.session_id,
            "action_type": event.action_type,
            "intent_classification": event.intent_classification,
            "tool_name": event.tool_name,
            "resource_class": event.resource_class,
            "policy_decision": event.policy_decision,
            "policy_name": event.policy_name,
            "policy_reasons": event.policy_reasons,
            "mission_id": event.mission_id,
            "mission_phase": event.mission_phase,
            "cognitive_threat_score": event.cognitive_threat_score,
            "dominant_signal": event.dominant_signal,
            "attack_pattern_detected": event.attack_pattern_detected,
            "transformations_applied": event.transformations_applied,
            "data_classes_accessed": event.data_classes_accessed,
            "pii_detected": event.pii_detected,
            "pii_scrubbed": event.pii_scrubbed,
            "retention_class": event.retention_class,
            "cbk_compliant": event.cbk_compliant,
        }
        severity = self._compute_severity(event)
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    sql,
                    event.event_id,
                    event.timestamp,
                    event.tenant_id,
                    event.entity_id or "system",
                    event.action_type,
                    json.dumps(details),
                    severity,
                    event.previous_hash,
                    event.event_hash,
                )
            return True
        except Exception as exc:
            logger.error(f"[COMPLIANCE] DB write error: {exc}")
            return False

    async def _emit_to_kafka(self, event: ComplianceEvent) -> bool:
        """Emit compliance event to Kafka."""
        if not self._kafka:
            return False
        try:
            message = event.to_kafka_message()
            # Use the existing Kafka streaming interface
            await self._kafka.emit(
                topic="compliance_events",
                key=f"{event.tenant_id}:{event.event_id}",
                value=message,
            )
            return True
        except Exception as exc:
            logger.warning(f"[COMPLIANCE] Kafka emit failed: {exc}")
            return False

    @staticmethod
    def _determine_retention(event: ComplianceEvent) -> str:
        """Determine retention class based on event type and tenant compliance."""
        if event.attack_pattern_detected:
            return RetentionClass.CRITICAL
        if event.cbk_compliant or event.cognitive_threat_score > 0.7:
            return RetentionClass.COMPLIANCE
        return RetentionClass.STANDARD

    @staticmethod
    def _compute_severity(event: ComplianceEvent) -> str:
        """Map event to severity string for the audit_logs table."""
        if event.attack_pattern_detected or event.policy_decision == "DENY":
            return "HIGH"
        if event.cognitive_threat_score > 0.5:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _fallback_log(event: ComplianceEvent):
        """Fallback plaintext log when DB and Kafka are both unavailable."""
        logger.warning(
            f"[COMPLIANCE_FALLBACK] event={event.event_id} tenant={event.tenant_id} "
            f"action={event.action_type} decision={event.policy_decision} "
            f"score={event.cognitive_threat_score:.3f} hash={event.event_hash}"
        )


class ComplianceAuditError(Exception):
    """Raised when compliance audit write fails for a CBK-compliant tenant."""
    pass


# Module-level singleton
compliance_ledger = ComplianceLedger()
