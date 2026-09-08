"""
containment.py — ProjectXY Phase 3 (UPGRADED): CGNAT-Aware Containment Engine
==============================================================================
CRITICAL SECURITY UPGRADE — East African Mobile Network Compliance
-------------------------------------------------------------------
The original version blocked malicious IP addresses directly in Redis. This is
CATASTROPHIC in mobile-heavy markets because Carrier-Grade NAT (CGNAT) means
that a single public IP (e.g., on Safaricom or Airtel) can represent tens of
thousands of simultaneous legitimate users sharing the same egress point.

Blocking an IP in a CGNAT environment = blocking an entire city block of users.

NEW CONTAINMENT PRIORITY ORDER (most precise → broadest impact):
  [1] Device Fingerprint Hash  — blocks the specific physical device
  [2] JWT Token ID (JTI)       — revokes a specific compromised session token
  [3] API Key Hash             — blocks a specific compromised integration key
  [4] User/Entity ID           — blocks the specific account identity
  [5] IP Address               — LAST RESORT ONLY, logged with CGNAT warning

All actions are written into Redis with a structured schema so edge proxies,
the API Gateway, and the SOAR playbook can all read the same truth store.

CBK Compliance: All containment events are logged with reason codes, duration,
                and entity resolution type.
"""
import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import redis

logger = logging.getLogger("projectxy.containment")


# ---------------------------------------------------------------------------
# Containment Identity Resolution Priority
# ---------------------------------------------------------------------------

class ContainmentScope(str, Enum):
    """
    Priority ladder for containment actions.
    Always use the most precise scope available to avoid CGNAT collateral damage.
    """
    DEVICE_FINGERPRINT = "device_fingerprint"  # Most precise — physical device
    JWT_JTI            = "jwt_jti"             # Session token revocation
    API_KEY_HASH       = "api_key_hash"        # Integration key block
    ENTITY_ID          = "entity_id"           # Account-level block
    IP_ADDRESS         = "ip_address"          # LAST RESORT — CGNAT risk!


# ---------------------------------------------------------------------------
# CGNAT Detection — known regional CGNAT prefixes for East Africa
# ---------------------------------------------------------------------------

# These are approximate shared egress ranges from major East African carriers.
# Traffic from these should NEVER be IP-blocked without extreme caution.
CGNAT_RISK_PREFIXES = (
    "100.",         # RFC 6598 CGNAT shared address space (10.64.0.0/10)
    "197.232.",     # Safaricom Kenya CGNAT block (approximate)
    "197.156.",     # Airtel Kenya CGNAT block (approximate)
    "41.90.",       # Telkom Kenya (approximate)
    "41.80.",       # KDN / Liquid Telecom
    "196.201.",     # Various East African ISPs
    "105.160.",     # MTN Africa shared blocks
    "154.65.",      # Airtel Africa shared blocks
)


def _is_cgnat_risk(ip_address: str) -> bool:
    """
    Heuristic check: is this IP likely a shared CGNAT address?
    Returns True if blocking would risk collateral damage to innocent users.
    """
    return any(ip_address.startswith(prefix) for prefix in CGNAT_RISK_PREFIXES)


# ---------------------------------------------------------------------------
# Containment Engine
# ---------------------------------------------------------------------------

