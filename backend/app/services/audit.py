import json
import hashlib
from datetime import datetime
from uuid import uuid4
from typing import Optional, Dict, Any
from app.core.logging import logger

class AuditLogger:
    """
    Forensic Grade Logger.
    ensures 'Who did What, When, and Why' is recorded for every action.
    """
    
    def log_action(
        self, 
        actor_id: str, 
        action: str, 
        resource: str, 
        target_id: Optional[str] = None,
        metadata: Dict[str, Any] = None,
        prev_hash: str = "" # In a blockchain implementation, this links rows
    ):
        """
        Records an audit event.
        """
        entry_id = str(uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        # 1. Structure the Log Entry
        log_entry = {
            "entry_id": entry_id,
            "timestamp": timestamp,
            "actor_id": actor_id,
            "action": action.upper(),  # e.g., 'SEARCH', 'VIEW_PROFILE'
            "resource": resource,      # e.g., 'ENTITY', 'REPORT'
            "target_id": target_id,
            "metadata": metadata or {},
            "prev_hash": prev_hash
        }
        
        # 2. Cryptographic Seal (Tamper Evidence)
        # Hash the entry content so any modification breaks the seal
        log_string = json.dumps(log_entry, sort_keys=True)
        entry_hash = hashlib.sha256(log_string.encode()).hexdigest()
        log_entry["hash"] = entry_hash
        
        # 3. Write to Secure Storage
        # In this demo, we use the structured logger which goes to stdout/file.
        # In prod, this goes to WORM storage (Write Once Read Many).
        logger.bind(audit=True).info("AUDIT_EVENT", **log_entry)
        
        return entry_id

audit_logger = AuditLogger()

# Example Usage
# audit_logger.log_action(
#     actor_id="user_123", 
#     action="VIEW", 
#     resource="ENTITY", 
#     target_id="target_alpha",
#     metadata={"reason": "Active Investigation"}
# )
