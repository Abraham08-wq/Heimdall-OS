"""
threat_classifier.py — ProjectXY Phase 4 (UPGRADED): SIEM Dynamic Behavioral Classifier
==========================================================================================
Kafka consumer that processes real-time telemetry events from all Execution Nodes
and applies multi-signal AI threat classification. Queries Neo4j graph in real-time
to correlate isolated events into attack chains.

Architecture:
  Kafka Topics Consumed:
    • infrastructure_telemetry   — Node heartbeats, latency, endpoint hits
    • firewall_events            — AI Firewall verdicts and blocked prompts
    • ai_agent_telemetry         — AI swarm activity logs
    • mobile_session_events      — USSD/OTP/SIM session events from telco API

  Classification Signals:
    • Login failure rate           → Credential stuffing detection
    • API error entropy            → Scanner/fuzzer detection
    • Firewall block frequency     → Adversarial AI campaign detection
    • Graph correlations (Neo4j)   → Multi-stage APT chain detection
    • Geographic anomalies         → SIM swap / account takeover
    • Device identity velocity     → SIM swap + rapid login = critical threat
    • USSD session anomalies       → Concurrent USSD hijacking detection

  SOAR Triggers (CGNAT-Aware):
    • Risk ≥ 85 → Device fingerprint block + JWT revocation + webhook alert
                   (IP block AVOIDED for CGNAT mobile ranges)
    • Risk ≥ 65 → Rate-limit by device ID + SOC notification
    • Risk ≥ 40 → Elevated observation + audit log
    • SIM_SWAP + login within 15min → CRITICAL regardless of score

  SIM Swap Velocity Filter (NEW):
    If SIEM sees IMEI/IMSI change from telco API feed followed by any of:
      - Password reset request
      - Login attempt
      - M-Pesa PIN change
      - USSD session initiation
    …all within a 15-minute window, the Neo4j graph flags this as CRITICAL
    regardless of whether the password/OTP is correct.

CBK Compliance: All classifications are immutably logged.
"""
import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("projectxy.siem.classifier")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SIEM_CONFIG = {
    "kafka_bootstrap": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
    "kafka_group_id": "projectxy-siem-classifier",
    "consume_topics": [
        "infrastructure_telemetry",
        "firewall_events",
        "ai_agent_telemetry",
        "mobile_session_events",    # NEW: telco-sourced SIM/USSD events
    ],
    "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    "neo4j_uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    "neo4j_user": os.getenv("NEO4J_USER", "neo4j"),
    "neo4j_password": os.getenv("NEO4J_PASSWORD"),
    "soar_risk_block": 85.0,
    "soar_risk_ratelimit": 65.0,
    "soar_risk_observe": 40.0,
    "soar_webhook_url": os.getenv("SOAR_WEBHOOK_URL", ""),
    "block_duration_seconds": 86400,  # 24h block
    "rate_limit_rps": 2,
    "rate_limit_ttl": 3600,
    # SIM Swap Velocity Filter — window in seconds (15 minutes)
    "sim_swap_velocity_window": int(os.getenv("SIM_SWAP_VELOCITY_WINDOW_SECONDS", "900")),
    # CGNAT-safe: prefer device fingerprint over IP for containment
    "cgnat_safe_mode": os.getenv("CGNAT_SAFE_MODE", "true").lower() == "true",
}

# ---------------------------------------------------------------------------
# Graph Correlation Queries (Neo4j)
# ---------------------------------------------------------------------------

CYPHER_CORRELATED_THREAT = """
MATCH (ip:IPAddress {value: $ip_address})
OPTIONAL MATCH (ip)-[:ATTEMPTED]->(scan:ScanEvent)
  WHERE scan.timestamp > datetime() - duration({hours: 24})
OPTIONAL MATCH (ip)-[:FAILED_LOGIN]->(svc:Service)
  WHERE svc.timestamp > datetime() - duration({hours: 1})
OPTIONAL MATCH (ip)-[:TRIGGERED]->(fw:FirewallBlock)
  WHERE fw.timestamp > datetime() - duration({hours: 1})
RETURN
  COUNT(DISTINCT scan)    AS scan_count,
  COUNT(DISTINCT svc)     AS failed_login_count,
  COUNT(DISTINCT fw)      AS firewall_block_count
"""

