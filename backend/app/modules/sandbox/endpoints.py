from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from .digital_twin import twin_orchestrator

router = APIRouter()

class TwinRerouteRequest(BaseModel):
    attacker_ip: str
    original_asset_id: str
    original_asset_ip: str

@router.post("/isolate", tags=["Aegis Vault Sandboxing"])
async def trigger_digital_twin_isolation(request: TwinRerouteRequest, background_tasks: BackgroundTasks):
    """
    Tier 3: The ultimate containment action.
    Triggered autonomously by the AI Analyst Swarm when a high-confidence threat is moving laterally.
    Clones the target asset and reroutes the attacker into the clone.
    """
    try:
        # 1. Clone the asset (Async to prevent blocking the AI event loop)
        twin_id = await twin_orchestrator.clone_asset_to_sandbox(
            original_asset_id=request.original_asset_id,
            attacker_ip=request.attacker_ip
        )
        
        if not twin_id:
             raise HTTPException(status_code=500, detail="Failed to provision Digital Twin Sandbox.")
             
        # ── Twin IP Resolution ───────────────────────────────────────────
        # In a real deployment this IP comes from the container orchestrator
        # (Docker inspect / Kubernetes pod IP) after the honeypot container
        # is started.  The honeynet_ops service must be extended to return
        # the assigned container IP alongside the twin_id.
        # TODO: Replace with: twin_ip = await honeynet_ops.get_container_ip(twin_id)
        # For now we derive a stable placeholder from the twin_id so the
        # SDN reroute call at least receives a non-random value.
        twin_ip = f"10.99.0.{abs(hash(twin_id)) % 254 + 1}"
             
        # 2. Execute the SDN Reroute to trap the attacker
        background_tasks.add_task(
            twin_orchestrator.execute_sdn_reroute,
            original_asset_ip=request.original_asset_ip,
            twin_ip=twin_ip,
            attacker_ip=request.attacker_ip
        )
        
        return {
            "status": "CONTAINMENT_ACTIVE",
            "action": "DIGITAL_TWIN_REROUTE",
            "twin_id": twin_id,
            "twin_ip": twin_ip,
            "message": f"Attacker {request.attacker_ip} is being seamlessly routed to Sandbox {twin_id}"
        }
        
    except Exception as e:
        print(f"[AEGIS VAULT] Isolation failure: {e}")
        raise HTTPException(status_code=500, detail="Critical containment failure.")

class QuarantineRequest(BaseModel):
    target_ip: str

@router.post("/quarantine", tags=["Aegis Vault Sandboxing"])
async def trigger_network_quarantine(request: QuarantineRequest):
    """
    Tier 3: Standard Containment.
    Instantly drops all inbound/outbound traffic for a specific IP at the edge firewall level.
    """
    try:
        print(f"[AEGIS VAULT] Executing ZERO-TRUST QUARANTINE on {request.target_ip}...")
        # Executing system-level containment script (simulating Palo Alto/Cisco ISE integration via SSH/API)
        import asyncio
        import subprocess
        import os
        
        script_path = os.path.join(os.path.dirname(__file__), "../../scripts/containment/null_route.sh")
        
        # In a real environment, we'd use asyncio.create_subprocess_exec for non-blocking IO, 
        # but for this controlled simulation, subprocess.run is sufficient.
        process = subprocess.run(
            [script_path, request.target_ip],
            capture_output=True,
            text=True
        )
        
        if process.returncode != 0:
            raise Exception(f"Firewall reject script failed: {process.stderr}")
            
        print(f"[AEGIS VAULT: SYS-LOG] {process.stdout.strip()}")
        print(f"[AEGIS VAULT] SUCCESS: Null route established for {request.target_ip}. Host is completely dark.")
        
        return {
            "status": "QUARANTINED",
            "action": "NULL_ROUTE",
            "target": request.target_ip,
            "message": f"Absolute network isolation enforced on {request.target_ip}."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Quarantine failed.")
