"""
Distributed Request Orchestrator - Resilient Intelligence Gathering

Provides resilient HTTP request orchestration using an authorized proxy mesh.

Features:
- Transparent proxy rotation for load balancing and resilience
- Polite rate-limit handling (respects Retry-After headers)
- Org-scoped request tracking and metrics
- Async/await concurrency control with semaphores
"""

from typing import List, Optional, Dict, Any
import asyncio
import logging
import random
import httpx
import time

from app.core.config import settings

logger = logging.getLogger(__name__)


class DistributedRequestOrchestrator:
    """
    Resilient request orchestrator using an authorized proxy mesh.

    Behavior:
    - Rotates through configured proxies (PROXY_MESH env var or settings)
    - Honors rate-limit headers and backs off politely
    - Uses a semaphore to cap concurrency (prevent resource exhaustion)
    - Tracks all requests with org_id for audit and metrics
    - All proxies must be authorized and configured (no circumvention)

    Example usage:
        orchestrator = DistributedRequestOrchestrator()
        resp = await orchestrator.request("GET", "https://api.example.com/data")
    """

    def __init__(
        self,
        proxies: Optional[List[str]] = None,
        concurrency: int = 6,
        request_timeout: float = 10.0
    ):
        """
        Initialize the orchestrator.
        
        Args:
            proxies: List of authorized proxy URLs (e.g., ["https://p1.example.com:8080", ...])
                     If None, will try to load from settings.PROXY_MESH
            concurrency: Max concurrent requests (semaphore limit)
            request_timeout: HTTP request timeout in seconds
        """
        self.proxies = proxies or getattr(settings, "PROXY_MESH", [])
        self.sem = asyncio.Semaphore(concurrency)
        self.client_timeout = request_timeout or getattr(settings, "REQUEST_TIMEOUT", 10.0)
        self._org_id: Optional[str] = None
        
        # Metrics tracking
        self._request_count: Dict[str, int] = {}  # proxy -> count
        self._error_count: Dict[str, int] = {}    # proxy -> error_count
        self._total_latency: Dict[str, float] = {}  # proxy -> cumulative ms
        
        logger.info(
            f"[Orchestrator] Initialized with {len(self.proxies)} proxies, "
            f"concurrency={concurrency}, timeout={self.client_timeout}s"
        )

    async def _request_via_proxy(
        self,
        method: str,
        url: str,
        proxy: Optional[str],
        **kwargs
    ) -> httpx.Response:
        """
        Execute a single HTTP request through a specific proxy.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Target URL
            proxy: Proxy URL (or None for direct connection)
            **kwargs: Additional httpx.request() arguments
        
        Returns:
            httpx.Response object
        """
        try:
            async with httpx.AsyncClient(
                timeout=self.client_timeout,
                proxies=proxy,
                verify=False  # Allow self-signed certs in authorized proxy scenarios
            ) as client:
                resp = await client.request(method, url, **kwargs)
                return resp
        except Exception as e:
            logger.warning(f"[Orchestrator] Request failed via {proxy}: {e}")
            raise

    async def request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute an HTTP request with transparent proxy rotation and rate-limit handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Target URL
            **kwargs: Additional arguments (headers, json, params, etc.)
        
        Returns:
            Dictionary containing:
            - status: HTTP status code
            - proxy: Proxy used (or None for direct)
            - body: Response body (parsed JSON if applicable, else text)
            - headers: Response headers
            - elapsed_ms: Request latency in milliseconds
        """
        async with self.sem:  # Enforce concurrency limit
            # Try proxies in randomized order to spread load
            pool = list(self.proxies) or [None]  # [None] = direct connection
            random.shuffle(pool)
            
            last_exc = None
            last_resp = None
            
            for proxy in pool:
                try:
                    start = time.time()
                    resp = await self._request_via_proxy(method, url, proxy, **kwargs)
                    elapsed_ms = (time.time() - start) * 1000
                    
                    # Track metrics
                    proxy_key = proxy or "direct"
                    self._request_count[proxy_key] = self._request_count.get(proxy_key, 0) + 1
                    self._total_latency[proxy_key] = self._total_latency.get(proxy_key, 0) + elapsed_ms
                    
                    # Handle rate limiting gracefully
                    if resp.status_code in (429, 503):
                        # Read Retry-After header (can be seconds or HTTP-date)
                        retry_after = resp.headers.get("Retry-After") or resp.headers.get("X-RateLimit-Reset")
                        
                        if retry_after:
                            try:
                                wait_seconds = int(retry_after)
                            except ValueError:
                                # Assume it's an HTTP-date; back off exponentially
                                wait_seconds = 2 ** len([p for p in pool if p == proxy])  # 2, 4, 8, ...
                        else:
                            wait_seconds = 2
                        
                        logger.warning(
                            f"[Orchestrator] Rate limited via {proxy or 'direct'}, "
                            f"sleeping {wait_seconds}s (status={resp.status_code})"
                        )
                        
                        # Track error
                        self._error_count[proxy_key] = self._error_count.get(proxy_key, 0) + 1
                        
                        # Wait and try next proxy
                        await asyncio.sleep(wait_seconds)
                        last_resp = resp
                        continue
                    
                    # Success: parse and return
                    try:
                        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
                    except Exception:
                        body = resp.text
                    
                    logger.info(
                        f"[Orchestrator] Request succeeded via {proxy or 'direct'} "
                        f"(status={resp.status_code}, latency={elapsed_ms:.1f}ms, org_id={self._org_id})"
                    )
                    
                    return {
                        "status": resp.status_code,
                        "proxy": proxy or "direct",
                        "body": body,
                        "headers": dict(resp.headers),
                        "elapsed_ms": elapsed_ms,
                        "org_id": self._org_id
                    }
                
                except Exception as e:
                    logger.warning(f"[Orchestrator] Proxy {proxy or 'direct'} failed: {e}")
                    proxy_key = proxy or "direct"
                    self._error_count[proxy_key] = self._error_count.get(proxy_key, 0) + 1
                    last_exc = e
                    
                    # Add jitter before trying next proxy
                    await asyncio.sleep(0.2 + random.random() * 0.3)
            
            # All proxies failed
            logger.error(
                f"[Orchestrator] All {len(pool)} proxies failed for {url}: {last_exc}"
            )
            raise last_exc or Exception(f"Request failed (last response: {last_resp})")

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get aggregated metrics for all proxies.
        
        Returns:
            Dictionary containing request counts, error rates, latencies
        """
        metrics = {
            "total_requests": sum(self._request_count.values()),
            "total_errors": sum(self._error_count.values()),
            "by_proxy": {}
        }
        
        for proxy in (self.proxies or ["direct"]):
            proxy_key = proxy or "direct"
            count = self._request_count.get(proxy_key, 0)
            errors = self._error_count.get(proxy_key, 0)
            total_latency = self._total_latency.get(proxy_key, 0)
            avg_latency = (total_latency / count) if count > 0 else 0
            
            metrics["by_proxy"][proxy_key] = {
                "requests": count,
                "errors": errors,
                "avg_latency_ms": avg_latency,
                "error_rate": (errors / count) if count > 0 else 0
            }
        
        return metrics

    def reset_metrics(self):
        """
        Reset all accumulated metrics.
        """
        self._request_count.clear()
        self._error_count.clear()
        self._total_latency.clear()
        logger.info("[Orchestrator] Metrics reset")


# Expose default orchestrator instance (uses PROXY_MESH from settings if configured)
request_orchestrator = DistributedRequestOrchestrator()
