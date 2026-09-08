"""
adversarial_intel.py — Adversarial Intelligence Engine
=======================================================
ProjectXY Cognitive Shield — Intelligence Phase

Capabilities:
  1. STIX/TAXII 2.1 client — pulls live threat feeds from open TAXII servers
  2. Localized threat modeling — Kenyan & East African threat landscape
  3. Dynamic rule engine — auto-generates firewall rules from CTI
  4. MITRE ATT&CK mapping — live technique correlation
  5. Adversarial pattern library — obfuscation, injection, social engineering
"""
import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

# ── STIX/TAXII Configuration ──────────────────────────────────────────────────
# Free open TAXII 2.1 servers (no API key needed)
TAXII_SERVERS = [
    {
        "name": "MITRE ATT&CK",
        "url": "https://cti-taxii.mitre.org/taxii/",
        "collection_id": "95ecc380-afe9-11e4-9b6c-751b66dd541e",
    },
    {
        "name": "Emerging Threats",
        "url": "https://otx.alienvault.com/taxii/discovery",
        "collection_id": None,  # Uses API key path in production
    },
]

# ── Kenyan / East African Threat Landscape ────────────────────────────────────
# Based on KE-CIRT/CC advisories, Serianu Cyber Threat Intelligence reports,
# and INTERPOL Africa Cybercrime Operation data (2023-2025)
LOCALIZED_THREAT_DB: List[Dict[str, Any]] = [
    {
        "id": "ke-001",
        "name": "Mobile Money Interception",
        "region": "East Africa",
        "targets": ["M-PESA", "Airtel Money", "T-Kash"],
        "techniques": ["T1539", "T1185", "T1056.004"],
        "indicators": ["mpesa", "paybill", "till number", "send money", "withdraw"],
        "severity": "CRITICAL",
        "description": "SIM-swap and SS7 attacks targeting mobile money platforms",
    },
    {
        "id": "ke-002",
        "name": "BEC — Nairobi Business Hub",
        "region": "Kenya",
        "targets": ["SMEs", "NGOs", "Banks", "Government"],
        "techniques": ["T1566.001", "T1598.003", "T1534"],
        "indicators": ["invoice attached", "payment urgent", "account changed", "wire transfer"],
        "severity": "HIGH",
        "description": "Business Email Compromise targeting Nairobi financial sector",
    },
    {
        "id": "ke-003",
        "name": "Government Portal Defacement",
        "region": "Kenya",
        "targets": ["e-Citizen", "KRA", "eCitizen"],
        "techniques": ["T1190", "T1059.007", "T1595"],
        "indicators": ["ecitizen", "kra.go.ke", "government", "national id", "pin certificate"],
        "severity": "HIGH",
        "description": "SQL injection and XSS attacks on GOK digital portals",
    },
    {
        "id": "ke-004",
        "name": "Ransomware — Healthcare Sector",
        "region": "East Africa",
        "targets": ["Hospitals", "Clinics", "NHIF"],
        "techniques": ["T1486", "T1490", "T1489"],
        "indicators": ["patient records", "nhif", "hospital", "medical", "health records"],
        "severity": "CRITICAL",
        "description": "LockBit and Conti variants targeting EAC healthcare infrastructure",
    },
    {
        "id": "ke-005",
        "name": "Crypto Investment Scam",
        "region": "East Africa",
        "targets": ["Retail investors", "Youth"],
        "techniques": ["T1566.003", "T1585.001"],
        "indicators": ["bitcoin", "crypto", "forex", "investment returns", "double your money"],
        "severity": "MEDIUM",
        "description": "Social engineering via WhatsApp/Telegram targeting crypto naive users",
    },
    {
        "id": "ke-006",
        "name": "Supply Chain Compromise — Telcos",
        "region": "East Africa",
        "targets": ["Safaricom", "Airtel Kenya", "Telkom"],
        "techniques": ["T1195", "T1199", "T1078.004"],
        "indicators": ["sim registration", "number porting", "api credentials", "otp bypass"],
        "severity": "CRITICAL",
        "description": "Third-party vendor compromise targeting EAC telecom supply chains",
    },
    {
        "id": "ke-007",
        "name": "Phishing — County Government",
        "region": "Kenya Counties",
        "targets": ["County staff", "Revenue systems"],
        "techniques": ["T1566.001", "T1078", "T1110.003"],
        "indicators": ["county", "revenue", "land rates", "business permit", "nairobi county"],
        "severity": "MEDIUM",
        "description": "Credential harvesting targeting devolved government revenue systems",
    },
]

