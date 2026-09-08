import docker
import tempfile
import os
from app.schemas.ghost import ScriptExecuteResponse

class SandboxService:
    def __init__(self):
        try:
            self.client = docker.from_env()
        except Exception as e:
            import logging
            logging.error(f"Failed to initialize SandboxService docker client: {e}")
            self.client = None

    def run_in_container(self, code: str, language: str) -> ScriptExecuteResponse:
        if not self.client:
            return ScriptExecuteResponse(stdout="", stderr="Docker client unavailable", exit_code=-1, status="error")
        try:
            image = "python:3.9-alpine" if language == "python" else "alpine:3.19"
            
            # Determine command and file extension
            if language == "python":
                cmd = ["python", "/code/script.py"]
                filename = "script.py"
            elif language == "bash":
                cmd = ["/bin/sh", "/code/script.sh"]
                filename = "script.sh"
            elif language == "go":
                 # Go needs compilation, for MVP we can use `go run` if we use a go image, 
                 # but for now let's stick to simple scripting. 
                 # Switching to golang image for Go support
                 image = "golang:1.21-alpine"
                 cmd = ["go", "run", "/code/script.go"]
                 filename = "script.go"
            else:
                 return ScriptExecuteResponse(stdout="", stderr="Unsupported language", exit_code=1, status="error")

            # Create a wrapped script execution
            # We mount a temporary directory containing the script
            with tempfile.TemporaryDirectory() as temp_dir:
                script_path = os.path.join(temp_dir, filename)
                with open(script_path, "w") as f:
                    f.write(code)
                
                # Make script executable for bash
                if language == "bash":
                    os.chmod(script_path, 0o777)

                container = self.client.containers.run(
                    image,
                    command=cmd,
                    volumes={temp_dir: {'bind': '/code', 'mode': 'rw'}},
                    working_dir="/code",
                    detach=True,
                    network_disabled=False, # Allow network for "active defense" scripts if needed, or restrict for safety
                    mem_limit="128m",
                    cpu_period=100000,
                    cpu_quota=50000, # 50% CPU
                )

                try:
                    result = container.wait(timeout=10) # 10s timeout
                    logs = container.logs(stdout=True, stderr=True)
                    stdout = logs.decode("utf-8") # Docker combines streams in simple logs or we can separate
                    # For simplicity in this driver, we'll just dump logs to stdout
                    
                    return ScriptExecuteResponse(
                        stdout=stdout, 
                        stderr="", 
                        exit_code=result['StatusCode'], 
                        status="success"
                    )
                except Exception as e:
                     container.kill()
                     return ScriptExecuteResponse(stdout="", stderr=str(e), exit_code=-1, status="timeout")
                finally:
                    container.remove(force=True)

        except Exception as e:
             return ScriptExecuteResponse(stdout="", stderr=str(e), exit_code=-1, status="error")

sandbox_service = SandboxService()
