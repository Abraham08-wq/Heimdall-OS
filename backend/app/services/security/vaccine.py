import asyncio
import logging
import json
from typing import Dict, Any

from app.infrastructure.cache.redis_manager import redis_cache
from app.services.combat import combat_orchestrator

logger = logging.getLogger(__name__)

class HiveMindInoculationEngine:
    """
    Sovereign Weapon: Hive-Mind Inoculation.
    Distributes zero-day threat "Vaccines" across all connected tenants
    the microsecond one tenant is attacked and successfully mitigates it.
    """
    
    GLOBAL_CHANNEL = "global_threat_intel"

    def __init__(self):
        # Local, in-memory representation of distributed blocklists injected into WAFs
        self.local_deny_lists: Dict[str, set] = {}

    async def publish_vaccine(self, source_tenant: str, threat_ip: str, signature: Dict[str, Any]):
        """
        Broadcasts a confirmed attacker fingerprint to the global Redis network.
        """
        logger.critical(f"HIVE-MIND: Extracting vaccine from {source_tenant} attack (Target: {threat_ip})")
        
        payload = {
            "origin_tenant": source_tenant,
            "threat_ip": threat_ip,
            "signature": signature,
            "action": "AUTO_INOCULATE"
        }
        
        try:
            await redis_cache.redis_client.publish(self.GLOBAL_CHANNEL, json.dumps(payload))
            logger.info("HIVE-MIND: Vaccine successfully published to global network.")
        except Exception as e:
            logger.error(f"Failed to publish vaccine: {e}")

    async def start_vaccination_listener(self):
        """
        Background daemon listening to the Global Threat channel.
        Automatically updates local tenant firewalls when a vaccine is received.
        Includes exponential backoff retry so Redis connectivity issues never abort server startup.
        """
        retry_delay = 5
        max_retry_delay = 60

        while True:
            try:
                pubsub = redis_cache.redis_client.pubsub()
                await pubsub.subscribe(self.GLOBAL_CHANNEL)
                logger.info(f"HIVE-MIND: Subscribed to {self.GLOBAL_CHANNEL}. Listening for cross-tenant vaccines.")
                retry_delay = 5  # Reset on successful connection

                async for message in pubsub.listen():
                    if message["type"] == "message":
                        data = json.loads(message["data"])
                        threat_ip = data.get("threat_ip")
                        origin = data.get("origin_tenant")

                        if origin not in self.local_deny_lists:
                            self.local_deny_lists[origin] = set()

                        for tenant in self.local_deny_lists.keys():
                            if tenant != origin:
                                self.local_deny_lists[tenant].add(threat_ip)
                                logger.warning(f"HIVE-MIND: Inoculated tenant '{tenant}' against {threat_ip} (Source: {origin})")

                        await combat_orchestrator.broadcast_dashboard("GLOBAL_INOCULATION_EVENT", {
                            "threat_ip": threat_ip,
                            "origin": origin,
                            "status": "VACCINATED_GLOBALLY"
                        })

            except Exception as e:
                logger.warning(f"HIVE-MIND: Redis listener disconnected ({e}). Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)

vaccine_engine = HiveMindInoculationEngine()
