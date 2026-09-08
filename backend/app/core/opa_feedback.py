"""
opa_feedback.py — Self-Learning Defense Engine
==============================================
When the AI Firewall BLOCKs a request, this module:
1. Hashes the attack pattern → stores in Redis with TTL
2. On subsequent requests: early-exit if hash matches (skip full inference)
3. Publishes the pattern to Kafka `threat_feed` topic for SIEM ingestion
4. Maintains a rolling in-memory bloom-filter for sub-ms decision speed

Architecture:
  Cognitive Shield BLOCK → opa_feedback.learn() → Redis SETEX + Kafka publish
  Next request         → opa_feedback.check()  → Redis GET (sub-ms bypass)

This is the "self-patching" feedback loop described in Phase 4 requirements.
"""

import hashlib
import json
import logging
import time
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# In-memory bloom filter (approximate, fast, no external dep)
_BLOCKED_HASHES: set[str] = set()
_MAX_MEMORY_BLOOM = 50_000  # evict oldest when exceeded

def _normalise_pattern(text: str) -> str:
    """
    Normalise adversarial text for consistent hashing:
    - lowercase
    - collapse whitespace
    - strip zero-width chars and unicode confusables
    """
    import unicodedata
    text = unicodedata.normalize("NFKC", text.lower())
    text = " ".join(text.split())  # collapse whitespace
    # Remove zero-width chars
    for zwc in ["\u200b", "\u200c", "\u200d", "\ufeff", "\u2060"]:
        text = text.replace(zwc, "")
    return text

def _attack_hash(text: str, category: str = "") -> str:
    """SHA-256 fingerprint of a normalised attack prompt."""
    normalised = _normalise_pattern(text)
    payload = f"{category}:{normalised}"
    return hashlib.sha256(payload.encode()).hexdigest()[:24]

def _prefix_hash(text: str) -> str:
    """Shorter 12-char hash for prefix/family matching (catches obfuscation variants)."""
    normalised = _normalise_pattern(text)[:100]  # first 100 chars as family key
    return hashlib.sha256(normalised.encode()).hexdigest()[:12]


