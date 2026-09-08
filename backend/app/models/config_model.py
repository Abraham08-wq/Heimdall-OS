"""
config_model.py — Dynamic Configuration Table
Stores all values previously hardcoded in the frontend as static arrays.
Categories: device_types, simulation_types, offensive_tools, soc_playbooks
"""
from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.models.models import Base
import uuid


class ConfigEntry(Base):
    __tablename__ = "config_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category = Column(String(64), nullable=False, index=True)   # e.g. "device_types"
    key = Column(String(128), nullable=False, index=True)       # e.g. "server"
    label = Column(String(256), nullable=False)                 # e.g. "Server"
    description = Column(Text, nullable=True)
    value = Column(JSONB, nullable=True)                        # Arbitrary metadata JSON
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "id": str(self.id),
            "category": self.category,
            "key": self.key,
            "label": self.label,
            "description": self.description,
            "value": self.value,
            "is_active": self.is_active,
        }
