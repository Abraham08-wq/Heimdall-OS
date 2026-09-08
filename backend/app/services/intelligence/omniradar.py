"""
SOVEREIGN RADAR (Omni-Probe 2.0)
=================================
Global continuous threat discovery and reconnaissance

Integrates with:
- Censys API (certificate, host data)
- Shodan API (IoT, vulnerable services)
- Intel X (breach databases)
- TheBlacklight (breach corpus)
- Passive DNS records
- BGP routing announcements
- SSL certificate transparency logs

Creates a "Global Radar" view of threat landscape.
"""

from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import json
import hashlib
from abc import ABC, abstractmethod


class RadarSource(Enum):
    """Data sources for global threat radar"""
    CENSYS = "censys"
    SHODAN = "shodan"
    INTEL_X = "intel_x"
    BLACKLIGHT = "blacklight"
    PASSIVE_DNS = "passive_dns"
    CT_LOGS = "ct_logs"
    BGP = "bgp"
    URLHAUS = "urlhaus"
    MALWAREBAZAAR = "malwarebazaar"
    ABUSEIPDB = "abuseipdb"


class AssetType(Enum):
    """Types of discoverable assets"""
    WEB_SERVICE = "web_service"
    DATABASE = "database"
    VPN = "vpn"
    SSH = "ssh"
    CLOUD_STORAGE = "cloud_storage"
    ICS_SCADA = "ics_scada"
    IoT_DEVICE = "iot_device"
    VoIP = "voip"
    PRINTER = "printer"
    CAMERA = "camera"


class VulnerabilityStatus(Enum):
    """Known vulnerability status"""
    UNPATCHED = "unpatched"
    PATCHED = "patched"
    EXPLOITED = "exploited"
    UNKNOWN = "unknown"


@dataclass
class DiscoveredAsset:
    """An asset discovered through global scanning"""
    asset_id: str
    ip_address: str
    hostname: str
    asset_type: AssetType
    port: int
    service: str
    version: Optional[str]
    organization: str
    country: str
    asn: int
    
    # Vulnerability info
    vulnerabilities: List[Dict]
    known_exploits: List[str]
    patch_status: VulnerabilityStatus
    
    # Exposure metrics
    is_exposed: bool
    exposure_severity: int  # 1-10
    data_at_risk_type: Optional[str]
    
    # Discovery
    discovered_via: RadarSource
    discovered_at: datetime
    last_scan: datetime
    confidence: float


@dataclass
class BreachDataSet:
    """Discovered breach data"""
    dataset_id: str
    name: str
    date_discovered: datetime
    record_count: int
    data_types: List[str]  # emails, passwords, SSNs, etc.
    source: str  # Leaked database name
    has_customer_data: bool
    affected_organizations: List[str]
    leaked_via: RadarSource


@dataclass
class DomainIntelligence:
    """Intelligence about a domain"""
    domain: str
    ip_addresses: List[str]
    whois_owner: Optional[str]
    registration_date: Optional[datetime]
    expiration_date: Optional[datetime]
    is_sinkholed: bool
    
    # Threat indicators
    is_malicious: bool
    malware_family: Optional[str]
    c2_server: bool
    phishing_domain: bool
    typosquatting: bool
    
    # Certificate data
    ssl_certificates: List[Dict]
    certificate_history: List[Dict]
    
    # DNS history
    dns_history: List[Tuple[str, datetime]]  # (IP, date)
    
    # Threat intel
    threat_feeds: List[str]
    abuse_reports: int


@dataclass
class GlobalRadarSnapshot:
    """Snapshot of global threat landscape"""
    snapshot_id: str
    timestamp: datetime
    
    # Statistics
    total_assets_discovered: int
    exposed_assets: int
    critical_vulnerabilities: int
    malicious_ips: int
    known_breaches: int
    active_campaigns: int
    
    # Top threats
    top_threat_actors: List[str]
    top_malware_families: List[str]
    top_vulnerable_services: List[str]
    top_targeted_sectors: List[str]
    
    # Regional analysis
    threat_map: Dict[str, int]  # country -> threat count
    
    # Full data sets
    assets: List[DiscoveredAsset]
    breaches: List[BreachDataSet]


