"""
Correlation Engine — v2 (Power Upgrade)
────────────────────────────────────────
Upgrades over v1:
  • find_kill_chain(): Links anomaly events into a temporal attack sequence
  • Levenshtein fuzzy name matching (replaces exact-match fallback)
  • Bi-directional confidence propagation between linked entities
  • Relationship type scoring taxonomy
  • Full confidence matrix output for graph visualization
"""
import math
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Any, Optional
from app.schemas.entity import Entity, Attribute
from app.schemas.relationships import Relationship, LinkType
from app.schemas.evidence import Reliability, Evidence


# ─── Relationship strength weights ───────────────────────────────────────────

LINK_TYPE_STRENGTH: Dict[str, float] = {
    "SHARED_IDENTIFIER":     1.0,    # Same phone, email, IMSI — deterministic
    "SHARED_INFRASTRUCTURE": 0.90,   # Same C2 domain or IP range
    "BEHAVIORAL_PATTERN":    0.80,   # Same TTP fingerprint
    "TEMPORAL_PROXIMITY":    0.65,   # Events within tight time window
    "NAME_SIMILARITY":       0.55,   # Fuzzy name match
    "LOCATION_OVERLAP":      0.50,   # Geographical proximity
    "WEAK_ASSOCIATION":      0.35,   # Single indirect indicator
}

KILL_CHAIN_ORDER = [
    "INITIAL ACCESS", "EXECUTION", "PERSISTENCE",
    "PRIVILEGE ESCALATION", "DEFENSE EVASION",
    "CREDENTIAL ACCESS", "DISCOVERY",
    "LATERAL MOVEMENT", "COLLECTION",
    "EXFILTRATION", "IMPACT",
]


def levenshtein(a: str, b: str) -> int:
    """Full Levenshtein distance computation."""
    a, b = a.lower(), b.lower()
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            curr[j] = min(prev[j] + 1, curr[j-1] + 1, prev[j-1] + (0 if ca == cb else 1))
        prev = curr
    return prev[-1]


def name_similarity(a: str, b: str) -> float:
    """Returns 0–1 similarity score using normalized Levenshtein."""
    dist = levenshtein(a, b)
    max_len = max(len(a), len(b), 1)
    return round(1.0 - dist / max_len, 3)


