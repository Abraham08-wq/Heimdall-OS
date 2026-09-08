import math
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.models import Device, Geofence
from app.core.logging import logger

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees) in meters.
    """
    R = 6371000  # Radius of earth in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

async def check_geofence(db: Session, device_id: UUID, current_lat: float, current_lon: float):
    """
    Check if device is within its active geofences.
    Trigger alert if breached.
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        return

    # Check all active geofences for this device
    geofences = db.query(Geofence).filter(Geofence.device_id == device_id, Geofence.active == True).all()
    
    for fence in geofences:
        distance = haversine_distance(current_lat, current_lon, fence.center_latitude, fence.center_longitude)
        
        if distance > fence.radius_meters:
            # BREACH DETECTED
            logger.warning(f"GEOFENCE BREACH: Device {device.name} is {distance:.2f}m away from center! (Radius: {fence.radius_meters}m)")
            
            # TODO: Emit WebSocket event
            # await websocket_manager.broadcast(f"ALERT: Device {device.name} unauthorized movement!")
            
            # Log to Audit (Mocked for now or use audit_logger if importable)
            from app.services.audit import audit_logger
            audit_logger.log_action(
                actor_id="SYSTEM_WATCHDOG",
                action="GEOFENCE_BREACH",
                resource="DEVICE",
                target_id=str(device.id),
                metadata={
                    "distance": distance,
                    "radius": fence.radius_meters,
                    "lat": current_lat,
                    "lon": current_lon
                }
            )
