import json
import time
import logging
import redis
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID

logger = logging.getLogger(__name__)

class UEBAMonitor:
    """
    User & Entity Behavior Analytics (UEBA) Engine
    
    Tracks request volumes, distinct IPs, and access patterns to baseline normal 
    user behavior using Exponential Moving Averages (EMA).
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        try:
            self.redis = redis.from_url(redis_url, decode_responses=True)
            self.redis.ping()
            self.is_connected = True
        except Exception as e:
            logger.error(f"Failed to connect to UEBA Redis cache: {e}")
            self.is_connected = False
            
    def compute_anomaly(self, user_id: str, action_type: str, ip_address: str, weight: float = 1.0) -> Dict[str, Any]:
        """
        [PHASE 4: UEBA MATHEMATICAL MODEL]
        Calculates EMA baseline, standard deviation z-score, and applies Bayesian Risk Propagation.
        """
        import math
        if not self.is_connected:
            return {"status": "bypassed", "risk_score": 0.0}
            
        now = int(time.time())
        window_start = now - (now % 60) # aggregate to current minute
        
        # Keys for tracking
        base_key = f"ueba:{user_id}:{action_type}"
        minute_key = f"{base_key}:min:{window_start}"
        baseline_key = f"{base_key}:ema"
        var_key = f"{base_key}:var" # Variance tracking
        ip_set_key = f"{base_key}:ips"
        
        # 1. Increment volume for this minute
        pipe = self.redis.pipeline()
        pipe.incrbyfloat(minute_key, weight)
        pipe.expire(minute_key, 3600)
        pipe.sadd(ip_set_key, ip_address)
        pipe.expire(ip_set_key, 86400)
        results = pipe.execute()
        current_volume = results[0]
        
        # 2. Fetch running baseline (EMA) and Variance
        ema_str = self.redis.get(baseline_key)
        var_str = self.redis.get(var_key)
        previous_ema = float(ema_str) if ema_str else current_volume
        previous_var = float(var_str) if var_str else 0.0
        
        # 3. Calculate Deviation Risk via Mathematical Engine
        alpha = 0.1 # Smoothing factor for EMA
        new_ema = (current_volume * alpha) + (previous_ema * (1 - alpha))
        
        # Welford's online variance calculation
        diff = current_volume - previous_ema
        incr = alpha * diff
        new_var = (1 - alpha) * (previous_var + diff * incr)
        
        self.redis.set(baseline_key, new_ema)
        self.redis.set(var_key, new_var)
        
        deviation_ratio = current_volume / new_ema if new_ema > 0 else 1.0
        
        # Z-Score Anomaly Detection
        variance = max(0.0001, new_var)
        std_dev = math.sqrt(variance)
        z_score = (current_volume - new_ema) / std_dev
        
        # 4. Bayesian Risk Update Logic
        risk_score = 0.0
        findings = []
        
        # Statistical outlier
        if z_score > 3.0 and current_volume > 5:
            # Amplification
            risk_score += min(60.0, z_score * 10)
            findings.append(f"Statistically significant volume spike (Z = {z_score:.2f}).")
            
        unique_ips = self.redis.scard(ip_set_key)
        if unique_ips > 3:
            # Contextual Risk Amplification
            risk_score += min(40.0, unique_ips * 10)
            findings.append(f"High Bayesian prior on credential abuse ({unique_ips} distinct IPs).")
            
        # Ensure max 100
        risk_score = min(100.0, risk_score)
        
        result = {
            "status": "analyzed",
            "current_volume": current_volume,
            "baseline_ema": round(new_ema, 2),
            "z_score": round(z_score, 2),
            "deviation_ratio": round(deviation_ratio, 2),
            "risk_score": round(risk_score, 2),
            "findings": findings,
            "is_anomalous": risk_score >= 75.0
        }
        
        if result["is_anomalous"]:
            logger.warning(f"UEBA ANOMALY DETECTED for User {user_id}: {findings} (Risk: {risk_score})")
            
        return result
        
    def record_outcome(self, user_id: str, status_code: int):
        """
        Track API Abuse and Endpoint Entropy (Phase 2).
        Calculates the ratio of 4xx/5xx vs 2xx responses per user to detect fuzzing or enumeration.
        """
        if not self.is_connected:
            return
            
        error_key = f"ueba:{user_id}:errors"
        success_key = f"ueba:{user_id}:success"
        
        pipe = self.redis.pipeline()
        
        if status_code >= 400:
            pipe.incr(error_key)
            pipe.expire(error_key, 3600)
        else:
            pipe.incr(success_key)
            pipe.expire(success_key, 3600)
            
        results = pipe.execute()
        
        if status_code >= 400:
            errors = results[0]
            successes = int(self.redis.get(success_key) or 1)
            
            # Entropy Analysis: High volume of errors vs successes
            if errors > 15 and (errors / (successes + errors)) > 0.6:
                logger.critical(f"API ABUSE DETECTED: {user_id} executing high-entropy enumeration (Error Ratio: >60%, Count: {errors}).")

ueba_engine = UEBAMonitor()
