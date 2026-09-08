import logging
import uuid
from typing import Dict, Any, List, Tuple

from app.modules.defensive.services.intelligence import soc_engine
from app.modules.defensive.services.containment import containment_engine
from app.services.deception.hallucinator import hallucination_engine

logger = logging.getLogger(__name__)

class DeceptionEngine:
    """
    Deception Operations Module (Phase 4)
    
    Generates invisible trap-doors, dummy schemas (Honeypots) and tracked 
    documents (Canary Tokens). Any interaction instantly triggers a High severity lockdown.
    """
    
    def __init__(self):
        # TODO: This is a mock in-memory store. In production, these artifacts must be
        # persisted to a database table (e.g., 'deception_artifacts') to be effective
        # across service restarts and multiple nodes.
        self.honeypot_endpoints: Dict[str, Dict] = {}
        self.canary_tokens: Dict[str, str] = {}
        self.credential_decoys: Dict[str, str] = {}
        
    async def create_honeypot_endpoint(self) -> str:
        """Uses the LLM to generate a plausible, fake API endpoint path."""
        system_prompt = "You generate plausible but fake API endpoint paths for use as honeypots. Respond with only the path string. Examples: /api/v1/internal/debug/user-sessions, /api/v2/admin/system/export-data"
        prompt = "Generate a new, convincing internal or admin-level API endpoint path."
        path = await hallucination_engine.llm_client.complete(prompt, system=system_prompt, temperature=0.8)
        
        # Basic cleanup if LLM adds quotes or extra text
        path = path.strip().replace('"', '').replace("'", "")
        if path and path.startswith('/api'):
            logger.info(f"Generated new honeypot endpoint: {path}")
            self.honeypot_endpoints[path] = {"type": "api_path", "created_at": "NOW"}
            return path
        return "/api/v1/system/fallback-honeypot"
        
    async def create_canary_token(self, fake_asset_description: str) -> str:
        """Creates a unique canary token for a given fake asset."""
        token = f"projxy-canary-{uuid.uuid4().hex}"
        self.canary_tokens[token] = fake_asset_description
        logger.info(f"Generated new canary token for asset '{fake_asset_description}'")
        return token

    async def deploy_invisible_traps(self, graph_db_session) -> None:
        """
        [PHASE 7: DECEPTION ENGINEERING]
        Inject invisible, dynamically-named nodes into the Neo4j graph.
        """
        # Use LLM to generate a convincing but fake service name
        fake_service_name = await hallucination_engine.llm_client.complete(
            prompt="Generate a plausible name for a critical internal backup service (e.g., 'vcenter-prod-backup-01', 'oracle-financials-archive').",
            temperature=0.7
        )
        fake_service_name = fake_service_name.strip().replace('"', '').replace("'", "")

        query = """
        MERGE (h:Honeypot:Resource {name: $name, type: 'shadow_VM'})
        MERGE (a:Honeypot:User {id: 'svc_db_backup'})
        CREATE (a)-[:ADMIN_ACCESS]->(h)
        """
        try:
            graph_db_session.run(query, {"name": fake_service_name})
            logger.info(f"Deception: Invisible trap relationships active in Graph for honeypot '{fake_service_name}'.")
        except Exception as e:
            logger.warning(f"Deception: Failed to deploy invisible traps: {e}")
            
    def evaluate_request(self, path: str, ip_address: str, user_id: str, payload_data: Any = None) -> bool:
        """
        Check if a request touched a honeypot endpoint or used decoy credentials.
        Returns True if a trap was triggered, False otherwise.
        """
        if path in self.honeypot_endpoints:
            self._trigger_trap("HONEYPOT_API_TOUCHED", path, ip_address, user_id)
            return True
            
        if payload_data and isinstance(payload_data, dict):
            # Evaluate for Credential Decoys
            attempted_user = payload_data.get("username", "")
            if attempted_user in self.credential_decoys:
                self._trigger_trap("CREDENTIAL_DECOY_USED", attempted_user, ip_address, user_id)
                return True
                
        return False
        
    def check_exfiltrated_canary(self, token_found: str, ip_address: str, context: str):
        """
        Invoked conditionally if a monitoring hook spots a canary token being used 
        anywhere in request payloads or outbound traffic.
        """
        if token_found in self.canary_tokens:
            fake_asset = self.canary_tokens[token_found]
            self._trigger_trap("CANARY_EXFILTRATION_TOUCHED", fake_asset, ip_address, "unknown")
            
    def _trigger_trap(self, trap_type: str, asset: str, ip_address: str, user_id: str):
        """Execute immediate maximum-severity lockdown for deception triggers."""
        logger.critical(f"DECEPTION TRAP TRIGGERED: Type {trap_type} via IP {ip_address} on asset {asset}")
        
        # 1. Alerting
        soc_engine.trigger_alert(
            severity="CRITICAL", 
            source="DECEPTION_ENGINE", 
            message=f"Adversary interacted with trap ({trap_type}: {asset}) from {ip_address}."
        )
        
        # 2. Instant Containment
        containment_engine.isolate_entity(
            entity_id=f"ip_entity_{ip_address}",
            reason=f"Deception trap triggered: {asset}",
            duration_seconds=86400 # 24-hour instant block
        )
        
        if user_id and user_id != "unknown":
            containment_engine.isolate_entity(
                entity_id=user_id,
                reason=f"Deception trap triggered via compromised session: {asset}",
                duration_seconds=86400
            )

deception_ops = DeceptionEngine()