class CorrelationEngine:
    """
    The analytical brain of the platform.
    Links disparate entities, surfaces kill chains, and propagates
    confidence through the intelligence graph.
    """

    CONFIDENCE_THRESHOLD = 0.65      # Lowered from 0.75 for broader coverage
    DECAY_RATE           = 0.05
    FUZZY_NAME_THRESHOLD = 0.75      # Min name similarity to propose an alias link

    # ── Core confidence calculation ───────────────────────────────────────────

    def calculate_confidence(self, method: str, evidence: List[Evidence]) -> float:
        """
        Confidence = (method_base × reliability_factor) × time_decay
        """
        base = {
            "deterministic":   1.0,
            "strong_heuristic":0.85,
            "behavioral":      0.75,
            "temporal":        0.65,
            "weak_heuristic":  0.40,
        }.get(method, 0.30)

        # Reliability penalty
        low_grades = {Reliability.D, Reliability.E, Reliability.F}
        if evidence and all(e.reliability in low_grades for e in evidence):
            base *= 0.60

        # Time decay on newest evidence
        if evidence:
            newest = max(e.collected_at for e in evidence)
            age_years = (datetime.utcnow() - newest).days / 365.0
            base *= math.exp(-self.DECAY_RATE * age_years)

        return round(min(base, 1.0), 3)

    # ── Alias detection (upgraded with fuzzy matching) ────────────────────────

    def detect_aliases(
        self, entity: Entity, candidates: List[Entity]
    ) -> List[Tuple[Entity, float, str]]:
        """
        Returns list of (candidate, confidence, match_method) for likely aliases.
        Match methods: 'shared_attribute' | 'exact_name' | 'fuzzy_name'
        """
        matches = []

        for c in candidates:
            if c.id == entity.id:
                continue

            # 1. Exact shared attribute (hard link)
            shared = set(a.value for a in entity.attributes) & set(a.value for a in c.attributes)
            if shared:
                matches.append((c, 1.0, "shared_attribute"))
                continue

            # 2. Exact name (case-insensitive)
            if entity.canonical_name.lower() == c.canonical_name.lower():
                matches.append((c, 0.60, "exact_name"))
                continue

            # 3. Fuzzy name similarity (Levenshtein)
            sim = name_similarity(entity.canonical_name, c.canonical_name)
            if sim >= self.FUZZY_NAME_THRESHOLD:
                matches.append((c, round(sim * 0.55, 3), "fuzzy_name"))

        return [(c, conf, method) for c, conf, method in matches
                if conf >= self.CONFIDENCE_THRESHOLD]

    # ── Kill-chain reconstruction ─────────────────────────────────────────────

    def find_kill_chain(
        self,
        anomaly_events: List[Dict[str, Any]],
        time_window_minutes: int = 60,
    ) -> Optional[Dict[str, Any]]:
        """
        Chains a list of anomaly dicts (with 'timestamp', 'phase', 'source_ip')
        into a temporal kill-chain sequence.

        Returns a structured kill-chain report if a chain of ≥3 events is found.
        """
        if not anomaly_events:
            return None

        # Sort by time
        def parse_ts(e: Dict) -> datetime:
            ts = e.get("timestamp", "")
            try:
                t = datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
                return t.replace(tzinfo=None) if t.tzinfo else t
            except Exception:
                return datetime.utcnow()

        sorted_events = sorted(anomaly_events, key=parse_ts)

        # Sliding window grouping
        chains = []
        current_chain = [sorted_events[0]]

        for ev in sorted_events[1:]:
            last_ts = parse_ts(current_chain[-1])
            ev_ts   = parse_ts(ev)
            if (ev_ts - last_ts) <= timedelta(minutes=time_window_minutes):
                current_chain.append(ev)
            else:
                if len(current_chain) >= 3:
                    chains.append(current_chain)
                current_chain = [ev]

        if len(current_chain) >= 3:
            chains.append(current_chain)

        if not chains:
            return None

        # Pick longest chain
        best = max(chains, key=len)
        phases_seen = [e.get("phase", "UNKNOWN") for e in best]

        # Order phases against kill-chain taxonomy
        ordered = [p for p in KILL_CHAIN_ORDER if p in phases_seen]
        extra   = [p for p in phases_seen if p not in KILL_CHAIN_ORDER]

        source_ips = list({e.get("source_ip", "") for e in best if e.get("source_ip")})
        techniques  = list({e.get("mitre_technique", "") for e in best if e.get("mitre_technique")})

        return {
            "kill_chain_confirmed": True,
            "event_count":         len(best),
            "phases_progression":  ordered + extra,
            "furthest_phase":      ordered[-1] if ordered else "UNKNOWN",
            "source_ips":          source_ips,
            "mitre_techniques":    techniques,
            "duration_minutes":    max(
                int((parse_ts(best[-1]) - parse_ts(best[0])).total_seconds() / 60), 1
            ),
            "confidence":          min(0.5 + len(best) * 0.05, 0.99),
        }

    # ── Bi-directional confidence propagation ────────────────────────────────

    def propagate_confidence(
        self,
        graph: Dict[str, Any],
        iterations: int = 3,
        damping: float = 0.65,
    ) -> Dict[str, float]:
        """
        Propagates confidence scores across a graph dict of
        { entity_id: { neighbors: [id, ...], confidence: float } }.
        Returns updated confidence dict after `iterations` passes.
        Returns {entity_id: propagated_confidence}.
        """
        scores: Dict[str, float] = {
            eid: data.get("confidence", 0.5)
            for eid, data in graph.items()
        }

        for _ in range(iterations):
            new_scores: Dict[str, float] = {}
            for eid, data in graph.items():
                neighbors = data.get("neighbors", [])
                if not neighbors:
                    new_scores[eid] = scores[eid]
                    continue
                neighbor_avg = sum(scores.get(n, 0.0) for n in neighbors) / len(neighbors)
                new_scores[eid] = round(
                    scores[eid] * (1 - damping) + neighbor_avg * damping, 4
                )
            scores = new_scores

        return scores

    # ── Relationship suggestion ───────────────────────────────────────────────

    def suggest_relationships(
        self,
        source: Entity,
        targets: List[Entity],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generates typed relationship suggestions with confidence for analyst review.
        """
        context = context or {}
        results = []

        aliases = self.detect_aliases(source, targets)
        for candidate, confidence, method in aliases:
            link_type = {
                "shared_attribute": "SHARED_IDENTIFIER",
                "exact_name":       "NAME_SIMILARITY",
                "fuzzy_name":       "NAME_SIMILARITY",
            }.get(method, "WEAK_ASSOCIATION")

            results.append({
                "source_id":   str(source.id),
                "target_id":   str(candidate.id),
                "link_type":   link_type,
                "confidence":  confidence,
                "method":      method,
                "weight":      round(confidence * LINK_TYPE_STRENGTH.get(link_type, 0.5), 3),
                "requires_analyst_review": confidence < 0.85,
            })

        return sorted(results, key=lambda r: r["confidence"], reverse=True)


correlation_engine = CorrelationEngine()
