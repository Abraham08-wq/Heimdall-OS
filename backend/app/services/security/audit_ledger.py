import json
import hashlib
import asyncio
import logging
from datetime import datetime
from uuid import uuid4
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session
from app.core.config import settings
from app.services.combat import combat_orchestrator
from app.infrastructure.session import SessionLocal
from app.models.models import AuditLog

logger = logging.getLogger(__name__)

class AuditLedgerService:
    """
    Sovereign Hardening: Cryptographic Integrity (The Tamper-Proof Log).
    Implements a Merkle-Tree style append-only hash chain for all actions.
    This service now uses the main database via the AuditLog model.
    """

    def __init__(self):
        self.is_verifying = False

    def _generate_hash(self, prev_hash: str, payload: dict, timestamp: str) -> str:
        """Creates an SHA-256 seal combining the previous hash and current payload."""
        payload_str = json.dumps(payload, sort_keys=True)
        block = f"{prev_hash}|{timestamp}|{payload_str}"
        return hashlib.sha256(block.encode('utf-8')).hexdigest()

    async def log_event(self, event_type: str, actor_id: str, target_id: Optional[str] = None, metadata: Dict[str, Any] = None) -> str:
        """
        Appends a new cryptographically sealed record to the ledger.
        """
        db: Session = SessionLocal()
        try:
            entry_id = uuid4()
            timestamp = datetime.utcnow()
            
            payload = {
                "entry_id": str(entry_id),
                "actor": actor_id,
                "action": event_type.upper(),
                "target": target_id,
                "metadata": metadata or {}
            }
            
            # 1. Fetch Previous Hash
            prev_hash = await self.get_latest_hash(db)
            
            # 2. Compute Current Merkle Hash
            current_hash = self._generate_hash(prev_hash, payload, timestamp.isoformat())
            
            # 3. Store the immutable record
            record = AuditLog(
                id=entry_id,
                timestamp=timestamp,
                actor_id=actor_id,
                action=event_type,
                resource_id=target_id,
                metadata_=payload,
                hash=current_hash,
                previous_hash=prev_hash,
                # signature= #TODO
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            logger.info(f"AUDIT LEDGER: Appended {entry_id} [Hash: {current_hash[:8]}...]")
            
            return str(entry_id)
        finally:
            db.close()

    async def get_latest_hash(self, db: Session) -> str:
        """Fetches the hash of the most recent record in the audit log."""
        latest_record = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).first()
        if not latest_record:
            return "0000000000000000000000000000000000000000000000000000000000000000"  # Genesis Node
        return latest_record.hash

    async def verify_integrity_chain(self) -> bool:
        """
        Background process to verify the cryptographic chain of the ledger.
        """
        if self.is_verifying:
            return True
            
        self.is_verifying = True
        logger.info("AUDIT LEDGER: Initiating Cryptographic Integrity Verification Sweep...")
        
        db: Session = SessionLocal()
        try:
            records = db.query(AuditLog).order_by(AuditLog.timestamp.asc()).all()
            
            if not records:
                self.is_verifying = False
                return True

            expected_prev_hash = "0000000000000000000000000000000000000000000000000000000000000000"

            for idx, record in enumerate(records):
                # 1. Does the prev_hash match the actual previous hash?
                if record.previous_hash != expected_prev_hash:
                    await self._trigger_p0_alert(f"CHAIN BROKEN at Block {idx}. Prev Hash Mismatch.")
                    self.is_verifying = False
                    return False

                # 2. Recalculate the current hash based on payload to catch tampering
                recalculated_hash = self._generate_hash(
                    record.previous_hash,
                    record.metadata_,
                    record.timestamp.isoformat()
                )
                
                if recalculated_hash != record.hash:
                    await self._trigger_p0_alert(f"PAYLOAD TAMPERING DETECTED at Block {idx}. Hash mismatch.")
                    self.is_verifying = False
                    return False
                    
                expected_prev_hash = record.hash

            logger.info("AUDIT LEDGER: Integrity Sweep Passed. Chain is pristine.")
            self.is_verifying = False
            return True
        finally:
            db.close()

    async def _trigger_p0_alert(self, detail: str):
        """Immediately alerts the God View upon detecting forensic tampering."""
        logger.critical(f"SYSTEM INTEGRITY COMPROMISED: {detail}")
        await combat_orchestrator.broadcast_dashboard("ALERT", {
            "level": "CRITICAL",
            "message": f"P0 SYSTEM INTEGRITY ALERT: Cryptographic Audit Ledger Tampering Detected. {detail}"
        })

    async def start_verification_daemon(self):
        """Background loop to continually check database integrity."""
        while True:
            await self.verify_integrity_chain()
            await asyncio.sleep(60) # Sweep every 60 seconds

audit_ledger = AuditLedgerService()
