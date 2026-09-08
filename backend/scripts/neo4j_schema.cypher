// ProjectXY: Neo4j Central Nervous System Schema Initialization
// Community Edition compatible — uses UNIQUENESS constraints in place of NODE KEY.
// Execution: docker exec -i projectxy-neo4j-1 cypher-shell -u neo4j -p <pass> < neo4j_schema.cypher

// ---------------------------------------------------------
// 1. Uniqueness Constraints (Multi-Tenancy Deduplication)
// ---------------------------------------------------------
CREATE CONSTRAINT user_uuid_unique IF NOT EXISTS
  FOR (u:User) REQUIRE u.uuid IS UNIQUE;

CREATE CONSTRAINT agent_session_unique IF NOT EXISTS
  FOR (a:AIAgent) REQUIRE a.session_id IS UNIQUE;

CREATE CONSTRAINT tool_endpoint_unique IF NOT EXISTS
  FOR (t:Tool) REQUIRE t.api_endpoint IS UNIQUE;

CREATE CONSTRAINT data_asset_id_unique IF NOT EXISTS
  FOR (d:DataAsset) REQUIRE d.asset_id IS UNIQUE;

CREATE CONSTRAINT threat_actor_uuid_unique IF NOT EXISTS
  FOR (t:ThreatActor) REQUIRE t.uuid IS UNIQUE;

// ---------------------------------------------------------
// 2. B-Tree Indexes for Multi-Tenant Graph Traversal
// Every query MUST anchor by org_id. These indexes make it sub-millisecond.
// ---------------------------------------------------------
CREATE INDEX infra_org_ip_idx IF NOT EXISTS
  FOR (i:Infrastructure) ON (i.org_id, i.ip_address);

CREATE INDEX user_org_idx IF NOT EXISTS
  FOR (u:User) ON (u.org_id);

CREATE INDEX agent_org_idx IF NOT EXISTS
  FOR (a:AIAgent) ON (a.org_id);

CREATE INDEX tool_org_idx IF NOT EXISTS
  FOR (t:Tool) ON (t.org_id);

CREATE INDEX data_asset_org_idx IF NOT EXISTS
  FOR (d:DataAsset) ON (d.org_id);

CREATE INDEX threat_org_idx IF NOT EXISTS
  FOR (t:ThreatActor) ON (t.org_id);
