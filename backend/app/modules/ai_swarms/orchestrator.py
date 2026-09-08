import asyncio
from typing import Dict, Any
from app.modules.ai_swarms.agents import osint_hunter, reverse_engineer, profiler

class AISwarmOrchestrator:
    """
    Tier 2: The Synapse.
    Orchestrates the AI Analyst Swarm to autonomously investigate threats.
    """
    
    async def investigate_threat_cluster(self, raw_telemetry: dict) -> Dict[str, Any]:
        """
        Coordinates a multi-agent investigation.
        """
        print(f"[ORCHESTRATOR] Initializing Swarm Investigation for Telemetry ID: {raw_telemetry.get('id', 'N/A')}")
        
        # Step 1: OSINT Hunting
        osint_report = await osint_hunter.investigate(raw_telemetry)
        
        # Step 2: Reverse Engineering (Parallelizable depending on data available)
        re_report = await reverse_engineer.investigate(raw_telemetry)
        
        # Step 3: Synthesis & Profiling
        combined_context = {
            "telemetry": raw_telemetry,
            "osint_findings": osint_report.findings,
            "re_findings": re_report.findings
        }
        
        final_profile = await profiler.investigate(combined_context)
        
        # Assemble the Threat Package
        threat_package = {
            "status": "INVESTIGATION_COMPLETE",
            "threat_actor_profile": final_profile.findings,
            "confidence": min(osint_report.confidence_score, re_report.confidence_score), # Conservative confidence
            "recommended_mitigation": final_profile.recommended_action,
            "raw_reports": {
                "osint": osint_report.dict(),
                "re": re_report.dict()
            }
        }
        
        print("[ORCHESTRATOR] Swarm Investigation complete. Outputting Target Package.")
        return threat_package

swarm_director = AISwarmOrchestrator()
