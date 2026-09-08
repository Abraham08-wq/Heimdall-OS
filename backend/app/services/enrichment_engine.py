"""
Enrichment Engine — v2 (Power Upgrade)
────────────────────────────────────────
Upgrades over v1:
  • APT group attribution: maps IP/behavior to known MITRE ATT&CK groups
  • Passive TLS fingerprint: JA3/JA3S hash simulation
  • Combined omniscient verdict: HOSTILE / SUSPICIOUS / BENIGN
  • Passive banner grab simulation
  • Enrichment confidence score with multi-source weighting
"""
import logging
import hashlib
from typing import Dict, Any
from fastapi import HTTPException, status
from app.infrastructure.graph import graph_db
from app.services.audit import audit_logger

logger = logging.getLogger(__name__)

# ─── Known APT group signatures ───────────────────────────────────────────────

APT_SIGNATURES: Dict[str, Dict[str, Any]] = {
    "APT-29": {
        "aliases": ["Cozy Bear", "The Dukes", "NOBELIUM"],
        "nation": "Russia",
        "ttps": ["T1566.001", "T1078", "T1027", "T1071.001"],
        "sectors_targeted": ["Government", "Defence", "Energy", "Healthcare"],
        "confidence": 0.88,
    },
    "APT-41": {
        "aliases": ["Double Dragon", "Winnti", "BARIUM"],
        "nation": "China",
        "ttps": ["T1190", "T1059.003", "T1021.002", "T1041"],
        "sectors_targeted": ["Technology", "Healthcare", "Telecoms", "Gaming"],
        "confidence": 0.91,
    },
    "Lazarus Group": {
        "aliases": ["HIDDEN COBRA", "Guardians of Peace"],
        "nation": "North Korea",
        "ttps": ["T1059.001", "T1486", "T1041", "T1078"],
        "sectors_targeted": ["Finance", "Cryptocurrency", "Defence"],
        "confidence": 0.85,
    },
    "Sandworm": {
        "aliases": ["Voodoo Bear", "IRIDIUM"],
        "nation": "Russia",
        "ttps": ["T1561.002", "T1486", "T1071.004", "T1498"],
        "sectors_targeted": ["Critical Infrastructure", "Energy", "Government"],
        "confidence": 0.93,
    },
    "Kimsuky": {
        "aliases": ["Velvet Chollima", "Black Banshee"],
        "nation": "North Korea",
        "ttps": ["T1566.001", "T1059.005", "T1071.001"],
        "sectors_targeted": ["Think tanks", "Government", "Research"],
        "confidence": 0.80,
    },
}

VERDICT_THRESHOLDS = {
    "HOSTILE":    80,
    "SUSPICIOUS": 50,
    "BENIGN":     0,
}


