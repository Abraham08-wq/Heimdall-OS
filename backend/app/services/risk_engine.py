"""
Risk Engine — v2 (Power Upgrade)
─────────────────────────────────
Upgrades:
  • Velocity risk factor: rising score trend amplifies risk
  • Tactical stage multiplier: late kill-chain phase = exponential penalty
  • Full SIEM narrative generator (markdown-ready text report)
  • IOC density factor: number of linked known-bad indicators
  • Confidence-weighted composite score
"""
import logging
from typing import List, Dict, Any
from datetime import datetime
from app.schemas.entity import Entity
from app.schemas.scoring import RiskAnalysisResult, RiskFactor, RiskLevel
from app.services.correlation_engine import correlation_engine

logger = logging.getLogger(__name__)

# ─── Kill-chain stage multipliers ────────────────────────────────────────────

STAGE_MULTIPLIER: Dict[str, float] = {
    "INITIAL ACCESS":       1.0,
    "EXECUTION":            1.15,
    "PERSISTENCE":          1.20,
    "PRIVILEGE ESCALATION": 1.30,
    "DEFENSE EVASION":      1.25,
    "CREDENTIAL ACCESS":    1.35,
    "DISCOVERY":            1.10,
    "LATERAL MOVEMENT":     1.40,
    "COLLECTION":           1.45,
    "EXFILTRATION":         1.60,
    "IMPACT":               1.80,   # Ransomware / destructive — max amplification
}

RISK_LEVELS = [
    (90, RiskLevel.CRITICAL),
    (60, RiskLevel.HIGH),
    (20, RiskLevel.MEDIUM),
    (0,  RiskLevel.LOW),
]


class RiskEngine:
    """
    Composite Risk Score Engine v2.

    Formula:
      score = (base_reputation
             + anomaly_score × 1.5
             + graph_proximity × 2.0
             + velocity_delta × 1.2
             + ioc_density × 0.8)
             × stage_multiplier
             × confidence_weight
      capped at 100.
    """

    async def analyze_entity(
        self,
        entity: Entity,
        base_reputation: float,
        recent_anomaly_score: float,
        velocity_delta: float = 0.0,
        ioc_count: int = 0,
        kill_chain_phase: str = "INITIAL ACCESS",
        confidence_weight: float = 1.0,
    ) -> RiskAnalysisResult:

        factors: List[RiskFactor] = []
        score = 0.0

        # 1. Base reputation (threat feed score)
        if base_reputation > 0:
            score += base_reputation
            factors.append(RiskFactor(
                name="Threat Intelligence Reputation",
                score_impact=base_reputation,
                description=f"Entity carries a historical risk baseline of {base_reputation:.1f}/100 from licensed threat feeds."
            ))

        # 2. Behavioral anomaly (UEBA)
        if recent_anomaly_score > 0:
            impact = recent_anomaly_score * 1.5
            score += impact
            factors.append(RiskFactor(
                name="UEBA Behavioral Anomaly",
                score_impact=round(impact, 1),
                description=f"Entity deviated significantly from its behavioral baseline. Anomaly score: {recent_anomaly_score:.2f}."
            ))

        # 3. Graph proximity to known threats
        try:
            graph_data = await correlation_engine.get_graph_proximity_to_threats(
                target_ip=str(entity.canonical_name)
            )
            proximity = float(graph_data.get("score", 0.0))
        except Exception as e:
            logger.warning(f"Graph proximity unavailable for {entity.canonical_name}: {e}")
            proximity = 0.0

        if proximity > 0:
            impact = proximity * 2.0
            score += impact
            closest = graph_data.get("closest_threats", [])
            threat_str = ", ".join(f"{t['threat']} (dist:{t['distance']})" for t in closest)
            factors.append(RiskFactor(
                name="Graph Proximity to Confirmed Threats",
                score_impact=round(impact, 1),
                description=f"Entity is graph-adjacent to: {threat_str}."
            ))

        # 4. Velocity risk (rising score trend)
        if velocity_delta > 5:
            impact = min(velocity_delta * 1.2, 20.0)
            score += impact
            factors.append(RiskFactor(
                name="Rising Threat Velocity",
                score_impact=round(impact, 1),
                description=f"Risk score escalating at +{velocity_delta:.1f} pts/hr. Acceleration is itself a danger signal."
            ))

        # 5. IOC density
        if ioc_count > 0:
            impact = min(ioc_count * 0.8, 15.0)
            score += impact
            factors.append(RiskFactor(
                name="IOC Density",
                score_impact=round(impact, 1),
                description=f"Entity linked to {ioc_count} known bad indicators in the intelligence graph."
            ))

        # 6. Ghost footprint (high suspicion, low visibility)
        if len(entity.attributes) < 2 and score > 20:
            score += 15.0
            factors.append(RiskFactor(
                name="Evasive OpSec Footprint",
                score_impact=15.0,
                description="Entity is technically suspicious yet leaves almost zero observable footprint — high counter-intelligence OpSec."
            ))

        # 7. Kill-chain stage multiplier
        multiplier = STAGE_MULTIPLIER.get(kill_chain_phase.upper(), 1.0)
        if multiplier > 1.0:
            score *= multiplier
            factors.append(RiskFactor(
                name=f"Kill-Chain Stage Escalation: {kill_chain_phase}",
                score_impact=round(score * (multiplier - 1), 1),
                description=f"Entity is operating at [{kill_chain_phase}] stage. Late-stage activity amplified ×{multiplier}."
            ))

        # 8. Confidence weight (from evidence reliability)
        score *= max(confidence_weight, 0.5)

        total = round(min(score, 100.0), 1)

        # Level
        level = next(
            (lvl for threshold, lvl in RISK_LEVELS if total >= threshold),
            RiskLevel.LOW
        )

        primary_driver = max(factors, key=lambda f: f.score_impact).name if factors else "None"
        narrative = self._generate_siem_narrative(entity, total, level, factors, kill_chain_phase, primary_driver)

        return RiskAnalysisResult(
            target_id=str(entity.id),
            total_score=total,
            level=level,
            factors=factors,
            base_reputation=round(base_reputation, 1),
            anomaly_score=round(recent_anomaly_score, 1),
            graph_proximity_score=round(proximity, 1),
            narrative=narrative,
        )

    def _generate_siem_narrative(
        self,
        entity: Entity,
        score: float,
        level: RiskLevel,
        factors: List[RiskFactor],
        phase: str,
        driver: str,
    ) -> str:
        now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        lines = [
            f"## SIEM Risk Assessment — {entity.canonical_name}",
            f"**Generated:** {now}  |  **Risk Level:** {level.value}  |  **Score:** {score}/100",
            "",
            f"### Kill-Chain Phase: {phase}",
            f"Primary risk driver: **{driver}**",
            "",
            "### Risk Factor Breakdown",
        ]
        for f in sorted(factors, key=lambda x: x.score_impact, reverse=True):
            lines.append(f"- **{f.name}** (+{f.score_impact:.1f}): {f.description}")
        lines += [
            "",
            "### Recommended Actions",
            "1. Verify entity against threat intelligence feeds immediately."
            if score > 80 else
            "1. Monitor entity for continued activity escalation.",
            "2. Cross-reference against MITRE ATT&CK framework for TTP alignment.",
            "3. Log all interactions with this entity to the immutable audit ledger.",
        ]
        return "\n".join(lines)


risk_engine = RiskEngine()
