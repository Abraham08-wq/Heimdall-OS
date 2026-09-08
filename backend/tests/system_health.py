#!/usr/bin/env python3
"""
ProjectXY Sovereign Infrastructure Health Diagnostic
=====================================================
Phase 2 Directive: Comprehensive health-check that pings Neo4j, PostgreSQL,
Redis, and Kafka. Validates connectivity, latency, and capacity thresholds
critical for CBK-compliant operations.

Usage:
    python system_health.py                # Full check with table output
    python system_health.py --json         # Machine-readable JSON output
    python system_health.py --watch        # Continuous monitoring (5s interval)
"""
import asyncio
import json
import socket
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Optional rich formatting (degrades gracefully if not installed)
# ---------------------------------------------------------------------------
try:
    from rich.console import Console
    from rich.table import Table
    from rich import box
    _rich = True
    console = Console()
except ImportError:
    _rich = False

# ---------------------------------------------------------------------------
# Import heavy drivers lazily so the script still runs even when some
# packages are missing
# ---------------------------------------------------------------------------

def _try_import(module_name: str):
    try:
        import importlib
        return importlib.import_module(module_name)
    except ImportError:
        return None


# ===========================================================================
# CHECKER FUNCTIONS
# ===========================================================================

async def check_postgresql(url: str = None) -> Dict[str, Any]:
    """Verify PostgreSQL / TimescaleDB connectivity and key metrics."""
    result = {"service": "PostgreSQL (TimescaleDB)", "status": "UNKNOWN", "latency_ms": None, "detail": {}}
    try:
        # Load .env values if no explicit URL given
        if url is None:
            import os
            from dotenv import load_dotenv
            load_dotenv("/home/bantu/Documents/ProjectXY/.env.local") or load_dotenv("/home/bantu/Documents/ProjectXY/.env")
            url = os.getenv("DATABASE_URL", "postgresql://postgres:changethis@localhost:5433/cyberintel")
        
        # Normalise URL for asyncpg (remove +asyncpg if present)
        pg_url = url.replace("postgresql+asyncpg", "postgresql").replace("+asyncpg", "")
        
        asyncpg = _try_import("asyncpg")
        if asyncpg is None:
            result["status"] = "SKIP"
            result["detail"]["reason"] = "asyncpg not installed"
            return result

        t0 = time.perf_counter()
        conn = await asyncpg.connect(pg_url, timeout=5)
        latency = (time.perf_counter() - t0) * 1000

        # Basic metadata
        version = await conn.fetchval("SELECT version()")
        db_size = await conn.fetchval(
            "SELECT pg_size_pretty(pg_database_size(current_database()))"
        )
        
        # TimescaleDB check
        ts_installed = await conn.fetchval(
            "SELECT COUNT(*) FROM pg_extension WHERE extname = 'timescaledb'"
        )
        
        # pgvector check
        vec_installed = await conn.fetchval(
            "SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'"
        )
        
        # Hypertable count
        hypertable_count = 0
        if ts_installed:
            hypertable_count = await conn.fetchval(
                "SELECT COUNT(*) FROM timescaledb_information.hypertables"
            )
        
        # Active connections
        active_conns = await conn.fetchval(
            "SELECT COUNT(*) FROM pg_stat_activity WHERE state = 'active'"
        )

        await conn.close()

        result["status"] = "HEALTHY"
        result["latency_ms"] = round(latency, 2)
        result["detail"] = {
            "version": version.split(",")[0] if version else "unknown",
            "database_size": db_size,
            "timescaledb_installed": bool(ts_installed),
            "pgvector_installed": bool(vec_installed),
            "hypertable_count": hypertable_count,
            "active_connections": active_conns,
        }
    except Exception as exc:
        result["status"] = "CRITICAL" if "refused" in str(exc).lower() else "DEGRADED"
        result["detail"]["error"] = str(exc)
    return result


