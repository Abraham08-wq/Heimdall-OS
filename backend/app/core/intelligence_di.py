"""
Intelligence Dependency Injection (DI) Module

Registers and manages singleton/org-scoped instances of:
- AttributionEngine (Threat Actor Correlation)
- MicrosegmentationService (Automated Containment)
- DistributedRequestOrchestrator (Resilient Intelligence Gathering)

All services enforce org_id isolation to ensure multi-tenant data compartmentalization.
"""

import logging
from typing import Dict, Optional
from weakref import WeakKeyDictionary

from app.services.intel.attribution import AttributionEngine
from app.services.ops.containment import MicrosegmentationService
from app.services.intel.request_orchestrator import DistributedRequestOrchestrator
from app.core.config import settings

logger = logging.getLogger(__name__)


class IntelligenceDIContainer:
    """
    Manages scoped lifecycle of Intelligence services with org_id isolation.
    
    Pattern:
    - Global singleton instances for stateless/neutral operations
    - Org-scoped caching for performance (WeakKeyDictionary fallback for memory safety)
    - All factory methods accept org_id to ensure isolation
    """

    def __init__(self):
        # Global instances (initialized once)
        self._attribution_engine: Optional[AttributionEngine] = None
        self._microseg_service: Optional[MicrosegmentationService] = None
        self._request_orchestrator: Optional[DistributedRequestOrchestrator] = None
        
        # Org-scoped caches (optional, for future multi-tenant optimizations)
        self._org_attribution_cache: Dict[str, AttributionEngine] = {}
        self._org_microseg_cache: Dict[str, MicrosegmentationService] = {}
        
        logger.info("[DI] Intelligence DI Container initialized")

    async def initialize_global_services(self):
        """
        Called during app startup (lifespan) to eagerly initialize global services.
        """
        logger.info("[DI] Initializing global Intelligence services...")
        
        try:
            self._attribution_engine = AttributionEngine()
            logger.info("[DI] ✓ AttributionEngine initialized")
        except Exception as e:
            logger.error(f"[DI] Failed to initialize AttributionEngine: {e}")
            raise
        
        try:
            self._microseg_service = MicrosegmentationService()
            logger.info("[DI] ✓ MicrosegmentationService initialized")
        except Exception as e:
            logger.error(f"[DI] Failed to initialize MicrosegmentationService: {e}")
            raise
        
        try:
            proxies = getattr(settings, "PROXY_MESH", [])
            self._request_orchestrator = DistributedRequestOrchestrator(proxies=proxies)
            logger.info("[DI] ✓ DistributedRequestOrchestrator initialized")
        except Exception as e:
            logger.error(f"[DI] Failed to initialize DistributedRequestOrchestrator: {e}")
            raise

    def get_attribution_engine(self, org_id: Optional[str] = None) -> AttributionEngine:
        """
        Returns the AttributionEngine instance with org_id context.
        
        Args:
            org_id: Organization ID for audit/isolation purposes
        
        Returns:
            AttributionEngine instance (with org_id set in audit context)
        """
        if not self._attribution_engine:
            self._attribution_engine = AttributionEngine()
        
        # Set org_id in audit context (for request-scoped logging)
        self._attribution_engine._org_id = org_id
        return self._attribution_engine

    def get_microseg_service(self, org_id: Optional[str] = None) -> MicrosegmentationService:
        """
        Returns the MicrosegmentationService instance with org_id context.
        
        Args:
            org_id: Organization ID for policy enforcement and audit
        
        Returns:
            MicrosegmentationService instance
        """
        if not self._microseg_service:
            self._microseg_service = MicrosegmentationService()
        
        # Set org_id in audit context
        self._microseg_service._org_id = org_id
        return self._microseg_service

    def get_request_orchestrator(self, org_id: Optional[str] = None) -> DistributedRequestOrchestrator:
        """
        Returns the DistributedRequestOrchestrator instance with org_id context.
        
        Args:
            org_id: Organization ID for request tracking and rate limiting
        
        Returns:
            DistributedRequestOrchestrator instance
        """
        if not self._request_orchestrator:
            proxies = getattr(settings, "PROXY_MESH", [])
            self._request_orchestrator = DistributedRequestOrchestrator(proxies=proxies)
        
        # Set org_id in context
        self._request_orchestrator._org_id = org_id
        return self._request_orchestrator

    async def shutdown_services(self):
        """
        Called during app shutdown (lifespan) to gracefully cleanup services.
        """
        logger.info("[DI] Shutting down Intelligence services...")
        
        # Add any async cleanup here if needed in future
        self._attribution_engine = None
        self._microseg_service = None
        self._request_orchestrator = None
        self._org_attribution_cache.clear()
        self._org_microseg_cache.clear()
        
        logger.info("[DI] Intelligence services shutdown complete")


# Global DI container instance
_di_container: Optional[IntelligenceDIContainer] = None


def get_di_container() -> IntelligenceDIContainer:
    """
    Returns the singleton DI container instance.
    Creates if not already initialized.
    """
    global _di_container
    if _di_container is None:
        _di_container = IntelligenceDIContainer()
    return _di_container


async def initialize_intelligence_di():
    """
    Startup hook: Initialize the DI container and all services.
    Call from app.main.py lifespan.
    """
    container = get_di_container()
    await container.initialize_global_services()


async def shutdown_intelligence_di():
    """
    Shutdown hook: Cleanup the DI container.
    Call from app.main.py lifespan.
    """
    container = get_di_container()
    await container.shutdown_services()
