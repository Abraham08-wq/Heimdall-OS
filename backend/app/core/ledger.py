"""
Postgres Ledger Logger - Immutable Execution & Security Audit Trail

Writes all execution logs and security events to PostgreSQL in an append-only format.
This ensures an immutable record for forensics and compliance.
"""

import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class LedgerEventType(str, Enum):
    """Types of events logged to the ledger."""
    EXECUTION_STARTED = "execution_started"
    EXECUTION_LOG = "execution_log"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_CANCELLED = "execution_cancelled"
    SECURITY_EVENT = "security_event"
    SYSTEM_LOCKDOWN = "system_lockdown"
    TOKEN_REVOCATION = "token_revocation"
    SCRIPT_MODIFIED = "script_modified"
    SCRIPT_UPLOADED = "script_uploaded"


class PostgresLedger:
    """
    Append-only audit ledger stored in PostgreSQL.
    
    Features:
    - Immutable append-only table
    - Structured logging with JSON payload
    - Automatic timestamps
    - Integration with existing DB session
    """

    def __init__(self, db_session=None):
        """
        Initialize the ledger logger.
        
        Args:
            db_session: SQLAlchemy session for database operations
        """
        self.db = db_session

    async def log_event(
        self,
        event_type: LedgerEventType,
        related_entity_type: str,
        related_entity_id: str,
        payload: Dict[str, Any],
        user_id: Optional[str] = None,
        org_id: Optional[str] = None
    ) -> None:
        """
        Log an event to the immutable ledger.
        
        Args:
            event_type: Type of event
            related_entity_type: Type of entity (e.g., "execution", "script")
            related_entity_id: ID of the entity
            payload: Event details (JSON-serializable dict)
            user_id: User who triggered the event
            org_id: Organization context
        """
        if not self.db:
            logger.warning("No DB session, ledger logging skipped")
            return

        try:
            # This assumes an AuditLog model exists in the app
            # If not, this will be created in the models migration
            from sqlalchemy import text

            query = text("""
                INSERT INTO audit_logs 
                (event_type, related_entity_type, related_entity_id, payload, user_id, org_id, created_at)
                VALUES (:event_type, :entity_type, :entity_id, :payload, :user_id, :org_id, :created_at)
            """)

            await self.db.execute(
                query,
                {
                    "event_type": event_type.value,
                    "entity_type": related_entity_type,
                    "entity_id": related_entity_id,
                    "payload": json.dumps(payload),
                    "user_id": user_id,
                    "org_id": org_id,
                    "created_at": datetime.utcnow()
                }
            )

            await self.db.commit()

            logger.debug(
                f"✓ Ledger event logged: {event_type.value} "
                f"({related_entity_type}:{related_entity_id})"
            )

        except Exception as e:
            logger.error(f"Failed to log ledger event: {e}")
            await self.db.rollback()

    async def log_execution_started(
        self,
        execution_id: str,
        script_id: str,
        script_name: str,
        user_id: Optional[str] = None,
        org_id: Optional[str] = None
    ) -> None:
        """Log when an execution starts."""
        await self.log_event(
            event_type=LedgerEventType.EXECUTION_STARTED,
            related_entity_type="execution",
            related_entity_id=execution_id,
            payload={
                "script_id": script_id,
                "script_name": script_name,
                "status": "RUNNING"
            },
            user_id=user_id,
            org_id=org_id
        )

    async def log_execution_output(
        self,
        execution_id: str,
        chunk: str,
        is_stderr: bool = False,
        user_id: Optional[str] = None,
        org_id: Optional[str] = None
    ) -> None:
        """Log execution output chunk."""
        await self.log_event(
            event_type=LedgerEventType.EXECUTION_LOG,
            related_entity_type="execution",
            related_entity_id=execution_id,
            payload={
                "stream": "stderr" if is_stderr else "stdout",
                "chunk": chunk[:1000]  # Truncate very long chunks
            },
            user_id=user_id,
            org_id=org_id
        )

    async def log_execution_completed(
        self,
        execution_id: str,
        exit_code: int,
        duration_seconds: float,
        stdout: str,
        stderr: str,
        user_id: Optional[str] = None,
        org_id: Optional[str] = None
    ) -> None:
        """Log when an execution completes."""
        await self.log_event(
            event_type=LedgerEventType.EXECUTION_COMPLETED,
            related_entity_type="execution",
            related_entity_id=execution_id,
            payload={
                "exit_code": exit_code,
                "duration_seconds": duration_seconds,
                "stdout_length": len(stdout),
                "stderr_length": len(stderr),
                "status": "COMPLETED" if exit_code == 0 else "FAILED"
            },
            user_id=user_id,
            org_id=org_id
        )

    async def log_security_event(
        self,
        event_type: str,
        details: Dict[str, Any],
        user_id: Optional[str] = None,
        org_id: Optional[str] = None
    ) -> None:
        """Log a security-related event."""
        await self.log_event(
            event_type=LedgerEventType.SECURITY_EVENT,
            related_entity_type="security",
            related_entity_id=event_type,
            payload=details,
            user_id=user_id,
            org_id=org_id
        )

    async def log_lockdown(
        self,
        enabled: bool,
        reason: str,
        user_id: Optional[str] = None,
        org_id: Optional[str] = None
    ) -> None:
        """Log a lockdown event."""
        await self.log_event(
            event_type=LedgerEventType.SYSTEM_LOCKDOWN,
            related_entity_type="system",
            related_entity_id="lockdown",
            payload={
                "enabled": enabled,
                "reason": reason
            },
            user_id=user_id,
            org_id=org_id
        )

    async def log_script_modification(
        self,
        script_id: str,
        script_name: str,
        changes: Dict[str, Any],
        user_id: Optional[str] = None,
        org_id: Optional[str] = None
    ) -> None:
        """Log when a script is modified."""
        await self.log_event(
            event_type=LedgerEventType.SCRIPT_MODIFIED,
            related_entity_type="script",
            related_entity_id=script_id,
            payload={
                "script_name": script_name,
                "changes": changes
            },
            user_id=user_id,
            org_id=org_id
        )

    async def get_execution_history(
        self,
        execution_id: str,
        limit: int = 100
    ) -> list:
        """
        Retrieve all logged events for an execution.
        
        Args:
            execution_id: Execution ID to query
            limit: Maximum number of events to return
            
        Returns:
            List of logged events
        """
        if not self.db:
            return []

        try:
            from sqlalchemy import text

            query = text("""
                SELECT * FROM audit_logs
                WHERE related_entity_type = 'execution' AND related_entity_id = :execution_id
                ORDER BY created_at DESC
                LIMIT :limit
            """)

            result = await self.db.execute(
                query,
                {"execution_id": execution_id, "limit": limit}
            )

            return result.fetchall()

        except Exception as e:
            logger.error(f"Failed to retrieve execution history: {e}")
            return []


# Global ledger instance (will be initialized in main.py)
ledger = PostgresLedger()
