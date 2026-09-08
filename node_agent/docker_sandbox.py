import docker
import json
import logging
from typing import Callable, Coroutine
import asyncio

logger = logging.getLogger(__name__)

class DockerSandbox:
    def __init__(self):
        try:
            self.client = docker.from_env()
        except Exception as e:
            logger.error(f"Failed to initialize Docker: {e}")
            self.client = None

    async def execute_and_stream(self, image: str, script_content: str, on_log: Callable[[str], Coroutine]):
        if not self.client:
            await on_log(json.dumps({"error": "Docker engine not available on node"}))
            return
            
        try:
            await on_log(json.dumps({"info": f"Starting container with image {image}..."}))
            
            # Spin up container (heavily restricted sandbox)
            container = self.client.containers.run(
                image, 
                command=["sh", "-c", script_content],
                detach=True,
                remove=True,
                mem_limit="512m",
                cpu_quota=100000,
                network_disabled=True
            )
            
            for line in container.logs(stream=True):
                await on_log(json.dumps({"log": line.decode('utf-8').strip()}))
                await asyncio.sleep(0.01) # Yield to event loop
                
        except Exception as e:
            logger.error(f"Execution error: {e}")
            await on_log(json.dumps({"error": str(e)}))

sandbox = DockerSandbox()
