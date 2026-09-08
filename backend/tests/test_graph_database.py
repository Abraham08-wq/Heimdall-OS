import importlib
import os
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch


class _FakeNeo4jModule(types.ModuleType):
    class AsyncGraphDatabase:
        @staticmethod
        def driver(*args, **kwargs):
            raise AssertionError("driver should be patched in the test")


neo4j_stub = _FakeNeo4jModule("neo4j")
sys.modules.setdefault("neo4j", neo4j_stub)

loguru_stub = types.ModuleType("loguru")
loguru_stub.logger = MagicMock()
sys.modules.setdefault("loguru", loguru_stub)


def load_graph_module(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:password@postgres:5432/projectxy")
    monkeypatch.setenv("DATABASE_URL_SYNC", "postgresql://postgres:password@postgres:5432/projectxy")
    monkeypatch.setenv("FRONTEND_URL", "https://localhost")
    monkeypatch.setenv("JWT_SECRET_KEY", "abcdefghijklmnopqrstuvwxzy123456")
    monkeypatch.setenv("NEO4J_URI", "bolt://neo4j:7687")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "password")
    import sys

    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import app.infrastructure.graph as graph_module

    return importlib.reload(graph_module)


async def _run_execute_write_test(monkeypatch):
    graph_module = load_graph_module(monkeypatch)

    fake_session = MagicMock()
    fake_session.execute_write = AsyncMock(
        side_effect=lambda callback: callback(MagicMock(run=MagicMock(return_value=[MagicMock(data=lambda: {"ok": True})])))
    )
    fake_session.execute_read = AsyncMock(
        side_effect=lambda callback: callback(MagicMock(run=MagicMock(return_value=[MagicMock(data=lambda: {"ok": True})])))
    )
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock(return_value=None)

    fake_driver = MagicMock()
    fake_driver.session.return_value = fake_session
    fake_driver.verify_connectivity = AsyncMock()
    fake_driver.close = AsyncMock()

    class FakeAsyncGraphDatabase:
        @staticmethod
        def driver(*args, **kwargs):
            return fake_driver

    with patch.object(graph_module, "AsyncGraphDatabase", FakeAsyncGraphDatabase):
        graph = graph_module.GraphDatabase()
        await graph.connect()
        await graph.execute_query("MERGE (n:Test {id: $id}) RETURN n", {"id": 1})

    return fake_session


def test_execute_query_uses_execute_write_for_mutating_queries(monkeypatch):
    import asyncio

    fake_session = asyncio.run(_run_execute_write_test(monkeypatch))

    fake_session.execute_write.assert_awaited_once()
    fake_session.execute_read.assert_not_awaited()
