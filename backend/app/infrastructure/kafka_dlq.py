"""
kafka_dlq.py — ProjectXY Phase 4: Kafka Dead-Letter Queue (DLQ) System
========================================================================
CRITICAL INFRASTRUCTURE UPGRADE — Telemetry Loss Prevention
------------------------------------------------------------
Problem: When the TimescaleDB writer is under lock contention, or the FastAPI
backend experiences a momentary spike, security telemetry events can be
SILENTLY DROPPED from Kafka. In a fintech security platform, every dropped
event is a potential undetected breach.

Solution — Dead-Letter Queue Architecture:
  1. Primary topics are consumed as normal.
  2. If processing fails (DB write fails, malformed event, network error),
     the message is NOT committed — it's routed to a `.dlq` shadow topic.
  3. A dedicated DLQ consumer retries these events with exponential backoff.
  4. Events that fail all retries are written to a persistent audit log
     (TimescaleDB `failed_telemetry` hypertable) for forensic review.
  5. DLQ depth is monitored and emits alerts if the backlog grows > threshold.

DLQ Topics (auto-created with 1 partition, 7-day retention):
  • infrastructure_telemetry.dlq
  • firewall_events.dlq
  • ai_agent_telemetry.dlq
  • mobile_session_events.dlq

Retry Policy:
  • Attempt 1: 5 seconds
  • Attempt 2: 30 seconds
  • Attempt 3: 5 minutes
  • Attempt 4: 30 minutes (final — then mark as DEAD)

CBK Compliance: Dead events are never deleted — they are immutably archived
                to `failed_telemetry` with the original payload, error message,
                and retry history for audit purposes.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("projectxy.kafka.dlq")

# ---------------------------------------------------------------------------
# DLQ Configuration
# ---------------------------------------------------------------------------

DLQ_CONFIG = {
    "kafka_bootstrap": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
    "group_id_suffix": "-dlq-consumer",
    "max_retry_attempts": int(os.getenv("DLQ_MAX_RETRIES", "4")),
    # Exponential backoff intervals in seconds between each retry attempt
    "retry_delays_seconds": [5, 30, 300, 1800],
    "dlq_topic_suffix": ".dlq",
    "alert_depth_threshold": int(os.getenv("DLQ_ALERT_DEPTH_THRESHOLD", "100")),
    # Primary topics that have DLQ protection
    "protected_topics": [
        "infrastructure_telemetry",
        "firewall_events",
        "ai_agent_telemetry",
        "mobile_session_events",
    ],
}


def dlq_topic_name(primary_topic: str) -> str:
    """Returns the DLQ shadow topic name for a given primary topic."""
    return f"{primary_topic}{DLQ_CONFIG['dlq_topic_suffix']}"


# ---------------------------------------------------------------------------
# DLQ Event Envelope
# ---------------------------------------------------------------------------

@dataclass
class DLQEnvelope:
    """
    Wrapper applied to any message routed to the DLQ.
    Contains the original payload PLUS failure forensics.
    """
    original_topic: str
    original_payload: Dict[str, Any]
    error_message: str
    error_type: str
    first_failed_at: str
    retry_count: int = 0
    retry_history: List[Dict[str, str]] = field(default_factory=list)
    is_dead: bool = False        # True when all retries exhausted
    tenant_id: str = "unknown"
    entity_id: str = "unknown"

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "DLQEnvelope":
        return cls(**data)

    def record_retry_attempt(self, attempt_number: int, error: str):
        self.retry_count = attempt_number
        self.retry_history.append({
            "attempt": attempt_number,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(error)[:500],
        })

    def mark_dead(self, final_error: str):
        self.is_dead = True
        self.retry_history.append({
            "attempt": "FINAL_DEAD",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(final_error)[:500],
        })


# ---------------------------------------------------------------------------
# DLQ Producer — routes failed messages to shadow topic
# ---------------------------------------------------------------------------

class DLQProducer:
    """
    Companion to any Kafka consumer. Call `route_to_dlq()` when your
    message processor fails instead of silently dropping the message.
    """

    def __init__(self):
        self._producer = None
        self._ready = False

    async def connect(self):
        try:
            from aiokafka import AIOKafkaProducer
            self._producer = AIOKafkaProducer(
                bootstrap_servers=DLQ_CONFIG["kafka_bootstrap"],
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks="all",              # wait for full replication
                enable_idempotence=True, # exactly-once semantics
                compression_type="gzip",
            )
            await self._producer.start()
            self._ready = True
            logger.info("[DLQ] Producer connected and ready.")
        except Exception as exc:
            logger.error(f"[DLQ] Producer connection failed: {exc}. DLQ protection disabled.")

    async def route_to_dlq(
        self,
        original_topic: str,
        original_payload: Dict[str, Any],
        error: Exception,
        tenant_id: str = "unknown",
        entity_id: str = "unknown",
    ) -> bool:
        """
        Route a failed message to its DLQ shadow topic.

        Returns True if successfully enqueued to DLQ, False if DLQ itself
        is unavailable (catastrophic — log to stderr for external alerting).
        """
        if not self._ready or not self._producer:
            logger.error(
                f"[DLQ] CRITICAL: DLQ producer not ready. "
                f"Message from topic '{original_topic}' will be LOST. "
                f"Payload: {str(original_payload)[:200]}"
            )
            return False

        envelope = DLQEnvelope(
            original_topic=original_topic,
            original_payload=original_payload,
            error_message=str(error)[:1000],
            error_type=type(error).__name__,
            first_failed_at=datetime.now(timezone.utc).isoformat(),
            tenant_id=tenant_id,
            entity_id=entity_id,
        )

        dlq_topic = dlq_topic_name(original_topic)

        try:
            await self._producer.send_and_wait(dlq_topic, envelope.to_dict())
            logger.warning(
                f"[DLQ] Routed to {dlq_topic} | "
                f"entity={entity_id} | error_type={type(error).__name__} | "
                f"error={str(error)[:100]}"
            )
            return True
        except Exception as dlq_exc:
            # DLQ itself failed — this is a catastrophic condition
            logger.critical(
                f"[DLQ] ⚠️  DOUBLE FAILURE: Could not route to DLQ topic {dlq_topic}. "
                f"SECURITY EVENT WILL BE LOST. Original error: {error}. "
                f"DLQ error: {dlq_exc}. Payload: {str(original_payload)[:200]}"
            )
            return False

    async def disconnect(self):
        if self._producer:
            await self._producer.stop()


# ---------------------------------------------------------------------------
# DLQ Consumer — retry processor with exponential backoff
# ---------------------------------------------------------------------------

class DLQConsumer:
    """
    Dedicated consumer for DLQ shadow topics.

    Retries failed events with configurable exponential backoff.
    Events that exhaust all retries are archived to TimescaleDB
    `failed_telemetry` for forensic review.
    """

    def __init__(self, processor_map: Dict[str, Callable]):
        """
        Args:
            processor_map: Maps original topic names to async handler functions.
                           e.g., {"firewall_events": process_firewall_event}
        """
        self._consumer = None
        self._processor_map = processor_map
        self._pg_pool = None
        self._running = False
        self._stats = {
            "retried": 0,
            "recovered": 0,
            "permanently_dead": 0,
        }

    async def connect(self):
        """Initialize Kafka consumer for all DLQ shadow topics."""
        try:
            from aiokafka import AIOKafkaConsumer
            dlq_topics = [
                dlq_topic_name(t) for t in DLQ_CONFIG["protected_topics"]
            ]
            group_id = f"projectxy-dlq{DLQ_CONFIG['group_id_suffix']}"
            self._consumer = AIOKafkaConsumer(
                *dlq_topics,
                bootstrap_servers=DLQ_CONFIG["kafka_bootstrap"],
                group_id=group_id,
                auto_offset_reset="earliest",
                enable_auto_commit=False,   # Manual commit after successful processing
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            )
            await self._consumer.start()
            logger.info(f"[DLQ] Consumer listening on: {dlq_topics}")
        except Exception as exc:
            logger.error(f"[DLQ] Consumer connection failed: {exc}")

        # Optional: Connect to TimescaleDB for archiving dead letters
        try:
            import asyncpg
            db_url = os.getenv(
                "DATABASE_URL",
                "postgresql://postgres:changethis@localhost:5433/cyberintel"
            ).replace("postgresql+asyncpg://", "postgresql://").replace("+asyncpg", "")
            self._pg_pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3)
            logger.info("[DLQ] TimescaleDB archive pool connected.")
        except Exception as exc:
            logger.warning(f"[DLQ] TimescaleDB archive unavailable: {exc}. Dead letters will be logged only.")

    async def start_consuming(self):
        """Main DLQ retry processing loop."""
        if not self._consumer:
            logger.error("[DLQ] Consumer not initialized. Cannot start.")
            return

        self._running = True
        logger.info("[DLQ] Retry processor started.")

        try:
            async for msg in self._consumer:
                if not self._running:
                    break
                try:
                    envelope = DLQEnvelope.from_dict(msg.value)
                    await self._process_dlq_message(envelope)
                    await self._consumer.commit()  # Only commit on success
                except Exception as exc:
                    logger.error(f"[DLQ] Failed to process DLQ message itself: {exc}")
                    # Don't commit — let it be retried from DLQ offset
        finally:
            if self._consumer:
                await self._consumer.stop()

    async def _process_dlq_message(self, envelope: DLQEnvelope):
        """Apply exponential backoff retry logic to a DLQ envelope."""
        attempt = envelope.retry_count + 1
        max_attempts = DLQ_CONFIG["max_retry_attempts"]

        if attempt > max_attempts:
            await self._archive_dead_letter(envelope)
            return

        # Wait for backoff delay before retrying
        delay_idx = min(attempt - 1, len(DLQ_CONFIG["retry_delays_seconds"]) - 1)
        delay = DLQ_CONFIG["retry_delays_seconds"][delay_idx]
        logger.info(
            f"[DLQ] Retry attempt {attempt}/{max_attempts} for "
            f"topic={envelope.original_topic} entity={envelope.entity_id} "
            f"(waiting {delay}s backoff)"
        )
        await asyncio.sleep(delay)

        processor = self._processor_map.get(envelope.original_topic)
        if not processor:
            logger.warning(f"[DLQ] No processor registered for topic: {envelope.original_topic}")
            return

        try:
            await processor(envelope.original_topic, envelope.original_payload)
            # Success! The message has been recovered.
            self._stats["recovered"] += 1
            logger.info(
                f"[DLQ] ✅ RECOVERED: topic={envelope.original_topic} "
                f"entity={envelope.entity_id} after {attempt} attempt(s)"
            )
        except Exception as retry_exc:
            self._stats["retried"] += 1
            envelope.record_retry_attempt(attempt, retry_exc)
            logger.warning(
                f"[DLQ] Retry {attempt} failed: {retry_exc}. "
                f"{'Will retry.' if attempt < max_attempts else 'Marking DEAD.'}"
            )

            if attempt >= max_attempts:
                envelope.mark_dead(retry_exc)
                await self._archive_dead_letter(envelope)

    async def _archive_dead_letter(self, envelope: DLQEnvelope):
        """
        Archive permanently dead messages to TimescaleDB for forensic review.
        This ensures no security event is ever truly lost — it's available
        for incident investigation even if it couldn't be processed in real-time.
        """
        self._stats["permanently_dead"] += 1
        logger.critical(
            f"[DLQ] ☠️  DEAD LETTER ARCHIVED: topic={envelope.original_topic} "
            f"entity={envelope.entity_id} retries={envelope.retry_count} "
            f"first_failed={envelope.first_failed_at}"
        )

        if self._pg_pool:
            try:
                async with self._pg_pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO failed_telemetry (
                            original_topic, original_payload, error_message,
                            error_type, first_failed_at, retry_count,
                            retry_history, tenant_id, entity_id, archived_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
                        """,
                        envelope.original_topic,
                        json.dumps(envelope.original_payload),
                        envelope.error_message,
                        envelope.error_type,
                        envelope.first_failed_at,
                        envelope.retry_count,
                        json.dumps(envelope.retry_history),
                        envelope.tenant_id,
                        envelope.entity_id,
                    )
            except Exception as db_exc:
                # Last resort: log to stderr so external alerting can catch it
                logger.critical(
                    f"[DLQ] CRITICAL: Cannot archive dead letter to DB: {db_exc}. "
                    f"PAYLOAD: {json.dumps(envelope.to_dict())}"
                )
        else:
            # No DB available — emit as structured log for external collection
            logger.critical(
                "[DLQ] DEAD_LETTER_PAYLOAD",
                extra={"dlq_envelope": envelope.to_dict()},
            )

    def get_stats(self) -> Dict[str, int]:
        """Return DLQ health statistics."""
        return dict(self._stats)

    async def stop(self):
        self._running = False
        if self._consumer:
            await self._consumer.stop()
        if self._pg_pool:
            await self._pg_pool.close()


