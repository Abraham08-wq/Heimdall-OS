from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any

from app.infrastructure.graph import graph_db
from app.api.deps import get_current_user

router = APIRouter(prefix="/threat-actors", tags=["Threat Actors"])


def neo4j_to_force_graph(records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Converts a Neo4j graph query result into a format
    compatible with react-force-graph.
    """
    nodes = {}
    links = []

    for record in records:
        # Process every node and relationship dynamically returned in the cypher stream
        for key, value in record.items():
            if hasattr(value, 'id') and not hasattr(value, 'start_node'):  # It's a node
                node_id = str(value.id)
                if node_id not in nodes:
                    # Safely map fallback labels based on available Neo4j labels
                    node_labels = list(value.labels) if hasattr(value, 'labels') else ["Unknown Node"]
                    primary_label = node_labels[0] if node_labels else "Unknown Node"

                    # Extract descriptive properties safely from database row data
                    display_text = value.get("ip_address") or value.get("node_id") or value.get(
                        "gateway_name") or value.get("label") or primary_label

                    nodes[node_id] = {
                        "id": getattr(value, 'element_id', node_id),
                        "label": display_text,
                        "type": primary_label.lower(),
                        "severity": value.get("severity") or value.get("risk_level") or "warning",
                        **dict(value)  # Merges remaining true properties without duplication
                    }
            elif hasattr(value, 'start_node'):  # It's a relationship
                links.append({
                    "id": getattr(value, 'element_id', f"link_{value.id}"),
                    "source": value.start_node.element_id if hasattr(value.start_node, 'element_id') else str(
                        value.start_node.id),
                    "target": value.end_node.element_id if hasattr(value.end_node, 'element_id') else str(
                        value.end_node.id),
                    "type": value.type,
                    "weight": float(value.get("weight", 1.0))
                })

    return {"nodes": list(nodes.values()), "links": links}


@router.get("/topology-nodes")
async def get_live_correlated_topology(
        current_user: dict = Depends(get_current_user),
):
    """
    Phase 2 Core API Endpoint:
    Queries real-time relationship edges mapping regional attack vectors across
    Safaricom M-Pesa, Airtel Core Loops, and corporate infrastructure.
    """
    # High-utility cross-regional threat detection query string
    query = """
    MATCH (a:ThreatActor)-[r:LAUNCHED_ATTACK]->(e:EdgeNode)-[m:LATERAL_MOVEMENT]->(g:MobileMoneyGateway)
    RETURN a, r, e, m, g
    LIMIT 50
    """
    try:
        records = await graph_db.execute_query(query)

        if not records:
            return {"status": "EMPTY_STREAM", "nodes": [], "links": []}

        # Format the database payload using the clean helper logic
        formatted_graph = neo4j_to_force_graph(records)

        return {
            "status": "NEO4J_SOVEREIGN_ENGINE_ONLINE",
            "correlated_nodes_count": len(formatted_graph["nodes"]),
            "graph_payload": formatted_graph
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Real-time threat graph matrix calculation error: {str(e)}"
        )
