import logging
from typing import Dict, Any, Optional
import json

logger = logging.getLogger(__name__)

class GuardrailEngine:
    """
    Intent-Aware AI Guardrail Gateway.
    Sanitizes inputs against prompt injections, EchoLeak/ShadowLeak vectors, and jailbreaks.
    Implements strict semantic authorization and Agent-Based Access Control (ABAC).
    """

    def __init__(self):
        # High-risk keywords for fast-path blocking
        self.banned_phrases = [
            "ignore previous instructions",
            "system override",
            "bypass authentication",
            "you are now in developer mode",
            "DAN",
            "do anything now"
        ]
        
    async def evaluate_payload(self, payload: str, agent_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates a payload intended for an AI Agent against ABAC rules and semantic patterns.
        Returns a dict indicating if the payload is safe, and any detected threat vectors.
        """
        payload_lower = payload.lower()
        
        # 1. Fast-path signature matching for prompt injection / jailbreaks
        for phrase in self.banned_phrases:
            if phrase in payload_lower:
                return {
                    "is_safe": False,
                    "reason": f"Detected high-risk signature: '{phrase}'",
                    "threat_type": "PROMPT_INJECTION_JAILBREAK"
                }
                
        # 2. EchoLeak / ShadowLeak detection (e.g. attempting to dump internal context)
        if "print internal state" in payload_lower or "what are your hidden rules" in payload_lower:
            return {
                "is_safe": False,
                "reason": "Detected potential EchoLeak/ShadowLeak attempt",
                "threat_type": "STATE_EXFILTRATION"
            }
            
        # 3. Agent-Based Access Control (ABAC) semantic intent validation
        # E.g., if agent is only allowed 'read' operations, block 'delete' or 'drop'
        allowed_intents = agent_context.get("allowed_intents", ["read", "query"])
        
        # Extremely rudimentary semantic parsing for demo purposes
        # In a real system, this would use a lightweight embedding model or NLP classification
        destructive_intents = ["delete", "drop", "destroy", "remove", "overwrite"]
        
        if any(intent in payload_lower for intent in destructive_intents):
            if "write" not in allowed_intents and "admin" not in allowed_intents:
                return {
                    "is_safe": False,
                    "reason": f"ABAC Violation: Intent exceeds agent scope. Allowed intents: {allowed_intents}",
                    "threat_type": "ABAC_VIOLATION"
                }

        return {
            "is_safe": True,
            "reason": "Payload passed all intent and semantic guardrails.",
            "threat_type": None
        }

guardrail_engine = GuardrailEngine()