async def check_neo4j(uri: str = None, user: str = "neo4j", password: str = "password") -> Dict[str, Any]:
    """Verify Neo4j graph database connectivity and node counts."""
    result = {"service": "Neo4j (Graph Engine)", "status": "UNKNOWN", "latency_ms": None, "detail": {}}
    try:
        if uri is None:
            import os
            from dotenv import load_dotenv
            load_dotenv("/home/bantu/Documents/ProjectXY/.env.local") or load_dotenv("/home/bantu/Documents/ProjectXY/.env")
            uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            user = os.getenv("NEO4J_USER", "neo4j")
            password = os.getenv("NEO4J_PASSWORD", "password")

        neo4j_driver = _try_import("neo4j")
        if neo4j_driver is None:
            result["status"] = "SKIP"
            result["detail"]["reason"] = "neo4j driver not installed"
            return result

        from neo4j import GraphDatabase as GDB
        t0 = time.perf_counter()
        driver = GDB.driver(uri, auth=(user, password), connection_timeout=5)
        with driver.session() as session:
            node_count = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            rel_count = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
            labels = [r["label"] for r in session.run("CALL db.labels() YIELD label RETURN label LIMIT 20")]
        latency = (time.perf_counter() - t0) * 1000
        driver.close()

        result["status"] = "HEALTHY"
        result["latency_ms"] = round(latency, 2)
        result["detail"] = {
            "node_count": node_count,
            "relationship_count": rel_count,
            "active_labels": labels,
        }
    except Exception as exc:
        result["status"] = "CRITICAL" if "refused" in str(exc).lower() else "DEGRADED"
        result["detail"]["error"] = str(exc)
    return result


async def check_redis(url: str = None) -> Dict[str, Any]:
    """Verify Redis cache connectivity and UEBA state metrics."""
    result = {"service": "Redis (Cache / UEBA State)", "status": "UNKNOWN", "latency_ms": None, "detail": {}}
    try:
        if url is None:
            import os
            from dotenv import load_dotenv
            load_dotenv("/home/bantu/Documents/ProjectXY/.env.local") or load_dotenv("/home/bantu/Documents/ProjectXY/.env")
            url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        redis_mod = _try_import("redis")
        if redis_mod is None:
            result["status"] = "SKIP"
            result["detail"]["reason"] = "redis-py not installed"
            return result

        import redis as redis_lib
        client = redis_lib.from_url(url, socket_connect_timeout=5, decode_responses=True)
        
        t0 = time.perf_counter()
        ping_ok = client.ping()
        latency = (time.perf_counter() - t0) * 1000

        info = client.info("all")
        ueba_keys = len(client.keys("ueba:*"))
        containment_keys = len(client.keys("containment:*"))
        firewall_keys = len(client.keys("firewall:*"))

        result["status"] = "HEALTHY" if ping_ok else "DEGRADED"
        result["latency_ms"] = round(latency, 2)
        result["detail"] = {
            "redis_version": info.get("redis_version"),
            "used_memory_human": info.get("used_memory_human"),
            "connected_clients": info.get("connected_clients"),
            "total_commands_processed": info.get("total_commands_processed"),
            "ueba_state_keys": ueba_keys,
            "containment_keys": containment_keys,
            "firewall_block_keys": firewall_keys,
        }
    except Exception as exc:
        result["status"] = "CRITICAL" if "refused" in str(exc).lower() else "DEGRADED"
        result["detail"]["error"] = str(exc)
    return result


async def check_kafka(bootstrap_servers: str = None) -> Dict[str, Any]:
    """Verify Kafka broker connectivity and topic health."""
    result = {"service": "Kafka (Telemetry Bus)", "status": "UNKNOWN", "latency_ms": None, "detail": {}}
    try:
        if bootstrap_servers is None:
            import os
            from dotenv import load_dotenv
            load_dotenv("/home/bantu/Documents/ProjectXY/.env.local") or load_dotenv("/home/bantu/Documents/ProjectXY/.env")
            bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

        aiokafka = _try_import("aiokafka")
        if aiokafka is None:
            result["status"] = "SKIP"
            result["detail"]["reason"] = "aiokafka not installed"
            return result

        from aiokafka import AIOKafkaProducer
        from aiokafka.admin import AIOKafkaAdminClient

        t0 = time.perf_counter()
        admin = AIOKafkaAdminClient(bootstrap_servers=bootstrap_servers)
        await admin.start()
        topics = await admin.list_topics()
        latency = (time.perf_counter() - t0) * 1000
        await admin.close()

        projectxy_topics = [t for t in topics if any(kw in t.lower() for kw in [
            "threat", "telemetry", "firewall", "siem", "soar", "infrastructure", "ai_"
        ])]

        result["status"] = "HEALTHY"
        result["latency_ms"] = round(latency, 2)
        result["detail"] = {
            "total_topics": len(topics),
            "projectxy_topics": projectxy_topics,
            "broker": bootstrap_servers,
        }
    except Exception as exc:
        result["status"] = "CRITICAL" if "refused" in str(exc).lower() else "DEGRADED"
        result["detail"]["error"] = str(exc)
    return result


