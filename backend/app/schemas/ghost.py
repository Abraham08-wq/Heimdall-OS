from pydantic import BaseModel
from typing import Optional

class ScriptExecuteRequest(BaseModel):
    code: str
    language: str  # python, bash, go
    target_ip: Optional[str] = None

class ScriptExecuteResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    status: str # success, error, timeout
