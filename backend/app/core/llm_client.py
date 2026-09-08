"""
backend/app/core/llm_client.py
Async LLM client — Ollama primary, graceful degradation on failure.
No OpenAI dependency. Model: llama3.2 (fast, local, private).
"""
from __future__ import annotations
import asyncio
import json
import logging
from typing import Any, Optional
import httpx
from app.core.config import settings

log = logging.getLogger(__name__)

OLLAMA_BASE   = getattr(settings, "OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_MODEL  = getattr(settings, "OLLAMA_MODEL", "llama3.2")
TIMEOUT       = 60.0   # seconds


class LLMClient:
    """Async wrapper around the Ollama /api/generate endpoint."""

    def __init__(self, base_url: str = OLLAMA_BASE, model: str = OLLAMA_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model    = model
        self._client  = httpx.AsyncClient(timeout=TIMEOUT)

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> str:
        """Return a text completion from Ollama. Returns stub string when disabled or on failure."""
        if not getattr(settings, "ENABLE_OLLAMA", True):
            log.debug("[LLM] Ollama disabled (ENABLE_OLLAMA=false). Returning stub response.")
            return "[LLM OFFLINE] Ollama is disabled. Set ENABLE_OLLAMA=true to enable."

        payload: dict[str, Any] = {
            "model":  self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if system:
            payload["system"] = system

        try:
            resp = await self._client.post(f"{self.base_url}/api/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "").strip()
        except httpx.ConnectError:
            log.warning("[LLM] Ollama not reachable at %s — is the service running?", self.base_url)
            return "[LLM OFFLINE] Local Ollama service unavailable. Start with: docker compose up ollama"
        except httpx.TimeoutException:
            log.warning("[LLM] Ollama request timed out after %.0fs", TIMEOUT)
            return "[LLM TIMEOUT] Model inference exceeded time limit."
        except Exception as exc:  # noqa: BLE001
            log.error("[LLM] Unexpected error: %s", exc)
            return f"[LLM ERROR] {exc}"

    async def analyze_threat(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Structured threat analysis. Returns:
          {severity, summary, recommended_actions, mitre_techniques, confidence}

        When Ollama is disabled or unavailable, returns a safe structured stub
        rather than a raw error string (which would break JSON-parsing callers).
        """
        _offline_stub = {
            "severity": "UNKNOWN",
            "summary": "[LLM OFFLINE] Analysis unavailable — Ollama is disabled or unreachable.",
            "recommended_actions": ["Review logs manually"],
            "mitre_techniques": [],
            "confidence": 0.0,
        }

        if not getattr(settings, "ENABLE_OLLAMA", True):
            log.debug("[LLM] Ollama disabled — returning structured stub from analyze_threat.")
            return _offline_stub

        system_prompt = (
            "You are a cybersecurity threat analyst for ProjectXY. "
            "Analyze the given threat context and respond ONLY with valid JSON "
            "matching this schema: "
            '{"severity":"LOW|MEDIUM|HIGH|CRITICAL","summary":"string",'
            '"recommended_actions":["string"],"mitre_techniques":["Txxxx"],"confidence":0.0}'
        )
        user_prompt = f"Threat context:\n{json.dumps(context, indent=2)}"
        raw = await self.complete(user_prompt, system=system_prompt, temperature=0.1)

        # Detect offline/error string responses — return structured stub instead of crashing.
        if raw.startswith("[LLM "):
            return _offline_stub

        try:
            # Extract JSON from response (model may wrap it in markdown)
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(raw[start:end])
        except json.JSONDecodeError:
            pass

        # Fallback structured response
        return {
            "severity": "UNKNOWN",
            "summary": raw[:500] if raw else "Analysis unavailable",
            "recommended_actions": ["Review logs manually"],
            "mitre_techniques": [],
            "confidence": 0.0,
        }

    async def is_available(self) -> bool:
        """Ping Ollama to check if it's running."""
        try:
            resp = await self._client.get(f"{self.base_url}/api/tags", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.aclose()


# Singleton
llm_client = LLMClient()