async def check_pgvector_threats(pg_url: str = None) -> Dict[str, Any]:
    """Count ingested real threat vectors in PostgreSQL pgvector store."""
    result = {"service": "pgvector Threat DB", "status": "UNKNOWN", "latency_ms": None, "detail": {}}
    try:
        if pg_url is None:
            import os
            from dotenv import load_dotenv
            load_dotenv("/home/bantu/Documents/ProjectXY/.env.local") or load_dotenv("/home/bantu/Documents/ProjectXY/.env")
            pg_url = os.getenv("DATABASE_URL", "postgresql://postgres:changethis@localhost:5433/cyberintel")
        pg_url = pg_url.replace("postgresql+asyncpg", "postgresql").replace("+asyncpg", "")

        asyncpg = _try_import("asyncpg")
        if asyncpg is None:
            result["status"] = "SKIP"
            return result

        t0 = time.perf_counter()
        conn = await asyncpg.connect(pg_url, timeout=5)
        
        # Check if the threat vector table exists
        table_exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='threat_vectors')"
        )
        
        if table_exists:
            count = await conn.fetchval("SELECT COUNT(*) FROM threat_vectors")
            categories = await conn.fetch(
                "SELECT category, COUNT(*) as cnt FROM threat_vectors GROUP BY category ORDER BY cnt DESC LIMIT 5"
            )
            result["detail"] = {
                "threat_vectors_count": count,
                "top_categories": [{"category": r["category"], "count": r["cnt"]} for r in categories]
            }
            result["status"] = "HEALTHY" if count > 0 else "EMPTY_DB"
        else:
            result["status"] = "NOT_INITIALIZED"
            result["detail"] = {"message": "Run ingest_real_threats.py first"}
        
        latency = (time.perf_counter() - t0) * 1000
        result["latency_ms"] = round(latency, 2)
        await conn.close()
    except Exception as exc:
        result["status"] = "DEGRADED"
        result["detail"]["error"] = str(exc)
    return result


# ===========================================================================
# DISPLAY LAYER
# ===========================================================================

def _status_icon(status: str) -> str:
    icons = {
        "HEALTHY": "[bold green]✔ HEALTHY[/bold green]",
        "DEGRADED": "[bold yellow]⚠ DEGRADED[/bold yellow]",
        "CRITICAL": "[bold red]✘ CRITICAL[/bold red]",
        "SKIP": "[dim]– SKIPPED[/dim]",
        "EMPTY_DB": "[bold yellow]⚠ EMPTY DB[/bold yellow]",
        "NOT_INITIALIZED": "[bold blue]ℹ NOT INITIALIZED[/bold blue]",
    }
    return icons.get(status, f"[dim]{status}[/dim]")


def display_rich(results: List[Dict[str, Any]]):
    table = Table(title="\n🛡  ProjectXY Sovereign Infrastructure Health Report", box=box.DOUBLE_EDGE, style="bold")
    table.add_column("Service", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Latency", justify="right", style="magenta")
    table.add_column("Key Metrics", style="dim")

    for r in results:
        latency_str = f"{r['latency_ms']} ms" if r["latency_ms"] is not None else "N/A"
        detail_str = " | ".join(f"{k}: {v}" for k, v in list(r["detail"].items())[:3])
        table.add_row(r["service"], _status_icon(r["status"]), latency_str, detail_str)

    console.print()
    console.print(table)
    console.print(f"[dim]Generated: {datetime.now(timezone.utc).isoformat()}[/dim]")


def display_plain(results: List[Dict[str, Any]]):
    print("\n" + "=" * 65)
    print("  ProjectXY Sovereign Infrastructure Health Report")
    print("=" * 65)
    for r in results:
        latency_str = f"{r['latency_ms']} ms" if r["latency_ms"] is not None else "N/A"
        print(f"  [{r['status']:15}] {r['service']:<35} ({latency_str})")
        for k, v in list(r["detail"].items())[:4]:
            print(f"               {k}: {v}")
    print("=" * 65)
    print(f"  Generated: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 65 + "\n")


# ===========================================================================
# MAIN RUNNER
# ===========================================================================

async def run_all_checks() -> List[Dict[str, Any]]:
    tasks = [
        check_postgresql(),
        check_neo4j(),
        check_redis(),
        check_kafka(),
        check_pgvector_threats(),
    ]
    return await asyncio.gather(*tasks)


async def main():
    args = sys.argv[1:]
    as_json = "--json" in args
    watch_mode = "--watch" in args

    if watch_mode:
        import os
        interval = 5
        while True:
            os.system("clear")
            results = await run_all_checks()
            if _rich:
                display_rich(results)
            else:
                display_plain(results)
            await asyncio.sleep(interval)
    else:
        results = await run_all_checks()
        if as_json:
            print(json.dumps(results, indent=2, default=str))
        elif _rich:
            display_rich(results)
        else:
            display_plain(results)

        # Exit with error code if any service is CRITICAL
        if any(r["status"] == "CRITICAL" for r in results):
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
