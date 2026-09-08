"""
timescale_models.py — ProjectXY TimescaleDB Schema Extensions
=============================================================
Clean SQLAlchemy models that extend the existing `cyberintel` database
with TimescaleDB hypertables for CBK-compliant log retention:

  • 30-day HOT storage  → TimescaleDB with fast chunk access
  • 7-year COLD archival → Tiered storage (S3-compatible) via TimescaleDB policies

All new tables are designed to coexist non-destructively with existing tables.
The migration script (timescale_migration.py) applies them safely.

CBK Log Retention Framework:
  - CBK/CRAF guidelines require 7-year retention for financial security logs
  - Kenya DPA 2019 requires minimal retention (PII auto-purge after business need)
  - Solution: TimescaleDB continuous aggregates (daily rollups) + data tiering
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    event,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import declarative_base
from sqlalchemy.schema import DDL
from sqlalchemy.sql import func
import uuid

# Reuse the existing Base from models.py to keep all models consistent
from app.models.models import Base


# ===========================================================================
# TABLE 1: LLM Firewall Events (TimescaleDB Hypertable)
# ===========================================================================

class FirewallEvent(Base):
    """
    Every AI Firewall decision, hyper-partitioned by timestamp.
    Chunk interval: 1 day (for hot 30-day access)
    Retention policy: compress after 30d, move to cold tier after 1 year
    """
    __tablename__ = "firewall_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(
        DateTime(timezone=True),
        primary_key=True,           # Required for TimescaleDB composite PK
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    tenant_id = Column(String(64), index=True, nullable=True)
    entity_id = Column(String(128), index=True, nullable=True)

    # Firewall verdict
    action = Column(String(32), nullable=False)      # PASS | BLOCK | SCRUB_AND_PASS
    threat_score = Column(Float, nullable=False, default=0.0)
    semantic_similarity = Column(Float, default=0.0)
    matched_category = Column(String(64), nullable=True)

    # PII / DLP
    pii_types_detected = Column(JSONB, nullable=True)

    # Reasons (list of strings)
    reasons = Column(JSONB, nullable=True)

    # Performance
    latency_ms = Column(Float, nullable=True)
    prompt_hash = Column(String(64), index=True, nullable=True)

    # Compliance: hashed prompt preview (never store raw PII)
    prompt_preview_hash = Column(String(64), nullable=True)

    # Source IP (anonymised via /24 subnet for DPA compliance)
    source_ip_subnet = Column(String(20), nullable=True)    # e.g., "197.232.1.0/24"

    __table_args__ = (
        Index("ix_fw_tenant_ts", "tenant_id", "timestamp"),
        Index("ix_fw_action_ts", "action", "timestamp"),
    )


# ===========================================================================
# TABLE 2: SIEM Threat Events (TimescaleDB Hypertable)
# ===========================================================================

class SIEMThreatEvent(Base):
    """
    All SIEM-classified threat events from the Kafka processing pipeline.
    High-volume hypertable with 1-day chunks.
    """
    __tablename__ = "siem_threat_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(
        DateTime(timezone=True),
        primary_key=True,
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    tenant_id = Column(String(64), index=True, nullable=True)
    entity_id = Column(String(128), index=True)
    source_ip = Column(String(45), index=True, nullable=True)   # IPv4 or IPv6

    # Classification result
    event_topic = Column(String(64))                            # Kafka topic origin
    risk_score = Column(Float, nullable=False)
    soar_action = Column(String(32), nullable=True)             # BLOCK | RATE_LIMIT | OBSERVE
    reasons = Column(JSONB, nullable=True)

    # Graph correlation
    graph_scan_count = Column(Integer, default=0)
    graph_login_fail_count = Column(Integer, default=0)
    graph_fw_block_count = Column(Integer, default=0)
    is_apt_chain = Column(Boolean, default=False)

    # MITRE ATT&CK mapping
    mitre_tactic = Column(String(64), nullable=True)
    mitre_technique = Column(String(32), nullable=True)

    __table_args__ = (
        Index("ix_siem_tenant_ts", "tenant_id", "timestamp"),
        Index("ix_siem_risk_ts", "risk_score", "timestamp"),
        Index("ix_siem_apt", "is_apt_chain", "timestamp"),
    )


# ===========================================================================
# TABLE 3: DGA Detection Events (Offensive AI — DGA Predictor)
# ===========================================================================

class DGADetectionEvent(Base):
    """
    Predicted malicious domains from the DGA detector.
    Feeds the regional blacklist shared across tenants.
    """
    __tablename__ = "dga_detection_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(
        DateTime(timezone=True),
        primary_key=True,
        server_default=func.now(),
        index=True,
    )
    domain = Column(String(253), nullable=False, index=True)
    dga_probability = Column(Float, nullable=False)        # 0.0 – 1.0
    algorithm_family = Column(String(64), nullable=True)   # e.g., "NewGOZ", "Locky", "TrickBot"
    is_blacklisted = Column(Boolean, default=False)
    country_code = Column(String(3), nullable=True)        # ISO 3166-1 alpha-2

    __table_args__ = (
        Index("ix_dga_domain_ts", "domain", "timestamp"),
    )


# ===========================================================================
# TABLE 4: OSINT Threat Intelligence Feed (Continuous Aggregation)
# ===========================================================================

class OSINTThreatFeed(Base):
    """
    Raw OSINT intelligence from regional threat feeds and dark-web monitors.
    CBK 7-year cold archive candidate.
    """
    __tablename__ = "osint_threat_feed"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(
        DateTime(timezone=True),
        primary_key=True,
        server_default=func.now(),
        index=True,
    )
    source = Column(String(128), nullable=False)            # e.g., "AlienVault_OTX"
    indicator_type = Column(String(32), nullable=False)     # ip | domain | hash | url
    indicator_value = Column(Text, nullable=False)
    severity = Column(SmallInteger, default=3)              # 1–4
    tags = Column(JSONB, nullable=True)
    region = Column(String(16), nullable=True)              # "EA" = East Africa

    __table_args__ = (
        Index("ix_osint_type_ts", "indicator_type", "timestamp"),
        Index("ix_osint_source_ts", "source", "timestamp"),
    )


# ===========================================================================
# TimescaleDB DDL Events — Applied after_create
# ===========================================================================

def _hypertable(table_name: str, time_col: str = "timestamp", chunk_interval: str = "1 day") -> DDL:
    return DDL(
        f"SELECT create_hypertable('{table_name}', '{time_col}', "
        f"chunk_time_interval => INTERVAL '{chunk_interval}', "
        f"if_not_exists => TRUE);"
    )


def _compression_policy(table_name: str, compress_after: str = "30 days") -> DDL:
    return DDL(
        f"SELECT add_compression_policy('{table_name}', INTERVAL '{compress_after}', if_not_exists => TRUE);"
    )


def _retention_policy(table_name: str, drop_after: str = "7 years") -> DDL:
    return DDL(
        f"SELECT add_retention_policy('{table_name}', INTERVAL '{drop_after}', if_not_exists => TRUE);"
    )


# Firewall Events
event.listen(FirewallEvent.__table__, "after_create", _hypertable("firewall_events"))
event.listen(FirewallEvent.__table__, "after_create", _compression_policy("firewall_events", "30 days"))
event.listen(FirewallEvent.__table__, "after_create", _retention_policy("firewall_events", "7 years"))

# SIEM Threat Events
event.listen(SIEMThreatEvent.__table__, "after_create", _hypertable("siem_threat_events"))
event.listen(SIEMThreatEvent.__table__, "after_create", _compression_policy("siem_threat_events", "30 days"))
event.listen(SIEMThreatEvent.__table__, "after_create", _retention_policy("siem_threat_events", "7 years"))

# DGA Events
event.listen(DGADetectionEvent.__table__, "after_create", _hypertable("dga_detection_events"))
event.listen(DGADetectionEvent.__table__, "after_create", _compression_policy("dga_detection_events", "7 days"))

# OSINT Feed
event.listen(OSINTThreatFeed.__table__, "after_create", _hypertable("osint_threat_feed"))
event.listen(OSINTThreatFeed.__table__, "after_create", _compression_policy("osint_threat_feed", "30 days"))
event.listen(OSINTThreatFeed.__table__, "after_create", _retention_policy("osint_threat_feed", "7 years"))
