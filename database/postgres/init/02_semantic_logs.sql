-- ============================================================
-- semantic_logs — ProjectXY Cognitive Shield Layer 4
-- pgvector (384-dim) + TimescaleDB hypertable
-- ============================================================

-- Ensure the vector extension is available (created by 01_enable_vector.sql)
CREATE EXTENSION IF NOT EXISTS vector;

-- Core semantic log table
CREATE TABLE IF NOT EXISTS semantic_logs (
    id                      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    tenant_id               TEXT            NOT NULL DEFAULT '',
    entity_id               TEXT            NOT NULL DEFAULT '',
    session_id              TEXT,
    prompt_hash             TEXT            NOT NULL DEFAULT '',
    threat_score            DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    action                  TEXT            NOT NULL DEFAULT 'PASS'
                                CHECK (action IN ('PASS', 'WARN', 'BLOCK', 'SCRUB_AND_PASS')),
    intent_classification   TEXT,
    dominant_signal         TEXT,
    transformations_applied JSONB           NOT NULL DEFAULT '[]',
    multi_stage_flag        BOOLEAN         NOT NULL DEFAULT FALSE,
    attack_pattern          TEXT,
    -- 384-dimensional sentence embedding (SentenceTransformer all-MiniLM-L6-v2)
    embedding               vector(384)
);

-- Make it a TimescaleDB hypertable partitioned by created_at
-- (graceful: does nothing if TimescaleDB extension is not installed)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'
    ) THEN
        PERFORM create_hypertable(
            'semantic_logs',
            'created_at',
            chunk_time_interval => INTERVAL '7 days',
            if_not_exists => TRUE
        );
    END IF;
EXCEPTION WHEN OTHERS THEN
    -- TimescaleDB may not be available in lite mode — continue without it
    RAISE NOTICE 'TimescaleDB hypertable creation skipped: %', SQLERRM;
END;
$$;

-- Indices for hot query paths
CREATE INDEX IF NOT EXISTS idx_semantic_logs_tenant_time
    ON semantic_logs (tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_semantic_logs_entity
    ON semantic_logs (entity_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_semantic_logs_action
    ON semantic_logs (action, created_at DESC)
    WHERE action IN ('BLOCK', 'WARN');

CREATE INDEX IF NOT EXISTS idx_semantic_logs_multi_stage
    ON semantic_logs (multi_stage_flag, created_at DESC)
    WHERE multi_stage_flag = TRUE;

-- IVFFlat index for vector cosine similarity search
-- (Built with 100 lists — tune to sqrt(row_count) after data grows)
CREATE INDEX IF NOT EXISTS idx_semantic_logs_embedding_cosine
    ON semantic_logs USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- ============================================================
-- siem_threat_events — SIEM / SOAR event log
-- Required by main.py WebSocket telemetry bootstrap
-- ============================================================

CREATE TABLE IF NOT EXISTS siem_threat_events (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    tenant_id       TEXT            NOT NULL DEFAULT '',
    entity_id       TEXT            NOT NULL DEFAULT '',
    source_ip       INET,
    risk_score      DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    soar_action     TEXT,
    is_apt_chain    BOOLEAN         NOT NULL DEFAULT FALSE,
    reasons         TEXT[],
    mitre_tactic    TEXT,
    raw_event       JSONB           NOT NULL DEFAULT '{}'
);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'
    ) THEN
        PERFORM create_hypertable(
            'siem_threat_events',
            'timestamp',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        );
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'siem_threat_events hypertable skipped: %', SQLERRM;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_siem_events_tenant_time
    ON siem_threat_events (tenant_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_siem_events_risk
    ON siem_threat_events (risk_score DESC, timestamp DESC);

DO $$ 
BEGIN 
    RAISE NOTICE 'semantic_logs and siem_threat_events tables ready.'; 
END $$;
