import logging
import asyncio
import os
import uuid
import json
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_ORG_UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")


# ─── Phase 0: Canonical Default Tenant ──────────────────────────────────────────────────
def seed_default_tenant():
    """
    Creates the canonical default Tenant record with a deterministic UUID.
    Must run before init_db() so that seeded users can be linked to it.
    Idempotent — safe to run multiple times.
    """
    from app.infrastructure.session import SessionLocal
    from app.models.models import Tenant

    db = SessionLocal()
    try:
        existing = db.query(Tenant).filter(Tenant.id == DEFAULT_ORG_UUID).first()
        if not existing:
            db.add(Tenant(
                id=DEFAULT_ORG_UUID,
                name="Default Organization",
                domain="projectxy.local",
                subscription_tier="enterprise",
                is_active=True,
            ))
            db.commit()
            logger.info(f"[SEED] Default tenant created: {DEFAULT_ORG_UUID}")
        else:
            logger.info(f"[SEED] Default tenant already exists: {DEFAULT_ORG_UUID}")
    finally:
        db.close()



# ─── Phase 1: Admin & AI Advisor Users ───────────────────────────────────────
def init_db():
    """
    Idempotent user seed.  Reads all credentials from environment — no
    hardcoded values.  Safe to run multiple times.
    Expects seed_default_tenant() to have run first.
    """
    from app.infrastructure.session import SessionLocal
    from app.models.models import User
    from app.core.security import get_password_hash

    db = SessionLocal()
    try:
        users_to_seed = [
            {
                "email": os.getenv("ADMIN_USER", ""),
                "password": os.getenv("ADMIN_PASSWORD", ""),
                "full_name": "System Administrator",
                "role": "admin",
            },
            {
                "email": os.getenv("AI_ADVISOR_USER", f"ai_advisor@{os.getenv('ADMIN_USER', 'projectxy.local').split('@')[-1]}"),
                "password": os.getenv("AI_ADVISOR_PASSWORD", ""),
                "full_name": "AI Advisor Agent",
                "role": "analyst",
            },
        ]

        for u in users_to_seed:
            if not u["email"] or not u["password"]:
                logger.warning(f"[SEED] Skipping user with missing email/password — check .env")
                continue
            existing = db.query(User).filter(User.email == u["email"]).first()
            if not existing:
                new_user = User(
                    email=u["email"],
                    hashed_password=get_password_hash(u["password"]),
                    full_name=u["full_name"],
                    role=u["role"],
                    is_active=True,
                    # Link to the canonical default tenant so JWT tokens are always valid.
                    tenant_id=DEFAULT_ORG_UUID,
                )
                db.add(new_user)
                db.commit()
                logger.info(f"[SEED] User created: {u['email']} ({u['role']})")
            else:
                # Backfill tenant_id for existing users that have none.
                if not existing.tenant_id:
                    existing.tenant_id = DEFAULT_ORG_UUID
                    db.commit()
                    logger.info(f"[SEED] Backfilled tenant_id for existing user: {u['email']}")
                else:
                    logger.info(f"[SEED] User already exists: {u['email']}")
    finally:
        db.close()


