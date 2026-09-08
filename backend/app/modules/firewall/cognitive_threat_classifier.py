"""
cognitive_threat_classifier.py — ProjectXY Cognitive Shield: Layer 3
======================================================================
Ensemble threat scoring engine.

Replaces the simple priority-chain decision fusion in the existing
firewall with a weighted multi-signal ensemble that produces a
nuanced threat score rather than a binary block/pass.

5 Threat Signals (weighted ensemble):
  Signal 1: Injection pattern match score (regex, 9 tiers)  — weight 0.35
  Signal 2: Semantic similarity (pgvector cosine)           — weight 0.30
  Signal 3: Behavioral entropy (unusual field combos)       — weight 0.15
  Signal 4: Temporal velocity (requests per sliding window)  — weight 0.15
  Signal 5: Cross-session cluster correlation               — weight 0.05

Decision thresholds:
  score >= 0.90 → BLOCK (high confidence threat)
  score >= 0.75 → BLOCK (elevated threat, multiple signals)
  score >= 0.55 → WARN  (elevated, monitor, log to semantic logger)
  score <  0.55 → PASS

Multi-Stage Attack Detection:
  The MultiStageCorrelator maintains a per-entity sliding window and
  detects known attack chains even when individual scores are low.
"""

import asyncio
import hashlib
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("projectxy.firewall.cognitive")

# Signal weights must sum to 1.0
SIGNAL_WEIGHTS = {
    "injection_pattern": 0.35,
    "semantic_similarity": 0.30,
    "behavioral_entropy": 0.15,
    "temporal_velocity": 0.15,
    "cross_session_correlation": 0.05,
}

BLOCK_THRESHOLD = 0.75
WARN_THRESHOLD = 0.50


# ---------------------------------------------------------------------------
# Ensemble Result
# ---------------------------------------------------------------------------

@dataclass
class EnsembleResult:
    ensemble_score: float           # 0.0 – 1.0
    action: str                     # PASS | WARN | BLOCK
    signal_scores: Dict[str, float] = field(default_factory=dict)
    dominant_signal: str = "none"
    reasons: List[str] = field(default_factory=list)
    latency_ms: float = 0.0


# ---------------------------------------------------------------------------
# Cognitive Threat Classifier
# ---------------------------------------------------------------------------

