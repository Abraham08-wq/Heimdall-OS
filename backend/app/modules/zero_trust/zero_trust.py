import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ZeroTrustPolicyEngine:
    """
    Zero Trust Enforcement Engine (Phase 7)
    
    Evaluates contextual signals dynamically instead of relying purely on a valid JWT.
    Enforces continuous verification and device posture checking.
    """
    
    def evaluate_session_context(self, user_id: str, client_ip: str, device_fingerprint: str, expected_role: str) -> Dict[str, Any]:
        """
        [PHASE 8: ZERO TRUST POLICY ENGINE]
        Continuous Verification via Mathematical Trust Decay.
        Starting at T=100, we penalize for context deviations.
        """
        trust_score = 100.0
        reasons = []
        is_authorized = True
        
        known_valid_devices = {"fp_secure_m1_mac", "fp_soc_terminal_alpha"}
        high_risk_ips = {"198.51.100.4"} 
        
        # 1. Device Posture Decay
        if device_fingerprint and device_fingerprint not in known_valid_devices and device_fingerprint != "unknown":
            trust_score -= 40.0
            reasons.append(f"Device Not Trusted (-40). Given FP: {device_fingerprint}")
            
        # 2. Impossible Travel / IP Velocity Decay
        if client_ip in high_risk_ips:
            # Simulated: Real architecture would use Redis geo-distance over time Delta
            trust_score -= 80.0
            reasons.append(f"Impossible Geo-Velocity/High Risk IP (-80). IP: {client_ip}")

        # 3. Decision Boundary Evaluation
        action_required = "Proceed"
        
        if trust_score < 20.0:
            is_authorized = False
            action_required = "Reject (403)"
            logger.warning(f"ZERO TRUST FAILURE: {user_id} dropped below 20.0 trust.")
        elif trust_score < 50.0:
            action_required = "Enforce MFA Re-challenge"
            logger.info(f"ZERO TRUST CHALLENGE: {user_id} requires step-up auth (Score: {trust_score}).")
            
        # 4. Dynamic Least Privilege (Role Downgrades during anomalies)
        granted_role = expected_role
        
        # If trust is dubious, strip admin rights down to Read-Only
        if trust_score < 80.0 and expected_role == "admin":
            granted_role = "admin_readonly"
            reasons.append("Trust degraded below 80; enforcing Read-Only Sandbox.")
            
        return {
            "is_authorized": is_authorized, 
            "dynamic_role": granted_role,
            "session_trust_score": trust_score,
            "action_required": action_required,
            "reasons": reasons
        }

zero_trust_engine = ZeroTrustPolicyEngine()
