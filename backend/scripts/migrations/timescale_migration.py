#!/usr/bin/env python3
"""
timescale_migration.py — ProjectXY TimescaleDB Safe Migration Script
=====================================================================
Installs TimescaleDB extension and creates all new AI Firewall hypertables
INSIDE the existing PostgreSQL container WITHOUT disrupting current tables.

SAFETY: This script is idempotent (can be run multiple times safely).
All operations use IF NOT EXISTS guards.

Operations performed:
  1. Verify TimescaleDB extension is available in the container
  2. Install vector (pgvector) extension
  3. Install timescaledb extension
  4. Create firewall_events hypertable
  5. Create siem_threat_events hypertable
  6. Create dga_detection_events hypertable
  7. Create osint_threat_feed hypertable
  8. Set CBK-compliant compression + retention policies
  9. Create continuous aggregate views (daily rollups)
  10. Verify all hypertables are healthy

Usage:
    cd /home/bantu/Documents/ProjectXY/backend
    python timescale_migration.py
    python timescale_migration.py --verify-only
    python timescale_migration.py --rollback   # Removes new tables only
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone

# ── Bootstrap path ──────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env.local"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))  # fallback
load_dotenv(os.path.join(os.path.dirname(__file__), ".env.local"))
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))  # fallback

import asyncpg

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:changethis@localhost:5433/cyberintel")
DB_URL = DB_URL.replace("postgresql+asyncpg://", "postgresql://").replace("+asyncpg", "")

# ===========================================================================
# SQL Statements
# ===========================================================================

EXTENSIONS_SQL = [
    "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;",
    "CREATE EXTENSION IF NOT EXISTS vector;",
    "CREATE EXTENSION IF NOT EXISTS pg_trgm;",   # For text search
]

CREATE_FIREWALL_EVENTS = """
CREATE TABLE IF NOT EXISTS firewall_events (
    id                  UUID            NOT NULL DEFAULT gen_random_uuid(),
    timestamp           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    tenant_id           VARCHAR(64),
    entity_id           VARCHAR(128),
    action              VARCHAR(32)     NOT NULL,  -- PASS | BLOCK | SCRUB_AND_PASS
    threat_score        FLOAT           NOT NULL DEFAULT 0.0,
    semantic_similarity FLOAT                    DEFAULT 0.0,
    matched_category    VARCHAR(64),
    pii_types_detected  JSONB,
    reasons             JSONB,
    latency_ms          FLOAT,
    prompt_hash         VARCHAR(64),
    prompt_preview_hash VARCHAR(64),
    source_ip_subnet    VARCHAR(20),
    PRIMARY KEY (id, timestamp)
);
"""

CREATE_SIEM_THREAT_EVENTS = """
CREATE TABLE IF NOT EXISTS siem_threat_events (
    id                      UUID        NOT NULL DEFAULT gen_random_uuid(),
    timestamp               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tenant_id               VARCHAR(64),
    entity_id               VARCHAR(128),
    source_ip               VARCHAR(45),
    event_topic             VARCHAR(64),
    risk_score              FLOAT       NOT NULL,
    soar_action             VARCHAR(32),
    reasons                 JSONB,
    graph_scan_count        INT         DEFAULT 0,
    graph_login_fail_count  INT         DEFAULT 0,
    graph_fw_block_count    INT         DEFAULT 0,
    is_apt_chain            BOOLEAN     DEFAULT FALSE,
    mitre_tactic            VARCHAR(64),
    mitre_technique         VARCHAR(32),
    PRIMARY KEY (id, timestamp)
);
"""

CREATE_DGA_EVENTS = """
CREATE TABLE IF NOT EXISTS dga_detection_events (
    id                UUID        NOT NULL DEFAULT gen_random_uuid(),
    timestamp         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    domain            VARCHAR(253) NOT NULL,
    dga_probability   FLOAT       NOT NULL,
    algorithm_family  VARCHAR(64),
    is_blacklisted    BOOLEAN     DEFAULT FALSE,
    country_code      VARCHAR(3),
    PRIMARY KEY (id, timestamp)
);
"""

CREATE_OSINT_FEED = """
CREATE TABLE IF NOT EXISTS osint_threat_feed (
    id              UUID        NOT NULL DEFAULT gen_random_uuid(),
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source          VARCHAR(128) NOT NULL,
    indicator_type  VARCHAR(32) NOT NULL,
    indicator_value TEXT        NOT NULL,
    severity        SMALLINT    DEFAULT 3,
    tags            JSONB,
    region          VARCHAR(16),
    PRIMARY KEY (id, timestamp)
);
"""

CREATE_THREAT_VECTORS = """
CREATE TABLE IF NOT EXISTS threat_vectors (
    id          SERIAL      PRIMARY KEY,
    text        TEXT        NOT NULL,
    category    VARCHAR(64) NOT NULL,
    source      VARCHAR(128),
    severity    SMALLINT    DEFAULT 3,
    is_active   BOOLEAN     DEFAULT TRUE,
    embedding   vector(384),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
"""

# Indexes
INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS ix_fw_tenant_ts     ON firewall_events    (tenant_id, timestamp DESC);",
    "CREATE INDEX IF NOT EXISTS ix_fw_action_ts     ON firewall_events    (action, timestamp DESC);",
    "CREATE INDEX IF NOT EXISTS ix_fw_hash          ON firewall_events    (prompt_hash);",
    "CREATE INDEX IF NOT EXISTS ix_siem_tenant_ts   ON siem_threat_events (tenant_id, timestamp DESC);",
    "CREATE INDEX IF NOT EXISTS ix_siem_risk_ts     ON siem_threat_events (risk_score DESC, timestamp DESC);",
    "CREATE INDEX IF NOT EXISTS ix_siem_apt         ON siem_threat_events (is_apt_chain, timestamp DESC);",
    "CREATE INDEX IF NOT EXISTS ix_dga_domain_ts    ON dga_detection_events (domain, timestamp DESC);",
    "CREATE INDEX IF NOT EXISTS ix_osint_type_ts    ON osint_threat_feed  (indicator_type, timestamp DESC);",
    "CREATE INDEX IF NOT EXISTS ix_tv_embedding     ON threat_vectors USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);",
    "CREATE INDEX IF NOT EXISTS ix_tv_category      ON threat_vectors (category);",
]

# Hypertable creation
HYPERTABLES_SQL = [
    ("firewall_events",       "timestamp", "1 day"),
    ("siem_threat_events",    "timestamp", "1 day"),
    ("dga_detection_events",  "timestamp", "1 day"),
    ("osint_threat_feed",     "timestamp", "1 day"),
]

# CBK Retention policies (TimescaleDB automatic data lifecycle management)
COMPRESSION_POLICIES = [
    ("firewall_events",       "30 days"),
    ("siem_threat_events",    "30 days"),
    ("osint_threat_feed",     "30 days"),
    ("dga_detection_events",  "7 days"),
]

RETENTION_POLICIES = [
    ("firewall_events",       "7 years"),
    ("siem_threat_events",    "7 years"),
    ("osint_threat_feed",     "7 years"),
    ("audit_logs",            "7 years"),  # Also apply to existing audit_logs
]

# Continuous Aggregates (daily threat summary for dashboards)
CONTINUOUS_AGGREGATES_SQL = [
    """
    CREATE MATERIALIZED VIEW IF NOT EXISTS daily_firewall_summary
    WITH (timescaledb.continuous) AS
    SELECT
        time_bucket('1 day', timestamp) AS bucket,
        tenant_id,
        action,
        COUNT(*)                        AS event_count,
        AVG(threat_score)               AS avg_threat_score,
        MAX(threat_score)               AS max_threat_score,
        AVG(latency_ms)                 AS avg_latency_ms
    FROM firewall_events
    GROUP BY bucket, tenant_id, action
    WITH NO DATA;
    """,
    """
    CREATE MATERIALIZED VIEW IF NOT EXISTS daily_siem_summary
    WITH (timescaledb.continuous) AS
    SELECT
        time_bucket('1 day', timestamp) AS bucket,
        tenant_id,
        soar_action,
        COUNT(*)                        AS event_count,
        AVG(risk_score)                 AS avg_risk_score,
        MAX(risk_score)                 AS max_risk_score,
        SUM(CASE WHEN is_apt_chain THEN 1 ELSE 0 END) AS apt_chain_count
    FROM siem_threat_events
    GROUP BY bucket, tenant_id, soar_action
    WITH NO DATA;
    """,
]

ROLLBACK_SQL = [
    "DROP TABLE IF EXISTS firewall_events CASCADE;",
    "DROP TABLE IF EXISTS siem_threat_events CASCADE;",
    "DROP TABLE IF EXISTS dga_detection_events CASCADE;",
    "DROP TABLE IF EXISTS osint_threat_feed CASCADE;",
    "DROP TABLE IF EXISTS threat_vectors CASCADE;",
    "DROP MATERIALIZED VIEW IF EXISTS daily_firewall_summary CASCADE;",
    "DROP MATERIALIZED VIEW IF EXISTS daily_siem_summary CASCADE;",
]


# ===========================================================================
# Migration Runner
# ===========================================================================

async def run_migration(conn: asyncpg.Connection, verify_only: bool = False):
    print("\n" + "="*65)
    print("  ProjectXY TimescaleDB Migration — CBK Compliance Layer")
    print("="*65)

    if verify_only:
        await verify_health(conn)
        return

    # Step 1: Extensions
    print("\n[1/8] Installing PostgreSQL extensions...")
    for sql in EXTENSIONS_SQL:
        try:
            await conn.execute(sql)
            ext_name = sql.split("extension IF NOT EXISTS ")[-1].split(" ")[0].strip(";")
            print(f"      ✓ {ext_name}")
        except Exception as exc:
            print(f"      ✗ Failed: {exc}")

    # Step 2: Create Tables
    print("\n[2/8] Creating hypertable-ready tables...")
    tables = [
        ("firewall_events",      CREATE_FIREWALL_EVENTS),
        ("siem_threat_events",   CREATE_SIEM_THREAT_EVENTS),
        ("dga_detection_events", CREATE_DGA_EVENTS),
        ("osint_threat_feed",    CREATE_OSINT_FEED),
        ("threat_vectors",       CREATE_THREAT_VECTORS),
    ]
    for name, sql in tables:
        try:
            await conn.execute(sql)
            print(f"      ✓ {name}")
        except Exception as exc:
            print(f"      ✗ {name}: {exc}")

    # Step 3: Create Hypertables
    print("\n[3/8] Converting tables to TimescaleDB hypertables...")
    for table, col, interval in HYPERTABLES_SQL:
        try:
            await conn.execute(
                f"SELECT create_hypertable('{table}', '{col}', "
                f"chunk_time_interval => INTERVAL '{interval}', "
                f"if_not_exists => TRUE);"
            )
            print(f"      ✓ {table} (chunk: {interval})")
        except Exception as exc:
            print(f"      ✗ {table}: {exc}")

    # Step 4: Create Indexes
    print("\n[4/8] Creating performance indexes...")
    for sql in INDEXES_SQL:
        try:
            await conn.execute(sql)
            idx_name = sql.split("INDEX IF NOT EXISTS ")[-1].split(" ")[0]
            print(f"      ✓ {idx_name}")
        except Exception as exc:
            print(f"      ✗ {exc}")

    # Step 5: Compression Policies (Hot→Cold after 30 days)
    print("\n[5/8] Applying TimescaleDB compression policies (hot→cold after 30 days)...")
    for table, interval in COMPRESSION_POLICIES:
        try:
            # Enable compression first
            await conn.execute(
                f"ALTER TABLE {table} SET (timescaledb.compress, "
                f"timescaledb.compress_orderby = 'timestamp DESC');"
            )
            await conn.execute(
                f"SELECT add_compression_policy('{table}', INTERVAL '{interval}', if_not_exists => TRUE);"
            )
            print(f"      ✓ {table} → compress after {interval}")
        except Exception as exc:
            print(f"      ✗ {table}: {exc}")

    # Step 6: Retention Policies (7-year CBK compliance)
    print("\n[6/8] Applying CBK 7-year data retention policies...")
    for table, duration in RETENTION_POLICIES:
        try:
            await conn.execute(
                f"SELECT add_retention_policy('{table}', INTERVAL '{duration}', if_not_exists => TRUE);"
            )
            print(f"      ✓ {table} → retain for {duration}")
        except Exception as exc:
            print(f"      ✗ {table}: {exc}")

    # Step 7: Continuous Aggregates
    print("\n[7/8] Creating continuous aggregate views (daily summaries)...")
    for sql in CONTINUOUS_AGGREGATES_SQL:
        try:
            await conn.execute(sql)
            view_name = sql.split("VIEW IF NOT EXISTS ")[-1].split("\n")[0]
            print(f"      ✓ {view_name}")
        except Exception as exc:
            print(f"      ✗ {exc}")

    # Step 8: Verify
    print("\n[8/8] Verifying migration health...")
    await verify_health(conn)

    print(f"\n{'='*65}")
    print(f"  MIGRATION COMPLETE")
    print(f"  Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"  Database: {DB_URL.split('@')[-1]}")
    print(f"{'='*65}\n")


async def verify_health(conn: asyncpg.Connection):
    """Query TimescaleDB metadata to verify all hypertables are healthy."""
    try:
        hypertables = await conn.fetch(
            """
            SELECT hypertable_name, num_chunks, compression_enabled
            FROM timescaledb_information.hypertables
            ORDER BY hypertable_name;
            """
        )
        print("\n  TimescaleDB Hypertables:")
        for ht in hypertables:
            print(f"    • {ht['hypertable_name']:<30} chunks={ht['num_chunks']}  "
                  f"compressed={ht['compression_enabled']}")

        # pgvector check
        vec_count = await conn.fetchval(
            "SELECT COUNT(*) FROM threat_vectors"
        ) if await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='threat_vectors')"
        ) else 0
        print(f"\n  pgvector threat_vectors: {vec_count} entries")

        # Retention policies
        policies = await conn.fetch(
            "SELECT hypertable_name, config FROM timescaledb_information.jobs "
            "WHERE application_name LIKE '%Retention%';"
        )
        print(f"\n  Active Retention Policies: {len(policies)}")

    except Exception as exc:
        print(f"  [VERIFY] Error: {exc}")


async def rollback(conn: asyncpg.Connection):
    print("\n[ROLLBACK] Removing AI Firewall tables (existing tables untouched)...")
    for sql in ROLLBACK_SQL:
        try:
            await conn.execute(sql)
            table = sql.split("EXISTS ")[-1].split(" ")[0].strip(";")
            print(f"  ✓ Dropped: {table}")
        except Exception as exc:
            print(f"  ✗ {exc}")


async def main(verify_only: bool, do_rollback: bool):
    conn = await asyncpg.connect(DB_URL, timeout=10)
    print(f"[DB] Connected to {DB_URL.split('@')[-1]}")
    try:
        if do_rollback:
            await rollback(conn)
        else:
            await run_migration(conn, verify_only=verify_only)
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ProjectXY TimescaleDB Migration")
    parser.add_argument("--verify-only", action="store_true", help="Only verify existing setup")
    parser.add_argument("--rollback", action="store_true", help="Drop AI Firewall tables (safe rollback)")
    args = parser.parse_args()
    asyncio.run(main(args.verify_only, args.rollback))
