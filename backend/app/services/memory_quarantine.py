import redis.asyncio as redis
import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class MemoryQuarantineService:
    """
    Agent Containment Service.
    Freezes an agent's short-term memory state in Redis to prevent memory poisoning 
    and preserves forensic evidence.
    """
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.client = None

    async def connect(self):
        if not self.client:
            self.client = redis.from_url(self.redis_url, decode_responses=True)

    async def freeze_agent_memory(self, agent_id: str, tenant_id: str) -> bool:
        """
        Moves the agent's active memory keys into a persistent, read-only forensic namespace.
        """
        await self.connect()
        try:
            active_key = f"agent_memory:{tenant_id}:{agent_id}:active"
            forensic_key = f"forensic:agent_memory:{tenant_id}:{agent_id}:quarantined"
            
            # Read existing active memory
            active_state = await self.client.get(active_key)
            if active_state:
                # Save to forensic namespace (persistent, no TTL)
                await self.client.set(forensic_key, active_state)
                # Delete active memory to halt execution context
                await self.client.delete(active_key)
                
                logger.warning(f"Agent {agent_id} memory frozen and quarantined successfully.")
                return True
            else:
                logger.info(f"No active memory found for Agent {agent_id} during freeze.")
                return False
                
        except Exception as e:
            logger.error(f"Failed to freeze agent memory for {agent_id}: {e}")
            return False

memory_quarantine = MemoryQuarantineService()
