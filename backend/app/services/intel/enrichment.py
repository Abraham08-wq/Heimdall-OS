import asyncio
import httpx
from typing import Any, Dict, List, TypedDict
from textblob import TextBlob

from app.core.config import settings

# --- Mock Data Structures ---

class ShodanScanResult(TypedDict):
    ip: str
    ports: List[int]
    vulnerabilities: List[str]
    hostname: str

class IntelXLeakResult(TypedDict):
    source: str
    email: str
    password_hash: str
    breach_date: str

class BabelXChatterResult(TypedDict):
    source_language: str
    translated_text: str
    sentiment: float # -1 (negative) to 1 (positive)
    source_url: str


class EnrichmentEngine:
    """
    Connects to multiple OSINT sources to enrich data about a given target.
    This class simulates asynchronous API calls to various intelligence platforms.
    """

    def __init__(self):
        pass

    async def query_global_radar(self, target_ip: str) -> Dict[str, Any]:
        """
        Queries Shodan to map the target's public exposure.
        """
        print(f"🛰️  [Global Radar] Scanning IP: {target_ip}...")
        if not settings.SHODAN_API_KEY:
            print("⚠️  [Global Radar] SHODAN_API_KEY missing. Returning simulated data.")
            return {"shodan": {"ip": target_ip, "ports": [80, 443], "vulnerabilities": ["Simulated_No_Key"], "hostname": ""}}
            
        shodan_result = {}
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"https://api.shodan.io/shodan/host/{target_ip}?key={settings.SHODAN_API_KEY}", timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    shodan_result = {
                        "ip": data.get("ip_str", target_ip),
                        "ports": data.get("ports", []),
                        "vulnerabilities": list(data.get("vulns", {}).keys()) if "vulns" in data else [],
                        "hostname": data.get("hostnames", [""])[0] if data.get("hostnames") else ""
                    }
                else:
                    print(f"⚠️  [Global Radar] Shodan error: {resp.status_code}")
            except Exception as e:
                print(f"⚠️  [Global Radar] Error connecting to Shodan: {e}")

        print(f"📡  [Global Radar] Found {len(shodan_result.get('ports', []))} open ports for {target_ip}.")
        return {"shodan": shodan_result if shodan_result else None, "censys": None}

    async def query_archive_of_secrets(self, target_email: str) -> Dict[str, Any]:
        """
        Uses Intel X to pull historical breach data.
        """
        print(f"📚  [Archive of Secrets] Searching for email: {target_email}")
        if not settings.INTEL_X_API_KEY:
            print("⚠️  [Archive of Secrets] INTEL_X_API_KEY missing. Returning simulated data.")
            return {"intelx": [{"source": "Simulated", "email": target_email, "password_hash": "xxx", "breach_date": "2024-01-01"}]}

        intelx_result = []
        async with httpx.AsyncClient() as client:
            try:
                headers = {"x-key": settings.INTEL_X_API_KEY}
                # Intel X Search API (simplified implementation)
                resp = await client.post("https://2.intelx.io/intelligent/search", headers=headers, json={"term": target_email}, timeout=10.0)
                if resp.status_code == 200:
                    search_id = resp.json().get("id")
                    # Wait and fetch results
                    await asyncio.sleep(2)
                    res_resp = await client.get(f"https://2.intelx.io/intelligent/search/result?id={search_id}&limit=5", headers=headers, timeout=10.0)
                    if res_resp.status_code == 200:
                        records = res_resp.json().get("records", [])
                        for rec in records:
                            intelx_result.append({
                                "source": rec.get("bucket", "Unknown"),
                                "email": target_email,
                                "password_hash": "REDACTED",
                                "breach_date": rec.get("date", "Unknown")
                            })
            except Exception as e:
                print(f"⚠️  [Archive of Secrets] Intel X error: {e}")

        print(f"🤫  [Archive of Secrets] Found {len(intelx_result)} leaks for {target_email}.")
        return {"intelx": intelx_result if intelx_result else None}

    async def query_linguistic_mesh(self, keywords: List[str]) -> Dict[str, Any]:
        """
        Simulates scraping dark web chatter and uses TextBlob for real NLP sentiment analysis.
        """
        print(f"🕸️  [Linguistic Mesh] Monitoring chatter for keywords: {keywords}")
        
        # Simulate scraped text since we don't have a real dark web feed API
        scraped_texts = [
            f"The '{keywords[0]}' exploit is working well. Systems are dropping.",
            f"I cannot figure out how to bypass the firewall for '{keywords[0]}', very frustrating.",
            f"Is the '{keywords[0]}' vulnerability patched in the latest release?"
        ]
        
        babelx_result = []
        for text in scraped_texts:
            blob = TextBlob(text)
            sentiment = blob.sentiment.polarity
            babelx_result.append({
                "source_language": "English (NLP Analyzed)",
                "translated_text": text,
                "sentiment": sentiment,
                "source_url": "https://chatter.site/feed"
            })

        print(f"🗣️  [Linguistic Mesh] Analyzed {len(babelx_result)} conversations with NLP.")
        return {"babelx": babelx_result}

    async def enrich_entity(self, target: str) -> Dict[str, Any]:
        """
        Orchestrates the enrichment process for a given target (IP, email, or keyword).
        This is the main entry point for the unified_chain.
        """
        # A simple heuristic to determine target type
        if "@" in target:
            # Assumes target is an email
            return await self.query_archive_of_secrets(target)
        elif all(c in "0123456789." for c in target) and target.count('.') == 3:
            # Assumes target is an IP address
            return await self.query_global_radar(target)
        else:
            # Assumes target is a keyword for chatter analysis
            return await self.query_linguistic_mesh([target])

# Global instance to be imported by other services
enrichment_engine = EnrichmentEngine()

