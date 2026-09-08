import hashlib
import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.models import AuditLog
import uuid
from typing import Dict, Any

from app.core.config import settings
from app.modules.forge.quantum_crypto import pqc_engine

logger = logging.getLogger(__name__)

class WormLedgerService:
    """
    Tier 3: The Immutable Ledger (WORM - Write Once Read Many)
    Provides an un-tamperable cryptographic audit trail for the Unified Intelligence Chain.
    Every event is hashed together with the previous event's hash, forming a strict chain.
    """
    def __init__(self):
        """
        Initializes the WormLedgerService, loading the essential private key for signing.
        NOTE: To generate a key pair, use the `pqc_engine.generate_lattice_keypair()` method
        and store the private key PEM in your environment as `LEDGER_SIGNING_PRIVATE_KEY_PEM`.
        """
        self.signing_key_pem = getattr(settings, "LEDGER_SIGNING_PRIVATE_KEY_PEM", None)
        if not self.signing_key_pem:
            logger.critical("[IMMUTABLE LEDGER] CRITICAL FAILURE: No signing key found. Ledger is not configured and will fail to append events.")
            self.is_configured = False
        else:
            self.is_configured = True

    def _calculate_hash(self, previous_hash: str, actor_id: str, action: str, timestamp_str: str, metadata: Dict[str, Any]) -> str:
        """Calculates a SHA-256 hash forming the cryptographic chain."""
        # Ensure consistent ordering for JSON dumps to maintain hash stability
        metadata_str = json.dumps(metadata, sort_keys=True)
        
        # Structure the block string
        block_string = f"{previous_hash}|{actor_id}|{action}|{timestamp_str}|{metadata_str}"
        
        # Return the SHA-256 Digest
        return hashlib.sha256(block_string.encode('utf-8')).hexdigest()

    async def append_event(self, db: Session, actor_id: uuid.UUID, action: str, metadata: Dict[str, Any] = None, resource_type: str = "TELEMETRY", resource_id: uuid.UUID = None) -> AuditLog:
        """
        Appends a new event to the ledger, calculating its cryptographic hash and signing it.
        """
        if not self.is_configured:
            raise Exception("WormLedgerService is not configured with a signing key. Cannot append to the ledger.")

        if metadata is None:
            metadata = {}
            
        timestamp = datetime.utcnow()
        timestamp_str = timestamp.isoformat()
        
        # 1. Retrieve the previous hash
        # To prevent race conditions in a highly concurrent distributed system, 
        # this would ideally use a database row lock (`with_for_update`) or a Redis sequencer.
        # For this implementation, we query the latest row.
        last_log = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).first()
        
        previous_hash = last_log.hash if last_log and last_log.hash else "0" * 64 # Genesis Block
        
        # 2. Calculate the new hash
        actor_id_str = str(actor_id) if actor_id else "SYSTEM"
        new_hash = self._calculate_hash(
            previous_hash=previous_hash,
            actor_id=actor_id_str,
            action=action,
            timestamp_str=timestamp_str,
            metadata=metadata
        )
        
        # 3. Sign the new hash
        signature = pqc_engine.quantum_sign_payload(
            private_key_pem=self.signing_key_pem,
            payload_data={"hash": new_hash, "timestamp": timestamp_str}
        )
        if not signature:
            raise Exception("Failed to sign the new ledger event. Aborting append.")

        # 4. Create the Database Entry
        new_audit_log = AuditLog(
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_=metadata,
            timestamp=timestamp,
            hash=new_hash,
            previous_hash=previous_hash,
            signature=signature
        )
        
        # 5. Commit to the immutable store
        try:
            db.add(new_audit_log)
            db.commit()
            db.refresh(new_audit_log)
        except Exception as e:
            db.rollback()
            logger.critical(f"[IMMUTABLE LEDGER] Critical Failure appending to chain: {e}")
            raise e
            
        logger.info(f"[IMMUTABLE LEDGER] Event {action} securely chained. Hash: {new_hash[:8]}...")
        return new_audit_log

worm_ledger = WormLedgerService()
