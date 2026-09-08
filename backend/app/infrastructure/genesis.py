import logging
import random
import uuid
from datetime import datetime, timedelta
from neo4j import GraphDatabase
from sqlalchemy.orm import Session
from app.models.models import EntityDB, AttributeDB, User
from app.core.config import settings

logger = logging.getLogger(__name__)

# --- Scenario Data ---
THREAT_ACTORS = [
    {"name": "Voltaic Typhoon", "type": "threat-actor", "risk": 95},
    {"name": "Hidden Cobra", "type": "threat-actor", "risk": 90},
    {"name": "Aquarium Fish", "type": "threat-actor", "risk": 45},
]

MALWARE = [
    {"name": "Ryuk Ransomware", "type": "malware", "risk": 98},
    {"name": "Emotet Loader", "type": "malware", "risk": 85},
    {"name": "Cobalt Strike Beacon", "type": "malware", "risk": 92},
]

INFRASTRUCTURE = [
    {"name": "192.168.1.105", "type": "ip", "risk": 20},
    {"name": "update-sys-kernel.com", "type": "domain", "risk": 75},
    {"name": "cdn-jquery-auth.net", "type": "domain", "risk": 80},
    {"name": "10.0.0.55", "type": "ip", "risk": 15},
]

RELATIONSHIPS = [
    ("Voltaic Typhoon", "USES", "Ryuk Ransomware"),
    ("Hidden Cobra", "USES", "Emotet Loader"),
    ("Ryuk Ransomware", "COMMUNICATES_WITH", "update-sys-kernel.com"),
    ("Emotet Loader", "COMMUNICATES_WITH", "cdn-jquery-auth.net"),
    ("Voltaic Typhoon", "TARGETS", "192.168.1.105"),
]

# --- Neo4j Driver ---
driver = GraphDatabase.driver(
    settings.NEO4J_URI,
    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
)


def create_entity_pg(db: Session, data: dict) -> EntityDB:
    """Create Entity in Postgres"""
    exists = db.query(EntityDB).filter(EntityDB.canonical_name == data["name"]).first()
    if exists:
        return exists

    entity = EntityDB(
        id=uuid.uuid4(),
        canonical_name=data["name"],
        type=data["type"],
        risk_score=data["risk"]
    )
    db.add(entity)
    db.commit()
    return entity


def create_node_neo4j(tx, name, type, id_str, risk):
    """Create Node in Neo4j"""
    query = (
        "MERGE (n:Entity {id: $id}) "
        "SET n.name = $name, n.type = $type, n.risk = $risk, n.group = 1"
    )
    tx.run(query, name=name, type=type, id=str(id_str), risk=risk)


def create_link_neo4j(tx, source_name, rel_type, target_name):
    """Create Relationship in Neo4j"""
    query = (
        "MATCH (a:Entity {name: $source}), (b:Entity {name: $target}) "
        "MERGE (a)-[r:RELATED_TO {type: $rel}]->(b)"
    )
    tx.run(query, source=source_name, target=target_name, rel=rel_type)


def sow_chaos(db: Session):
    """
    The Genesis Function: Populates the world with data.
    """
    logger.info("🔮 Casting Genesis Spell...")

    # 1. Create Entities
    all_entities = THREAT_ACTORS + MALWARE + INFRASTRUCTURE
    created_map = {}

    for item in all_entities:
        # Postgres
        pg_entity = create_entity_pg(db, item)
        created_map[item["name"]] = pg_entity

        # Neo4j
        with driver.session() as session:
            session.execute_write(create_node_neo4j, item["name"], item["type"], pg_entity.id, item["risk"])

    logger.info(f"✨ Created {len(created_map)} Entities in SQL & Graph.")

    # 2. Create Relationships
    with driver.session() as session:
        for source, rel, target in RELATIONSHIPS:
            session.execute_write(create_link_neo4j, source, rel, target)

    logger.info(f"🔗 Established {len(RELATIONSHIPS)} Graph Connections.")

    # 3. Add some random attributes
    # (Simplified for brevity)

    # FIX: Removed driver.close() to keep the connection open for subsequent seeding scripts
    # driver.close()

    logger.info("🧙‍♂️ Genesis Complete. The world is alive.")
