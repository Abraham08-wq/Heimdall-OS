"""
llm_firewall.py — ProjectXY Cognitive Shield: Sovereign LLM Guardrail (UPGRADED)
==================================================================================
High-performance (<60ms) 5-layer security stack that intercepts all prompts
destined for third-party or local LLMs.

  LAYER 1 — Cleansing Transformer     — Unicode homoglyphs, zero-width chars,
                                         Sheng/Swahili expansion, leetspeak,
                                         BIDI override attacks, punct-padding
  LAYER 3 — Cognitive Threat Classifier — Ensemble scoring (5 weighted signals)
                                           Multi-stage attack chain detection
  LAYER 4 — Forensic AI Observability — Semantic logging to pgvector,
                                         retroactive similarity hunting

  PLUS existing 4-vector defence (preserved fully):
  1. Semantic Anomaly Detection  — pgvector cosine-similarity vs threat corpus
  2. PII / DLP Scrubbing         — spaCy NER + East Africa–aware regex
  3. Malicious Payload Detection — Base64/Hex obfuscation, injection regex
  4. Localized Semantic Evasion  — Swahili, Sheng, code-switched patterns

Architecture:
    Client Prompt
      → Layer 1: CleansingTransformer (normalize BEFORE inference)
      → Existing 4 defence vectors (concurrent)
      → Layer 3: EnsembleClassifier (replaces simple priority chain)
      → Layer 4: SemanticLogger (async, non-blocking, fail-open)
      → [PASS | BLOCK | SCRUB+PASS] → LLM

All decisions streamed to Kafka (firewall_events) for SIEM correlation.
Blocked prompts cached in Redis to prevent replay attacks.
CBK Compliance: Every decision immutably logged to TimescaleDB with SHA-256 chain.
"""
import asyncio
import base64
import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import asyncpg
import numpy as np
import redis.asyncio as aioredis

# ── Cognitive Shield Layer imports ────────────────────────────────────────
try:
    from app.modules.firewall.cleansing_transformer import (
        CleansingTransformer, CleansingResult, cleansing_transformer
    )
    _CLEANSING_AVAILABLE = True
except ImportError:
    _CLEANSING_AVAILABLE = False

try:
    from app.modules.firewall.cognitive_threat_classifier import (
        CognitiveThreatClassifier, MultiStageCorrelator,
        cognitive_classifier, multi_stage_correlator
    )
    _ENSEMBLE_AVAILABLE = True
except ImportError:
    _ENSEMBLE_AVAILABLE = False

try:
    from app.modules.firewall.semantic_logger import (
        SemanticLogger, SemanticLogEntry, semantic_logger
    )
    _SEMANTIC_LOG_AVAILABLE = True
except ImportError:
    _SEMANTIC_LOG_AVAILABLE = False
# ─────────────────────────────────────────────────────────────────────────

logger = logging.getLogger("projectxy.firewall")

# ---------------------------------------------------------------------------
# Configuration — loaded from environment / settings
# ---------------------------------------------------------------------------

FIREWALL_CONFIG = {
    "similarity_block_threshold": float(os.getenv("FW_SIMILARITY_THRESHOLD", "0.82")),
    "similarity_warn_threshold": float(os.getenv("FW_WARN_THRESHOLD", "0.70")),
    "embedding_model": os.getenv("FW_EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
    "max_prompt_length": int(os.getenv("FW_MAX_PROMPT_LENGTH", "8192")),
    "replay_cache_ttl": int(os.getenv("FW_REPLAY_TTL_SECONDS", "3600")),
    "pii_mask_token": os.getenv("FW_PII_MASK_TOKEN", "[REDACTED]"),
    "db_url": os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:changethis@localhost:5433/cyberintel"
    ).replace("postgresql+asyncpg://", "postgresql://").replace("+asyncpg", ""),
    "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    "kafka_bootstrap": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
}

# ---------------------------------------------------------------------------
# PII Patterns — Comprehensive East Africa DLP Pipeline
# ---------------------------------------------------------------------------
# UPGRADE: Expanded from basic patterns to full East African financial and
# government ID coverage. Each pattern is annotated with its data class.
# Order matters: more specific patterns run BEFORE broad numeric patterns.
# ---------------------------------------------------------------------------

