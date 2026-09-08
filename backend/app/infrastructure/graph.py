from neo4j import AsyncGraphDatabase
from app.core.config import settings
from app.core.logging import log


class GraphServiceDisabledError(RuntimeError):
    """Raised when a graph query is attempted but Neo4j is disabled or unavailable."""


class GraphDatabase:
    def __init__(self):
        self.driver = None

    async def connect(self):
        """Initializes the Neo4j driver with connection pooling."""
        if self.driver is not None:
            return

        try:
            self.driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                # Increase connection pool for concurrent AI agent queries
                max_connection_pool_size=50,
                connection_acquisition_timeout=30
            )
            # Verify connectivity immediately
            await self.driver.verify_connectivity()
            log.info("[GRAPH] Neo4j Connection Established Successfully.")
        except Exception as e:
            # Log the failure but do not raise: allow the application to start
            # in degraded mode and let callers attempt reconnection later.
            log.error(f"[CRITICAL] Neo4j Connection Failed: {e}")
            self.driver = None
            return

    async def close(self):
        """Gracefully closes the driver."""
        if self.driver:
            await self.driver.close()
            self.driver = None
            log.info("[GRAPH] Neo4j Connection Closed.")

    @staticmethod
    async def _collect_query_records(tx, query: str, params: dict | None = None):
        # Async transaction run must be awaited and iterated asynchronously.
        result = await tx.run(query, params or {})
        records = []
        async for record in result:
            records.append(record.data())
        return records

    async def execute_query(self, query: str, params: dict = None):
        """Executes a Cypher query with automatic reconnection check.

        Raises:
            GraphServiceDisabledError: If Neo4j is not available and cannot reconnect.
        """
        if not self.driver:
            # Attempt one reconnect before giving up.
            await self.connect()
        if not self.driver:
            # Driver is still None after reconnect attempt — raise a typed error
            # so service-layer callers can return graceful empty responses.
            raise GraphServiceDisabledError(
                "Neo4j is unavailable. Set ENABLE_GRAPH_DB=false to use the in-memory adapter."
            )

        mutation_keywords = ("CREATE", "MERGE", "DELETE", "SET", "REMOVE", "FOREACH", "DETACH")
        is_mutation = any(keyword in query.upper() for keyword in mutation_keywords)

        try:
            async with self.driver.session() as session:
                async def _runner(tx):
                    return await self._collect_query_records(tx, query, params or {})

                if is_mutation:
                    return await session.execute_write(_runner)

                return await session.execute_read(_runner)
        except Exception as e:
            log.error(f"[GRAPH] Query Execution Failed: {query[:50]}... | Error: {e}")
            raise

# Global instance
graph_db = GraphDatabase()