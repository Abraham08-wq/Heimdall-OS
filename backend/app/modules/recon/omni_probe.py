import asyncio
import socket
from typing import Dict, Any, List
import uuid

class OmniProbeEngine:
    """
    Tier 2: The Synapse - The Omni-Probe (Absolute Reconnaissance)
    Hyper-concurrent scanning capability utilizing Python async streams.
    """
    
    # Common ports + Critical Database & Infrastructure Ports
    TOP_PORTS = [
        # Standard Web/Mail/Infra
        21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445,
        # Databases & Big Data
        1433,  # MSSQL
        1521,  # Oracle
        3306,  # MySQL
        5432,  # PostgreSQL
        6379,  # Redis
        7474, 7687,  # Neo4j
        9200, 9300,  # Elasticsearch
        27017, # MongoDB
        # Dev & App Servers
        3000, 8000, 8080, 8443, 8081,
        # Remote Admin
        3389, 5900 # RDP, VNC
    ]

    async def _grab_banner(self, reader, writer, timeout: float = 1.0) -> str | None:
        """Attempts to read the service banner (e.g., SSH-2.0, HTTP/1.x, Redis ready)."""
        try:
            # Send a generic probe that might coax a response from HTTP or generic TCP services
            writer.write(b"GET / HTTP/1.1\r\nHost: omni-probe\r\n\r\n")
            await writer.drain()
            
            # Non-blocking read
            banner = await asyncio.wait_for(reader.read(1024), timeout=timeout)
            if banner:
                return banner.decode('utf-8', errors='ignore').split('\\n')[0].strip()
            return None
        except Exception:
            # Silent fail for banner grabbing to keep the scan fast
            return None

    async def _scan_port(self, ip: str, port: int, timeout: float = 1.0) -> Dict[str, Any] | None:
        """Asynchronously attempts a TCP connection to a specific port and grabs the banner."""
        try:
            # Use asyncio to establish a non-blocking TCP connection
            fut = asyncio.open_connection(ip, port)
            reader, writer = await asyncio.wait_for(fut, timeout=timeout)
            
            # Connection successful - attempt banner grab
            banner = await self._grab_banner(reader, writer, timeout=0.5)
            
            # If successful, close the connection cleanly
            writer.close()
            await writer.wait_closed()
            
            return {
                "port": port,
                "banner": banner or "Open (No Banner)"
            }
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            return None

    async def _scan_host(self, ip: str) -> Dict[str, Any]:
        """Scans the top ports for a single host concurrently."""
        tasks = [self._scan_port(ip, port) for port in self.TOP_PORTS]
        
        # Run all port checks simultaneously for maximum speed
        results = await asyncio.gather(*tasks)
        
        # Filter out failed connections (None)
        discovered_services = [res for res in results if res is not None]
        
        # Provide structured data for the AI Swarms
        open_ports = [srv["port"] for srv in discovered_services]
        services = {srv["port"]: srv["banner"] for srv in discovered_services}
        
        return {
            "ip": ip,
            "open_ports": open_ports,
            "services": services,
            "status": "up" if open_ports else "down"
        }

    async def launch_mass_scan(self, target_cidr: str, scan_type: str = "FULL_SPECTRUM") -> Dict[str, Any]:
        """
        Executes the concurrent reconnaissance engine against the targets.
        """
        scan_id = f"PROBE-{uuid.uuid4().hex[:8].upper()}"
        print(f"[OMNI-PROBE] Initiating {scan_type} scan across: {target_cidr} (ID: {scan_id})")
        
        target_ips = []
        import ipaddress
        try:
            # Safely expand CIDR or single IP. 
            net = ipaddress.ip_network(target_cidr, strict=False)
            
            # Handle deep scanning configurations
            max_hosts = 254
            if scan_type == "AGGRESSIVE":
                max_hosts = 1024 # /22 scanning
            elif scan_type == "OMNICIDE":
                max_hosts = 65536 # /16 scanning (extreme caution needed)

            target_ips = [str(ip) for ip in net.hosts()][:max_hosts]
            
            # If it was a single IP (/32 or just IP string), hosts() might be empty
            if not target_ips:
                 target_ips = [str(net.network_address)]
        except ValueError:
            print(f"[OMNI-PROBE] Error parsing CIDR {target_cidr}. Falling back to localhost.")
            target_ips = ["127.0.0.1"]

        # Launch host scans concurrently
        print(f"[*] Spawning {len(target_ips) * len(self.TOP_PORTS)} asynchronous probes with deep banner extraction...")
        host_tasks = [self._scan_host(ip) for ip in target_ips]
        raw_results = await asyncio.gather(*host_tasks)
        
        # Filter to only show active hosts
        active_hosts = [res for res in raw_results if res["status"] == "up"]
            
        print(f"[OMNI-PROBE] Scan {scan_id} absolute. {len(active_hosts)} active hosts identified with intelligence packages extracted.")
        
        return {
            "scan_id": scan_id,
            "target": target_cidr,
            "status": "COMPLETED",
            "scan_type": scan_type,
            "hosts_discovered": len(active_hosts),
            "telemetry": active_hosts
        }

omni_probe = OmniProbeEngine()
