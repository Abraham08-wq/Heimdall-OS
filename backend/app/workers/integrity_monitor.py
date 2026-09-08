"""
Integrity Monitor — WORM Audit Chain Background Worker
=======================================================
Runs every 60s verifying the blockchain-style audit log.
Includes exponential backoff retry on DB/DNS transient failures.
Only escalates to CRITICAL after 3 consecutive failures.
"""

import asyncio
import logging
import socket
from app.infrastructure.session import SessionLocal
from app.services.worm import worm_service

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────

_MAX_RETRIES      = 3
_BASE_BACKOFF_SEC = 2.0   # doubles each retry: 2s → 4s → 8s
_POLL_INTERVAL    = 60    # seconds between verification cycles

# Track consecutive failures to distinguish transient vs persistent
_consecutive_failures = 0

# ── Helper: detect DNS/network transient errors ────────────────────────────────

def _is_transient(exc: Exception) -> bool:
    """Return True if this is a network-transient error (DNS, connection refused, etc.)."""
    msg = str(exc).lower()
    return any(kw in msg for kw in [
        "could not translate host",
        "name or service not known",
        "connection refused",
        "connection reset",
        "timeout",
        "temporarily unavailable",
    ])


async def _run_check_with_retry() -> None:
    """
    Attempt worm_service.verify_chain() with up to _MAX_RETRIES attempts.
    Uses exponential backoff for transient failures.
    Raises the last exception if all retries are exhausted.
    """
    backoff = _BASE_BACKOFF_SEC
    last_exc: Exception | None = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            db = SessionLocal()
            try:
                is_valid = worm_service.verify_chain(db)
            finally:
                db.close()

            if not is_valid:
                logger.critical(
                    "🚨 AUDIT LOG INTEGRITY FAILURE — WORM chain verification FAILED. "
                    "Possible tamper detected."
                )
            else:
                logger.debug("Audit Log Integrity: VERIFIED ✓")

            return  # success — exit retry loop

        except Exception as exc:
            last_exc = exc
            if _is_transient(exc):
                logger.warning(
                    f"[IntegrityMonitor] Transient failure (attempt {attempt}/{_MAX_RETRIES}): {exc}"
                )
            else:
                logger.warning(
                    f"[IntegrityMonitor] Unexpected error (attempt {attempt}/{_MAX_RETRIES}): {exc}"
                )

            if attempt < _MAX_RETRIES:
                await asyncio.sleep(backoff)
                backoff *= 2  # exponential: 2 → 4 → 8 seconds

    # All retries exhausted — re-raise so caller can track consecutive failures
    raise last_exc  # type: ignore[misc]


async def integrity_monitor_loop() -> None:
    """
    Runs forever — checks WORM chain every _POLL_INTERVAL seconds.
    Distinguishes transient DNS/network failures (WARNING) from
    persistent failures (ERROR → CRITICAL after 3 consecutive).
    """
    global _consecutive_failures

    logger.info(
        f"🔐 WORM Integrity Monitor starting — "
        f"poll={_POLL_INTERVAL}s, retries={_MAX_RETRIES}, backoff={_BASE_BACKOFF_SEC}s"
    )

    while True:
        try:
            await _run_check_with_retry()
            # Success — reset consecutive failure counter
            if _consecutive_failures > 0:
                logger.info(
                    f"[IntegrityMonitor] Recovered after {_consecutive_failures} consecutive failure(s)."
                )
            _consecutive_failures = 0

        except Exception as exc:
            _consecutive_failures += 1

            if _consecutive_failures < _MAX_RETRIES:
                logger.warning(
                    f"[IntegrityMonitor] Consecutive failure #{_consecutive_failures} — "
                    f"treating as transient: {exc}"
                )
            else:
                logger.error(
                    f"[IntegrityMonitor] 🚨 PERSISTENT FAILURE — {_consecutive_failures} consecutive failures. "
                    f"Last error: {exc}. Escalating to CRITICAL."
                )
                if _consecutive_failures == _MAX_RETRIES:
                    logger.critical(
                        "[IntegrityMonitor] CRITICAL: Cannot reach database for integrity verification. "
                        "Manual intervention may be required."
                    )

        await asyncio.sleep(_POLL_INTERVAL)
