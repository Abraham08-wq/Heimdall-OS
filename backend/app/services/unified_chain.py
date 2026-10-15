import asyncio
import logging
from uuid import uuid4
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import BackgroundTasks

from app.schemas.mission import Mission, MissionPhase, Dossier, EnrichmentResult, DemaskingResult
from app.services.discovery_service import unified_probe
from app.services.intel.enrichment import enrichment_engine
from app.services.intel.demasking import NeuralDeMasking
from app.services.intel.retriever import unified_retriever
from app.services.response_orchestrator import response_orchestrator
from app.services.sandbox_manager import sandbox_orchestrator
from app.services.financial_risk import financial_risk_engine

logger = logging.getLogger(__name__)

class UnifiedIntelligenceChain:
    """
    The Master Operational Pipeline for ProjectXY.
    Drives a mission through RECON -> ANALYZE -> EXECUTE -> PERSIST anonymously 
    via FastAPI BackgroundTasks without blocking HTTP requests.
    """
    
    def __init__(self):
        # In-memory mission store for MVP caching. In production, this syncs with Redis.
        self.active_missions: Dict[str, Mission] = {}

    def initiate_mission(
        self,
        target: str,
        tenant_id: str,
        background_tasks: BackgroundTasks,
        # FIXED: mission_router.py's launch_unified_mission() has always called this
        # with mode= and priority= keyword arguments (they come straight from the
        # frontend's MissionLaunchRequest) -- this method just never accepted them,
        # so every single POST /missions/launch raised a TypeError and 500'd before
        # a mission was ever actually created.
        mode: str = "full",
        priority: str = "MEDIUM",
        # ADDED: see the matching note on Mission.objective/techniques in
        # schemas/mission.py -- the frontend already sends these, they just
        # had nowhere to land.
        objective: Optional[str] = None,
        techniques: Optional[list] = None,
    ) -> Mission:
        """
        Launches the Intelligence Chain against a target. Returns immediately.
        """
        mission_id = f"MIS-{str(uuid4())[:8].upper()}"
        mission = Mission(
            mission_id=mission_id,
            tenant_id=tenant_id,
            target_entity=target,
            phase=MissionPhase.RECON,
            mode=mode,
            priority=priority,
            objective=objective,
            techniques=techniques or [],
        )
        
        self.active_missions[mission_id] = mission
        logger.info(f"[{mission_id}] Mission Initiated against {target} (mode={mode}, priority={priority})")
        
        # Dispatch the pipeline to the background
        background_tasks.add_task(self._process_mission_lifecycle, mission_id)
        
        return mission

    async def abort_mission(self, mission_id: str) -> None:
        """
        ADDED: mission_router.py's DELETE /missions/{id} has always called this,
        but it never existed on this class -- every abort attempt raised an
        AttributeError and 500'd.

        This is a COOPERATIVE abort: FastAPI's BackgroundTasks doesn't hand back
        a cancellable asyncio.Task, so there's no way to forcibly interrupt a
        phase already in flight. Instead, _process_mission_lifecycle checks
        mission.phase before starting each phase and stops early if it sees
        ABORTED here -- so a mission is genuinely halted before its next phase,
        even though the phase already running when abort was called will still
        finish that one step first.
        """
        mission = self.active_missions.get(mission_id)
        if not mission:
            raise ValueError(f"Mission {mission_id} not found")
        if mission.phase in {MissionPhase.COMPLETED, MissionPhase.FAILED, MissionPhase.ABORTED}:
            raise ValueError(f"Mission {mission_id} is already in a terminal state: {mission.phase}")

        mission.phase = MissionPhase.ABORTED
        mission.updated_at = datetime.utcnow()
        mission.execution_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "ABORT",
            "status": "SUCCESS",
            "details": {"reason": "Operator-initiated abort"},
        })
        logger.warning(f"[{mission_id}] Mission aborted by operator.")

    async def escalate_mission(self, mission_id: str, new_priority: str, reason: str, operator: str) -> None:
        """
        ADDED: mission_router.py's POST /missions/{id}/escalate has always
        called this, but it never existed on this class either -- same
        AttributeError/500 as abort_mission above.
        """
        mission = self.active_missions.get(mission_id)
        if not mission:
            raise ValueError(f"Mission {mission_id} not found")

        old_priority = mission.priority
        mission.priority = new_priority
        mission.updated_at = datetime.utcnow()
        mission.execution_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "ESCALATE",
            "status": "SUCCESS",
            "details": {
                "old_priority": old_priority,
                "new_priority": new_priority,
                "reason": reason,
                "operator": operator,
            },
        })
        logger.warning(f"[{mission_id}] Escalated {old_priority} -> {new_priority} by {operator}: {reason}")

    async def _process_mission_lifecycle(self, mission_id: str):
        """
        The central asynchronous state machine coordinating the Smart Weapon.
        """
        mission = self.active_missions.get(mission_id)
        if not mission:
            return

        try:
            # PHASE I: RECON (The Probe)
            await self._phase_recon(mission)
            # ADDED: cooperative abort check -- see abort_mission()'s docstring above.
            if mission.phase == MissionPhase.ABORTED:
                return
            
            # PHASE II: ANALYZE (The Brain)
            await self._phase_analyze(mission)
            if mission.phase == MissionPhase.ABORTED:
                return
            
            # PHASE III: EXECUTE (The Action)
            await self._phase_execute(mission)
            if mission.phase == MissionPhase.ABORTED:
                return
            
            # PHASE IV: PERSIST (The Watch)
            await self._phase_persist(mission)
            
            mission.phase = MissionPhase.COMPLETED
            logger.info(f"[{mission_id}] Mission successfully archived into Deep Watch.")

        except Exception as e:
            logger.error(f"[{mission_id}] Mission FAILED: {e}")
            mission.phase = MissionPhase.FAILED
        finally:
            mission.updated_at = datetime.utcnow()
            # In Prod: Write final state to PostgreSQL database

    async def _phase_recon(self, mission: Mission):
        """Phase I: Consolidated passive and active discovery."""
        mission.phase = MissionPhase.RECON
        logger.info(f"[{mission.mission_id}] Executing Phase I: RECON (Global Radar, Archive of Secrets)")
        
        # 1. Base network probe
        base_recon = await unified_probe.unified_scan(
            target=mission.target_entity,
            tenant_id=mission.tenant_id
        )

        # 2. "World is Leaking" OSINT Integration
        osint_data = await unified_retriever.gather_all(target=mission.target_entity)
        
        # Merge OSINT into recon
        mission.recon_data = {
            "probe_baseline": base_recon,
            "osint_intel": osint_data
        }

    async def _phase_analyze(self, mission: Mission):
        """Phase II: AI Correlation, Enrichment, and Neural De-Masking."""
        mission.phase = MissionPhase.ANALYZE
        logger.info(f"[{mission.mission_id}] Executing Phase II: ANALYZE (Neural De-Masking)")

        # 1. Enrichment
        enrichment_data = await enrichment_engine.enrich_entity(mission.target_entity)
        
        # 2. Neural De-Masking: A custom AI fingerprinting module that links disparate aliases 
        #    (Telegram, Twitter, GitHub) into a single :ThreatActor node in Neo4j.
        demasker = NeuralDeMasking()
        if "@" in mission.target_entity:
            alias_type = "email"
        elif all(c in "0123456789." for c in mission.target_entity) and mission.target_entity.count('.') == 3:
            alias_type = "ip"
        else:
            alias_type = "username"
            
        # The demasker maps the disparate aliases found in OSINT to the Neo4j Graph
        # We pass the intercepted OSINT data to aid the AI de-masking
        intercept_data = mission.recon_data.get("osint_intel", {}).get("interceptor", {})
        fingerprint = await demasker.fingerprint_actor((alias_type, mission.target_entity))

        # 3. Linguistic Mesh Processing
        # If darkweb chatter found, process sentiment
        darkweb_sentiment = mission.recon_data.get("osint_intel", {}).get("secrets", {}).get("linguistic_mesh", {})

        # 4. Assemble the Dossier
        mission.analysis_findings = Dossier(
            enrichment=EnrichmentResult(**enrichment_data),
            demasking=DemaskingResult(
                fingerprint=fingerprint,
                status="Linked Telegram and GitHub aliases" if fingerprint else "No new links found"
            )
        )
        
        logger.info(f"[{mission.mission_id}] Analysis complete. ThreatActor fingerprint: {fingerprint}")

    async def _phase_execute(self, mission: Mission):
        """Phase III: Defensive Counter-Strike or Deception Launch."""
        mission.phase = MissionPhase.EXECUTE
        strategy = mission.analysis_findings.recommended_strategy or "SHADOW_SANDBOX" 
        # Default to Shadow Sandboxing for Sovereign Fortress logic
        logger.warning(f"[{mission.mission_id}] Executing Phase III: ACTION -> [{strategy}]")
        
        await asyncio.sleep(1.0)
        
        # Feature: Shadow Sandboxing & Adaptive Throttling
        if strategy == "SHADOW_SANDBOX":
            action_result = await sandbox_orchestrator.spawn_shadow_environment(
                target_ip=mission.target_entity,
                tenant_id=mission.tenant_id
            )
        elif strategy == "ADAPTIVE_THROTTLING":
            # Feature: Adaptive Throttling (Blackhole 1kbps without closing connection)
            logger.info("Engaging 'Blackhole' - slowing attacker packets to 1kbps.")
            action_result = {"status": "throttled", "rate": "1kbps"}
        else:
            # Send to Response orchestrator
            action_result = await response_orchestrator.evaluate_and_respond(
                tenant_id=mission.tenant_id,
                target_ip=mission.target_entity,
                reasoning=mission.analysis_findings.ai_narrative or "Automated Defense Strike"
            )
            
        # Global Inoculation
        # Push the attacker fingerprint to a global Redis channel to protect Firm B-Z
        self._global_inoculation(fingerprint=mission.analysis_findings.demasking.fingerprint)

        mission.execution_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": strategy,
            "status": "SUCCESS",
            "details": action_result
        })

    def _global_inoculation(self, fingerprint: str):
        """Pushes the blocked attacker fingerprint to the global Hive-Mind (Firm B through Z)."""
        if not fingerprint:
            return
        logger.info(f"[Global Inoculation] Distributing block rule for {fingerprint} to all connected sovereign nodes.")
        # In reality: await redis_client.publish('hive_mind_inoculation', fingerprint)

    async def _phase_persist(self, mission: Mission):
        """Phase IV: Establish Deep Watch on the asset."""
        mission.phase = MissionPhase.PERSIST
        logger.info(f"[{mission.mission_id}] Executing Phase IV: PERSIST / LOCKDOWN VERIFIED")
        
        await asyncio.sleep(0.5)
        # Setup continuous Redis polling flag or WAF rule verification here.

unified_cyber_pipeline = UnifiedIntelligenceChain()
