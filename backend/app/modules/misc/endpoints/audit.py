from typing import Any, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api import deps
from app.services.worm import worm_service
from app.models.models import AuditLog

router = APIRouter()

@router.get("/logs")
def get_audit_logs(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
#    current_user: Any = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve the immutable audit ledger.
    """
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()
    return logs

@router.post("/verify")
def verify_integrity(
    db: Session = Depends(deps.get_db),
#    current_user: Any = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Triggers a full cryptographic verification of the SHA-256 chain.
    """
    is_valid = worm_service.verify_chain(db)
    
    if is_valid:
        return {"status": "success", "message": "Cryptographic Integrity Verified. Ledger is immutable."}
    else:
        # In a real system, you might return 400 or a specific breach exception
        return {"status": "breach", "message": "CRITICAL: Chain integrity broken. Data tampering detected."}
