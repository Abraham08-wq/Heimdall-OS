"""
stats.py — Real system metrics from /proc and DB.
No random fallbacks.
"""
from typing import Any, Dict
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.api import deps
from app.models import models
import os
import logging

logger = logging.getLogger(__name__)

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

router = APIRouter()


def _read_proc_meminfo() -> float:
    """Read /proc/meminfo for real memory % without psutil."""
    try:
        with open("/proc/meminfo") as f:
            lines = {l.split(":")[0]: int(l.split()[1]) for l in f if ":" in l}
        total = lines.get("MemTotal", 0)
        avail = lines.get("MemAvailable", lines.get("MemFree", 0))
        if total > 0:
            return round((1 - avail / total) * 100, 1)
    except Exception:
        pass
    return 0.0


def _read_cpu_load() -> float:
    """Read CPU load from /proc/loadavg — no psutil needed."""
    try:
        load1, *_ = os.getloadavg()
        cpu_count = os.cpu_count() or 1
        return round(min(100.0, (load1 / cpu_count) * 100), 1)
    except (AttributeError, OSError):
        return 0.0


@router.get("/", response_model=Dict[str, Any])
def get_system_stats(db: Session = Depends(deps.get_db)) -> Any:
    """
    Real system statistics — PostgreSQL + /proc filesystem.
    No simulated data.
    """
    # 1. Pipeline Status
    try:
        db.execute(text("SELECT 1"))
        pipeline_status = "Active"
    except Exception as e:
        pipeline_status = f"Degraded: {str(e)}"

    # 2. Entity Count
    try:
        entity_count = db.query(models.EntityDB).count()
    except Exception:
        entity_count = 0

    # 3. High Risk Count (risk_score > 80)
    try:
        active_breaches = db.query(models.EntityDB).filter(
            models.EntityDB.risk_score > 80
        ).count()
    except Exception:
        active_breaches = 0

    # 4. Firewall stats from semantic_logs
    total_requests = 0
    blocked_requests = 0
    pii_events = 0
    avg_threat_score = 0.0
    try:
        row = db.execute(text(
            "SELECT COUNT(*) as total, "
            "SUM(CASE WHEN action='BLOCK' THEN 1 ELSE 0 END) as blocked, "
            "SUM(CASE WHEN action='SCRUB_AND_PASS' THEN 1 ELSE 0 END) as scrubbed, "
            "AVG(threat_score) as avg_score "
            "FROM semantic_logs"
        )).fetchone()
        if row:
            total_requests   = int(row[0] or 0)
            blocked_requests = int(row[1] or 0)
            pii_events       = int(row[2] or 0)
            avg_threat_score = round(float(row[3] or 0.0), 4)
    except Exception as e:
        logger.debug(f"semantic_logs stats query: {e}")

    # 5. Real CPU/memory from proc or psutil
    if HAS_PSUTIL:
        cpu_percent = psutil.cpu_percent(interval=None)
        mem_percent = psutil.virtual_memory().percent
        try:
            disk_io = psutil.disk_io_counters()
            io_percent = round(min(100.0, (disk_io.read_bytes + disk_io.write_bytes) / 1e9 * 10), 1)
        except Exception:
            io_percent = 0.0
        try:
            net_io = psutil.net_io_counters()
            net_percent = round(min(100.0, (net_io.bytes_sent + net_io.bytes_recv) / 1e8), 1)
        except Exception:
            net_percent = 0.0
    else:
        cpu_percent = _read_cpu_load()
        mem_percent = _read_proc_meminfo()
        io_percent  = 0.0
        net_percent = 0.0

    return {
        "pipeline":         pipeline_status,
        "nodes":            str(entity_count),
        "active_breaches":  active_breaches,
        "cpu":              round(cpu_percent, 1),
        "mem":              round(mem_percent, 1),
        "net":              net_percent,
        "io":               io_percent,
        # Firewall metrics (consumed by Situation Room)
        "total_requests":   total_requests,
        "blocked_requests": blocked_requests,
        "pii_events":       pii_events,
        "avg_threat_score": avg_threat_score,
    }
