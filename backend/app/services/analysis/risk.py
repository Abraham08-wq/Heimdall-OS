from typing import List
from app.schemas.entity import Entity
from app.schemas.scoring import RiskAnalysisResult, RiskFactor, RiskLevel
from app.schemas.relationships import Relationship

class RiskEngine:
    """
    Calculates a 0-100 Risk Score based on weighted factors.
    Design Philosophy: Score must be explainable.
    """
    
    def __init__(self):
        self.weights = {
            "breach_exposure": 0.4,
            "footprint_volume": 0.3,
            "link_density": 0.2,
            "past_flags": 0.1
        }

    def analyze(self, entity: Entity, relationships: List[Relationship]) -> RiskAnalysisResult:
        factors = []
        score = 0
        
        # 1. Breach Exposure Analysis (Simulated Logic)
        # In prod, this would check attributes against a 'Breach' database
        breach_count = sum(1 for a in entity.attributes if "password" in a.value.lower() or "db_leak" in a.evidence_refs)
        if breach_count > 0:
            impact = min(breach_count * 15, 40) # 15 points per breach, max 40
            score += impact
            factors.append(RiskFactor(
                name="Breach Exposure",
                score_impact=impact,
                description=f"Entity features in {breach_count} known data breaches."
            ))
            
        # 2. Link Density (Centrality)
        # High connectivity in a criminal graph = High Risk
        conn_count = len(relationships)
        if conn_count > 10:
            impact = 20
            score += impact
            factors.append(RiskFactor(
                name="High Connectivity",
                score_impact=impact,
                description=f"Entity is a hub with {conn_count}+ direct connections."
            ))
            
        # 3. Attribute/Footprint Volume
        # No footprint = Suspicious (Ghost?); Extensive footprint = Higher attack surface
        attr_count = len(entity.attributes)
        if attr_count < 2:
            impact = 10
            score += impact
            factors.append(RiskFactor(
                name="Low Visibility (Ghost)",
                score_impact=impact,
                description="Entity has remarkably little public footprint, suggesting operational security."
            ))
            
        # 4. Behavioral Heuristics (AI Analyst Input)
        # Mock logic: check for 'suspicious' patterns in attributes/relationships
        is_evasive = any("proxy" in str(a.value).lower() for a in entity.attributes)
        if is_evasive:
            impact = 25
            score += impact
            factors.append(RiskFactor(
                name="Evasive Behavior",
                score_impact=impact,
                description="Use of proxy/anonymization services detected."
            ))

        # Final Score Cap
        total_score = min(score, 100)
        
        # Determine Level
        if total_score < 20: level = RiskLevel.LOW
        elif total_score < 60: level = RiskLevel.MEDIUM
        elif total_score < 90: level = RiskLevel.HIGH
        else: level = RiskLevel.CRITICAL
        
        # Auto-Narrative
        narrative = f"Entity assesses as {level.value} Risk ({total_score}/100). "
        narrative += f"Primary driver is {factors[0].name}." if factors else "No significant risk factors detected."

        return RiskAnalysisResult(
            target_id=str(entity.id),
            total_score=total_score,
            level=level,
            factors=factors,
            narrative=narrative
        )
