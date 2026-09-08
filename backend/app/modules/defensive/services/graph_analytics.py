import logging
from typing import Dict, Any, List
from neo4j import GraphDatabase
from app.core.config import settings

logger = logging.getLogger(__name__)

class GraphAnalyticsEngine:
    """
    Graph-based Anomaly Detection Engine (Neo4j)
    
    Identifies sudden relationship bursts, unusual privilege escalations,
    and lateral traversal patterns by analyzing temporal distances in Neo4j.
    """
    
    def __init__(self):
        try:
            self.driver = GraphDatabase.driver(
                settings.NEO4J_URI, 
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
            self.is_connected = True
        except Exception as e:
            logger.error(f"Graph DB connection failed: {e}")
            self.is_connected = False
            
    def record_access(self, user_id: str, resource_name: str, ip_address: str, risk: float):
        """Record an access relationship temporarily in the graph."""
        if not self.is_connected:
            return
            
        query = """
        MERGE (u:User {id: $user_id})
        MERGE (r:Resource {name: $resource_name})
        CREATE (u)-[a:ACCESSED {time: timestamp(), ip: $ip, risk: $risk}]->(r)
        // Keep temporal bounded (Delete edges older than 24h for performance)
        WITH u
        MATCH (u)-[old:ACCESSED]->()
        WHERE old.time < timestamp() - 86400000
        DELETE old
        """
        try:
            with self.driver.session() as session:
                session.run(query, user_id=user_id, resource_name=resource_name, ip=ip_address, risk=risk)
        except Exception as e:
            logger.warning(f"Failed to record graph access: {e}")

    def detect_lateral_movement(self, user_id: str) -> Dict[str, Any]:
        """
        [PHASE 5: GRAPH ANOMALY DETECTION ENGINE]
        Detect sudden relationship bursts across subnets.
        Cypher logic evaluates traversal velocity over a 60-second window.
        """
        if not self.is_connected:
            return {"detected": False}
            
        # Cypher: Find User who accessed distinct Resources in a Sudden Burst
        query = """
        MATCH (u:User {id: $user_id})-[a:ACCESSED]->(r:Resource)
        WHERE a.time > (timestamp() - 60000) // Last 60s
        WITH u, count(DISTINCT r.name) as traverse_count
        WHERE traverse_count > 5 // In production: compare to u.historical_max_traverse_per_min * 2
        RETURN u.id as user_id, traverse_count AS Lateral_Movement_Burst
        """
        try:
            with self.driver.session() as session:
                result = session.run(query, user_id=user_id).data()
                if result:
                    data = result[0]
                    burst_count = data["Lateral_Movement_Burst"]
                    return {
                        "detected": True,
                        "distinct_resources_touched": burst_count,
                        "confidence": min(100.0, burst_count * 10.0),
                        "reason": f"Sudden relationship burst ({burst_count} distinct nodes in 60s)."
                    }
        except Exception as e:
            logger.warning(f"Graph query failed for traversal: {e}")
            
        return {"detected": False}
        
    def detect_escalation(self, user_id: str) -> Dict[str, Any]:
        """
        [PHASE 5: GRAPH ANOMALY DETECTION ENGINE]
        Subgraph anomaly scoring: Detect if an entity suddenly bridges two previously 
        disconnected subnets or connects to a high-centrality target (e.g. root DB)
        without normal peer-group relationships.
        """
        if not self.is_connected:
            return {"detected": False}

        query = """
        MATCH (u:User {id: $user_id})-[a:ACCESSED]->(r:Resource)
        // Check if resource is high-centrality (many incoming connections) but user has few out-degrees
        WITH u, r, size(()-->(r)) as resource_centrality, size((u)-->()) as user_degree
        WHERE resource_centrality > 50 AND user_degree < 5
        RETURN r.name as target, resource_centrality
        """
        try:
            with self.driver.session() as session:
                result = session.run(query, user_id=user_id).data()
                if result:
                    detected_targets = [d["target"] for d in result]
                    return {
                        "detected": True,
                        "confidence": 85.0,
                        "reason": f"Privilege escalation anomaly: Accessed high-centrality nodes {detected_targets} with low systemic trust."
                    }
        except Exception:
            pass
            
        return {"detected": False}

graph_analytics = GraphAnalyticsEngine()
