from fastapi import APIRouter, HTTPException, status, Request, Query
from sys import maxsize
from app.schemas.telemetry import HoneypotTelemetryEvent, GeoIPData
from app.services.graph_tracking import GraphTrackingService
from typing import Optional
from datetime import datetime
import hmac, hashlib
from app.core.config import settings
from fastapi import Depends
from sqlalchemy.orm import Session
from app.api import deps
from app.services.ledger.worm_ledger import worm_ledger
from app.services.correlation_engine import correlation_engine
import uuid

router = APIRouter()

@router.post("/telemetry/honeypot", status_code=status.HTTP_202_ACCEPTED)
async def ingest_external_telemetry(
    event: HoneypotTelemetryEvent,
    request: Request
):
    """
    Ingest telemetry from the global Honeypot network (Hemisphere 1).
    This endpoint validates the incoming data and routes it to Neo4j.
    In a full production environment, this pushes directly to a Kafka topic.
    """
    # 1. Pydantic Model implicitly validates the IP and format (event parameter)

    # 2. Add to Immutable Ledger (Postgres)
    # Using a background task or synchronous call depending on architecture. For now, doing it synchronously.
    # We retrieve the db session from the request state or dependencies. 
    # Since this is a fast ingestion endpoint, we'll try to get it from deps.
    db = next(deps.get_db())
    try:
        await worm_ledger.append_event(
            db=db,
            actor_id=None, # System ingestion
            action="TELEMETRY_INGESTION",
            metadata=event.model_dump(),
            resource_type="HONEYPOT_EVENT",
            resource_id=event.event_id
        )
    except Exception as e:
        print(f"Failed to append to Immutable Ledger: {e}")

    # 3. Stream to Kafka for distributed processing by AI Swarms
    from app.infrastructure.kafka import kafka_streamer
    await kafka_streamer.emit_event("external_telemetry", event.model_dump())
    
    # 4. Directly update the Graph Mapping (Neo4j)
    try:
         await GraphTrackingService.ingest_honeypot_telemetry(event)
    except Exception as e:
         # Log loudly, but don't fail the ingestion 
         print(f"Failed to map to graph: {e}")
         raise HTTPException(status_code=500, detail="Graph ingestion failure")

    return {"status": "Accepted", "event_id": str(event.event_id)}

@router.get("/beacon/{payload}")
async def ingest_honeytoken_beacon(payload: str, sig: str, request: Request):
    """
    Ingests hits from our weaponized Honey-Tokens (e.g., tracking pixel in a document).
    """
    # 1. Verify Signature to prevent spoofing
    expected_sig = hmac.new(settings.JWT_SECRET_KEY.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(sig, expected_sig):
        raise HTTPException(status_code=403, detail="Invalid beacon signature")
        
    # 2. Extract Data
    client_ip = request.client.host if request.client else "UNKNOWN"
    
    # Payload format: DOC:filename:target_adversary
    parts = payload.split(":")
    token_type = parts[0] if len(parts) > 0 else "UNKNOWN"
    target = parts[2] if len(parts) > 2 else "UNKNOWN"
    
    print(f"[DECEPTION] Honey-Token triggered by {client_ip} for target {target}")
    
    # 3. Map to Graph (Mocking the event structure for brevity)
    if client_ip != "UNKNOWN":
        event = HoneypotTelemetryEvent(
            attacker_ip=client_ip,
            honeypot_name=f"Token-{token_type}",
            target_port=0,
            protocol="HTTP_BEACON",
            interaction_type="TOKEN_OPENED",
            details={"payload": payload}
        )
        try:
             await GraphTrackingService.ingest_honeypot_telemetry(event)
             
             # Calculate exact threat proximity to trigger ethical evidence-based scoring
             proximity = await correlation_engine.get_graph_proximity_to_threats(client_ip)
             
             # Example usage of Ethical Time Decay - Honey tokens are 'A' tier evidence initially
             base_score = correlation_engine.calculate_evidence_score("A") 
             current_confidence = correlation_engine.calculate_time_decay_confidence(base_score, datetime.utcnow().isoformat())
             
             print(f"[DECEPTION] Proximity to known threats: {proximity['score']}. Confidence: {current_confidence}")
             
        except Exception as e:
             print(f"Failed to map beacon to graph: {e}")

    # Return a 1x1 transparent tracking pixel
    import base64
    from fastapi.responses import Response
    pixel = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
    return Response(content=pixel, media_type="image/gif")