# ─── Phase 2: Config Entries (Device Types Enum, Simulation Types, SOC Tools) ─
def seed_config_entries():
    """
    Seeds the config_entries table with all dynamic values the frontend
    previously had hardcoded.  Idempotent — uses INSERT OR IGNORE pattern.
    """
    from app.infrastructure.session import SessionLocal
    from app.models.config_model import ConfigEntry

    db = SessionLocal()
    try:
        entries = [
            # ── Device Types (Enum) ────────────────────────────────────────────
            {"category": "device_types", "key": "server",      "label": "Server",      "value": {"icon": "Server",   "color": "sky"}},
            {"category": "device_types", "key": "workstation",  "label": "Workstation", "value": {"icon": "Laptop",   "color": "indigo"}},
            {"category": "device_types", "key": "network",      "label": "Network",     "value": {"icon": "Network",  "color": "violet"}},
            {"category": "device_types", "key": "iot",          "label": "IoT",         "value": {"icon": "Cpu",      "color": "amber"}},
            {"category": "device_types", "key": "mobile",       "label": "Mobile",      "value": {"icon": "Smartphone","color": "emerald"}},
            {"category": "device_types", "key": "ot_ics",       "label": "OT/ICS",      "value": {"icon": "Zap",      "color": "orange"}},
            {"category": "device_types", "key": "cloud",        "label": "Cloud",       "value": {"icon": "Cloud",    "color": "cyan"}},

            # ── SOC Simulation Types ───────────────────────────────────────────
            {"category": "simulation_types", "key": "ransomware_detected",    "label": "Ransomware Detected",      "value": {"severity": "CRITICAL", "mitre": "T1486"}},
            {"category": "simulation_types", "key": "lateral_movement",       "label": "Lateral Movement",         "value": {"severity": "HIGH",     "mitre": "T1021"}},
            {"category": "simulation_types", "key": "credential_dump",        "label": "Credential Dump",          "value": {"severity": "HIGH",     "mitre": "T1003"}},
            {"category": "simulation_types", "key": "c2_beacon",              "label": "C2 Beacon Detected",       "value": {"severity": "CRITICAL", "mitre": "T1071"}},
            {"category": "simulation_types", "key": "data_exfiltration",      "label": "Data Exfiltration",        "value": {"severity": "HIGH",     "mitre": "T1041"}},
            {"category": "simulation_types", "key": "privilege_escalation",   "label": "Privilege Escalation",     "value": {"severity": "CRITICAL", "mitre": "T1068"}},
            {"category": "simulation_types", "key": "supply_chain_compromise","label": "Supply Chain Compromise",  "value": {"severity": "CRITICAL", "mitre": "T1195"}},

            # ── Offensive Tools ────────────────────────────────────────────────
            {"category": "offensive_tools", "key": "nmap",          "label": "Nmap",           "value": {"category": "Reconnaissance", "risk": "low"}},
            {"category": "offensive_tools", "key": "masscan",       "label": "Masscan",        "value": {"category": "Reconnaissance", "risk": "low"}},
            {"category": "offensive_tools", "key": "metasploit",    "label": "Metasploit",     "value": {"category": "Exploitation",   "risk": "critical"}},
            {"category": "offensive_tools", "key": "sqlmap",        "label": "SQLMap",         "value": {"category": "Exploitation",   "risk": "high"}},
            {"category": "offensive_tools", "key": "hydra",         "label": "Hydra",          "value": {"category": "Credential",     "risk": "high"}},
            {"category": "offensive_tools", "key": "burpsuite",     "label": "Burp Suite",     "value": {"category": "Web",           "risk": "medium"}},
            {"category": "offensive_tools", "key": "mimikatz",      "label": "Mimikatz",       "value": {"category": "Credential",     "risk": "critical"}},
            {"category": "offensive_tools", "key": "bloodhound",    "label": "BloodHound",     "value": {"category": "Recon/AD",      "risk": "high"}},
            {"category": "offensive_tools", "key": "empire",        "label": "Empire C2",      "value": {"category": "C2",            "risk": "critical"}},
            {"category": "offensive_tools", "key": "cobaltstrike",  "label": "Cobalt Strike",  "value": {"category": "C2",            "risk": "critical"}},

            # ── SOC Playbooks ──────────────────────────────────────────────────
            {"category": "soc_playbooks", "key": "pb_ransomware",      "label": "Ransomware Response",       "value": {"steps": ["Isolate host", "Snapshot memory", "Kill suspicious processes", "Restore from backup", "Patch CVE"], "auto_isolate": True}},
            {"category": "soc_playbooks", "key": "pb_lateral_move",    "label": "Lateral Movement Playbook", "value": {"steps": ["Identify source IP", "Map AD path", "Revoke session tokens", "Rotate credentials", "Enable MFA"], "auto_isolate": True}},
            {"category": "soc_playbooks", "key": "pb_cred_dump",       "label": "Credential Dump Response",  "value": {"steps": ["Force password reset", "Audit LSASS access", "Enable credential guard", "Notify affected users"], "auto_isolate": False}},
            {"category": "soc_playbooks", "key": "pb_c2_detection",    "label": "C2 Beacon Playbook",        "value": {"steps": ["Block C2 domain/IP", "Terminate process", "Capture PCAP", "Submit IOCs to SIEM"], "auto_isolate": True}},
            {"category": "soc_playbooks", "key": "pb_exfiltration",    "label": "Data Exfiltration Response","value": {"steps": ["Block egress path", "Revoke cloud tokens", "Identify exfiltrated data", "Notify DPO"], "auto_isolate": True}},
            {"category": "soc_playbooks", "key": "pb_phishing",        "label": "Phishing Response",         "value": {"steps": ["Quarantine email", "Reset user password", "Revoke OAuth tokens", "Awareness training"], "auto_isolate": False}},
            {"category": "soc_playbooks", "key": "pb_supply_chain",    "label": "Supply Chain Playbook",     "value": {"steps": ["Identify affected packages", "Block package registry", "Audit CI/CD pipeline", "Notify upstream vendor"], "auto_isolate": False}},
        ]

        seeded = 0
        for entry in entries:
            existing = db.query(ConfigEntry).filter(
                ConfigEntry.category == entry["category"],
                ConfigEntry.key == entry["key"],
            ).first()
            if not existing:
                db.add(ConfigEntry(
                    id=uuid.uuid4(),
                    category=entry["category"],
                    key=entry["key"],
                    label=entry["label"],
                    value=entry["value"],
                    is_active=True,
                ))
                seeded += 1

        db.commit()
        logger.info(f"[SEED] Config entries: {seeded} new entries seeded.")
    finally:
        db.close()


