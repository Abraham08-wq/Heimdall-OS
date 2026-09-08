"""
firewall_timescale_writer.py — Async TimescaleDB Event Logger for the AI Firewall
==================================================================================
Persists every FirewallVerdict into the `firewall_events` hypertable.
Designed to be called non-blocking (fire-and-forget) from the firewall.check() path
so it never adds latency to the critical <50ms path.

Usage (inside llm_firewall.py or the FastAPI endpoint):
    asyncio.create_task(log_firewall_event(verdict, tenant_id, entity_id, pg_pool))
"""
import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

import asyncpg

from app.modules.firewall.llm_firewall import FirewallVerdict

logger = logging.getLogger("projectxy.firewall.writer")


async def log_firewall_event(
    verdict: FirewallVerdict,
    tenant_id: str,
    entity_id: str,
    source_ip: str = "unknown",
    pg_pool: Optional[asyncpg.Pool] = None,
) -> None:
    """
    Persist a FirewallVerdict to the TimescaleDB firewall_events hypertable.
    Safe to call as fire-and-forget (ignores DB failures gracefully).

    CBK Compliance: Raw prompt is NEVER stored. Only the SHA-256 hash of
    the prompt preview is persisted to satisfy the data minimisation requirement
    of Kenya DPA 2019 Section 25.
    """
    if pg_pool is None:
        return

    # Anonymise IP to /24 subnet (Kenya DPA 2019 — minimal PII)
    ip_parts = source_ip.split(".")
    if len(ip_parts) == 4:
        subnet = f"{'.'.join(ip_parts[:3])}.0/24"
    else:
        subnet = None

    # Hash of prompt preview (deterministic, non-reversible)
    preview_hash = (
        hashlib.sha256(verdict.scrubbed_prompt.encode()).hexdigest()
        if verdict.scrubbed_prompt
        else None
    )

    try:
        async with pg_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO firewall_events (
                    timestamp, tenant_id, entity_id, action, threat_score,
                    semantic_similarity, matched_category, pii_types_detected,
                    reasons, latency_ms, prompt_hash, prompt_preview_hash,
                    source_ip_subnet
                ) VALUES (
                    NOW(), $1, $2, $3, $4, $5, $6, $7::jsonb,
                    $8::jsonb, $9, $10, $11, $12
                )
                """,
                tenant_id,
                entity_id,
                verdict.action,
                verdict.threat_score,
                verdict.semantic_similarity,
                verdict.matched_category,
                verdict.pii_types_detected,
                verdict.reasons,
                verdict.latency_ms,
                verdict.prompt_hash,
                preview_hash,
                subnet,
            )
    except Exception as exc:
        logger.debug(f"[FIREWALL_WRITER] TimescaleDB write skipped: {exc}")


async def log_siem_event(
    entity_id: str,
    source_ip: str,
    risk_score: float,
    soar_action: str,
    reasons: list,
    is_apt_chain: bool = False,
    graph_context: dict = None,
    mitre_tactic: str = None,
    tenant_id: str = "default",
    event_topic: str = "siem",
    pg_pool: Optional[asyncpg.Pool] = None,
) -> None:
    """Persist a SIEM classification result to the siem_threat_events hypertable."""
    if pg_pool is None:
        return
    ctx = graph_context or {}
    try:
        async with pg_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO siem_threat_events (
                    timestamp, tenant_id, entity_id, source_ip, event_topic,
                    risk_score, soar_action, reasons, graph_scan_count,
                    graph_login_fail_count, graph_fw_block_count,
                    is_apt_chain, mitre_tactic
                ) VALUES (
                    NOW(), $1, $2, $3, $4, $5, $6, $7::jsonb,
                    $8, $9, $10, $11, $12
                )
                """,
                tenant_id,
                entity_id,
                source_ip,
                event_topic,
                risk_score,
                soar_action,
                reasons,
                ctx.get("scan_count", 0),
                ctx.get("failed_login_count", 0),
                ctx.get("firewall_block_count", 0),
                is_apt_chain,
                mitre_tactic,
            )
    except Exception as exc:
        logger.debug(f"[SIEM_WRITER] TimescaleDB write skipped: {exc}")
