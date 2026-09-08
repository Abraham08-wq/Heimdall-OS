import asyncio
import json
import logging
import docker
from docker.errors import DockerException
from typing import Dict, Optional, Tuple
from app.infrastructure.graph import graph_db

logger = logging.getLogger(__name__)

class HoneynetGenerator:
    """
    Tier 1: Dynamic Labyrinth Generation.
    This service interfaces with Docker to dynamically spawn high-interaction honeypots.
    The type of honeypot spawned is determined by current AI intelligence.
    """
    
    def __init__(self):
        self.active_nets: Dict[str, dict] = {}
        self.client = None
        # Mapping of honeypot profiles to Docker images and their internal ports
        self.profile_map = {
            "FINANCIAL_DB": {"image": "postgres:13-alpine", "port": 5432},
            "SSH": {"image": "linuxserver/openssh-server:latest", "port": 2222},
            "WEB_APP": {"image": "httpd:2.4-alpine", "port": 80},
        }
        try:
            self.client = docker.from_env(timeout=5)
            self.client.ping()
            logger.info("[DECEPTION] Docker client initialized successfully for HoneynetGenerator.")
        except DockerException as e:
            logger.error(f"[DECEPTION] Failed to initialize Docker client: {e}. HoneynetGenerator will run in mock mode.")
            self.client = None
        
    async def spawn_tailored_honeypot(self, target_campaign_id: str, profile_type: str = "FINANCIAL_DB") -> Optional[str]:
        """
        Spawns a specific Docker image designed to look like a vulnerable asset.
        Falls back to mock deployment in DEV mode or if Docker is unavailable.
        """
        logger.info(f"[DECEPTION] Planning to spawn honeypot type: {profile_type} for campaign {target_campaign_id}")

        profile = self.profile_map.get(profile_type)
        if not profile:
            logger.error(f"[DECEPTION] Unknown honeypot profile type: {profile_type}")
            return None

        # Live Mode: Spawn a real Docker container
        if self.client:
            try:
                # This synchronous block will be run in a separate thread
                def _run_container():
                    container = self.client.containers.run(
                        profile["image"],
                        detach=True,
                        ports={f'{profile["port"]}/tcp': None}, # Let Docker assign a random high-numbered host port
                        labels={
                            "projectxy_honeypot": "true",
                            "campaign": target_campaign_id,
                            "profile": profile_type
                        },
                        # Add environment variables for some images if needed, e.g., Postgres
                        environment={"POSTGRES_PASSWORD": "mysecretpassword"} if profile_type == "FINANCIAL_DB" else {},
                    )
                    # We need to reload the container object to get the port mapping
                    container.reload()
                    host_port = container.ports[f'{profile["port"]}/tcp'][0]['HostPort']
                    return container.id, int(host_port)

                deployment_id, exposed_port = await asyncio.to_thread(_run_container)
                logger.info(f"[DECEPTION] Successfully spawned container {deployment_id} ({profile['image']}) on host port {exposed_port}")

            except DockerException as e:
                logger.error(f"[DECEPTION] Docker operation failed: {e}. Falling back to mock deployment.")
                # Fall through to mock deployment on failure
                deployment_id = f"hp-mock-{profile_type.lower()}"
                exposed_port = profile["port"]
        # Mock Mode: Fallback for DEV or Docker failure
        else:
            logger.warning("[DECEPTION] Docker client unavailable. Using mock deployment.")
            
            deployment_id = f"hp-mock-{profile_type.lower()}"
            exposed_port = profile["port"]
            await asyncio.sleep(0.1) # Simulate latency

        # Log to Graph to track our deployed infrastructure (real or mocked)
        query = """
        MERGE (hp:Honeypot {id: $id})
        SET hp.type = $type, hp.port = $port, hp.campaign = $campaign, hp.zone = 'Labyrinth', hp.status = 'active'
        """
        try:
            await graph_db.execute_query(query, {
                "id": deployment_id,
                "type": profile_type, 
                "port": exposed_port,
                "campaign": target_campaign_id
            })
            logger.info(f"[DECEPTION] Graph node for honeypot {deployment_id} initialized.")
            return deployment_id
        except Exception as e:
            logger.error(f"[DECEPTION] Failed to register honeypot in graph: {e}")
            return None

honeynet_ops = HoneynetGenerator()
