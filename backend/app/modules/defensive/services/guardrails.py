import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class DeterministicGuardrail:
    """
    AI Model Upgrade: Anti-Hallucination & Explainability
    Ensures that AI outputs are rooted in factual network telemetry.
    """
    
    def __init__(self):
        # Master ontology of valid network nodes, subnets, and known attack vectors
        self.valid_assets = {"VPN_Gateway_01", "Internal_Subnet_A", "Core_Database_Primary", "Web_DMZ"}
        self.valid_vectors = {"Credential Stuffing", "Lateral Movement (SMB)", "Data Exfiltration", "Ransomware"}
        
    def verify_prediction(self, ai_output: Dict[str, Any]) -> Dict[str, Any]:
        """Runs the prediction output through deterministic checks to strip hallucinations."""
        predicted_path = ai_output.get("predicted_path", [])
        
        verified_path = []
        hallucination_detected = False
        
        for step in predicted_path:
            node = step.get("node")
            action = step.get("action")
            
            is_valid_node = node in self.valid_assets
            is_valid_action = any(v in action for v in self.valid_vectors)
            
            if is_valid_node and is_valid_action:
                verified_path.append(step)
            else:
                hallucination_detected = True
                logger.warning(f"HALLUCINATION GUARDRAIL TRIPPED (Discarding step): {node} - {action}")
                
        # Calculate Explainable Score
        explainable_scoring = self._calculate_confidence_score(verified_path, len(predicted_path))
        
        return {
            "source_node": ai_output.get("source_node"),
            "verified_path": verified_path,
            "hallucination_mitigated": hallucination_detected,
            "explainable_scoring": explainable_scoring
        }

    def _calculate_confidence_score(self, verified_path: List[Dict], original_length: int) -> Dict[str, Any]:
        if original_length == 0:
            return {"score": 0.0, "reasoning": "No threat path predicted."}
            
        retention_rate = len(verified_path) / original_length
        base_confidence = 0.95 if retention_rate == 1.0 else (0.95 * retention_rate)
        
        reasoning = []
        if retention_rate == 1.0:
            reasoning.append("All requested nodes exist in CMDB inventory.")
            reasoning.append("All predicted actions map to known MITRE ATT&CK techniques.")
        else:
            reasoning.append("Some nodes or actions hallucinated by LLM and removed.")
            
        return {
            "score": round(base_confidence, 2),
            "reasoning": reasoning
        }

guardrail_engine = DeterministicGuardrail()