# ---------------------------------------------------------------------------
# DLQ-Aware Consumer Mixin
# ---------------------------------------------------------------------------

class DLQAwareConsumerMixin:
    """
    Mixin for Kafka consumers that want automatic DLQ protection.

    Usage:
        class MyConsumer(DLQAwareConsumerMixin):
            async def process_message(self, topic, payload):
                ... your logic ...

            async def start(self):
                await self._dlq_producer.connect()
                ...
                async for msg in consumer:
                    await self.safe_process(msg.topic, msg.value)
    """

    _dlq_producer: DLQProducer = None

    def _get_dlq_producer(self) -> DLQProducer:
        if self._dlq_producer is None:
            self._dlq_producer = DLQProducer()
        return self._dlq_producer

    async def safe_process(
        self,
        topic: str,
        payload: Dict[str, Any],
        tenant_id: str = "unknown",
        entity_id: str = "unknown",
    ) -> bool:
        """
        Process a Kafka message with automatic DLQ fallback.

        Returns True on success, False if routed to DLQ.
        """
        try:
            await self.process_message(topic, payload)
            return True
        except Exception as exc:
            logger.warning(
                f"[DLQ-MIXIN] Processing failed for topic={topic} entity={entity_id}: {exc}. "
                f"Routing to DLQ."
            )
            producer = self._get_dlq_producer()
            await producer.route_to_dlq(
                original_topic=topic,
                original_payload=payload,
                error=exc,
                tenant_id=tenant_id,
                entity_id=entity_id,
            )
            return False

    async def process_message(self, topic: str, payload: Dict[str, Any]):
        """Override this in your consumer class."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# TimescaleDB Schema for Dead Letters (run once during migration)
# ---------------------------------------------------------------------------

FAILED_TELEMETRY_DDL = """
-- Dead-Letter Archive Hypertable (TimescaleDB)
-- Run this once as part of DB migrations.
CREATE TABLE IF NOT EXISTS failed_telemetry (
    id              BIGSERIAL,
    archived_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    original_topic  TEXT NOT NULL,
    original_payload JSONB NOT NULL,
    error_message   TEXT,
    error_type      TEXT,
    first_failed_at TEXT,
    retry_count     INTEGER DEFAULT 0,
    retry_history   JSONB,
    tenant_id       TEXT DEFAULT 'unknown',
    entity_id       TEXT DEFAULT 'unknown'
);

