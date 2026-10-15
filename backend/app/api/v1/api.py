from fastapi import APIRouter
from app.modules.auth.endpoints import auth
from app.api.v1.endpoints import ingestion
from app.api.v1.ops import router as ops_router
from app.api.v1 import warroom
from app.modules.deception import endpoints as deception
from app.modules.ai_swarms import endpoints as ai_swarms
from app.modules.sandbox import endpoints as sandbox
from app.modules.catalyst import endpoints as catalyst
from app.modules.offensive.endpoints import offensive, redteam
from app.modules.ghost.endpoints import ghost as ghost_c2
from app.modules.forge.endpoints import forge
from app.modules.oracle.endpoints import oracle
from app.modules.recon.endpoints import probe as omni_probe, osint as osint_probe
from app.modules.intelligence.endpoints import entities, analysis, ai_tactical, ai_analyst
from app.modules.monitoring.endpoints import stats, health_integrity
from app.modules.misc.endpoints import devices, ghost, socket, connectors, audit
from app.modules.defensive.endpoints import defense, guardian, soc
from app.routers import mission_router, action_router, threat_actor_router
from app.api.v1.endpoints import node_socket
from app.api.v1.endpoints import graph_topology
from app.modules.siem.siem_endpoints import router as siem_router
from app.api.v1.endpoints import config as config_endpoints
from app.routers import sensor_router, organization_router
from app.modules.misc.endpoints.devices import organizations_router

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/login", tags=["Auth"])
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(mission_router.router)
api_router.include_router(action_router.router)
api_router.include_router(threat_actor_router.router)

api_router.include_router(ops_router, tags=["Operations - Script Library & Execution"])
api_router.include_router(warroom.router, prefix="/warroom", tags=["War Room - Command Center"])
api_router.include_router(ingestion.router, prefix="/ingest", tags=["Telemetry Ingestion"])
api_router.include_router(config_endpoints.router, prefix="/config", tags=["System Configuration"])
api_router.include_router(omni_probe.router, prefix="/recon", tags=["Absolute Reconnaissance - Omni-Probe"])
api_router.include_router(osint_probe.router, prefix="/recon/osint", tags=["Global Reconnaissance - OSINT"])
api_router.include_router(deception.router, prefix="/deception", tags=["Deception Ops - The Labyrinth"])
api_router.include_router(ai_swarms.router, prefix="/swarms", tags=["AI Autonomous Swarms - The Synapse"])
api_router.include_router(sandbox.router, prefix="/sandbox", tags=["Sandboxing - The Aegis Vault"])
api_router.include_router(catalyst.router, prefix="/catalyst", tags=["Inoculation - Sentinel Catalyst"])

api_router.include_router(offensive.router, prefix="/offensive", tags=["Active Exploitation - The Spear"])
api_router.include_router(redteam.router, prefix="/redteam", tags=["Adversary Emulation - The Spear"])
api_router.include_router(ghost_c2.router, prefix="/ghost", tags=["C2 Operations - The Spear"])

api_router.include_router(forge.router, prefix="/forge", tags=["Zero-Trust Engineering - The Forge"])

api_router.include_router(oracle.router, prefix="/oracle", tags=["Predictive AI Command - The Oracle"])

api_router.include_router(entities.router, prefix="/entities", tags=["Entities"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["Analysis"])
api_router.include_router(stats.router, prefix="/stats", tags=["Stats"])
api_router.include_router(health_integrity.router, prefix="/health", tags=["Status"])
api_router.include_router(devices.router, prefix="/devices", tags=["Devices"])
api_router.include_router(ghost.router, prefix="/ghost_legacy", tags=["Ghost Shell"])
api_router.include_router(defense.router, prefix="/defense", tags=["Active Defense"])
api_router.include_router(guardian.router, prefix="/guardian", tags=["Guardian IoT"])
api_router.include_router(soc.router, prefix="/soc", tags=["Cyber Command SOC"])
api_router.include_router(socket.router, tags=["Combat Socket"])
api_router.include_router(ai_tactical.router, prefix="/ai", tags=["Tactical AI"])
api_router.include_router(ai_analyst.router, prefix="/analyst", tags=["AI Analyst"])
api_router.include_router(connectors.router, prefix="/connectors", tags=["Global Connectors"])
api_router.include_router(audit.router, prefix="/audit", tags=["Cryptographic Ledger"])
api_router.include_router(node_socket.router, prefix="/nodes", tags=["Execution Nodes"])
api_router.include_router(graph_topology.router, prefix="/intel", tags=["Threat Graph Intelligence"])

# ── Sensor agent + Organizations (human CRUD lives in devices.py's
#    organizations_router; sensor_router/organization_router are the agents'
#    own enroll/heartbeat/command-result endpoints) ─────────────────────────
api_router.include_router(sensor_router.router, tags=["Sensor Agent"])
api_router.include_router(organization_router.router, tags=["Organization Agent"])
api_router.include_router(organizations_router, prefix="/organizations", tags=["Organizations"])
# Note: sensor_router.py declares prefix="/sensor" and organization_router.py
# declares prefix="/organization-agent" on their own APIRouters, so no extra
# prefix= is added here for either (matching how mission_router.router is
# included with no extra prefix, since it already declares its own).

# ── Phase 4: SIEM / SOAR / DGA Intelligence ────────────────────────────────
api_router.include_router(siem_router, prefix="/siem", tags=["SIEM — Behavioral Analysis"])

# ── Cognitive Shield: Layer 2 — Agentic Orchestration Proxy ────────────────
from app.api.v1.endpoints.agent_proxy import router as agent_proxy_router
api_router.include_router(
    agent_proxy_router,
    prefix="/agent/proxy",
    tags=["Agentic Orchestration Proxy — Layer 2"],
)

# ── Cognitive Shield: Layer 4 — Forensic AI Observability ──────────────────
from app.api.v1.endpoints.forensic_hunt import router as forensic_router
api_router.include_router(
    forensic_router,
    prefix="/forensic/hunt",
    tags=["Forensic AI Observability — Layer 4"],
)

# ── Cognitive Shield: Layers 1,3,5 — AI Firewall Gateway ───────────────────
from app.modules.firewall.firewall_endpoints import router as firewall_router
api_router.include_router(
    firewall_router,
    prefix="/firewall",
    tags=["AI Firewall — Cognitive Shield L1/L3/L5"],
)

# ── Intelligence Phase: Adversarial Intel + Autonomous SOC + Compliance ──────
from app.modules.intelligence.intelligence_router import router as intelligence_router
api_router.include_router(
    intelligence_router,
    prefix="/intel",
    tags=["Intelligence Phase — Adversarial Intel / SOC / Compliance"],
)
from app.api.v1.intelligence import comprehensive_routes
api_router.include_router(
    comprehensive_routes.router,
    prefix="/intel",
    tags=["Sovereign Intelligence"],
)