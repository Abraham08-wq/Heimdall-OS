import logging
import httpx
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

NVD_BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"

class NVDService:
    """
    Service for fetching CVE data from the National Vulnerability Database (NVD).
    """

    def _get_fallback_cves(self) -> List[Dict[str, Any]]:
        """
        Returns a structured sample of real data for development or fallback.
        """
        logger.debug("[NVDService] Using fallback CVE data.")
        return [
            {
                "cve_id": "CVE-2021-44228",
                "severity": 10.0,
                "description": "Apache Log4j2 JNDI features do not protect against attacker controlled LDAP...",
                "published": "2021-12-10T07:15Z",
                "last_modified": "2022-03-28T15:08Z",
                "keywords": ["apache", "java"],
            },
            {
                "cve_id": "CVE-2023-23397",
                "severity": 9.8,
                "description": "Microsoft Outlook Elevation of Privilege Vulnerability.",
                "published": "2023-03-14T17:15Z",
                "last_modified": "2023-06-13T20:15Z",
                "keywords": ["microsoft", "outlook"],
            },
        ]

    def fetch_cves(self, keyword: str, limit: int) -> List[Dict[str, Any]]:
        """
        Fetches CVEs from the NVD API v2.
        Falls back to sample data on API failure.
        """
        try:
            resp = httpx.get(
                NVD_BASE_URL,
                params={"keywordSearch": keyword, "resultsPerPage": limit},
                timeout=15.0,
                headers={"User-Agent": "ProjectXY-ThreatIntel/1.0"},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"[NVDService] NVD fetch failed: {e}. Using fallback data.")
            return self._get_fallback_cves()

        results = []
        if not data.get("vulnerabilities"):
            return results

        for item in data.get("vulnerabilities", []):
            cve_data = item.get("cve", {})
            cve_id   = cve_data.get("id", "")
            if not cve_id:
                continue

            # Extract CVSS score
            severity  = 0.0
            metrics   = cve_data.get("metrics", {})
            for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
                if key in metrics and metrics[key]:
                    score = metrics[key][0].get("cvssData", {}).get("baseScore", 0.0)
                    severity = float(score)
                    break

            # Extract description
            desc = ""
            for d in cve_data.get("descriptions", []):
                if d.get("lang") == "en":
                    desc = d.get("value", "")[:500]
                    break
            
            # Extract keywords from description for Neo4j resource matching
            keywords = [kw for kw in [
                "nginx", "redis", "kafka", "postgres", "postgresql",
                "apache", "tomcat", "spring", "docker", "kubernetes",
                "openssl", "python", "nodejs", "react", "linux",
            ] if kw.lower() in desc.lower()]

            results.append({
                "cve_id":        cve_id,
                "severity":      severity,
                "description":   desc,
                "published":     cve_data.get("published", ""),
                "last_modified": cve_data.get("lastModified", ""),
                "keywords":      keywords,
            })

        return results

nvd_service = NVDService()