class CensysScanner(ABC):
    """Base class for Censys integration"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
    
    @abstractmethod
    async def scan_hosts(self, query: str) -> List[DiscoveredAsset]:
        """Search hosts via Censys API"""
        pass
    
    @abstractmethod
    async def scan_certificates(self, query: str) -> List[Dict]:
        """Search certificates via Censys API"""
        pass


class ShodanScanner(ABC):
    """Base class for Shodan integration"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
    
    @abstractmethod
    async def search_devices(self, query: str) -> List[DiscoveredAsset]:
        """Search vulnerable devices via Shodan API"""
        pass


class BreachDatabaseAggregator(ABC):
    """Base class for breach database integration"""
    
    @abstractmethod
    async def search_intel_x(self, search_term: str) -> List[BreachDataSet]:
        """Search Intel X breach databases"""
        pass
    
    @abstractmethod
    async def search_blacklight(self, search_term: str) -> List[BreachDataSet]:
        """Search Blacklight breach corpus"""
        pass


class PassiveDNSLookup(ABC):
    """Base class for Passive DNS queries"""
    
    @abstractmethod
    async def get_domain_history(self, domain: str) -> List[Tuple[str, datetime]]:
        """Get DNS resolution history for domain"""
        pass
    
    @abstractmethod
    async def reverse_lookup(self, ip: str) -> List[str]:
        """Reverse DNS lookup - find domains pointing to IP"""
        pass


class CTLogAnalyzer(ABC):
    """Base class for Certificate Transparency log analysis"""
    
    @abstractmethod
    async def search_certificates(self, domain: str) -> List[Dict]:
        """Search CT logs for certificates issued for domain"""
        pass


