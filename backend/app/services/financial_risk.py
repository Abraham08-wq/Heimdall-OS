import logging
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ─── Financial Risk Models ───────────────────────────────────────────────────

class Asset(BaseModel):
    id: str = Field(..., description="Unique identifier for the asset (e.g., db-main, api-server, user-data)")
    name: str = Field(..., description="Human-readable name of the asset")
    criticality_value: float = Field(..., description="Monetary value of the asset or its revenue-generating capacity ($/hour)")
    description: Optional[str] = None

class RiskIncident(BaseModel):
    asset_id: str = Field(..., description="The ID of the targeted asset")
    threat_actor_id: Optional[str] = None
    kill_chain_phase: str = "INITIAL ACCESS"
    likelihood: float = Field(..., description="Probability of successful exploit (0.0 to 1.0)")
    severity: float = Field(..., description="Estimated impact percentage if exploited (0.0 to 1.0)")

class FinancialVaRResult(BaseModel):
    asset_id: str
    asset_name: str
    value_at_risk: float = Field(..., description="Calculated VaR in USD")
    saved_revenue: float = Field(0.0, description="Estimated revenue loss prevented by blocking this attack")
    description: str

# ─── Financial Risk Engine ───────────────────────────────────────────────────

class FinancialRiskEngine:
    """
    Financial Risk Projection Engine
    Calculates Financial Value at Risk (VaR).
    
    Formula: Risk = (Likelihood * Severity) * Asset_Criticality_Value
    """
    def __init__(self):
        # In-memory registry of critical enterprise assets
        # In a real system, this would be backed by PostgreSQL
        self.assets: Dict[str, Asset] = {
            "customer_db": Asset(
                id="customer_db",
                name="Primary Customer Database",
                criticality_value=5000000.0,  # $5M
                description="Contains PII and payment tokens for all active subscribers."
            ),
            "auth_gateway": Asset(
                id="auth_gateway",
                name="SSO Authentication Gateway",
                criticality_value=2000000.0,  # $2M
                description="Centralized login system. Downtime blocks all user access."
            ),
            "ceo_inbox": Asset(
                id="ceo_inbox",
                name="Executive Communications (CEO)",
                criticality_value=1000000.0,  # $1M
                description="Highly confidential corporate strategy and M&A data."
            )
        }

    def register_asset(self, asset: Asset):
        """Registers a new corporate asset for risk calculation."""
        self.assets[asset.id] = asset
        logger.info(f"Registered new digital asset for risk projection: {asset.name} (${asset.criticality_value:,.2f})")

    def project_risk(self, incident: RiskIncident, blocked: bool = False) -> FinancialVaRResult:
        """
        Projects the Financial Value at Risk (VaR) for a given security incident.
        If `blocked` is True, it calculates the 'Estimated Revenue Loss Prevented'.
        """
        asset = self.assets.get(incident.asset_id)
        if not asset:
            logger.warning(f"Asset '{incident.asset_id}' not found in registry. Using default generic asset.")
            asset = Asset(
                id="generic_asset",
                name="Unclassified Digital Asset",
                criticality_value=100000.0, # $100k baseline
            )

        # Enforce bounds [0.0, 1.0]
        likelihood = max(0.0, min(incident.likelihood, 1.0))
        severity = max(0.0, min(incident.severity, 1.0))

        # Core Formula: Risk = (Likelihood * Severity) * Asset_Criticality_Value
        # A late kill_chain_phase (e.g. EXFILTRATION) could implicitly mean high likelihood.
        value_at_risk = (likelihood * severity) * asset.criticality_value

        saved_revenue = value_at_risk if blocked else 0.0

        description = (
            f"Projected VaR of ${value_at_risk:,.2f} on '{asset.name}'. "
            f"(Likelihood: {likelihood:.0%}, Severity: {severity:.0%}, Base Value: ${asset.criticality_value:,.2f})"
        )
        if blocked:
            description += f" -> THREAT BLOCKED. Saved company ${saved_revenue:,.2f}."

        return FinancialVaRResult(
            asset_id=asset.id,
            asset_name=asset.name,
            value_at_risk=round(value_at_risk, 2),
            saved_revenue=round(saved_revenue, 2),
            description=description
        )

    def calculate_global_var(self, incidents: List[RiskIncident]) -> float:
        """Calculates total aggregated Value at Risk for the enterprise."""
        return sum(self.project_risk(inc, blocked=False).value_at_risk for inc in incidents)

    def calculate_total_savings(self, blocked_incidents: List[RiskIncident]) -> float:
        """Calculates total money saved via autonomous defense blocks."""
        return sum(self.project_risk(inc, blocked=True).saved_revenue for inc in blocked_incidents)

# Singleton instance
financial_risk_engine = FinancialRiskEngine()
