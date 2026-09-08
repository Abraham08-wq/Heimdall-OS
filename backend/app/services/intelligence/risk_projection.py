"""
FINANCIAL & GEOPOLITICAL RISK PROJECTION
==========================================
Strategic impact intelligence and risk modeling

Uses FAIR framework (Factor Analysis of Information Risk) to calculate:
- Dollar Value at Risk (VaR)
- Business impact projections
- Geopolitical signal analysis
- Attack likelihood and impact assessments
- Risk quantification for C-suite decisions
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import json
import math


class RiskCategory(Enum):
    """Risk categories for FAIR framework"""
    DATA_BREACH = "data_breach"
    RANSOMWARE = "ransomware"
    APT_INFILTRATION = "apt_infiltration"
    DDOS = "ddos"
    INSIDER_THREAT = "insider_threat"
    SUPPLY_CHAIN = "supply_chain"
    INFRASTRUCTURE = "infrastructure"
    IP_THEFT = "ip_theft"


class GeopoliticalSignal(Enum):
    """Geopolitical indicators"""
    PRE_CONFLICT = "pre_conflict"
    ESPIONAGE = "espionage"
    INFLUENCE_OPERATION = "influence_operation"
    SANCTIONS_EVASION = "sanctions_evasion"
    ECONOMIC_WARFARE = "economic_warfare"
    TERRITORIAL_CLAIM = "territorial_claim"
    RESOURCE_COMPETITION = "resource_competition"


class BusinessImpactType(Enum):
    """Types of business impacts"""
    REVENUE_LOSS = "revenue_loss"
    OPERATIONAL_DOWNTIME = "operational_downtime"
    CUSTOMER_CHURN = "customer_churn"
    REGULATORY_FINES = "regulatory_fines"
    REPUTATIONAL_DAMAGE = "reputational_damage"
    LITIGATION = "litigation"
    MARKET_CAP_LOSS = "market_cap_loss"
    INCIDENT_RESPONSE_COSTS = "incident_response_costs"


@dataclass
class LossEvent:
    """A single loss event in the FAIR model"""
    event_type: RiskCategory
    frequency: float  # Events per year
    magnitude_min: float  # USD
    magnitude_max: float  # USD
    probability: float  # 0-1
    confidence: float  # 0-1


@dataclass
class FAIRModel:
    """FAIR framework risk calculation model"""
    risk_category: RiskCategory
    
    # Threat
    threat_agent_capability: float  # 0-100
    threat_agent_intent: float  # 0-1
    threat_frequency: float  # Events per year
    
    # Vulnerability
    vulnerability_severity: float  # 0-100
    vulnerability_count: int
    controls_effectiveness: float  # 0-1
    
    # Asset Value
    asset_value: float  # USD
    business_criticality: float  # 0-1
    recovery_cost: float  # USD
    
    # Loss estimation
    primary_loss_min: float  # USD
    primary_loss_max: float  # USD
    secondary_loss_min: float  # USD
    secondary_loss_max: float  # USD
    
    # Temporal
    model_date: datetime
    time_horizon: int  # Years


@dataclass
class RiskMetrics:
    """Calculated risk metrics"""
    var_95: float  # Value at Risk at 95% confidence (USD)
    var_99: float  # Value at Risk at 99% confidence (USD)
    expected_loss: float  # Annual expected loss (USD)
    maximum_probable_loss: float  # USD
    risk_score: float  # 0-100
    threat_level: str  # critical, high, medium, low
    probability: float  # Probability of loss event
    impact_if_exploited: float  # USD


@dataclass
class GeopoliticalAnalysis:
    """Geopolitical risk assessment"""
    country: str
    signal_type: GeopoliticalSignal
    confidence: float  # 0-1
    precursor_indicators: List[str]
    timeline_estimate: str  # e.g., "weeks", "months"
    affected_assets: List[str]
    recommended_actions: List[str]
    impact_if_realized: Dict[str, float]  # By impact type


@dataclass
class BusinessImpactProjection:
    """Projected business impact of security incident"""
    scenario: str
    probability: float
    
    # Financial impacts
    revenue_loss_year_1: float  # USD
    market_cap_loss: float  # USD
    customer_churn_rate: float  # % of customers
    regulatory_fines: float  # USD
    litigation_costs: float  # USD
    incident_response_costs: float  # USD
    
    # Operational impacts
    downtime_hours: int
    affected_systems: List[str]
    recovery_time: int  # hours
    
    # Strategic impacts
    market_share_loss: float  # %
    brand_damage_score: float  # 0-100
    employee_turnover_increase: float  # %
    stock_price_impact: float  # %
    
    # Total impact
    total_financial_impact: float  # USD
    confidence: float


class FAIRCalculator:
    """FAIR framework risk calculator"""
    
    @staticmethod
    def calculate_frequency(threat_capability: float, threat_intent: float, 
                          vulnerability_severity: float, 
                          controls_effectiveness: float) -> float:
        """
        Calculate loss event frequency
        
        Frequency = Threat Frequency * Vulnerability Score
        """
        threat_score = threat_capability * threat_intent
        vulnerability_score = vulnerability_severity * (1 - controls_effectiveness)
        frequency = threat_score * vulnerability_score / 10000  # Normalize
        
        return frequency
    
    @staticmethod
    def calculate_magnitude(asset_value: float, 
                          business_criticality: float,
                          recovery_cost: float) -> Tuple[float, float]:
        """
        Calculate loss magnitude range
        
        Min: Direct loss (data breach, downtime)
        Max: Direct + Secondary losses (fines, litigation, churn)
        """
        direct_loss_min = asset_value * 0.3  # Assume 30% direct loss
        direct_loss_max = asset_value * 0.8  # Assume 80% direct loss
        
        secondary_loss = asset_value * business_criticality * recovery_cost
        
        magnitude_min = direct_loss_min
        magnitude_max = direct_loss_max + secondary_loss
        
        return magnitude_min, magnitude_max
    
    @staticmethod
    def calculate_ale(frequency: float, magnitude_min: float, 
                     magnitude_max: float) -> float:
        """
        Calculate Annual Loss Expectancy
        
        ALE = Frequency * Average Magnitude
        """
        avg_magnitude = (magnitude_min + magnitude_max) / 2
        ale = frequency * avg_magnitude
        
        return ale
    
    @staticmethod
    def calculate_var(ale: float, std_deviation: float, 
                     confidence_level: float = 0.95) -> float:
        """
        Calculate Value at Risk
        
        VaR approximates loss at given confidence level
        """
        # Using normal distribution approximation
        z_score = {0.90: 1.28, 0.95: 1.645, 0.99: 2.33}
        z = z_score.get(confidence_level, 1.645)
        
        var = ale + (z * std_deviation)
        return max(0, var)  # Cannot be negative


class FAIRModel:
    """Complete FAIR framework implementation"""
    
    def __init__(self):
        self.calculator = FAIRCalculator()
    
    def assess_risk(self, model_params: Dict) -> RiskMetrics:
        """
        Comprehensive risk assessment using FAIR framework
        
        Args:
            model_params: Dict containing all risk parameters
        
        Returns:
            RiskMetrics with calculated values
        """
        
        # Extract parameters
        threat_capability = model_params.get('threat_capability', 50)
        threat_intent = model_params.get('threat_intent', 0.7)
        threat_frequency = model_params.get('threat_frequency', 0.5)  # Times per year
        
        vulnerability_severity = model_params.get('vulnerability_severity', 70)
        controls_effectiveness = model_params.get('controls_effectiveness', 0.6)
        
        asset_value = model_params.get('asset_value', 1000000)  # USD
        business_criticality = model_params.get('business_criticality', 0.8)
        recovery_cost = model_params.get('recovery_cost', 0.5)
        
        # Calculate frequency
        frequency = self.calculator.calculate_frequency(
            threat_capability, threat_intent,
            vulnerability_severity, controls_effectiveness
        )
        
        # Calculate magnitude
        magnitude_min, magnitude_max = self.calculator.calculate_magnitude(
            asset_value, business_criticality, recovery_cost
        )
        
        # Calculate ALE
        ale = self.calculator.calculate_ale(frequency, magnitude_min, magnitude_max)
        
        # Calculate VAR
        std_deviation = (magnitude_max - magnitude_min) / 4  # Rough estimate
        var_95 = self.calculator.calculate_var(ale, std_deviation, 0.95)
        var_99 = self.calculator.calculate_var(ale, std_deviation, 0.99)
        
        # Calculate probability
        probability = min(1.0, frequency)
        
        # Assess threat level
        if var_99 > asset_value:
            threat_level = "critical"
        elif var_99 > asset_value * 0.5:
            threat_level = "high"
        elif var_99 > asset_value * 0.1:
            threat_level = "medium"
        else:
            threat_level = "low"
        
        # Risk score (0-100)
        risk_score = min(100, (var_99 / asset_value) * 100)
        
        return RiskMetrics(
            var_95=var_95,
            var_99=var_99,
            expected_loss=ale,
            maximum_probable_loss=magnitude_max,
            risk_score=risk_score,
            threat_level=threat_level,
            probability=probability,
            impact_if_exploited=magnitude_max,
        )


class GeopoliticalAnalyzer:
    """Analyzes geopolitical signals and strategic implications"""
    
    def __init__(self, intelligence_feeds=None):
        self.feeds = intelligence_feeds or {}
    
    async def analyze_signal(self, country: str, signal_type: GeopoliticalSignal,
                           confidence: float) -> GeopoliticalAnalysis:
        """
        Analyze geopolitical signal
        
        Maps cyber activity to strategic objectives
        """
        
        precursor_indicators = self._get_precursors(signal_type)
        timeline = self._estimate_timeline(signal_type)
        affected_assets = await self._identify_affected_assets(country, signal_type)
        
        analysis = GeopoliticalAnalysis(
            country=country,
            signal_type=signal_type,
            confidence=confidence,
            precursor_indicators=precursor_indicators,
            timeline_estimate=timeline,
            affected_assets=affected_assets,
            recommended_actions=self._recommend_actions(signal_type),
            impact_if_realized=self._project_impact(signal_type, country),
        )
        
        return analysis
    
    @staticmethod
    def _get_precursors(signal: GeopoliticalSignal) -> List[str]:
        """Get precursor indicators for geopolitical signal"""
        
        precursors = {
            GeopoliticalSignal.PRE_CONFLICT: [
                "Increased dark web chatter about target country",
                "Reconnaissance of critical infrastructure",
                "Recruitment of local threat actors",
                "Preparation of malware variants",
                "Testing of command & control infrastructure",
            ],
            GeopoliticalSignal.ESPIONAGE: [
                "Targeted phishing of government officials",
                "Advanced persistence in networks",
                "Data exfiltration of strategic documents",
                "Social engineering of key personnel",
                "Long-dwell reconnaissance activity",
            ],
            GeopoliticalSignal.ECONOMIC_WARFARE: [
                "Targeting of financial institutions",
                "Attacks on supply chain infrastructure",
                "Currency market manipulation signals",
                "Critical resource facility probing",
                "Coordinated multi-vector attacks",
            ],
        }
        
        return precursors.get(signal, [])
    
    @staticmethod
    def _estimate_timeline(signal: GeopoliticalSignal) -> str:
        """Estimate timeline for geopolitical event"""
        
        timelines = {
            GeopoliticalSignal.PRE_CONFLICT: "weeks to months",
            GeopoliticalSignal.ESPIONAGE: "ongoing",
            GeopoliticalSignal.INFLUENCE_OPERATION: "months",
            GeopoliticalSignal.ECONOMIC_WARFARE: "immediate to weeks",
        }
        
        return timelines.get(signal, "unknown")
    
    async def _identify_affected_assets(self, country: str, 
                                       signal: GeopoliticalSignal) -> List[str]:
        """Identify which critical infrastructure would be affected"""
        
        if signal == GeopoliticalSignal.PRE_CONFLICT:
            return [
                "Electric grid",
                "Water treatment",
                "Transportation systems",
                "Military networks",
                "Government communications",
            ]
        elif signal == GeopoliticalSignal.ECONOMIC_WARFARE:
            return [
                "Financial markets",
                "Banking infrastructure",
                "Supply chains",
                "Energy sector",
                "Agricultural systems",
            ]
        
        return []
    
    @staticmethod
    def _recommend_actions(signal: GeopoliticalSignal) -> List[str]:
        """Recommend actions based on geopolitical signal"""
        
        return [
            "Increase monitoring of critical infrastructure",
            "Coordinate with government agencies",
            "Brief executive leadership",
            "Activate incident response teams",
            "Increase network isolation protocols",
            "Deploy additional threat hunting resources",
            "Share intelligence with sector peers",
        ]
    
    @staticmethod
    def _project_impact(signal: GeopoliticalSignal, country: str) -> Dict[str, float]:
        """Project financial impact by type"""
        
        base_impact = {
            "infrastructure_damage": 500000000,
            "business_interruption": 1000000000,
            "recovery_costs": 200000000,
            "lost_productivity": 300000000,
        }
        
        multipliers = {
            GeopoliticalSignal.PRE_CONFLICT: 10.0,
            GeopoliticalSignal.ECONOMIC_WARFARE: 5.0,
            GeopoliticalSignal.ESPIONAGE: 0.5,
        }
        
        multiplier = multipliers.get(signal, 1.0)
        
        return {
            k: v * multiplier for k, v in base_impact.items()
        }


class BusinessImpactProjector:
    """Projects business impact of security incidents"""
    
    @staticmethod
    def project_incident_impact(incident_type: str, 
                               company_revenue: float,
                               company_market_cap: float,
                               customers: int) -> BusinessImpactProjection:
        """
        Project business impact of security incident
        
        Args:
            incident_type: Type of incident (breach, ransomware, etc.)
            company_revenue: Annual revenue (USD)
            company_market_cap: Market capitalization (USD)
            customers: Number of customers
        """
        
        if incident_type == "data_breach":
            revenue_loss = company_revenue * 0.08  # 8% revenue impact
            market_cap_loss = company_market_cap * 0.12  # 12% market cap
            customer_churn = 0.15  # 15% churn
            fines = customers * 5000  # $5k per customer (GDPR-level)
            downtime = 4  # hours
            
        elif incident_type == "ransomware":
            revenue_loss = company_revenue * 0.20  # 20% revenue impact
            market_cap_loss = company_market_cap * 0.25
            customer_churn = 0.25
            fines = customers * 2000
            downtime = 72  # hours
            
        elif incident_type == "apt_breach":
            revenue_loss = company_revenue * 0.15
            market_cap_loss = company_market_cap * 0.20
            customer_churn = 0.20
            fines = customers * 3000
            downtime = 24
            
        else:
            revenue_loss = company_revenue * 0.05
            market_cap_loss = company_market_cap * 0.08
            customer_churn = 0.10
            fines = customers * 1000
            downtime = 8
        
        litigation_costs = revenue_loss * 0.3
        response_costs = revenue_loss * 0.15
        churn_revenue_loss = company_revenue * customer_churn * 0.1  # Annual impact
        
        total_impact = (
            revenue_loss + churn_revenue_loss + fines + litigation_costs + response_costs
        )
        
        return BusinessImpactProjection(
            scenario=f"{incident_type}_impact",
            probability=0.85,
            revenue_loss_year_1=revenue_loss,
            market_cap_loss=market_cap_loss,
            customer_churn_rate=customer_churn,
            regulatory_fines=fines,
            litigation_costs=litigation_costs,
            incident_response_costs=response_costs,
            downtime_hours=downtime,
            affected_systems=["Web servers", "Database", "Email", "File storage"],
            recovery_time=downtime,
            market_share_loss=customer_churn * 100,
            brand_damage_score=customer_churn * 100,
            employee_turnover_increase=customer_churn * 10,
            stock_price_impact=-(market_cap_loss / company_market_cap),
            total_financial_impact=total_impact,
            confidence=0.85,
        )


# Async endpoint helpers
async def assess_risk_endpoint(risk_model: Dict) -> Dict:
    """FastAPI endpoint for FAIR risk assessment"""
    try:
        fair = FAIRModel()
        metrics = fair.assess_risk(risk_model)
        return asdict(metrics)
    except Exception as e:
        return {"error": str(e), "status": "failed"}


async def analyze_geopolitical_endpoint(country: str, signal_type: str) -> Dict:
    """FastAPI endpoint for geopolitical analysis"""
    try:
        analyzer = GeopoliticalAnalyzer()
        analysis = await analyzer.analyze_signal(
            country=country,
            signal_type=GeopoliticalSignal(signal_type),
            confidence=0.85
        )
        return asdict(analysis)
    except Exception as e:
        return {"error": str(e), "status": "failed"}


async def project_business_impact_endpoint(incident_type: str, 
                                          company_revenue: float,
                                          company_market_cap: float,
                                          customers: int) -> Dict:
    """FastAPI endpoint for business impact projection"""
    try:
        impact = BusinessImpactProjector.project_incident_impact(
            incident_type=incident_type,
            company_revenue=company_revenue,
            company_market_cap=company_market_cap,
            customers=customers,
        )
        return asdict(impact)
    except Exception as e:
        return {"error": str(e), "status": "failed"}
