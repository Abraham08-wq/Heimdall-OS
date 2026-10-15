"""
Execution Engine - Docker-in-Docker Script Execution

The Executor spawns isolated Docker containers to run scripts safely.
It captures stdout/stderr in real-time and provides webhook callbacks for output streaming.

Safety Features:
- Memory limits (512MB default)
- CPU limits (1 CPU default)
- Network isolation (no external network by default)
- Timeout enforcement (300s default)
- Automatic container cleanup

Integration:
- WebSocket streaming via socket.py (real-time log broadcasting)
- Security state management via security_state.py (SYSTEM_LOCKDOWN, JWT revocation)
- Postgres ledger logging via ledger.py (immutable audit trail)
"""

import asyncio
import json
import os
import uuid
import docker
import logging
from datetime import datetime
from typing import Optional, Callable, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Import companion modules
try:
    from app.core.socket import ws_manager, MessageType, WSMessage
except ImportError:
    ws_manager = None

try:
    from app.core.security_state import security_manager
except ImportError:
    security_manager = None

try:
    from app.core.ledger import ledger
except ImportError:
    ledger = None


# FIXED: was a literal absolute path — "/home/ibraah/Desktop/ProjectXY/backend/tmp" — hardcoded into the
# source, which only ever resolved correctly on one specific machine at one specific clone location. Docker
# bind mounts are always resolved by the DAEMON against the HOST filesystem, regardless of which container is
# asking for them — so this container needs to be told what its own project root looks like from the host's
# point of view. HOST_PROJECT_ROOT is set in docker-compose.yml as ${PWD} (the directory `docker compose` was
# run from), which is exactly that path. If it's ever unset (e.g. running this module outside Docker), we fail
# loudly rather than silently building a wrong, possibly-someone-else's-home-directory path.
def _host_tmp_dir() -> str:
    root = os.environ.get("HOST_PROJECT_ROOT")
    if not root:
        raise RuntimeError(
            "HOST_PROJECT_ROOT is not set. This must be provided by docker-compose.yml (e.g. "
            "HOST_PROJECT_ROOT: ${PWD}) so the executor can tell the Docker daemon the correct HOST path "
            "for the sandbox's bind mount — a container-internal path (like /app/tmp) is meaningless to the "
            "daemon, which always resolves bind-mount sources against the host filesystem."
        )
    return f"{root.rstrip('/')}/backend/tmp"


# ─── Enums ────────────────────────────────────────────────────────────────────

class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


# ─── Pydantic Models ──────────────────────────────────────────────────────────

class ExecutionResult(BaseModel):
    """Result of script execution."""
    execution_id: str
    script_id: str
    script_name: str
    status: ExecutionStatus
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    error_message: Optional[str] = None

    class Config:
        use_enum_values = True


class ExecutionConfig(BaseModel):
    """Configuration for script execution."""
    memory_mb: int = Field(default=512, description="Memory limit in MB")
    cpu_quota: float = Field(default=1.0, description="CPU quota (1.0 = 1 full CPU)")
    timeout_seconds: int = Field(default=300, description="Execution timeout")
    network_disabled: bool = Field(default=True, description="Disable network access")
    user: str = Field(default="nobody", description="User to run script as")
    working_dir: str = Field(default="/tmp", description="Working directory in container")


# ─── Executor Service ──────────────────────────────────────────────────────────

