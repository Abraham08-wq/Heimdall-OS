from typing import Dict, Any, List
import logging
from app.infrastructure.cache.redis_manager import redis_cache

logger = logging.getLogger(__name__)


class ABACEvaluator:
    """
    Attribute-Based Access Control Evaluator (Pillar 2).
    Evaluates permissions dynamically based on user attributes, tenant constraints, and asset severity.
    """

    def __init__(self):
        # Base clearance mappings
        self.clearance_levels = {
            "viewer": 1,
            "analyst": 2,
            "operator": 3,
            "admin": 4
        }

        # Explicit matrix of valid actions allowed in the sovereign platform
        self.valid_platform_actions = {
            "view_topology", "view_metrics", "execute_payload",
            "quarantine_node", "trigger_emulation"
        }

    async def evaluate_access(
            self,
            user_id: str,
            tenant_id: str,
            role: str,
            action: str,
            resource_attributes: Dict[str, Any]
    ) -> bool:
        """
        Dynamically calculates access utilizing Redis cache for sub-10ms response times.
        """
        # --- Strict Zero-Trust Check: Fail Closed on Unregistered Actions ---
        if action not in self.valid_platform_actions:
            logger.warning(f"ABAC Block: Unrecognized operation action '{action}' requested by user {user_id}")
            return False

        # 1. Check Redis Cache for pre-calculated policy state
        cached_policy = await redis_cache.get_abac_policy(user_id, tenant_id)
        if cached_policy and f"{action}:{resource_attributes.get('type')}" in cached_policy.get("allowed_actions", []):
            return True

        # 2. Perform Dynamic Evaluation if Cache Miss
        user_clearance = self.clearance_levels.get(role, 0)
        required_clearance = resource_attributes.get("required_clearance", 1)

        # Rule 1: Tenant Isolation (Hard Boundary)
        if resource_attributes.get("tenant_id") != tenant_id:
            logger.warning(f"ABAC Block: Cross-tenant access attempt by user {user_id}")
            return False

        # Rule 2: Clearance Level
        if user_clearance < required_clearance:
            logger.warning(
                f"ABAC Block: Insufficient clearance level for user {user_id}. Has {user_clearance}, needs {required_clearance}")
            return False

        # Rule 3: Operational Severity Constraints
        # E.g., only 'operator' or higher can execute actions on 'critical' severity assets
        if action in ["execute_payload", "quarantine_node"]:
            if resource_attributes.get("severity") == "critical" and user_clearance < 3:
                logger.warning(
                    f"ABAC Block: Critical mitigation tool access denied for insufficient operator level role: {role}")
                return False

        # Access Granted explicitly under safety boundaries
        return True


abac_evaluator = ABACEvaluator()