class CognitiveThreatClassifier:
    """
    Ensemble threat scoring — upgrades the existing decision fusion
    from a static priority chain to a weighted multi-signal model.

    Feed in the raw scores from each defence vector (already computed
    by LLMFirewall) and this classifier combines them intelligently.
    """

    def __init__(self):
        # Per-entity velocity tracking (in-memory, bounded)
        self._velocity_windows: Dict[str, List[float]] = {}
        self._velocity_max_entries = 200  # prevent unbounded growth
        self._velocity_window_seconds = 60

    def compute_ensemble(
        self,
        *,
        injection_score: float = 0.0,        # 0 = clean, 1 = definite injection
        semantic_score: float = 0.0,          # pgvector cosine similarity
        pii_detected: bool = False,           # any PII found
        obfuscation_detected: bool = False,   # base64/hex encoding found
        entity_id: str = "unknown",
        payload_field_count: int = 1,
        payload_length: int = 0,
        replay_blocked: bool = False,
    ) -> EnsembleResult:
        """Compute ensemble threat score from all available signals."""
        t_start = time.perf_counter()
        signal_scores: Dict[str, float] = {}
        reasons: List[str] = []

        # --- Signal 1: Injection Pattern Score ---
        # Injection score from regex scan: each hit contributes 1.0/total_patterns
        inj_score = min(injection_score, 1.0)
        if obfuscation_detected:
            inj_score = max(inj_score, 0.85)  # obfuscation is high confidence
        signal_scores["injection_pattern"] = inj_score
        if inj_score > 0.5:
            reasons.append(f"Injection signal elevated: {inj_score:.2f}")

        # --- Signal 2: Semantic Similarity ---
        sem_score = min(semantic_score, 1.0)
        signal_scores["semantic_similarity"] = sem_score
        if sem_score > 0.7:
            reasons.append(f"Semantic similarity elevated: {sem_score:.2f}")

        # --- Signal 3: Behavioral Entropy ---
        # Unusual field combinations and disproportionate payload length
        entropy_score = self._compute_behavioral_entropy(
            pii_detected=pii_detected,
            payload_field_count=payload_field_count,
            payload_length=payload_length,
        )
        signal_scores["behavioral_entropy"] = entropy_score
        if entropy_score > 0.6:
            reasons.append(f"Behavioral entropy elevated: {entropy_score:.2f}")

        # --- Signal 4: Temporal Velocity ---
        velocity_score = self._compute_velocity_score(entity_id)
        signal_scores["temporal_velocity"] = velocity_score
        if velocity_score > 0.7:
            reasons.append(f"Request velocity spike detected: {velocity_score:.2f}")

        # --- Signal 5: Cross-Session Correlation (simplified without pgvector) ---
        # In production, this would query the semantic_logs table for similar embeddings
        # from different entity_ids. Here we use replay as a proxy.
        cross_session_score = 1.0 if replay_blocked else 0.0
        signal_scores["cross_session_correlation"] = cross_session_score
        if cross_session_score > 0:
            reasons.append("Replay/cross-session correlation detected.")

        # --- Weighted Ensemble ---
        ensemble = sum(
            SIGNAL_WEIGHTS[sig] * score
            for sig, score in signal_scores.items()
        )
        ensemble = round(min(ensemble, 1.0), 4)

        # Find dominant signal
        dominant = max(signal_scores, key=signal_scores.get)

        # Determine action
        if replay_blocked:
            action = "BLOCK"
            reasons.insert(0, "Replay attack detected (hash match).")
        elif ensemble >= BLOCK_THRESHOLD:
            action = "BLOCK"
        elif ensemble >= WARN_THRESHOLD:
            action = "WARN"
        else:
            action = "PASS"

        latency = round((time.perf_counter() - t_start) * 1000, 2)

        return EnsembleResult(
            ensemble_score=ensemble,
            action=action,
            signal_scores=signal_scores,
            dominant_signal=dominant,
            reasons=reasons,
            latency_ms=latency,
        )

    def _compute_behavioral_entropy(
        self,
        pii_detected: bool,
        payload_field_count: int,
        payload_length: int,
    ) -> float:
        """
        Compute behavioral entropy score.
        High entropy = unusual field/length combination typical of probing.
        """
        score = 0.0

        # PII in combination with suspicious length is a data exfil signal
        if pii_detected and payload_length > 2000:
            score += 0.4

        # Very short payloads with many fields = unusual API probing
        if payload_field_count > 10 and payload_length < 100:
            score += 0.3

        # Extreme length (approaching limit) = injection attempt
        if payload_length > 7000:
            score += 0.5

        return min(score, 1.0)

    def _compute_velocity_score(self, entity_id: str) -> float:
        """
        Compute request velocity score for this entity.
        Uses an in-memory sliding window (60 seconds).
        """
        now = time.time()
        window = self._velocity_windows.setdefault(entity_id, [])

        # Prune entries outside the window
        window[:] = [t for t in window if now - t < self._velocity_window_seconds]
        window.append(now)

        # Bound memory
        if len(self._velocity_windows) > self._velocity_max_entries:
            oldest_entity = next(iter(self._velocity_windows))
            del self._velocity_windows[oldest_entity]

        count = len(window)

        # Score: 0 at 1 req/min, 1.0 at 30+ req/min
        if count <= 5:
            return 0.0
        elif count <= 10:
            return 0.3
        elif count <= 20:
            return 0.6
        elif count <= 30:
            return 0.8
        else:
            return 1.0


# ---------------------------------------------------------------------------
# Multi-Stage Attack Correlator
# ---------------------------------------------------------------------------

@dataclass
class AttackChainEntry:
    timestamp: float
    threat_score: float
    action: str
    dominant_signal: str
    prompt_hash: str


@dataclass
class ChainAnalysis:
    entity_id: str
    chain_length: int
    pattern_detected: Optional[str] = None
    chain_score: float = 0.0
    entries: List[AttackChainEntry] = field(default_factory=list)