CYPHER_UPSERT_THREAT_NODE = """
MERGE (ip:IPAddress {value: $ip_address})
ON CREATE SET ip.first_seen = datetime(), ip.risk_score = $risk
ON MATCH  SET ip.last_seen  = datetime(), ip.risk_score = $risk
MERGE (ev:ThreatEvent {id: $event_id})
ON CREATE SET
  ev.timestamp    = datetime(),
  ev.event_type   = $event_type,
  ev.risk_score   = $risk,
  ev.tenant_id    = $tenant_id
MERGE (ip)-[:TRIGGERED]->(ev)
"""

CYPHER_DETECT_APT_CHAIN = """
// Detect if this IP is part of a multi-stage APT chain
// Stage 1: Recon (scan) → Stage 2: Login brute-force → Stage 3: AI exfiltration
MATCH (ip:IPAddress {value: $ip_address})
MATCH (ip)-[:ATTEMPTED]->(:ScanEvent)
MATCH (ip)-[:FAILED_LOGIN]->(:Service)
MATCH (ip)-[:TRIGGERED]->(:FirewallBlock)
RETURN
  ip.value AS ip,
  ip.risk_score AS cumulative_risk,
  true AS is_apt_chain
LIMIT 1
"""

# ---------------------------------------------------------------------------
# SOAR Playbook Engine (CGNAT-Aware Upgrade)
# ---------------------------------------------------------------------------