class EnrichmentEngine:
    """
    Adaptive Threat Intelligence Enrichment Engine v2.
    Enriches entities with APT attribution, TLS fingerprinting,
    multi-source threat intelligence, and a compiled omniscient verdict.
    """

    async def _verify_prior_interaction(self, target_ip: str, tenant_id: str) -> bool:
        query = """
        MATCH (ip:IP {value: $ip})-[:TARGETS]->(asset:InternalAsset {tenant_id: $tenant_id})
        RETURN ip LIMIT 1
        """
        try:
            results = await graph_db.execute_query(query, {"ip": target_ip, "tenant_id": tenant_id})
            return len(results) > 0
        except Exception as e:
            logger.error(f"Interaction check failed for {target_ip}: {e}")
            return False

    async def enrich_entity(
        self,
        target_ip: str,
        user_id: str,
        tenant_id: str,
        justification: str,
    ) -> Dict[str, Any]:

        has_interacted = await self._verify_prior_interaction(target_ip, tenant_id)
        if not has_interacted:
            audit_logger.log_action(
                actor_id=user_id,
                action="DENIED_ENRICHMENT_ATTEMPT",
                resource="THREAT_INTEL",
                target_id=target_ip,
                metadata={"reason": "No prior infrastructure interaction. Legally prohibited."},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Enrichment Denied: Target has no recorded interaction with tenant infrastructure.",
            )

        audit_id = audit_logger.log_action(
            actor_id=user_id,
            action="ENRICHMENT_EXECUTED",
            resource="THREAT_INTEL",
            target_id=target_ip,
            metadata={"justification": justification},
        )

        # Run all enrichment layers
        geo      = self._geo_lookup(target_ip)
        asn      = self._asn_lookup(target_ip)
        device   = self._device_fingerprint(target_ip)
        threat   = self._threat_feed(target_ip)
        apt      = self._apt_attribution(target_ip, threat)
        tls      = self._tls_fingerprint(target_ip)
        banner   = self._banner_grab(target_ip)

        # Composite omniscient confidence score
        omniscient = round(
            (threat["risk_score"] * 0.40)
            + (device["evasion_score"] * 100 * 0.25)
            + (apt["attribution_confidence"] * 100 * 0.20)
            + (float(geo["is_anonymous_proxy"]) * 15)
        , 1)

        verdict = next(
            (v for v, threshold in VERDICT_THRESHOLDS.items() if omniscient >= threshold),
            "BENIGN"
        )

        return {
            "entity_id":           target_ip,
            "audit_reference_id":  audit_id,
            "timestamp":           "2026-03-06T18:00:00Z",
            "location_data":       geo,
            "network_infrastructure": asn,
            "device_fingerprint":  device,
            "tls_fingerprint":     tls,
            "passive_banner":      banner,
            "threat_reputation":   threat,
            "apt_attribution":     apt,
            "omniscient_confidence_score": omniscient,
            "verdict":             verdict,
            "verdict_rationale":   self._build_rationale(threat, apt, geo, omniscient),
        }

    # ─── Intelligence layers ──────────────────────────────────────────────────

    def _geo_lookup(self, ip: str) -> Dict[str, Any]:
        """Simulates MaxMind GeoIP2 Enterprise."""
        return {
            "country": "Russian Federation",
            "country_iso": "RU",
            "city": "St. Petersburg",
            "coordinates": {"lat": 59.9311, "lon": 30.3609},
            "accuracy_radius_km": 5,
            "is_anonymous_proxy": True,
            "is_tor_exit_node": "185." in ip,
            "is_satellite_provider": False,
        }

    def _asn_lookup(self, ip: str) -> Dict[str, Any]:
        """Simulates BGP/ASN lookup."""
        return {
            "asn": "AS4134",
            "organization": "Chinanet",
            "domain": "chinatelecom.com.cn",
            "route": "1.0.0.0/24",
            "type": "hosting",
            "abuse_score": 87,
        }

    def _device_fingerprint(self, ip: str) -> Dict[str, Any]:
        """Simulates Shodan/Censys passive fingerprinting."""
        return {
            "inferred_os": "Linux 4.x",
            "inferred_mac_vendor": "Cisco Systems" if "192." in ip else "Unknown VPS",
            "open_ports": [22, 80, 443, 8080, 4444],
            "running_services": ["OpenSSH 8.2p1", "nginx/1.18.0", "Cobalt Strike Beacon"],
            "evasion_score": 0.82,
            "ttl_anomaly": True,
            "tcp_fingerprint": "Linux/4.15 (High-confidence)",
        }

    def _tls_fingerprint(self, ip: str) -> Dict[str, Any]:
        """Simulates JA3/JA3S passive TLS fingerprint."""
        # Deterministic but realistic-looking hashes
        ja3  = hashlib.md5(f"ja3_{ip}".encode()).hexdigest()
        ja3s = hashlib.md5(f"ja3s_{ip}".encode()).hexdigest()
        return {
            "ja3_hash":  ja3,
            "ja3s_hash": ja3s,
            "ja3_known_malware": ja3 in {
                "51c64c77e60f3980eea90869b68c58a8",
                "a0e9f5d64349fb13191bc781f81f42e1",
            },
            "tls_version": "TLSv1.3",
            "cipher_suite": "TLS_AES_256_GCM_SHA384",
            "certificate_issuer": "Let's Encrypt Authority X3",
            "cert_age_days": 4,
            "cert_suspicion": "Newly issued — common in C2 infrastructure.",
        }

    def _banner_grab(self, ip: str) -> Dict[str, Any]:
        """Simulates passive banner analysis."""
        return {
            "http_server": "nginx/1.18.0",
            "http_title":  "400 Bad Request",
            "ssh_banner":  "OpenSSH_8.2p1 Ubuntu-4ubuntu0.11",
            "anomaly":     "HTTP returns 400 on all paths — consistent with Cobalt Strike default listener.",
        }

    def _threat_feed(self, ip: str) -> Dict[str, Any]:
        """Simulates VirusTotal / GreyNoise / CrowdStrike lookup."""
        return {
            "known_botnet_member": "Mirai Variant",
            "recent_c2_activity": True,
            "malware_associations": ["Ransom:Win32/WannaCrypt", "Trojan:Linux/Xorddos"],
            "last_seen_scanning_internet": "2026-03-05T18:00:00Z",
            "risk_score": 92,
            "feed_sources": ["VirusTotal", "GreyNoise", "AbuseIPDB", "CrowdStrike Falcon"],
            "first_seen_malicious": "2025-11-14T00:00:00Z",
        }

    def _apt_attribution(self, ip: str, threat: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maps observed indicators to known APT groups.
        In production: match against CrowdStrike, Dragos, or Mandiant TIP.
        """
        # Simulated: high-risk IPs get APT-41 attribution
        if threat.get("risk_score", 0) > 85:
            group_name = "APT-41"
            group = APT_SIGNATURES[group_name]
            return {
                "attributed_group":      group_name,
                "nation_state":          group["nation"],
                "aliases":               group["aliases"],
                "observed_ttps":         group["ttps"],
                "sectors_at_risk":       group["sectors_targeted"],
                "attribution_confidence": group["confidence"],
                "attribution_method":    "TTP_FINGERPRINT_MATCH",
                "confidence_rationale":  (
                    f"TTP overlap with {group_name} ({', '.join(group['ttps'][:2])}) "
                    f"combined with geo origin ({group['nation']}) exceeds attribution threshold."
                ),
            }
        return {
            "attributed_group":       "UNKNOWN",
            "attribution_confidence": 0.0,
            "attribution_method":     "INSUFFICIENT_INDICATORS",
        }

    def _build_rationale(
        self,
        threat: Dict,
        apt: Dict,
        geo: Dict,
        score: float,
    ) -> str:
        verdict_word = "HOSTILE" if score >= 80 else "SUSPICIOUS" if score >= 50 else "BENIGN"
        parts = [f"Verdict [{verdict_word}] based on composite evidence:"]
        if threat.get("recent_c2_activity"):
            parts.append("Active C2 beaconing detected in threat feeds.")
        if geo.get("is_tor_exit_node"):
            parts.append("Source is a known Tor exit node.")
        if apt.get("attributed_group") != "UNKNOWN":
            parts.append(
                f"Attributed to {apt['attributed_group']} ({apt['nation_state']}) "
                f"with {apt['attribution_confidence']*100:.0f}% confidence."
            )
        if threat.get("known_botnet_member"):
            parts.append(f"Member of {threat['known_botnet_member']} botnet.")
        return " ".join(parts)


enrichment_engine = EnrichmentEngine()
