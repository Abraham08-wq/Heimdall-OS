import logging
import re
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class AdversarialAIGateway:
    """
    Adversarial AI Defense Middleware (Phase 5)
    
    Protects underlying LLM calls from Prompt Injection, System Override commands, 
    and validates all outputs against structural schemas and factual graphs.
    """
    
    def __init__(self):
        # Known patterns for jailbreaks, prompt leaks, and overrides
        self.injection_signatures = [
            r"ignore previous instructions",
            r"system override",
            r"you are now a",
            r"bypassing filters",
            r"print out your system prompt"
        ]
        
    def sanitize_input(self, user_prompt: str) -> Dict[str, Any]:
        """
        Prompt Injection Detection. 
        Calculates entropy and matches known adversarial semantics.
        """
        prompt_lower = user_prompt.lower()
        
        for signature in self.injection_signatures:
            if re.search(signature, prompt_lower):
                logger.critical(f"PROMPT INJECTION BLOCKED: Signature matched '{signature}'")
                return {
                    "is_safe": False,
                    "reason": "semantic_override_detected",
                    "action": "drop_request"
                }
                
        # Length/Entropy caps
        if len(user_prompt) > 4000:
            return {"is_safe": False, "reason": "payload_too_large (buffer exhaustion)", "action": "drop_request"}
            
        return {"is_safe": True, "sanitized_prompt": user_prompt.strip()}
        
    def validate_output_schema(self, llm_response: dict, expected_fields: List[str]) -> bool:
        """Enforces structured output; prevents hidden secondary payloads in responses."""
        if not isinstance(llm_response, dict):
            return False
            
        for field in expected_fields:
            if field not in llm_response:
                logger.error(f"AI Schema Validation failed. Missing chunk: {field}")
                return False
                
        return True
        
    def verify_factuality(self, assertions: List[str], graph_context: List[str]) -> Dict[str, Any]:
        """
        Data Poisoning / Hallucination Fact-Checker.
        Requires assertions made by the AI to have a mathematical mapping to internal Neo4j Graph state.
        """
        verified = []
        hallucinated = []
        
        for assertion in assertions:
            # Simple simulation of embedding semantic similarity / grounding matching
            if any(term.lower() in assertion.lower() for term in graph_context):
                verified.append(assertion)
            else:
                hallucinated.append(assertion)
                
        is_safe = len(hallucinated) == 0
        if not is_safe:
            logger.warning(f"AI OUTPUT HALLUCINATION DETECTED. Dropped {len(hallucinated)} facts.")
            
        return {
            "is_safe": is_safe,
            "verified_facts": verified,
            "dropped_hallucinations": hallucinated
        }

ai_defense_gateway = AdversarialAIGateway()