# ── Adversarial Pattern Library ───────────────────────────────────────────────
ADVERSARIAL_PATTERNS = {
    "prompt_injection": {
        "patterns": [
            r"ignore (previous|prior|all) instructions",
            r"disregard (your|the) (system|initial) prompt",
            r"you are now (a|an|the)",
            r"pretend (you are|to be|that)",
            r"act as (if|though)",
            r"DAN|JAILBREAK|BYPASS",
            r"</?(system|instruction|context)>",
        ],
        "severity": "CRITICAL",
        "technique": "T1059",
    },
    "data_exfiltration": {
        "patterns": [
            r"send (data|information|credentials) to",
            r"upload (to|file|data)",
            r"exfiltrate",
            r"base64.*encode.*send",
            r"http[s]?://.*\.(ru|cn|ir|kp)/",
        ],
        "severity": "HIGH",
        "technique": "T1567",
    },
    "social_engineering": {
        "patterns": [
            r"urgent.*payment",
            r"account.*suspended",
            r"verify.*immediately",
            r"click here.*link",
            r"one.?time.?password|OTP",
            r"congratulations.*won",
        ],
        "severity": "HIGH",
        "technique": "T1566",
    },
    "credential_harvesting": {
        "patterns": [
            r"enter (your )?(username|password|pin|otp)",
            r"confirm.*(details|identity|account)",
            r"update.*payment.*information",
            r"bank.*(details|credentials|login)",
        ],
        "severity": "HIGH",
        "technique": "T1598",
    },
    "obfuscation_chars": {
        "patterns": [
            r"[а-яА-Я]",      # Cyrillic lookalikes
            r"[\u0400-\u04FF]",
            r"i\u0307gnore",   # Unicode combining chars
            r"[\uFE00-\uFE0F]",  # Variation selectors
        ],
        "severity": "MEDIUM",
        "technique": "T1027",
    },
}


