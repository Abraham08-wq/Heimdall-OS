"""
POSTGRESQL ROW-LEVEL SECURITY (RLS) FOR MULTI-TENANT ISOLATION
==============================================================

Enforces complete data isolation for international firms and government agencies
at the database layer. Each organization only sees its own threat intelligence.

RLS Policies:
- org_isolation_policy: Only access your organization's data
- intelligence_sensitivity: Role-based access to sensitive data
- government_compartment: Separate classification levels
"""

-- ============================================================================
-- ENABLE ROW LEVEL SECURITY
-- ============================================================================

ALTER TABLE threat_actors ENABLE ROW LEVEL SECURITY;
ALTER TABLE neural_signatures ENABLE ROW LEVEL SECURITY;
ALTER TABLE threat_vaccines ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE radar_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE incident_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE intelligence_queries ENABLE ROW LEVEL SECURITY;


-- ============================================================================
-- ORGANIZATION ISOLATION POLICIES
-- ============================================================================

-- Policy for threat_actors table
CREATE POLICY threat_actor_isolation ON threat_actors
USING (
    org_id = current_setting('app.current_org_id')::UUID
)
WITH CHECK (
    org_id = current_setting('app.current_org_id')::UUID
);

-- Policy for neural_signatures table
CREATE POLICY neural_sig_isolation ON neural_signatures
USING (
    org_id = current_setting('app.current_org_id')::UUID
)
WITH CHECK (
    org_id = current_setting('app.current_org_id')::UUID
);

-- Policy for threat_vaccines table
CREATE POLICY vaccine_isolation ON threat_vaccines
USING (
    -- Allow access to own vaccines OR shared vaccines from hive-mind
    org_id = current_setting('app.current_org_id')::UUID OR
    is_shared_via_hivemind = true
)
WITH CHECK (
    org_id = current_setting('app.current_org_id')::UUID
);

-- Policy for risk_assessments table
CREATE POLICY risk_assessment_isolation ON risk_assessments
USING (
    org_id = current_setting('app.current_org_id')::UUID
)
WITH CHECK (
    org_id = current_setting('app.current_org_id')::UUID
);

-- Policy for radar_assets table
CREATE POLICY radar_asset_isolation ON radar_assets
USING (
    -- Allow access to owned assets OR public scan results
    org_id = current_setting('app.current_org_id')::UUID OR
    asset_ownership = 'public'
)
WITH CHECK (
    org_id = current_setting('app.current_org_id')::UUID
);

-- Policy for incident_reports table
CREATE POLICY incident_isolation ON incident_reports
USING (
    org_id = current_setting('app.current_org_id')::UUID
)
WITH CHECK (
    org_id = current_setting('app.current_org_id')::UUID
);

-- Policy for intelligence_queries table (audit trail)
CREATE POLICY query_audit_isolation ON intelligence_queries
USING (
    org_id = current_setting('app.current_org_id')::UUID
)
WITH CHECK (
    org_id = current_setting('app.current_org_id')::UUID
);


-- ============================================================================
-- SENSITIVITY-BASED ACCESS CONTROL
-- ============================================================================

-- Only allow access to sensitive data if user has required clearance
CREATE POLICY threat_actor_sensitivity ON threat_actors
USING (
    CASE 
        WHEN sensitivity_level = 'public' THEN TRUE
        WHEN sensitivity_level = 'internal' THEN 
            current_user_role IN ('analyst', 'operator', 'commander')
        WHEN sensitivity_level = 'classified' THEN 
            current_user_role = 'commander' AND has_top_secret_clearance()
        ELSE FALSE
    END
)
WITH CHECK (
    CASE 
        WHEN sensitivity_level = 'public' THEN TRUE
        WHEN sensitivity_level = 'internal' THEN 
            current_user_role IN ('analyst', 'operator', 'commander')
        WHEN sensitivity_level = 'classified' THEN 
            current_user_role = 'commander' AND has_top_secret_clearance()
        ELSE FALSE
    END
);


-- ============================================================================
-- GOVERNMENT COMPARTMENTALIZATION
-- ============================================================================

