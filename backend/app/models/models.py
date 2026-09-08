from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Float, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, index=True, unique=True)
    domain = Column(String, unique=True, index=True)
    subscription_tier = Column(String, default="starter") # starter, professional, enterprise
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Add back_populates after defining User
    users = relationship("User", back_populates="tenant")
    nodes = relationship("ExecutionNode", back_populates="tenant")

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=True) # Added for multi-tenancy
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    role = Column(String, default="analyst")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tenant = relationship("Tenant", back_populates="users")

class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), unique=True)
    stripe_customer_id = Column(String, index=True)
    stripe_subscription_id = Column(String, index=True)
    status = Column(String) # active, past_due, canceled
    current_period_end = Column(DateTime(timezone=True))

class ExecutionNode(Base):
    __tablename__ = "execution_nodes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=False)
    name = Column(String, index=True)
    api_key_hash = Column(String, unique=True, index=True)
    is_online = Column(Boolean, default=False)
    last_ping = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tenant = relationship("Tenant", back_populates="nodes")

class EntityDB(Base):
    __tablename__ = "entities"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=True) # Added for multi-tenancy
    canonical_name = Column(String, index=True)
    type = Column(String, index=True)  # Added index
    risk_score = Column(Integer, default=0, index=True)  # Added index
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    attributes = relationship("AttributeDB", back_populates="entity")

class AttributeDB(Base):
    __tablename__ = "attributes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), index=True) # Added index
    type = Column(String, index=True) # Added index
    value = Column(Text) # App-layer encryption recommended
    value_hash = Column(String, index=True)
    source = Column(String, index=True) # Added index
    confidence = Column(Float)
    last_seen = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    entity = relationship("EntityDB", back_populates="attributes")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    # TimescaleDB requires the partition column (timestamp) to be part of the primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), primary_key=True, server_default=func.now(), index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=True) # Added for partitioning
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    action = Column(String, index=True) 
    resource_type = Column(String)
    resource_id = Column(UUID(as_uuid=True), index=True) 
    metadata_ = Column("metadata", JSONB)
    
    # WORM / Immutable Ledger Fields
    hash = Column(String, index=True) # SHA-256(prev_hash + actor + action + timestamp)
    previous_hash = Column(String, index=True)
    signature = Column(String) # Digital signature (e.g., Ed25519) for non-repudiation

class Device(Base):
    __tablename__ = "devices"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Core identification
    name = Column(String, index=True)           # friendly display name (legacy field)
    hostname = Column(String, index=True)        # FQDN or short hostname
    ip = Column(String, index=True)              # primary IPv4/IPv6
    mac = Column(String, index=True, nullable=True)

    # Categorisation
    type = Column(String, index=True)            # Server | Workstation | Network | IoT | Mobile | OT/ICS | Cloud
    os = Column(String, nullable=True)           # OS name + version e.g. "Ubuntu 22.04 LTS"
    department = Column(String, nullable=True)
    tags = Column(JSONB, nullable=True)          # ["finance", "critical"]

    # Posture / risk
    risk_score = Column(Integer, default=0, index=True)
    status = Column(String, default="online", index=True)  # online | offline | quarantined

    # Discovery data (stored as JSONB for flexibility)
    ports = Column(JSONB, nullable=True)          # [22, 80, 443]
    services = Column(JSONB, nullable=True)       # ["sshd 8.9", "nginx 1.23"]
    cves = Column(JSONB, nullable=True)           # ["CVE-2023-38408"]

    # Geo (kept for compatibility with geofence / OmniProbe)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    accuracy_radius = Column(Float, nullable=True)

    last_seen = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    active_trace = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship to Geofences
    geofences = relationship("Geofence", back_populates="device")


class Geofence(Base):
    __tablename__ = "geofences"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id"))
    center_latitude = Column(Float, nullable=False)
    center_longitude = Column(Float, nullable=False)
    radius_meters = Column(Float, default=1000.0)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    device = relationship("Device", back_populates="geofences")

class IntelligenceReport(Base):
    __tablename__ = "intelligence_reports"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target = Column(String, index=True)
    source = Column(String, index=True)
    data = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Loot(Base):
    __tablename__ = "loot"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=True)
    operator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=True)
    source = Column(String, index=True, nullable=True) # E.g., IP address, hostname, or API hook
    loot_type = Column(String, index=True) # e.g., 'AWS_KEY', 'PASSWORD', 'PRIVATE_KEY'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# TimescaleDB Hypertable DDL Triggers
from sqlalchemy import event
from sqlalchemy.schema import DDL

# Trigger to create a TimescaleDB hypertable partitioned by time and tenant_id
event.listen(
    AuditLog.__table__,
    "after_create",
    DDL(
        "SELECT create_hypertable('audit_logs', 'timestamp', 'tenant_id', 4, if_not_exists => TRUE);"
    )
)
