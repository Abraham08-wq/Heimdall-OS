import asyncio
import logging
import json
from typing import Dict, List, Any
from fastapi import WebSocket
from app.infrastructure.cache.redis_manager import redis_cache

logger = logging.getLogger(__name__)

class CombatOrchestratorService:
    def __init__(self, org_id: str = "global"):
        # Session Multiplexing: map of agent_id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        # Geofence groups: map of geofence_id -> List[agent_id]
        self.geofenced_agents: Dict[str, List[str]] = {}
        # Dashboard connections (Situation Room) - Local to this worker
        self.dashboard_connections: List[WebSocket] = []
        
        # Redis Pub/Sub Channels
        self.DASHBOARD_CHANNEL = f"god_view_sync_{org_id}"

    async def start_redis_listener(self):
        """
        Background task to listen to Redis Pub/Sub and broadcast to local WebSockets.
        Allows horizontal scaling across 100+ Docker containers.
        Includes exponential backoff retry on connection errors.
        """
        retry_delay = 5
        max_retry_delay = 60

        while True:
            try:
                pubsub = redis_cache.redis_client.pubsub()
                await pubsub.subscribe(self.DASHBOARD_CHANNEL)
                logger.info(f"Combat Orchestrator subscribed to Redis channel: {self.DASHBOARD_CHANNEL}")
                retry_delay = 5  # Reset on successful connection

                async for message in pubsub.listen():
                    if message["type"] == "message":
                        payload = message["data"]
                        for connection in self.dashboard_connections[:]:
                            try:
                                await connection.send_text(payload)
                            except Exception as e:
                                logger.error(f"Failed to send to Dashboard UI instance: {e}")
                                self.disconnect_dashboard(connection)
            except Exception as e:
                logger.warning(f"Combat Orchestrator Redis listener disconnected ({e}). Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)

    async def connect_dashboard(self, websocket: WebSocket):
        await websocket.accept()
        self.dashboard_connections.append(websocket)
        logger.info(f"Dashboard Client CONNECTED locally. Total on this node: {len(self.dashboard_connections)}")

    def disconnect_dashboard(self, websocket: WebSocket):
        if websocket in self.dashboard_connections:
            self.dashboard_connections.remove(websocket)
            logger.info("Dashboard Client DISCONNECTED locally")

    async def broadcast_dashboard(self, event_type: str, data: Any):
        """
        Publishes live intel to Redis, implicitly reaching all distributed dashboards.
        """
        message = json.dumps({
            "type": event_type,
            "data": data
        })
        
        # Publish to Redis instead of sending directly to local sockets
        try:
            await redis_cache.redis_client.publish(self.DASHBOARD_CHANNEL, message)
        except Exception as e:
            logger.error(f"Failed to publish to Redis: {e}")

    async def connect(self, websocket: WebSocket, agent_id: str, geofence_id: str = "global"):
        await websocket.accept()
        self.active_connections[agent_id] = websocket
        
        if geofence_id not in self.geofenced_agents:
            self.geofenced_agents[geofence_id] = []
        self.geofenced_agents[geofence_id].append(agent_id)
        
        logger.info(f"Stealth Agent {agent_id} CONNECTED in sector {geofence_id}")
        await self.broadcast_dashboard("AGENT_CONNECT", {"agent_id": agent_id, "sector": geofence_id})

    def disconnect(self, agent_id: str):
        if agent_id in self.active_connections:
            del self.active_connections[agent_id]
        
        for group in self.geofenced_agents.values():
            if agent_id in group:
                group.remove(agent_id)
        
        logger.info(f"Stealth Agent {agent_id} DISCONNECTED")
        asyncio.create_task(self.broadcast_dashboard("AGENT_DISCONNECT", {"agent_id": agent_id}))

    async def broadcast_command(self, payload: Dict[str, Any], target_agents: List[str] = None):
        """
        Sends encrypted command payloads to agents locally connected.
        (Note: In a true distributed agent model, this would also need Pub/Sub per agent_id)
        """
        message = json.dumps({
            "type": "KINETIC_COMMAND",
            "payload": payload,
            "signature": "simulated_operator_key_sig_x99" 
        })
        
        targets = target_agents if target_agents else self.active_connections.keys()
        
        for agent_id in targets:
            if agent_id in self.active_connections:
                try:
                    await self.active_connections[agent_id].send_text(message)
                except Exception as e:
                    logger.error(f"Failed to send to {agent_id}: {e}")
        
        await self.broadcast_dashboard("COMMAND_Issued", {"targets": list(targets), "command": payload.get("command")})

    async def trigger_lockdown(self, geofence_id: str):
        logger.critical(f"⚠️ INITIATING LOCKDOWN FOR SECTOR: {geofence_id} ⚠️")
        targets = self.geofenced_agents.get(geofence_id, [])
        payload = {"command": "WIPE_VFS", "force": True, "reason": "EMERGENCY_LOCKDOWN"}
        await self.broadcast_command(payload, targets)
        await self.broadcast_dashboard("ALERT", {"level": "CRITICAL", "message": f"LOCKDOWN INITIATED: {geofence_id}"})
        return len(targets)

    async def assess_neural_threat(self, prediction: Dict[str, Any]):
        confidence = prediction.get("confidence", 0)
        attack_type = prediction.get("type", "unknown")
        
        if confidence > 0.9 and attack_type == "lateral_movement":
            logger.warning(f"NEURAL INTERCEPT: High confidence lateral move detected ({confidence*100}%). Engaging Sinkhole.")
            await self.broadcast_command({
                "command": "ISOLATE_HOST",
                "target": prediction.get("target_ip")
            })
            await self.broadcast_dashboard("THREAT_INTERCEPT", prediction)

combat_orchestrator = CombatOrchestratorService()
