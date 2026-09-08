import asyncio
import sys
import os

# Add the app directory to PYTHONPATH so we can import modules
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.services.unified_chain import unified_cyber_pipeline
from fastapi import BackgroundTasks

class MockBackgroundTasks:
    def __init__(self):
        self.tasks = []
    def add_task(self, func, *args, **kwargs):
        self.tasks.append((func, args, kwargs))

async def simulate_attack():
    print("==========================================================")
    print("🛡️ SOVEREIGN ENTERPRISE FORTRESS - SIMULATION STARTED 🛡️")
    print("==========================================================")
    
    target_ip = "192.168.1.100"  # Can be ip, email, or handle
    tenant = "sim_tenant_01"
    
    bg_tasks = MockBackgroundTasks()

    print(f"[*] Initiating Intelligence Chain against Target: {target_ip}")
    mission = unified_cyber_pipeline.initiate_mission(target_ip, tenant, bg_tasks)
    
    print(f"[*] Mission ID generated: {mission.mission_id}")
    print("[*] Forcing synchronous execution of Background Task for simulation...")
    
    for task_func, args, kwargs in bg_tasks.tasks:
        await task_func(*args, **kwargs)
        
    print("\n==========================================================")
    print("🏁 SIMULATION COMPLETE. REVIEWING MISSION DOSSIER 🏁")
    print("==========================================================")
    print(f"Final Phase: {mission.phase.value}")
    
    if mission.recon_data:
        print("\n[PHASE I: RECON DATA]")
        print(mission.recon_data)
        
    if mission.analysis_findings:
        print("\n[PHASE II: ANALYSIS & DE-MASKING]")
        print("Fingerprint:", mission.analysis_findings.demasking.fingerprint)
        print("Status:", mission.analysis_findings.demasking.status)
        
    if mission.execution_history:
        print("\n[PHASE III: EXECUTION / COUNTER-STRIKES]")
        for event in mission.execution_history:
            print(f"- {event['timestamp']}: Triggered {event['action']} -> {event['status']}")
            print(f"  Details: {event['details']}")

if __name__ == "__main__":
    asyncio.run(simulate_attack())
