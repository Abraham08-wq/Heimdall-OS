import asyncio
import socket
import json
from typing import Dict, Any, List, Optional
import httpx
from app.core.config import settings


class OSINTEngine:
    """
    Global Reconnaissance Engine — OSINT Web Footprinting.
    Executes entirely passive, legal, non-intrusive operations.
    """

    def __init__(self):
        self._client = httpx.AsyncClient(
            headers={"User-Agent": "ProjectXY-OSINT-Engine/1.0"},
            timeout=10.0,
        )
        # Fallback used only when Shodan key is absent or in DEVELOPMENT_MODE
        self._fallback_shodan_data = {
            "open_ports_historical": [80, 443, 8080, 22],
            "vulnerabilities": ["CVE-2021-34527", "CVE-2023-23397"],
            "isp": "Cloud Hosting Provider",
            "last_scanned": "2023-10-15T00:00:00Z",
        }

    # ── DNS Resolution ─────────────────────────────────────────────────────────

    async def resolve_dns_records(self, domain: str) -> Dict[str, Any]:
        """
        Passive DNS Enumeration using the system resolver (no external deps).

        Uses asyncio thread-executor to call socket.getaddrinfo / gethostbyname_ex
        for A records, and dnspython if available for MX/TXT/NS.  When dnspython
        is not installed the engine still resolves A records live and returns
        empty lists for MX/TXT/NS rather than mocked strings.
        """
        records: Dict[str, Any] = {"A": [], "MX": [], "TXT": [], "NS": [], "CNAME": []}
        loop = asyncio.get_running_loop()

        # ── A record (always live via stdlib) ─────────────────────────────────
        try:
            _, _, ip_addresses = await loop.run_in_executor(
                None, socket.gethostbyname_ex, domain
            )
            records["A"] = ip_addresses
        except OSError as e:
            records["error"] = str(e)

        # ── MX / TXT / NS via dnspython if installed ──────────────────────────
        try:
            import dns.resolver  # type: ignore[import]
            import dns.asyncresolver  # type: ignore[import]

            async_resolver = dns.asyncresolver.Resolver()

            async def _query(qtype: str) -> List[str]:
                try:
                    answer = await async_resolver.resolve(domain, qtype)
                    if qtype == "MX":
                        return [f"{r.preference} {r.exchange.to_text()}" for r in answer]
                    return [r.to_text() for r in answer]
                except Exception:
                    return []

            mx, txt, ns = await asyncio.gather(
                _query("MX"), _query("TXT"), _query("NS"), return_exceptions=False
            )
            records["MX"] = mx
            records["TXT"] = txt
            records["NS"] = ns

        except ImportError:
            # dnspython not installed — A record is still live, others are empty
            pass
        except Exception as e:
            records["dns_error"] = str(e)

        return records

    # ── HTTP Footprinting ──────────────────────────────────────────────────────

    async def extract_technology_stack(self, url: str) -> Dict[str, Any]:
        """
        Passive HTTP Footprinting via Header Extraction and Server Signatures.
        """
        stack: Dict[str, Any] = {"server": "Unknown", "x-powered-by": "Unknown", "headers": {}}

        if not url.startswith("http"):
            url = f"https://{url}"

        try:
            response = await self._client.get(url, follow_redirects=True)
            headers = dict(response.headers)
            stack["headers"] = headers
            stack["server"] = headers.get("server", headers.get("Server", "Unknown"))
            stack["x-powered-by"] = headers.get("x-powered-by", headers.get("X-Powered-By", "Unknown"))
            stack["status_code"] = response.status_code
        except httpx.RequestError as e:
            stack["error"] = f"Could not connect to {url}: {e}"

        return stack

    # ── Shodan Lookup ──────────────────────────────────────────────────────────

    async def shodan_lookup(self, ip_or_domain: str) -> Dict[str, Any]:
        """
        Performs a lookup using the Shodan API.
        Falls back to safe placeholder data in DEV mode or when the key is absent.
        """
        fallback_data = self._fallback_shodan_data.copy()
        fallback_data["query"] = ip_or_domain

        api_key: Optional[str] = getattr(settings, "SHODAN_API_KEY", None)
        if not api_key:
            fallback_data["note"] = "SHODAN_API_KEY not configured"
            return fallback_data

        # Resolve domain → IP before querying Shodan
        target_ip = ip_or_domain
        if not _looks_like_ip(target_ip):
            dns_results = await self.resolve_dns_records(ip_or_domain)
            a_records = dns_results.get("A", [])
            if a_records:
                target_ip = a_records[0]
            else:
                return {"error": f"Could not resolve domain: {ip_or_domain}", "query": ip_or_domain}

        try:
            url = f"https://api.shodan.io/shodan/host/{target_ip}?key={api_key}"
            response = await self._client.get(url)
            if response.status_code == 200:
                return response.json()
            fallback_data["error"] = f"Shodan API returned status {response.status_code}"
            return fallback_data
        except httpx.RequestError as e:
            fallback_data["error"] = f"Shodan API request failed: {e}"
            return fallback_data

    # ── Full Recon Chain ───────────────────────────────────────────────────────

    async def execute_full_recon(self, target: str) -> Dict[str, Any]:
        """
        Chains all passive OSINT operations against a target in parallel.
        """
        vitals = await asyncio.gather(
            self.resolve_dns_records(target),
            self.extract_technology_stack(target),
            self.shodan_lookup(target),
            return_exceptions=True,
        )

        return {
            "target": target,
            "dns_topology": vitals[0] if not isinstance(vitals[0], Exception) else str(vitals[0]),
            "tech_stack": vitals[1] if not isinstance(vitals[1], Exception) else str(vitals[1]),
            "threat_intel": vitals[2] if not isinstance(vitals[2], Exception) else str(vitals[2]),
            "status": "COMPLETED",
        }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _looks_like_ip(value: str) -> bool:
    """Returns True if value resembles an IPv4 or IPv6 address."""
    try:
        socket.inet_pton(socket.AF_INET, value)
        return True
    except OSError:
        pass
    try:
        socket.inet_pton(socket.AF_INET6, value)
        return True
    except OSError:
        pass
    return False


osint_global_engine = OSINTEngine()
