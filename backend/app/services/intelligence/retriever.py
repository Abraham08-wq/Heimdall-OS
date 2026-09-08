"""
Federated Data Retrieval Engine
───────────────────────────────
Connects to multiple OSINT sources to pull data in parallel.
"""
import asyncio
import httpx
import logging
from typing import Dict, Any, List

from app.core.config import settings
from app.infrastructure.graph import graph_db

logger = logging.getLogger(__name__)

class FederatedDataRetrievalEngine:
    """
    The central intelligence orchestrator.
    """

    async def _query_leak_archives(self, target: str) -> Dict:
        logger.info(f"[LeakArchives] Querying for {target}...")
        if not settings.LEAK_LOOKUP_API_KEY:
            logger.warning("[LeakArchives] LEAK_LOOKUP_API_KEY missing. Returning simulated data.")
            return {"source": "Leak-Lookup (Sim)", "data": f"Simulated leak for {target}"}

        async with httpx.AsyncClient() as client:
            try:
                payload = {"key": settings.LEAK_LOOKUP_API_KEY, "type": "email_address", "query": target}
                resp = await client.post("https://leak-lookup.com/api/search", data=payload, timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    return {"source": "Leak-Lookup", "data": f"Found {len(data.get('message', {}))} breach sources."}
            except Exception as e:
                logger.error(f"[LeakArchives] Error: {e}")
                
        return {"source": "Leak-Lookup (Fail)", "data": "Request Failed"}

    async def _query_infrastructure_radar(self, target: str) -> Dict:
        logger.info(f"[InfrastructureRadar] Querying for {target}...")
        if not settings.SHODAN_API_KEY:
            logger.warning("[InfrastructureRadar] SHODAN_API_KEY missing. Returning simulated data.")
            return {"source": "Shodan (Sim)", "data": f"Simulated infrastructure for {target}"}
            
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"https://api.shodan.io/shodan/host/{target}?key={settings.SHODAN_API_KEY}", timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    ports = data.get("ports", [])
                    return {"source": "Shodan", "data": f"Open ports: {ports}"}
            except Exception as e:
                 logger.error(f"[InfrastructureRadar] Error: {e}")
                 
        return {"source": "Shodan (Fail)", "data": "Request Failed"}

    async def _query_social_identity(self, target: str) -> Dict:
        logger.info(f"[SocialIdentity] Querying for {target}...")
        await asyncio.sleep(1.2)
        # Simulating Sherlock as real Sherlock requires local CLI execution and scraping
        return {"source": "Sherlock (Sim)", "data": f"Simulated social media profiles found for {target}"}

    async def _query_malware_c2(self, target: str) -> Dict:
        logger.info(f"[MalwareC2] Querying for {target}...")
        if not settings.ALIENVAULT_API_KEY:
            logger.warning("[MalwareC2] ALIENVAULT_API_KEY missing. Returning simulated data.")
            return {"source": "AlienVault OTX (Sim)", "data": f"Simulated C2 data for {target}"}

        async with httpx.AsyncClient() as client:
            try:
                headers = {"X-OTX-API-KEY": settings.ALIENVAULT_API_KEY}
                indicator_type = "IPv4" if " " not in target and target.count(".") == 3 else "domain"
                
                resp = await client.get(f"https://otx.alienvault.com/api/v1/indicators/{indicator_type}/{target}/general", headers=headers, timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    pulse_count = data.get('pulse_info', {}).get('count', 0)
                    return {"source": "AlienVault OTX", "data": f"Found in {pulse_count} OTX pulses."}
            except Exception as e:
                logger.error(f"[MalwareC2] Error: {e}")
                
        return {"source": "AlienVault OTX (Fail)", "data": "Request Failed"}
    
    async def _inject_to_neo4j(self, target: str, results: List[Dict]):
        """
        Injects the results of the deep scan into Neo4j.
        """
        logger.info(f"Injecting deep scan results for {target} into Neo4j...")
        
        # Create the target node
        await graph_db.execute_query("MERGE (t:Target {id: $target})", {"target": target})
        
        for result in results:
            source = result['source']
            # Create the OSINT source node
            await graph_db.execute_query("MERGE (s:OSINTSource {name: $source})", {"source": source})
            # Create the relationship
            await graph_db.execute_query(
                "MATCH (t:Target {id: $target}), (s:OSINTSource {name: $source}) "
                "MERGE (t)-[:HAS_DATA_FROM]->(s)",
                {"target": target, "source": source}
            )

    async def deep_scan(self, target: str) -> List[Dict]:
        """
        Runs a deep scan across all connected OSINT sources.
        """
        logger.info(f"Initiating deep scan for: {target}")

        tasks = [
            self._query_leak_archives(target),
            self._query_infrastructure_radar(target),
            self._query_social_identity(target),
            self._query_malware_c2(target),
        ]

        results = await asyncio.gather(*tasks)
        logger.info(f"Deep scan completed for: {target}")

        await self._inject_to_neo4j(target, results)

        return results

retriever_engine = FederatedDataRetrievalEngine()
