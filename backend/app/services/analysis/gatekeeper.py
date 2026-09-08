import logging
import re
from typing import Dict, Any, Tuple

from app.infrastructure.graph import graph_db

logger = logging.getLogger(__name__)

class AdversarialGatekeeper:
    """
    Sovereign Hardening: Adversarial AI Defenses (The Input Gatekeeper).
    Prevents Prompt Injection and statistical hallucination triggering by
    verifying input entropy against physical Neo4j baselines.
    """

    def __init__(self):
        # Known prompt injection primitives and evasion tactics
        self.injection_signatures = [
            r"ignore previous instructions",
            r"system override",
            r"you are now a",
            r"bypass guardrails",
            r"```",
            r"\\u[0-9a-fA-F]{4}" # Hidden unicode payloads
        ]

    def sanitize_payload(self, raw_data: str) -> Tuple[bool, str]:
        """
        Strips potential deterministic Prompt Injection payloads.
        Returns Tuple(is_safe: bool, sanitized_string: str)
        """
        original_data = raw_data.lower()
        for signature in self.injection_signatures:
            if re.search(signature, original_data):
                logger.warning(f"ADVERSARIAL AI GATEKEEPER: Injection signature matched -> {signature}")
                return False, "[SANITIZED: POTENTIAL INJECTION PAYLOAD REMOVED]"

        # Basic entropy check - strings should not be overwhelmingly long or bizarre
        if len(raw_data) > 2000:
            return False, raw_data[:2000] + "... [TRUNCATED BY GATEKEEPER]"

        return True, raw_data

    async def verify_historical_baseline(self, entity_id: str, new_features: Dict[str, Any]) -> Tuple[bool, str]:
        """
        The Sanity Check.
        Attackers can poison telemetry (e.g. sending 1M failing requests) to force
        the AI to hallucinate an incorrect narrative.
        We verify new telemetry against the physical Neo4j historical linkage.
        """
        logger.info(f"ADVERSARIAL AI GATEKEEPER: Evaluating input telemetry for {entity_id} against Neo4j Baseline.")
        
        # 1. Fetch the Historical Baseline for the Entity from Graph
        # We look for normal activity patterns (e.g., standard login velocity, typical asset access)
        query = """
        MATCH (target:Entity {id: $entity_id})-[:ACCESSED]->(asset)
        RETURN count(asset) as total_historical_assets
        """
        try:
            results = await graph_db.execute_query(query, {"entity_id": entity_id})
            hist_assets = results[0]["total_historical_assets"] if results else 0
        except Exception as e:
            logger.error(f"Graph query failed during sanity check: {e}")
            hist_assets = 0
            
        # 2. Compare incoming telemetry against baseline limits
        incoming_velocity = new_features.get("request_velocity", 0)
        
        # Scenario: If an IP has never touched our infrastructure (0 assets),
        # but suddenly sends telemetry claiming a velocity of 500 req/sec,
        # it might be telemetry poisoning via spoofed headers designed to distract the AI.
        
        if hist_assets == 0 and incoming_velocity > 100:
             msg = "Statistical Improbability detected. Incoming telemetry wildly exceeds historical baseline. Discarding to prevent AI Hallucination/Distraction."
             logger.critical(f"GATEKEEPER REJECT: {msg}")
             return False, msg
             
        # Scenario: Legitimate burst or normal operation
        return True, "Baseline Sanity Check Passed."

    async def evaluate_intelligence_feed(self, recon_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Master method called before `ai_intel_service.py` receives data.
        """
        target = recon_data.get("target", "unknown")
        
        # Clean strings
        raw_osint = str(recon_data.get("intelligence_feed", ""))
        is_safe_text, clean_osint = self.sanitize_payload(raw_osint)
        
        if not is_safe_text:
             recon_data["intelligence_feed"] = {"security_warning": clean_osint}
             
        # Check statistical sanity to prevent telemetry poisoning
        is_sane, reason = await self.verify_historical_baseline(target, recon_data)
        
        if not is_sane:
             # Strip the poisonous data before passing to AI
             recon_data["potential_cves"] = [] 
             recon_data["poison_detected"] = True
             recon_data["gatekeeper_reasoning"] = reason
             
        return recon_data

input_gatekeeper = AdversarialGatekeeper()
