-- Add missing columns to audit_logs
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS previous_hash VARCHAR(255);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS signature VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_audit_prev_hash ON audit_logs(previous_hash);