class Executor:
    """
    Docker-in-Docker Execution Engine.

    Safely executes scripts in isolated Docker containers with resource limits.
    Captures output in real-time and provides webhook callbacks.
    """

    def __init__(self, docker_host: str = "unix:///var/run/docker.sock"):
        """
        Initialize the Executor.

        Args:
            docker_host: Docker daemon socket/endpoint
        """
        try:
            self.client = docker.from_env()
            logger.info("✅ Docker client connected")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Docker: {e}")
            self.client = None

        self.running_containers: Dict[str, str] = {}  # execution_id -> container_id
        self.results: Dict[str, ExecutionResult] = {}  # execution_id -> result
        self.user_id: Optional[str] = None  # Will be set per execution
        self.org_id: Optional[str] = None  # Will be set per execution

    # ─── Execution ─────────────────────────────────────────────────────────

    async def _check_lockdown(self, execution_id: str) -> bool:
        """
        Check if SYSTEM_LOCKDOWN is active. If so, prevent execution.
        """
        if security_manager:
            lockdown = await security_manager.get_lockdown_state()
            if lockdown:
                logger.error(f"🚨 Execution blocked due to SYSTEM_LOCKDOWN: {execution_id}")
                if ws_manager:
                    await ws_manager.send_system_alert(
                        "LOCKDOWN",
                        "System is in lockdown mode. Executions are blocked."
                    )
                return True
        return False

    async def execute_python(
            self,
            script_id: str,
            script_name: str,
            code: str,
            config: ExecutionConfig = None,
            output_callback: Optional[Callable[[str], None]] = None,
            user_id: Optional[str] = None,
            org_id: Optional[str] = None
    ) -> ExecutionResult:
        """
        Execute Python script in a Docker container.

        Args:
            script_id: UUID of the script
            script_name: Human-readable name
            code: Python code to execute
            config: ExecutionConfig (resource limits, timeouts)
            output_callback: Async callback for output chunks (for WebSocket streaming)
            user_id: User initiating the execution (for audit trail)
            org_id: Organization context (for audit trail)

        Returns:
            ExecutionResult with status, stdout, stderr, exit code
        """
        if not config:
            config = ExecutionConfig()

        execution_id = str(uuid.uuid4())
        self.user_id = user_id
        self.org_id = org_id

        logger.info(f"🚀 Executing Python script: {script_name} (ID: {execution_id})")

        # Check for SYSTEM_LOCKDOWN
        if await self._check_lockdown(execution_id):
            start_time = datetime.utcnow()
            result = ExecutionResult(
                execution_id=execution_id,
                script_id=script_id,
                script_name=script_name,
                status=ExecutionStatus.FAILED,
                exit_code=-1,
                stdout="",
                stderr="System is in lockdown mode",
                started_at=start_time,
                completed_at=start_time,
                duration_seconds=0,
                error_message="SYSTEM_LOCKDOWN"
            )
            return result

        # Log execution start to ledger
        if ledger:
            await ledger.log_execution_started(
                execution_id=execution_id,
                script_id=script_id,
                script_name=script_name,
                user_id=user_id,
                org_id=org_id
            )

        # Notify frontend via WebSocket
        if ws_manager:
            await ws_manager.send_status_update(
                execution_id=execution_id,
                status="RUNNING",
                details={"script_name": script_name, "script_id": script_id}
            )

        # Create a temporary file path inside the shared application scope
        container_script_path = f"/app/tmp/{script_id}.py"

        # FIXED: write the script BEFORE starting the sibling container, not after. The original order
        # started the container (which immediately tries to `python /app/tmp/{id}.py`) and only wrote the
        # file afterward — a race the sibling container could easily lose, on top of the host-mount mismatch
        # fixed below.
        os.makedirs("tmp", exist_ok=True)
        with open(f"tmp/{script_id}.py", "w") as f:
            f.write(code)

        try:
            # Spin up a lightweight Python container sandbox
            container = self.client.containers.run(
                "python:3.11-slim",
                command=f"python {container_script_path}",
                # FIXED: was a hardcoded absolute path that only existed on one developer's machine
                # (see _host_tmp_dir() above). This also now matches a real bind mount on the BACKEND
                # service itself (docker-compose.yml: `- ./backend/tmp:/app/tmp` on the `backend` service),
                # so a file this process writes to its own `tmp/` directory is actually visible at that host
                # path, and therefore actually visible to this sibling container too. Without that backend-side
                # mount, the file written above never reaches the host, and the sibling container's `python
                # /app/tmp/{id}.py` would always fail with "No such file or directory".
                volumes={_host_tmp_dir(): {"bind": "/app/tmp", "mode": "rw"}},
                detach=True,
                remove=False,
                mem_limit=f"{config.memory_mb}m",
                memswap_limit=f"{config.memory_mb}m",
                cpu_quota=int(config.cpu_quota * 100000),
                network_disabled=config.network_disabled,
                # FIXED: was hardcoded to "root" regardless of `config.user` (which defaults to "nobody").
                # Submitted code was always executed as root inside the sandbox container, silently ignoring
                # the privilege-drop this config field exists to provide.
                user=config.user,
                working_dir="/app"
            )

            self.running_containers[execution_id] = container.id
            logger.info(f"📦 Container started: {container.id[:12]}")

            # Monitor execution with timeout
            start_time = datetime.utcnow()
            stdout_data = ""
            stderr_data = ""

            try:
                # Wait for container with timeout
                exit_code = await asyncio.wait_for(
                    self._wait_container(container, output_callback),
                    timeout=config.timeout_seconds
                )

            except asyncio.TimeoutError:
                logger.warning(f"⏱️ Execution timeout for {script_name}")
                container.kill()
                exit_code = -1
                status = ExecutionStatus.TIMEOUT
                stderr_data = f"Execution timeout after {config.timeout_seconds} seconds"

            else:
                status = ExecutionStatus.COMPLETED if exit_code == 0 else ExecutionStatus.FAILED

            # Collect logs
            logs = container.logs(stdout=True, stderr=True).decode('utf-8', errors='replace')
            stdout_data = logs if exit_code == 0 else logs
            stderr_data = "" if exit_code == 0 else logs

            # Cleanup
            container.remove(force=True)
            del self.running_containers[execution_id]

            completed_time = datetime.utcnow()
            duration = (completed_time - start_time).total_seconds()

            result = ExecutionResult(
                execution_id=execution_id,
                script_id=script_id,
                script_name=script_name,
                status=status,
                exit_code=exit_code,
                stdout=stdout_data,
                stderr=stderr_data,
                started_at=start_time,
                completed_at=completed_time,
                duration_seconds=duration
            )

            self.results[execution_id] = result

            logger.info(
                f"✅ Execution completed: {script_name} "
                f"[Status: {status}, Exit Code: {exit_code}, Duration: {duration:.2f}s]"
            )

            # Log completion to ledger
            if ledger:
                await ledger.log_execution_completed(
                    execution_id=execution_id,
                    exit_code=exit_code,
                    duration_seconds=duration,
                    stdout=stdout_data,
                    stderr=stderr_data,
                    user_id=self.user_id,
                    org_id=self.org_id
                )

            # Notify frontend of completion
            if ws_manager:
                await ws_manager.send_completion(
                    execution_id=execution_id,
                    exit_code=exit_code,
                    duration_seconds=duration
                )

            return result

        except Exception as e:
            logger.error(f"❌ Execution failed: {e}")

            # Fallback if start_time was never initialized before crashing
            if 'start_time' not in locals():
                start_time = datetime.utcnow()

            # Ensure cleanup
            try:
                container.kill()
                container.remove(force=True)
            except:
                pass

            if execution_id in self.running_containers:
                del self.running_containers[execution_id]

            completed_time = datetime.utcnow()
            duration = (completed_time - start_time).total_seconds()

            result = ExecutionResult(
                execution_id=execution_id,
                script_id=script_id,
                script_name=script_name,
                status=ExecutionStatus.FAILED,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                started_at=start_time,
                completed_at=completed_time,
                duration_seconds=duration,
                error_message=str(e)
            )

            self.results[execution_id] = result

            # Log failure to ledger
            if ledger:
                await ledger.log_execution_completed(
                    execution_id=execution_id,
                    exit_code=-1,
                    duration_seconds=duration,
                    stdout="",
                    stderr=str(e),
                    user_id=self.user_id,
                    org_id=self.org_id
                )

            # Notify frontend of failure
            if ws_manager:
                await ws_manager.send_system_alert(
                    "EXECUTION_ERROR",
                    f"Execution {script_name} failed: {str(e)}"
                )

            return result

    # ─── Container Management ──────────────────────────────────────────────

    async def _wait_container(
            self,
            container,
            output_callback: Optional[Callable[[str], None]] = None
    ) -> int:
        """
        Wait for a container to finish and capture output in real-time.

        Args:
            container: Docker container object
            output_callback: Async callback for output streaming (called per chunk)

        Returns:
            Exit code
        """
        loop = asyncio.get_event_loop()

        # Stream logs in real-time
        if output_callback:
            try:
                logs_stream = container.logs(stream=True, follow=True)
                for log_chunk in logs_stream:
                    decoded_chunk = log_chunk.decode('utf-8', errors='replace')
                    if decoded_chunk:
                        await output_callback(decoded_chunk)
            except Exception as e:
                logger.warning(f"Failed to stream logs: {e}")

        def wait_for_exit():
            return container.wait()

        exit_code = await loop.run_in_executor(None, wait_for_exit)

        return exit_code.get('StatusCode', -1) if isinstance(exit_code, dict) else exit_code

    async def cancel_execution(self, execution_id: str) -> bool:
        """
        Cancel a running execution.

        Args:
            execution_id: UUID of the execution

        Returns:
            True if cancelled, False if not found
        """
        if execution_id not in self.running_containers:
            return False

        container_id = self.running_containers[execution_id]

        try:
            container = self.client.containers.get(container_id)
            container.kill()
            container.remove(force=True)

            if execution_id in self.results:
                self.results[execution_id].status = ExecutionStatus.CANCELLED

            logger.info(f"🛑 Execution cancelled: {execution_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to cancel execution: {e}")
            return False

    def get_result(self, execution_id: str) -> Optional[ExecutionResult]:
        """Retrieve execution result by ID."""
        return self.results.get(execution_id)

    def list_running_executions(self) -> List[str]:
        """List all running execution IDs."""
        return list(self.running_containers.keys())

    async def system_lockdown(self) -> None:
        """
        GLOBAL KILL SWITCH: Kill all running containers and revoke tokens.

        Called when SYSTEM_LOCKDOWN is triggered.
        """
        logger.critical("🚨 SYSTEM LOCKDOWN INITIATED - Killing all containers")

        execution_ids = list(self.running_containers.keys())

        for execution_id in execution_ids:
            await self.cancel_execution(execution_id)

        logger.critical("🚨 All containers terminated")

    # ─── Statistics ────────────────────────────────────────────────────────

    def get_statistics(self) -> Dict[str, Any]:
        """Get executor statistics."""
        completed = [r for r in self.results.values() if r.status == ExecutionStatus.COMPLETED]
        failed = [r for r in self.results.values() if r.status == ExecutionStatus.FAILED]
        timeouts = [r for r in self.results.values() if r.status == ExecutionStatus.TIMEOUT]

        avg_duration = (
            sum(r.duration_seconds for r in completed) / len(completed)
            if completed
            else 0
        )

        return {
            "total_executions": len(self.results),
            "running": len(self.running_containers),
            "completed": len(completed),
            "failed": len(failed),
            "timeouts": len(timeouts),
            "average_duration_seconds": avg_duration
        }