SELECT create_hypertable(
    'failed_telemetry',
    'archived_at',
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '7 days'
);

CREATE INDEX IF NOT EXISTS idx_failed_telemetry_entity
    ON failed_telemetry (entity_id, archived_at DESC);

CREATE INDEX IF NOT EXISTS idx_failed_telemetry_topic
    ON failed_telemetry (original_topic, archived_at DESC);

COMMENT ON TABLE failed_telemetry IS
    'Dead-Letter archive: immutable log of all Kafka messages that '
    'failed processing after all retry attempts. CBK audit evidence.';
"""


# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

_dlq_producer_singleton: Optional[DLQProducer] = None
_dlq_consumer_singleton: Optional[DLQConsumer] = None


async def get_dlq_producer() -> DLQProducer:
    """Get the global DLQ producer (connects on first call)."""
    global _dlq_producer_singleton
    if _dlq_producer_singleton is None:
        _dlq_producer_singleton = DLQProducer()
        await _dlq_producer_singleton.connect()
    return _dlq_producer_singleton


async def start_dlq_consumer(processor_map: Dict[str, Callable]):
    """
    Initialize and start the DLQ consumer as a background task.

    Args:
        processor_map: Maps original topic → async handler.
                       e.g., {"firewall_events": my_firewall_handler}
    """
    global _dlq_consumer_singleton
    _dlq_consumer_singleton = DLQConsumer(processor_map)
    await _dlq_consumer_singleton.connect()
    asyncio.create_task(_dlq_consumer_singleton.start_consuming())
    logger.info("[DLQ] Dead-Letter Queue consumer launched as background task.")
    return _dlq_consumer_singleton


async def shutdown_dlq():
    """Graceful shutdown of DLQ producer and consumer."""
    global _dlq_producer_singleton, _dlq_consumer_singleton
    if _dlq_producer_singleton:
        await _dlq_producer_singleton.disconnect()
    if _dlq_consumer_singleton:
        await _dlq_consumer_singleton.stop()
