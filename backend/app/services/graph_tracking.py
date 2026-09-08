from app.infrastructure.graph import graph_db
from app.schemas.telemetry import HoneypotTelemetryEvent

class GraphTrackingService:
    @staticmethod
    async def ingest_honeypot_telemetry(event: HoneypotTelemetryEvent):
        """
        Maps adversarial infrastructure from our external honeypots into the Neo4j graph.
        Creates HostileIP nodes, targets, and interaction edges.
        """
        query = """
        // 1. Map the Attacker IP
        MERGE (attacker:IPAddress {ip: $attacker_ip})
        SET attacker.type = 'Hostile',
            attacker.last_seen = $timestamp,
            attacker.country = $country,
            attacker.city = $city
            
        // 2. Map their ASN (if available) to group infrastructure
        WITH attacker
        WHERE $asn IS NOT NULL
        MERGE (asn:AutonomousSystem {number: $asn})
        SET asn.org = $org
        MERGE (attacker)-[:ROUTED_THROUGH]->(asn)
        
        // 3. Map our Honeypot (The sensor)
        WITH attacker
        MERGE (sensor:Honeypot {name: $honeypot_name})
        SET sensor.type = 'Sensor',
            sensor.zone = 'External'

        // 4. Create the Interaction Edge (The Attack)
        MERGE (attacker)-[attack:TARGETED {
            port: $target_port,
            protocol: $protocol,
            interaction: $interaction_type
        }]->(sensor)
        SET attack.timestamp = $timestamp,
            attack.details = $details
            
        // 5. Update Threat Scores dynamically
        SET attacker.risk_score = COALESCE(attacker.risk_score, 0) + 10
        """
        
        await graph_db.execute_query(
            query,
            {
                "attacker_ip": str(event.attacker_ip),
                "timestamp": event.timestamp.isoformat(),
                "country": event.attacker_geo.country_code if event.attacker_geo else None,
                "city": event.attacker_geo.city if event.attacker_geo else None,
                "asn": event.attacker_geo.asn if event.attacker_geo else None,
                "org": event.attacker_geo.org if event.attacker_geo else None,
                "honeypot_name": event.honeypot_name,
                "target_port": event.target_port,
                "protocol": event.protocol,
                "interaction_type": event.interaction_type,
                "details": str(event.details) # Serialize dict for neo4j properties
            }
        )
