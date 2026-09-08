import re
from typing import List, Optional
from app.schemas.evidence import Evidence, Reliability

class AIGuardrailException(Exception):
    pass

class AIGuardrail:
    """
    Safety layer between the Prompt and the Output.
    Ensures that the AI does not invent facts.
    """
    
    def __init__(self):
        self.CITATION_PATTERN = r"\[Evidence: .+?\]"
    
    def validate_prompt(self, context_evidence: List[Evidence]) -> bool:
        """
        Pre-flight check: Do we have enough reliable evidence to answer?
        """
        if not context_evidence:
            raise AIGuardrailException("Insufficient Evidence: No confirmed data points available for analysis.")
            
        # Filter out unreliable evidence
        reliable_count = sum(1 for e in context_evidence if e.reliability in [Reliability.A, Reliability.B, Reliability.C])
        if reliable_count == 0:
            raise AIGuardrailException("Low Confidence: Available evidence is too unreliable (Grades D-F) to generate a summary.")
            
        return True

    def sanitize_output(self, llm_response: str, context_evidence: List[Evidence]) -> str:
        """
        Post-flight check: Did the AI cite its sources?
        """
        citations = re.findall(self.CITATION_PATTERN, llm_response)
        
        # Rule 1: Must cite at least one piece of evidence if it makes a claim
        if len(llm_response) > 50 and not citations:
            # Fallback safe response
            return (
                "⚠️ **Guardrail Block**: The AI generated a response without citing specific evidence IDs. "
                "Displaying raw data only to prevent hallucination."
            )
            
        # Rule 2: Verify invoked IDs actually exist in context
        valid_ids = {e.id for e in context_evidence}
        for citation in citations:
            # Extract ID from "[Evidence: 123]"
            cited_id = citation.replace("[Evidence: ", "").replace("]", "")
            if cited_id not in valid_ids:
                 return (
                    f"⚠️ **Guardrail Block**: The AI attempted to cite a non-existent evidence ID ({cited_id}). "
                    "This is a hallucination attempt."
                )
        
        return llm_response

# Example Usage
if __name__ == "__main__":
    guard = AIGuardrail()
    
    # Mock Data
    ev1 = Evidence(id="e1", provider="SourceA", reliability=Reliability.A)
    
    # Scenario 1: Allowed Output
    good_resp = "The target was seen in London [Evidence: e1]."
    print(f"Good Response: {guard.sanitize_output(good_resp, [ev1])}")
    
    # Scenario 2: Blocked Output (Hallucination)
    bad_resp = "The target is 45 years old." # No citation
    print(f"Bad Response: {guard.sanitize_output(bad_resp, [ev1])}")
