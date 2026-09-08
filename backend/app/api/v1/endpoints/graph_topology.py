"""
ProjectXY: Graph Threat Topology FastAPI Router
================================================
Exposes the Neo4j GraphRepository as a production-grade REST endpoint.
ABAC-gated. Returns structured JSON ready for the WebGL force-graph renderer.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, Dict, Any, List
from app.infrastructure.neo4j_repo.graph_repository import GraphRepository
from app.core.config import settings
from app.api.deps import get_current_user
from app.models.models import User, EntityDB
from app.infrastructure.session import SessionLocal

router = APIRouter(prefix="/graph", tags=["Threat Graph"])

def get_graph_repository() -> GraphRepository:
    """Dependency injection for the GraphRepository with connection settings."""
    return GraphRepository(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD
    )


@router.get(
    "/trace",
    summary="Patient Zero: Trace AI Agent Compromise Path",
    response_description="Dual-spectrum threat topology for WebGL rendering."
)
async def trace_agent_compromise(
    org_id: str = Query(..., description="Tenant org ID for strict multi-tenancy."),
    agent_id: str = Query(..., description="The AI Agent session_id under investigation."),
    current_user: User = Depends(get_current_user),
    repo: GraphRepository = Depends(get_graph_repository)
) -> Dict[str, Any]:
    """
    Executes the 'Patient Zero' Cypher query against Neo4j.
    Traverses: Infrastructure → User → AIAgent → Tool → DataAsset.
    Returns JSON-serializable node/link structure for react-force-graph-3d.
    """
    if current_user.tenant_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Org ID mismatch. Cross-tenant access denied."
        )

    try:
        result = await repo.trace_agent_compromise(
            org_id=org_id,
            agent_id=agent_id,
            caller_user_id=str(current_user.id),
            caller_role=current_user.role
        )

        if not result:
            return {
                "status": "clean",
                "message": f"No compromise topology detected for agent {agent_id}.",
                "nodes": [],
                "links": []
            }

        nodes: List[Dict[str, Any]] = [
            {"id": "infra_source", "label": f"IP: {result['threat_actor_ip']}", "type": "infrastructure", "severity": "critical"},
            {"id": "user_node", "label": f"User: {result['user_id']}", "type": "user", "severity": "warning"},
            {"id": "agent_node", "label": f"Agent Session: {result['agent_session']}", "type": "ai_agent", "severity": "critical"},
            {"id": "tool_node", "label": f"Tool Endpoint: {result['compromised_tool']}", "type": "tool", "severity": "critical"},
            {"id": "asset_target", "label": f"Asset: {result['targeted_asset']}", "type": "data_asset", "severity": "warning"}
        ]

        links: List[Dict[str, Any]] = [
            {"source": "infra_source", "target": "user_node", "type": "AUTHENTICATED_FROM", "weight": 1.0},
            {"source": "user_node", "target": "agent_node", "type": "INVOKED", "weight": 1.0},
            {"source": "agent_node", "target": "tool_node", "type": "EXECUTED", "weight": 1.0},
            {"source": "tool_node", "target": "asset_target", "type": "ACCESSED", "weight": 1.0}
        ]

        return {
            "status": "CRITICAL_COMPROMISE_DETECTED",
            "calculated_severity": result["calculated_severity"],
            "graph_payload": {
                "nodes": nodes,
                "links": links
            }
        }

    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph traversal failed: {str(e)}"
        )


# ─── UNIVERSAL LITE MODE GRAPH FALLBACK ADAPTER ───────────────────────────────

@router.get("/full")
async def get_universal_lite_graph(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Exposes a dynamic fallback mapping path for the front-end network graph views.
    Bypasses Neo4j in Lite Mode and structures Postgres rows directly into 3D node shapes.
    """
    db = SessionLocal()
    try:
        entities = db.query(EntityDB).all()
        nodes: List[Dict[str, Any]] = []
        links: List[Dict[str, Any]] = []

        # Convert records into reactive canvas shapes
        for ent in entities:
            severity_level = "critical" if ent.risk_score > 80 else "warning" if ent.risk_score > 50 else "info"
            nodes.append({
                "id": str(ent.id),
                "label": f"{ent.canonical_name}",
                "type": ent.type or "infrastructure",
                "severity": severity_level,
                "risk_score": ent.risk_score
            })

        # Link threat actor nodes explicitly to internal gateways to generate map layout links
        threats = [n for n in nodes if "threat_actor" in str(n["type"]).lower() or "ip" in str(n["type"]).lower()]
        assets = [n for n in nodes if n not in threats]

        for t in threats:
            for a in assets:
                links.append({
                    "source": t["id"],
                    "target": a["id"],
                    "type": "TARGETS",
                    "weight": 1.0
                })

        # Render out dual payload trees for both structural interface endpoints
        payload = {"nodes": nodes, "links": links}
        return {
            "status": "LITE_MODE_GRAPH_LOADED",
            "nodes": nodes,
            "links": links,
            "graph_payload": payload
        }
    except Exception as e:
        return {"status": "error", "detail": str(e), "nodes": [], "links": []}
    finally:
        db.close()
