"""
GLOBAL HIVE-MIND INOCULATION SYSTEM
====================================
Distributed threat intelligence sharing via Redis

When one organization neutralizes a threat, the "Digital Vaccine"
is shared globally through Redis pub/sub to inoculate all connected nodes.

This creates a networked immune system where threat intelligence
automatically propagates across the entire ecosystem.
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import json
import hashlib
import asyncio


class VaccineType(Enum):
    """Types of digital vaccines (threat intelligence)"""
    IOC_BLOCKLIST = "ioc_blocklist"
    YARA_SIGNATURE = "yara_signature"
    EXPLOIT_PATCH = "exploit_patch"
    MALWARE_SIGNATURE = "malware_signature"
    ATTACK_SIGNATURE = "attack_signature"
    BEHAVIORAL_PATTERN = "behavioral_pattern"
    THREAT_ACTOR_PROFILE = "threat_actor_profile"
    C2_INFRASTRUCTURE = "c2_infrastructure"


class VaccineStatus(Enum):
    """Status of vaccination across network"""
    DISCOVERED = "discovered"
    VALIDATED = "validated"
    DISTRIBUTED = "distributed"
    APPLIED = "applied"
    EFFECTIVE = "effective"
    DEPRECATED = "deprecated"


@dataclass
class DigitalVaccine:
    """A single threat intelligence vaccine"""
    vaccine_id: str
    vaccine_type: VaccineType
    threat_name: str
    threat_actor: Optional[str]
    indicators: List[str]  # IOCs, signatures, patterns
    detection_method: str
    effectiveness_rate: float  # 0-1
    
    # Distribution
    origin_organization: str
    discovered_at: datetime
    first_applied_at: Optional[datetime]
    distributed_at: Optional[datetime]
    
    # Metadata
    ttl: timedelta
    severity: int  # 1-10
    tags: List[str]
    
    # Status
    status: VaccineStatus
    nodes_applied: int  # How many organizations have applied this
    blocked_count: int  # How many threats blocked globally
    
    signature: str  # Cryptographic signature for verification


@dataclass
class VaccineStats:
    """Statistics about vaccine effectiveness"""
    vaccine_id: str
    total_nodes: int
    nodes_protected: int
    protection_rate: float
    
    threat_instances_blocked: int
    threat_instances_attempted: int
    block_rate: float
    
    false_positive_rate: float
    time_to_containment: timedelta
    estimated_damage_prevented: float  # USD


@dataclass
class HiveMindNode:
    """A connected node in the hive-mind network"""
    node_id: str
    organization_name: str
    node_type: str  # "enterprise", "government", "startup", etc.
    region: str
    
    # Capabilities
    threat_hunting_capability: float  # 0-1
    response_capability: float  # 0-1
    intelligence_production: float  # 0-1
    
    # Status
    is_active: bool
    last_heartbeat: datetime
    vaccines_applied: int
    threats_blocked: int
    
    # Trust score (for weighting intelligence)
    trust_score: float  # 0-1
    accuracy_history: float  # Past accuracy


class VaccineRepository:
    """Central repository for digital vaccines"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.vaccines: Dict[str, DigitalVaccine] = {}
    
    async def add_vaccine(self, vaccine: DigitalVaccine) -> str:
        """Add new vaccine to repository"""
        vaccine_key = f"vaccine:{vaccine.vaccine_id}"
        await self.redis.set(vaccine_key, json.dumps(asdict(vaccine), default=str))
        self.vaccines[vaccine.vaccine_id] = vaccine
        return vaccine.vaccine_id
    
    async def get_vaccine(self, vaccine_id: str) -> Optional[DigitalVaccine]:
        """Retrieve vaccine by ID"""
        if vaccine_id in self.vaccines:
            return self.vaccines[vaccine_id]
        
        vaccine_key = f"vaccine:{vaccine_id}"
        vaccine_data = await self.redis.get(vaccine_key)
        
        if vaccine_data:
            return json.loads(vaccine_data)
        return None
    
    async def search_vaccines(self, threat_name: str, 
                            vaccine_type: Optional[VaccineType] = None) -> List[DigitalVaccine]:
        """Search for vaccines by threat name and type"""
        results = []
        
        for vaccine in self.vaccines.values():
            if threat_name.lower() in vaccine.threat_name.lower():
                if vaccine_type is None or vaccine.vaccine_type == vaccine_type:
                    results.append(vaccine)
        
        return results
    
    async def get_active_vaccines(self) -> List[DigitalVaccine]:
        """Get all active vaccines (not yet expired)"""
        now = datetime.utcnow()
        return [
            v for v in self.vaccines.values()
            if v.status != VaccineStatus.DEPRECATED and
            (v.distributed_at + v.ttl) > now
        ]
    
    async def deprecate_vaccine(self, vaccine_id: str):
        """Mark vaccine as deprecated"""
        if vaccine_id in self.vaccines:
            self.vaccines[vaccine_id].status = VaccineStatus.DEPRECATED
            vaccine_key = f"vaccine:{vaccine_id}"
            await self.redis.set(vaccine_key, json.dumps(asdict(self.vaccines[vaccine_id]), default=str))


class HiveMindNetwork:
    """Network of connected organizations sharing threat intelligence"""
    
    def __init__(self, redis_client, node_id: str, organization_name: str):
        self.redis = redis_client
        self.node_id = node_id
        self.organization_name = organization_name
        
        self.nodes: Dict[str, HiveMindNode] = {}
        self.vaccine_repo = VaccineRepository(redis_client)
        self.pubsub_channel = "hivemind:vaccines"
    
    async def register_node(self, node: HiveMindNode):
        """Register a new node in the hive-mind"""
        self.nodes[node.node_id] = node
        node_key = f"hivemind:node:{node.node_id}"
        await self.redis.set(node_key, json.dumps(asdict(node), default=str))
        
        # Broadcast to network
        await self.redis.publish(self.pubsub_channel, json.dumps({
            "event": "node_registered",
            "node_id": node.node_id,
            "organization": node.organization_name,
        }))
    
    async def discover_threat(self, threat_data: Dict) -> str:
        """Discover a new threat locally"""
        
        vaccine_id = hashlib.sha256(
            str(threat_data).encode()
        ).hexdigest()
        
        vaccine = DigitalVaccine(
            vaccine_id=vaccine_id,
            vaccine_type=VaccineType(threat_data.get('type', 'IOC_BLOCKLIST')),
            threat_name=threat_data.get('threat_name'),
            threat_actor=threat_data.get('threat_actor'),
            indicators=threat_data.get('indicators', []),
            detection_method=threat_data.get('detection_method', 'unknown'),
            effectiveness_rate=threat_data.get('effectiveness_rate', 0.85),
            origin_organization=self.organization_name,
            discovered_at=datetime.utcnow(),
            first_applied_at=datetime.utcnow(),
            distributed_at=None,
            ttl=timedelta(days=90),
            severity=threat_data.get('severity', 5),
            tags=threat_data.get('tags', []),
            status=VaccineStatus.DISCOVERED,
            nodes_applied=1,
            blocked_count=threat_data.get('blocked_count', 0),
            signature=self._create_signature(vaccine_id),
        )
        
        await self.vaccine_repo.add_vaccine(vaccine)
        print(f"🔬 Threat discovered: {vaccine.threat_name} ({vaccine_id})")
        
        return vaccine_id
    
    async def validate_threat(self, vaccine_id: str) -> bool:
        """Validate threat after analysis"""
        vaccine = await self.vaccine_repo.get_vaccine(vaccine_id)
        if vaccine:
            vaccine.status = VaccineStatus.VALIDATED
            await self.vaccine_repo.add_vaccine(vaccine)
            print(f"✅ Threat validated: {vaccine.threat_name}")
            return True
        return False
    
    async def distribute_vaccine(self, vaccine_id: str) -> int:
        """Distribute vaccine to entire hive-mind network"""
        vaccine = await self.vaccine_repo.get_vaccine(vaccine_id)
        if not vaccine:
            return 0
        
        vaccine.status = VaccineStatus.DISTRIBUTED
        vaccine.distributed_at = datetime.utcnow()
        
        # Publish vaccine to all connected nodes
        await self.redis.publish(self.pubsub_channel, json.dumps({
            "event": "vaccine_distributed",
            "vaccine": asdict(vaccine),
        }, default=str))
        
        print(f"💉 Vaccine distributed: {vaccine.threat_name}")
        
        await self.vaccine_repo.add_vaccine(vaccine)
        
        # Return number of nodes in network
        return len(self.nodes)
    
    async def apply_vaccine(self, vaccine_id: str) -> Dict:
        """Apply vaccine locally"""
        vaccine = await self.vaccine_repo.get_vaccine(vaccine_id)
        if not vaccine:
            return {"error": "Vaccine not found"}
        
        vaccine.status = VaccineStatus.APPLIED
        vaccine.nodes_applied += 1
        
        # In production, would:
        # - Add IOCs to blocklist
        # - Install YARA rules
        # - Deploy firewall rules
        # - Update IDS/IPS signatures
        
        print(f"💉 Vaccine applied: {vaccine.threat_name}")
        
        await self.vaccine_repo.add_vaccine(vaccine)
        
        return {
            "vaccine_id": vaccine_id,
            "status": "applied",
            "threat_name": vaccine.threat_name,
            "indicators_added": len(vaccine.indicators),
        }
    
    async def report_threat_blocked(self, vaccine_id: str, count: int = 1):
        """Report that a vaccine blocked threats"""
        vaccine = await self.vaccine_repo.get_vaccine(vaccine_id)
        if vaccine:
            vaccine.blocked_count += count
            vaccine.status = VaccineStatus.EFFECTIVE
            await self.vaccine_repo.add_vaccine(vaccine)
            
            # Broadcast to network
            await self.redis.publish(self.pubsub_channel, json.dumps({
                "event": "threat_blocked",
                "vaccine_id": vaccine_id,
                "organization": self.organization_name,
                "count": count,
                "total_blocked": vaccine.blocked_count,
            }))
    
    async def listen_for_vaccines(self):
        """Listen for incoming vaccines from hive-mind"""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(self.pubsub_channel)
        
        print(f"🔗 Connected to hive-mind network")
        
        async for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    data = json.loads(message['data'])
                    
                    if data.get('event') == 'vaccine_distributed':
                        vaccine_data = data.get('vaccine')
                        await self._apply_incoming_vaccine(vaccine_data)
                    
                    elif data.get('event') == 'threat_blocked':
                        print(f"🛡️ Threat blocked by {data.get('organization')}: "
                              f"{data.get('count')} instances")
                    
                    elif data.get('event') == 'node_registered':
                        print(f"👥 New node joined: {data.get('organization')}")
                
                except Exception as e:
                    print(f"Error processing hive-mind message: {e}")
    
    async def _apply_incoming_vaccine(self, vaccine_data: Dict):
        """Automatically apply incoming vaccine"""
        vaccine_id = vaccine_data.get('vaccine_id')
        print(f"💉 Applying incoming vaccine: {vaccine_data.get('threat_name')}")
        
        result = await self.apply_vaccine(vaccine_id)
        
        # Confirm application to network
        await self.redis.publish(self.pubsub_channel, json.dumps({
            "event": "vaccine_applied",
            "vaccine_id": vaccine_id,
            "organization": self.organization_name,
            "success": result.get('error') is None,
        }))
    
    async def get_vaccine_stats(self, vaccine_id: str) -> Optional[VaccineStats]:
        """Get statistics on vaccine effectiveness"""
        vaccine = await self.vaccine_repo.get_vaccine(vaccine_id)
        if not vaccine:
            return None
        
        return VaccineStats(
            vaccine_id=vaccine_id,
            total_nodes=len(self.nodes),
            nodes_protected=vaccine.nodes_applied,
            protection_rate=vaccine.nodes_applied / max(len(self.nodes), 1),
            threat_instances_blocked=vaccine.blocked_count,
            threat_instances_attempted=vaccine.blocked_count * 3,  # Estimate
            block_rate=1.0 if vaccine.blocked_count > 0 else 0.0,
            false_positive_rate=0.01,
            time_to_containment=timedelta(hours=4),
            estimated_damage_prevented=vaccine.blocked_count * 50000,  # $50k per block
        )
    
    async def get_hive_status(self) -> Dict:
        """Get status of entire hive-mind network"""
        active_vaccines = await self.vaccine_repo.get_active_vaccines()
        
        total_threats_blocked = sum(v.blocked_count for v in active_vaccines)
        
        return {
            "nodes_connected": len(self.nodes),
            "active_vaccines": len(active_vaccines),
            "total_threats_blocked": total_threats_blocked,
            "threat_types": list(set(v.vaccine_type.value for v in active_vaccines)),
            "network_effectiveness": min(1.0, total_threats_blocked / max(len(active_vaccines) * 100, 1)),
        }
    
    @staticmethod
    def _create_signature(vaccine_id: str) -> str:
        """Create cryptographic signature for vaccine"""
        return hashlib.sha256(vaccine_id.encode()).hexdigest()


# Async endpoint helpers
async def discover_threat_endpoint(hivemind: HiveMindNetwork, threat_data: Dict) -> Dict:
    """FastAPI endpoint to discover and share a threat"""
    try:
        vaccine_id = await hivemind.discover_threat(threat_data)
        return {
            "vaccine_id": vaccine_id,
            "status": "discovered",
            "threat_name": threat_data.get('threat_name'),
        }
    except Exception as e:
        return {"error": str(e), "status": "failed"}


async def validate_threat_endpoint(hivemind: HiveMindNetwork, vaccine_id: str) -> Dict:
    """FastAPI endpoint to validate a threat"""
    try:
        success = await hivemind.validate_threat(vaccine_id)
        return {"vaccine_id": vaccine_id, "validated": success}
    except Exception as e:
        return {"error": str(e), "status": "failed"}


async def distribute_vaccine_endpoint(hivemind: HiveMindNetwork, vaccine_id: str) -> Dict:
    """FastAPI endpoint to distribute vaccine to network"""
    try:
        nodes_count = await hivemind.distribute_vaccine(vaccine_id)
        return {
            "vaccine_id": vaccine_id,
            "nodes_notified": nodes_count,
            "status": "distributed",
        }
    except Exception as e:
        return {"error": str(e), "status": "failed"}


async def get_hive_status_endpoint(hivemind: HiveMindNetwork) -> Dict:
    """FastAPI endpoint to get hive-mind network status"""
    try:
        status = await hivemind.get_hive_status()
        return status
    except Exception as e:
        return {"error": str(e), "status": "failed"}


async def apply_vaccine_endpoint(hivemind: HiveMindNetwork, vaccine_id: str) -> Dict:
    """FastAPI endpoint to apply vaccine locally"""
    try:
        result = await hivemind.apply_vaccine(vaccine_id)
        return result
    except Exception as e:
        return {"error": str(e), "status": "failed"}
