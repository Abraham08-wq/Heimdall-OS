"""
WebSocket Manager - Real-Time Execution Log Streaming

Manages WebSocket connections for streaming execution output to the frontend.
Implements connection pooling, session management, and broadcast patterns.
"""

import asyncio
import json
import logging
from typing import Dict, Set, Optional, Callable
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """WebSocket message types."""
    LOG_CHUNK = "log_chunk"
    STATUS_UPDATE = "status_update"
    EXECUTION_COMPLETE = "execution_complete"
    EXECUTION_FAILED = "execution_failed"
    SYSTEM_ALERT = "system_alert"
    HEARTBEAT = "heartbeat"


class WSMessage:
    """Structured WebSocket message."""

    def __init__(
        self,
        message_type: MessageType,
        execution_id: str,
        payload: Dict,
        timestamp: Optional[datetime] = None
    ):
        self.message_type = message_type
        self.execution_id = execution_id
        self.payload = payload
        self.timestamp = timestamp or datetime.utcnow()

    def to_json(self) -> str:
        """Serialize to JSON for transmission."""
        return json.dumps({
            "type": self.message_type.value,
            "execution_id": self.execution_id,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload
        })


class WebSocketManager:
    """
    Manages WebSocket connections and broadcasts execution logs.
    
    Features:
    - Connection pooling per execution
    - Broadcast of logs to multiple subscribers
    - Session lifecycle management
    - Automatic cleanup on disconnect
    """

    def __init__(self):
        # execution_id -> Set of WebSocket connections
        self.active_connections: Dict[str, Set] = {}
        # execution_id -> Queue of pending messages (for late subscribers)
        self.message_queue: Dict[str, asyncio.Queue] = {}
        # execution_id -> Lock for thread-safe operations
        self.locks: Dict[str, asyncio.Lock] = {}

    async def connect(self, execution_id: str, websocket) -> None:
        """
        Register a WebSocket connection for an execution.
        
        Args:
            execution_id: UUID of the execution
            websocket: WebSocket connection object
        """
        if execution_id not in self.active_connections:
            self.active_connections[execution_id] = set()
            self.message_queue[execution_id] = asyncio.Queue(maxsize=1000)
            self.locks[execution_id] = asyncio.Lock()

        self.active_connections[execution_id].add(websocket)
        logger.info(f"📡 WS connected for execution {execution_id} "
                   f"({len(self.active_connections[execution_id])} clients)")

    async def disconnect(self, execution_id: str, websocket) -> None:
        """
        Unregister a WebSocket connection.
        
        Args:
            execution_id: UUID of the execution
            websocket: WebSocket connection object
        """
        if execution_id in self.active_connections:
            self.active_connections[execution_id].discard(websocket)

            # Cleanup if no more clients
            if not self.active_connections[execution_id]:
                del self.active_connections[execution_id]
                del self.message_queue[execution_id]
                del self.locks[execution_id]
                logger.info(f"🧹 Cleaned up execution {execution_id} (no more clients)")

    async def broadcast(self, execution_id: str, message: WSMessage) -> None:
        """
        Broadcast a message to all connected clients for an execution.
        
        Args:
            execution_id: UUID of the execution
            message: WSMessage to broadcast
        """
        if execution_id not in self.active_connections:
            logger.debug(f"No active connections for {execution_id}, queueing message")
            # Queue for late subscribers
            if execution_id in self.message_queue:
                try:
                    self.message_queue[execution_id].put_nowait(message)
                except asyncio.QueueFull:
                    logger.warning(f"Message queue full for {execution_id}, dropping message")
            return

        async with self.locks[execution_id]:
            json_msg = message.to_json()
            disconnected = set()

            for websocket in self.active_connections[execution_id]:
                try:
                    await websocket.send_text(json_msg)
                except Exception as e:
                    logger.warning(f"Failed to send WS message: {e}")
                    disconnected.add(websocket)

            # Clean up disconnected clients
            for ws in disconnected:
                await self.disconnect(execution_id, ws)

    async def send_log_chunk(
        self,
        execution_id: str,
        chunk: str,
        is_stderr: bool = False
    ) -> None:
        """
        Stream a log chunk to all connected clients.
        
        Args:
            execution_id: UUID of the execution
            chunk: Log text chunk
            is_stderr: True if stderr, False if stdout
        """
        message = WSMessage(
            message_type=MessageType.LOG_CHUNK,
            execution_id=execution_id,
            payload={
                "text": chunk,
                "stream": "stderr" if is_stderr else "stdout"
            }
        )
        await self.broadcast(execution_id, message)

    async def send_status_update(
        self,
        execution_id: str,
        status: str,
        details: Optional[Dict] = None
    ) -> None:
        """
        Broadcast a status update.
        
        Args:
            execution_id: UUID of the execution
            status: Status string (e.g., "RUNNING", "COMPLETED")
            details: Additional metadata
        """
        message = WSMessage(
            message_type=MessageType.STATUS_UPDATE,
            execution_id=execution_id,
            payload={
                "status": status,
                "details": details or {}
            }
        )
        await self.broadcast(execution_id, message)

    async def send_completion(
        self,
        execution_id: str,
        exit_code: int,
        duration_seconds: float
    ) -> None:
        """
        Broadcast execution completion.
        
        Args:
            execution_id: UUID of the execution
            exit_code: Process exit code
            duration_seconds: Total execution duration
        """
        message = WSMessage(
            message_type=MessageType.EXECUTION_COMPLETE,
            execution_id=execution_id,
            payload={
                "exit_code": exit_code,
                "duration_seconds": duration_seconds
            }
        )
        await self.broadcast(execution_id, message)

    async def send_system_alert(
        self,
        alert_type: str,
        message_text: str
    ) -> None:
        """
        Broadcast a system-wide alert to all active executions.
        
        Args:
            alert_type: Type of alert (e.g., "LOCKDOWN", "ERROR")
            message_text: Alert message
        """
        message = WSMessage(
            message_type=MessageType.SYSTEM_ALERT,
            execution_id="SYSTEM",
            payload={
                "alert_type": alert_type,
                "message": message_text
            }
        )

        # Broadcast to all active executions
        for execution_id in list(self.active_connections.keys()):
            await self.broadcast(execution_id, message)

    def get_active_execution_count(self) -> int:
        """Get count of active execution streams."""
        return len(self.active_connections)

    def get_connection_count(self, execution_id: str) -> int:
        """Get count of clients for a specific execution."""
        return len(self.active_connections.get(execution_id, set()))


# Global WebSocket manager instance
ws_manager = WebSocketManager()
