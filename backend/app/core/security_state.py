"""
Global Security State Manager - SYSTEM_LOCKDOWN & JWT Revocation

Manages system-wide security states including emergency lockdown and token revocation.
Uses Redis for distributed state and fast access.
"""

import logging
import json
from typing import Optional, Set
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class LockdownLevel(str, Enum):
    """Security lockdown levels."""
    NORMAL = "normal"
    ALERT = "alert"
    LOCKDOWN = "lockdown"
    NUCLEAR_RESET = "nuclear_reset"


class SecurityStateManager:
    """
    Manages global security state including lockdown and JWT revocation.
    
    Features:
    - SYSTEM_LOCKDOWN toggle with immediate effect
    - JWT token blacklist (revocation)
    - Audit trail of security events
    - Integration with Redis for distribution
    """

    LOCKDOWN_KEY = "system:lockdown:state"
    REVOKED_TOKENS_KEY = "system:revoked_tokens"
    SECURITY_EVENTS_KEY = "system:security_events"

    def __init__(self, redis_client=None):
        """
        Initialize the security manager.
        
        Args:
            redis_client: Redis connection (optional, for distributed state)
        """
        self.redis = redis_client
        self.local_lockdown = False
        self.local_revoked_tokens: Set[str] = set()

    async def set_lockdown(self, enabled: bool, reason: str = "") -> None:
        """
        Enable or disable system-wide lockdown.
        
        Args:
            enabled: True to enable lockdown, False to disable
            reason: Reason for lockdown toggle
        """
        self.local_lockdown = enabled
        level = LockdownLevel.LOCKDOWN if enabled else LockdownLevel.NORMAL

        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "LOCKDOWN_TOGGLE",
            "enabled": enabled,
            "reason": reason,
            "level": level.value
        }

        if self.redis:
            try:
                # Set lockdown state in Redis
                await self.redis.set(
                    self.LOCKDOWN_KEY,
                    json.dumps({
                        "enabled": enabled,
                        "level": level.value,
                        "timestamp": event["timestamp"],
                        "reason": reason
                    }),
                    ex=86400  # 24 hour TTL
                )

                # Log event
                await self.redis.lpush(self.SECURITY_EVENTS_KEY, json.dumps(event))

                logger.critical(
                    f"🚨 SYSTEM LOCKDOWN {'ENABLED' if enabled else 'DISABLED'}: {reason}"
                )

            except Exception as e:
                logger.error(f"Failed to update Redis lockdown state: {e}")

        logger.info(f"🔒 Lockdown set to {level.value}: {reason}")

    async def get_lockdown_state(self) -> bool:
        """
        Get current lockdown state.
        
        Returns:
            True if lockdown is active
        """
        if self.redis:
            try:
                state = await self.redis.get(self.LOCKDOWN_KEY)
                if state:
                    data = json.loads(state)
                    return data.get("enabled", False)
            except Exception as e:
                logger.warning(f"Failed to read lockdown state from Redis: {e}")

        return self.local_lockdown

    async def revoke_token(self, token: str, reason: str = "") -> None:
        """
        Add a JWT token to the revocation blacklist.
        
        Args:
            token: JWT token to revoke
            reason: Reason for revocation (e.g., "LOCKDOWN", "USER_LOGOUT")
        """
        self.local_revoked_tokens.add(token)

        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "TOKEN_REVOKED",
            "token_hash": self._hash_token(token),
            "reason": reason
        }

        if self.redis:
            try:
                # Add to revocation set (24 hour TTL)
                await self.redis.setex(
                    f"{self.REVOKED_TOKENS_KEY}:{self._hash_token(token)}",
                    86400,  # 24 hours
                    json.dumps(event)
                )

                # Log event
                await self.redis.lpush(self.SECURITY_EVENTS_KEY, json.dumps(event))

                logger.warning(f"🛑 Token revoked: {reason}")

            except Exception as e:
                logger.error(f"Failed to revoke token in Redis: {e}")

    async def is_token_revoked(self, token: str) -> bool:
        """
        Check if a token has been revoked.
        
        Args:
            token: JWT token to check
            
        Returns:
            True if token is revoked
        """
        token_hash = self._hash_token(token)

        # Check local cache first
        if token_hash in self.local_revoked_tokens:
            return True

        # Check Redis
        if self.redis:
            try:
                revoked = await self.redis.exists(
                    f"{self.REVOKED_TOKENS_KEY}:{token_hash}"
                )
                if revoked:
                    self.local_revoked_tokens.add(token_hash)
                    return True
            except Exception as e:
                logger.warning(f"Failed to check token revocation in Redis: {e}")

        return False

    async def revoke_all_tokens(self, reason: str = "") -> None:
        """
        Revoke all active tokens (used during lockdown).
        
        Args:
            reason: Reason for global revocation
        """
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "GLOBAL_TOKEN_REVOCATION",
            "reason": reason
        }

        if self.redis:
            try:
                # Create a global revocation marker
                await self.redis.set(
                    "system:token_revocation_timestamp",
                    datetime.utcnow().isoformat(),
                    ex=86400  # 24 hours
                )

                # Log event
                await self.redis.lpush(self.SECURITY_EVENTS_KEY, json.dumps(event))

                logger.critical(f"🚨 ALL TOKENS REVOKED: {reason}")

            except Exception as e:
                logger.error(f"Failed to revoke all tokens: {e}")

        self.local_revoked_tokens.clear()

    async def get_security_events(self, limit: int = 100) -> list:
        """
        Retrieve recent security events.
        
        Args:
            limit: Maximum number of events to return
            
        Returns:
            List of security events
        """
        if not self.redis:
            return []

        try:
            events = await self.redis.lrange(self.SECURITY_EVENTS_KEY, 0, limit - 1)
            return [json.loads(e) for e in events]
        except Exception as e:
            logger.error(f"Failed to retrieve security events: {e}")
            return []

    async def clear_lockdown_and_revoke(self) -> None:
        """Nuclear option: Clear all state and revoke everything (SYSTEM RESET)."""
        await self.set_lockdown(False, "NUCLEAR_RESET")
        await self.revoke_all_tokens("NUCLEAR_RESET")

        if self.redis:
            try:
                # Clear all security-related keys
                keys = await self.redis.keys("system:*")
                if keys:
                    await self.redis.delete(*keys)
            except Exception as e:
                logger.error(f"Failed to clear system keys during reset: {e}")

        logger.critical("🔥 NUCLEAR RESET COMPLETE")

    @staticmethod
    def _hash_token(token: str) -> str:
        """Hash a token for storage (first 20 chars for partial visibility)."""
        import hashlib
        return hashlib.sha256(token.encode()).hexdigest()[:20]


# Global security state manager instance (will be initialized in main.py with Redis)
security_manager = SecurityStateManager()
