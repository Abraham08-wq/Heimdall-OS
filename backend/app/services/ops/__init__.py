"""
Operations Service Module - Script Library & Execution Engine

This module provides:
- Script Repository Pattern (CRUD operations on executable scripts)
- Metadata Integration (Team, Category, Danger Level tagging)
- Docker-in-Docker Execution Engine (Isolated subprocess spawning)
- Real-time output streaming via WebSockets
"""

from .library import ScriptLibrary, Script, ScriptMetadata
from app.core.executor import Executor, ExecutionResult

__all__ = [
    "ScriptLibrary",
    "Script",
    "ScriptMetadata",
    "Executor",
    "ExecutionResult",
]
