import math
from datetime import datetime, timezone
import logging
from typing import List, Dict, Any, Optional
from app.infrastructure.graph import graph_db

logger = logging.getLogger(__name__)


class CorrelationEngine:
    """
    Graph-based Threat Correlation Engine (Neo4j-backed).
    Leverages shortest-path traversal, cluster detection,
    and kill-chain timeline reconstruction.
    """

    DECAY_RATE = 0.05

    # ── Time-decay confidence ─────────────────────────────────────────────────

    def calculate_time_decay_confidence(self, base: float, timestamp_iso: str) -> float:
        try:
            t = datetime.fromisoformat(timestamp_iso.replace("Z", "+00:00"))
            age_years = (datetime.now(timezone.utc) - t).days / 365.25
            return round(base * math.exp(-self.DECAY_RATE * max(0, age_years)), 2)
        except Exception as e:
            logger.error(f"Time decay error: {e}")
            return round(base * 0.5, 2)

    # ── Evidence scoring ──────────────────────────────────────────────────────

    def calculate_evidence_score(self, reliability_level: str) -> float:
        return {"A": 1.0, "B": 0.8, "C": 0.6, "D": 0.4, "E": 0.2, "F": 0.1}.get(
            reliability_level.upper(), 0.1
        )
    # ── Graph proximity (used by RiskEngine) ──────────────────────────────────

    async def calculate_graph_proximity(self, target_ip: str) -> Dict[str, Any]:
        """
        Calculates shortest path distance from target to known threat actors.
        Returns proximity score: dist=1 → 30pts, dist=2 → 15pts, dist=3 → 5pts.
        """
        query = """
        MATCH (target:IP {value: $ip})
        MATCH (threat:ThreatActor)
        MATCH path = shortestPath((target)-[*1..3]-(threat))
        RETURN threat.name AS threat_name,
               length(path) AS distance,
               [n IN nodes(path) | labels(n)[0]] AS node_types
        ORDER BY distance ASC
        LIMIT 5
        """
        try:
            results = await graph_db.execute_query(query, {"ip": target_ip})
            if not results:
                return {"score": 0.0, "closest_threats": []}

            min_dist = min(r["distance"] for r in results)
            score = {1: 30.0, 2: 15.0}.get(min_dist, 5.0)

            return {
                "score": score,
                "closest_threats": [
                    {"threat": r["threat_name"], "distance": r["distance"]}
                    for r in results
                ],
            }
        except Exception as e:
            logger.error(f"Graph proximity failed for {target_ip}: {e}")
            return {"score": 0.0, "closest_threats": []}

    # ── Alias for RiskEngine backward-compat ──────────────────────────────────

    async def get_graph_proximity_to_threats(self, target_ip: str) -> Dict[str, Any]:
        """Alias for calculate_graph_proximity — used by RiskEngine."""
        return await self.calculate_graph_proximity(target_ip)

    # ── Attack cluster detection ───────────────────────────────────────────────

    async def find_attack_cluster(self, target_ip: str) -> List[Dict[str, Any]]:
        """
        Finds sibling IPs targeting the same internal assets.
        Returns ranked list with shared_target count and sibling risk.
        """
        query = """
        MATCH (target:IP {value: $ip})-[:TARGETS]->(asset:InternalAsset)
        MATCH (sibling:IP)-[:TARGETS]->(asset)
        WHERE sibling.value <> $ip
        WITH sibling.value AS sibling_ip, count(asset) AS shared_targets,
             collect(asset.name)[..3] AS sample_assets
        RETURN sibling_ip, shared_targets, sample_assets
        ORDER BY shared_targets DESC
        LIMIT 10
        """
        try:
            results = await graph_db.execute_query(query, {"ip": target_ip})
            for r in results:
                r["sibling_score"] = min(r.get("shared_targets", 0) * 10, 100)
            return results
        except Exception as e:
            logger.error(f"Cluster detection failed for {target_ip}: {e}")
            return []
    # ── Timeline Reconstruction ───────────────────────────────────────────────

    async def reconstruct_attack_timeline(self, incident_id: str) -> Dict[str, Any]:
        """Reconstructs a kill-chain event timeline from the graph."""
        query = """
        MATCH (incident:Incident {id: $incident_id})-[:INVOLVES]->(event:TelemetryEvent)
        RETURN event.timestamp AS time, event.type AS type, event.source_ip AS source,
               event.target AS target, event.technique AS technique, event.phase AS phase
        ORDER BY event.timestamp ASC
        """
        try:
            events = await graph_db.execute_query(query, {"incident_id": incident_id})
            for ev in events:
                if not ev.get("phase"):
                    ev["phase"] = self._infer_phase(ev.get("type", ""))
            return {
                "incident_id": incident_id,
                "event_count": len(events),
                "timeline": events,
                "phases_seen": list({ev.get("phase") for ev in events if ev.get("phase")}),
            }
        except Exception as e:
            logger.error(f"Timeline reconstruction failed: {e}")
            return {"incident_id": incident_id, "event_count": 0, "timeline": []}

    def _infer_phase(self, event_type: str) -> str:
        t = event_type.upper()
        if any(k in t for k in ("LOGIN", "AUTH", "BRUTE")):   return "INITIAL ACCESS"
        if any(k in t for k in ("EXEC", "SCRIPT", "SHELL")):  return "EXECUTION"
        if any(k in t for k in ("PERSIST", "REGISTRY")):      return "PERSISTENCE"
        if any(k in t for k in ("PRIV", "ESCALAT", "TOKEN")): return "PRIVILEGE ESCALATION"
        if any(k in t for k in ("LATERAL", "SMB", "RDP")):    return "LATERAL MOVEMENT"
        if any(k in t for k in ("LSASS", "CRED", "DUMP")):    return "CREDENTIAL ACCESS"
        if any(k in t for k in ("EXFIL", "UPLOAD", "TRANSFER")): return "EXFILTRATION"
        if any(k in t for k in ("RANSOM", "WIPE", "DESTRUCT")): return "IMPACT"
        return "DISCOVERY"

    # ── Campaign correlation ───────────────────────────────────────────────────

    async def correlate_campaign(self, c2_domain: str) -> Dict[str, Any]:
        """Links all IPs communicating to the same C2 domain into a campaign."""
        query = """
        MATCH (ip:IP)-[:COMMUNICATES_TO]->(c2:C2Infrastructure {domain: $domain})
        WITH collect(ip.value) AS actor_ips, count(ip) AS actor_count
        MATCH (victim:InternalAsset)<-[:TARGETS]-(actor:IP)
        WHERE actor.value IN actor_ips
        RETURN actor_ips, actor_count, collect(DISTINCT victim.name)[..10] AS compromised_assets, count(DISTINCT victim) AS victim_count
        LIMIT 1
        """
        try:
            results = await graph_db.execute_query(query, {"domain": c2_domain})
            if not results:
                return {"c2_domain": c2_domain, "campaign_detected": False, "actor_ips": [], "victim_count": 0}
            r = results[0]
            return {
                "c2_domain": c2_domain, "campaign_detected": r["actor_count"] > 1, "actor_ips": r.get("actor_ips", []),
                "actor_count": r.get("actor_count", 0), "compromised_assets": r.get("compromised_assets", []), "victim_count": r.get("victim_count", 0),
            }
        except Exception as e:
            logger.error(f"Campaign correlation failed for {c2_domain}: {e}")
            return {"c2_domain": c2_domain, "campaign_detected": False, "error": str(e)}

    # ── Entity ego-graph summary ───────────────────────────────────────────────

    async def entity_graph_summary(self, entity_id: str) -> Dict[str, Any]:
        """Returns an ego-graph summary: the entity + all 1-hop neighbors."""
        query = """
        MATCH (e {id: $entity_id})-[r]-(neighbor)
        RETURN type(r) AS relationship, labels(neighbor)[0] AS neighbor_type,
               neighbor.name AS neighbor_name, neighbor.id AS neighbor_id, neighbor.risk_score AS risk_score
        LIMIT 25
        """
        try:
            results = await graph_db.execute_query(query, {"entity_id": entity_id})
            return {
                "entity_id": entity_id, "connections": results, "connection_count": len(results),
                "high_risk_neighbors": [r for r in results if (r.get("risk_score") or 0) > 70],
            }
        except Exception as e:
            logger.error(f"Entity summary failed for {entity_id}: {e}")
            return {"entity_id": entity_id, "connections": [], "connection_count": 0}


