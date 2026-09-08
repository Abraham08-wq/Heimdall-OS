"""
Anomaly Detection Engine — v2 (Power Upgrade)
──────────────────────────────────────────────
Upgrades:
  • UEBA (User & Entity Behavior Analytics) per-entity baseline tracking
  • Sequential kill-chain chaining: 3+ anomalies in 15-min window → breach flag
  • 95% confidence interval reasoning for explainability
  • MITRE ATT&CK technique auto-mapping
  • Temporal sliding-window state per entity
"""
import math
from collections import defaultdict, deque
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timezone, timedelta

MITRE_MAP = {
    "auth_failures":       "T1110",
    "endpoint_admin":      "T1078",
    "high_velocity":       "T1071",
    "large_payload":       "T1041",
    "port_scan":           "T1046",
    "lateral_smb":         "T1021.002",
}

PHASE_FROM_TECHNIQUE = {
    "T1041": "EXFILTRATION",
    "T1021": "LATERAL MOVEMENT",
    "T1021.002": "LATERAL MOVEMENT",
    "T1003": "CREDENTIAL ACCESS",
    "T1110": "CREDENTIAL ACCESS",
    "T1134": "PRIVILEGE ESCALATION",
    "T1059": "EXECUTION",
}


class UEBAProfile:
    """Per-entity sliding-window behavioral baseline."""
    def __init__(self, window: int = 100):
        self.anomaly_history: deque = deque(maxlen=50)
        self.feature_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.baseline: Dict[str, float] = {}

    def update(self, features: Dict[str, float]) -> None:
        for k, v in features.items():
            self.feature_history[k].append(v)
            vals = list(self.feature_history[k])
            self.baseline[k] = sum(vals) / len(vals)

    def ci(self, feature: str) -> Tuple[float, float]:
        """95% confidence interval (mean ± 2σ)."""
        vals = list(self.feature_history.get(feature, []))
        if len(vals) < 3:
            return (0.0, float('inf'))
        mean = sum(vals) / len(vals)
        std  = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))
        return (max(0.0, mean - 2 * std), mean + 2 * std)

    def record_anomaly(self, score: float, technique: str) -> None:
        self.anomaly_history.append({
            "score": score, "technique": technique,
            "ts": datetime.now(timezone.utc)
        })


