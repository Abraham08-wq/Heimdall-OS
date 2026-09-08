from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.services.combat import combat_orchestrator
import logging
import asyncio
import json
import random

router = APIRouter()
logger = logging.getLogger(__name__)


# ─── MITRE ATT&CK Kill-Chain Phase Definitions ────────────────────────────────

KILL_CHAIN_PHASES = [
    {"idx": 0, "id": "recon", "label": "RECONNAISSANCE", "color": "slate"},
    {"idx": 1, "id": "resource", "label": "RESOURCE DEV", "color": "blue"},
    {"idx": 2, "id": "initial", "label": "INITIAL ACCESS", "color": "amber"},
    {"idx": 3, "id": "execution", "label": "EXECUTION", "color": "orange"},
    {"idx": 4, "id": "persist", "label": "PERSISTENCE", "color": "red"},
    {"idx": 5, "id": "escalate", "label": "PRIV ESCALATION", "color": "rose"},
    {"idx": 6, "id": "lateral", "label": "LATERAL MOVEMENT", "color": "purple"},
    {"idx": 7, "id": "exfil", "label": "EXFILTRATION", "color": "fuchsia"},
]

# ─── Attack Narratives keyed by scenario ID ───────────────────────────────────

SCENARIO_NARRATIVES = {
    "apt_phantom": [
        # Phase 0: RECON
        (0, "T1595", "info", "[*] Initiating passive reconnaissance using OSINT sources: Shodan, Censys, Hunter.io..."),
        (0, "T1596", "info", "[*] Harvesting domain registration data, SSL certificate metadata, and exposed GitHub repos..."),
        (0, "T1591", "success", "[+] 14 employee emails extracted via LinkedIn scraping. 3 target executives identified."),
        (0, None, "success", "[+] Shodan reveals unpatched Apache Tomcat 9.0.50 on 192.168.1.45 (CVE-2021-33037 candidate)."),
        # Phase 1: RESOURCE DEV
        (1, "T1583", "info", "[*] Registering lookalike domain: corp-internal-vpn[.]net (typosquat of target domain)..."),
        (1, "T1587", "info", "[*] Compiling polymorphic payload — XOR-encoded, fileless, packed with MPRESS..."),
        (1, None, "success", "[+] Malicious macro-enabled Office document crafted. Metadata spoofed as 'Q1_Financial_Review.docx'."),
        # Phase 2: INITIAL ACCESS
        (2, "T1566.001", "warning", "[!] Spearphishing email dispatched to CFO <m.kowalski@target.corp> with weaponized attachment..."),
        (2, None, "info", "[*] Email bypassed Proofpoint SEG. No SPF/DKIM anomaly flagged."),
        (2, "T1190", "success", "[+] MACRO EXECUTED. Shellcode injected into WmiPrvSE.exe via process hollowing."),
        (2, None, "success", "[+] Reverse shell established: 192.168.1.205 → attacker-c2.corp-internal-vpn[.]net:443 (HTTPS)"),
        # Phase 3: EXECUTION
        (3, "T1059.001", "info", "[*] PowerShell Empire stager executing in-memory (no disk touch, AMSI bypassed via reflection)..."),
        (3, "T1106", "info", "[*] WMI lateral execution initiated. Spawning process on 192.168.1.45..."),
        (3, None, "success", "[+] Persistent beacon registered. Heartbeat interval: 30s. Traffic camouflaged as O365 OAuth."),
        # Phase 4: PERSISTENCE
        (4, "T1547.001", "warning", "[!] REGISTRY MODIFICATION: HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run → malware_svc.exe"),
        (4, "T1053.005", "warning", "[!] Scheduled task created: 'WindowsDefenderUpdate' → runs every 4 hours."),
        (4, None, "success", "[+] Domain admin account cloned: svc_backup_HIDDEN. AD object set to never expire."),
        # Phase 5: PRIVILEGE ESCALATION
        (5, "T1055", "info", "[*] Injecting into LSASS via process injection to dump credential hashes..."),
        (5, "T1068", "critical", "[!!!] LOCAL PRIVILEGE ESCALATION via PrintNightmare (CVE-2021-34527). SYSTEM achieved."),
        (5, "T1134", "success", "[+] Token impersonation: running as NT AUTHORITY\\SYSTEM. All access controls bypassed."),
        # Phase 6: LATERAL MOVEMENT
        (6, "T1021.002", "info", "[*] SMB lateral movement via Pass-the-Hash to shares (ADMIN$, C$) on .110, .115, .120..."),
        (6, "T1550.002", "warning", "[!] Pass-the-Hash successful on 192.168.1.110 — Domain Controller reached."),
        (6, "T1018", "info", "[*] Active Directory discovery: found 892 users, 47 admin accounts, 12 service principals."),
        (6, "T1003.001", "critical", "[!!!] DCSync attack executed — NTDS.dit extracted. ALL domain password hashes dumped."),
        # Phase 7: EXFILTRATION
        (7, "T1041", "critical", "[!!!] EXFILTRATION INITIATED: 14.7GB staged in encrypted .7z archives..."),
        (7, "T1567.002", "critical", "[!!!] Archive uploaded to GitHub private repo via HTTPS. Traffic blends with legitimate developer flow."),
        (7, None, "separator", "══ ACTION REPORT: OPERATION APT-41 PHANTOM PROTOCOL ══"),
        (7, None, "critical", "   CROWN JEWELS: COMPROMISED"),
        (7, None, "success", "   DATA EXFILTRATED: 14.7 GB (NTDS.dit, Financial DB, R&D Schematics)"),
        (7, None, "warning", "   INDICATORS: 0 ALERTS FIRED — COMPLETE STEALTH"),
    ],
    "ransomware_eclipse": [
        (0, "T1133", "info", "[*] Scanning for exposed RDP endpoints (port 3389)... 3 found."),
        (0, None, "success", "[+] Brute-force success on RDP 10.0.5.12 — credential: Administrator/Welcome1!"),
        (2, "T1486", "warning", "[!] Ransomware payload deployed: LockBit 3.0 clone — AES-256 + RSA-2048 hybrid encrypt."),
        (3, None, "critical", "[!!!] Backup catalog deletion initiated: vssadmin delete shadows /all /quiet"),
        (4, "T1490", "critical", "[!!!] VSS copies destroyed. System restore disabled. Backup agent killed."),
        (5, "T1489", "critical", "[!!!] Database services stopped: MySQL, PostgreSQL, MSSQL, Redis."),
        (6, None, "critical", "[!!!] Encrypting 847,293 files across 23 shared drives..."),
        (7, "T1567", "critical", "[!!!] 250GB exfiltrated to attacker CDN before encryption — double-extortion leverage secured."),
        (7, None, "separator", "══ OPERATION ECLIPSE: COMPLETE ══"),
        (7, None, "critical", "   IMPACT: €4.2M estimated ransom demand. 14-day deadline."),
    ],
    "insider_threat": [
        (0, "T1195", "info", "[*] Compromised dev credentials used to access CI/CD pipeline..."),
        (1, "T1176", "info", "[*] Malicious GitHub Action injected into .github/workflows/deploy.yml..."),
        (2, "T1525", "critical", "[!!!] Backdoor injected into production Docker image — pushed to ECR registry."),
        (3, "T1552", "warning", "[!] Env vars scraped: AWS_ACCESS_KEY_ID, DB_PASSWORD, JWT_SECRET extracted."),
        (4, "T1098", "critical", "[!!!] New IAM admin user created: svc-monitor-prod. MFA disabled."),
        (7, None, "separator", "══ OPERATION SILENT MOLE: COMPLETE ══"),
        (7, None, "critical", "   SUPPLY CHAIN POISONED — 34 enterprise customers affected."),
    ],
    "zero_day_storm": [
        (0, "T1190", "info", "[*] Scanning edge gateway firmware for unpatched CVEs..."),
        (2, "T1190", "critical", "[!!!] ZERO-DAY RCE exploited on edge gateway (CVE-2024-ZERO-0DAY). Root shell obtained."),
        (3, "T1572", "info", "[*] Protocol tunneling: SSH over DNS-over-HTTPS to bypass DPI..."),
        (4, "T1071.004", "warning", "[!] C2 heartbeat established over DoH — virtually undetectable by NGFW."),
        (6, "T1018", "info", "[*] OT network pivot successful — 47 ICS/SCADA endpoints discovered."),
        (7, None, "separator", "══ ZERO-DAY STORM: CRITICAL INFRASTRUCTURE BREACHED ══"),
        (7, None, "critical", "   OT NETWORK COMPROMISED — Physical process manipulation possible."),
    ],
}


