import asyncio
import websockets
import os
import json
import logging
import random
from docker_sandbox import sandbox

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY = os.environ["NODE_API_KEY"]
SAAS_WS_URL = os.getenv("SAAS_WS_URL", "ws://localhost:8000/api/v1/nodes/ws")

async def telemetry_loop(websocket):
    """Continuously broadcasts structured telemetry metrics."""
    endpoints = ["/api/v1/auth", "/admin/config", "/public/status", "/api/v2/data"]
    while True:
        try:
            telemetry_payload = {
                "type": "telemetry",
                "source_ip": f"10.0.1.{random.randint(10, 100)}",
                "data": {
                    "requests_per_second": random.uniform(5.0, 150.0),
                    "payload_bytes": random.randint(500, 55000000),
                    "path": random.choice(endpoints),
                    "failed_login_attempts": random.randint(0, 10),
                    "unique_dst_ports": random.randint(1, 25),
                    "bytes_in": random.randint(1000, 100000),
                    "bytes_out": random.randint(1000, 10000000)
                }
            }
            await websocket.send(json.dumps(telemetry_payload))
            await asyncio.sleep(3)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Telemetry loop error: {e}")
            break

async def authenticate_and_listen():
    logger.info(f"Connecting to {SAAS_WS_URL}...")
    headers = {"X-Node-API-Key": API_KEY}
    while True:
        try:
            async with websockets.connect(SAAS_WS_URL, additional_headers=headers) as websocket:
                logger.info("Connected to SaaS Control Plane successfully.")
                
                # Start background telemetry generator
                telemetry_task = asyncio.create_task(telemetry_loop(websocket))
                
                # Listen for commands
                while True:
                    try:
                        message = await websocket.recv()
                        command_payload = json.loads(message)
                        logger.info(f"Received execution command")
                    except Exception as parse_err:
                        logger.error(f"Failed to parse incoming command: {parse_err}")
                        continue
                    
                    script_code = command_payload.get("script", "echo 'No script provided'")
                    image = command_payload.get("image", "alpine:latest")
                    
                    # Async callback to stream logs back
                    async def send_log_back(log_frame: str):
                        await websocket.send(log_frame)

                    # Run isolated payload
                    await sandbox.execute_and_stream(image, script_code, send_log_back)
                    await send_log_back(json.dumps({"info": "Execution complete."}))
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Connection to SaaS closed. Reconnecting in 5s...")
            if 'telemetry_task' in locals():
                telemetry_task.cancel()
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"WebSocket error: {e}. Reconnecting in 5s...")
            if 'telemetry_task' in locals():
                telemetry_task.cancel()
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(authenticate_and_listen())
