import json
import logging
from typing import Optional, Any
import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)

class RedisCacheManager:
    """
    Sub-200ms Threat State Caching for the Unified Operational Pipeline.
    Manages active Mission states and rate-limiting payloads across the cluster.
    """
    
    def __init__(self):
        self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

    async def get_mission_state(self, mission_id: str) -> Optional[dict]:
        """Retrieves a cached mission state in real-time."""
        try:
            data = await self.redis_client.get(f"mission:{mission_id}")
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Redis Cache Miss/Error for {mission_id}: {e}")
            return None

    async def cache_mission_state(self, mission_id: str, state: dict, expire_seconds: int = 3600):
        """Persists the live state to Redis for immediate WebSocket/API retrieval."""
        try:
            await self.redis_client.setex(
                name=f"mission:{mission_id}", 
                time=expire_seconds, 
                value=json.dumps(state)
            )
        except Exception as e:
            logger.error(f"Failed to cache mission state {mission_id}: {e}")

    async def increment_threat_counter(self, target_ip: str) -> int:
        """Atomic counter for throttling logic."""
        key = f"threat_count:{target_ip}"
        try:
             count = await self.redis_client.incr(key)
             # Set generic expiry on initial increment
             if count == 1:
                 await self.redis_client.expire(key, 600)  # 10 minute rolling window
             return count
        except Exception as e:
             logger.error(f"Redis increment failed for {target_ip}: {e}")
             return 0

    # --- Pillar 1: Multi-Tier Caching for ABAC & UI State ---
    
    async def get_abac_policy(self, user_id: str, tenant_id: str) -> Optional[dict]:
        """Sub-10ms retrieval of calculated ABAC permissions."""
        try:
            data = await self.redis_client.get(f"abac:{tenant_id}:{user_id}")
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"ABAC Cache Miss/Error for {user_id}: {e}")
            return None

    async def cache_abac_policy(self, user_id: str, tenant_id: str, policy: dict, expire_seconds: int = 300):
        """Caches ABAC evaluation for 5 minutes."""
        try:
            await self.redis_client.setex(
                name=f"abac:{tenant_id}:{user_id}", 
                time=expire_seconds, 
                value=json.dumps(policy)
            )
        except Exception as e:
            logger.error(f"Failed to cache ABAC policy for {user_id}: {e}")

    async def get_ui_state(self, tenant_id: str, component: str) -> Optional[dict]:
        """Retrieves high-frequency UI state (e.g., active topology layout)."""
        try:
            data = await self.redis_client.get(f"ui_state:{tenant_id}:{component}")
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"UI State Cache Miss/Error for {component}: {e}")
            return None

    async def cache_ui_state(self, tenant_id: str, component: str, state: dict, expire_seconds: int = 60):
        """Caches volatile UI state for 60 seconds to prevent DB hammering on reloads."""
        try:
            await self.redis_client.setex(
                name=f"ui_state:{tenant_id}:{component}", 
                time=expire_seconds, 
                value=json.dumps(state)
            )
        except Exception as e:
            logger.error(f"Failed to cache UI state for {component}: {e}")

redis_cache = RedisCacheManager()