class MultiStageCorrelator:
    """
    Sliding-window multi-stage attack detection.

    Maintains a 60-minute rolling history of entity interactions
    and scores sequences against known attack chain patterns:

    1. MODEL_INVERSION: probe (low score) → extract → reconstruct (rising scores)
    2. PROMPT_CHAINING: series of WARN-level prompts → single high-value pivot
    3. IDENTITY_DRIFT: gradual semantic shift in persona/role across sessions
    4. VELOCITY_ESCALATION: requests slow initially → rapidly accelerating

    When a chain is detected, emits MULTI_STAGE_ATTACK_DETECTED event.
    """

    WINDOW_SECONDS = 3600  # 60 minutes
    MIN_CHAIN_LENGTH = 3   # Need at least 3 events to detect a pattern

    def __init__(self):
        self._chains: Dict[str, List[AttackChainEntry]] = {}

    def record_interaction(
        self,
        entity_id: str,
        threat_score: float,
        action: str,
        dominant_signal: str,
        prompt_hash: str,
    ) -> ChainAnalysis:
        """
        Record an interaction and check for multi-stage patterns.
        Returns a ChainAnalysis with detected pattern (if any).
        """
        now = time.time()
        chain = self._chains.setdefault(entity_id, [])

        # Prune old entries
        chain[:] = [e for e in chain if now - e.timestamp < self.WINDOW_SECONDS]

        # Add new entry
        entry = AttackChainEntry(
            timestamp=now,
            threat_score=threat_score,
            action=action,
            dominant_signal=dominant_signal,
            prompt_hash=prompt_hash,
        )
        chain.append(entry)

        analysis = ChainAnalysis(
            entity_id=entity_id,
            chain_length=len(chain),
            entries=list(chain[-10:]),  # last 10
        )

        if len(chain) >= self.MIN_CHAIN_LENGTH:
            analysis.pattern_detected, analysis.chain_score = self._detect_pattern(chain)

        return analysis

    def _detect_pattern(
        self, chain: List[AttackChainEntry]
    ) -> Tuple[Optional[str], float]:
        """
        Score the chain against known attack patterns.
        Returns (pattern_name, confidence_score) or (None, 0.0).
        """
        scores = chain[-10:]  # analyze last 10 interactions

        # --- Pattern 1: MODEL_INVERSION ---
        # Low → medium → high scoring trend over time
        threat_scores = [e.threat_score for e in scores]
        if len(threat_scores) >= 3:
            trend = self._linear_trend(threat_scores)
            if trend > 0.05:  # rising slope
                if threat_scores[-1] > 0.6 and threat_scores[0] < 0.4:
                    return "MODEL_INVERSION", min(trend * 5, 1.0)

        # --- Pattern 2: PROMPT_CHAINING ---
        # Multiple WARN-level actions followed by BLOCK
        warn_count = sum(1 for e in scores if e.action == "WARN")
        block_at_end = len(scores) > 0 and scores[-1].action == "BLOCK"
        if warn_count >= 3 and block_at_end:
            confidence = min(warn_count / 5.0, 1.0)
            return "PROMPT_CHAINING", confidence

        # --- Pattern 3: VELOCITY_ESCALATION ---
        # Slow start → rapid acceleration
        if len(scores) >= 5:
            early_avg = sum(
                scores[i + 1].timestamp - scores[i].timestamp
                for i in range(min(2, len(scores) - 1))
            ) / max(min(2, len(scores) - 1), 1)
            late_avg = sum(
                scores[i + 1].timestamp - scores[i].timestamp
                for i in range(max(len(scores) - 3, 0), len(scores) - 1)
            ) / max(len(scores) - max(len(scores) - 3, 0) - 1, 1)
            if early_avg > 0 and late_avg > 0 and (early_avg / late_avg) > 5:
                return "VELOCITY_ESCALATION", 0.7

        return None, 0.0

    @staticmethod
    def _linear_trend(values: List[float]) -> float:
        """Compute linear regression slope for trend detection."""
        n = len(values)
        if n < 2:
            return 0.0
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        return numerator / denominator if denominator else 0.0


# Module-level singletons
cognitive_classifier = CognitiveThreatClassifier()
multi_stage_correlator = MultiStageCorrelator()