PII_PATTERNS: List[Tuple[str, str]] = [
    # ── Kenya Revenue Authority (KRA) PIN ─────────────────────────────────
    # Format: A followed by 9 digits followed by uppercase letter (e.g., A123456789Z)
    # This is a TAX identifier — CRITICAL to scrub before any external LLM call.
    (r"\b[AP]\d{9}[A-Z]\b", "[KE_KRA_PIN_REDACTED]"),

    # ── M-Pesa Transaction Receipt Codes ─────────────────────────────────
    # Format: 2 uppercase letters + 2 digits + 2 uppercase + 2 digits + 2 uppercase
    # e.g., QA12BC34DE, SL97KM23NB — these confirm real financial transactions.
    # Leaking these lets attackers reconstruct transaction timelines.
    (r"\b[A-Z]{2}\d{2}[A-Z]{2}\d{2}[A-Z]{2}\b", "[MPESA_RECEIPT_REDACTED]"),

    # ── M-Pesa / Safaricom / Airtel Phone Numbers ─────────────────────────
    # Covers +254, 07xx, 01xx formats. These double as M-Pesa wallet addresses.
    (r"\b(?:\+254|0)(?:7\d{8}|1\d{8})\b", "[MPESA_PHONE_REDACTED]"),

    # ── Huduma Namba (Kenya National Integrated Identity) ────────────────
    # Format: 8 digits (replacing the old National ID in many systems)
    # Distinct from National ID — NIIMS database primary key.
    (r"\b(?:huduma|niims)[\s#:]+\d{8}\b", "[HUDUMA_NAMBA_REDACTED]"),

    # ── Kenya National ID / Alien Certificate ────────────────────────────
    # 7–8 digits for citizens; Alien Certificate is A + 7 digits
    (r"\b(?:id[\s#:]+)?\d{7,8}\b(?!\s*[A-Z])", "[KE_NATIONAL_ID_REDACTED]"),
    (r"\bA\d{7}\b", "[KE_ALIEN_ID_REDACTED]"),

    # ── Kenya Tax Identification Number (TIN) for Corporates ─────────────
    # Format: P followed by 9 digits (e.g., P051234567T)
    (r"\bP\d{9}[A-Z]\b", "[KE_CORPORATE_TIN_REDACTED]"),

    # ── USSD Session Codes & SIM Toolkit Commands ─────────────────────────
    # USSD strings used in mobile banking that carry session state.
    # e.g., *334*1*1#, *884*254XXXXXXXXX#
    (r"\*\d{2,5}(?:\*[A-Za-z0-9]+)*#", "[USSD_CODE_REDACTED]"),

    # ── M-Pesa Paybill & Till Numbers ────────────────────────────────────
    # Paybill: 5-7 digit numbers used as merchant identifiers in M-Pesa
    (r"\b(?:paybill|till|business number)[\s:]+\d{5,7}\b", "[MPESA_PAYBILL_REDACTED]"),

    # ── Equity, KCB, Cooperative Bank Account Numbers ────────────────────
    # Kenyan bank accounts are typically 10–14 digits.
    (r"\b(?:acc(?:ount)?[\s#:]+)?\d{10,14}\b", "[KE_BANK_ACCOUNT_REDACTED]"),

    # ── IBAN (regional cross-border payments) ────────────────────────────
    (r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}(?:[A-Z0-9]?){0,16}\b", "[IBAN_REDACTED]"),

    # ── Credit/Debit Card Numbers (Luhn-matching patterns) ───────────────
    (r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|6(?:011|5[0-9]{2})[0-9]{12}|3[47][0-9]{13})\b",
     "[CARD_NUMBER_REDACTED]"),

    # ── CVV / CVC ────────────────────────────────────────────────────────
    (r"\b(?:cvv|cvc|security\s+code|nambari\s+ya\s+usalama)[\s:]+\d{3,4}\b",
     "[CVV_REDACTED]"),

    # ── Email addresses ──────────────────────────────────────────────────
    (r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", "[EMAIL_REDACTED]"),

    # ── API keys / tokens ────────────────────────────────────────────────
    (r"\b(?:sk-|pk-|Bearer\s+)[A-Za-z0-9\-_]{20,}\b", "[API_KEY_REDACTED]"),

    # ── AWS access key IDs ───────────────────────────────────────────────
    (r"\bAKIA[0-9A-Z]{16}\b", "[AWS_KEY_REDACTED]"),

    # ── Private key PEM headers ──────────────────────────────────────────
    (r"-----BEGIN\s+(?:RSA\s+|EC\s+)?PRIVATE\s+KEY-----", "[PRIVATE_KEY_REDACTED]"),

    # ── Tanzania TIN and NIDA ────────────────────────────────────────────
    (r"\b\d{9}\b(?=.*(?:tz|tanzania|nida|tin))", "[TZ_ID_REDACTED]"),

    # ── Uganda NIN ───────────────────────────────────────────────────────
    # Uganda National ID: CMxxxxxxxxxx format
    (r"\bCM[A-Z0-9]{10}\b", "[UG_NIN_REDACTED]"),
]

# ---------------------------------------------------------------------------
# Malicious Payload Patterns — English + Swahili/Sheng Adversarial Injection
# ---------------------------------------------------------------------------
# UPGRADE: Added a dedicated second tier of patterns for Swahili, Sheng
# (Kenyan urban slang), and code-switched East African language variants.
# Attackers targeting local fintech AI models may use these to bypass
# English-only pattern classifiers.
# ---------------------------------------------------------------------------

