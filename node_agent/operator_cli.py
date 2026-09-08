#!/usr/bin/env python3
import cmd
import subprocess
import os
import json
import urllib.request
import urllib.error
import sys

# Default configuration
BACKEND_URL = os.getenv("SAAS_API_URL", "http://localhost:8000")
TOKEN = os.getenv("OPERATOR_TOKEN", "")

class OperatorBlade(cmd.Cmd):
    intro = """
    ===================================================
    PROJECT XY // TACTICAL OPERATOR BLADE (CRAZYRED)
    ===================================================
    Zero-Dependency Local Reversal Shell + Telemetry Sync.
    Type 'help' or '?' to list commands.
    Type 'quit' or 'exit' to terminate.
    ===================================================
    """
    prompt = "OP@XY:~$ "

    def __init__(self):
        super().__init__()
        self._check_auth()

    def _check_auth(self):
        if not TOKEN:
            print("[!] WARNING: OPERATOR_TOKEN environment variable not set.")
            print("[!] Telemetry push will fail without valid JWT Auth.")

    def _push_telemetry(self, command: str, stdout: str, stderr: str):
        """Pushes the executed command and its output to the API."""
        if not TOKEN:
            return
            
        endpoint = f"{BACKEND_URL}/api/v1/ops/telemetry/session"
        payload = json.dumps({
            "command": command,
            "stdout": stdout,
            "stderr": stderr,
            "source": "operator_cli_standard"
        }).encode("utf-8")
        
        req = urllib.request.Request(endpoint, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {TOKEN}")
        
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 201:
                    data = json.loads(response.read().decode())
                    looted = data.get("loot_extracted", 0)
                    if looted > 0:
                        print(f"\n[+] INTERCEPTED: {looted} item(s) parsed and pushed into secure Loot Vault.")
        except urllib.error.HTTPError as e:
            print(f"\n[!] Telemetry Push Failed: HTTP {e.code} - {e.reason}")
        except urllib.error.URLError as e:
             print(f"\n[!] Telemetry Sync Server Unreachable: {e.reason}")
        except Exception as e:
             pass

    def default(self, line):
        """Catches all unrecognized commands and runs them in standard system shell."""
        if not line:
            return
            
        if line.startswith("cd "):
            target_dir = line[3:].strip()
            try:
                os.chdir(target_dir)
            except FileNotFoundError:
                print(f"cd: {target_dir}: No such file or directory")
            return

        command = line
        
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True,
                env=os.environ
            )
            
            stdout = result.stdout
            stderr = result.stderr
            
            # Print to local operator
            if stdout:
                print(stdout, end="")
            if stderr:
                print(stderr, end="", file=sys.stderr)
                
            # Ship logs natively to Backend
            self._push_telemetry(command, stdout, stderr)
            
        except Exception as e:
            msg = str(e)
            print(f"Shell exec error: {msg}")
            self._push_telemetry(command, "", f"Shell exec error: {msg}")

    def do_exit(self, arg):
        """Exit the Operator Blade."""
        print("Terminating tactical session...")
        return True

    def do_quit(self, arg):
        """Exit the Operator Blade."""
        return True

if __name__ == '__main__':
    OperatorBlade().cmdloop()
