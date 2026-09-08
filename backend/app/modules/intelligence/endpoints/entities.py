from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api import deps
from app.schemas.entity import Entity, EntityCreate # Assuming EntityCreate exists or we use Entity
from app.models import models
from app.models.models import EntityDB, AttributeDB

router = APIRouter()

@router.get("/", response_model=List[Entity])
def read_entities(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    type: Optional[str] = None,
    current_user: models.User = Depends(deps.get_current_active_user),
):
    """
    Retrieve entities.
    """
    query = db.query(EntityDB)
    if type:
        query = query.filter(EntityDB.type == type)
    
    from sqlalchemy.orm import selectinload
    
    entities = query.options(selectinload(EntityDB.attributes)).offset(skip).limit(limit).all()
    # Pydantic's from_orm will handle conversion if configured
    return entities

@router.post("/", response_model=Entity)
def create_entity(
    *,
    db: Session = Depends(deps.get_db),
    entity_in: EntityCreate, # Using EntityCreate schema for input
    current_user: models.User = Depends(deps.get_current_active_user),
):
    """
    Create new entity.
    """
    # 1. Create DB Object
    db_entity = EntityDB(
        canonical_name=entity_in.canonical_name,
        type=entity_in.type.value, # Enum to str
        risk_score=entity_in.risk_score
    )
    db.add(db_entity)
    db.commit()
    db.refresh(db_entity)
    
    # 2. Add Attributes
    for attr in entity_in.attributes:
        db_attr = AttributeDB(
            entity_id=db_entity.id,
            type=attr.type.value,
            value=attr.value,
            confidence=attr.confidence,
            source=attr.evidence_refs[0] if attr.evidence_refs else "Unknown"
        )
        db.add(db_attr)
    
    db.commit()
    
    # TODO: Sync to Neo4j Graph (Async Task)
    
    return db_entity

@router.get("/{entity_id}", response_model=Entity)
def read_entity(
    entity_id: str,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
):
    """
    Get specific entity by ID.
    """
    from sqlalchemy.orm import selectinload
    entity = db.query(EntityDB).options(selectinload(EntityDB.attributes)).filter(EntityDB.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity
