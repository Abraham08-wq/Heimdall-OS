// 1. Constraints (Ensure integrity)
CREATE CONSTRAINT person_id_unique IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT org_id_unique IF NOT EXISTS FOR (o:Organization) REQUIRE o.id IS UNIQUE;
CREATE CONSTRAINT email_addr_unique IF NOT EXISTS FOR (e:Email) REQUIRE e.address IS UNIQUE;
CREATE CONSTRAINT domain_name_unique IF NOT EXISTS FOR (d:Domain) REQUIRE d.name IS UNIQUE;
CREATE CONSTRAINT ip_addr_unique IF NOT EXISTS FOR (i:IP) REQUIRE i.address IS UNIQUE;

// 2. Indexes (Speed up lookups)
CREATE INDEX person_name_index IF NOT EXISTS FOR (p:Person) ON (p.name);
CREATE INDEX email_address_index IF NOT EXISTS FOR (e:Email) ON (e.address);

/*
3. Node & Relationship Types

Nodes:
(:Person {id, name, risk_score})
(:Organization {id, name})
(:Email {address, hash})
(:Phone {number, hash})
(:Domain {name, registrar})
(:IP {address, geolocation})

Relationships:
(Person)-[:OWNS {confidence, source}]->(Email)
(Person)-[:WORKS_AT]->(Organization)
(Organization)-[:HOSTS_AT]->(IP)
(Domain)-[:RESOLVES_TO]->(IP)
(Person)-[:ASSOCIATED_WITH {reason}]->(Person)
*/

// 4. Example Investigation Queries

// Q1: Find all emails linked to a high-risk person
// MATCH (p:Person {risk_score: 'HIGH'})-[:OWNS]->(e:Email) RETURN p.name, e.address

// Q2: Shortest Path between two suspects
// MATCH path = shortestPath((p1:Person {name: 'John'})-[*]-(p2:Person {name: 'Jane'})) RETURN path

// Q3: Find "Bridge" nodes (Entities connecting two disparate groups)
// MATCH (n) WHERE size((n)--()) > 10 RETURN n, size((n)--()) AS connectivity ORDER BY connectivity DESC LIMIT 10

// 5. ProjectXY Omni-Graph Cyber Nodes (The Synapse)

// Constraints
CREATE CONSTRAINT honeypot_name_unique IF NOT EXISTS FOR (h:Honeypot) REQUIRE h.name IS UNIQUE;
CREATE CONSTRAINT digital_twin_id_unique IF NOT EXISTS FOR (d:DigitalTwin) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT asn_number_unique IF NOT EXISTS FOR (a:AutonomousSystem) REQUIRE a.number IS UNIQUE;
CREATE CONSTRAINT ipaddress_ip_unique IF NOT EXISTS FOR (i:IPAddress) REQUIRE i.ip IS UNIQUE;

// Indexes
CREATE INDEX attacker_ip_index IF NOT EXISTS FOR (i:IPAddress) ON (i.ip);
CREATE INDEX attacker_risk_index IF NOT EXISTS FOR (i:IPAddress) ON (i.risk_score);
CREATE INDEX interaction_timestamp_index IF NOT EXISTS FOR ()-[r:TARGETED]-() ON (r.timestamp);

/*
Omni-Graph Nodes:
(:IPAddress {ip, type, last_seen, country, city, risk_score})
(:AutonomousSystem {number, org})
(:Honeypot {name, type})
(:InternalAsset {id, hostname})
(:DigitalTwin {id, source_asset, zone})

Omni-Graph Relational Flow (The Aegis):
(IPAddress)-[:ROUTED_THROUGH]->(AutonomousSystem)
(IPAddress)-[:TARGETED {port, protocol, interaction, timestamp}]->(Honeypot)
(IPAddress)-[:REROUTED_TO {timestamp}]->(DigitalTwin)
*/
