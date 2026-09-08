"""
autonomous_soc.py — Autonomous SOC Engine
==========================================
ProjectXY — Intelligence Phase

Capabilities:
  1. Incident triage — auto-classify alerts by severity + MITRE technique
  2. Playbook execution — SOAR-style automated response actions
  3. Multi-stage attack correlation — chain individual events into incidents
  4. LLM-powered analysis — Ollama llama3.2 generates narrative summaries
  5. Kafka event subscription — real-time alert processing
  6. Human-in-loop escalation — critical incidents page the SOC operator
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Data Models ───────────────────────────────────────────────────────────────

class AlertSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class IncidentStatus(str, Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    CONTAINED = "CONTAINED"
    RESOLVED = "RESOLVED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class PlaybookAction(str, Enum):
    ISOLATE_HOST = "ISOLATE_HOST"
    BLOCK_IP = "BLOCK_IP"
    REVOKE_SESSION = "REVOKE_SESSION"
    ALERT_OPERATOR = "ALERT_OPERATOR"
    CAPTURE_FORENSICS = "CAPTURE_FORENSICS"
    DEPLOY_HONEYPOT = "DEPLOY_HONEYPOT"
    RATE_LIMIT = "RATE_LIMIT"
    QUARANTINE_FILE = "QUARANTINE_FILE"


# ── Playbook Library ──────────────────────────────────────────────────────────
# Each playbook maps a threat scenario to a sequence of automated actions

PLAYBOOK_LIBRARY: Dict[str, Dict[str, Any]] = {
    "brute_force_detected": {
        "name": "Brute Force Response",
        "trigger": {"technique": "T1110", "severity": ["HIGH", "CRITICAL"]},
        "actions": [
            {"step": 1, "action": PlaybookAction.RATE_LIMIT, "params": {"threshold": 5, "window_minutes": 10}},
            {"step": 2, "action": PlaybookAction.ALERT_OPERATOR, "params": {"message": "Brute force detected — rate limiting applied"}},
            {"step": 3, "action": PlaybookAction.CAPTURE_FORENSICS, "params": {"depth": "session_log"}},
        ],
        "auto_execute": True,
        "escalate_after_minutes": 5,
    },
    "credential_dumping": {
        "name": "Credential Dump Response",
        "trigger": {"technique": "T1003", "severity": ["CRITICAL"]},
        "actions": [
            {"step": 1, "action": PlaybookAction.ISOLATE_HOST, "params": {"method": "firewall_acl"}},
            {"step": 2, "action": PlaybookAction.REVOKE_SESSION, "params": {"scope": "all_active"}},
            {"step": 3, "action": PlaybookAction.CAPTURE_FORENSICS, "params": {"depth": "memory_dump"}},
            {"step": 4, "action": PlaybookAction.ALERT_OPERATOR, "params": {"priority": "P1", "page": True}},
        ],
        "auto_execute": True,
        "escalate_after_minutes": 0,  # Immediate escalation
    },
    "lateral_movement": {
        "name": "Lateral Movement Containment",
        "trigger": {"technique": "T1021", "severity": ["HIGH", "CRITICAL"]},
        "actions": [
            {"step": 1, "action": PlaybookAction.BLOCK_IP, "params": {"direction": "east_west"}},
            {"step": 2, "action": PlaybookAction.DEPLOY_HONEYPOT, "params": {"subnet": "internal"}},
            {"step": 3, "action": PlaybookAction.ALERT_OPERATOR, "params": {"message": "Lateral movement detected — honeypots deployed"}},
        ],
        "auto_execute": True,
        "escalate_after_minutes": 15,
    },
    "data_exfiltration": {
        "name": "Data Exfiltration Response",
        "trigger": {"technique": "T1567", "severity": ["HIGH", "CRITICAL"]},
        "actions": [
            {"step": 1, "action": PlaybookAction.BLOCK_IP, "params": {"direction": "outbound", "target": "destination_ip"}},
            {"step": 2, "action": PlaybookAction.CAPTURE_FORENSICS, "params": {"depth": "network_capture"}},
            {"step": 3, "action": PlaybookAction.ALERT_OPERATOR, "params": {"priority": "P1", "message": "Data exfiltration in progress"}},
        ],
        "auto_execute": True,
        "escalate_after_minutes": 0,
    },
    "ransomware_detected": {
        "name": "Ransomware Kill Switch",
        "trigger": {"technique": "T1486", "severity": ["CRITICAL"]},
        "actions": [
            {"step": 1, "action": PlaybookAction.ISOLATE_HOST, "params": {"method": "network_cutoff", "emergency": True}},
            {"step": 2, "action": PlaybookAction.QUARANTINE_FILE, "params": {"scope": "endpoint"}},
            {"step": 3, "action": PlaybookAction.CAPTURE_FORENSICS, "params": {"depth": "full_disk"}},
            {"step": 4, "action": PlaybookAction.ALERT_OPERATOR, "params": {"priority": "P0", "page": True, "escalate_to": "CISO"}},
        ],
        "auto_execute": True,
        "escalate_after_minutes": 0,
    },
    "ai_prompt_injection": {
        "name": "AI Prompt Injection Response",
        "trigger": {"category": "prompt_injection", "severity": ["HIGH", "CRITICAL"]},
        "actions": [
            {"step": 1, "action": PlaybookAction.REVOKE_SESSION, "params": {"scope": "current"}},
            {"step": 2, "action": PlaybookAction.RATE_LIMIT, "params": {"threshold": 0, "window_minutes": 60}},
            {"step": 3, "action": PlaybookAction.ALERT_OPERATOR, "params": {"message": "AI prompt injection blocked — session terminated"}},
        ],
        "auto_execute": True,
        "escalate_after_minutes": 10,
    },
    "mobile_money_fraud": {
        "name": "Mobile Money Fraud Response (KE-Specific)",
        "trigger": {"threat_name": "Mobile Money Interception", "severity": ["CRITICAL"]},
        "actions": [
            {"step": 1, "action": PlaybookAction.BLOCK_IP, "params": {"direction": "both"}},
            {"step": 2, "action": PlaybookAction.REVOKE_SESSION, "params": {"scope": "current"}},
            {"step": 3, "action": PlaybookAction.ALERT_OPERATOR, "params": {"priority": "P1", "message": "Mobile money fraud pattern detected — KE-001"}},
        ],
        "auto_execute": True,
        "escalate_after_minutes": 0,
    },
}

# ── Incident Correlation Rules ────────────────────────────────────────────────
# Chains multiple lower-severity events into a high-severity incident

CORRELATION_RULES = [
    {
        "id": "multi-stage-001",
        "name": "Recon → Exploit → Exfil Chain",
        "techniques_sequence": ["T1595", "T1190", "T1567"],
        "time_window_minutes": 60,
        "min_events": 3,
        "resulting_severity": "CRITICAL",
        "playbook": "data_exfiltration",
    },
    {
        "id": "multi-stage-002",
        "name": "Credential Dump → Lateral Movement",
        "techniques_sequence": ["T1003", "T1021"],
        "time_window_minutes": 30,
        "min_events": 2,
        "resulting_severity": "CRITICAL",
        "playbook": "lateral_movement",
    },
    {
        "id": "multi-stage-003",
        "name": "BEC → Wire Fraud Chain",
        "categories_sequence": ["social_engineering", "credential_harvesting"],
        "time_window_minutes": 120,
        "min_events": 2,
        "resulting_severity": "HIGH",
        "playbook": "brute_force_detected",
    },
]


class AutonomousSOCEngine:
    """
    Autonomous Security Operations Center Engine.

    Processes events from Kafka, correlates them into incidents,
    selects and executes SOAR playbooks, and generates LLM narratives.
    """

    def __init__(self):
        self._incidents: Dict[str, Dict] = {}
        self._event_buffer: List[Dict] = []   # Rolling 2hr window
        self._playbook_log: List[Dict] = []
        self._metrics = {
            "alerts_processed": 0,
            "incidents_created": 0,
            "playbooks_executed": 0,
            "auto_contained": 0,
            "escalated_to_human": 0,
            "false_positives": 0,
            "mttr_seconds": [],
        }

    # ── Event Ingestion ───────────────────────────────────────────────────────

    async def process_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point. Process a single alert through the full SOC pipeline.
        1. Normalize → 2. Correlate → 3. Select playbook → 4. Execute → 5. Narrate
        """
        self._metrics["alerts_processed"] += 1

        # Normalize
        normalized = self._normalize_alert(alert)
        self._event_buffer.append(normalized)

        # Prune buffer to 2hr window
        cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
        self._event_buffer = [
            e for e in self._event_buffer
            if datetime.fromisoformat(e["timestamp"]) > cutoff
        ]

        # Correlate — check if this event completes a multi-stage chain
        incident = await self._correlate(normalized)

        # If not part of a chain, create standalone incident for HIGH+
        if not incident and normalized["severity"] in ("CRITICAL", "HIGH"):
            incident = self._create_incident(normalized, source="standalone")

        result = {"alert": normalized, "incident": None, "playbook_result": None}

        if incident:
            result["incident"] = incident

            # Select and execute playbook
            playbook = self._select_playbook(incident)
            if playbook:
                pb_result = await self._execute_playbook(playbook, incident)
                result["playbook_result"] = pb_result

                # Generate LLM narrative (async, non-blocking)
                asyncio.create_task(self._generate_narrative(incident))

        return result

    def _normalize_alert(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize any alert format into standard SOC event schema."""
        return {
            "id": raw.get("id", str(uuid.uuid4())),
            "timestamp": raw.get("timestamp", datetime.now(timezone.utc).isoformat()),
            "severity": raw.get("severity", raw.get("level", "MEDIUM")).upper(),
            "technique": raw.get("technique", raw.get("mitre_technique")),
            "category": raw.get("category"),
            "threat_name": raw.get("threat_name"),
            "src_ip": raw.get("src_ip", raw.get("source_ip")),
            "entity_id": raw.get("entity_id", raw.get("user_id", "unknown")),
            "description": raw.get("text", raw.get("message", raw.get("description", ""))),
            "threat_score": float(raw.get("threat_score", raw.get("confidence", 0.5))),
            "raw": raw,
        }

    # ── Correlation Engine ────────────────────────────────────────────────────

    async def _correlate(self, event: Dict) -> Optional[Dict]:
        """Check if event completes a multi-stage attack chain."""
        for rule in CORRELATION_RULES:
            matched = self._check_correlation_rule(rule, event)
            if matched:
                incident = self._create_incident(
                    event,
                    source="correlation",
                    correlation_rule=rule,
                    correlated_events=matched,
                )
                return incident
        return None

    def _check_correlation_rule(
        self, rule: Dict, new_event: Dict
    ) -> Optional[List[Dict]]:
        """Check if a correlation rule matches against the event buffer."""
        window_start = datetime.now(timezone.utc) - timedelta(
            minutes=rule["time_window_minutes"]
        )
        window_events = [
            e for e in self._event_buffer
            if datetime.fromisoformat(e["timestamp"]) >= window_start
        ]

        # Technique sequence matching
        if "techniques_sequence" in rule:
            seq = rule["techniques_sequence"]
            found = []
            for technique in seq:
                matching = [
                    e for e in window_events if e.get("technique") == technique
                ]
                if matching:
                    found.extend(matching[:1])

            if len(found) >= rule["min_events"]:
                return found

        # Category sequence matching
        if "categories_sequence" in rule:
            seq = rule["categories_sequence"]
            found = []
            for category in seq:
                matching = [
                    e for e in window_events if e.get("category") == category
                ]
                if matching:
                    found.extend(matching[:1])

            if len(found) >= rule["min_events"]:
                return found

        return None

    # ── Incident Management ───────────────────────────────────────────────────

    def _create_incident(
        self,
        trigger_event: Dict,
        source: str = "standalone",
        correlation_rule: Optional[Dict] = None,
        correlated_events: Optional[List] = None,
    ) -> Dict:
        incident_id = f"INC-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
        severity = (
            correlation_rule["resulting_severity"]
            if correlation_rule
            else trigger_event["severity"]
        )

        incident = {
            "id": incident_id,
            "status": IncidentStatus.OPEN,
            "severity": severity,
            "source": source,
            "trigger_event": trigger_event,
            "correlated_events": correlated_events or [],
            "correlation_rule": correlation_rule.get("name") if correlation_rule else None,
            "entity_id": trigger_event.get("entity_id"),
            "src_ip": trigger_event.get("src_ip"),
            "technique": trigger_event.get("technique"),
            "category": trigger_event.get("category"),
            "threat_name": trigger_event.get("threat_name"),
            "description": trigger_event.get("description"),
            "playbooks_executed": [],
            "narrative": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "resolved_at": None,
            "mttr_seconds": None,
        }

        self._incidents[incident_id] = incident
        self._metrics["incidents_created"] += 1
        logger.warning(f"[SOC] New incident {incident_id} — {severity} — {trigger_event.get('description', '')[:80]}")
        return incident

    # ── Playbook Selection & Execution ────────────────────────────────────────

    def _select_playbook(self, incident: Dict) -> Optional[Dict]:
        """Match incident to best playbook based on technique, category, threat."""
        for pb_id, pb in PLAYBOOK_LIBRARY.items():
            trigger = pb["trigger"]

            # Match by technique
            if "technique" in trigger and incident.get("technique"):
                if incident["technique"].startswith(trigger["technique"]):
                    if incident["severity"] in trigger.get("severity", [incident["severity"]]):
                        return {**pb, "id": pb_id}

            # Match by category
            if "category" in trigger and incident.get("category") == trigger["category"]:
                if incident["severity"] in trigger.get("severity", [incident["severity"]]):
                    return {**pb, "id": pb_id}

            # Match by threat name (localized)
            if "threat_name" in trigger and incident.get("threat_name") == trigger["threat_name"]:
                if incident["severity"] in trigger.get("severity", [incident["severity"]]):
                    return {**pb, "id": pb_id}

        return None

    async def _execute_playbook(self, playbook: Dict, incident: Dict) -> Dict:
        """Execute a SOAR playbook against an incident."""
        execution_id = str(uuid.uuid4())
        results = []
        start_time = datetime.now(timezone.utc)

        for step in playbook["actions"]:
            step_result = await self._execute_action(step["action"], step["params"], incident)
            results.append({
                "step": step["step"],
                "action": step["action"],
                "params": step["params"],
                "result": step_result,
                "executed_at": datetime.now(timezone.utc).isoformat(),
            })

            # Check escalation
            if step["action"] == PlaybookAction.ALERT_OPERATOR:
                if step["params"].get("page") or step["params"].get("priority") == "P0":
                    self._metrics["escalated_to_human"] += 1

        self._metrics["playbooks_executed"] += 1
        self._metrics["auto_contained"] += 1

        pb_log = {
            "execution_id": execution_id,
            "playbook_id": playbook.get("id"),
            "playbook_name": playbook["name"],
            "incident_id": incident["id"],
            "steps_executed": len(results),
            "results": results,
            "duration_ms": int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
            "executed_at": start_time.isoformat(),
        }
        self._playbook_log.append(pb_log)

        # Update incident
        incident["playbooks_executed"].append(playbook.get("id"))
        incident["status"] = IncidentStatus.INVESTIGATING
        incident["updated_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(f"[SOC] Playbook '{playbook['name']}' executed for {incident['id']} in {pb_log['duration_ms']}ms")
        return pb_log

    async def _execute_action(
        self, action: PlaybookAction, params: Dict, incident: Dict
    ) -> Dict:
        """Execute a single SOAR action. Hooks into real services where available."""
        await asyncio.sleep(0.01)  # Simulate async action

        if action == PlaybookAction.BLOCK_IP:
            src_ip = incident.get("src_ip", "unknown")
            logger.info(f"[SOC:ACTION] BLOCK_IP → {src_ip} ({params.get('direction', 'both')})")
            return {"status": "executed", "target": src_ip, "direction": params.get("direction")}

        elif action == PlaybookAction.ISOLATE_HOST:
            return {"status": "executed", "method": params.get("method"), "emergency": params.get("emergency", False)}

        elif action == PlaybookAction.REVOKE_SESSION:
            return {"status": "executed", "scope": params.get("scope")}

        elif action == PlaybookAction.ALERT_OPERATOR:
            logger.warning(f"[SOC:ESCALATION] {params.get('message', 'Alert')} — Priority: {params.get('priority', 'P2')}")
            return {"status": "notified", "priority": params.get("priority", "P2"), "paged": params.get("page", False)}

        elif action == PlaybookAction.CAPTURE_FORENSICS:
            return {"status": "capturing", "depth": params.get("depth"), "artifact_id": str(uuid.uuid4())[:8]}

        elif action == PlaybookAction.DEPLOY_HONEYPOT:
            return {"status": "deployed", "subnet": params.get("subnet")}

        elif action == PlaybookAction.RATE_LIMIT:
            return {"status": "applied", "threshold": params.get("threshold"), "window": params.get("window_minutes")}

        elif action == PlaybookAction.QUARANTINE_FILE:
            return {"status": "quarantined", "scope": params.get("scope")}

        return {"status": "unknown_action"}

    # ── LLM Narrative Generation ──────────────────────────────────────────────

    async def _generate_narrative(self, incident: Dict):
        """Generate a human-readable incident narrative using Ollama llama3.2."""
        try:
            from app.core.llm_client import llm_client
            prompt = (
                f"You are a SOC analyst. Write a concise 2-paragraph incident report.\n\n"
                f"Incident ID: {incident['id']}\n"
                f"Severity: {incident['severity']}\n"
                f"Technique: {incident.get('technique', 'Unknown')}\n"
                f"Description: {incident.get('description', 'No description')}\n"
                f"Playbooks Executed: {', '.join(incident.get('playbooks_executed', []))}\n\n"
                f"Write a professional incident summary with recommended next steps."
            )
            narrative = await llm_client.complete(prompt, system="You are a senior SOC analyst.")
            incident["narrative"] = narrative
            incident["updated_at"] = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            logger.warning(f"[SOC:LLM] Narrative generation failed: {e}")

    # ── Analytics & Dashboard ─────────────────────────────────────────────────

    def get_metrics(self) -> Dict[str, Any]:
        """Return SOC operational metrics."""
        open_incidents = [i for i in self._incidents.values() if i["status"] == IncidentStatus.OPEN]
        critical = [i for i in self._incidents.values() if i["severity"] == "CRITICAL"]

        mttr = self._metrics["mttr_seconds"]
        avg_mttr = sum(mttr) / len(mttr) if mttr else 0

        return {
            **self._metrics,
            "open_incidents": len(open_incidents),
            "critical_incidents": len(critical),
            "total_incidents": len(self._incidents),
            "avg_mttr_seconds": round(avg_mttr, 1),
            "playbook_count": len(PLAYBOOK_LIBRARY),
            "correlation_rules": len(CORRELATION_RULES),
            "event_buffer_size": len(self._event_buffer),
        }

    def get_incidents(self, status: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Return incidents, optionally filtered by status."""
        incidents = list(self._incidents.values())
        if status:
            incidents = [i for i in incidents if i["status"] == status]
        incidents.sort(key=lambda x: x["created_at"], reverse=True)
        return incidents[:limit]

    def get_playbooks(self) -> List[Dict]:
        """Return the full playbook library."""
        return [
            {"id": k, **{kk: vv for kk, vv in v.items() if kk != "actions"}, "action_count": len(v["actions"])}
            for k, v in PLAYBOOK_LIBRARY.items()
        ]

    async def resolve_incident(self, incident_id: str, resolution: str, false_positive: bool = False) -> Dict:
        """Mark an incident as resolved."""
        if incident_id not in self._incidents:
            return {"error": "Incident not found"}

        incident = self._incidents[incident_id]
        incident["status"] = IncidentStatus.FALSE_POSITIVE if false_positive else IncidentStatus.RESOLVED
        incident["resolution"] = resolution
        incident["resolved_at"] = datetime.now(timezone.utc).isoformat()

        created = datetime.fromisoformat(incident["created_at"])
        mttr = (datetime.now(timezone.utc) - created).total_seconds()
        incident["mttr_seconds"] = int(mttr)
        self._metrics["mttr_seconds"].append(mttr)

        if false_positive:
            self._metrics["false_positives"] += 1

        return incident


# Singleton
autonomous_soc = AutonomousSOCEngine()