class OPAFeedbackEngine:
    """
    In-process policy feedback engine.
    Does NOT require external OPA binary — runs in-process using Redis as the
    distributed policy store so all backend replicas share state.
    """

    def __init__(self):
        self._redis = None
        self._kafka = None
        self._enabled = True

    async def _get_redis(self):
        """Lazy Redis connection — avoids import-time failures."""
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                import os
                redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
                self._redis = aioredis.from_url(redis_url, decode_responses=True)
            except Exception as e:
                logger.warning(f"[OPA] Redis unavailable: {e}")
                self._redis = None
        return self._redis

    async def _publish_to_kafka(self, event: Dict[str, Any]):
        """Publish block event to `threat_feed` Kafka topic."""
        try:
            from app.infrastructure.kafka import kafka_streamer
            await kafka_streamer.publish("threat_feed", event)
        except Exception as e:
            logger.debug(f"[OPA] Kafka publish skipped: {e}")

    async def learn(
        self,
        prompt: str,
        category: str,
        threat_score: float,
        entity_id: str = "unknown",
        tenant_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Record a confirmed adversarial pattern.
        Called by the firewall on every BLOCK decision.

        Returns the hash fingerprint for audit logging.
        """
        if not self._enabled:
            return ""

        global _BLOCKED_HASHES

        full_hash   = _attack_hash(prompt, category)
        prefix_hash = _prefix_hash(prompt)
        now         = int(time.time())

        # 1. Update in-memory bloom filter
        if len(_BLOCKED_HASHES) >= _MAX_MEMORY_BLOOM:
            # Simple eviction: clear half
            _BLOCKED_HASHES = set(list(_BLOCKED_HASHES)[_MAX_MEMORY_BLOOM // 2:])
        _BLOCKED_HASHES.add(full_hash)
        _BLOCKED_HASHES.add(prefix_hash)

        # 2. Store in Redis with 30-day TTL
        r = await self._get_redis()
        if r:
            try:
                pipe = r.pipeline()
                # Full hash → block entry
                pipe.setex(
                    f"opa:block:{full_hash}",
                    2_592_000,  # 30 days
                    json.dumps({
                        "category":    category,
                        "score":       threat_score,
                        "entity_id":   entity_id,
                        "tenant_id":   tenant_id,
                        "blocked_at":  now,
                    })
                )
                # Prefix hash → family block (catches obfuscated variants)
                pipe.setex(
                    f"opa:family:{prefix_hash}",
                    2_592_000,
                    category
                )
                # Increment category counter (for policy analytics)
                pipe.hincrby(f"opa:stats:{tenant_id}", category, 1)
                await pipe.execute()
            except Exception as e:
                logger.warning(f"[OPA] Redis write failed: {e}")

        # 3. Publish to Kafka threat_feed
        await self._publish_to_kafka({
            "event_type":   "THREAT_BLOCKED",
            "hash":         full_hash,
            "category":     category,
            "threat_score": threat_score,
            "entity_id":    entity_id,
            "tenant_id":    tenant_id,
            "timestamp":    now,
            "metadata":     metadata or {},
        })

        logger.info(f"[OPA] Learnt block pattern: {category} hash={full_hash[:8]}.. score={threat_score:.2f}")
        return full_hash

    async def check(
        self,
        prompt: str,
        category_hint: str = "",
        tenant_id: str = "default",
    ) -> Optional[Dict[str, Any]]:
        """
        Early-exit check: is this prompt already in the block policy?

        Returns:
            None          → proceed to full inference (not in policy)
            dict          → immediate BLOCK (skip ML inference entirely)

        Sub-millisecond path: bloom filter → Redis (only if bloom positive)
        """
        if not self._enabled:
            return None

        full_hash   = _attack_hash(prompt, category_hint)
        prefix_hash = _prefix_hash(prompt)

        # Fast path: in-memory bloom (O(1), no network)
        if full_hash not in _BLOCKED_HASHES and prefix_hash not in _BLOCKED_HASHES:
            return None

        # Confirm via Redis (avoid false positives from hash collisions)
        r = await self._get_redis()
        if not r:
            # Redis unavailable: let full inference decide
            return None

        try:
            # Check full hash first
            entry = await r.get(f"opa:block:{full_hash}")
            if entry:
                data = json.loads(entry)
                return {
                    "blocked":     True,
                    "reason":      f"[OPA Policy] Pattern in block list: {data.get('category', 'UNKNOWN')}",
                    "category":    data.get("category"),
                    "threat_score": data.get("score", 1.0),
                    "policy_hit":  "full_hash",
                    "hash":        full_hash,
                }

            # Check family/prefix hash (obfuscation variant)
            family_cat = await r.get(f"opa:family:{prefix_hash}")
            if family_cat:
                return {
                    "blocked":     True,
                    "reason":      f"[OPA Policy] Variant of blocked pattern family: {family_cat}",
                    "category":    family_cat,
                    "threat_score": 0.92,
                    "policy_hit":  "prefix_hash",
                    "hash":        prefix_hash,
                }

        except Exception as e:
            logger.debug(f"[OPA] Check error: {e}")

        return None

    async def get_policy_stats(self, tenant_id: str = "default") -> Dict[str, Any]:
        """Return category block counts for the policy analytics dashboard."""
        r = await self._get_redis()
        if not r:
            return {}
        try:
            stats = await r.hgetall(f"opa:stats:{tenant_id}")
            return {k: int(v) for k, v in stats.items()}
        except Exception:
            return {}

    async def revoke_hash(self, hash_key: str) -> bool:
        """Remove a hash from the policy (false positive management)."""
        r = await self._get_redis()
        if not r:
            return False
        try:
            deleted = await r.delete(f"opa:block:{hash_key}")
            _BLOCKED_HASHES.discard(hash_key)
            return deleted > 0
        except Exception:
            return False


# Singleton — imported by firewall and middleware
opa_feedback = OPAFeedbackEngine()
