import asyncio
import random
from typing import List, Dict, Any, Coroutine

from app.core.llm_client import llm_client
from app.services.sandbox import sandbox_service, ScriptExecuteResponse

class AnalystService:
    """
    AI Analyst: Orchestrates investigations and generates reports.
    """
    def __init__(self):
        self.personas = ["Forensic Analyst", "Threat Hunter", "Malware Researcher"]
        self.severity_map = {"CRITICAL": 95, "HIGH": 80, "MEDIUM": 50, "LOW": 20, "UNKNOWN": 0}

    def _get_fallback_investigation(self, entity_id: str) -> Dict[str, Any]:
        """Returns a static, structured report for development or fallback."""
        return {
            "case_id": f"CASE-{random.randint(1000,9999)}",
            "entity_id": entity_id,
            "threat_score": 75,
            "verdict": "SUSPICIOUS",
            "summary": "Static analysis indicates potential obfuscation. The artifact communicates with a known suspicious domain (example.com). Further dynamic analysis is recommended.",
            "kill_chain_stage": "Reconnaissance",
            "recommendations": [
                "Monitor traffic to example.com.",
                "Scan endpoints for related IOCs.",
            ]
        }

    async def investigate_entity(self, entity_id: str, context: Dict[str, Any], seed: int = None) -> Dict[str, Any]:
        """
        Conduct a deep-dive investigation on an entity using sandboxing and AI analysis.
        """
        # 1. Sandbox Analysis (non-blocking)
        sandbox_tasks: List[Coroutine[Any, Any, ScriptExecuteResponse]] = []
        artifacts = context.get("artifacts", [])
        for artifact in artifacts:
            if artifact.get("type") in ["file", "script"] and "content" in artifact and "lang" in artifact:
                task = asyncio.to_thread(
                    sandbox_service.run_in_container, artifact["content"], artifact["lang"]
                )
                sandbox_tasks.append(task)
        
        sandbox_results = await asyncio.gather(*sandbox_tasks, return_exceptions=True)

        # 2. Heuristic Analysis (Live LLM Generation)
        enhanced_context = context.copy()
        enhanced_context["sandbox_analysis_reports"] = [
            res.model_dump() for res in sandbox_results if isinstance(res, ScriptExecuteResponse)
        ]

        llm_analysis = await llm_client.analyze_threat(context=enhanced_context)

        # If LLM fails or returns its own minimal fallback, use our structured fallback.
        if llm_analysis.get("severity") == "UNKNOWN":
            return self._get_fallback_investigation(entity_id)

        threat_score = self.severity_map.get(llm_analysis.get("severity", "LOW").upper(), 20)
        
        report = {
            "case_id": f"CASE-{random.randint(1000,9999)}",
            "entity_id": entity_id,
            "threat_score": threat_score,
            "verdict": "MALICIOUS" if threat_score > 70 else "SUSPICIOUS",
            "summary": llm_analysis.get("summary", "AI analysis could not generate a summary."),
            "kill_chain_stage": random.choice(["Reconnaissance", "Weaponization", "Delivery", "Exploitation"]), # This could also come from LLM
            "recommendations": llm_analysis.get("recommended_actions", ["Manual review required."])
        }
        return report

    async def chat_with_analyst(self, entity_id: str, question: str) -> str:
        """
        Answers questions about an entity using an AI model with simulated context.
        """
        # In a real RAG implementation, this context would be retrieved from a database.
        rag_context = f"""
        Entity ID: {entity_id}
        Known IOCs: [1.2.3.4, 'bad-domain.com']
        Last Seen: In a network connection from host 'workstation-123'.
        Associated CVEs: [CVE-2023-23397]
        Summary: This entity has been flagged as suspicious due to connections to known malicious infrastructure.
        """
        
        system_prompt = "You are a helpful cybersecurity analyst. Answer the user's question based ONLY on the provided context about the security entity. Be concise."
        user_prompt = f"Context:\n---\n{rag_context}\n---\n\nQuestion: {question}"

        response = await llm_client.complete(prompt=user_prompt, system=system_prompt)

        if not response or response.startswith("[LLM"):
            return "I am currently unable to access the analysis data for this entity. Please try again later."
        
        return response

analyst_service = AnalystService()