async def _stream_narrative(ws: WebSocket, scenario_id: str, scenario: dict):
    """
    Streams the full MITRE ATT&CK kill-chain narrative to the Red Team UI.
    Sends structured events with phase progression, objectives, and metrics.
    """
    narrative = SCENARIO_NARRATIVES.get(scenario_id, SCENARIO_NARRATIVES["apt_phantom"])
    target = scenario.get("target", "Unknown Target")

    completed_phases = set()
    objectives = [
        "Establish Foothold", "Bypass EDR Detection", "Escalate Privileges",
        "Move Laterally", "Reach Crown Jewels", "Exfiltrate Payload"
    ]
    obj_phase_map = {0: 0, 1: 1, 3: 2, 5: 3, 6: 4, 7: 5}

    # Opening system message
    await ws.send_text(json.dumps({
        "log": f"[NEMESIS] Autonomous Adversary Engine v3.1 — ONLINE",
        "type": "system", "phase": "SYS", "phase_color": "slate"
    }))
    await asyncio.sleep(0.5)
    await ws.send_text(json.dumps({
        "log": f"[NEMESIS] Operation: {scenario.get('name', scenario_id)} | Target: {target} | Mode: FULL KILL CHAIN",
        "type": "system"
    }))
    await asyncio.sleep(0.8)

    total_vulns = 0
    total_alerts_fired = 0

    for phase_idx, technique, log_type, message in narrative:
        phase = KILL_CHAIN_PHASES[phase_idx]

        # Announce phase transition
        if phase_idx not in completed_phases:
            completed_phases.add(phase_idx)
            await ws.send_text(json.dumps({
                "phase_idx": phase_idx,
                "log": f"━━━ [{phase['label']}] ━━━",
                "type": "separator",
                "phase": phase['label'],
                "phase_color": phase['color']
            }))
            # Update objective if applicable
            obj_idx = obj_phase_map.get(phase_idx)
            if obj_idx is not None:
                # Mark previous objective as done
                if obj_idx > 0:
                    await ws.send_text(json.dumps({
                        "objective": {"label": objectives[obj_idx - 1], "status": "done"}
                    }))
                # Mark current as active
                if obj_idx < len(objectives):
                    await ws.send_text(json.dumps({
                        "objective": {"label": objectives[obj_idx], "status": "active"}
                    }))
            await asyncio.sleep(random.uniform(0.4, 0.8))

        # Stream the log event
        await ws.send_text(json.dumps({
            "log": message,
            "type": log_type,
            "technique": technique,
            "phase": phase['label'],
            "phase_color": phase['color'],
            "phase_idx": phase_idx,
        }))

        # Update metrics periodically
        if log_type in ("success", "critical"):
            total_vulns += 1
            await ws.send_text(json.dumps({
                "metrics": [
                    {"label": "SYSTEMS PWNED", "value": total_vulns, "color": "text-red-400"},
                    {"label": "ALERTS FIRED", "value": total_alerts_fired, "color": "text-emerald-400"},
                    {"label": "PHASE", "value": phase['label'][:10], "color": "text-amber-400"},
                    {"label": "DWELL TIME", "value": f"{random.randint(2,72)}h", "color": "text-purple-400"},
                ]
            }))

        await asyncio.sleep(random.uniform(0.8, 2.0))

    # Final objective wrap-up
    for obj in objectives:
        await ws.send_text(json.dumps({"objective": {"label": obj, "status": "done"}}))

    # Final metrics
    await ws.send_text(json.dumps({
        "metrics": [
            {"label": "SYSTEMS PWNED", "value": total_vulns, "color": "text-red-400"},
            {"label": "ALERTS FIRED", "value": total_alerts_fired, "color": "text-emerald-400"},
            {"label": "STATUS", "value": "COMPLETE", "color": "text-red-500"},
            {"label": "DWELL TIME", "value": f"72h", "color": "text-purple-400"},
        ]
    }))
    await ws.send_text(json.dumps({"log": "[NEMESIS] Operation concluded. Report delivered to Situation Room.", "type": "system"}))
    await ws.send_text(json.dumps({"log": "[TERMINATE]"}))


