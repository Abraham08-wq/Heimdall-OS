import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class ExfiltrationImpactSimulator:
    """
    Data Exfiltration & Business Continuity Impact Modeling (Phase 6)
    
    Classifies entity sensitivity and simulates dollar-value loss and downtime
    if a specific subnet or database layer is breached.
    """
    
    def __init__(self):
        # Master classification matrix mapping asset types to base costs
        self.sensitivity_classes = {
            "PII": {"cost_per_record": 250, "reputation_dmg": "SEVERE", "regulatory_fine_prob": 0.9},
            "FINANCIAL": {"cost_per_record": 400, "reputation_dmg": "CRITICAL", "regulatory_fine_prob": 0.99},
            "STRATEGIC_IP": {"cost_per_record": 1500, "reputation_dmg": "MODERATE", "regulatory_fine_prob": 0.2},
            "INTERNAL_OPS": {"cost_per_record": 50, "reputation_dmg": "LOW", "regulatory_fine_prob": 0.05}
        }
        
    def classify_asset_zone(self, node_name: str) -> str:
        """Determines the primary sensitivity classification of a network zone."""
        name_lower = node_name.lower()
        if "db" in name_lower or "database" in name_lower or "sql" in name_lower:
            return "PII"
        if "billing" in name_lower or "payment" in name_lower or "financial" in name_lower:
            return "FINANCIAL"
        if "repo" in name_lower or "code" in name_lower or "ip" in name_lower:
            return "STRATEGIC_IP"
        return "INTERNAL_OPS"

    def simulate_impact(self, node_name: str, assets_at_risk: int, threat_severity: str) -> Dict[str, Any]:
        """
        [PHASE 9: BUSINESS IMPACT AI]
        Calculates Exfiltration Loss and Downtime metrics using formal damage equations.
        F_loss = N_records * (C_base * R_multiplier)
        """
        classification = self.classify_asset_zone(node_name)
        params = self.sensitivity_classes.get(classification, self.sensitivity_classes["INTERNAL_OPS"])
        
        # 1. Base Regulatory Cost (C_base)
        c_base = params["cost_per_record"]
        
        # 2. Regulatory Exposure Multiplier (R_multiplier)
        # Emulating a framework where PII/Financial incurs heavy GDPR/HIPAA multipliers
        regulatory_multiplier = 3.0 if classification in ["PII", "FINANCIAL"] else 1.0
        
        # 3. Threat Severity Escalation
        threat_multiplier = {"LOW": 1.0, "MEDIUM": 2.5, "HIGH": 5.0, "CRITICAL": 10.0}.get(threat_severity.upper(), 1.0)
        
        # 4. Financial Breach Cost (F_loss)
        f_loss = assets_at_risk * (c_base * regulatory_multiplier) * threat_multiplier
        
        # 5. Business Continuity / SLA Violation Modeling
        # Downtime follows an exponential recovery curve based on severity magnitude
        downtime_hours = (assets_at_risk * 0.01) * (threat_multiplier ** 1.8)
        
        # Calculate SLA Violation fines ($1000 per hour over 4 hours downtime)
        sla_violation_cost = max(0, (downtime_hours - 4.0) * 1000)
        
        total_enterprise_damage = f_loss + sla_violation_cost
        
        return {
            "node_analyzed": node_name,
            "sensitivity_classification": classification,
            "assets_at_risk": assets_at_risk,
            "threat_severity": threat_severity,
            "metrics": {
                "base_cost_per_record": c_base,
                "regulatory_multiplier": regulatory_multiplier
            },
            "projections": {
                "estimated_data_breach_cost_usd": int(f_loss),
                "estimated_sla_violation_cost": int(sla_violation_cost),
                "total_enterprise_damage_usd": int(total_enterprise_damage),
                "estimated_downtime_hours": round(downtime_hours, 1),
                "reputation_impact": params["reputation_dmg"],
                "regulatory_exposure_probability": params["regulatory_fine_prob"]
            },
            "recovery_recommendation": f"Enact Tier {classification} isolation protocols and notify Legal."
        }

exfiltration_engine = ExfiltrationImpactSimulator()
