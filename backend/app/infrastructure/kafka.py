import json
import asyncio
import os
from datetime import datetime, timezone
from aiokafka import AIOKafkaProducer
from app.core.logging import log

# Tracks topics already warned about to avoid log spam on every dropped event.
_redis_fallback_warned: set[str] = set()

class KafkaStreamer:
    """
    ProjectXY Tier 1 Infrastructure: High-throughput event streaming.
    Integrated with Google Chronicle UDM for SIEM readiness.
    """
    def __init__(self):
        self.producer: AIOKafkaProducer = None
        self.bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self._lock = asyncio.Lock()  # Ensures atomic connection state

    async def connect(self):
        """Initializes the connection to the Kafka broker."""
        async with self._lock:
            if self.producer is not None:
                return
            
            log.info(f"[KAFKA] Initializing broker at {self.bootstrap_servers}...")
            try:
                # `retries` is not supported by some aiokafka versions; omit to maintain compatibility.
                self.producer = AIOKafkaProducer(
                    bootstrap_servers=self.bootstrap_servers,
                    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                    acks='all'  # Guarantee persistence for security logs
                )
                await self.producer.start()
                log.info("[KAFKA] Producer connected and ready to transmit.")
            except Exception as e:
                log.error(f"[KAFKA] Connection failed: {e}. Running in degraded mode.")
                self.producer = None

    async def disconnect(self):
        """Gracefully stops the producer."""
        if self.producer:
            await self.producer.stop()
            log.info("[KAFKA] Producer stopped cleanly.")
            self.producer = None

    async def emit_event(self, topic: str, event_data: dict):
        """Pushes a validated event into the stream.
        Falls back to Redis Pub/Sub when Kafka is unavailable.
        """
        if not self.producer:
            await self._fallback_to_redis(topic, event_data)
            return

        try:
            await self.producer.send_and_wait(topic, event_data)
        except Exception as e:
            log.error(f"[KAFKA] Failed emit to {topic}: {e}")
            await self._fallback_to_redis(topic, event_data)

    # Alias — used by newer modules (opa_feedback, auth, adversarial intel)
    async def publish(self, topic: str, event_data: dict):
        """Alias for emit_event — preferred in new modules."""
        await self.emit_event(topic, event_data)

    async def _fallback_to_redis(self, topic: str, event_data: dict) -> None:
        """
        Publish to a Redis Pub/Sub channel when Kafka is unavailable.
        Preserves event-driven audit logging during light-profile local dev.
        Channel format: kafka_fallback:<topic>
        """
        channel = f"kafka_fallback:{topic}"
        if topic not in _redis_fallback_warned:
            log.warning(
                f"[KAFKA] Producer unavailable — routing '{topic}' events through "
                f"Redis Pub/Sub fallback (channel: {channel})."
            )
            _redis_fallback_warned.add(topic)

        try:
            from app.infrastructure.cache.redis_manager import redis_cache
            await redis_cache.redis_client.publish(channel, json.dumps(event_data))
        except Exception as exc:
            # Redis itself may also be unavailable in ultra-light mode — log and continue.
            log.debug(f"[KAFKA] Redis fallback also failed for '{topic}': {exc}")

    async def emit_threat_intel(self, stix_object: dict, source: str = "STIX/TAXII", tenant_id: str = "default"):
        """
        Emit STIX threat intelligence into the threat_feed Kafka topic.
        Chronicle UDM-compatible format for SIEM ingestion.
        """
        udm_payload = {
            "metadata": {
                "event_timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": "GENERIC_EVENT",
                "vendor_name": "ProjectXY",
                "product_name": "Adversarial Intelligence Engine",
                "tenant_id": tenant_id,
            },
            "source": source,
            "stix": stix_object,
            "security_result": {
                "severity": stix_object.get("confidence_level", "MEDIUM"),
                "summary": stix_object.get("description", "")[:200],
            },
        }
        await self.emit_event("threat_feed", udm_payload)

    async def emit_compliance_event(self, tenant_id: str, entity_id: str, action: str,
                                     data_category: str, dpa_article: str, outcome: str):
        """
        Emit a DPA 2019 / GDPR compliance audit event.
        Every touch of personal/sensitive data must produce this event.
        Goes to compliance_events topic → Postgres ledger → PDF report.
        """
        payload = {
            "event_type": "COMPLIANCE_AUDIT",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tenant_id": tenant_id,
            "entity_id": entity_id,
            "action": action,
            "data_category": data_category,
            "dpa_article": dpa_article,
            "outcome": outcome,
            "platform": "ProjectXY Cognitive Shield",
        }
        await self.emit_event("compliance_events", payload)

    async def emit_syslog_event(self, tenant_id: str, source_ip: str, action: str, severity: str, details: str):
        """
        Infrastructure Containment Log (Chronicle UDM compatible).
        Used by the Cognitive Shield to report network-level threats.
        """
        udm_payload = {
            "metadata": {
                "event_timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": "NETWORK_CONNECTION",
                "vendor_name": "ProjectXY",
                "product_name": "Omni-Threat Containment",
                "tenant_id": tenant_id
            },
            "principal": {"ip": source_ip},
            "security_result": {
                "action": [action],
                "severity": severity,
                "summary": details
            }
        }
        await self.emit_event("infrastructure_telemetry", udm_payload)

    async def emit_ai_telemetry(self, tenant_id: str, agent_id: str, tool: str, target: str, prompt: str, confidence: float):
        """
        AI Agent Telemetry (Chronicle UDM compatible).
        Captures agent intent and confidence for auditability.
        """
        udm_payload = {
            "metadata": {
                "event_timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": "APPLICATION_ACTIVITY",
                "vendor_name": "ProjectXY",
                "product_name": "Agentic Security Framework",
                "tenant_id": tenant_id
            },
            "target": {
                "application": tool,
                "resource": {"name": target}
            },
            "principal": {"user": {"userid": agent_id}},
            "about": {
                "labels": [
                    {"key": "prompt", "value": prompt},
                    {"key": "confidence_score", "value": str(confidence)}
                ]
            }
        }
        await self.emit_event("ai_agent_telemetry", udm_payload)

# Global singleton
kafka_streamer = KafkaStreamer()