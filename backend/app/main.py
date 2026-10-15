from contextlib import asynccontextmanager
import os
import time
import json
import logging
import uvicorn
import asyncio
from typing import Any, Optional
from fastapi import FastAPI, Request, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime

# Internal ProjectXY Core Modules
from app.core.config import settings
from app.core.security_headers import SecurityHeadersMiddleware
from app.api.v1.api import api_router
from app.core.logging import setup_logging, log
from app.core.security import verify_token
from app.infrastructure.cache.redis_manager import redis_cache
from app.infrastructure.session import SessionLocal
from app.modules.firewall.llm_firewall import startup_firewall, shutdown_firewall
from app.modules.firewall.semantic_logger import semantic_logger
from app.infrastructure.kafka import kafka_streamer
from app.infrastructure.graph import graph_db


# ── LIFESPAN: SYSTEM INITIALIZATION ──────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    log.info("System Initializing Sovereign Defense Matrix...")

    # Infrastructure Connection
    if settings.ENABLE_GRAPH_DB:
        await graph_db.connect()
    else:
        # Swap in the lightweight NetworkX in-memory adapter so all graph call-sites
        # continue to work without a JVM/Neo4j container running.
        from app.infrastructure.graph_adapter import NetworkXGraphAdapter
        import app.infrastructure.graph as _graph_module
        _graph_module.graph_db = NetworkXGraphAdapter()
        log.info("[GRAPH] Startup skipped (ENABLE_GRAPH_DB=false). Using NetworkX in-memory adapter.")

    if settings.ENABLE_KAFKA:
        await kafka_streamer.connect()
    else:
        log.info("[KAFKA] Startup skipped (ENABLE_KAFKA=false).")

    # Async Task Orchestration (Fail-Safe)
    tasks = []
    try:
        from app.workers.integrity_monitor import integrity_monitor_loop
        tasks.append(asyncio.create_task(integrity_monitor_loop()))
        log.info("[STATUS] WORM Integrity Monitor: ONLINE")
    except Exception as e:
        log.error(f"[CRITICAL] Integrity Monitor startup failed: {e}")

    # AI Firewall Warmup
    if settings.ENABLE_FIREWALL:
        try:
            await startup_firewall()
            log.info("[FIREWALL] Cognitive Shield: ONLINE (Cleansing+RBAC+Ensemble+SemanticLog+Compliance)")
        except Exception as e:
            log.warning(f"[FIREWALL] Startup degraded: {e}")
    else:
        log.info("[FIREWALL] Startup skipped (ENABLE_FIREWALL=false).")

    yield

    # Graceful Shutdown
    log.info("System Shutting Down...")
    for t in tasks: t.cancel()
    if settings.ENABLE_KAFKA:
        await kafka_streamer.disconnect()
    if settings.ENABLE_GRAPH_DB:
        await graph_db.close()
    if settings.ENABLE_FIREWALL:
        await shutdown_firewall()
    await semantic_logger.stop()


# ── APP INITIALIZATION ───────────────────────────────────────────────────────
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    lifespan=lifespan
)

# ── CORS POLICY (Crucial for 3000/3001 Frontend) ────────────────────────────
# In production: traffic hits Traefik → Next.js proxy → backend (no CORS needed)
# In local dev: browser may hit :8000 directly, so we allow :3000/:3001
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "https://localhost",
    "https://localhost:443",
]
# FIXED: settings.BACKEND_CORS_ORIGINS (populated from .env.local's
# BACKEND_CORS_ORIGINS) was parsed by pydantic but never consulted anywhere in
# this file. Merged in here so that setting is finally meaningful.
allowed_origins = list(dict.fromkeys(
    allowed_origins + [str(o) for o in settings.BACKEND_CORS_ORIGINS]
))

app.add_middleware(SecurityHeadersMiddleware)


