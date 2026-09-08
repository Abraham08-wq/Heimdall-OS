import logging
from neo4j import AsyncGraphDatabase
from typing import Optional, Dict, Any, List
from app.core.abac import abac_evaluator

logger = logging.getLogger(__name__)


class GraphRepository:
    def __init__(self, uri: str, user: str, password: str):
        # Establish active production connection pool
        self.driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    async def close(self):
        await self.driver.close()

    async def fetch_live_threat_topology(self) -> Dict[str, Any]:
        """
        Phase 2 Real-Time Engine:
        Queries real-time relationship edges mapping regional attack vectors.
        Transforms raw Neo4j graph entities cleanly into visual node/edge arrays.
        """
        cypher_query = """
        MATCH (a:ThreatActor)-[r:LAUNCHED_ATTACK]->(e:EdgeNode)-[m:LATERAL_MOVEMENT]->(g:MobileMoneyGateway)
        RETURN a, r, e, m, g
        LIMIT 50
        """
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        seen_node_ids = set()

        try:
            async with self.driver.session() as session:
                result = await session.run(cypher_query)

                async for record in result:
                    actor_node = record["a"]
                    edge_node = record["e"]
                    gateway_node = record["g"]
                    launched_rel = record["r"]
                    lateral_rel = record["m"]

                    # Process Nodes safely (avoiding duplication)
                    node_mappings = [
                        (actor_node, "hostile_infrastructure"),
                        (edge_node, "perimeter_defense"),
                        (gateway_node, "internal_asset")
                    ]

                    for node, node_type in node_mappings:
                        n_id = node.element_id if hasattr(node, "element_id") else str(node.id)
                        if n_id not in seen_node_ids:
                            seen_node_ids.add(n_id)
                            nodes.append({
                                "id": n_id,
                                "label": node.get("label", node.get("ip_address", "Unknown Endpoint")),
                                "type": node_type,
                                "severity": node.get("severity", "warning")
                            })

                    # Process Relationships into visual edges
                    for rel in [launched_rel, lateral_rel]:
                        r_id = rel.element_id if hasattr(rel, "element_id") else str(rel.id)
                        src_id = rel.start_node.element_id if hasattr(rel.start_node, "element_id") else str(
                            rel.start_node.id)
                        tgt_id = rel.end_node.element_id if hasattr(rel.end_node, "element_id") else str(
                            rel.end_node.id)

                        edges.append({
                            "id": r_id,
                            "source": src_id,
                            "target": tgt_id,
                            "type": rel.type,
                            "weight": float(rel.get("weight", 1.0))
                        })

            return {
                "status": "NEO4J_SOVEREIGN_ENGINE_ONLINE",
                "correlated_nodes_count": len(nodes),
                "graph_payload": {
                    "nodes": nodes,
                    "edges": edges
                }
            }
        except Exception as e:
            logger.error(f"Live threat topology extraction failed: {str(e)}")
            raise

    async def trace_agent_compromise(
            self, org_id: str, agent_id: str, caller_user_id: str, caller_role: str
    ) -> Optional[Dict[str, Any]]:
        """Phase 3 Zero-Trust Agent Trace Gate"""
        has_clearance = await abac_evaluator.evaluate_access(
            user_id=caller_user_id, tenant_id=org_id, role=caller_role,
            action="view_topology",
            resource_attributes={"tenant_id": org_id, "type": "graph_data", "required_clearance": 2}
        )
        if not has_clearance:
            raise PermissionError("Insufficient clearance to execute threat topology trace.")

        cypher_query = """
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
        """
        try:
            async with self.driver.session() as session:
                result = await session.run(cypher_query, org_id=org_id, agent_id=agent_id)
                record = await result.single()
                return record["threat_topology"] if record else None
        except Exception as e:
            logger.error(f"Graph traversal failed: {str(e)}")
            raise
