import httpx
import logging
from typing import List, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

class ConnectorService:
    """
    Global Connector: Fetches data from external/public sources (OSINT).
    Connects to real OSINT APIs like Shodan and AlienVault OTX.
    """

    async def _search_shodan(self, ip: str) -> List[Dict[str, Any]]:
        """
        Searches Shodan for a given IP address.
        """
        if not settings.SHODAN_API_KEY:
            logger.warning("SHODAN_API_KEY not configured. Skipping Shodan search.")
            return []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.shodan.io/shodan/host/{ip}",
                    params={"key": settings.SHODAN_API_KEY},
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                return [{
                    "source": "Shodan",
                    "type": "infrastructure",
                    "data": {
                        "ip": data.get("ip_str"),
                        "ports": data.get("ports"),
                        "vulns": data.get("vulns"),
                        "isp": data.get("isp"),
                        "org": data.get("org"),
                    }
                }]
        except httpx.HTTPStatusError as e:
            logger.error(f"Shodan API error for IP {ip}: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Error searching Shodan for IP {ip}: {e}")
            return []

    async def _search_otx(self, indicator: str) -> List[Dict[str, Any]]:
        """
        Searches AlienVault OTX for a given indicator (domain or hash).
        """
        if not settings.ALIENVAULT_API_KEY:
            logger.warning("ALIENVAULT_API_KEY not configured. Skipping OTX search.")
            return []

        indicator_type = "domain" if "." in indicator else "file"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://otx.alienvault.com/api/v1/indicators/{indicator_type}/{indicator}/general",
                    headers={"X-OTX-API-KEY": settings.ALIENVAULT_API_KEY},
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                
                # Basic transformation, can be improved
                return [{
                    "source": "AlienVault OTX",
                    "type": f"{indicator_type}_indicator",
                    "data": {
                        "indicator": data.get("indicator"),
                        "pulse_info": data.get("pulse_info"),
                        "reputation": data.get("reputation"),
                    }
                }]
        except httpx.HTTPStatusError as e:
            logger.error(f"OTX API error for {indicator}: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Error searching OTX for {indicator}: {e}")
            return []

    async def search_public_intel(self, query: str) -> List[Dict[str, Any]]:
        """
        Search public databases for a given query (IP, Hash, Domain).
        """
        # Simple IP address regex
        import re
        if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", query):
            return await self._search_shodan(query)
        # For domains and hashes, we use OTX
        else:
            return await self._search_otx(query)

connector_service = ConnectorService()