class AnomalyDetectionEngine:
    """
    Continuous behavioral anomaly detection with UEBA, kill-chain chaining,
    MITRE ATT&CK attribution, and confidence interval explainability.
    """
    THRESHOLD        = 0.72
    DECAY_LAMBDA     = 0.10
    KC_WINDOW_MINS   = 15
    KC_MIN_EVENTS    = 3

    def __init__(self):
        self._profiles: Dict[str, UEBAProfile] = defaultdict(UEBAProfile)

    # ── Feature extraction ────────────────────────────────────────────────────

    def _extract(self, event: Dict[str, Any]) -> Dict[str, float]:
        return {
            "velocity":           float(event.get("requests_per_second", 0.0)),
            "payload_mb":         float(event.get("payload_bytes", 0)) / (1024 * 1024),
            "endpoint_risk":      self._score_path(event.get("path", "")),
            "auth_failures":      float(event.get("failed_login_attempts", 0)),
            "unique_dst_ports":   float(event.get("unique_dst_ports", 0)),
            "exfil_ratio":        float(event.get("bytes_out", 0)) / max(float(event.get("bytes_in", 1)), 1),
        }

    def _score_path(self, path: str) -> float:
        if any(k in path for k in ("admin", "config", "passwd")): return 1.0
        if any(k in path for k in ("auth", "login", "token")):    return 0.8
        if "api" in path:                                          return 0.4
        return 0.1

    # ── Deviation scoring ─────────────────────────────────────────────────────

    def _isolation_score(
        self, features: Dict[str, float], profile: UEBAProfile
    ) -> Tuple[float, List[str]]:
        if not profile.baseline:
            return 0.5, ["No baseline — elevated prior."]

        distances, reasoning = [], []
        for k, v in features.items():
            lo, hi = profile.ci(k)
            if v > hi and hi < float('inf'):
                dev = min((v - hi) / max(hi, 1e-9), 1.0)
                distances.append(dev)
                if dev > 0.3:
                    reasoning.append(f"{k}={v:.2f} breaches 95% CI upper ({hi:.2f})")
            elif v < lo and lo > 0:
                distances.append(min((lo - v) / max(lo, 1e-9), 1.0) * 0.5)
            else:
                distances.append(0.0)

        return min(sum(distances) / len(distances), 1.0) if distances else 0.0, reasoning

    # ── MITRE mapping ─────────────────────────────────────────────────────────

    def _mitre(self, features: Dict[str, float]) -> str:
        if features["auth_failures"] > 5:    return MITRE_MAP["auth_failures"]
        if features["payload_mb"] > 50:      return MITRE_MAP["large_payload"]
        if features["velocity"] > 100:       return MITRE_MAP["high_velocity"]
        if features["unique_dst_ports"] > 20:return MITRE_MAP["port_scan"]
        if features["endpoint_risk"] >= 0.8: return MITRE_MAP["endpoint_admin"]
        return "T1071"

    # ── Time decay ────────────────────────────────────────────────────────────

    def _decay(self, ts_iso: str) -> float:
        try:
            ts = datetime.fromisoformat(ts_iso.replace('Z', '+00:00'))
            ts = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        except Exception:
            ts = datetime.now(timezone.utc)
        days = max((datetime.now(timezone.utc) - ts).days, 0)
        return math.exp(-self.DECAY_LAMBDA * days)

    # ── Kill-chain detection ──────────────────────────────────────────────────

    def _kill_chain(self, profile: UEBAProfile) -> Optional[Dict[str, Any]]:
        now   = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=self.KC_WINDOW_MINS)
        recent = [a for a in profile.anomaly_history if a["ts"] >= cutoff]
        if len(recent) < self.KC_MIN_EVENTS:
            return None
        techniques = list({a["technique"] for a in recent})
        avg = sum(a["score"] for a in recent) / len(recent)
        phase = next(
            (PHASE_FROM_TECHNIQUE[t] for t in techniques if t in PHASE_FROM_TECHNIQUE),
            "INITIAL ACCESS"
        )
        return {
            "kill_chain_detected": True,
            "event_count": len(recent),
            "techniques": techniques,
            "avg_score": round(avg, 3),
            "phase_estimate": phase,
        }

    # ── Public API ────────────────────────────────────────────────────────────

    def compute_ueba_score(self, entity_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
        """Full UEBA pipeline for a single event."""
        profile  = self._profiles[entity_id]
        features = self._extract(event)
        raw, reasoning = self._isolation_score(features, profile)
        decay    = self._decay(event.get("timestamp", datetime.now(timezone.utc).isoformat()))
        score    = round(min(raw * decay, 1.0), 4)
        technique = self._mitre(features)

        profile.record_anomaly(score, technique)
        profile.update(features)

        return {
            "entity_id":       entity_id,
            "ueba_score":      score,
            "is_anomalous":    score > self.THRESHOLD,
            "mitre_technique": technique,
            "reasoning":       reasoning,
            "kill_chain":      self._kill_chain(profile),
            "features":        {k: round(v, 4) for k, v in features.items()},
        }

    def detect_anomalies(
        self,
        telemetry_stream: List[Dict[str, Any]],
        historical_baselines: Dict[str, Dict[str, float]],
    ) -> List[Dict[str, Any]]:
        """Batch processor — backward-compatible with existing callers."""
        detected = []
        for event in telemetry_stream:
            ip = event.get("source_ip", "0.0.0.0")
            profile = self._profiles[ip]
            if not profile.baseline and ip in historical_baselines:
                profile.baseline = dict(historical_baselines[ip])

            r = self.compute_ueba_score(ip, event)
            if r["is_anomalous"]:
                detected.append({
                    "source_ip":       ip,
                    "anomaly_type":    "BEHAVIORAL_DEVIATION",
                    "confidence_score": r["ueba_score"],
                    "mitre_technique": r["mitre_technique"],
                    "reasoning_tree":  r["reasoning"],
                    "kill_chain":      r["kill_chain"],
                    "event_reference": event.get("event_id"),
                })
        return detected


anomaly_engine = AnomalyDetectionEngine()
