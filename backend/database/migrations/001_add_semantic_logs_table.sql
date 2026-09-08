-- ============================================================
-- ProjectXY Cognitive Shield — DB Migration
-- Layer 4: Semantic Logs Table for Forensic AI Observability
-- ============================================================
-- Run this migration AFTER TimescaleDB is available.
-- Requires: pgvector extension

-- 1. Enable pgvector (already installed by setup_ai_firewall.sh)
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create the semantic_logs hypertable
CREATE TABLE IF NOT EXISTS semantic_logs (
    id              UUID            DEFAULT gen_random_uuid()   NOT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    -- Multi-tenant context
    tenant_id       TEXT            NOT NULL,
    entity_id       TEXT            NOT NULL,
    session_id      TEXT,

    -- Request fingerprint
    prompt_hash     TEXT,                     -- SHA-256 of original prompt

    -- Threat scoring
    threat_score    FLOAT4          NOT NULL DEFAULT 0.0,
    action          TEXT            NOT NULL DEFAULT 'PASS',   -- PASS|WARN|BLOCK|SCRUB_AND_PASS

    -- Classification
    intent_classification   TEXT,
    dominant_signal         TEXT,

    -- Cleansing transformer output
    transformations_applied JSONB   DEFAULT '[]',

    -- Multi-stage attack detection
    multi_stage_flag        BOOLEAN DEFAULT FALSE,
    attack_pattern          TEXT,             -- MODEL_INVERSION|PROMPT_CHAINING|VELOCITY_ESCALATION

    -- Semantic vector (384-dim, matches all-MiniLM-L6-v2 used in LLMFirewall)
    embedding       VECTOR(384),

    -- Constraint
    PRIMARY KEY (id, created_at)
);

-- 3. Convert to TimescaleDB hypertable (partitioned by time)
--    This is idempotent — safe to run multiple times
SELECT create_hypertable(
    'semantic_logs',
    'created_at',
    if_not_exists => TRUE,
    migrate_data => TRUE
);

-- 4. TimescaleDB compression policy (compress chunks older than 30 days)
SELECT add_compression_policy(
    'semantic_logs',
    INTERVAL '30 days',
    if_not_exists => TRUE
);

-- 5. Retention policy (7 years for compliance tenants — configurable)
--    We use a generous 2555 days (~7 years) as the default.
SELECT add_retention_policy(
    'semantic_logs',
    INTERVAL '2555 days',
    if_not_exists => TRUE
);

-- 6. IVFFlat index for vector similarity search
--    lists=100 is optimal for ~1M rows. Adjust for production volume.
CREATE INDEX IF NOT EXISTS semantic_logs_embedding_idx
    ON semantic_logs USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- 7. B-tree indexes for common filter queries
CREATE INDEX IF NOT EXISTS semantic_logs_tenant_time_idx
    ON semantic_logs (tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS semantic_logs_entity_idx
    ON semantic_logs (entity_id, tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS semantic_logs_action_score_idx
    ON semantic_logs (action, threat_score DESC)
    WHERE threat_score > 0.5;

CREATE INDEX IF NOT EXISTS semantic_logs_multi_stage_idx
    ON semantic_logs (tenant_id, multi_stage_flag, created_at DESC)
    WHERE multi_stage_flag = TRUE;

-- 8. Row-Level Security (RLS) for multi-tenant isolation
ALTER TABLE semantic_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY semantic_logs_tenant_isolation
    ON semantic_logs
    USING (tenant_id = current_setting('app.current_tenant', TRUE));

-- 9. Grant access to the backend application role
GRANT SELECT, INSERT ON semantic_logs TO projectxy_backend;

-- ============================================================
-- Verify the migration
-- ============================================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'semantic_logs'
    ) THEN
        RAISE NOTICE '[OK] semantic_logs table created successfully';
    ELSE
        RAISE EXCEPTION '[FAIL] semantic_logs table was not created';
    END IF;
END
$$;

-- ============================================================
-- Layer 4 Forensic Views for the Dashboard
-- ============================================================

-- View: Recent threat summary (last 24h, by tenant)
CREATE OR REPLACE VIEW v_threat_summary_24h AS
SELECT
    tenant_id,
    COUNT(*)                                            AS total_interactions,
    SUM(CASE WHEN action = 'BLOCK' THEN 1 ELSE 0 END)  AS total_blocks,
    SUM(CASE WHEN action = 'WARN' THEN 1 ELSE 0 END)   AS total_warns,
    SUM(CASE WHEN action = 'SCRUB_AND_PASS' THEN 1 ELSE 0 END) AS total_scrubs,
    AVG(threat_score)::FLOAT4                           AS avg_threat_score,
    MAX(threat_score)::FLOAT4                           AS max_threat_score,
    SUM(CASE WHEN multi_stage_flag THEN 1 ELSE 0 END)  AS multi_stage_detections,
    COUNT(DISTINCT entity_id)                           AS unique_entities
FROM semantic_logs
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY tenant_id;

-- View: Attack pattern frequency
CREATE OR REPLACE VIEW v_attack_patterns_7d AS
SELECT
    tenant_id,
    attack_pattern,
    COUNT(*)                        AS occurrence_count,
    AVG(threat_score)::FLOAT4       AS avg_threat_score,
    MAX(created_at)                 AS last_seen
FROM semantic_logs
WHERE created_at >= NOW() - INTERVAL '7 days'
  AND attack_pattern IS NOT NULL
GROUP BY tenant_id, attack_pattern
ORDER BY occurrence_count DESC;

COMMENT ON TABLE semantic_logs IS
    'ProjectXY Cognitive Shield Layer 4: Forensic AI Observability.
     Stores 384-dim semantic embeddings of all flagged LLM interactions.
     Enables retroactive threat hunting via pgvector cosine similarity.
     TimescaleDB hypertable: compressed after 30 days, retained 7 years.';
