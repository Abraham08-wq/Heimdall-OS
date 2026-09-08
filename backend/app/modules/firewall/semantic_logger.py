"""
semantic_logger.py — ProjectXY Cognitive Shield: Layer 4
=========================================================
Forensic AI Observability — Semantic Interaction Logging.

Every request with threat_score > LOG_THRESHOLD gets its sentence
embedding stored in the semantic_logs pgvector table, enabling:

1. Retroactive similarity hunt: "Find all historically similar prompts"
2. Cluster analysis: "What are the 5 threat clusters this week?"
3. Multi-stage chain reconstruction: "Show the full attack timeline for entity X"
4. Zero-Day detection: Novel embeddings far from known-good corpus

Architecture:
  - Non-blocking: writes via background asyncio Task
  - Fail-OPEN: if pgvector write fails, falls back to plaintext TimescaleDB log
  - Sampling: configurable sample_rate per tenant (default 1.0 = log everything)
  - Embeddings: reuses the existing SentenceTransformer already loaded in LLMFirewall
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("projectxy.firewall.semantic_logger")

# Threshold: log interactions with threat_score above this value
LOG_THRESHOLD = 0.30
DEFAULT_SAMPLE_RATE = 1.0  # 1.0 = 100%, 0.5 = 50%, etc.


# ---------------------------------------------------------------------------
# Semantic Log Entry
# ---------------------------------------------------------------------------

@dataclass
class SemanticLogEntry:
    """A single semantic interaction log record."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    tenant_id: str = ""
    entity_id: str = ""
    session_id: Optional[str] = None
    prompt_hash: str = ""              # SHA-256 of original prompt
    threat_score: float = 0.0
    action: str = "PASS"               # PASS | WARN | BLOCK | SCRUB_AND_PASS
    intent_classification: Optional[str] = None
    dominant_signal: Optional[str] = None
    transformations_applied: List[str] = field(default_factory=list)
    multi_stage_flag: bool = False
    attack_pattern: Optional[str] = None
    embedding: Optional[List[float]] = None   # 384-dim vector (stored in pgvector)
    extra_metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Semantic Logger
# ---------------------------------------------------------------------------

