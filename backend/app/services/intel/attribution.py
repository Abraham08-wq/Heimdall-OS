"""
Attribution Engine - Correlate threat indicators and create threat actor dossiers.

This module correlates disparate threat indicators (IPs, emails, social metadata) from
authorized OSINT APIs (Shodan, Censys, Intel X) and creates a "Threat Actor Dossier" 
in Neo4j to assist in the legal attribution of state-sponsored or criminal cyber activity.

Features:
- Parallel OSINT gathering for multiple indicators
- Enrichment with threat intelligence feeds
- Neo4j threat actor graph persistence
- Confidence scoring for attribution signals
"""

from typing import List, Dict, Any, Optional
import logging
import asyncio

from app.core.config import settings
from app.infrastructure.graph import graph_db
from app.services.connectors import ConnectorService
from app.services.enrichment_engine import EnrichmentEngine

logger = logging.getLogger(__name__)


class AttributionEngine:
    """
    Correlates disparate indicators (IPs, emails, social aliases) into a Threat Actor Dossier
    and persists a minimal Neo4j threat-actor subgraph for downstream legal workflows.

    Workflow:
    1) Uses ConnectorService.search_public_intel(...) to gather source observations
    2) Enriches with EnrichmentEngine to produce attribution signals
    3) Creates/updates a ThreatActor node and linked evidence nodes in Neo4j
    """

    def __init__(self, connector: Optional[ConnectorService] = None, enrichment: Optional[EnrichmentEngine] = None):
        self.connector = connector or ConnectorService()
        self.enrichment = enrichment or EnrichmentEngine()

    async def correlate_indicators(
        self, 
        indicators: List[str], 
        dossier_meta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main entry point: correlate a list of indicators into a threat actor dossier.
        
        Args:
            indicators: List of threat indicators (IPs, emails, domains, file hashes)
            dossier_meta: Optional metadata (note, classification, etc.)
        
        Returns:
            Dictionary with actor_id, confidence score, and observation counts
        """
        dossier_meta = dossier_meta or {}
        logger.info(f"[Attribution] Correlating {len(indicators)} indicators")

        # 1. Gather raw OSINT for each indicator in parallel
        async def gather(indicator):
            try:
                return await self.connector.search_public_intel(indicator)
            except Exception as e:
                logger.warning(f"[Attribution] connector failure for {indicator}: {e}")
                return []

        tasks = [gather(i) for i in indicators]
        raw_results = await asyncio.gather(*tasks)

        # Flatten results
        observations: List[Dict[str, Any]] = [r for sub in raw_results for r in sub]

        # 2. Enrich key infrastructure indicators (IPs/domains)
        infra_hits = [o for o in observations if o.get("type") == "infrastructure"]
        enriched = []
        for hit in infra_hits:
            ip = hit.get("data", {}).get("ip")
            if ip:
                try:
                    enriched_data = await self.enrichment._threat_feed(ip) if hasattr(self.enrichment, "_threat_feed") else {"ip": ip}
                    enriched.append(enriched_data)
                except Exception as e:
                    logger.warning(f"[Attribution] enrichment failed for {ip}: {e}")

        # 3. Heuristic attribution scoring (confidence based on evidence count)
        # Combine evidence count and enriched hits to produce confidence score
        confidence = min(0.99, 0.1 * len(observations) + 0.3 * len(enriched))
        actor_id = f"TA-{abs(hash(tuple(sorted(indicators)))) % (10**8)}"

        logger.info(f"[Attribution] Generated actor_id={actor_id}, confidence={confidence:.2f}")

        # 4. Persist minimal dossier to Neo4j
        # Create ThreatActor node + Evidence nodes and HAS_EVIDENCE relationships
        try:
            await graph_db.execute_query(
                "MERGE (ta:ThreatActor {actor_id: $actor_id}) "
                "SET ta.last_seen = datetime(), ta.confidence = $confidence, ta.summary = $summary",
                {
                    "actor_id": actor_id,
                    "confidence": float(confidence),
                    "summary": dossier_meta.get("note", "Automated dossier")
                }
            )

            # Link evidence to threat actor
            for obs in observations:
                src = obs.get("source", "unknown")
                key = (
                    obs.get("data", {}).get("ip") 
                    or obs.get("data", {}).get("hash") 
                    or obs.get("data", {}).get("domain") 
                    or str(obs.get("data"))
                )
                
                await graph_db.execute_query(
                    "MERGE (e:Evidence {key: $key}) "
                    "SET e.source = $src, e.payload = $payload "
                    "WITH e "
                    "MATCH (ta:ThreatActor {actor_id: $actor_id}) "
                    "MERGE (ta)-[:HAS_EVIDENCE {first_seen: datetime()}]->(e)",
                    {
                        "key": key,
                        "src": src,
                        "payload": obs.get("data", {}),
                        "actor_id": actor_id
                    }
                )

            logger.info(f"[Attribution] Persisted dossier to Neo4j: {actor_id}")
        except Exception as e:
            logger.error(f"[Attribution] Neo4j persistence failed: {e}")

        # 5. Return dossier summary (for API response / UI consumption)
        dossier = {
            "actor_id": actor_id,
            "confidence": confidence,
            "observations": len(observations),
            "enriched_matches": len(enriched),
        }

        logger.info(f"[Attribution] Created dossier {actor_id} (confidence={confidence:.2f})")
        return dossier


# Expose default engine instance
attribution_engine = AttributionEngine()
