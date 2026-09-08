import logging
from typing import Dict, Any, List
from app.modules.defensive.services.containment import containment_engine
from app.modules.defensive.services.intelligence import soc_engine

logger = logging.getLogger(__name__)

class RealtimeThreatScorer:
    """
    Real-Time Threat Scoring Engine (Phase 3)
    
    Fuses multiple signals (UEBA, Graph, TI) into a single risk score.
    Automatically triggers containment if thresholds are breached, and generates an explainable decision tree.
    """
    
    def evaluate_signals(self, entity_id: str, ueba_score: float, graph_is_anomalous: bool, api_abuse_detected: bool, prompt_injection_flag: bool = False) -> Dict[str, Any]:
        """
        [PHASE 6: AUTONOMOUS DEFENSIVE AI]
        Fuses signals to generate a global risk score G_T.
        G_T = (W_ueba * S_ueba) + (W_graph * S_graph) + (W_api * S_api)
        """
        total_risk = 0.0
        reasoning = []
        
        # Pull down MITRE Capability Mapping (Phase 3)
        from app.modules.offensive.ai_models import ai_threat_model
        
        # Signal weighting and contribution calculation
        # Signal 1: Behavioral Deviation
        if ueba_score > 0:
            weight = 0.5
            contribution = ueba_score * weight
            total_risk += contribution
            reasoning.append(f"UEBA Anomaly ({contribution:.1f} pts): Behavioral deviation detected.")
            
        # Signal 2: Lateral Movement (Graph)
        if graph_is_anomalous:
            contribution = 40.0
            total_risk += contribution
            reasoning.append(f"Graph Anomaly ({contribution:.1f} pts): Unusual lateral movement/burst access.")
            
        # Signal 3: API Fuzzing/Abuse
        if api_abuse_detected:
            contribution = 35.0
            total_risk += contribution
            mitre_map = ai_threat_model.map_signal_to_tactic("ueba.api_error_ratio")
            tactic = mitre_map["tactic"] if mitre_map else "UNKNOWN"
            reasoning.append(f"API Entropy ({contribution:.1f} pts): High error-to-success ratio (Fuzzing). MITRE: {tactic}")
            
        # Signal 4: Adversarial AI (Prompt Injection)
        if prompt_injection_flag:
            contribution = 80.0 # Critical weight for adversarial AI bypass attempt
            total_risk += contribution
            mitre_map = ai_threat_model.map_signal_to_tactic("ai_defense.entropy_flags")
            tactic = mitre_map["tactic"] if mitre_map else "UNKNOWN"
            reasoning.append(f"Adversarial AI ({contribution:.1f} pts): Prompt Injection Bypass attempt. MITRE: {tactic}")
            
        # Decision Explainability Layer
        confidence_metric = min(100.0, total_risk)
        
        decision_tree = {
            "entity_id": entity_id,
            "calculated_risk_score": round(confidence_metric, 2),
            "evidence_linked_attribution": reasoning,
            "confidence_metric": "HIGH" if confidence_metric > 75 else "MEDIUM" if confidence_metric > 40 else "LOW"
        }
        
        # Autonomous Action Trigger
        action_taken = "Monitoring"
        
        # [PHASE 6] Context-Aware Containment Policies
        if confidence_metric >= 80.0:
            if prompt_injection_flag:
                # Adversarial AI attempt -> Immediate Sandbox + Token Invalidation
                containment_engine.invalidate_token(entity_id)
                action_taken = "TOKEN_INVALIDATED_AND_SANDBOXED"
                soc_engine.trigger_alert("CRITICAL", "AI_SCORER", f"Token Invalidated for {entity_id}. Risk: {confidence_metric}")
            else:
                # General high risk -> Isolate Session and Sandbox
                containment_engine.quarantine_session(entity_id)
                action_taken = "SESSION_QUARANTINED"
                soc_engine.trigger_alert("CRITICAL", "AI_SCORER", f"Auto-contained {entity_id}. Risk: {confidence_metric}")
                
            containment_engine.isolate_entity(
                entity_id, 
                reason="Cumulative risk threshold surpassed (Autonomous Defense)."
            )
        elif confidence_metric >= 60.0:
            if api_abuse_detected:
                # Fuzzing -> Throttle API explicitly
                containment_engine.throttle_api(entity_id, limit_per_minute=2)
                action_taken = "API_THROTTLED"
                soc_engine.trigger_alert("HIGH", "AI_SCORER", f"API Throttled for {entity_id}. Risk: {confidence_metric}")
            else:
                # General anomalous behavior -> Downgrade Privilege
                containment_engine.downgrade_privilege(entity_id)
                action_taken = "PRIVILEGE_DOWNGRADED"
                soc_engine.trigger_alert("HIGH", "AI_SCORER", f"Privilege downgraded for {entity_id}. Risk: {confidence_metric}")
        elif confidence_metric >= 40.0:
            action_taken = "ELEVATED_OBSERVATION"
        
        decision_tree["autonomous_action"] = action_taken
        
        return decision_tree

threat_scorer = RealtimeThreatScorer()