# ── SECURITY MIDDLEWARE: SOVEREIGN DEFENSE MATRIX ───────────────────────────
@app.middleware("http")
async def sovereign_defense_middleware(request: Request, call_next):
    # FIXED: was `origin = request.headers.get("origin", "http://localhost:3000")`,
    # then reflected back on every response with Access-Control-Allow-Credentials:
    # true regardless of what it was — meaning literally any origin on the
    # internet could make credentialed requests to this API. Now only an origin
    # actually present in allowed_origins is ever reflected; anything else gets
    # a non-matching Access-Control-Allow-Origin, which browsers reject.
    request_origin = request.headers.get("origin", "")
    origin = request_origin if request_origin in allowed_origins else allowed_origins[0]

    # Bypass for Health checks
    if request.url.path in ["/health", "/"]:
        return await call_next(request)

    # Handle Preflight OPTIONS requests cleanly
    if request.method == "OPTIONS":
        return JSONResponse(
            content={},
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
                "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Requested-With, Accept, Origin, Access-Control-Request-Method, Access-Control-Request-Headers",
            }
        )

    # AI Guardrail Logic
    if (request.url.path.startswith("/api/v1/agent")) and request.method in ["POST"]:
        body_bytes = await request.body()
        request._receive = lambda: {"type": "http.request", "body": body_bytes}

        if body_bytes and b"override system prompts" in body_bytes.lower():
            return JSONResponse(
                status_code=403,
                content={"detail": "Payload Blocked by AI Guardrail"},
                headers={
                    "Access-Control-Allow-Origin": origin,
                    "Access-Control-Allow-Credentials": "true",
                }
            )

    response = await call_next(request)

    # Ensure CORS headers are attached to every standard response too
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    response.headers[
        "Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-Requested-With, Accept, Origin, Access-Control-Request-Method, Access-Control-Request-Headers"

    return response


# ── ROUTER MAPPING ──────────────────────────────────────────────────────────
app.include_router(api_router, prefix=settings.API_V1_STR)


def _extract_ws_token(websocket: WebSocket) -> Optional[str]:
    token = websocket.query_params.get("token")
    if token:
        return token

    authorization = websocket.headers.get("authorization", "")
    if authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()

    cookie_token = websocket.cookies.get("access_token")
    if cookie_token:
        return cookie_token.removeprefix("Bearer ").strip()

    return None


async def _authenticate_ws(websocket: WebSocket) -> bool:
    if settings.AUTH_BYPASS_ENABLED:
        return True

    token = _extract_ws_token(websocket)
    if not token:
        await websocket.accept()
        await websocket.close(code=4003, reason="Authentication required")
        return False

    payload = verify_token(token)
    if not payload or not payload.get("sub"):
        await websocket.accept()
        await websocket.close(code=4003, reason="Invalid authentication token")
        return False

    return True


async def _send_recent_threats(websocket: WebSocket, limit: int = 25) -> None:
    db = SessionLocal()
    try:
        from sqlalchemy import text

        rows = db.execute(
            text(
                """
                SELECT id::text, timestamp, entity_id, source_ip, risk_score,
                       soar_action, is_apt_chain, reasons, mitre_tactic
                FROM siem_threat_events
                ORDER BY timestamp DESC
                    LIMIT :limit
                """
            ),
            {"limit": limit},
        ).fetchall()

        for row in rows:
            risk_score = float(row[4] or 0)
            severity = "critical" if risk_score >= 85 else "high" if risk_score >= 65 else "medium"
            await websocket.send_text(
                json.dumps(
                    {
                        "id": row[0],
                        "event_type": "SIEM_THREAT",
                        "channel": "threats",
                        "severity": severity,
                        "timestamp": row[1].isoformat() if row[1] else datetime.utcnow().isoformat(),
                        "payload": {
                            "entity_id": row[2],
                            "source": row[3] or "unknown",
                            "target": row[2],
                            "risk_score": risk_score,
                            "soar_action": row[5],
                            "is_apt_chain": bool(row[6]),
                            "reasons": row[7] or [],
                            "mitre_tactic": row[8],
                            "title": f"Threat score {risk_score:.0f}",
                            "summary": ", ".join(row[7] or []) if row[7] else "Recent SIEM classification event.",
                        },
                    }
                )
            )
    except Exception as exc:
        log.warning(f"[TELEMETRY] Bootstrap threat snapshot unavailable: {exc}")
    finally:
        db.close()


def _map_pubsub_event(channel: str, raw_payload: Any) -> dict:
    if isinstance(raw_payload, str):
        try:
            payload = json.loads(raw_payload)
        except Exception:
            payload = {"message": raw_payload}
    elif isinstance(raw_payload, dict):
        payload = raw_payload
    else:
        payload = {"message": str(raw_payload)}

    if channel == "god_view_sync_global" and isinstance(payload, dict):
        event_type = str(payload.get("type") or payload.get("event_type") or "DASHBOARD_EVENT")
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    elif channel == "soar:ip_block_events":
        event_type = "SOAR_BLOCK_EVENT"
        data = payload if isinstance(payload, dict) else {"message": payload}
    elif channel == "hivemind:vaccines":
        event_type = "HIVEMIND_VACCINE_EVENT"
        data = payload if isinstance(payload, dict) else {"message": payload}
    else:
        event_type = str(channel).upper()
        data = payload if isinstance(payload, dict) else {"message": payload}

    lowered = event_type.lower()
    if channel == "soar:ip_block_events" or lowered in {"alert", "threat_intercept", "soar_block_event"}:
        mapped_channel = "threats"
        severity = "critical"
    elif lowered in {"command_issued", "agent_connect", "agent_disconnect", "global_inoculation_event",
                     "defense_action"}:
        mapped_channel = "ops_execution" if lowered.startswith("command") or lowered.startswith("agent") else "defense"
        severity = data.get("severity") if isinstance(data, dict) and data.get("severity") else "medium"
    else:
        mapped_channel = data.get("channel") if isinstance(data, dict) and data.get("channel") else "threats"
        severity = data.get("severity") if isinstance(data, dict) and data.get("severity") else "low"

    return {
        "id": data.get("id") if isinstance(data, dict) and data.get(
            "id") else f"{event_type}-{datetime.utcnow().timestamp()}",
        "event_type": event_type,
        "channel": mapped_channel,
        "severity": severity,
        "timestamp": data.get("timestamp") if isinstance(data, dict) and data.get(
            "timestamp") else datetime.utcnow().isoformat(),
        "payload": data,
    }


@app.websocket("/api/v1/ws/telemetry")
async def websocket_telemetry_bridge(websocket: WebSocket):
    if not await _authenticate_ws(websocket):
        return

    await websocket.accept()
    pubsub = redis_cache.redis_client.pubsub()
    channels = ["god_view_sync_global", "soar:ip_block_events", "hivemind:vaccines"]

    try:
        await pubsub.subscribe(*channels)
        await _send_recent_threats(websocket)

        await websocket.send_text(
            json.dumps(
                {
                    "id": f"telemetry-bootstrap-{datetime.utcnow().timestamp()}",
                    "event_type": "TELEMETRY_CONNECTED",
                    "channel": "status",
                    "severity": "low",
                    "timestamp": datetime.utcnow().isoformat(),
                    "payload": {"status": "connected", "channels": channels},
                }
            )
        )

        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is None:
                await asyncio.sleep(0.05)
                continue

            telemetry_message = _map_pubsub_event(message.get("channel") or "threats", message.get("data"))
            await websocket.send_text(json.dumps(telemetry_message))
    except Exception as exc:
        log.warning(f"[TELEMETRY] Bridge disconnected: {exc}")
    finally:
        try:
            await pubsub.unsubscribe(*channels)
            await pubsub.close()
        except Exception:
            pass


@app.websocket("/api/v1/ws/terminal")
async def websocket_terminal(websocket: WebSocket):
    """
    ProjectXY Nexus Command Console — Real authenticated interactive shell.

    Accepts commands from the browser terminal and executes backend operations.
    Each response is a JSON object: {type, output, level, timestamp}

    Auth: token via query param, Authorization header, or access_token cookie.
    """
    token = websocket.query_params.get("token")
    if not token:
        auth_header = websocket.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        cookie = websocket.cookies.get("access_token", "")
        token = cookie.removeprefix("Bearer ").strip() or cookie

    if not token:
        await websocket.accept()
        await websocket.send_text(json.dumps({
            "type": "ERROR", "level": "error",
            "output": "[AUTH] Authentication required. Reconnect with a valid session.",
            "timestamp": datetime.utcnow().isoformat(),
        }))
        await websocket.close(code=4003)
        return

    payload = verify_token(token)
    if not payload or not payload.get("sub"):
        await websocket.accept()
        await websocket.send_text(json.dumps({
            "type": "ERROR", "level": "error",
            "output": "[AUTH] Invalid or expired token.",
            "timestamp": datetime.utcnow().isoformat(),
        }))
        await websocket.close(code=4003)
        return

    user_sub = payload.get("sub", "unknown")
    user_role = payload.get("role", "analyst")

    await websocket.accept()
    log.info(f"[TERMINAL] Nexus Console connected: user={user_sub} role={user_role}")

    def _ts() -> str:
        return datetime.utcnow().isoformat()

    async def send(output: str, level: str = "info", msg_type: str = "OUTPUT"):
        await websocket.send_text(json.dumps({
            "type": msg_type, "level": level,
            "output": output, "timestamp": _ts(),
        }))

    # ── Banner ───────────────────────────────────────────────────────────────
    await send(
        f"\r\n  ██████  ██████   ██████        ███████  ██████ ████████\r\n"
        f"  ██   ██ ██   ██ ██    ██       ██      ██    ██   ██\r\n"
        f"  ██████  ██████  ██    ██ █████ ███████ ██       ██\r\n"
        f"  ██      ██   ██ ██    ██            ██ ██    ██   ██\r\n"
        f"  ██      ██   ██  ██████        ███████  ██████    ██\r\n"
        f"\r\n  NEXUS COMMAND CONSOLE v2.0  |  user={user_sub}  role={user_role.upper()}\r\n"
        f"  Type 'help' for available commands.\r\n",
        level="system", msg_type="SYSTEM_CONNECTED"
    )

    HELP_TEXT = """\r
SOVEREIGN COMMAND CONSOLE — Available Commands:\r
\r
  SYSTEM:\r
    status               — Live system health (DB, Redis, entity count)\r
    soc-metrics          — SOC event counts, MTTR, playbook runs\r
    tail-logs [n]        — Stream last N SIEM events (default 20)\r
\r
  DEVICE MANAGEMENT:\r
    devices              — List all registered devices\r
    isolate <host>       — Quarantine a host (operator/admin only)\r
    flush-sessions <id>  — Terminate all WS sessions for an entity\r
\r
  IDENTITY:\r
    revoke-token <sub>   — Revoke JWT sessions for a subject (admin only)\r
\r
  PLAYBOOKS:\r
    playbook list        — Show available SOAR playbooks\r
    playbook run <id>    — Execute a SOAR playbook (operator/admin only)\r
\r
  DISPLAY:\r
    clear                — Clear terminal\r
    help                 — Show this message\r
"""

    # ── Command loop ─────────────────────────────────────────────────────────
    try:
        while True:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=120)
            cmd = raw.strip()
            if not cmd:
                continue

            parts = cmd.split()
            verb = parts[0].lower() if parts else ""

            # ── help ──────────────────────────────────────────────────────
            if verb == "help":
                await send(HELP_TEXT, level="info")

            # ── clear ─────────────────────────────────────────────────────
            elif verb == "clear":
                await send("", level="clear", msg_type="CLEAR")

            # ── status ────────────────────────────────────────────────────
            elif verb == "status":
                from app.infrastructure.cache.redis_manager import redis_cache
                from sqlalchemy import text
                lines = ["[STATUS] ProjectXY System Health\r\n"]
                # DB
                db = SessionLocal()
                try:
                    db.execute(text("SELECT 1"))
                    entity_count = db.execute(text("SELECT COUNT(*) FROM entities")).scalar()
                    device_count = db.execute(text("SELECT COUNT(*) FROM devices")).scalar()
                    fw_24h = db.execute(text(
                        "SELECT COUNT(*) FROM semantic_logs "
                        "WHERE created_at >= NOW() - INTERVAL '24 hours'"
                    )).scalar()
                    lines.append(f"  DATABASE   : \033[32mONLINE\033[0m")
                    lines.append(f"  ENTITIES   : {entity_count}")
                    lines.append(f"  DEVICES    : {device_count}")
                    lines.append(f"  FW EVENTS  : {fw_24h} (last 24h)")
                except Exception as e:
                    lines.append(f"  DATABASE   : \033[31mDEGRADED — {e}\033[0m")
                finally:
                    db.close()
                # Redis
                try:
                    redis_cache.redis_client.ping()
                    lines.append(f"  REDIS      : \033[32mONLINE\033[0m")
                    blocked = redis_cache.redis_client.llen("blocked_ips")
                    lines.append(f"  BLOCKED IPs: {blocked}")
                except Exception:
                    lines.append(f"  REDIS      : \033[31mOFFLINE\033[0m")
                await send("\r\n".join(lines), level="info")

            # ── soc-metrics ───────────────────────────────────────────────
            elif verb == "soc-metrics":
                from sqlalchemy import text
                db = SessionLocal()
                try:
                    row = db.execute(text(
                        "SELECT COUNT(*) as total, "
                        "SUM(CASE WHEN action='BLOCK' THEN 1 ELSE 0 END) as blocks, "
                        "SUM(CASE WHEN action='WARN' THEN 1 ELSE 0 END) as warns, "
                        "AVG(threat_score) as avg_score, "
                        "SUM(CASE WHEN multi_stage_flag THEN 1 ELSE 0 END) as multi_stage "
                        "FROM semantic_logs WHERE created_at >= NOW() - INTERVAL '24 hours'"
                    )).fetchone()
                    total = int(row[0] or 0)
                    blocks = int(row[1] or 0)
                    warns = int(row[2] or 0)
                    avg_s = float(row[3] or 0.0)
                    ms = int(row[4] or 0)
                    out = (
                        f"[SOC METRICS] Last 24h\r\n"
                        f"  Total events     : {total}\r\n"
                        f"  Blocked          : {blocks}\r\n"
                        f"  Warnings         : {warns}\r\n"
                        f"  Avg threat score : {avg_s:.4f}\r\n"
                        f"  Multi-stage flags: {ms}"
                    )
                except Exception as e:
                    out = f"[SOC METRICS] Error: {e}"
                finally:
                    db.close()
                await send(out, level="info")

            # ── tail-logs [n] ─────────────────────────────────────────────
            elif verb == "tail-logs":
                limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 20
                limit = min(limit, 100)
                from sqlalchemy import text
                db = SessionLocal()
                try:
                    rows = db.execute(text(
                        "SELECT timestamp, entity_id, source_ip, risk_score, mitre_tactic "
                        "FROM siem_threat_events ORDER BY timestamp DESC LIMIT :lim"
                    ), {"lim": limit}).fetchall()
                    if not rows:
                        await send("[LOGS] No SIEM events found.", level="warn")
                    else:
                        header = f"[LOGS] Last {limit} SIEM events:\r\n"
                        lines = [header]
                        for r in rows:
                            ts = r[0].strftime("%H:%M:%S") if r[0] else "?"
                            lines.append(
                                f"  {ts} | {str(r[1] or '?')[:16]:16s} | "
                                f"{str(r[2] or 'unknown'):15s} | "
                                f"risk={float(r[3] or 0):.1f} | {r[4] or 'N/A'}"
                            )
                        await send("\r\n".join(lines), level="info")
                except Exception as e:
                    await send(f"[LOGS] Error: {e}", level="error")
                finally:
                    db.close()

            # ── devices ───────────────────────────────────────────────────
            elif verb == "devices":
                from sqlalchemy import text
                db = SessionLocal()
                try:
                    rows = db.execute(text(
                        "SELECT name, hostname, ip, status, type, risk_score "
                        "FROM devices ORDER BY risk_score DESC LIMIT 30"
                    )).fetchall()
                    if not rows:
                        await send("[DEVICES] No devices registered.", level="warn")
                    else:
                        lines = [f"[DEVICES] {len(rows)} registered:\r\n"]
                        for r in rows:
                            status_color = "\033[31m" if r[3] == "isolated" else "\033[32m"
                            lines.append(
                                f"  {str(r[0] or '?'):20s} | {str(r[1] or '?'):20s} | "
                                f"{str(r[2] or '?'):15s} | "
                                f"{status_color}{str(r[3] or 'unknown'):10s}\033[0m | "
                                f"risk={float(r[5] or 0):.1f}"
                            )
                        await send("\r\n".join(lines), level="info")
                except Exception as e:
                    await send(f"[DEVICES] Error: {e}", level="error")
                finally:
                    db.close()

            # ── isolate <host> ────────────────────────────────────────────
            elif verb == "isolate":
                if user_role not in ("operator", "admin"):
                    await send("[ISOLATE] Insufficient clearance. Requires operator or admin.", level="error")
                elif len(parts) < 2:
                    await send("[ISOLATE] Usage: isolate <hostname_or_ip>", level="warn")
                else:
                    target = parts[1]
                    from sqlalchemy import text
                    db = SessionLocal()
                    try:
                        result = db.execute(text(
                            "UPDATE devices SET status='isolated', updated_at=NOW() "
                            "WHERE hostname=:t OR ip::text=:t RETURNING name, hostname, ip"
                        ), {"t": target})
                        row = result.fetchone()
                        db.commit()
                        if row:
                            # Publish isolation event
                            from app.infrastructure.cache.redis_manager import redis_cache
                            redis_cache.redis_client.publish(
                                "god_view_sync_global",
                                json.dumps({
                                    "type": "HOST_ISOLATED",
                                    "event_type": "HOST_ISOLATED",
                                    "channel": "threats",
                                    "severity": "high",
                                    "data": {"host": target, "by": user_sub},
                                })
                            )
                            log.warning(f"[TERMINAL] Host {target} isolated by {user_sub}")
                            await send(
                                f"[ISOLATE] ✓ Host '{row[0] or target}' ({row[2]}) quarantined. "
                                f"Network isolation active. Telemetry event published.",
                                level="warn"
                            )
                        else:
                            await send(f"[ISOLATE] No device found matching '{target}'.", level="warn")
                    except Exception as e:
                        db.rollback()
                        await send(f"[ISOLATE] Error: {e}", level="error")
                    finally:
                        db.close()

            # ── revoke-token <sub> ────────────────────────────────────────
            elif verb == "revoke-token":
                if user_role != "admin":
                    await send("[REVOKE] Insufficient clearance. Requires admin.", level="error")
                elif len(parts) < 2:
                    await send("[REVOKE] Usage: revoke-token <subject_id>", level="warn")
                else:
                    sub = parts[1]
                    try:
                        from app.infrastructure.cache.redis_manager import redis_cache
                        keys = redis_cache.redis_client.keys(f"session:{sub}:*")
                        revoked = len(keys)
                        if keys:
                            redis_cache.redis_client.delete(*keys)
                        # Also add to denylist with TTL
                        redis_cache.redis_client.setex(f"jwt:denylist:{sub}", 86400, "revoked")
                        log.warning(f"[TERMINAL] Token revoked for sub={sub} by admin={user_sub}")
                        await send(
                            f"[REVOKE] ✓ {revoked} session(s) revoked for subject '{sub}'. "
                            f"JWT denylist entry created (24h TTL).",
                            level="warn"
                        )
                    except Exception as e:
                        await send(f"[REVOKE] Error: {e}", level="error")

            # ── flush-sessions <entity_id> ────────────────────────────────
            elif verb == "flush-sessions":
                if len(parts) < 2:
                    await send("[FLUSH] Usage: flush-sessions <entity_id>", level="warn")
                else:
                    eid = parts[1]
                    try:
                        from app.infrastructure.cache.redis_manager import redis_cache
                        pattern_keys = redis_cache.redis_client.keys(f"*{eid}*")
                        count = len(pattern_keys)
                        if pattern_keys:
                            redis_cache.redis_client.delete(*pattern_keys)
                        await send(
                            f"[FLUSH] ✓ Flushed {count} cache/session key(s) for entity '{eid}'.",
                            level="warn"
                        )
                    except Exception as e:
                        await send(f"[FLUSH] Error: {e}", level="error")

            # ── playbook list / run ───────────────────────────────────────
            elif verb == "playbook":
                action = parts[1].lower() if len(parts) > 1 else "list"
                if action == "list":
                    pb_list = (
                        "[PLAYBOOKS] Available SOAR Playbooks:\r\n"
                        "  PB-001  credential_dump       — Revoke sessions, force MFA, alert SOC\r\n"
                        "  PB-002  ransomware_detected   — Isolate all devices, snapshot state\r\n"
                        "  PB-003  lateral_movement      — Segment network, increase monitoring\r\n"
                        "  PB-004  prompt_injection      — Block entity, log to WORM ledger\r\n"
                        "  PB-005  mobile_money_fraud    — Freeze account, notify compliance"
                    )
                    await send(pb_list, level="info")
                elif action == "run":
                    if user_role not in ("operator", "admin"):
                        await send("[PLAYBOOK] Insufficient clearance. Requires operator or admin.", level="error")
                    elif len(parts) < 3:
                        await send("[PLAYBOOK] Usage: playbook run <id>", level="warn")
                    else:
                        pb_id = parts[2].upper()
                        try:
                            from app.infrastructure.cache.redis_manager import redis_cache
                            redis_cache.redis_client.publish(
                                "god_view_sync_global",
                                json.dumps({
                                    "type": "PLAYBOOK_TRIGGERED",
                                    "event_type": "PLAYBOOK_TRIGGERED",
                                    "channel": "ops_execution",
                                    "severity": "medium",
                                    "data": {
                                        "playbook_id": pb_id,
                                        "triggered_by": user_sub,
                                        "timestamp": _ts(),
                                    },
                                })
                            )
                            log.warning(f"[TERMINAL] Playbook {pb_id} triggered by {user_sub}")
                            await send(
                                f"[PLAYBOOK] ✓ Playbook '{pb_id}' execution initiated. "
                                f"Event published to SOC telemetry channel.",
                                level="warn"
                            )
                        except Exception as e:
                            await send(f"[PLAYBOOK] Error: {e}", level="error")
                else:
                    await send("[PLAYBOOK] Unknown action. Use: playbook list | playbook run <id>", level="warn")

            else:
                await send(
                    f"[CONSOLE] Unknown command: '{cmd}'. Type 'help' for available commands.",
                    level="warn"
                )

    except asyncio.TimeoutError:
        await send("[SYSTEM] Session idle timeout. Reconnect to continue.", level="warn", msg_type="SYSTEM_DISCONNECT")
    except Exception as exc:
        log.warning(f"[TERMINAL] Console disconnected: {exc}")
    finally:
        log.info(f"[TERMINAL] Console session closed: user={user_sub}")


# Note: the duplicate dead /health route + ~45 lines of unreachable orphaned
# websocket-auth code that used to sit here (leftover from a botched refactor,
# referencing an undefined 'websocket' name — harmless since it followed a
# return statement and never executed) has been removed. The real /health
# route is immediately below.

@app.get("/health")
async def health():
    return {"status": "active", "timestamp": datetime.utcnow()}

# CORS is implemented via sovereign_defense_middleware, defined near the top
# of this file — it validates the request Origin against allowed_origins
# (which includes settings.BACKEND_CORS_ORIGINS from .env.local) rather than
# reflecting any origin unconditionally.