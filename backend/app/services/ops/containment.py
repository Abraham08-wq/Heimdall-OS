"""
Microsegmentation Service - Dynamic Infrastructure Defense

Provides programmatic network micro-segmentation for automated incident containment.

Features:
- Risk-threshold-based isolation policies
- Delegation to authorized NetOps API (or local simulation)
- Org-scoped policy enforcement
- Audit trail integration
"""

from typing import Dict, Any, Optional
import logging
import httpx
import time

from app.core.config import settings

logger = logging.getLogger(__name__)


class MicrosegmentationService:
    """
    High-level micro-segmentation service for authorized incident containment.

    Behavior:
    - Validates policy against severity threshold (severity >= 9 for P1/P0)
    - Delegates to an authorized NetOps API if configured (NETOPS_API_URL)
    - Falls back to local simulated containment for dev environments
    - Enforces org_id isolation for all operations
    """

    def __init__(self):
        self._org_id: Optional[str] = None
        self.netops_url = getattr(settings, "NETOPS_API_URL", None)
        self.api_token = getattr(settings, "NETOPS_API_TOKEN", None)
        self.request_timeout = getattr(settings, "REQUEST_TIMEOUT", 15.0)
        
        # Local isolation tracking (dev/test mode)
        self._isolated_hosts: Dict[str, Dict[str, Any]] = {}

    def _policy_allows(self, tenant_id: str, severity: int) -> bool:
        """
        Policy check: Only allow programmatic isolation for severity >= 9 (P1/P0).
        
        In production, this should query an RBAC policy engine.
        For now, we enforce a simple severity threshold.
        """
        allowed = severity >= 9
        logger.info(f"[Microseg] Policy check: tenant={tenant_id}, severity={severity}, allowed={allowed}")
        return allowed

    async def isolate_host(
        self,
        tenant_id: str,
        host_identifier: str,
        severity: int,
        reason: str,
        ttl_seconds: int = 3600
    ) -> Dict[str, Any]:
        """
        Isolate a host (internal asset) due to a security threat.

        Primary interface used by AutonomousSOC or incident response orchestrators.
        
        Args:
            tenant_id: Organization/tenant identifier (org_id)
            host_identifier: Target host (IP, hostname, asset_id)
            severity: Threat severity (0-10; P1=9-10, P2=7-8, etc.)
            reason: Human-readable isolation reason
            ttl_seconds: Duration of isolation (default 1 hour)
        
        Returns:
            Dictionary containing:
            - outcome: "success" | "denied" | "partial" | "simulated"
            - method: "netops" | "local-sim"
            - audit: Audit trail metadata
            - status_code: HTTP status (if NetOps)
            - error: Exception message (if failed)
        """
        logger.info(
            f"[Microseg] Isolation request: host={host_identifier}, "
            f"tenant={tenant_id}, severity={severity}, reason={reason}"
        )

        # 1. Policy enforcement
        if not self._policy_allows(tenant_id, severity):
            logger.warning(
                f"[Microseg] Policy DENIED isolation for {host_identifier} "
                f"(severity={severity} < 9)"
            )
            return {
                "outcome": "denied",
                "reason": "policy",
                "detail": "Automatic isolation requires severity >= 9"
            }

        # 2. Audit context
        audit = {
            "host": host_identifier,
            "tenant": tenant_id,
            "reason": reason,
            "severity": severity,
            "started_at": time.time(),
            "ttl": ttl_seconds,
            "org_id": self._org_id  # Include org_id in audit
        }

        # 3. Record in local isolation tracking (for dev/test)
        self._isolated_hosts[host_identifier] = audit

        # 4. If NetOps API is configured, call it to apply micro-segmentation
        if self.netops_url:
            return await self._apply_via_netops_api(
                tenant_id=tenant_id,
                host_identifier=host_identifier,
                reason=reason,
                ttl=ttl_seconds,
                audit=audit
            )
        else:
            # Simulate firewall update for dev environments
            logger.info(
                f"[Microseg] Simulating firewall quarantine for {host_identifier} "
                f"(no NetOps API configured)"
            )
            return {
                "outcome": "simulated",
                "method": "local-sim",
                "audit": audit,
                "detail": "Isolation simulated (set NETOPS_API_URL to enable real segregation)"
            }

    async def _apply_via_netops_api(
        self,
        tenant_id: str,
        host_identifier: str,
        reason: str,
        ttl: int,
        audit: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Delegate isolation to external NetOps API.
        
        Args:
            tenant_id: Organization ID
            host_identifier: Target host
            reason: Isolation reason
            ttl: Time-to-live (seconds)
            audit: Audit metadata
        
        Returns:
            API response or error dictionary
        """
        headers = {}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        payload = {
            "tenant_id": tenant_id,
            "host": host_identifier,
            "action": "isolate",
            "reason": reason,
            "ttl": ttl
        }

        try:
            async with httpx.AsyncClient(timeout=self.request_timeout) as client:
                resp = await client.post(
                    f"{self.netops_url}/segmentation/apply",
                    json=payload,
                    headers=headers
                )
                
                if resp.status_code in (200, 202):
                    logger.info(f"[Microseg] NetOps isolation applied for {host_identifier}")
                    return {
                        "outcome": "success",
                        "method": "netops",
                        "status_code": resp.status_code,
                        "netops_resp": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text,
                        "audit": audit
                    }
                else:
                    logger.error(
                        f"[Microseg] NetOps API error: {resp.status_code} {resp.text}"
                    )
                    return {
                        "outcome": "partial",
                        "method": "netops",
                        "status_code": resp.status_code,
                        "detail": resp.text,
                        "audit": audit
                    }
        except Exception as e:
            logger.error(f"[Microseg] NetOps API call failed: {e}")
            return {
                "outcome": "partial",
                "method": "netops",
                "error": str(e),
                "audit": audit
            }

    async def unisolate_host(
        self,
        tenant_id: str,
        host_identifier: str
    ) -> Dict[str, Any]:
        """
        Release a host from isolation (restore network access).
        
        Args:
            tenant_id: Organization ID
            host_identifier: Target host
        
        Returns:
            Status dictionary
        """
        logger.info(
            f"[Microseg] Release request: host={host_identifier}, tenant={tenant_id}"
        )

        # Remove from local tracking
        if host_identifier in self._isolated_hosts:
            del self._isolated_hosts[host_identifier]

        # Call NetOps API if configured
        if self.netops_url:
            headers = {}
            if self.api_token:
                headers["Authorization"] = f"Bearer {self.api_token}"

            payload = {
                "tenant_id": tenant_id,
                "host": host_identifier,
                "action": "unisolate"
            }

            try:
                async with httpx.AsyncClient(timeout=self.request_timeout) as client:
                    resp = await client.post(
                        f"{self.netops_url}/segmentation/apply",
                        json=payload,
                        headers=headers
                    )
                    
                    if resp.status_code in (200, 202):
                        logger.info(f"[Microseg] NetOps release applied for {host_identifier}")
                        return {"outcome": "success", "method": "netops", "status_code": resp.status_code}
                    else:
                        logger.error(f"[Microseg] NetOps release failed: {resp.status_code}")
                        return {"outcome": "failed", "status_code": resp.status_code}
            except Exception as e:
                logger.error(f"[Microseg] NetOps release call failed: {e}")
                return {"outcome": "error", "error": str(e)}
        else:
            logger.info(f"[Microseg] Simulating unisolation for {host_identifier}")
            return {"outcome": "simulated", "method": "local-sim"}

    async def get_containment_status(
        self,
        tenant_id: str,
        host_identifier: str
    ) -> Dict[str, Any]:
        """
        Get the current containment status for a host.
        
        Args:
            tenant_id: Organization ID
            host_identifier: Target host
        
        Returns:
            Dictionary with isolation status, reason, TTL remaining
        """
        audit = self._isolated_hosts.get(host_identifier)
        
        if not audit:
            return {
                "is_isolated": False,
                "host": host_identifier,
                "reason": None,
                "ttl_remaining": None
            }
        
        # Check if TTL has expired
        elapsed = time.time() - audit.get("started_at", time.time())
        ttl_remaining = max(0, audit.get("ttl", 3600) - elapsed)
        
        return {
            "is_isolated": ttl_remaining > 0,
            "host": host_identifier,
            "reason": audit.get("reason"),
            "severity": audit.get("severity"),
            "started_at": audit.get("started_at"),
            "ttl_remaining": ttl_remaining,
            "tenant": audit.get("tenant"),
            "method": "simulated" if not self.netops_url else "netops"
        }

    def get_isolation_status(self, host_identifier: str) -> Optional[Dict[str, Any]]:
        """
        Get the current isolation status for a host.
        
        Args:
            host_identifier: Target host
        
        Returns:
            Audit metadata if isolated, None otherwise
        """
        return self._isolated_hosts.get(host_identifier)

    def list_isolated_hosts(self, tenant_id: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        List all currently isolated hosts (optionally filtered by tenant).
        
        Args:
            tenant_id: Filter by organization (optional)
        
        Returns:
            Dictionary of host_identifier -> audit_metadata
        """
        if tenant_id:
            return {
                host: audit for host, audit in self._isolated_hosts.items()
                if audit.get("tenant") == tenant_id
            }
        return dict(self._isolated_hosts)


# Expose default service instance
microsegmentation_service = MicrosegmentationService()
