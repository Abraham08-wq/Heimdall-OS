import asyncio
import hashlib
from typing import Dict, Any, Tuple, List
from app.infrastructure.graph import graph_db

class NeuralDeMasking:
    """
    Fingerprints an attacker by linking disparate aliases and behavioral metadata
    into a single :ThreatActor node in the graph database.
    
    This class simulates using tools like Spiderfoot and Recon-ng.
    """

    async def _query_osint_sources(self, alias_value: str) -> Dict[str, Any]:
        """
        Simulates running OSINT tools like Spiderfoot or SocialBlade
        to find related accounts and metadata based on a username.
        """
        print(f"🕵️  [De-Masking] Running deep OSINT scan for alias: {alias_value}")
        await asyncio.sleep(2.5) # Simulate long-running scan

        # Mock results: find related email and a GitHub account
        if "hacker" in alias_value:
            return {
                "leaked_email": f"{alias_value}@proton.me",
                "related_profiles": {
                    "github": alias_value,
                    "twitter": f"{alias_value}_x",
                },
                "behavioral_keywords": ["exploit-dev", "crypto", "rust-lang"],
            }
        return {}

    def _generate_fingerprint(self, identifiers: List[str]) -> str:
        """
        Creates a stable, unique fingerprint for a threat actor based on a sorted
        list of their known identifiers (emails, usernames, etc.).
        """
        s = "".join(sorted(identifiers)).encode()
        return hashlib.sha256(s).hexdigest()

    async def link_aliases_to_threat_actor(self, primary_alias: Tuple[str, str], discovered_data: Dict[str, Any]):
        """
        Takes discovered data and merges it into the Neo4j graph, linking
        all aliases and metadata to a central :ThreatActor node.
        """
        primary_type, primary_value = primary_alias
        
        # 1. Collect all known identifiers to create a stable fingerprint
        all_identifiers = [primary_value]
        if "leaked_email" in discovered_data:
            all_identifiers.append(discovered_data["leaked_email"])
        if "related_profiles" in discovered_data:
            all_identifiers.extend(discovered_data["related_profiles"].values())
            
        fingerprint = self._generate_fingerprint(all_identifiers)
        
        print(f"🔗  [De-Masking] Linking identifiers to ThreatActor with fingerprint: {fingerprint[:12]}...")

        # 2. Merge the core ThreatActor node
        await graph_db.execute_query(
            "MERGE (ta:ThreatActor {fingerprint: $fingerprint}) SET ta.last_seen = timestamp()",
            {"fingerprint": fingerprint}
        )

        # 3. Link the primary alias
        await graph_db.execute_query(
            """
            MATCH (ta:ThreatActor {fingerprint: $fingerprint})
            MERGE (alias:Alias {type: $type, value: $value})
            MERGE (ta)-[:HAS_ALIAS]->(alias)
            """,
            {"fingerprint": fingerprint, "type": primary_type, "value": primary_value}
        )

        # 4. Link the discovered email
        if "leaked_email" in discovered_data:
            email = discovered_data["leaked_email"]
            await graph_db.execute_query(
                """
                MATCH (ta:ThreatActor {fingerprint: $fingerprint})
                MERGE (e:Email {address: $email})
                MERGE (ta)-[:HAS_EMAIL]->(e)
                """,
                {"fingerprint": fingerprint, "email": email}
            )

        # 5. Link other related profiles
        if "related_profiles" in discovered_data:
            for profile_type, profile_value in discovered_data["related_profiles"].items():
                await graph_db.execute_query(
                    """
                    MATCH (ta:ThreatActor {fingerprint: $fingerprint})
                    MERGE (alias:Alias {type: $type, value: $value})
                    MERGE (ta)-[:HAS_ALIAS]->(alias)
                    """,
                    {"fingerprint": fingerprint, "type": profile_type, "value": profile_value}
                )
        print("✅  [De-Masking] Graph updated with new identity links.")


    async def fingerprint_actor(self, alias: Tuple[str, str]):
        """
        High-level orchestration method to fingerprint and link a new alias.
        
        :param alias: A tuple containing the alias type and value (e.g., ("telegram", "hacker123")).
        """
        alias_type, alias_value = alias
        
        # 1. Gather intelligence from OSINT sources
        osint_data = await self._query_osint_sources(alias_value)
        
        if not osint_data:
            print(f"🤷  [De-Masking] No new intelligence found for {alias_value}.")
            return

        # 2. Link the discovered data in the graph
        await self.link_aliases_to_threat_actor(alias, osint_data)
        
        return self._generate_fingerprint([alias_value] + list(osint_data.get("related_profiles", {}).values()))


# --- Example Usage ---
async def main():
    # This requires the Neo4j container to be running.
    # We manually connect the graph_db for this standalone example.
    await graph_db.connect()

    demasker = NeuralDeMasking()
    
    print("\n--- Running Neural De-Masking Example ---")
    target_alias = ("telegram", "hacker123")
    
    fingerprint = await demasker.fingerprint_actor(target_alias)
    
    if fingerprint:
        print(f"\n✅ Dossier created for ThreatActor. Fingerprint: {fingerprint}")
        # You can now query Neo4j with this fingerprint
        # MATCH (ta:ThreatActor {fingerprint: "..."})-[:HAS_ALIAS]->(a) RETURN ta, a

    await graph_db.close()

if __name__ == "__main__":
    asyncio.run(main())
