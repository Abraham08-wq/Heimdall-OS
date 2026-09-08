"""
Seed: Operations Arsenal - Red & Blue Team Scripts

This seed populates the scripts_library with sample Red Team (offensive)
and Blue Team (defensive) scripts for demonstration and testing.
"""

import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import String
from app.services.ops.library import (
    ScriptORM, Team, Category, ScriptMetadata
)

logger = logging.getLogger(__name__)


def seed_operations_arsenal(db: Session):
    """Populate the scripts library with Red/Blue team scripts."""
    
    logger.info("🎯 Seeding Operations Arsenal...")
    
    # Check if already seeded
    existing_count = db.query(ScriptORM).count()
    if existing_count > 0:
        logger.info(f"⚠️ Scripts library already contains {existing_count} scripts, skipping seed")
        return
    
    # ─── RED TEAM SCRIPTS (Offensive/Attack Simulation) ─────────────────────
    
    red_team_scripts = [
        {
            "name": "Port Scan - Nmap Deep Recon",
            "language": "bash",
            "code": """#!/bin/bash
# Deep Reconnaissance Port Scan
# Scans target for open ports and service fingerprinting

TARGET=${1:-192.168.1.1}
echo "[*] Starting deep recon on $TARGET"
echo "[*] Scanning common ports (1-10000)..."

# Simulate port scan results
for port in 22 80 443 3306 5432 8080; do
    echo "[+] Port $port open - service: $(shuf -e "ssh" "http" "https" "mysql" "postgres" "http-alt" | head -1)"
done

echo "[*] Recon complete. Found 6 open ports."
""",
            "metadata": {
                "team": "red",
                "category": "recon",
                "danger_level": 2,
                "description": "Performs deep network reconnaissance using port scanning",
                "tags": ["nmap", "recon", "network-enumeration"],
                "author": "Red Team",
                "requires_approval": True,
                "timeout_seconds": 120
            }
        },
        {
            "name": "SQL Injection Probe",
            "language": "python",
            "code": """#!/usr/bin/env python3
# SQL Injection Vulnerability Scanner
# Tests target application for SQL injection vulnerabilities

import sys
import time

target_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000/api/user"

payloads = [
    "' OR '1'='1",
    "admin' --",
    "1'; DROP TABLE users; --",
    "1' UNION SELECT NULL, NULL, NULL --"
]

print("[*] Starting SQL Injection probe")
print(f"[*] Target: {target_url}")
print(f"[*] Testing {len(payloads)} payload variations...")

for i, payload in enumerate(payloads):
    print(f"[>] Testing payload {i+1}/{len(payloads)}: {payload[:40]}...")
    time.sleep(0.5)

print("[*] Probe complete. No vulnerabilities detected in this simulation.")
""",
            "metadata": {
                "team": "red",
                "category": "exploit",
                "danger_level": 5,
                "description": "Tests web applications for SQL injection vulnerabilities",
                "tags": ["sql-injection", "web-app", "vulnerability-scanning"],
                "author": "Red Team",
                "requires_approval": True,
                "timeout_seconds": 180
            }
        },
        {
            "name": "Credential Harvesting - Phishing Simulation",
            "language": "python",
            "code": """#!/usr/bin/env python3
# Phishing Campaign Simulator (Educational)
# Generates HTML phishing page templates for authorized testing

import json
from datetime import datetime

phishing_targets = [
    {"email": "admin@company.com", "name": "Admin User"},
    {"email": "finance@company.com", "name": "Finance Team"},
    {"email": "hr@company.com", "name": "HR Department"}
]

print("[*] Phishing Campaign Simulator - Educational Mode")
print(f"[*] Generated {len(phishing_targets)} target profiles")
print("[!] NOTE: This is for authorized red team exercises only")

campaign_data = {
    "campaign_id": "SIMUL-2026-001",
    "created_at": datetime.now().isoformat(),
    "targets": phishing_targets,
    "status": "simulated"
}

print(json.dumps(campaign_data, indent=2))
""",
            "metadata": {
                "team": "red",
                "category": "exploit",
                "danger_level": 7,
                "description": "Simulates phishing campaigns for authorized security testing",
                "tags": ["phishing", "social-engineering", "authorized-only"],
                "author": "Red Team",
                "requires_approval": True,
                "timeout_seconds": 60
            }
        }
    ]
    
    # ─── BLUE TEAM SCRIPTS (Defensive/Containment) ──────────────────────────
    
    blue_team_scripts = [
        {
            "name": "Firewall Rule Deployment - Quick Patch",
            "language": "bash",
            "code": """#!/bin/bash
# Emergency Firewall Rule Deployment
# Quickly blocks known malicious IP ranges

echo "[*] Emergency Firewall Deployment"
echo "[*] Deploying critical firewall rules..."

rules=(
    "192.168.100.0/24 DROP"
    "10.10.10.0/24 DROP"
    "172.16.50.0/24 DROP"
)

for rule in "${rules[@]}"; do
    echo "[+] Deploying rule: $rule"
    sleep 0.5
done

echo "[✓] Firewall rules deployed successfully"
echo "[*] Blocked 3 malicious networks"
""",
            "metadata": {
                "team": "blue",
                "category": "isolation",
                "danger_level": 4,
                "description": "Deploys emergency firewall rules to block known threats",
                "tags": ["firewall", "incident-response", "network-isolation"],
                "author": "Blue Team",
                "requires_approval": False,
                "timeout_seconds": 60
            }
        },
        {
            "name": "Patch Management - Security Updates",
            "language": "bash",
            "code": """#!/bin/bash
# Automated Patch Management
# Applies security patches to vulnerable systems

echo "[*] Security Patch Management System"
echo "[*] Scanning for vulnerable packages..."

vulnerable_packages=(
    "openssl-1.0.2"
    "apache2-2.4.1"
    "mysql-5.7.0"
)

echo "[*] Found ${#vulnerable_packages[@]} vulnerable packages"

for pkg in "${vulnerable_packages[@]}"; do
    echo "[+] Patching: $pkg"
    sleep 0.5
done

echo "[✓] All security patches applied"
echo "[*] System is now hardened against known CVEs"
""",
            "metadata": {
                "team": "blue",
                "category": "patch",
                "danger_level": 2,
                "description": "Automatically applies security patches to vulnerable systems",
                "tags": ["patching", "vulnerability-management", "hardening"],
                "author": "Blue Team",
                "requires_approval": False,
                "timeout_seconds": 300
            }
        },
        {
            "name": "Incident Response - Log Forensics",
            "language": "python",
            "code": """#!/usr/bin/env python3
# Forensic Log Analysis
# Analyzes security logs to detect indicators of compromise (IoCs)

import json
from datetime import datetime, timedelta

print("[*] Security Log Forensics Analysis")
print("[*] Analyzing last 7 days of audit logs...")

# Simulated detection results
findings = {
    "total_events": 15643,
    "suspicious_events": 23,
    "detected_iocs": [
        {"type": "ip", "value": "192.168.100.55", "severity": "high"},
        {"type": "user", "value": "service_account_001", "severity": "medium"},
        {"type": "file_hash", "value": "5d41402abc4b2a76b9719d911017c592", "severity": "critical"}
    ],
    "attack_timeline": [
        {"timestamp": (datetime.now() - timedelta(hours=2)).isoformat(), "event": "Lateral movement detected"},
        {"timestamp": (datetime.now() - timedelta(hours=1)).isoformat(), "event": "Data exfiltration attempt"}
    ]
}

print("[+] Analysis complete:")
print(json.dumps(findings, indent=2))
print("\\n[!] RECOMMENDATION: Initiate immediate containment procedures for detected IoCs")
""",
            "metadata": {
                "team": "blue",
                "category": "forensics",
                "danger_level": 3,
                "description": "Analyzes security logs and detects indicators of compromise",
                "tags": ["forensics", "log-analysis", "incident-response"],
                "author": "Blue Team",
                "requires_approval": False,
                "timeout_seconds": 120
            }
        },
        {
            "name": "Endpoint Hardening - Security Baseline",
            "language": "bash",
            "code": """#!/bin/bash
# System Hardening & Security Baseline Configuration
# Applies CIS benchmark security controls

echo "[*] System Hardening and Security Baseline"
echo "[*] Applying CIS Benchmark Controls..."

controls=(
    "Disable unnecessary services"
    "Enable SELinux/AppArmor"
    "Configure auditd rules"
    "Set restrictive file permissions"
    "Enable firewall"
    "Configure fail2ban"
    "Update security limits"
)

for control in "${controls[@]}"; do
    echo "[+] Applying: $control"
    sleep 0.3
done

echo "[✓] System hardening complete"
echo "[*] Security baseline established per CIS Benchmark v2.0"
""",
            "metadata": {
                "team": "blue",
                "category": "hardening",
                "danger_level": 3,
                "description": "Applies CIS Benchmark security controls for system hardening",
                "tags": ["hardening", "cis-benchmark", "security-baseline"],
                "author": "Blue Team",
                "requires_approval": False,
                "timeout_seconds": 240
            }
        }
    ]
    
    # ─── Insert Red Team Scripts ────────────────────────────────────────────
    
    for index, script_data in enumerate(red_team_scripts, start=1):
        script_id = f"script-red-{index}"
        if db.query(ScriptORM).filter(ScriptORM.name == script_data["name"]).first():
            logger.info(f"⚠️ Red Team script already exists: {script_data['name']}")
            continue

        script = ScriptORM(
            id=script_id,
            name=script_data["name"],
            language=script_data["language"],
            code=script_data["code"],
            metadata_=script_data["metadata"],
            created_by="seed_script",
            is_approved=False,  # Red team scripts require manual approval
            is_disabled=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(script)
        logger.info(f"✅ Added Red Team script: {script_data['name']}")
    
    # ─── Insert Blue Team Scripts ───────────────────────────────────────────
    
    for index, script_data in enumerate(blue_team_scripts, start=1):
        script_id = f"script-blue-{index}"
        if db.query(ScriptORM).filter(ScriptORM.name == script_data["name"]).first():
            logger.info(f"⚠️ Blue Team script already exists: {script_data['name']}")
            continue

        script = ScriptORM(
            id=script_id,
            name=script_data["name"],
            language=script_data["language"],
            code=script_data["code"],
            metadata_=script_data["metadata"],
            created_by="seed_script",
            is_approved=True,  # Blue team scripts auto-approved (safe)
            is_disabled=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(script)
        logger.info(f"✅ Added Blue Team script: {script_data['name']}")
    
    db.commit()
    
    logger.info("✅ Operations Arsenal seeding complete!")
    logger.info(f"   - {len(red_team_scripts)} Red Team (Offensive) scripts loaded")
    logger.info(f"   - {len(blue_team_scripts)} Blue Team (Defensive) scripts loaded")
