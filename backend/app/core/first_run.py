"""
backend/app/core/first_run.py
First-boot detection and credential warning for ProjectXY.
"""
from __future__ import annotations
import logging
from typing import Optional

log = logging.getLogger(__name__)

_BANNER = """
╔═══════════════════════════════════════════════════════════════════╗
║         ⚠️  ProjectXY — FIRST RUN DETECTED                         ║
║                                                                   ║
║  Default enterprise credentials are no longer created by default. ║
║  Please create an administrator user manually.                    ║
╚═══════════════════════════════════════════════════════════════════╝
"""


async def check_first_run(db_pool=None) -> bool:
    """
    Returns True if this is the first run (credentials not yet changed).
    Works with asyncpg pool or gracefully degrades without a DB.
    """
    if db_pool is None:
        return True  # Can't check — assume first run

    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT value FROM system_flags WHERE key = 'first_run_complete'"
            )
            if row is None:
                return True
            return row["value"] != "true"
    except Exception as exc:
        log.warning("[FirstRun] Could not query system_flags: %s", exc)
        return True


async def mark_first_run_complete(db_pool=None) -> None:
    """Mark first run as complete in the database."""
    if db_pool is None:
        return
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO system_flags (key, value, updated_at)
                VALUES ('first_run_complete', 'true', NOW())
                ON CONFLICT (key) DO UPDATE SET value = 'true', updated_at = NOW()
                """
            )
        log.info("[FirstRun] First-run flag cleared. Default credentials deactivated.")
    except Exception as exc:
        log.warning("[FirstRun] Could not update system_flags: %s", exc)


def print_first_run_banner() -> None:
    """Print the first-run credential banner to stdout."""
    for line in _BANNER.splitlines():
        log.warning(line)


async def run_first_boot_checks(db_pool=None) -> None:
    """
    Call this from main.py lifespan startup.
    Prints the credential banner if this is the first boot.
    """
    is_first = await check_first_run(db_pool)
    if is_first:
        print_first_run_banner()
    else:
        log.info("[FirstRun] ✅ First-run complete. Custom credentials active.")
