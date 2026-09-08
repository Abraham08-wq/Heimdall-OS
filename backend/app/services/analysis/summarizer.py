import os
from pathlib import Path
from typing import List
from app.schemas.entity import Entity
from app.schemas.evidence import Evidence
# Fake LLM wrapper for demonstration (replace with OpenAI/LangChain in prod)
# from langchain.llms import OpenAI

class IntelligenceSummarizer:
    def __init__(self):
        self.prompt_path = Path("/home/bantu/Documents/ProjectXY/ai_engine/prompts/summary_prompt.txt")
        self.template = self._load_template()

    def _load_template(self) -> str:
        if not self.prompt_path.exists():
            return "Error: Prompt template not found."
        return self.prompt_path.read_text()

    def format_evidence(self, evidence: List[Evidence]) -> str:
        return "\n".join([f"- [ID: {e.id}] ({e.reliability.value}): {e.source_url}" for e in evidence])

    async def generate_summary(self, entity: Entity, evidence: List[Evidence]) -> str:
        """
        Generates a summary profile.
        """
        # 1. Prepare Context
        context = self.format_evidence(evidence)
        attributes = ", ".join([f"{a.type}: {a.value}" for a in entity.attributes])
        
        # 2. Fill Template
        prompt = self.template.format(
            canonical_name=entity.canonical_name,
            attributes_list=attributes,
            risk_score=entity.risk_score,
            evidence_context=context
        )
        
        # 3. Simulate High-Fidelity Output (Since we don't have an API Key)
        # In a real deployment, this would be: 
        # response = await openai.ChatCompletion.create(model="gpt-4", messages=[...])
        
        risk_desc = "CRITICAL" if entity.risk_score > 80 else "HIGH" if entity.risk_score > 50 else "MODERATE"
        
        simulated_response = (
            f"**INTELLIGENCE BRIEFING: {entity.canonical_name}**\n\n"
            f"Subject is identified as a **{entity.type.value.upper()}** with a calculated risk score of **{entity.risk_score}/100** ({risk_desc}). "
            f"Primary indicators include {len(entity.attributes)} attribute(s) linked to known threat vectors. "
            f"\n\n**Assessment:** IMMEDIATE ACTION REQUIRED. The entity exhibits patterns consistent with {risk_desc} threat activity. "
            f"Recommended containment protocols should be activated."
        )
        
        return simulated_response

summarizer = IntelligenceSummarizer()
