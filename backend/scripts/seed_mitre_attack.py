#!/usr/bin/env python3
"""
backend/scripts/seed_mitre_attack.py
Seeds Neo4j with MITRE ATT&CK data.

Strategy:
  1. Try bundled JSON at /app/resources/mitre_attack_v14.json (offline/fast)
  2. Fall back to live download from MITRE CTI GitHub (requires internet)

Usage:
  python seed_mitre_attack.py                  # bundled + live fallback
  python seed_mitre_attack.py --bundled-only   # bundled only (air-gapped)
  python seed_mitre_attack.py --live-only      # force live pull
"""
from __future__ import annotations
import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import httpx
from neo4j import AsyncGraphDatabase

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[MITRE] %(message)s")

# ── Config ────────────────────────────────────────────────────────────────────
NEO4J_URI      = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER     = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

BUNDLED_PATH = Path("/app/resources/mitre_attack_v14.json")
LIVE_URL     = (
    "https://raw.githubusercontent.com/mitre/cti/master/"
    "enterprise-attack/enterprise-attack.json"
)

SUPPORTED_TYPES = {
    "attack-pattern",   # Techniques
    "x-mitre-tactic",  # Tactics
    "intrusion-set",    # APT Groups
    "tool",             # Software tools
    "malware",          # Malware families
    "course-of-action", # Mitigations
    "relationship",     # Relationships
}


# ── Data Loading ──────────────────────────────────────────────────────────────

def load_bundled() -> dict | None:
    if BUNDLED_PATH.exists():
        log.info("Loading bundled MITRE ATT&CK from %s", BUNDLED_PATH)
        return json.loads(BUNDLED_PATH.read_text())
    log.warning("Bundled file not found at %s", BUNDLED_PATH)
    return None


async def load_live() -> dict | None:
    log.info("Fetching live MITRE ATT&CK from GitHub CTI repo...")
    try:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            resp = await client.get(LIVE_URL)
            resp.raise_for_status()
            data = resp.json()
            log.info("✅ Live pull: %d objects downloaded", len(data.get("objects", [])))
            # Cache locally for next boot
            BUNDLED_PATH.parent.mkdir(parents=True, exist_ok=True)
            BUNDLED_PATH.write_text(json.dumps(data))
            log.info("Cached live data to %s", BUNDLED_PATH)
            return data
    except Exception as exc:
        log.error("Live pull failed: %s", exc)
        return None


# ── Neo4j Seeding ─────────────────────────────────────────────────────────────

def _ext_id(obj: dict) -> str:
    """Extract MITRE external ID (e.g. T1059) from STIX object."""
    for ref in obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            return ref.get("external_id", "")
    return obj.get("x_mitre_id", "")


