import os
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading

logger = logging.getLogger(__name__)

class TripwireHandler(FileSystemEventHandler):
    def __init__(self, service):
        self.service = service
        super().__init__()

    def on_modified(self, event):
        if event.is_directory:
            return
        import random
        attacker_ip = f"{random.randint(11, 200)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
        logger.critical(f"🚨 TRIPWIRE TRIGGERED: File modified - {event.src_path} by {attacker_ip}")
        self.service.add_alert("CRITICAL", f"Unauthorized access to decoy file: {event.src_path}", metadata={"attacker_ip": attacker_ip})
        # In a real scenario, we would trigger the "Deny Access" protocol here
        # via WebSocket broadcast and Firewall rules.

    def on_accessed(self, event):
        # Note: 'on_accessed' is not standard in all OS observers, but we can simulate/log
        pass

class TripwireService:
    def __init__(self):
        self.observer = Observer()
        self.active_decoys = []
        self.alerts = []
        self.handler = TripwireHandler(self)
        self._monitoring_active = False

    def add_alert(self, severity: str, message: str, metadata: dict = None):
        from datetime import datetime
        self.alerts.insert(0, {
            "id": len(self.alerts) + 1,
            "severity": severity,
            "message": message,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })
        # Keep only the latest 50 alerts
        if len(self.alerts) > 50:
            self.alerts = self.alerts[:50]

    def generate_decoy(self, type: str, path: str = ".") -> str:
        """
        Generates a fake configuration file with tracking tokens.
        """
        filename = f"config.{type}.env" if type == "env" else "secrets.yaml"
        full_path = os.path.join(path, filename)
        
        content = ""
        if type == "env":
            content = """# PRODUCTION DATABASE CREDENTIALS (DO NOT COMMIT)
DB_HOST=10.0.0.5
DB_USER=admin_root
DB_PASS=Sup3rS3cr3tP@ssw0rd!
AWS_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
            """
        else:
            content = """db:
  host: 10.0.0.5
  user: admin_root
  pass: Sup3rS3cr3tP@ssw0rd!
            """
            
        with open(full_path, "w") as f:
            f.write(content)
            
        self.active_decoys.append(full_path)
        logger.info(f"Decoy deployed at {full_path}")
        
        # Start monitoring if not already
        if not self._monitoring_active:
            self.start_monitoring(path)
            
        self.add_alert("MEDIUM", f"Deploying interactive tripwire decoy at {full_path}")
            
        return full_path

    def start_monitoring(self, path: str):
        if self._monitoring_active:
            return
            
        self.observer.schedule(self.handler, path, recursive=False)
        self.observer.start()
        self._monitoring_active = True
        logger.info(f"Tripwire Monitoring Active on {path}")

tripwire_service = TripwireService()
