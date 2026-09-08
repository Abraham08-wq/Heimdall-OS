"""
backend/app/infrastructure/graph_adapter.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NetworkX in-memory graph adapter — light-profile fallback for Neo4j.

Activated automatically by main.py when ENABLE_GRAPH_DB=false.

Interface contract:
    • connect() / close() — no-ops (in-memory)
    • execute_query(cypher, params) — translates a supported subset of Cypher
      into NetworkX operations on a shared DiGraph.

Supported Cypher patterns:
    MERGE (n:Label {prop: $val})
    MATCH  (a:Label {prop: $val})-[:REL]->(b:Label {prop: $val2}) RETURN ...
    Simple RETURN of node properties.

This adapter is NOT a full Cypher engine. It covers the patterns used by the
ProjectXY seed and intelligence service layers and returns empty lists for
anything it cannot parse, rather than raising.
"""
from __future__ import annotations

import logging
import re
from typing import Any

log = logging.getLogger(__name__)

try:
    import networkx as nx
    _NX_AVAILABLE = True
except ImportError:
    _NX_AVAILABLE = False
    log.warning(
        "[GRAPH-ADAPTER] networkx not installed. "
        "Run: pip install networkx   — all graph queries will return []."
    )


class NetworkXGraphAdapter:
    """
    Drop-in replacement for GraphDatabase when Neo4j is unavailable.
    Stores nodes and edges in an in-memory directed multigraph.
    """

    def __init__(self) -> None:
        self._graph: Any = nx.MultiDiGraph() if _NX_AVAILABLE else None
        log.info("[GRAPH] NetworkX in-memory adapter initialised (Neo4j disabled).")

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """No-op: graph is always 'connected' (in-memory)."""
        log.debug("[GRAPH-ADAPTER] connect() called (no-op for in-memory adapter).")

    async def close(self) -> None:
        """No-op: nothing to tear down."""
        log.debug("[GRAPH-ADAPTER] close() called (no-op for in-memory adapter).")

    # ── Query engine ───────────────────────────────────────────────────────────

    async def execute_query(self, query: str, params: dict = None) -> list[dict]:
        """
        Translate a limited subset of Cypher into NetworkX operations.
        Returns [] for unrecognised patterns rather than raising.
        """
        if not _NX_AVAILABLE or self._graph is None:
            return []

        params = params or {}
        q = query.strip()

        try:
            if self._is_merge_node(q):
                return self._handle_merge_node(q, params)
            if self._is_merge_relationship(q):
                return self._handle_merge_relationship(q, params)
            if self._is_match_return(q):
                return self._handle_match_return(q, params)
        except Exception as exc:
            log.warning(f"[GRAPH-ADAPTER] Query parse error — returning []: {exc}\nQuery: {q[:120]}")

        return []

    # ── Pattern detectors ──────────────────────────────────────────────────────

    @staticmethod
    def _is_merge_node(q: str) -> bool:
        return bool(re.search(r"^\s*MERGE\s*\(\s*\w+\s*:", q, re.IGNORECASE)
                    and "]->" not in q and "-[" not in q)

    @staticmethod
    def _is_merge_relationship(q: str) -> bool:
        return bool(re.search(r"MERGE\s*\(\w+\)-\[:\w+\]->\(\w+\)", q, re.IGNORECASE)
                    or (re.search(r"MATCH\s*\(.+\)\s*WITH", q, re.IGNORECASE)
                        and re.search(r"MERGE\s*\(\w+\)-\[:\w+\]->\(\w+\)", q, re.IGNORECASE)))

    @staticmethod
    def _is_match_return(q: str) -> bool:
        return bool(re.search(r"MATCH\b", q, re.IGNORECASE)
                    and re.search(r"RETURN\b", q, re.IGNORECASE))

    # ── Handlers ───────────────────────────────────────────────────────────────

    def _handle_merge_node(self, q: str, params: dict) -> list[dict]:
        """
        Handle: MERGE (alias:Label {key: $param}) SET alias.x = $y
        Creates or updates the node in the in-memory graph.
        """
        # Extract label and property dict
        m = re.search(r"MERGE\s*\(\s*\w+\s*:\s*(\w+)\s*\{([^}]+)\}\s*\)", q, re.IGNORECASE)
        if not m:
            return []

        label = m.group(1)
        props = self._parse_props(m.group(2), params)

        # Resolve primary key (first property)
        node_id = self._node_id(label, props)

        if self._graph.has_node(node_id):
            # Merge: update existing attributes
            self._graph.nodes[node_id].update(props)
        else:
            self._graph.add_node(node_id, label=label, **props)

        # Handle SET clause
        set_m = re.search(r"SET\s+(.+?)(?:$|RETURN)", q, re.IGNORECASE | re.DOTALL)
        if set_m:
            set_props = self._parse_set_clause(set_m.group(1), params)
            self._graph.nodes[node_id].update(set_props)

        log.debug(f"[GRAPH-ADAPTER] MERGE node: {node_id} ({label}) props={props}")
        return []

    def _handle_merge_relationship(self, q: str, params: dict) -> list[dict]:
        """
        Handle patterns like:
            MERGE (c:CVE {id: $cve_id})
            WITH c
            MATCH (a:ThreatActor {name: $actor_name})
            MERGE (a)-[:USES]->(c)
        """
        # Extract all MERGE node patterns
        node_patterns = re.findall(
            r"MERGE\s*\(\s*(\w+)\s*:\s*(\w+)\s*\{([^}]+)\}\s*\)", q, re.IGNORECASE
        )
        nodes: dict[str, str] = {}  # alias -> node_id

        for alias, label, raw_props in node_patterns:
            props = self._parse_props(raw_props, params)
            nid = self._node_id(label, props)
            if not self._graph.has_node(nid):
                self._graph.add_node(nid, label=label, **props)
            else:
                self._graph.nodes[nid].update(props)
            nodes[alias] = nid

        # Extract MATCH node patterns too (for the anchor side)
        match_patterns = re.findall(
            r"MATCH\s*\(\s*(\w+)\s*:\s*(\w+)\s*\{([^}]+)\}\s*\)", q, re.IGNORECASE
        )
        for alias, label, raw_props in match_patterns:
            props = self._parse_props(raw_props, params)
            nid = self._node_id(label, props)
            if self._graph.has_node(nid):
                nodes[alias] = nid

        # Extract relationship: (alias1)-[:REL]->(alias2)
        rel_m = re.search(
            r"\(\s*(\w+)\s*\)-\s*\[:\s*(\w+)\s*\]->\s*\(\s*(\w+)\s*\)", q, re.IGNORECASE
        )
        if rel_m:
            src_alias, rel_type, dst_alias = rel_m.group(1), rel_m.group(2), rel_m.group(3)
            src_id = nodes.get(src_alias)
            dst_id = nodes.get(dst_alias)
            if src_id and dst_id:
                if not self._graph.has_edge(src_id, dst_id, key=rel_type):
                    self._graph.add_edge(src_id, dst_id, key=rel_type, type=rel_type)
                    log.debug(f"[GRAPH-ADAPTER] MERGE edge: {src_id} -[{rel_type}]-> {dst_id}")

        return []

    def _handle_match_return(self, q: str, params: dict) -> list[dict]:
        """
        Handle simple MATCH ... RETURN queries. Returns node attribute dicts.
        """
        m = re.search(r"MATCH\s*\(\s*(\w+)\s*:\s*(\w+)\s*(?:\{([^}]*)\})?\s*\)", q, re.IGNORECASE)
        if not m:
            return [dict(self._graph.nodes[n]) for n in self._graph.nodes]

        label = m.group(2)
        raw_props = m.group(3) or ""
        filter_props = self._parse_props(raw_props, params) if raw_props.strip() else {}

        results = []
        for node_id, attrs in self._graph.nodes(data=True):
            if attrs.get("label") != label:
                continue
            if all(attrs.get(k) == v for k, v in filter_props.items()):
                results.append(dict(attrs))

        return results

    # ── Utilities ──────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_props(raw: str, params: dict) -> dict:
        """Parse `key: $param` or `key: 'literal'` pairs into a Python dict."""
        result = {}
        for part in raw.split(","):
            part = part.strip()
            if not part or ":" not in part:
                continue
            key, _, val_raw = part.partition(":")
            key = key.strip()
            val_raw = val_raw.strip()
            if val_raw.startswith("$"):
                result[key] = params.get(val_raw[1:], None)
            else:
                result[key] = val_raw.strip("'\"")
        return result

    @staticmethod
    def _parse_set_clause(raw: str, params: dict) -> dict:
        """Parse `alias.prop = $val` SET assignments."""
        result = {}
        for part in raw.split(","):
            part = part.strip()
            if "=" not in part:
                continue
            lhs, _, rhs = part.partition("=")
            # lhs may be `alias.prop` or just `prop`
            prop = lhs.strip().split(".")[-1]
            val_raw = rhs.strip()
            if val_raw.startswith("$"):
                result[prop] = params.get(val_raw[1:], None)
            else:
                result[prop] = val_raw.strip("'\"")
        return result

    @staticmethod
    def _node_id(label: str, props: dict) -> str:
        """Generate a stable node ID from label + first property value."""
        if props:
            first_val = next(iter(props.values()))
            return f"{label}:{first_val}"
        return label
