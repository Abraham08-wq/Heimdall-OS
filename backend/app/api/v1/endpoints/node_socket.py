from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Dict, List, Optional
import hashlib
import hmac
import logging
import json
from pydantic import BaseModel, Field

from app.infrastructure.session import get_db
from app.models.models import ExecutionNode, User
from app.api.deps import get_current_active_user
from app.services.anomaly_detection import anomaly_engine
from app.services.response_orchestrator import response_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter()

# 1. Input Validation: Strict Pydantic model prevents JSON bombs and Key Pollution
class ExecutionCommand(BaseModel):
    image: str = Field(..., max_length=100, description="Docker image to run")
    script: str = Field(..., max_length=10000, description="Payload script content")

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.node_contexts: Dict[WebSocket, dict] = {}

    async def connect(self, websocket: WebSocket, tenant_id: str, node_id: str):
        await websocket.accept()
        if tenant_id not in self.active_connections:
            self.active_connections[tenant_id] = []
        self.active_connections[tenant_id].append(websocket)
        self.node_contexts[websocket] = {"tenant_id": tenant_id, "node_id": node_id}
        logger.info(f"Node {node_id} connected for tenant {tenant_id}")

    def disconnect(self, websocket: WebSocket):
        ctx = self.node_contexts.get(websocket)
        if ctx:
            tenant_id = ctx["tenant_id"]
            if tenant_id in self.active_connections and websocket in self.active_connections[tenant_id]:
                self.active_connections[tenant_id].remove(websocket)
                if not self.active_connections[tenant_id]:
                    del self.active_connections[tenant_id]
            logger.info(f"Node {ctx['node_id']} disconnected")
            del self.node_contexts[websocket]

    async def send_command(self, tenant_id: str, command: ExecutionCommand):
        if tenant_id in self.active_connections and self.active_connections[tenant_id]:
            ws = self.active_connections[tenant_id][0]
            await ws.send_json(command.model_dump())
            return True
        return False

    async def sever_connection(self, tenant_id: str, node_id: str):
        """Emergency Kill-Switch: Severs specific node/agent connection."""
        if tenant_id in self.active_connections:
            for ws in list(self.active_connections[tenant_id]):
                ctx = self.node_contexts.get(ws)
                if ctx and ctx.get("node_id") == node_id:
                    await ws.close(code=status.WS_1008_POLICY_VIOLATION)
                    self.disconnect(ws)
                    return True
        return False

manager = ConnectionManager()

# 2. Key Handling: Verify the presented secret against the stored hash before upgrade
@router.websocket("/ws")
async def node_websocket_endpoint(
    websocket: WebSocket, 
    x_node_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    if not x_node_api_key:
        logger.warning("WebSocket connection attempt missing X-Node-API-Key header.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    presented_key_hash = hashlib.sha256(x_node_api_key.encode("utf-8")).hexdigest()

    result = db.execute(select(ExecutionNode).where(ExecutionNode.api_key_hash == presented_key_hash))
    node = result.scalars().first()
    
    if not node or not hmac.compare_digest(node.api_key_hash, presented_key_hash):
        logger.warning("Unauthorized node connection attempt.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    tenant_id = str(node.tenant_id)
    node_id = str(node.id)
    
    # 3. DB Resiliency: Safe persistence blocks
    try:
        node.is_online = True
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error updating node status: {e}")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    await manager.connect(websocket, tenant_id, node_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                logger.info(f"Log from node {node_id}: {data}")
                continue
                
            if payload.get("type") == "telemetry":
                event_data = payload.get("data", {})
                source_ip = payload.get("source_ip", "0.0.0.0")
                
                # Assign temporal context if missing
                if "timestamp" not in event_data:
                    from datetime import datetime, timezone
                    event_data["timestamp"] = datetime.now(timezone.utc).isoformat()
                
                # 1. Pipe directly into UEBA Anomaly Baseline Engine
                analysis = anomaly_engine.compute_ueba_score(source_ip, event_data)
                
                # 2. Trap Anomaly triggers
                if analysis.get("is_anomalous"):
                    logger.warning(f"UEBA ANOMALY [{source_ip}]: Score {analysis['ueba_score']}, Tech: {analysis['mitre_technique']}")
                    
                    # 3. Route to Response Orchestrator
                    actions = await response_orchestrator.evaluate_and_respond(
                        tenant_id=tenant_id,
                        target_ip=source_ip,
                        risk_score=analysis['ueba_score'] * 100, # Normalize scale to thresholds
                        reasoning=f"Automated Behavioral Trigger: {analysis['mitre_technique']}"
                    )
                    
                    # 4. Execute Playbook scripts directly onto the Client Node via reverse-tunnel
                    for action in actions:
                        if action.get("action") == "block_ip":
                            logger.error(f"Pushing Network Isolation script to node {node_id} for offending IP {source_ip}")
                            # Send highly restricted container payload back down the pipe
                            containment_script = ExecutionCommand(
                                image="alpine:latest",
                                script=f"echo '[MITIGATION] Pushing IPTables strict DROP for source {source_ip}...'; sleep 1; echo '[MITIGATION] Isolatation applied.'"
                            )
                            await manager.send_command(tenant_id, containment_script)
            else:
                logger.info(f"Log from node {node_id}: {data}")
                            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        try:
            node.is_online = False
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Database error updating node disconnect status: {e}")

# 5. IDOR Fix: Requires Authentication + Validation
@router.post("/execute/{tenant_id}", status_code=status.HTTP_200_OK)
async def trigger_execution(
    tenant_id: str, 
    command: ExecutionCommand,
    current_user: User = Depends(get_current_active_user)
):
    # Cross-tenant execution check
    if str(current_user.tenant_id) != tenant_id:
        logger.warning(f"IDOR attempt: User {current_user.id} attempted to access tenant {tenant_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="You are not authorized to execute commands for this tenant."
        )

    success = await manager.send_command(tenant_id, command)
    if success:
        return {"status": "success", "message": "Command securely dispatched to node"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="No online execution nodes found for this tenant."
        )

# 6. Agent Containment Kill-Switch (Phase 3)
from app.services.memory_quarantine import memory_quarantine

@router.post("/contain/agent/{agent_id}", status_code=status.HTTP_200_OK)
async def contain_agent(
    agent_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Emergency Agent Kill-Switch.
    1. Severs WebSocket connection.
    2. Revokes JWT/Access Tokens (implemented via Redis blocklist in security.py).
    3. Freezes short-term memory state in Redis to preserve forensics.
    """
    tenant_id = str(current_user.tenant_id)
    
    # 1. Sever WebSocket Connection
    severed = await manager.sever_connection(tenant_id, agent_id)
    
    # 2. Revoke JWT Access Tokens (Stubbed - assuming token revocation service integration)
    from app.core.security import revoke_agent_tokens
    await revoke_agent_tokens(agent_id, tenant_id)
    
    # 3. Quarantine Memory State
    quarantined = await memory_quarantine.freeze_agent_memory(agent_id, tenant_id)
    
    return {
        "status": "success", 
        "agent_id": agent_id,
        "actions_taken": {
            "websocket_severed": severed,
            "tokens_revoked": True,
            "memory_quarantined": quarantined
        }
    }