correlation_engine = CorrelationEngine()
# ── PRODUCTION STREAM PROCESSING PIPELINE (SIEM ADDITION) ─────────────────────
import json
import time
from aiokafka import AIOKafkaConsumer
from redis.asyncio import Redis

class CorrelationStreamProcessor:
    """
    High-performance stream processor extending CorrelationEngine.
    Evaluates sliding-window rules at O(1) inside Redis prior to graph write logs.
    """
    def __init__(self, kafka_broker: str = "kafka:29092", redis_url: str = "redis://redis:6379/0"):
        self.kafka_broker = kafka_broker
        self.redis_url = redis_url
        self.consumer = None
        self.redis = None

    async def initialize(self):
        self.redis = Redis.from_url(self.redis_url, decode_responses=True)
        self.consumer = AIOKafkaConsumer(
            'security.events',
            bootstrap_servers=self.kafka_broker,
            group_id='siem-core-group',
            auto_offset_reset='latest',
            enable_auto_commit=True
        )
        await self.consumer.start()
        logger.info("🛡️ Production SIEM Stream Processor listening live on: [security.events]")

    async def start_event_loop(self):
        try:
            async for message in self.consumer:
                event_data = json.loads(message.value.decode('utf-8'))
                await self.evaluate_realtime_rules(event_data)
        except Exception as e:
            logger.error(f"Critical stream consumer loop failure: {e}")
        finally:
            if self.consumer:
                await self.consumer.stop()

    async def evaluate_realtime_rules(self, event: dict):
        action = event.get("action")
        tenant_id = event.get("tenant_id")
        source_ip = event.get("source_ip", "unknown")
        current_time = time.time()

        if action in ("user.login_failed", "AUTH_FAILURE", "BRUTE"):
            window_key = f"siem:brute:{tenant_id}:{source_ip}"
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.zadd(window_key, {f"{current_time}:{source_ip}": current_time})
                pipe.zremrangebyscore(window_key, 0, current_time - 10)
                pipe.zcard(window_key)
                pipe.expire(window_key, 15)
                _, _, failed_count, _ = await pipe.execute()

            if failed_count >= 5:
                logger.warning(f"🚨 [SIEM MATCH] Brute force threshold breached for IP: {source_ip}")
                try:
                    from app.services.response_orchestrator import response_orchestrator
                    await response_orchestrator.execute_mitigation_playbook(tenant_id, source_ip, "T1110_BRUTE_FORCE")
                except Exception as integration_err:
                    logger.error(f"Failed to hand off alert context to ResponseOrchestrator: {integration_err}")

# Instantiate global accessible engine handler handle
stream_processor = CorrelationStreamProcessor()
