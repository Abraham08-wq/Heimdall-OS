"""
threat_intel.py — Real CVE ingestion from NVD API v2.
Replaces mock CVE feed with live National Vulnerability Database pulls.
Falls back gracefully to a sample dataset if NVD is unreachable or in DEV mode.
"""
import logging
from typing import Dict, Any, List
from neo4j import GraphDatabase
from app.core.config import settings
from app.services.intelligence_service import nvd_service

logger = logging.getLogger(__name__)

class ThreatIntelIngester:
    """
    Threat Intelligence Ingestion Pipeline

    Pulls real CVEs from NIST NVD API v2 and writes them into the
    Neo4j Risk Graph as ThreatIntel nodes linked to affected Resources.
    """

    def __init__(self):
        try:
            self.driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
            self.is_connected = True
        except Exception as e:
            logger.error(f"Failed to connect TI Ingester to Neo4j: {e}")
            self.is_connected = False

    def ingest_cve_feed(self, keyword: str = "remote code execution", results_per_page: int = 20) -> int:
        """
        Pull real CVEs from NVD API v2 matching a keyword and ingest into Neo4j.
        Replaces the deprecated mock feed.
        """
        if not self.is_connected:
            return 0

        cves = nvd_service.fetch_cves(keyword, results_per_page)
        if not cves:
            # This can happen if NVD returns 0 results for the keyword, or if the fetch fails and returns an empty list.
            logger.warning("[TI] NVD fetch returned no CVEs — check network, keyword, or see previous error logs.")
            return 0

        query = """
        UNWIND $cves as cve
        MERGE (t:ThreatIntel {id: cve.cve_id})
        SET t.severity      = cve.severity,
            t.description   = cve.description,
            t.published     = cve.published,
            t.last_modified = cve.last_modified,
            t.source        = 'NVD',
            t.updated_at    = timestamp()
        WITH t, cve
        OPTIONAL MATCH (r:Resource)
        WHERE any(kw IN cve.keywords WHERE toLower(r.name) CONTAINS kw)
        FOREACH (_ IN CASE WHEN r IS NOT NULL THEN [1] ELSE [] END |
            MERGE (t)-[:VULNERABILITY_EXPOSES]->(r)
        )
        """
        try:
            with self.driver.session() as session:
                session.run(query, cves=cves)
            logger.info(f"[TI] Ingested {len(cves)} CVEs from NVD into Neo4j.")
            return len(cves)
        except Exception as e:
            logger.warning(f"[TI] Neo4j CVE write failed: {e}")
            return 0

    def query_vulnerable_infrastructure(self) -> List[Dict[str, Any]]:
        """Identify internal resources exposed to known CVEs."""
        if not self.is_connected:
            return []

        query = """
        MATCH (t:ThreatIntel)-[:VULNERABILITY_EXPOSES]->(r:Resource)
        RETURN t.id as cve_id, t.severity as vulnerability_score,
               r.name as affected_resource, t.description as description
        ORDER BY t.severity DESC
        LIMIT 50
        """
        try:
            with self.driver.session() as session:
                return session.run(query).data()
        except Exception:
            return []


threat_intel_pipeline = ThreatIntelIngester()