class SovereignRadar:
    """Main global threat discovery engine"""
    
    def __init__(self, 
                 censys_key: str = None,
                 shodan_key: str = None,
                 intel_x_key: str = None,
                 db_service=None,
                 redis_client=None):
        
        # Instantiate integrations if concrete implementations are available.
        # If only abstract base classes exist (no provider implemented), set to None and continue.
        try:
            self.censys = CensysScanner(censys_key)
        except TypeError:
            self.censys = None

        try:
            self.shodan = ShodanScanner(shodan_key)
        except TypeError:
            self.shodan = None

        try:
            self.breach_agg = BreachDatabaseAggregator()
        except TypeError:
            self.breach_agg = None

        try:
            self.passive_dns = PassiveDNSLookup()
        except TypeError:
            self.passive_dns = None

        try:
            self.ct_logs = CTLogAnalyzer()
        except TypeError:
            self.ct_logs = None
        
        self.db = db_service
        self.redis = redis_client
        
        self.discovered_assets: Dict[str, DiscoveredAsset] = {}
        self.breach_datasets: Dict[str, BreachDataSet] = {}
        self.domain_intel: Dict[str, DomainIntelligence] = {}
    
    async def continuous_scan(self, interval_seconds: int = 3600):
        """Continuously scan global threat landscape"""
        while True:
            try:
                await self.perform_global_scan()
                await asyncio.sleep(interval_seconds)
            except Exception as e:
                print(f"Error during global scan: {e}")
                await asyncio.sleep(interval_seconds)
    
    async def perform_global_scan(self) -> GlobalRadarSnapshot:
        """Perform comprehensive global threat scan"""
        
        # Scan in parallel
        scan_tasks = [
            self._scan_exposed_services(),
            self._scan_breached_data(),
            self._scan_malicious_domains(),
            self._scan_malware_infrastructure(),
        ]
        
        await asyncio.gather(*scan_tasks)
        
        # Generate snapshot
        snapshot = await self._create_snapshot()
        
        # Store and alert
        await self._store_snapshot(snapshot)
        await self._process_snapshot(snapshot)
        
        return snapshot
    
    async def _scan_exposed_services(self) -> List[DiscoveredAsset]:
        """Scan for exposed services using Censys and Shodan"""
        
        queries = [
            "HTTP/1.1 200 OK",
            "MySQL server",
            "MongoDB",
            "Elasticsearch",
            "Jenkins",
            "Apache Hadoop",
            "CouchDB",
            "Exposed AWS buckets",
            "Confluence",
            "Jira",
        ]
        
        assets = []
        
        for query in queries:
            try:
                censys_results = []
                shodan_results = []
                if self.censys is not None:
                    try:
                        censys_results = await self.censys.scan_hosts(query)
                    except Exception as e:
                        print(f"Censys scan error for {query}: {e}")
                if self.shodan is not None:
                    try:
                        shodan_results = await self.shodan.search_devices(query)
                    except Exception as e:
                        print(f"Shodan scan error for {query}: {e}")
                
                assets.extend(censys_results)
                assets.extend(shodan_results)
            except Exception as e:
                print(f"Error scanning for {query}: {e}")
        
        # Store discovered assets
        for asset in assets:
            self.discovered_assets[asset.asset_id] = asset
        
        return assets
    
    async def _scan_breached_data(self) -> List[BreachDataSet]:
        """Scan for recently breached data"""
        
        breaches = []
        
        try:
            # Search Intel X for known breaches
            intel_x_breaches = await self.breach_agg.search_intel_x("*")
            breaches.extend(intel_x_breaches)
            
            # Search Blacklight
            blacklight_breaches = await self.breach_agg.search_blacklight("*")
            breaches.extend(blacklight_breaches)
        
        except Exception as e:
            print(f"Error scanning breaches: {e}")
        
        # Store breaches
        for breach in breaches:
            self.breach_datasets[breach.dataset_id] = breach
        
        return breaches
    
    async def _scan_malicious_domains(self) -> List[DomainIntelligence]:
        """Scan for malicious domains"""
        
        domains = []
        
        # Would scan:
        # - URLhaus for malware distribution URLs
        # - PhishTank for phishing domains
        # - Threat feeds for C2 domains
        # - DGA analysis results
        
        return domains
    
    async def _scan_malware_infrastructure(self) -> List[Dict]:
        """Scan for malware command & control infrastructure"""
        
        infrastructure = []
        
        # Would scan:
        # - MalwareBazaar for recent samples
        # - C2 tracker for active C2 servers
        # - Botnet tracker for botnet infrastructure
        # - Ransomware leak sites
        
        return infrastructure
    
    async def search_organization(self, org_name: str) -> Dict:
        """Search for all assets belonging to an organization"""
        
        results = {
            "exposed_assets": [],
            "breached_data": [],
            "malicious_domains": [],
            "vulnerable_ips": [],
        }
        
        # Search exposed assets
        for asset in self.discovered_assets.values():
            if org_name.lower() in asset.organization.lower():
                results["exposed_assets"].append(asdict(asset))
        
        # Search breached data
        for breach in self.breach_datasets.values():
            if any(org.lower().find(org_name.lower()) >= 0 
                   for org in breach.affected_organizations):
                results["breached_data"].append(asdict(breach))
        
        return results
    
    async def search_threat_actor(self, actor_name: str) -> Dict:
        """Search for infrastructure operated by threat actor"""
        
        results = {
            "known_ips": [],
            "known_domains": [],
            "malware_samples": [],
            "recent_activity": [],
        }
        
        # Would search threat intel feeds for known infrastructure
        
        return results
    
    async def search_vulnerability(self, cve_id: str) -> List[DiscoveredAsset]:
        """Find all exposed systems vulnerable to CVE"""
        
        vulnerable = []
        
        for asset in self.discovered_assets.values():
            for vuln in asset.vulnerabilities:
                if cve_id in vuln.get('cve', ''):
                    vulnerable.append(asset)
                    break
        
        return vulnerable
    
    async def search_malware(self, malware_name: str) -> Dict:
        """Search for systems infected with malware"""
        
        results = {
            "infected_systems": [],
            "c2_servers": [],
            "samples": [],
            "campaigns": [],
        }
        
        # Would search:
        # - AbuseIPDB for malware-infected IPs
        # - MalwareBazaar for samples
        # - Threat feeds for campaigns
        
        return results
    
    async def _create_snapshot(self) -> GlobalRadarSnapshot:
        """Create snapshot of global threat landscape"""
        
        exposed = sum(1 for a in self.discovered_assets.values() if a.is_exposed)
        critical = sum(1 for a in self.discovered_assets.values()
                      if any(v.get('severity') == 'critical' 
                             for v in a.vulnerabilities))
        
        # Aggregate statistics
        threat_map = {}
        for asset in self.discovered_assets.values():
            country = asset.country
            threat_map[country] = threat_map.get(country, 0) + 1
        
        snapshot = GlobalRadarSnapshot(
            snapshot_id=hashlib.sha256(str(datetime.utcnow()).encode()).hexdigest(),
            timestamp=datetime.utcnow(),
            total_assets_discovered=len(self.discovered_assets),
            exposed_assets=exposed,
            critical_vulnerabilities=critical,
            malicious_ips=len([a for a in self.discovered_assets.values() 
                              if any('malware' in str(v) for v in a.vulnerabilities)]),
            known_breaches=len(self.breach_datasets),
            active_campaigns=0,  # Would be calculated
            top_threat_actors=[],  # Would be aggregated
            top_malware_families=[],  # Would be aggregated
            top_vulnerable_services=self._get_top_services(),
            top_targeted_sectors=self._get_top_sectors(),
            threat_map=threat_map,
            assets=list(self.discovered_assets.values()),
            breaches=list(self.breach_datasets.values()),
        )
        
        return snapshot
    
    def _get_top_services(self, limit: int = 5) -> List[str]:
        """Get most commonly exposed services"""
        services = {}
        for asset in self.discovered_assets.values():
            services[asset.service] = services.get(asset.service, 0) + 1
        
        return sorted(services.items(), key=lambda x: x[1], reverse=True)[:limit]
    
    def _get_top_sectors(self, limit: int = 5) -> List[str]:
        """Get most targeted sectors"""
        # Would map organizations to sectors
        return ["Technology", "Finance", "Healthcare", "Energy", "Manufacturing"]
    
    async def _store_snapshot(self, snapshot: GlobalRadarSnapshot):
        """Store snapshot for historical analysis"""
        if self.redis:
            key = f"radar_snapshot:{snapshot.snapshot_id}"
            await self.redis.set(key, json.dumps(asdict(snapshot), default=str))
    
    async def _process_snapshot(self, snapshot: GlobalRadarSnapshot):
        """Process snapshot for alerts and analysis"""
        
        # Alert on critical changes
        if snapshot.critical_vulnerabilities > 100:
            print(f"ALERT: {snapshot.critical_vulnerabilities} critical vulnerabilities detected")
        
        if snapshot.exposed_assets > 1000:
            print(f"ALERT: {snapshot.exposed_assets} exposed assets detected")


