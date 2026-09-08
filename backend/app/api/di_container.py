"""
Dependency Injection Container - Intelligence & Defense Services

This module configures singleton instances for:
- Attribution Engine (threat actor correlation)
- Microsegmentation Service (network isolation)
- Distributed Request Orchestrator (resilient proxy mesh)
- Connected to Neo4j, Postgres, and Redis

Org_id isolation is enforced at the service layer through:
- Graph scoped queries via graph_db.with_scope()
- Query filtering for tenant/org isolation
- Context propagation through async context vars
"""

from typing import Optional, Dict, Any
import logging
from contextvars import ContextVar

from app.services.intel.attribution import AttributionEngine
from app.services.intel.request_orchestrator import DistributedRequestOrchestrator
from app.modules.defensive.services.microsegmentation import MicrosegmentationService
from app.modules.defensive.services.containment import ContainmentEngine
from app.services.connectors import ConnectorService
from app.services.enrichment_engine import EnrichmentEngine

logger = logging.getLogger(__name__)

# ─── Context Variables for Org/Tenant Isolation ───────────────────────────────

# Store the current org_id for multi-tenant queries
_current_org_id: ContextVar[str] = ContextVar("current_org_id", default="default")

# Store the current user_id for audit and UEBA
_current_user_id: ContextVar[str] = ContextVar("current_user_id", default="system")


def set_org_context(org_id: str):
    """Set the current organization context for this async task."""
    token = _current_org_id.set(org_id)
    logger.debug(f"[DI] Org context set to: {org_id}")
    return token


def get_org_context() -> str:
    """Retrieve the current organization context."""
    return _current_org_id.get()


def set_user_context(user_id: str):
    """Set the current user context for this async task."""
    token = _current_user_id.set(user_id)
    logger.debug(f"[DI] User context set to: {user_id}")
    return token


def get_user_context() -> str:
    """Retrieve the current user context."""
    return _current_user_id.get()


# ─── Service Singletons ────────────────────────────────────────────────────────

class IntelligenceServices:
    """
    Singleton container for all intelligence and defense services.
    Initialized once at startup, reused across all requests.
    """

    _instance: Optional["IntelligenceServices"] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        logger.info("[DI] Initializing IntelligenceServices container...")

        # ─── Intelligence & Enrichment ─────────────────────────────────────
        self.connector_service = ConnectorService()
        self.enrichment_engine = EnrichmentEngine()

        # ─── Attribution Engine (Threat Actor Correlation) ─────────────────
        self.attribution_engine = AttributionEngine(
            connector=self.connector_service,
            enrichment=self.enrichment_engine
        )
        logger.info("[DI] ✓ Attribution Engine initialized")

        # ─── Containment & Microsegmentation ───────────────────────────────
        self.containment_engine = ContainmentEngine()
        self.microsegmentation_service = MicrosegmentationService(
            containment=self.containment_engine
        )
        logger.info("[DI] ✓ Microsegmentation Service initialized")

        # ─── Distributed Request Orchestrator (Proxy Mesh) ──────────────────
        self.request_orchestrator = DistributedRequestOrchestrator()
        logger.info("[DI] ✓ Request Orchestrator initialized")

        IntelligenceServices._initialized = True
        logger.info("[DI] IntelligenceServices container ready")

    @classmethod
    def get_instance(cls) -> "IntelligenceServices":
        """Retrieve the singleton instance."""
        if cls._instance is None:
            cls()
        return cls._instance


# ─── Dependency Providers for FastAPI ─────────────────────────────────────────

def get_attribution_engine() -> AttributionEngine:
    """FastAPI dependency to inject AttributionEngine with org isolation."""
    engine = IntelligenceServices.get_instance().attribution_engine
    return engine


def get_microsegmentation_service() -> MicrosegmentationService:
    """FastAPI dependency to inject MicrosegmentationService with org isolation."""
    service = IntelligenceServices.get_instance().microsegmentation_service
    return service


def get_request_orchestrator() -> DistributedRequestOrchestrator:
    """FastAPI dependency to inject DistributedRequestOrchestrator."""
    return IntelligenceServices.get_instance().request_orchestrator


def get_containment_engine() -> ContainmentEngine:
    """FastAPI dependency to inject ContainmentEngine."""
    return IntelligenceServices.get_instance().containment_engine


def get_connector_service() -> ConnectorService:
    """FastAPI dependency to inject ConnectorService."""
    return IntelligenceServices.get_instance().connector_service


def get_enrichment_engine() -> EnrichmentEngine:
    """FastAPI dependency to inject EnrichmentEngine."""
    return IntelligenceServices.get_instance().enrichment_engine


# ─── Initialization Hook for Startup ───────────────────────────────────────────

async def initialize_di_container():
    """
    Call this in FastAPI lifespan startup to initialize all singletons.
    
    Example:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            await initialize_di_container()
            yield
            # Shutdown tasks...
    """
    logger.info("[DI] Starting dependency injection container initialization...")
    
    # Force singleton creation
    services = IntelligenceServices.get_instance()
    
    logger.info("[DI] ✓ All services initialized and ready for injection")
    return services


# ─── Context Manager for Org Scoped Operations ─────────────────────────────────

class OrgScopedContext:
    """
    Context manager to set org_id for a block of async operations.
    
    Usage:
        async with OrgScopedContext("org-123"):
            dossier = await attribution_engine.correlate_indicators(...)
            # All queries are scoped to org-123
    """

    def __init__(self, org_id: str, user_id: Optional[str] = None):
        self.org_id = org_id
        self.user_id = user_id or "system"
        self.org_token = None
        self.user_token = None

    async def __aenter__(self):
        self.org_token = set_org_context(self.org_id)
        self.user_token = set_user_context(self.user_id)
        logger.debug(f"[DI] Entered org scope: {self.org_id} / {self.user_id}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.org_token:
            _current_org_id.reset(self.org_token)
        if self.user_token:
            _current_user_id.reset(self.user_token)
        logger.debug(f"[DI] Exited org scope")
        return False
