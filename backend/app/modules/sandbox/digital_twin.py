import asyncio
import logging
import httpx
from typing import Dict, Any, Optional

from app.core.config import settings
from app.infrastructure.graph import graph_db
from app.modules.deception.honeypot_generator import honeynet_ops

logger = logging.getLogger(__name__)

class DigitalTwinCoordinator:
    """
    Tier 3: The Aegis Vault.
    Digital Twin Sandboxing logic.
    Provides the infrastructure to seamlessly route an active internal attacker into an isolated, instrumented clone.
    """
    
    def __init__(self):
        self.firewall_url = getattr(settings, "FIREWALL_API_URL", None)

    async def clone_asset_to_sandbox(self, original_asset_id: str, attacker_ip: str) -> Optional[str]:
        """
        1. Delegates spawning of an isolated container (The Twin) to the honeypot service.
        2. Instruments the Twin to record every keystroke/memory interaction (future work).
        3. Logs the new architecture to the graph database.
        """
        logger.critical(f"[AEGIS VAULT] CRITICAL: Cloning internal asset {original_asset_id} to Digital Twin Sandbox for attacker {attacker_ip}...")
        
        # TODO: Implement an asset-to-profile mapping service. For now, using a default profile.
        profile_type = "WEB_APP" 

        honeypot_result = await honeynet_ops.spawn_tailored_honeypot(
            target_campaign_id=attacker_ip,
            profile_type=profile_type
        )

        if not honeypot_result:
            logger.error(f"[AEGIS VAULT] Failed to provision Digital Twin for asset {original_asset_id}.")
            return None
        
        # TODO: The underlying `honeypot_generator` service must be refactored to return a tuple of (id, port).
        # A persistent tool error prevented this change. `twin_ip` will need to be derived from the container.
        twin_id = honeypot_result
        
        # Update Omni-Graph to reflect the new defensive architecture
        query = """
        MATCH (attacker:ThreatActor {id: $attacker_ip})
        MERGE (twin:DigitalTwin {id: $twin_id})
        SET twin.source_asset = $source_asset, twin.zone = 'Sandbox', twin.profile = $profile
        
        // Log the rerouting event
        MERGE (attacker)-[r:REROUTED_TO]->(twin)
        SET r.timestamp = datetime()
        """
        try:
             await graph_db.execute_query(query, {
                 "attacker_ip": attacker_ip,
                 "twin_id": twin_id,
                 "source_asset": original_asset_id,
                 "profile": profile_type
             })
             logger.info(f"[AEGIS VAULT] Asset {original_asset_id} cloned successfully. Twin ID: {twin_id}")
             return twin_id
        except Exception as e:
             logger.error(f"[AEGIS VAULT] Failed to log twin to graph: {e}")
             # Attempt to clean up the container if graph logging fails
             # In a real system, you'd have a robust cleanup/garbage collection process.
             # await honeynet_ops.destroy_honeypot(twin_id)
             return None

    async def execute_sdn_reroute(self, original_asset_ip: str, twin_ip: str, attacker_ip: str) -> bool:
        """
        Software-Defined Networking (SDN) magic.
        Modifies firewall rules on the fly so traffic originally destined for the real asset 
        is silently NAT'd to the Digital Twin Sandbox.
        """
        logger.info(f"[SDN CONTROLLER] Triggering BGP/NAT Reroute: {attacker_ip} -> {original_asset_ip} will now be routed to {twin_ip} (Sandbox)")
        
        if not self.firewall_url:
            logger.error("[SDN CONTROLLER] FIREWALL_API_URL not configured. Cannot execute SDN reroute.")
            return False

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.firewall_url}/api/v1/routes/reroute",
                    json={
                        "source_ip": attacker_ip,
                        "original_destination_ip": original_asset_ip,
                        "new_destination_ip": twin_ip
                    },
                    timeout=10.0
                )
                response.raise_for_status()
                logger.info(f"[SDN CONTROLLER] Reroute command acknowledged by firewall API for attacker {attacker_ip}.")
                return True
            except httpx.RequestError as e:
                logger.error(f"[SDN CONTROLLER] Failed to execute SDN reroute via firewall API: {e}")
                return False

twin_orchestrator = DigitalTwinCoordinator()