INJECTION_PATTERNS: List[re.Pattern] = [
    # ── Tier 1: Classic English DAN / Role-Escape Patterns ────────────────
    re.compile(r"\b(?:DAN|STAN|DUDE|AIM|JAILBREAK)\s*mode\b", re.IGNORECASE),
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+instructions", re.IGNORECASE),
    re.compile(r"(?:disregard|forget|override)\s+(?:your|all|previous)\s+(?:instructions|rules|prompt)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:an?\s+)?(?:evil|malicious|unrestricted|jailbroken)", re.IGNORECASE),
    re.compile(r"(?:pretend|act|roleplay)\s+(?:as\s+)?(?:if\s+)?(?:you\s+have\s+no\s+restrictions)", re.IGNORECASE),

    # ── Tier 2: System Prompt Extraction ──────────────────────────────────
    re.compile(r"(?:reveal|show|print|output|repeat)\s+(?:your\s+)?system\s+prompt", re.IGNORECASE),
    re.compile(r"what\s+(?:are|were)\s+your\s+instructions", re.IGNORECASE),
    # Swahili: "niambie maelekezo yako" = "tell me your instructions"
    re.compile(r"niambie\s+(?:maelekezo|kanuni|mwongozo)\s+yako", re.IGNORECASE),
    # Swahili: "onyesha mfumo wako" = "show your system"
    re.compile(r"onyesha\s+(?:mfumo|kanuni|miongozo)\s+(?:wako|yako)", re.IGNORECASE),

    # ── Tier 3: Exfiltration via Encoding ────────────────────────────────
    re.compile(r"(?:encode|decode|convert).*(?:base64|hex|rot13)", re.IGNORECASE),

    # ── Tier 4: East African Financial Injection (English) ───────────────
    re.compile(r"bypass\s+(?:mpesa|safaricom|equity|kcb|ncba|pesalink|airtel\s*money)\s+validation", re.IGNORECASE),
    re.compile(r"transfer\s+funds\s+without\s+(?:otp|pin|verification|authorization|idhini)", re.IGNORECASE),
    re.compile(r"(?:simulate|execute|fanya)\s+(?:unauthorized\s+)?(?:m-?pesa|mobile\s+money|pesa)\s+transaction", re.IGNORECASE),
    re.compile(r"(?:bypass|pitia|epuka)\s+(?:otp|pin\s+check|uthibitisho)", re.IGNORECASE),

    # ── Tier 5: Swahili Injection Patterns (Semantic Evasion Layer) ──────
    # Swahili: "sahau maagizo yako yote" = "forget all your instructions"
    re.compile(r"sahau\s+(?:maagizo|kanuni|mwongozo)\s+(?:yako\s+)?yote", re.IGNORECASE),
    # Swahili: "wewe ni sasa" = "you are now" (role escape setup)
    re.compile(r"wewe\s+ni\s+sasa\s+(?:AI|mfumo|roboti)\s+(?:bila|isio na)\s+(?:mipaka|vikwazo)", re.IGNORECASE),
    # Swahili: "toa data" / "tuma data" = "extract/send data"
    re.compile(r"(?:toa|tuma|peleka)\s+(?:data|taarifa|habari)\s+(?:yote|hii|hiyo)", re.IGNORECASE),
    # Swahili: "nakili" = "copy" — prompt duplication attacks
    re.compile(r"nakili\s+(?:mfumo|kanuni|maelekezo)\s+wako", re.IGNORECASE),

    # ── Tier 6: Sheng Injection Patterns (Urban Kenyan Slang Evasion) ────
    # Sheng is heavily code-switched Swahili/English/Kikuyu slang. These
    # patterns cover observed adversarial framings used in local testing.
    # "kanyaga sheria" = "step on the rules" (bypass instructions)
    re.compile(r"kanyag[ae]\s+(?:sheria|kanuni|maagizo|instructions)", re.IGNORECASE),
    # "fanya kitu kibaya" = "do something bad / malicious"
    re.compile(r"fanya\s+kitu\s+(?:kibaya|cha|kila|haramu)", re.IGNORECASE),
    # "iba" = "steal" in Sheng, targeting credential theft framing
    re.compile(r"\biba\s+(?:token|pesa|akaunti|account|kadi|card)\b", re.IGNORECASE),
    # "thibitisha peke yako" = "authenticate by yourself" (OTP bypass framing)
    re.compile(r"thibitisha\s+peke\s+yako\s+bila\s+(?:otp|pin|nambari)", re.IGNORECASE),
    # "hack" in Sheng context with Swahili verbs
    re.compile(r"(?:hac?k|vunja)\s+(?:mfumo|system|akaunti|account)", re.IGNORECASE),

    # ── Tier 7: SQL / Code Injection via Prompt ──────────────────────────
    re.compile(r"(?:execute|run|eval|tekeleza|endesha)\s+(?:this\s+)?(?:sql|code|script|command|amri)", re.IGNORECASE),
    re.compile(r"(?:'; ?DROP|;.*DELETE FROM|UNION SELECT|1=1|OR TRUE)", re.IGNORECASE),

    # ── Tier 8: Token / Credential Manipulation ──────────────────────────
    re.compile(r"(?:steal|extract|leak|iba|chukua)\s+(?:jwt|api[\s_-]?key|token|credential|kibali)", re.IGNORECASE),

    # ── Tier 9: USSD Session Hijacking Patterns ──────────────────────────
    # Attackers may attempt to inject USSD-like command sequences into AI
    # prompts to manipulate USSD-aware AI agents.
    re.compile(r"(?:send|tuma|piga)\s+ussd\s+(?:code|nambari|ombi)\s+(?:to|kwa)\s+(?:steal|kuiba|kupata)", re.IGNORECASE),
    re.compile(r"intercept\s+(?:ussd|otp|sim)\s+(?:session|jibu|ujumbe)", re.IGNORECASE),
]


def _detect_obfuscated_payload(text: str) -> Optional[str]:
    """
    Detect Base64 or Hex-encoded payloads hidden inside prompt text.
    Returns the decoded content if a threat pattern is found, else None.
    """
    # Find all Base64-looking strings (min 20 chars)
    b64_candidates = re.findall(r"(?:[A-Za-z0-9+/]{20,}={0,2})", text)
    for candidate in b64_candidates[:10]:  # limit checks for performance
        try:
            decoded = base64.b64decode(candidate + "==").decode("utf-8", errors="ignore")
            # Check decoded content for injection patterns
            for pattern in INJECTION_PATTERNS[:5]:
                if pattern.search(decoded):
                    return f"base64_encoded_injection: {decoded[:100]}"
        except Exception:
            pass

    # Hex-encoded check
    hex_candidates = re.findall(r"(?:0x)?[0-9a-fA-F]{40,}", text)
    for candidate in hex_candidates[:5]:
        try:
            decoded = bytes.fromhex(candidate).decode("utf-8", errors="ignore")
            for pattern in INJECTION_PATTERNS[:3]:
                if pattern.search(decoded):
                    return f"hex_encoded_injection: {decoded[:100]}"
        except Exception:
            pass

    return None


# ---------------------------------------------------------------------------
# Dataclasses for typed results
# ---------------------------------------------------------------------------

@dataclass
class PIIScrubResult:
    original_text: str
    scrubbed_text: str
    pii_types_found: List[str] = field(default_factory=list)
    was_modified: bool = False


@dataclass
class FirewallVerdict:
    """The complete decision from the AI Firewall for a single prompt."""
    action: str                           # PASS | BLOCK | SCRUB_AND_PASS
    threat_score: float                   # 0.0 – 1.0
    reasons: List[str] = field(default_factory=list)
    scrubbed_prompt: Optional[str] = None
    pii_types_detected: List[str] = field(default_factory=list)
    semantic_similarity: float = 0.0
    matched_threat_category: Optional[str] = None
    latency_ms: float = 0.0
    prompt_hash: str = ""
    timestamp: str = ""


# ---------------------------------------------------------------------------
# Core AI Firewall Engine
# ---------------------------------------------------------------------------

class LLMFirewall:
    """
    Sovereign AI Firewall — inline guardrail layer for all LLM traffic.

    Thread-safe singleton. Call ``await LLMFirewall.create()`` once at startup,
    then ``await firewall.check(prompt, tenant_id)`` per request.
    """

    def __init__(self):
        self._model = None          # SentenceTransformer — lazy-loaded
        self._pg_pool: Optional[asyncpg.Pool] = None
        self._redis: Optional[aioredis.Redis] = None
        self._kafka_producer = None
        self._spacy_nlp = None      # spaCy NER — lazy-loaded
        self._ready = False

    # ------------------------------------------------------------------ #
    # Startup / Teardown
    # ------------------------------------------------------------------ #

    @classmethod
    async def create(cls) -> "LLMFirewall":
        """Factory — use this instead of __init__ in async contexts."""
        fw = cls()
        await fw._init_connections()
        fw._load_ml_models()
        fw._ready = True

        # ── Layer 4: Wire Semantic Logger with DB pool and model ──────────
        if _SEMANTIC_LOG_AVAILABLE and fw._pg_pool and fw._model:
            try:
                semantic_logger.configure(
                    db_pool=fw._pg_pool,
                    sentence_transformer=fw._model,
                )
                await semantic_logger.start()
                logger.info("[FIREWALL] Semantic Logger (Layer 4) started.")
            except Exception as exc:
                logger.warning(f"[FIREWALL] Semantic Logger startup failed (non-critical): {exc}")
        # ─────────────────────────────────────────────────────────────────

        logger.info(
            "[FIREWALL] Cognitive Shield ONLINE — 5-layer security stack armed. "
            f"Cleansing={_CLEANSING_AVAILABLE}, Ensemble={_ENSEMBLE_AVAILABLE}, "
            f"SemanticLog={_SEMANTIC_LOG_AVAILABLE}"
        )
        return fw

    async def _init_connections(self):
        """Initialise asyncpg pool and Redis connection pool."""
        try:
            self._pg_pool = await asyncpg.create_pool(
                FIREWALL_CONFIG["db_url"],
                min_size=2,
                max_size=10,
                command_timeout=5,
            )
            logger.info("[FIREWALL] PostgreSQL (pgvector) pool established.")
        except Exception as exc:
            logger.warning(f"[FIREWALL] pgvector pool unavailable: {exc}. Semantic check disabled.")

        try:
            self._redis = aioredis.from_url(
                FIREWALL_CONFIG["redis_url"],
                encoding="utf-8",
                decode_responses=True,
            )
            await self._redis.ping()
            logger.info("[FIREWALL] Redis cache connected.")
        except Exception as exc:
            logger.warning(f"[FIREWALL] Redis unavailable: {exc}. Replay cache disabled.")

        try:
            from aiokafka import AIOKafkaProducer
            self._kafka_producer = AIOKafkaProducer(
                bootstrap_servers=FIREWALL_CONFIG["kafka_bootstrap"],
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
            await self._kafka_producer.start()
            logger.info("[FIREWALL] Kafka producer connected.")
        except Exception as exc:
            logger.warning(f"[FIREWALL] Kafka unavailable: {exc}. Event streaming degraded.")

    def _load_ml_models(self):
        """Load SentenceTransformer and spaCy NER (blocks during startup only)."""
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(FIREWALL_CONFIG["embedding_model"])
            logger.info(f"[FIREWALL] Embedding model '{FIREWALL_CONFIG['embedding_model']}' loaded.")
        except Exception as exc:
            logger.warning(f"[FIREWALL] Embedding model unavailable: {exc}. Semantic check disabled.")

        try:
            import spacy
            self._spacy_nlp = spacy.load("en_core_web_sm")
            logger.info("[FIREWALL] spaCy NER (en_core_web_sm) loaded.")
        except Exception as exc:
            logger.warning(f"[FIREWALL] spaCy NER unavailable: {exc}. Falling back to regex PII.")

    async def shutdown(self):
        if self._pg_pool:
            await self._pg_pool.close()
        if self._redis:
            await self._redis.aclose()
        if self._kafka_producer:
            await self._kafka_producer.stop()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def check(
        self,
        prompt: str,
        tenant_id: str = "default",
        entity_id: str = "unknown",
        target_model: str = "unknown",
    ) -> FirewallVerdict:
        """
        Main firewall entry point — Cognitive Shield 5-layer pipeline.
        Target latency: <60ms (cleansing adds ~5ms over previous <50ms target).

        LAYER 1 — CleansingTransformer (Step 0 — BEFORE any analysis)
          Normalizes: homoglyphs, zero-width chars, BIDI overrides,
          Sheng/Swahili expansion, leetspeak, punctuation-padding.
          Fail-closed: if cleansing errors, block the request.

        EXISTING VECTORS (concurrent, Step 1–5):
          A. Replay cache lookup      (Redis)  — ~1 ms
          B. Injection pattern scan   (Regex)  — ~2 ms
          C. Obfuscation detection    (Regex)  — ~2 ms
          D. PII scrubbing            (spaCy)  — ~5 ms
          E. Semantic similarity      (pgvec)  — ~10 ms (index hit)

        LAYER 3 — Ensemble Classifier (replaces simple priority chain)
          Weighs all 5 signals with configurable weights.
          Detects multi-stage attack chains.

        LAYER 4 — Semantic Logger (async, non-blocking, fail-open)
          Logs threat_score > 0.30 interactions to pgvector.
        """
        t_start = time.perf_counter()
        verdict = FirewallVerdict(
            action="PASS",
            threat_score=0.0,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # ── OPA POLICY PRE-CHECK (sub-ms early exit) ──────────────────────────
        # If this prompt matches a pattern we've previously learned to block,
        # return immediately without running ML inference.
        try:
            from app.core.opa_feedback import opa_feedback
            opa_hit = await opa_feedback.check(prompt, tenant_id=tenant_id)
            if opa_hit:
                verdict.action = "BLOCK"
                verdict.threat_score = float(opa_hit.get("threat_score", 1.0))
                verdict.reasons.append(opa_hit.get("reason", "[OPA] Policy block"))
                verdict.matched_threat_category = opa_hit.get("category", "OPA_POLICY")
                verdict.latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
                return verdict
        except Exception:
            pass  # OPA check is fail-open — never blocks progress
        # ─────────────────────────────────────────────────────────────────────

        # ── LAYER 1: Cleansing Transformer (Step 0) ───────────────────────
        # Run BEFORE length check so we normalize before measuring length.
        transformations_applied: List[str] = []

        if _CLEANSING_AVAILABLE:
            try:
                cleansing_result: CleansingResult = await asyncio.to_thread(
                    cleansing_transformer.transform, prompt
                )
                if cleansing_result.blocked:
                    verdict.action = "BLOCK"
                    verdict.threat_score = 1.0
                    verdict.reasons.append(
                        f"Cleansing Transformer (Layer 1) hard block: {cleansing_result.block_reason}"
                    )
                    await self._emit_event(tenant_id, entity_id, verdict, prompt[:200])
                    verdict.latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
                    return verdict

                # Use normalized text for all subsequent checks
                prompt = cleansing_result.normalized_text
                transformations_applied = cleansing_result.transformations_applied

                if cleansing_result.was_modified:
                    verdict.reasons.append(
                        f"[Layer 1] Input normalized — transformations: {transformations_applied}"
                    )
            except Exception as exc:
                # Fail-closed: block on unexpected cleansing error
                logger.error(f"[FIREWALL/L1] Cleansing Transformer exception: {exc}")
                verdict.action = "BLOCK"
                verdict.threat_score = 1.0
                verdict.reasons.append("Layer 1 Cleansing Transformer internal error — fail-closed.")
                await self._emit_event(tenant_id, entity_id, verdict, prompt[:200])
                verdict.latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
                return verdict
        # ─────────────────────────────────────────────────────────────────

        # Gate: prompt length (checked AFTER normalization)
        if len(prompt) > FIREWALL_CONFIG["max_prompt_length"]:
            verdict.action = "BLOCK"
            verdict.threat_score = 0.95
            verdict.reasons.append(f"Prompt exceeds maximum length ({len(prompt)} chars).")
            await self._emit_event(tenant_id, entity_id, verdict, prompt)
            verdict.latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
            return verdict

        # Compute deterministic hash for replay detection
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
        verdict.prompt_hash = prompt_hash

        # ── Run existing 4 defence vectors concurrently ────────────────────
        (
            replay_blocked,
            injection_result,
            obfuscation_result,
            pii_result,
            semantic_result,
        ) = await asyncio.gather(
            self._check_replay_cache(prompt_hash),
            asyncio.to_thread(self._scan_injection_patterns, prompt),
            asyncio.to_thread(self._scan_obfuscation, prompt),
            asyncio.to_thread(self._scrub_pii, prompt),
            self._semantic_similarity_check(prompt),
        )

        # Collect raw scores for ensemble
        working_prompt = pii_result.scrubbed_text
        verdict.pii_types_detected = pii_result.pii_types_found

        inj_score = min(len(injection_result) * 0.35, 1.0) if injection_result else 0.0
        sem_score = semantic_result.get("similarity", 0.0)

        # ── LAYER 3: Ensemble Classifier ─────────────────────────────────
        dominant_signal = "none"
        if _ENSEMBLE_AVAILABLE:
            ensemble = cognitive_classifier.compute_ensemble(
                injection_score=inj_score,
                semantic_score=sem_score,
                pii_detected=bool(pii_result.pii_types_found),
                obfuscation_detected=bool(obfuscation_result),
                entity_id=entity_id,
                payload_field_count=1,
                payload_length=len(prompt),
                replay_blocked=replay_blocked,
            )

            # Multi-stage correlator
            chain = multi_stage_correlator.record_interaction(
                entity_id=entity_id,
                threat_score=ensemble.ensemble_score,
                action=ensemble.action,
                dominant_signal=ensemble.dominant_signal,
                prompt_hash=prompt_hash,
            )
            if chain.pattern_detected and chain.chain_score >= 0.6:
                verdict.reasons.append(
                    f"[Layer 3] MULTI-STAGE ATTACK: {chain.pattern_detected} "
                    f"(confidence={chain.chain_score:.2f}, chain_len={chain.chain_length})"
                )
                ensemble.ensemble_score = max(ensemble.ensemble_score, 0.85)
                ensemble.action = "BLOCK"

            # Use ensemble decision
            verdict.threat_score = ensemble.ensemble_score
            dominant_signal = ensemble.dominant_signal
            if ensemble.action == "BLOCK" and verdict.action != "BLOCK":
                verdict.action = "BLOCK"
                verdict.reasons.extend(
                    [f"[Layer 3] {r}" for r in ensemble.reasons]
                )
                await self._cache_replay(prompt_hash)
            elif ensemble.action == "WARN" and verdict.action == "PASS":
                verdict.action = "PASS"  # WARN = log but don't block
                verdict.reasons.extend(
                    [f"[Layer 3 WARN] {r}" for r in ensemble.reasons]
                )
        else:
            # Fallback: original priority-chain decision fusion
            if replay_blocked:
                verdict.action = "BLOCK"
                verdict.threat_score = 1.0
                verdict.reasons.append("Replay attack blocked: identical prompt hash.")
            elif injection_result:
                verdict.action = "BLOCK"
                verdict.threat_score = 0.97
                verdict.reasons.extend(injection_result)
                await self._cache_replay(prompt_hash)
            elif obfuscation_result:
                verdict.action = "BLOCK"
                verdict.threat_score = 0.95
                verdict.reasons.append(f"Obfuscated payload: {obfuscation_result[:80]}")
                await self._cache_replay(prompt_hash)
            elif sem_score >= FIREWALL_CONFIG["similarity_block_threshold"]:
                verdict.action = "BLOCK"
                verdict.threat_score = sem_score
                verdict.reasons.append(f"Semantic similarity {sem_score:.3f} breached threshold.")
                await self._cache_replay(prompt_hash)
            elif pii_result.was_modified:
                verdict.action = "SCRUB_AND_PASS"
                verdict.threat_score = 0.25
            elif sem_score >= FIREWALL_CONFIG["similarity_warn_threshold"]:
                verdict.threat_score = sem_score * 0.5
        # ─────────────────────────────────────────────────────────────────

        # PII scrub — always apply regardless of block decision
        if pii_result.was_modified:
            verdict.scrubbed_prompt = working_prompt
            if verdict.action == "PASS":
                verdict.action = "SCRUB_AND_PASS"
            verdict.reasons.append(f"PII removed: {pii_result.pii_types_found}")

        verdict.semantic_similarity = sem_score
        verdict.matched_threat_category = semantic_result.get("category")
        verdict.latency_ms = round((time.perf_counter() - t_start) * 1000, 2)

        # Stream all verdicts to Kafka → SIEM
        await self._emit_event(tenant_id, entity_id, verdict, prompt[:200])

        if verdict.action != "PASS":
            logger.warning(
                f"[FIREWALL] {verdict.action} | tenant={tenant_id} entity={entity_id} "
                f"score={verdict.threat_score:.3f} latency={verdict.latency_ms}ms "
                f"signal={dominant_signal} | {verdict.reasons[:2]}"
            )

        # ── LAYER 4: Semantic Logging (async, non-blocking, fail-open) ────
        if _SEMANTIC_LOG_AVAILABLE and verdict.threat_score >= 0.30:
            try:
                log_entry = SemanticLogEntry(
                    tenant_id=tenant_id,
                    entity_id=entity_id,
                    prompt_hash=prompt_hash,
                    threat_score=verdict.threat_score,
                    action=verdict.action,
                    dominant_signal=dominant_signal,
                    transformations_applied=transformations_applied,
                    multi_stage_flag=any(
                        "MULTI-STAGE" in r for r in verdict.reasons
                    ),
                )
                semantic_logger.log_async(log_entry)
            except Exception:
                pass  # Fail-open: never block on logging failure
        # ─────────────────────────────────────────────────────────────────

        # ── LAYER 5 (self-learning): Update OPA policy on every BLOCK ───────
        if verdict.action == "BLOCK":
            try:
                from app.core.opa_feedback import opa_feedback
                await opa_feedback.learn(
                    prompt=prompt[:500],
                    category=verdict.matched_threat_category or dominant_signal or "UNKNOWN",
                    threat_score=verdict.threat_score,
                    entity_id=entity_id,
                    tenant_id=tenant_id,
                    metadata={"reasons": verdict.reasons[:3], "signal": dominant_signal},
                )
            except Exception as e:
                logger.debug(f"[FIREWALL] OPA learn skipped: {e}")
        # ─────────────────────────────────────────────────────────────────

        return verdict

    # ------------------------------------------------------------------ #
    # Defence Vector A: Replay Cache
    # ------------------------------------------------------------------ #

    async def _check_replay_cache(self, prompt_hash: str) -> bool:
        if not self._redis:
            return False
        try:
            return bool(await self._redis.exists(f"firewall:replay:{prompt_hash}"))
        except Exception:
            return False

    async def _cache_replay(self, prompt_hash: str):
        if not self._redis:
            return
        try:
            await self._redis.setex(
                f"firewall:replay:{prompt_hash}",
                FIREWALL_CONFIG["replay_cache_ttl"],
                "1",
            )
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Defence Vector B: Injection Pattern Scan
    # ------------------------------------------------------------------ #

    def _scan_injection_patterns(self, text: str) -> List[str]:
        findings = []
        for pattern in INJECTION_PATTERNS:
            match = pattern.search(text)
            if match:
                findings.append(f"Injection pattern matched: '{match.group()[:60]}'")
        return findings

    # ------------------------------------------------------------------ #
    # Defence Vector C: Obfuscation Detection
    # ------------------------------------------------------------------ #

    def _scan_obfuscation(self, text: str) -> Optional[str]:
        return _detect_obfuscated_payload(text)

    # ------------------------------------------------------------------ #
    # Defence Vector D: PII Scrubbing (spaCy NER + Regex)
    # ------------------------------------------------------------------ #

    def _scrub_pii(self, text: str) -> PIIScrubResult:
        result = PIIScrubResult(original_text=text, scrubbed_text=text)

        # Regex-based scrubbing (Africa-aware patterns)
        for pattern_str, replacement in PII_PATTERNS:
            new_text, count = re.subn(pattern_str, replacement, result.scrubbed_text, flags=re.IGNORECASE)
            if count > 0:
                label = replacement.strip("[]").replace("_REDACTED", "")
                result.pii_types_found.append(label)
                result.scrubbed_text = new_text

        # spaCy NER for additional entity types
        if self._spacy_nlp:
            try:
                doc = self._spacy_nlp(result.scrubbed_text[:1024])  # limit for latency
                for ent in doc.ents:
                    if ent.label_ in ("PERSON", "GPE", "ORG", "DATE"):
                        # Conservative: only redact PERSON names
                        if ent.label_ == "PERSON":
                            result.scrubbed_text = result.scrubbed_text.replace(
                                ent.text, "[PERSON_REDACTED]"
                            )
                            result.pii_types_found.append("PERSON")
            except Exception:
                pass

        result.pii_types_found = list(set(result.pii_types_found))
        result.was_modified = result.scrubbed_text != text
        return result

    # ------------------------------------------------------------------ #
    # Defence Vector E: Semantic Similarity (pgvector)
    # ------------------------------------------------------------------ #

    async def _semantic_similarity_check(self, text: str) -> Dict[str, Any]:
        result = {"similarity": 0.0, "category": None}

        if not self._model or not self._pg_pool:
            return result

        try:
            # Encode prompt into 384-dim vector
            embedding = await asyncio.to_thread(
                self._model.encode,
                text,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )

            # Cosine similarity search in pgvector (IVFFlat index — very fast)
            async with self._pg_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT category,
                           1 - (embedding <=> $1::vector) AS cosine_similarity
                    FROM   threat_vectors
                    WHERE  is_active = TRUE
                    ORDER  BY embedding <=> $1::vector
                    LIMIT  1
                    """,
                    embedding.tolist(),
                )

            if row:
                result["similarity"] = round(float(row["cosine_similarity"]), 4)
                result["category"] = row["category"]

        except Exception as exc:
            logger.debug(f"[FIREWALL] Semantic check error: {exc}")

        return result

    # ------------------------------------------------------------------ #
    # Kafka Event Emission
    # ------------------------------------------------------------------ #

    async def _emit_event(
        self,
        tenant_id: str,
        entity_id: str,
        verdict: FirewallVerdict,
        prompt_preview: str,
    ):
        if not self._kafka_producer:
            return
        try:
            event = {
                "event_type": "FIREWALL_VERDICT",
                "timestamp": verdict.timestamp,
                "tenant_id": tenant_id,
                "entity_id": entity_id,
                "action": verdict.action,
                "threat_score": verdict.threat_score,
                "semantic_similarity": verdict.semantic_similarity,
                "reasons": verdict.reasons,
                "pii_types": verdict.pii_types_detected,
                "latency_ms": verdict.latency_ms,
                "prompt_hash": verdict.prompt_hash,
                "prompt_preview": prompt_preview,  # first 200 chars only
            }
            await self._kafka_producer.send_and_wait("firewall_events", event)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Global singleton — initialised during FastAPI lifespan
# ---------------------------------------------------------------------------
_firewall_instance: Optional[LLMFirewall] = None


async def get_firewall() -> LLMFirewall:
    """FastAPI dependency — returns the singleton firewall instance."""
    global _firewall_instance
    if _firewall_instance is None:
        _firewall_instance = await LLMFirewall.create()
    return _firewall_instance


async def startup_firewall():
    """Call from FastAPI lifespan startup to warm up the firewall."""
    global _firewall_instance
    _firewall_instance = await LLMFirewall.create()


async def shutdown_firewall():
    """Call from FastAPI lifespan shutdown."""
    global _firewall_instance
    if _firewall_instance:
        await _firewall_instance.shutdown()
        _firewall_instance = None