# Async endpoint helpers
async def search_organization_endpoint(radar: SovereignRadar, org_name: str) -> Dict:
    """FastAPI endpoint to search for organization assets"""
    try:
        results = await radar.search_organization(org_name)
        return results
    except Exception as e:
        return {"error": str(e), "status": "failed"}


async def search_threat_actor_endpoint(radar: SovereignRadar, actor_name: str) -> Dict:
    """FastAPI endpoint to search for threat actor infrastructure"""
    try:
        results = await radar.search_threat_actor(actor_name)
        return results
    except Exception as e:
        return {"error": str(e), "status": "failed"}


async def search_vulnerability_endpoint(radar: SovereignRadar, cve_id: str) -> Dict:
    """FastAPI endpoint to find vulnerable systems"""
    try:
        vulnerable = await radar.search_vulnerability(cve_id)
        return {
            "cve": cve_id,
            "vulnerable_systems": [asdict(a) for a in vulnerable]
        }
    except Exception as e:
        return {"error": str(e), "status": "failed"}


async def search_malware_endpoint(radar: SovereignRadar, malware_name: str) -> Dict:
    """FastAPI endpoint to search malware infrastructure"""
    try:
        results = await radar.search_malware(malware_name)
        return results
    except Exception as e:
        return {"error": str(e), "status": "failed"}


async def get_radar_snapshot_endpoint(radar: SovereignRadar) -> Dict:
    """FastAPI endpoint to get current radar snapshot"""
    try:
        snapshot = await radar.perform_global_scan()
        return asdict(snapshot)
    except Exception as e:
        return {"error": str(e), "status": "failed"}
