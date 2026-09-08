import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class IoTBridgeService:
    def __init__(self):
        self.connected_devices = {
            "cam_01": {"type": "camera", "status": "online", "location": "Main Entrance"},
            "lock_05": {"type": "smart_lock", "status": "locked", "location": "Server Room"},
            "sensor_99": {"type": "motion", "status": "armed", "location": "Perimeter"},
        }

    def send_command(self, device_id: str, command: str) -> bool:
        """
        Sends a command to an IoT device via MQTT (Mocked).
        commands: LOCK, UNLOCK, ALARM_ON, ALARM_OFF, PAN_LEFT, PAN_RIGHT
        """
        if device_id not in self.connected_devices:
            logger.warning(f"Command failed: Device {device_id} not found.")
            return False

        logger.info(f"IoT COMMAND SENT: {command} -> {device_id} ({self.connected_devices[device_id]['location']})")
        
        # Simulate state change
        if command == "LOCK":
            self.connected_devices[device_id]['status'] = "locked"
        elif command == "UNLOCK":
            self.connected_devices[device_id]['status'] = "unlocked"
        elif command == "ALARM_ON":
             self.connected_devices[device_id]['status'] = "alarm_active"
             
        return True

    def get_rtsp_stream(self, device_id: str) -> str:
        """
        Returns the RTSP URL for a camera.
        """
        if self.connected_devices.get(device_id, {}).get("type") == "camera":
            return f"rtsp://10.0.0.50:554/{device_id}/live"
        return ""

iot_service = IoTBridgeService()