-- For government agencies: NOFORN (Not For Foreign Nationals) compartment
CREATE POLICY government_noforn_compartment ON threat_actors
USING (
    CASE 
        WHEN compartment = 'NOFORN' THEN 
            org_type = 'government' AND is_us_cleared()
        WHEN compartment = 'NATO' THEN
            org_type = 'government' AND is_nato_member()
        WHEN compartment = 'EYES_ONLY' THEN
            org_type = 'government' AND current_user_role = 'commander'
        ELSE TRUE  -- Unclassified
    END
);


-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Set organization context for session
CREATE OR REPLACE FUNCTION set_org_context(org_id UUID)
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_org_id', org_id::text, false);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Check if user has top secret clearance
CREATE OR REPLACE FUNCTION has_top_secret_clearance()
RETURNS BOOLEAN AS $$
DECLARE
    user_id UUID;
    clearance_level VARCHAR;
BEGIN
    user_id := (current_setting('app.current_user_id')::UUID);
    
    SELECT cleared_level INTO clearance_level 
    FROM user_clearances 
    WHERE id = user_id AND expires_at > NOW();
    
    RETURN clearance_level IN ('top_secret', 'top_secret_sci');
END;
$$ LANGUAGE plpgsql;

-- Check if user is from US government
CREATE OR REPLACE FUNCTION is_us_cleared()
RETURNS BOOLEAN AS $$
DECLARE
    org_country VARCHAR;
BEGIN
    SELECT country INTO org_country 
    FROM organizations 
    WHERE id = current_setting('app.current_org_id')::UUID;
    
    RETURN org_country = 'United States';
END;
$$ LANGUAGE plpgsql;

-- Check if organization is NATO member
CREATE OR REPLACE FUNCTION is_nato_member()
RETURNS BOOLEAN AS $$
DECLARE
    org_type VARCHAR;
BEGIN
    SELECT alliance INTO org_type 
    FROM organizations 
    WHERE id = current_setting('app.current_org_id')::UUID;
    
    RETURN org_type = 'NATO';
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- AUDIT & COMPLIANCE LOGGING
-- ============================================================================

-- Create audit table
CREATE TABLE IF NOT EXISTS intelligence_audit_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL,
    user_id UUID NOT NULL,
    action VARCHAR NOT NULL,
    resource_type VARCHAR NOT NULL,
    resource_id UUID,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address INET,
    query_text TEXT,
    result VARCHAR  -- success, denied, error
);

-- Enable RLS on audit log
ALTER TABLE intelligence_audit_log ENABLE ROW LEVEL SECURITY;

-- Audit log policy - only see own organization's logs
CREATE POLICY audit_isolation ON intelligence_audit_log
USING (org_id = current_setting('app.current_org_id')::UUID)
WITH CHECK (org_id = current_setting('app.current_org_id')::UUID);