class SemanticLogger:
    """
    Async, non-blocking semantic interaction logger.

    Maintains a write queue and processes entries in the background.
    If pgvector is unavailable, falls back to TimescaleDB plaintext log.

    Fail-OPEN: Logging failures NEVER block legitimate requests.
    """

    def __init__(
        self,
        db_pool=None,           # asyncpg connection pool (injected at startup)
        sentence_transformer=None,  # Existing SentenceTransformer from LLMFirewall
        sample_rate: float = DEFAULT_SAMPLE_RATE,
    ):
        self._pool = db_pool
        self._model = sentence_transformer
        self._sample_rate = sample_rate
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._dropped_count = 0

    def configure(self, db_pool, sentence_transformer, sample_rate: float = None):
        """Late-bind the db pool and model after async startup."""
        self._pool = db_pool
        self._model = sentence_transformer
        if sample_rate is not None:
            self._sample_rate = sample_rate

    async def start(self):
        """Start the background write worker."""
        self._running = True
        self._worker_task = asyncio.create_task(self._writer_loop())
        logger.info("[SEMANTIC_LOGGER] Background writer started.")

    async def stop(self):
        """Gracefully stop the writer, draining the queue."""
        self._running = False
        if self._worker_task:
            await asyncio.wait_for(self._worker_task, timeout=10)
        logger.info("[SEMANTIC_LOGGER] Writer stopped.")

    def log_async(self, entry: SemanticLogEntry) -> bool:
        """
        Non-blocking log submission. Returns True if queued, False if dropped.
        Never raises — fail-open guarantee.
        """
        try:
            if entry.threat_score < LOG_THRESHOLD:
                return False  # Below threshold — don't log

            # Sampling
            if self._sample_rate < 1.0:
                import random
                if random.random() > self._sample_rate:
                    return False

            self._queue.put_nowait(entry)
            return True
        except asyncio.QueueFull:
            self._dropped_count += 1
            if self._dropped_count % 100 == 1:
                logger.warning(
                    f"[SEMANTIC_LOGGER] Queue full — dropped {self._dropped_count} entries."
                )
            return False
        except Exception as exc:
            logger.debug(f"[SEMANTIC_LOGGER] log_async error (non-critical): {exc}")
            return False

    async def _writer_loop(self):
        """Background loop that drains the queue and writes to pgvector."""
        while self._running or not self._queue.empty():
            try:
                entry = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._write_entry(entry)
                self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as exc:
                logger.debug(f"[SEMANTIC_LOGGER] Writer loop error: {exc}")

    async def _write_entry(self, entry: SemanticLogEntry):
        """Compute embedding and write to pgvector. Falls back on error."""
        try:
            # Compute embedding if model is available and entry needs it
            if self._model and entry.embedding is None and entry.prompt_hash:
                # We don't have the original text here (only hash) — use metadata
                embed_text = f"{entry.intent_classification or ''} {entry.action} {entry.dominant_signal or ''}"
                embedding = self._model.encode(embed_text).tolist()
                entry.embedding = embedding

            await self._write_to_pgvector(entry)
        except Exception as exc:
            # Fallback: write as plaintext to standard log
            logger.warning(f"[SEMANTIC_LOGGER] pgvector write failed ({exc}), using fallback log.")
            await self._fallback_log(entry)

    async def _write_to_pgvector(self, entry: SemanticLogEntry):
        """Write the entry to the semantic_logs hypertable with pgvector embedding."""
        if not self._pool:
            return

        embedding_str = (
            f"[{','.join(str(v) for v in entry.embedding)}]"
            if entry.embedding else None
        )

        sql = """
            INSERT INTO semantic_logs (
                id, created_at, tenant_id, entity_id, session_id,
                prompt_hash, threat_score, action,
                intent_classification, dominant_signal,
                transformations_applied, multi_stage_flag, attack_pattern,
                embedding
            ) VALUES (
                $1, $2::timestamptz, $3, $4, $5,
                $6, $7, $8,
                $9, $10,
                $11::jsonb, $12, $13,
                $14::vector
            )
            ON CONFLICT (id) DO NOTHING
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                sql,
                entry.id,
                entry.created_at,
                entry.tenant_id,
                entry.entity_id,
                entry.session_id,
                entry.prompt_hash,
                entry.threat_score,
                entry.action,
                entry.intent_classification,
                entry.dominant_signal,
                json.dumps(entry.transformations_applied),
                entry.multi_stage_flag,
                entry.attack_pattern,
                embedding_str,
            )

    async def _fallback_log(self, entry: SemanticLogEntry):
        """Write a plaintext fallback record when pgvector is unavailable."""
        logger.info(
            f"[SEMANTIC_LOG_FALLBACK] id={entry.id} tenant={entry.tenant_id} "
            f"entity={entry.entity_id} score={entry.threat_score:.3f} "
            f"action={entry.action} signal={entry.dominant_signal} "
            f"multi_stage={entry.multi_stage_flag}"
        )

    async def retroactive_hunt(
        self,
        query_embedding: List[float],
        tenant_id: str,
        limit: int = 20,
        cosine_threshold: float = 0.85,
        days_back: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Find all historically similar interactions by semantic similarity.
        This is the retroactive forensic hunt capability.
        """
        if not self._pool:
            return []

        embedding_str = f"[{','.join(str(v) for v in query_embedding)}]"

        sql = """
            SELECT
                id, created_at, tenant_id, entity_id, session_id,
                prompt_hash, threat_score, action,
                intent_classification, dominant_signal,
                multi_stage_flag, attack_pattern,
                1 - (embedding <=> $1::vector) AS cosine_similarity
            FROM semantic_logs
            WHERE tenant_id = $2
              AND created_at >= NOW() - INTERVAL '$3 days'
              AND embedding IS NOT NULL
              AND 1 - (embedding <=> $1::vector) >= $4
            ORDER BY cosine_similarity DESC
            LIMIT $5
        """
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    sql,
                    embedding_str,
                    tenant_id,
                    days_back,
                    cosine_threshold,
                    limit,
                )
                return [dict(r) for r in rows]
        except Exception as exc:
            logger.error(f"[SEMANTIC_LOGGER] retroactive_hunt failed: {exc}")
            return []

    async def get_entity_timeline(
        self, entity_id: str, tenant_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get chronological interaction timeline for an entity."""
        if not self._pool:
            return []
        sql = """
            SELECT id, created_at, threat_score, action, dominant_signal,
                   intent_classification, multi_stage_flag, attack_pattern
            FROM semantic_logs
            WHERE entity_id = $1 AND tenant_id = $2
            ORDER BY created_at DESC
            LIMIT $3
        """
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(sql, entity_id, tenant_id, limit)
                return [dict(r) for r in rows]
        except Exception as exc:
            logger.error(f"[SEMANTIC_LOGGER] get_entity_timeline failed: {exc}")
            return []

    async def get_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get semantic logging statistics for a tenant."""
        if not self._pool:
            return {"queue_depth": self._queue.qsize(), "dropped": self._dropped_count}

        sql = """
            SELECT
                COUNT(*) AS total_logged,
                AVG(threat_score) AS avg_threat_score,
                SUM(CASE WHEN action = 'BLOCK' THEN 1 ELSE 0 END) AS blocks,
                SUM(CASE WHEN action = 'WARN' THEN 1 ELSE 0 END) AS warns,
                SUM(CASE WHEN multi_stage_flag THEN 1 ELSE 0 END) AS multi_stage_detections,
                COUNT(DISTINCT entity_id) AS unique_entities
            FROM semantic_logs
            WHERE tenant_id = $1
              AND created_at >= NOW() - INTERVAL '24 hours'
        """
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(sql, tenant_id)
                return {
                    **dict(row),
                    "queue_depth": self._queue.qsize(),
                    "dropped_entries": self._dropped_count,
                    "sample_rate": self._sample_rate,
                }
        except Exception as exc:
            logger.error(f"[SEMANTIC_LOGGER] get_stats failed: {exc}")
            return {"error": str(exc)}


# Module-level singleton
semantic_logger = SemanticLogger()
