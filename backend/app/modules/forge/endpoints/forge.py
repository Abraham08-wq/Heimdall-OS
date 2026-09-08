from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any
from app.modules.forge.quantum_crypto import pqc_engine
from app.modules.forge.iac_repair import iac_forge

router = APIRouter()

class DriftReport(BaseModel):
    node_id: str
    current_state: Dict[str, Any]

@router.get("/pqc/generate", tags=["The Forge - Zero-Trust Infra"])
async def generate_quantum_keys():
    """
    Tier 6: Generates a Post-Quantum Cryptography (PQC) keypair.
    Used for establishing secure, quantum-resistant communication channels
    between the Vanguard Interface and internal Sentinel agents.
    """
    try:
        pub_key, priv_key = pqc_engine.generate_lattice_keypair()
        return {
            "status": "PQC_KEYPAIR_GENERATED",
            "algorithm": "NIST_LATTICE_KEM_SIMULATION",
            "public_key": pub_key,
            # In a real environment, the private key would NEVER be returned over typical HTTP.
            # It would be securely injected via a hardware security module (HSM) or Vault.
            # We return it here strictly for architecture demonstration.
            "private_key": priv_key
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="PQC generation failed.")

@router.post("/iac/audit", tags=["The Forge - Zero-Trust Infra"])
async def audit_infrastructure_drift(report: DriftReport, background_tasks: BackgroundTasks):
    """
    Tier 6: Agents periodically submit their configuration state.
    If the Forge detects drift from the Terraform Golden Image, it annihilates the node
    and rebuilds it autonomously.
    """
    try:
        is_compromised = await iac_forge.detect_baseline_drift(report.node_id, report.current_state)
        
        if is_compromised:
            # Execute the destroy/rebuild sequence asynchronously
            background_tasks.add_task(
                iac_forge.execute_terraform_remediation,
                report.node_id
            )
            return {
                "status": "DRIFT_DETECTED",
                "action": "INITIATING_IAC_WIPE_AND_REBUILD",
                "target_node": report.node_id
            }
            
        return {"status": "GOLDEN_STATE_VERIFIED"}
        
    except Exception as e:
        print(f"[THE FORGE] Audit failure: {e}")
        raise HTTPException(status_code=500, detail="Infrastructure audit failed.")
