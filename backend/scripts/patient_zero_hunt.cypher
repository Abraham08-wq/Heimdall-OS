MATCH (infra:Infrastructure {org_id: $org_id})-[auth:AUTHENTICATED_FROM]->(user:User {org_id: $org_id})
MATCH (user)-[invoke:INVOKED]->(agent:AIAgent {org_id: $org_id, session_id: $agent_id})
MATCH (agent)-[exec:EXECUTED]->(tool:Tool {org_id: $org_id})
MATCH (tool)-[access:ACCESSED]->(data:DataAsset {org_id: $org_id})
WHERE infra.risk_score > 75 AND tool.privilege_level = 'HIGH'
RETURN {
    threat_actor_ip: infra.ip_address,
    user_id: user.uuid,
    agent_session: agent.session_id,
    compromised_tool: tool.api_endpoint,
    targeted_asset: data.asset_name,
    calculated_severity: infra.risk_score + tool.criticality_modifier
} AS threat_topology