@router.websocket("/ws/combat/{agent_id}")
async def combat_websocket(websocket: WebSocket, agent_id: str):
    """WebSocket endpoint for Stealth Agents."""
    await combat_orchestrator.connect(websocket, agent_id)
    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(f"Telemetry from {agent_id}: {data}")
    except WebSocketDisconnect:
        combat_orchestrator.disconnect(agent_id)


@router.websocket("/ws/status")
async def dashboard_websocket(websocket: WebSocket):
    """WebSocket endpoint for the Situation Room Dashboard."""
    await combat_orchestrator.connect_dashboard(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        combat_orchestrator.disconnect_dashboard(websocket)


@router.websocket("/ws/redteam")
async def redteam_websocket(websocket: WebSocket):
    """
    Red Team NEMESIS AI — Full MITRE ATT&CK Kill-Chain Streaming Engine.
    Sends structured phase progressions, objective updates, and metrics.
    """
    await websocket.accept()
    logger.info("Red Team NEMESIS session connected.")
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                action = payload.get("action")
                if action == "launch":
                    scenario = payload.get("scenario", {})
                    scenario_id = scenario.get("id", "apt_phantom")
                    await _stream_narrative(websocket, scenario_id, scenario)
                elif action == "abort":
                    await websocket.send_text(json.dumps({"log": "[TERMINATE]"}))
            except Exception as e:
                logger.error(f"RedTeam WS error: {e}")
                await websocket.send_text(json.dumps({"log": f"[ERROR] Internal engine fault: {e}", "type": "critical"}))
    except WebSocketDisconnect:
        logger.info("Red Team NEMESIS session disconnected.")


@router.websocket("/ws/omniprobe")
async def omniprobe_websocket(websocket: WebSocket):
    """
    Omni-Probe live scanning WebSocket — streams host discoveries in real-time.
    """
    from app.modules.recon.omni_probe import omni_probe
    import ipaddress

    await websocket.accept()
    logger.info("Omni-Probe live scan session started.")
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            if payload.get("action") == "scan":
                target = payload.get("target", "127.0.0.1")
                scan_type = payload.get("scan_type", "FULL_SPECTRUM")

                await websocket.send_text(json.dumps({
                    "type": "status",
                    "message": f"[OMNI-PROBE] Initiating {scan_type} sweep against {target}..."
                }))

                # Expand the CIDR
                try:
                    net = ipaddress.ip_network(target, strict=False)
                    ips = [str(ip) for ip in net.hosts()][:64]
                    if not ips:
                        ips = [str(net.network_address)]
                except ValueError:
                    ips = [target]

                alive = 0
                for ip in ips:
                    result = await omni_probe._scan_host(ip)
                    if result["status"] == "up":
                        alive += 1
                        await websocket.send_text(json.dumps({
                            "type": "host",
                            "host": result,
                            "alive_count": alive
                        }))
                        await asyncio.sleep(0.05)  # small delay so UI can render

                await websocket.send_text(json.dumps({
                    "type": "complete",
                    "total_scanned": len(ips),
                    "total_alive": alive
                }))
    except WebSocketDisconnect:
        logger.info("Omni-Probe scan session disconnected.")