# ─── Phase 3: Threat Actors + CVEs (Graph + Postgres) ────────────────────────
async def seed_threat_data():
    """
    Seeds the database with production-ready threat actor and CVE data.
    Idempotent — checks before inserting.
    """
    from app.infrastructure.session import SessionLocal
    from app.models.models import EntityDB, AttributeDB
    from app.infrastructure.graph import graph_db

    db = SessionLocal()
    graph_ready = False

    try:
        await graph_db.connect()
        graph_ready = True
    except Exception as exc:
        logger.info(f"[SEED] Neo4j unavailable, continuing without graph writes: {exc}")

    try:
        threat_actors = [
            {"name": "Lazarus Group",       "description": "North Korean state-sponsored group (DPRK RGB). Targets financial institutions and critical infrastructure.", "risk_score": 95},
            {"name": "APT28 (Fancy Bear)",  "description": "Russian GRU Unit 26165. Targets governments, militaries, and political organizations via spear-phishing.", "risk_score": 92},
            {"name": "APT41 (Barium)",      "description": "Chinese state-sponsored group conducting dual espionage and financial crime operations.", "risk_score": 90},
            {"name": "APT29 (Cozy Bear)",   "description": "Russian SVR group. Known for stealthy supply chain attacks including SolarWinds.", "risk_score": 93},
            {"name": "FIN7",                "description": "Financially motivated group targeting POS systems, hospitality, and retail sectors.", "risk_score": 80},
            {"name": "Sandworm Team",       "description": "Russian GRU Unit 74455. Responsible for NotPetya, Industroyer, and Ukrainian power grid attacks.", "risk_score": 98},
            {"name": "Charming Kitten",     "description": "Iranian APT (IRGC-linked) targeting academics, journalists, and dissidents via social engineering.", "risk_score": 82},
            {"name": "REvil (Sodinokibi)", "description": "Russian-linked ransomware-as-a-service group. Responsible for JBS and Kaseya attacks.", "risk_score": 88},
        ]

        cves = {
            "Lazarus Group":      ["CVE-2023-38831", "CVE-2023-42793", "CVE-2021-44228"],
            "APT28 (Fancy Bear)": ["CVE-2023-23397", "CVE-2023-36884", "CVE-2022-30190"],
            "APT41 (Barium)":     ["CVE-2023-2868",  "CVE-2023-34362", "CVE-2021-26855"],
            "APT29 (Cozy Bear)":  ["CVE-2020-4006",  "CVE-2021-26857", "CVE-2023-29357"],
            "FIN7":               ["CVE-2022-30190", "CVE-2022-2184"],
            "Sandworm Team":      ["CVE-2023-38408", "CVE-2022-42856", "CVE-2022-13871"],
            "Charming Kitten":    ["CVE-2021-34473", "CVE-2021-31207"],
            "REvil (Sodinokibi)": ["CVE-2021-30116", "CVE-2019-2725"],
        }

        for actor_data in threat_actors:
            actor_name = actor_data["name"]
            logger.info(f"[SEED] Threat actor: {actor_name}")

            entity = db.query(EntityDB).filter(EntityDB.canonical_name == actor_name).first()
            if not entity:
                entity = EntityDB(
                    canonical_name=actor_name,
                    type="threat-actor",
                    risk_score=actor_data["risk_score"],
                )
                db.add(entity)
                db.commit()

            if graph_ready:
                try:
                    await graph_db.execute_query(
                        "MERGE (a:ThreatActor {name: $name}) SET a.description = $description, a.risk_score = $risk_score",
                        {"name": actor_name, "description": actor_data["description"], "risk_score": actor_data["risk_score"]},
                    )
                except Exception as exc:
                    logger.warning(f"[SEED] Graph write skipped for {actor_name}: {exc}")

            for cve_id in cves.get(actor_name, []):
                value_hash = hashlib.sha256(cve_id.encode()).hexdigest()
                attribute = db.query(AttributeDB).filter(AttributeDB.value_hash == value_hash).first()
                if not attribute:
                    db.add(AttributeDB(
                        entity_id=entity.id,
                        type="cve",
                        value=cve_id,
                        value_hash=value_hash,
                        source="internal-seed",
                        confidence=0.95,
                    ))

                if graph_ready:
                    try:
                        await graph_db.execute_query(
                            """
                            MERGE (c:CVE {id: $cve_id})
                            WITH c
                            MATCH (a:ThreatActor {name: $actor_name})
                            MERGE (a)-[:USES]->(c)
                            """,
                            {"cve_id": cve_id, "actor_name": actor_name},
                        )
                    except Exception as exc:
                        logger.warning(f"[SEED] Graph relation skipped for {actor_name}/{cve_id}: {exc}")

        db.commit()
        logger.info("[SEED] Threat data seeding complete.")
    finally:
        db.close()
        if graph_ready:
            await graph_db.close()


# ─── Phase 4: Operations Arsenal ─────────────────────────────────────────────
async def seed_arsenal():
    try:
        from app.infrastructure.session import SessionLocal
        from app.services.ops.seed_arsenal import seed_operations_arsenal

        db = SessionLocal()
        try:
            seed_operations_arsenal(db)
        finally:
            db.close()
        logger.info("[SEED] Operations arsenal seeded.")
    except Exception as e:
        logger.warning(f"[SEED] Arsenal seed skipped (non-critical): {e}")


# ─── Entrypoint ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("  ProjectXY — Production Seed Runner")
    logger.info("=" * 60)

    logger.info("[PHASE 0] Seeding canonical default tenant...")
    seed_default_tenant()

    logger.info("[PHASE 1] Seeding admin users...")
    init_db()

    logger.info("[PHASE 2] Seeding config entries...")
    seed_config_entries()

    logger.info("[PHASE 3] Seeding threat intelligence...")
    asyncio.run(seed_threat_data())

    logger.info("[PHASE 4] Seeding operations arsenal...")
    asyncio.run(seed_arsenal())

    logger.info("=" * 60)
    logger.info("  Seed complete. System ready.")
    logger.info("=" * 60)