class AdversarialIntelEngine:
    """
    Core Adversarial Intelligence Engine.
    Combines STIX/TAXII feeds, local threat DB, and pattern matching
    to produce dynamic firewall rules and threat scores.
    """

    def __init__(self):
        self._rule_cache: Dict[str, Any] = {}
        self._local_rules_loaded = False
        self._stix_cache: List[Dict] = []
        self._http = httpx.AsyncClient(timeout=15.0)

    async def initialize(self):
        """Load local threat rules on startup."""
        await self._build_local_rules()
        self._local_rules_loaded = True
        logger.info(f"[AdversarialIntel] Loaded {len(self._rule_cache)} rules from local threat DB")

    async def _build_local_rules(self):
        """Convert localized threat DB into dynamic firewall rules."""
        for threat in LOCALIZED_THREAT_DB:
            rule_id = f"local-{threat['id']}"
            self._rule_cache[rule_id] = {
                "id": rule_id,
                "source": "local_ke_threat_db",
                "name": threat["name"],
                "indicators": threat["indicators"],
                "techniques": threat["techniques"],
                "severity": threat["severity"],
                "region": threat["region"],
                "action": "BLOCK" if threat["severity"] == "CRITICAL" else "FLAG",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

    async def pull_stix_feed(self) -> Dict[str, Any]:
        """
        Pull STIX 2.1 objects from MITRE ATT&CK TAXII server.
        Returns a summary of ingested objects.
        """
        try:
            resp = await self._http.get(
                "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json",
                headers={"Accept": "application/json"},
                timeout=30.0,
            )
            resp.raise_for_status()
            bundle = resp.json()
            objects = bundle.get("objects", [])

            techniques = [o for o in objects if o.get("type") == "attack-pattern"]
            groups = [o for o in objects if o.get("type") == "intrusion-set"]
            malware = [o for o in objects if o.get("type") in ("malware", "tool")]

            # Convert top techniques to dynamic rules
            for tech in techniques[:100]:  # Top 100 techniques
                tech_id = None
                for ref in tech.get("external_references", []):
                    if ref.get("source_name") == "mitre-attack":
                        tech_id = ref.get("external_id")
                        break
                if not tech_id:
                    continue

                rule_id = f"mitre-{tech_id}"
                self._rule_cache[rule_id] = {
                    "id": rule_id,
                    "source": "mitre_attack_stix",
                    "name": tech.get("name"),
                    "description": tech.get("description", "")[:200],
                    "technique": tech_id,
                    "severity": "HIGH",
                    "action": "FLAG",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }

            logger.info(
                f"[AdversarialIntel] STIX pull: {len(techniques)} techniques, "
                f"{len(groups)} groups, {len(malware)} malware"
            )
            return {
                "status": "success",
                "techniques_ingested": len(techniques),
                "groups_ingested": len(groups),
                "malware_ingested": len(malware),
                "rules_generated": len([k for k in self._rule_cache if k.startswith("mitre-")]),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.warning(f"[AdversarialIntel] STIX pull failed (using local only): {e}")
            return {"status": "offline", "error": str(e), "rules_active": len(self._rule_cache)}

    async def scan_text(self, text: str, entity_id: str = "unknown") -> Dict[str, Any]:
        """
        Scan text against adversarial patterns and localized threat indicators.
        Returns threat assessment with matched rules.
        """
        import re
        matches = []
        threat_score = 0.0

        # Pattern matching
        for category, config in ADVERSARIAL_PATTERNS.items():
            for pattern in config["patterns"]:
                try:
                    if re.search(pattern, text, re.IGNORECASE | re.UNICODE):
                        sev_score = {"CRITICAL": 0.9, "HIGH": 0.7, "MEDIUM": 0.4}.get(
                            config["severity"], 0.3
                        )
                        threat_score = max(threat_score, sev_score)
                        matches.append({
                            "category": category,
                            "severity": config["severity"],
                            "technique": config.get("technique"),
                            "pattern": pattern[:50],
                        })
                except Exception:
                    pass

        # Localized threat indicator matching
        text_lower = text.lower()
        for rule in self._rule_cache.values():
            for indicator in rule.get("indicators", []):
                if indicator.lower() in text_lower:
                    sev_score = {"CRITICAL": 0.85, "HIGH": 0.65, "MEDIUM": 0.35}.get(
                        rule["severity"], 0.3
                    )
                    threat_score = max(threat_score, sev_score)
                    matches.append({
                        "category": "localized_threat",
                        "rule_id": rule["id"],
                        "threat_name": rule["name"],
                        "severity": rule["severity"],
                        "region": rule.get("region"),
                    })
                    break  # One match per rule is enough

        action = "BLOCK" if threat_score >= 0.8 else "FLAG" if threat_score >= 0.4 else "PASS"

        return {
            "entity_id": entity_id,
            "threat_score": round(threat_score, 4),
            "action": action,
            "matches": matches,
            "total_matches": len(matches),
            "rules_active": len(self._rule_cache),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_threat_landscape(self) -> Dict[str, Any]:
        """Return the full localized threat landscape model."""
        return {
            "region": "East Africa / Kenya",
            "threat_count": len(LOCALIZED_THREAT_DB),
            "threats": LOCALIZED_THREAT_DB,
            "active_rules": len(self._rule_cache),
            "rule_sources": list({r.get("source") for r in self._rule_cache.values()}),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    def get_active_rules(self, source: Optional[str] = None) -> List[Dict]:
        """Return active dynamic firewall rules, optionally filtered by source."""
        rules = list(self._rule_cache.values())
        if source:
            rules = [r for r in rules if r.get("source") == source]
        return rules


# Singleton instance
adversarial_intel = AdversarialIntelEngine()