class ContainmentEngine:
    """
    CGNAT-Aware Automated Containment Engine.

    Provides rapid isolation capabilities with a strict priority ladder that
    protects innocent users on shared mobile carrier NAT from collateral
    blocking. Always prefer device-level or token-level precision over IP blocks.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        try:
            self.redis = redis.from_url(redis_url, decode_responses=True)
            self.redis.ping()
            self.is_connected = True
            logger.info("[CONTAINMENT] Redis containment store connected.")
        except Exception as exc:
            self.is_connected = False
            logger.warning(f"[CONTAINMENT] Redis unavailable: {exc}. Containment actions degraded.")

    # ------------------------------------------------------------------ #
    # Core Isolation — CGNAT-safe primary containment method
    # ------------------------------------------------------------------ #

    def isolate_entity(
        self,
        entity_id: str,
        reason: str,
        duration_seconds: int = 3600,
        scope: ContainmentScope = ContainmentScope.ENTITY_ID,
        device_fingerprint: Optional[str] = None,
        jwt_jti: Optional[str] = None,
        api_key_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        CGNAT-aware entity isolation.

        Automatically selects the most precise available identifier before
        falling back to broader scopes. IP-level blocking is never called
        from this method — see block_ip_last_resort() for that.

        Args:
            entity_id:          User/account identifier (fallback).
            reason:             Human-readable reason for containment.
            duration_seconds:   Isolation TTL (default: 1 hour).
            scope:              Explicit scope override (auto-detected if not set).
            device_fingerprint: SHA-256 of device hardware+OS fingerprint.
            jwt_jti:            JWT token ID from `jti` claim.
            api_key_hash:       SHA-256 of the compromised API key.

        Returns:
            Containment result dict with scope, key, and duration.
        """
        if not self.is_connected:
            return {"status": "failed", "reason": "cache_unavailable"}

        # Auto-select most precise scope available
        resolved_scope, containment_key = self._resolve_containment_key(
            entity_id=entity_id,
            device_fingerprint=device_fingerprint,
            jwt_jti=jwt_jti,
            api_key_hash=api_key_hash,
            scope_override=scope,
        )

        redis_key = f"containment:isolated:{resolved_scope.value}:{containment_key}"

        if self.redis.exists(redis_key):
            return {
                "status": "already_isolated",
                "scope": resolved_scope.value,
                "key": containment_key,
            }

        payload = json.dumps({
            "reason": reason,
            "scope": resolved_scope.value,
            "entity_id": entity_id,
            "isolated_at": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": duration_seconds,
        })
        self.redis.setex(redis_key, duration_seconds, payload)

        logger.critical(
            f"[CONTAINMENT] ENACTED scope={resolved_scope.value} "
            f"key={containment_key[:16]}... entity={entity_id} "
            f"duration={duration_seconds}s reason={reason}"
        )

        return {
            "status": "isolated",
            "scope": resolved_scope.value,
            "key_prefix": containment_key[:8] + "...",
            "entity_id": entity_id,
            "duration_seconds": duration_seconds,
            "action": "shadow_sandbox",
            "cgnat_safe": True,
        }

    def check_isolation(
        self,
        entity_id: str,
        device_fingerprint: Optional[str] = None,
        jwt_jti: Optional[str] = None,
        api_key_hash: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> bool:
        """
        Check if an entity is contained via ANY scope.

        Checks all available identifiers from most-precise to least-precise.
        Returns True immediately on the first match found.
        """
        if not self.is_connected:
            return False

        checks: List[tuple] = []

        if device_fingerprint:
            fp_hash = hashlib.sha256(device_fingerprint.encode()).hexdigest()
            checks.append((ContainmentScope.DEVICE_FINGERPRINT, fp_hash))

        if jwt_jti:
            checks.append((ContainmentScope.JWT_JTI, jwt_jti))

        if api_key_hash:
            checks.append((ContainmentScope.API_KEY_HASH, api_key_hash))

        checks.append((ContainmentScope.ENTITY_ID, entity_id))

        if ip_address:
            checks.append((ContainmentScope.IP_ADDRESS, ip_address))

        for scope, key in checks:
            if self.redis.exists(f"containment:isolated:{scope.value}:{key}"):
                return True

        return False

    # ------------------------------------------------------------------ #
    # Device Fingerprint Containment (Highest Precision)
    # ------------------------------------------------------------------ #

    def contain_device(
        self,
        device_fingerprint: str,
        entity_id: str,
        reason: str,
        duration_seconds: int = 86400,
    ) -> Dict[str, Any]:
        """
        Block a specific physical device by its fingerprint hash.
        This is the most precise containment — zero CGNAT risk.
        
        Device fingerprint should be a stable hash of:
          - User-Agent string
          - Accept-Language header
          - Screen resolution / color depth (from mobile SDK)
          - Device manufacturer + model (from telco API enrichment)
        """
        fp_hash = hashlib.sha256(device_fingerprint.encode()).hexdigest()
        return self.isolate_entity(
            entity_id=entity_id,
            reason=reason,
            duration_seconds=duration_seconds,
            scope=ContainmentScope.DEVICE_FINGERPRINT,
            device_fingerprint=device_fingerprint,
        )

    # ------------------------------------------------------------------ #
    # Token-Level Actions (Session Precision)
    # ------------------------------------------------------------------ #

    def invalidate_token(self, token_jti: str, duration_seconds: int = 86400) -> None:
        """
        Revokes a specific JWT token by its JTI claim.
        
        This is CGNAT-safe — only the specific bearer session is terminated,
        not the entire IP range or even the user account.
        """
        if not self.is_connected:
            return
        key = f"containment:revoked_token:{ContainmentScope.JWT_JTI.value}:{token_jti}"
        self.redis.setex(key, duration_seconds, json.dumps({
            "revoked_at": datetime.now(timezone.utc).isoformat(),
            "reason": "token_invalidated_by_ai_soar",
        }))
        # Also maintain legacy key format for backward compatibility
        self.redis.setex(f"containment:revoked_token:{token_jti}", duration_seconds, "invalidated_by_ai")
        logger.warning(f"[CONTAINMENT] JWT JTI revoked: {token_jti[:16]}...")

    def is_token_revoked(self, token_jti: str) -> bool:
        """Check if a specific JWT token has been revoked."""
        if not self.is_connected:
            return False
        return (
            self.redis.exists(f"containment:revoked_token:{ContainmentScope.JWT_JTI.value}:{token_jti}") > 0
            or self.redis.exists(f"containment:revoked_token:{token_jti}") > 0
        )

    # ------------------------------------------------------------------ #
    # API Key Containment
    # ------------------------------------------------------------------ #

    def contain_api_key(
        self,
        api_key: str,
        entity_id: str,
        reason: str,
        duration_seconds: int = 86400,
    ) -> Dict[str, Any]:
        """
        Block a compromised API key by its hash.
        The raw API key is NEVER stored — only its SHA-256 hash.
        """
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        if not self.is_connected:
            return {"status": "failed", "reason": "cache_unavailable"}
        redis_key = f"containment:isolated:{ContainmentScope.API_KEY_HASH.value}:{key_hash}"
        self.redis.setex(redis_key, duration_seconds, json.dumps({
            "reason": reason,
            "entity_id": entity_id,
            "blocked_at": datetime.now(timezone.utc).isoformat(),
        }))
        logger.critical(f"[CONTAINMENT] API key hash blocked for entity={entity_id}")
        return {
            "status": "api_key_blocked",
            "key_hash_prefix": key_hash[:8] + "...",
            "entity_id": entity_id,
            "cgnat_safe": True,
        }

    # ------------------------------------------------------------------ #
    # IP Block — LAST RESORT with CGNAT circuit-breaker
    # ------------------------------------------------------------------ #

    def block_ip_last_resort(
        self,
        ip_address: str,
        entity_id: str,
        reason: str,
        duration_seconds: int = 3600,
        force_despite_cgnat: bool = False,
    ) -> Dict[str, Any]:
        """
        IP-level blocking — USE ONLY AS ABSOLUTE LAST RESORT.

        This method has an automatic CGNAT circuit-breaker that will REFUSE
        to block IP addresses that match known East African mobile carrier
        CGNAT ranges unless `force_despite_cgnat=True` is explicitly passed
        by an authorized human operator.

        NEVER call this automatically from SOAR for mobile network traffic.
        Only call this for confirmed datacenter/botnet IPs.
        """
        if not self.is_connected:
            return {"status": "failed", "reason": "cache_unavailable"}

        cgnat_risk = _is_cgnat_risk(ip_address)

        if cgnat_risk and not force_despite_cgnat:
            logger.error(
                f"[CONTAINMENT] ⚠️  CGNAT CIRCUIT-BREAKER ACTIVATED: Refusing to block IP {ip_address} "
                f"— detected as a high-risk CGNAT range. Blocking this IP would harm thousands of "
                f"legitimate users on the same carrier NAT. Use device fingerprint or token revocation "
                f"instead. Pass force_despite_cgnat=True if a human operator has confirmed this is safe."
            )
            return {
                "status": "blocked_by_cgnat_circuit_breaker",
                "ip": ip_address,
                "cgnat_risk": True,
                "recommendation": "Use contain_device() or invalidate_token() instead",
                "collateral_damage_risk": "HIGH — thousands of innocent users on same carrier NAT",
            }

        redis_key = f"containment:isolated:{ContainmentScope.IP_ADDRESS.value}:{ip_address}"
        # Also write legacy key for edge proxy compatibility
        legacy_key = f"soar:blocked_ip:{ip_address}"

        payload = json.dumps({
            "reason": reason,
            "entity_id": entity_id,
            "blocked_at": datetime.now(timezone.utc).isoformat(),
            "cgnat_risk": cgnat_risk,
            "forced_by_operator": force_despite_cgnat,
            "scope": "IP_LAST_RESORT",
        })

        self.redis.setex(redis_key, duration_seconds, payload)
        self.redis.setex(legacy_key, duration_seconds, payload)

        log_level = logger.warning if cgnat_risk else logger.critical
        log_level(
            f"[CONTAINMENT] IP BLOCK: {ip_address} | entity={entity_id} | "
            f"cgnat_risk={cgnat_risk} | forced={force_despite_cgnat} | reason={reason}"
        )

        return {
            "status": "ip_blocked",
            "ip": ip_address,
            "cgnat_risk": cgnat_risk,
            "duration_seconds": duration_seconds,
            "warning": "IP_BLOCK_ACTIVE — verify CGNAT risk before leaving in place" if cgnat_risk else None,
        }

    # ------------------------------------------------------------------ #
    # Session & Privilege Actions
    # ------------------------------------------------------------------ #

    def quarantine_session(self, session_id: str, duration_seconds: int = 3600) -> None:
        """Place an active session into the read-only quarantine sandbox."""
        if self.is_connected:
            self.redis.setex(
                f"containment:quarantine:{session_id}",
                duration_seconds,
                json.dumps({"quarantined_at": datetime.now(timezone.utc).isoformat()}),
            )

    def downgrade_privilege(self, user_id: str, duration_seconds: int = 3600) -> None:
        """Dynamically downgrade user privilege to READ_ONLY_SANDBOX."""
        if self.is_connected:
            self.redis.setex(f"containment:downgrade:{user_id}", duration_seconds, "READ_ONLY")

    def throttle_api(
        self,
        entity_id: str,
        limit_per_minute: int = 5,
        duration_seconds: int = 3600,
        scope: ContainmentScope = ContainmentScope.ENTITY_ID,
        device_fingerprint: Optional[str] = None,
    ) -> None:
        """
        Impose strict rate-limiting on a suspicious entity.
        Prefers device-fingerprint throttling over entity-level for precision.
        """
        if not self.is_connected:
            return

        if device_fingerprint:
            fp_hash = hashlib.sha256(device_fingerprint.encode()).hexdigest()
            self.redis.setex(
                f"containment:throttle:{ContainmentScope.DEVICE_FINGERPRINT.value}:{fp_hash}",
                duration_seconds,
                str(limit_per_minute),
            )

        # Also set entity-level throttle as fallback
        self.redis.setex(
            f"containment:throttle:{entity_id}",
            duration_seconds,
            str(limit_per_minute),
        )

    # ------------------------------------------------------------------ #
    # SIM Swap Emergency Response
    # ------------------------------------------------------------------ #

    def respond_to_sim_swap(
        self,
        old_device_fingerprint: str,
        entity_id: str,
        duration_seconds: int = 900,  # 15-minute hold pending review
    ) -> Dict[str, Any]:
        """
        Emergency SIM swap response: freeze the account pending MSISDN verification.

        Called by the SIEM velocity filter when a device identity change is
        detected within 15 minutes of a login or USSD session event. Places
        the account in a step-up authentication hold without blocking the IP,
        since the new device may be on a different carrier/CGNAT entirely.
        """
        if not self.is_connected:
            return {"status": "failed"}

        # Invalidate old device fingerprint (the one before the SIM swap)
        old_fp_hash = hashlib.sha256(old_device_fingerprint.encode()).hexdigest()
        self.redis.setex(
            f"containment:isolated:{ContainmentScope.DEVICE_FINGERPRINT.value}:{old_fp_hash}",
            duration_seconds,
            json.dumps({
                "reason": "SIM_SWAP_DETECTED_PENDING_VERIFICATION",
                "entity_id": entity_id,
                "flagged_at": datetime.now(timezone.utc).isoformat(),
            }),
        )

        # Place entity in step-up auth hold (not full block)
        self.redis.setex(
            f"containment:stepup_auth:{entity_id}",
            duration_seconds,
            json.dumps({
                "reason": "SIM_SWAP_VELOCITY_TRIGGER",
                "requires": "MSISDN_OTP_REVERIFICATION",
                "triggered_at": datetime.now(timezone.utc).isoformat(),
            }),
        )

        logger.critical(
            f"[CONTAINMENT] SIM SWAP RESPONSE: entity={entity_id} "
            f"placed in step-up auth hold for {duration_seconds}s. "
            f"Old device fingerprint invalidated."
        )

        return {
            "status": "sim_swap_hold_active",
            "entity_id": entity_id,
            "action": "STEP_UP_AUTH_REQUIRED",
            "duration_seconds": duration_seconds,
            "requires": "MSISDN_OTP_REVERIFICATION",
            "cgnat_safe": True,
        }

    def requires_stepup_auth(self, entity_id: str) -> Optional[Dict]:
        """Check if entity is in step-up authentication hold (e.g., post-SIM-swap)."""
        if not self.is_connected:
            return None
        raw = self.redis.get(f"containment:stepup_auth:{entity_id}")
        return json.loads(raw) if raw else None

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _resolve_containment_key(
        self,
        entity_id: str,
        device_fingerprint: Optional[str],
        jwt_jti: Optional[str],
        api_key_hash: Optional[str],
        scope_override: Optional[ContainmentScope],
    ) -> tuple:
        """Resolve the most precise identifier available."""

        if scope_override == ContainmentScope.DEVICE_FINGERPRINT and device_fingerprint:
            return ContainmentScope.DEVICE_FINGERPRINT, hashlib.sha256(device_fingerprint.encode()).hexdigest()

        if scope_override == ContainmentScope.JWT_JTI and jwt_jti:
            return ContainmentScope.JWT_JTI, jwt_jti

        if scope_override == ContainmentScope.API_KEY_HASH and api_key_hash:
            return ContainmentScope.API_KEY_HASH, api_key_hash

        # Auto-resolve: pick best available
        if device_fingerprint:
            return ContainmentScope.DEVICE_FINGERPRINT, hashlib.sha256(device_fingerprint.encode()).hexdigest()
        if jwt_jti:
            return ContainmentScope.JWT_JTI, jwt_jti
        if api_key_hash:
            return ContainmentScope.API_KEY_HASH, api_key_hash

        return ContainmentScope.ENTITY_ID, entity_id


# ---------------------------------------------------------------------------
# Global singleton — initialized once per process
# ---------------------------------------------------------------------------

containment_engine = ContainmentEngine()
