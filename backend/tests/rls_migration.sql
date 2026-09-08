-- ──────────────────────────────────────────────────────────────────────────
-- Sovereign Enterprise Fortress - PostgreSQL RLS Migration
-- ──────────────────────────────────────────────────────────────────────────
-- Objective: Enforce pure Multi-Tenant Isolation using Row-Level Security.
-- Every interaction must be scoped to the specific `org_id` injected via the JWT.
-- ──────────────────────────────────────────────────────────────────────────

-- 1. Ensure all tables have an org_id column
ALTER TABLE users ADD COLUMN IF NOT EXISTS org_id UUID NOT NULL;
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS org_id UUID NOT NULL;
ALTER TABLE logs ADD COLUMN IF NOT EXISTS org_id UUID NOT NULL;
ALTER TABLE events ADD COLUMN IF NOT EXISTS org_id UUID NOT NULL;

-- 2. Define standard Sovereign Roles
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sovereign_admin') THEN
        CREATE ROLE sovereign_admin;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sovereign_analyst') THEN
        CREATE ROLE sovereign_analyst;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sovereign_executive') THEN
        CREATE ROLE sovereign_executive;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sovereign_auditor') THEN
        CREATE ROLE sovereign_auditor;
    END IF;
END
$$;

-- 3. Enable RLS on core tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;

-- 4. Create RLS Policies using current_setting('app.current_org_id')
-- Assume that the FastAPI middleware executes: SET LOCAL app.current_org_id = 'the-org-id';

-- Users Policy
CREATE POLICY isolation_users ON users
    FOR ALL
    USING (org_id = NULLIF(current_setting('app.current_org_id', true), '')::UUID);

-- Nodes Policy
CREATE POLICY isolation_nodes ON nodes
    FOR ALL
    USING (org_id = NULLIF(current_setting('app.current_org_id', true), '')::UUID);

-- Logs Policy (Executives and Auditors can READ only)
CREATE POLICY isolation_logs_read ON logs
    FOR SELECT
    USING (org_id = NULLIF(current_setting('app.current_org_id', true), '')::UUID);

CREATE POLICY isolation_logs_write ON logs
    FOR INSERT
    WITH CHECK (org_id = NULLIF(current_setting('app.current_org_id', true), '')::UUID AND current_user IN ('sovereign_admin', 'sovereign_analyst'));

-- Ensure Admins cannot delete immutable logs
CREATE OR REPLACE FUNCTION prevent_audit_deletion()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Immutable Ledger Error: Deleting audit logs is strictly prohibited by sovereign system policy.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_log_delete ON logs;
CREATE TRIGGER trg_prevent_log_delete
BEFORE DELETE ON logs
FOR EACH ROW EXECUTE FUNCTION prevent_audit_deletion();

-- 5. Force RLS for table owners (optional but highly recommended for extreme security)
ALTER TABLE users FORCE ROW LEVEL SECURITY;
ALTER TABLE nodes FORCE ROW LEVEL SECURITY;
ALTER TABLE logs FORCE ROW LEVEL SECURITY;
ALTER TABLE events FORCE ROW LEVEL SECURITY;

SELECT 'RLS Multi-Tenant Migration successfully applied for Sovereign Enterprise isolation.' AS migration_status;