class SOARPlaybook:
    """
    Automated Security Orchestration, Automation & Response.

    UPGRADE: Now CGNAT-aware. Containment actions prefer device fingerprints,
    JWT token IDs, and entity-level blocks over raw IP blocking. This prevents
    collateral damage to thousands of legitimate users sharing the same
    Safaricom/Airtel CGNAT egress IP.

    Priority order for containment:
      [1] Device fingerprint (most precise, zero CGNAT risk)
      [2] JWT Token ID revocation (session precision)
      [3] Entity ID isolation (account-level)
      [4] IP block (LAST RESORT — CGNAT circuit-breaker active)
    """

    def __init__(self, redis_client, webhook_url: str = ""):
        self._redis = redis_client
        self._webhook_url = webhook_url

    async def execute(
        self,
        entity_id: str,
        ip_address: str,
        risk_score: float,
        reasons: List[str],
        tenant_id: str = "default",
        device_fingerprint: Optional[str] = None,
        jwt_jti: Optional[str] = None,
        is_sim_swap: bool = False,
        old_device_fingerprint: Optional[str] = None,
    ) -> Dict[str, Any]:
        action_taken = "OBSERVE"
        actions = []

        if risk_score >= SIEM_CONFIG["soar_risk_block"] or is_sim_swap:
            action_taken = "BLOCK"
            actions.extend(
                await self._cgnat_safe_block(
                    entity_id=entity_id,
                    ip_address=ip_address,
                    tenant_id=tenant_id,
                    device_fingerprint=device_fingerprint,
                    jwt_jti=jwt_jti,
                    is_sim_swap=is_sim_swap,
                    old_device_fingerprint=old_device_fingerprint,
                )
            )
            severity = "CRITICAL" if is_sim_swap else "CRITICAL"
            await self._fire_webhook(entity_id, ip_address, risk_score, severity, reasons, is_sim_swap=is_sim_swap)

        elif risk_score >= SIEM_CONFIG["soar_risk_ratelimit"]:
            action_taken = "RATE_LIMIT"
            actions.extend(
                await self._cgnat_safe_ratelimit(
                    entity_id=entity_id,
                    ip_address=ip_address,
                    device_fingerprint=device_fingerprint,
                )
            )
            await self._fire_webhook(entity_id, ip_address, risk_score, "HIGH", reasons)

        elif risk_score >= SIEM_CONFIG["soar_risk_observe"]:
            action_taken = "OBSERVE"
            if self._redis:
                await self._redis.setex(
                    f"soar:watchlist:{entity_id}",
                    3600,
                    json.dumps({"risk": risk_score, "reasons": reasons}),
                )
            actions.append("ADDED_TO_WATCHLIST")

        result = {
            "action": action_taken,
            "entity_id": entity_id,
            "ip_address": ip_address,
            "risk_score": risk_score,
            "actions_executed": actions,
            "cgnat_safe": SIEM_CONFIG["cgnat_safe_mode"],
            "is_sim_swap_response": is_sim_swap,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.warning(f"[SOAR] {action_taken} | {entity_id} | risk={risk_score:.1f} | sim_swap={is_sim_swap} | {actions}")
        return result

    async def _cgnat_safe_block(
        self,
        entity_id: str,
        ip_address: str,
        tenant_id: str,
        device_fingerprint: Optional[str] = None,
        jwt_jti: Optional[str] = None,
        is_sim_swap: bool = False,
        old_device_fingerprint: Optional[str] = None,
    ) -> List[str]:
        """
        CGNAT-safe block: targets device/token/entity instead of raw IP.

        IP blocking is ONLY applied if:
          1. cgnat_safe_mode is disabled (explicit opt-out), OR
          2. The IP does not match any known CGNAT prefix
        """
        if not self._redis:
            return ["REDIS_UNAVAILABLE"]

        actions = []

        # Import the upgraded CGNAT-aware containment engine
        from app.modules.defensive.services.containment import (
            containment_engine, _is_cgnat_risk
        )

        # --- SIM Swap: use SIM swap emergency response ---
        if is_sim_swap and old_device_fingerprint:
            result = containment_engine.respond_to_sim_swap(
                old_device_fingerprint=old_device_fingerprint,
                entity_id=entity_id,
                duration_seconds=SIEM_CONFIG["sim_swap_velocity_window"],
            )
            actions.append(f"SIM_SWAP_HOLD: {result.get('status')}")

        # --- Prefer device fingerprint containment (most precise) ---
        if device_fingerprint:
            result = containment_engine.contain_device(
                device_fingerprint=device_fingerprint,
                entity_id=entity_id,
                reason="SOAR_AUTO_BLOCK_DEVICE",
                duration_seconds=SIEM_CONFIG["block_duration_seconds"],
            )
            actions.append(f"DEVICE_FINGERPRINT_BLOCKED: {result.get('status')}")

        # --- Revoke specific JWT token if known ---
        if jwt_jti:
            containment_engine.invalidate_token(
                token_jti=jwt_jti,
                duration_seconds=SIEM_CONFIG["block_duration_seconds"],
            )
            actions.append("JWT_TOKEN_REVOKED")

        # --- Entity-level isolation (account block) ---
        containment_engine.isolate_entity(
            entity_id=entity_id,
            reason="SOAR_AUTO_BLOCK",
            duration_seconds=SIEM_CONFIG["block_duration_seconds"],
        )
        actions.append("ENTITY_ISOLATED")

        # --- IP Block: LAST RESORT with CGNAT circuit-breaker ---
        if SIEM_CONFIG["cgnat_safe_mode"]:
            cgnat_risk = _is_cgnat_risk(ip_address)
            if cgnat_risk:
                logger.warning(
                    f"[SOAR] ⚠️  CGNAT circuit-breaker: Skipping IP block for {ip_address}. "
                    f"Device/token/entity-level blocks applied instead. "
                    f"This protects ~10K–100K innocent users on the same carrier NAT."
                )
                actions.append(f"IP_BLOCK_SKIPPED_CGNAT_RISK: {ip_address}")
            else:
                # Safe to block: datacenter/static IP
                result = containment_engine.block_ip_last_resort(
                    ip_address=ip_address,
                    entity_id=entity_id,
                    reason="SOAR_AUTO_BLOCK",
                    duration_seconds=SIEM_CONFIG["block_duration_seconds"],
                )
                actions.append(f"IP_BLOCKED: {result.get('status')}")
                # Also write legacy Redis key for edge proxies
                await self._redis.setex(
                    f"soar:blocked_ip:{ip_address}",
                    SIEM_CONFIG["block_duration_seconds"],
                    json.dumps({"blocked_at": datetime.now(timezone.utc).isoformat(), "tenant_id": tenant_id}),
                )
        else:
            # CGNAT-safe mode disabled — legacy IP block behavior
            await self._redis.setex(
                f"soar:blocked_ip:{ip_address}",
                SIEM_CONFIG["block_duration_seconds"],
                json.dumps({"blocked_at": datetime.now(timezone.utc).isoformat(), "tenant_id": tenant_id}),
            )
            actions.append("IP_BLOCKED_LEGACY_MODE")

        # Publish to pub/sub for edge node real-time sync
        await self._redis.publish("soar:ip_block_events", json.dumps({
            "ip": ip_address,
            "entity_id": entity_id,
            "action": "BLOCK",
            "cgnat_safe": SIEM_CONFIG["cgnat_safe_mode"],
        }))
        actions.append("EDGE_NODES_NOTIFIED")

        return actions

    async def _cgnat_safe_ratelimit(self, entity_id: str, ip_address: str, device_fingerprint: Optional[str] = None) -> List[str]:
        """Apply rate limiting on device fingerprint first, entity ID second, IP last."""
        if not self._redis:
            return ["REDIS_UNAVAILABLE"]
        try:
            from app.modules.defensive.services.containment import containment_engine
            containment_engine.throttle_api(
                entity_id=entity_id,
                limit_per_minute=SIEM_CONFIG["rate_limit_rps"],
                duration_seconds=SIEM_CONFIG["rate_limit_ttl"],
                device_fingerprint=device_fingerprint,
            )
            # Legacy Redis key for edge proxy compatibility
            await self._redis.setex(
                f"soar:rate_limited_ip:{ip_address}",
                SIEM_CONFIG["rate_limit_ttl"],
                "1",
            )
            return ["ENTITY_RATE_LIMITED", "DEVICE_THROTTLED", "IP_RATE_LIMITED"]
        except Exception as exc:
            return [f"RATE_LIMIT_FAILED: {exc}"]

    # --- Legacy _block_ip kept for backward compatibility with direct callers ---
    async def _block_ip(self, ip: str, entity_id: str, tenant_id: str) -> List[str]:
        """[DEPRECATED] Use _cgnat_safe_block() instead. Kept for backward compatibility."""
        logger.warning(
            "[SOAR] _block_ip() called directly — this bypasses CGNAT protection. "
            "Upgrade callers to use _cgnat_safe_block()."
        )
        return await self._cgnat_safe_block(entity_id, ip, tenant_id)

    async def _rate_limit_ip(self, ip: str, entity_id: str) -> List[str]:
        """[DEPRECATED] Use _cgnat_safe_ratelimit() instead."""
        return await self._cgnat_safe_ratelimit(entity_id, ip)

    async def _fire_webhook(
        self,
        entity_id: str,
        ip: str,
        risk_score: float,
        severity: str,
        reasons: List[str],
        is_sim_swap: bool = False,
    ):
        """Fire enterprise containment webhook (Splunk SIEM, Microsoft Sentinel, etc.)."""
        if not self._webhook_url:
            return
        try:
            import httpx
            payload = {
                "source": "ProjectXY_SOAR",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "severity": severity,
                "entity_id": entity_id,
                "source_ip": ip,
                "risk_score": risk_score,
                "automated_action": "BLOCK" if risk_score >= SIEM_CONFIG["soar_risk_block"] else "RATE_LIMIT",
                "reasons": reasons,
                "compliance": "CBK_GUIDELINES_COMPLIANT",
                "data_jurisdiction": "KENYA_DPA_2019",
                "cgnat_safe": SIEM_CONFIG["cgnat_safe_mode"],
                "sim_swap_triggered": is_sim_swap,
                "alert_class": "SIM_SWAP_VELOCITY" if is_sim_swap else "AI_THREAT_DETECTION",
            }
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(self._webhook_url, json=payload)
        except Exception as exc:
            logger.warning(f"[SOAR] Webhook delivery failed: {exc}")


# ---------------------------------------------------------------------------
# Threat Classifier
# ---------------------------------------------------------------------------

class ThreatClassifier:
    """
    Real-time SIEM event classifier.

    Consumes Kafka streams and applies multi-signal behavioral analysis.
    Queries Neo4j for graph correlation before making final risk determination.
    """

    def __init__(self):
        self._kafka_consumer = None
        self._redis = None
        self._neo4j_driver = None
        self._soar: Optional[SOARPlaybook] = None
        self._running = False

    async def initialize(self):
        """Set up all connections."""
        import redis.asyncio as aioredis

        try:
            self._redis = aioredis.from_url(SIEM_CONFIG["redis_url"], decode_responses=True)
            await self._redis.ping()
            logger.info("[SIEM] Redis connected.")
        except Exception as exc:
            logger.warning(f"[SIEM] Redis unavailable: {exc}")

        try:
            from neo4j import GraphDatabase
            self._neo4j_driver = GraphDatabase.driver(
                SIEM_CONFIG["neo4j_uri"],
                auth=(SIEM_CONFIG["neo4j_user"], SIEM_CONFIG["neo4j_password"]),
            )
            logger.info("[SIEM] Neo4j graph engine connected.")
        except Exception as exc:
            logger.warning(f"[SIEM] Neo4j unavailable: {exc}")

        self._soar = SOARPlaybook(self._redis, SIEM_CONFIG["soar_webhook_url"])
        logger.info("[SIEM] SOAR playbook engine initialized.")

    async def start_consuming(self):
        """Start Kafka consumer loop."""
        try:
            from aiokafka import AIOKafkaConsumer
            self._kafka_consumer = AIOKafkaConsumer(
                *SIEM_CONFIG["consume_topics"],
                bootstrap_servers=SIEM_CONFIG["kafka_bootstrap"],
                group_id=SIEM_CONFIG["kafka_group_id"],
                auto_offset_reset="latest",
                enable_auto_commit=True,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            )
            await self._kafka_consumer.start()
            self._running = True
            logger.info(f"[SIEM] Kafka consumer started. Listening on: {SIEM_CONFIG['consume_topics']}")

            async for msg in self._kafka_consumer:
                if not self._running:
                    break
                await self._process_event(msg.topic, msg.value)

        except Exception as exc:
            logger.error(f"[SIEM] Kafka consumer error: {exc}")
        finally:
            if self._kafka_consumer:
                await self._kafka_consumer.stop()

    async def _process_event(self, topic: str, event: Dict[str, Any]):
        """Process a single telemetry event through the classification pipeline."""
        try:
            entity_id = event.get("entity_id", event.get("principal", {}).get("ip", "unknown"))
            ip_address = event.get("client_ip", event.get("principal", {}).get("ip", "0.0.0.0"))
            tenant_id = event.get("tenant_id", "default")
            device_fingerprint = event.get("device_fingerprint")  # from mobile SDK / edge enrichment
            jwt_jti = event.get("jwt_jti")                        # from JWT claim

            # --- SIM Swap Velocity Filter (runs BEFORE standard signals) ---
            sim_swap_result = await self._detect_sim_swap_velocity(event, entity_id)

            if sim_swap_result.get("is_critical"):
                # IMMEDIATELY escalate to SOAR — no need to fuse signals first
                logger.critical(
                    f"[SIEM] 🚨 SIM SWAP VELOCITY DETECTED: entity={entity_id} "
                    f"new_carrier={sim_swap_result.get('new_carrier')} "
                    f"actions_within_window={sim_swap_result.get('actions_count')} "
                    f"velocity_window={SIEM_CONFIG['sim_swap_velocity_window']}s"
                )
                await self._soar.execute(
                    entity_id=entity_id,
                    ip_address=ip_address,
                    risk_score=100.0,  # SIM swap + immediate login = maximum risk
                    reasons=[
                        f"SIM_SWAP_VELOCITY: Device identity changed and sensitive action "
                        f"detected within {SIEM_CONFIG['sim_swap_velocity_window']}s window.",
                        f"New device carrier: {sim_swap_result.get('new_carrier', 'unknown')}",
                        f"Sensitive actions detected: {sim_swap_result.get('action_types', [])}",
                    ],
                    tenant_id=tenant_id,
                    device_fingerprint=device_fingerprint,
                    jwt_jti=jwt_jti,
                    is_sim_swap=True,
                    old_device_fingerprint=sim_swap_result.get("old_device_fingerprint"),
                )
                # Record the SIM swap threat in Neo4j for long-term correlation
                await self._upsert_sim_swap_threat(
                    entity_id=entity_id,
                    new_imei_hash=sim_swap_result.get("new_imei_hash", "unknown"),
                    risk_score=100.0,
                    tenant_id=tenant_id,
                )
                return  # Don't continue normal processing for SIM swap events

            # --- Standard Signal Extraction ---
            signals = await self._extract_signals(topic, event, entity_id, ip_address)

            # --- Graph Correlation (Neo4j) ---
            graph_context = await self._query_graph_correlation(ip_address)

            # --- Risk Score Fusion ---
            risk_score, reasons = self._fuse_signals(signals, graph_context)

            # --- SOAR Execution (if threshold breached) ---
            if risk_score >= SIEM_CONFIG["soar_risk_observe"]:
                await self._soar.execute(
                    entity_id=entity_id,
                    ip_address=ip_address,
                    risk_score=risk_score,
                    reasons=reasons,
                    tenant_id=tenant_id,
                    device_fingerprint=device_fingerprint,
                    jwt_jti=jwt_jti,
                )

            # --- Persist to Neo4j for future graph queries ---
            await self._upsert_threat_node(
                ip_address=ip_address,
                entity_id=entity_id,
                event_type=topic,
                risk_score=risk_score,
                tenant_id=tenant_id,
            )

        except Exception as exc:
            logger.error(f"[SIEM] Event processing error: {exc}")

    async def _extract_signals(
        self,
        topic: str,
        event: Dict[str, Any],
        entity_id: str,
        ip_address: str,
    ) -> Dict[str, float]:
        """Extract quantified signal scores from the raw event."""
        signals = {}

        if topic == "firewall_events":
            fw_action = event.get("action", "PASS")
            fw_score = event.get("threat_score", 0.0)
            if fw_action == "BLOCK":
                signals["firewall_block"] = min(1.0, fw_score + 0.3)
            elif fw_action == "SCRUB_AND_PASS":
                signals["firewall_pii"] = 0.4
            signals["firewall_semantic"] = event.get("semantic_similarity", 0.0)

        elif topic == "infrastructure_telemetry":
            status_code = event.get("status_code", 200)
            if status_code >= 400:
                if self._redis:
                    err_key = f"siem:errors:{ip_address}"
                    count = await self._redis.incr(err_key)
                    await self._redis.expire(err_key, 300)
                    if count > 20:
                        signals["api_abuse"] = min(1.0, count / 50.0)
                    elif count > 5:
                        signals["api_errors"] = min(0.5, count / 20.0)

        elif topic == "ai_agent_telemetry":
            confidence = event.get("about", {})
            if isinstance(confidence, dict):
                labels = confidence.get("labels", [])
                for label in labels:
                    if label.get("key") == "confidence_score":
                        conf = float(label.get("value", 0))
                        if conf > 0.8:
                            signals["ai_high_confidence_action"] = conf

        elif topic == "mobile_session_events":
            # NEW: Process mobile session events from telco API
            event_type = event.get("event_type", "")
            if event_type == "USSD_CONCURRENT_SESSION":
                # Multiple concurrent USSD sessions = session hijacking attempt
                concurrent_count = event.get("concurrent_sessions", 1)
                if concurrent_count > 1:
                    signals["ussd_concurrent_session"] = min(1.0, concurrent_count / 3.0)
            elif event_type == "OTP_EXHAUSTION":
                # Rapid OTP attempts = brute force on OTP
                attempt_count = event.get("attempts", 1)
                signals["otp_brute_force"] = min(1.0, attempt_count / 5.0)
            elif event_type == "DEVICE_IDENTITY_CHANGE":
                # IMEI/IMSI change observed by telco — potential SIM swap signal
                # This is handled by the velocity filter BEFORE we get here,
                # but also add a moderate signal for pattern analysis.
                signals["device_identity_change"] = 0.6
            elif event_type == "MSISDN_PORT_REQUEST":
                # Mobile number portability request — high SIM swap indicator
                signals["msisdn_port_request"] = 0.85

        return signals

    async def _query_graph_correlation(self, ip_address: str) -> Dict[str, Any]:
        """Query Neo4j to correlate this IP with historical threat events."""
        if not self._neo4j_driver:
            return {}
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._run_graph_query,
                ip_address,
            )
            return result
        except Exception as exc:
            logger.debug(f"[SIEM] Graph query error: {exc}")
            return {}

    def _run_graph_query(self, ip_address: str) -> Dict[str, Any]:
        """Synchronous Neo4j query (run in executor)."""
        with self._neo4j_driver.session() as session:
            # Check for correlated threat history
            result = session.run(
                CYPHER_CORRELATED_THREAT,
                ip_address=ip_address,
            ).single()

            # Check for multi-stage APT chain
            apt_result = session.run(
                CYPHER_DETECT_APT_CHAIN,
                ip_address=ip_address,
            ).single()

            return {
                "scan_count": result["scan_count"] if result else 0,
                "failed_login_count": result["failed_login_count"] if result else 0,
                "firewall_block_count": result["firewall_block_count"] if result else 0,
                "is_apt_chain": bool(apt_result) if apt_result else False,
            }

    def _fuse_signals(
        self,
        signals: Dict[str, float],
        graph_context: Dict[str, Any],
    ) -> tuple:
        """Fuse all signals into a final risk score with explainability."""
        total_risk = 0.0
        reasons = []

        # Signal weights (tuned for East African threat landscape)
        weights = {
            "firewall_block": 45.0,
            "firewall_pii": 25.0,
            "firewall_semantic": 30.0,
            "api_abuse": 40.0,
            "api_errors": 20.0,
            "ai_high_confidence_action": 15.0,
            # NEW: Mobile-specific signal weights
            "ussd_concurrent_session": 50.0,    # Very high — USSD hijacking
            "otp_brute_force": 55.0,            # Very high — OTP cracking
            "device_identity_change": 35.0,     # High — potential SIM swap
            "msisdn_port_request": 60.0,        # Critical — number porting + attack
        }

        for signal, value in signals.items():
            weight = weights.get(signal, 10.0)
            contribution = value * weight
            total_risk += contribution
            if contribution > 0:
                reasons.append(f"{signal}: +{contribution:.1f}pts (raw={value:.3f})")

        # Graph correlation amplifiers
        if graph_context.get("is_apt_chain"):
            total_risk += 35.0
            reasons.append("APT multi-stage chain detected via Neo4j graph (+35pts)")

        if graph_context.get("scan_count", 0) > 5:
            total_risk += min(20.0, graph_context["scan_count"] * 2)
            reasons.append(f"Historical API scanning: {graph_context['scan_count']} events")

        if graph_context.get("firewall_block_count", 0) > 2:
            total_risk += min(25.0, graph_context["firewall_block_count"] * 5)
            reasons.append(f"Prior firewall blocks: {graph_context['firewall_block_count']}")

        return round(min(100.0, total_risk), 2), reasons

    async def _upsert_threat_node(
        self,
        ip_address: str,
        entity_id: str,
        event_type: str,
        risk_score: float,
        tenant_id: str,
    ):
        """Write the threat event back to Neo4j for future correlation."""
        if not self._neo4j_driver or risk_score < 20:
            return
        import uuid
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._neo4j_driver.session().run(
                    CYPHER_UPSERT_THREAT_NODE,
                    ip_address=ip_address,
                    risk=risk_score,
                    event_id=str(uuid.uuid4()),
                    event_type=event_type,
                    tenant_id=tenant_id,
                ).consume(),
            )
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # NEW: SIM Swap Velocity Filter
    # ------------------------------------------------------------------ #

    async def _detect_sim_swap_velocity(
        self, event: Dict[str, Any], entity_id: str
    ) -> Dict[str, Any]:
        """
        SIM Swap Velocity Filter.

        Checks whether a device identity change (IMEI/IMSI swap, sourced from
        a telco API integration) has been followed by a sensitive action within
        the configured velocity window (default: 15 minutes).

        This catches the #1 fintech attack pattern in East Africa:
          SIM swap at telco → immediately request password reset → drain account.

        The critical insight: the password reset may be LEGITIMATE (correct OTP),
        but the velocity of the device swap + login makes it a critical threat
        regardless of password correctness.

        Args:
            event: The telemetry event dict (from any topic).
            entity_id: The resolved account/entity identifier.

        Returns:
            Dict with is_critical, new_carrier, actions_count, action_types, etc.
        """
        if not self._neo4j_driver:
            return {"is_critical": False}

        try:
            # Check Redis first for a recent device-identity-change marker
            # (written when a mobile_session_events DEVICE_IDENTITY_CHANGE arrives)
            if not self._redis:
                return {"is_critical": False}

            sim_swap_key = f"siem:sim_swap_pending:{entity_id}"
            sim_swap_data_raw = await self._redis.get(sim_swap_key)

            if not sim_swap_data_raw:
                # No pending SIM swap detected for this entity — safe
                # BUT: if this event IS a device identity change, record it
                if event.get("event_type") == "DEVICE_IDENTITY_CHANGE":
                    await self._record_sim_swap_marker(event, entity_id)
                return {"is_critical": False}

            # A device identity change was recently recorded.
            # Check if the current event is a sensitive action.
            sensitive_action_types = {
                "LOGIN", "PASSWORD_RESET", "OTP_REQUEST",
                "PIN_CHANGE", "USSD_SESSION", "ACCOUNT_RECOVERY",
                "MPESA_PIN_RESET", "BENEFICIARY_ADD",
            }
            current_action = event.get("event_type", "").upper()

            if current_action not in sensitive_action_types:
                return {"is_critical": False}

            # CRITICAL: SIM swap followed by sensitive action within velocity window
            sim_swap_data = json.loads(sim_swap_data_raw)

            logger.critical(
                f"[SIEM] 🚨 SIM SWAP VELOCITY TRIGGER: "
                f"entity={entity_id} | "
                f"device_changed={sim_swap_data.get('old_imei_hash', 'unknown')[:8]}... "
                f"→ {sim_swap_data.get('new_imei_hash', 'unknown')[:8]}... | "
                f"sensitive_action={current_action} | "
                f"time_since_swap={(time.time() - sim_swap_data.get('swap_timestamp', time.time())):.0f}s"
            )

            # Also verify with Neo4j graph for corroboration
            graph_result = await self._run_sim_swap_graph_query(entity_id, sim_swap_data)

            return {
                "is_critical": True,
                "new_carrier": sim_swap_data.get("new_carrier", "unknown"),
                "new_imei_hash": sim_swap_data.get("new_imei_hash", "unknown"),
                "old_device_fingerprint": sim_swap_data.get("old_device_fingerprint", ""),
                "actions_count": graph_result.get("sensitive_actions_count", 1),
                "action_types": [current_action] + graph_result.get("action_types", []),
            }

        except Exception as exc:
            logger.error(f"[SIEM] SIM swap velocity check error: {exc}")
            return {"is_critical": False}

    async def _record_sim_swap_marker(
        self, event: Dict[str, Any], entity_id: str
    ):
        """
        Record a device identity change in Redis for velocity tracking.
        Called when a DEVICE_IDENTITY_CHANGE event arrives from the telco API.
        """
        if not self._redis:
            return

        swap_data = {
            "old_imei_hash": event.get("old_imei_hash", "unknown"),
            "new_imei_hash": event.get("new_imei_hash", "unknown"),
            "old_device_fingerprint": event.get("old_device_fingerprint", ""),
            "new_carrier": event.get("new_carrier", "unknown"),
            "swap_timestamp": time.time(),
            "entity_id": entity_id,
        }

        sim_swap_key = f"siem:sim_swap_pending:{entity_id}"
        await self._redis.setex(
            sim_swap_key,
            SIEM_CONFIG["sim_swap_velocity_window"],
            json.dumps(swap_data),
        )
        logger.warning(
            f"[SIEM] Device identity change recorded for entity={entity_id}. "
            f"Velocity window active for {SIEM_CONFIG['sim_swap_velocity_window']}s. "
            f"Any sensitive action within this window will trigger CRITICAL alert."
        )

        # Also record in Neo4j for long-term graph analysis
        await self._upsert_device_identity(event, entity_id)

    async def _run_sim_swap_graph_query(
        self, entity_id: str, sim_swap_data: Dict
    ) -> Dict[str, Any]:
        """Query Neo4j to verify SIM swap velocity from graph perspective."""
        if not self._neo4j_driver:
            return {}
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                self._execute_sim_swap_query,
                entity_id,
                sim_swap_data,
            )
        except Exception as exc:
            logger.debug(f"[SIEM] SIM swap graph query error: {exc}")
            return {}

    def _execute_sim_swap_query(self, entity_id: str, sim_swap_data: Dict) -> Dict:
        """Synchronous Neo4j SIM swap velocity query (run in executor)."""
        with self._neo4j_driver.session() as session:
            result = session.run(
                CYPHER_DETECT_SIM_SWAP_VELOCITY,
                entity_id=entity_id,
                velocity_window=SIEM_CONFIG["sim_swap_velocity_window"],
                previous_imei_hash=sim_swap_data.get("old_imei_hash", "unknown"),
            ).single()
            if result:
                return {
                    "sensitive_actions_count": result["sensitive_actions_count"],
                    "action_types": list(result["action_types"]),
                }
            return {}

    async def _upsert_device_identity(
        self, event: Dict[str, Any], entity_id: str
    ):
        """Write device identity change into Neo4j graph for correlation."""
        if not self._neo4j_driver:
            return
        try:
            import hashlib as _hashlib
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._neo4j_driver.session().run(
                    CYPHER_RECORD_DEVICE_IDENTITY,
                    entity_id=entity_id,
                    imei_hash=event.get("new_imei_hash", "unknown"),
                    imsi_hash=event.get("new_imsi_hash", "unknown"),
                    carrier=event.get("new_carrier", "unknown"),
                    is_cgnat=event.get("is_cgnat", False),
                ).consume(),
            )
        except Exception:
            pass

    async def _upsert_sim_swap_threat(
        self,
        entity_id: str,
        new_imei_hash: str,
        risk_score: float,
        tenant_id: str,
    ):
        """Persist confirmed SIM swap threat into Neo4j."""
        if not self._neo4j_driver:
            return
        import uuid
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._neo4j_driver.session().run(
                    CYPHER_UPSERT_SIM_SWAP_THREAT,
                    entity_id=entity_id,
                    new_imei_hash=new_imei_hash,
                    threat_id=str(uuid.uuid4()),
                    risk_score=risk_score,
                    velocity_window=SIEM_CONFIG["sim_swap_velocity_window"],
                    tenant_id=tenant_id,
                ).consume(),
            )
        except Exception:
            pass

    async def stop(self):
        self._running = False
        if self._kafka_consumer:
            await self._kafka_consumer.stop()
        if self._neo4j_driver:
            self._neo4j_driver.close()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

threat_classifier = ThreatClassifier()


async def start_siem_classifier():
    """Start the SIEM classifier as a background task from FastAPI lifespan."""
    await threat_classifier.initialize()
    asyncio.create_task(threat_classifier.start_consuming())
    logger.info("[SIEM] Threat classifier background task launched.")
