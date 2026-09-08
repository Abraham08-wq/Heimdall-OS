"""
Neural De-Masking (Spiderfoot & Recon-ng)
─────────────────────────────────────────
Fingerprints an attacker using Spiderfoot and Recon-ng.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class NeuralDeMasking:
    """
    Links disparate aliases into a single ThreatActor node.
    """

    def __init__(self):
        self._graph = {
            "nodes": [],
            "links": [],
        }
        self._actors = {}

    def _add_node(self, id, type):
        if not any(n['id'] == id for n in self._graph['nodes']):
            self._graph['nodes'].append({"id": id, "type": type})

    def _add_link(self, source, target):
        self._graph['links'].append({"source": source, "target": target})

    def _get_or_create_actor(self, alias: str) -> str:
        """Finds the ThreatActor for an alias, or creates a new one."""
        for actor, data in self._actors.items():
            if alias in data['aliases']:
                return actor

        new_actor_id = f"ThreatActor-{len(self._actors) + 1}"
        self._actors[new_actor_id] = {"aliases": {alias}}
        self._add_node(new_actor_id, "ThreatActor")
        self._add_node(alias, "alias")
        self._add_link(new_actor_id, alias)
        return new_actor_id

    def _link_alias(self, existing_alias: str, new_alias: str):
        """Links a new alias to an existing ThreatActor."""
        actor_id = self._get_or_create_actor(existing_alias)
        self._actors[actor_id]['aliases'].add(new_alias)
        self._add_node(new_alias, "alias")
        self._add_link(actor_id, new_alias)

    async def fingerprint(self, target: str) -> Dict[str, Any]:
        """
        Fingerprints the target using various OSINT tools.
        """
        logger.info(f"[NeuralDeMasking] Fingerprinting {target}...")

        # 1. Get or create the ThreatActor
        actor_id = self._get_or_create_actor(target)

        # 2. Simulate finding new aliases (in a real implementation, this would come from Spiderfoot/Recon-ng)
        if "john" in target.lower():
            self._link_alias(target, "johnny99")
            self._link_alias(target, "J-Dog")
        
        # 3. Return the de-masked identity
        return {
            "threat_actor_id": actor_id,
            "aliases": list(self._actors[actor_id]['aliases']),
            "graph": self._graph,
        }

neural_demasking = NeuralDeMasking()
