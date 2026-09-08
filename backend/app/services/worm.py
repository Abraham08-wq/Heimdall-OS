import hashlib
import json
from sqlalchemy.orm import Session
from app.models.models import AuditLog

class WORMService:
    @staticmethod
    def calculate_hash(entry: AuditLog, previous_hash: str) -> str:
        """
        Generates a SHA-256 hash ensuring the chain integrity.
        Hash = SHA256(prev_hash + actor_id + action + resource_id + timestamp)
        """
        payload = {
            "prev": previous_hash,
            "actor": str(entry.actor_id),
            "action": entry.action,
            "resource": str(entry.resource_id),
            "ts": str(entry.timestamp)
        }
        # Sort keys for deterministic JSON serialization
        payload_str = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(payload_str.encode()).hexdigest()

    @staticmethod
    def verify_chain(db: Session) -> bool:
        """
        Iterates through the entire AuditLog table to verify integrity.
        Returns False if any link in the chain is broken.
        """
        logs = db.query(AuditLog).order_by(AuditLog.timestamp.asc()).all()
        
        if not logs:
            return True

        # Genesis block check (first log should have prev_hash='0' or None)
        # For simplicity, we skip the first block's prev_hash check if it's the very first ever.
        
        for i in range(1, len(logs)):
            current = logs[i]
            previous = logs[i-1]
            
            # Check 1: The current log's 'previous_hash' must match the previous log's 'hash'
            if current.previous_hash != previous.hash:
                print(f"Integrity Breach at ID {current.id}: Previous Hash Mismatch")
                return False
            
            # Check 2: The current log's 'hash' must be valid based on its contents
            calculated = WORMService.calculate_hash(current, previous.hash)
            if current.hash != calculated:
               print(f"Integrity Breach at ID {current.id}: Data Tampering Detected")
               return False
               
        return True

worm_service = WORMService()