async def seed_neo4j(objects: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {t: 0 for t in SUPPORTED_TYPES}
    counts["relationship"] = 0
    counts["error"] = 0

    driver = AsyncGraphDatabase.driver(
        NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
    )

    try:
        async with driver.session() as session:
            # Constraints (idempotent)
            for label, prop in [
                ("MitreTechnique", "mitre_id"),
                ("MitreTactic", "shortname"),
                ("MitreGroup", "mitre_id"),
                ("MitreSoftware", "mitre_id"),
                ("MitreMitigation", "mitre_id"),
            ]:
                await session.run(
                    f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
                )

            for obj in objects:
                obj_type = obj.get("type", "")
                if obj_type not in SUPPORTED_TYPES:
                    continue

                stix_id  = obj.get("id", "")
                name     = obj.get("name", "Unknown")
                mitre_id = _ext_id(obj)
                desc     = (obj.get("description") or "")[:500]

                try:
                    if obj_type == "attack-pattern":
                        phase = ""
                        for kc in obj.get("kill_chain_phases", []):
                            if kc.get("kill_chain_name") == "mitre-attack":
                                phase = kc.get("phase_name", "")
                                break
                        await session.run(
                            """
                            MERGE (t:MitreTechnique {mitre_id: $mitre_id})
                            SET t.name = $name, t.description = $desc,
                                t.tactic = $phase, t.stix_id = $stix_id
                            """,
                            mitre_id=mitre_id, name=name, desc=desc,
                            phase=phase, stix_id=stix_id,
                        )
                        counts["attack-pattern"] += 1

                    elif obj_type == "x-mitre-tactic":
                        shortname = obj.get("x_mitre_shortname", name.lower().replace(" ", "-"))
                        await session.run(
                            """
                            MERGE (t:MitreTactic {shortname: $shortname})
                            SET t.name = $name, t.description = $desc, t.stix_id = $stix_id
                            """,
                            shortname=shortname, name=name, desc=desc, stix_id=stix_id,
                        )
                        counts["x-mitre-tactic"] += 1

                    elif obj_type == "intrusion-set":
                        aliases = obj.get("aliases", [])
                        await session.run(
                            """
                            MERGE (g:MitreGroup {mitre_id: $mitre_id})
                            SET g.name = $name, g.description = $desc,
                                g.aliases = $aliases, g.stix_id = $stix_id
                            """,
                            mitre_id=mitre_id, name=name, desc=desc,
                            aliases=aliases, stix_id=stix_id,
                        )
                        counts["intrusion-set"] += 1

                    elif obj_type in ("tool", "malware"):
                        label = "MitreSoftware"
                        await session.run(
                            f"""
                            MERGE (s:{label} {{mitre_id: $mitre_id}})
                            SET s.name = $name, s.description = $desc,
                                s.software_type = $sw_type, s.stix_id = $stix_id
                            """,
                            mitre_id=mitre_id, name=name, desc=desc,
                            sw_type=obj_type, stix_id=stix_id,
                        )
                        counts["tool"] = counts.get("tool", 0) + 1

                    elif obj_type == "course-of-action":
                        await session.run(
                            """
                            MERGE (m:MitreMitigation {mitre_id: $mitre_id})
                            SET m.name = $name, m.description = $desc, m.stix_id = $stix_id
                            """,
                            mitre_id=mitre_id, name=name, desc=desc, stix_id=stix_id,
                        )
                        counts["course-of-action"] = counts.get("course-of-action", 0) + 1

                    elif obj_type == "relationship":
                        rel_type    = obj.get("relationship_type", "RELATED_TO").upper().replace("-", "_")
                        src_id      = obj.get("source_ref", "")
                        tgt_id      = obj.get("target_ref", "")
                        await session.run(
                            f"""
                            MATCH (src {{stix_id: $src_id}})
                            MATCH (tgt {{stix_id: $tgt_id}})
                            MERGE (src)-[:{rel_type}]->(tgt)
                            """,
                            src_id=src_id, tgt_id=tgt_id,
                        )
                        counts["relationship"] += 1

                except Exception as exc:
                    counts["error"] += 1
                    if counts["error"] <= 5:
                        log.debug("Seed error on %s: %s", stix_id, exc)

    finally:
        await driver.close()

    return counts


# ── Main ──────────────────────────────────────────────────────────────────────

async def main(bundled_only: bool = False, live_only: bool = False) -> None:
    data: dict | None = None

    if not live_only:
        data = load_bundled()

    if data is None and not bundled_only:
        data = await load_live()

    if data is None:
        log.error("No MITRE ATT&CK data available. Seed skipped.")
        sys.exit(0)  # Non-fatal — app still starts

    objects = data.get("objects", [])
    log.info("Seeding %d STIX objects into Neo4j at %s...", len(objects), NEO4J_URI)

    counts = await seed_neo4j(objects)

    log.info("✅ MITRE ATT&CK seed complete:")
    for k, v in counts.items():
        if v > 0:
            log.info("   %-20s %d", k, v)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed MITRE ATT&CK into Neo4j")
    parser.add_argument("--bundled-only", action="store_true", help="Use bundled JSON only")
    parser.add_argument("--live-only",    action="store_true", help="Force live download")
    args = parser.parse_args()

    asyncio.run(main(bundled_only=args.bundled_only, live_only=args.live_only))