-- Automatic audit trigger
CREATE OR REPLACE FUNCTION audit_threat_actor_access()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO intelligence_audit_log (
        org_id, user_id, action, resource_type, resource_id,
        ip_address, query_text, result
    ) VALUES (
        current_setting('app.current_org_id')::UUID,
        current_setting('app.current_user_id')::UUID,
        TG_OP,
        'threat_actor',
        CASE WHEN TG_OP = 'DELETE' THEN OLD.actor_id ELSE NEW.actor_id END,
        inet_client_addr(),
        current_query(),
        'success'
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER threat_actor_audit
AFTER INSERT OR UPDATE OR DELETE ON threat_actors
FOR EACH ROW
EXECUTE FUNCTION audit_threat_actor_access();


-- ============================================================================
-- HIVE-MIND SHARING POLICIES
-- ============================================================================

-- Special policy for shared vaccines via Hive-Mind
CREATE POLICY hivemind_vaccine_sharing ON threat_vaccines
USING (
    -- Can see own vaccines
    org_id = current_setting('app.current_org_id')::UUID OR
    -- Can see shared vaccines from trusted nodes
    (is_shared_via_hivemind = true AND vaccine_source_trust_score > 0.8)
)
WITH CHECK (
    -- Can only modify own vaccines
    org_id = current_setting('app.current_org_id')::UUID
);


-- ============================================================================
-- FEDERATION POLICIES (Multi-organization Intelligence Sharing)
-- ============================================================================

-- For federated organizations (consortiums, information sharing groups)
CREATE TABLE IF NOT EXISTS organization_federation (
    federation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_a UUID NOT NULL REFERENCES organizations(id),
    org_b UUID NOT NULL REFERENCES organizations(id),
    sharing_level VARCHAR NOT NULL,  -- 'none', 'read_only', 'bidirectional'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);

-- Federation-aware policy for threat_actors
CREATE OR REPLACE FUNCTION can_access_via_federation(actor_org_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    current_org_id UUID;
    federation_level VARCHAR;
BEGIN
    current_org_id := current_setting('app.current_org_id')::UUID;
    
    IF actor_org_id = current_org_id THEN
        RETURN TRUE;
    END IF;
    
    SELECT sharing_level INTO federation_level
    FROM organization_federation
    WHERE (org_a = current_org_id AND org_b = actor_org_id
       OR org_a = actor_org_id AND org_b = current_org_id)
    AND expires_at IS NULL OR expires_at > NOW();
    
    RETURN federation_level IN ('read_only', 'bidirectional');
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- PERFORMANCE OPTIMIZATION
-- ============================================================================

-- Create indexes on org_id for faster RLS evaluation
CREATE INDEX CONCURRENTLY idx_threat_actors_org_id 
ON threat_actors(org_id) 
WHERE deleted_at IS NULL;

CREATE INDEX CONCURRENTLY idx_neural_signatures_org_id 
ON neural_signatures(org_id) 
WHERE deleted_at IS NULL;

CREATE INDEX CONCURRENTLY idx_threat_vaccines_org_id 
ON threat_vaccines(org_id) 
WHERE deleted_at IS NULL;

CREATE INDEX CONCURRENTLY idx_risk_assessments_org_id 
ON risk_assessments(org_id) 
WHERE deleted_at IS NULL;

CREATE INDEX CONCURRENTLY idx_radar_assets_org_id 
ON radar_assets(org_id) 
WHERE deleted_at IS NULL;


-- ============================================================================
-- PYTHON APPLICATION INTEGRATION
-- ============================================================================

"""
In your FastAPI application:

from sqlalchemy import text

class DatabaseService:
    async def set_organization_context(self, org_id: UUID, user_id: UUID):
        '''Set RLS context for the session'''
        async with self.engine.begin() as conn:
            await conn.execute(
                text(\"SELECT set_config('app.current_org_id', :org_id, false)\"),
                {'org_id': str(org_id)}
            )
            await conn.execute(
                text(\"SELECT set_config('app.current_user_id', :user_id, false)\"),
                {'user_id': str(user_id)}
            )

# In middleware:
@app.middleware("http")
async def set_rls_context(request: Request, call_next):
    # Get org_id and user_id from JWT token
    org_id = request.state.user_org_id
    user_id = request.state.user_id
    
    # Set RLS context for all database operations in this request
    await db.set_organization_context(org_id, user_id)
    
    response = await call_next(request)
    return response

# Now all database queries automatically filtered by org_id
# Example: This query will only return threat_actors from the user's organization
async def get_threat_actors():
    result = await db.session.execute(
        select(ThreatActor)
    )
    # RLS automatically filters to current_setting('app.current_org_id')
    return result.scalars().all()
"""

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Check RLS is enabled
SELECT tablename FROM pg_tables 
WHERE schemaname = 'public' 
AND rowsecurity = true;

-- Check RLS policies
SELECT tablename, policyname FROM pg_policies 
WHERE schemaname = 'public';

-- Test RLS (as different orgs)
SELECT set_config('app.current_org_id', 'org-1-uuid', false);
SELECT count(*) FROM threat_actors;  -- Should show only org-1's data

SELECT set_config('app.current_org_id', 'org-2-uuid', false);
SELECT count(*) FROM threat_actors;  -- Should show only org-2's data
