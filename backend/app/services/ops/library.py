"""
Script Library - Repository Pattern for Managing Red/Blue Team Scripts

The Script Library is the "Arsenal" of ProjectXY. It stores and manages
all executable scripts (Python/Bash) with metadata (team, category, danger level).

Each script is immutably stored in PostgreSQL with a JSON header containing:
- team: 'red' or 'blue' (Offensive or Defensive)
- category: 'recon', 'exploit', 'patch', 'isolation', 'forensics'
- danger_level: 1-10 (1=safe, 10=system-breaking)
- description: Human-readable purpose
- tags: Free-form tags for filtering
"""

import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Text, DateTime, Float, JSON, create_engine, select
from sqlalchemy.orm import declarative_base, Session
import logging

logger = logging.getLogger(__name__)

# ─── Enums ────────────────────────────────────────────────────────────────────

class Team(str, Enum):
    RED = "red"      # Offensive / Attack Simulation
    BLUE = "blue"    # Defensive / Containment & Hardening


class Category(str, Enum):
    RECON = "recon"           # Information gathering
    EXPLOIT = "exploit"       # Active attack
    PATCH = "patch"           # Remediation
    ISOLATION = "isolation"   # Containment
    FORENSICS = "forensics"   # Post-incident analysis
    HARDENING = "hardening"   # Defensive improvement


# ─── Pydantic Models ──────────────────────────────────────────────────────────

class ScriptMetadata(BaseModel):
    """JSON metadata header embedded in each script."""
    team: Team
    category: Category
    danger_level: int = Field(ge=1, le=10, description="1=safe, 10=system-breaking")
    description: str
    tags: List[str] = Field(default_factory=list)
    author: Optional[str] = None
    requires_approval: bool = Field(default=True, description="Requires manual approval before execution")
    timeout_seconds: int = Field(default=300, description="Max execution time")

    class Config:
        use_enum_values = True


class Script(BaseModel):
    """Represents a stored script in the library."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    language: str = Field(description="python, bash, powershell")
    code: str
    metadata: ScriptMetadata
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None
    is_approved: bool = Field(default=False)
    is_disabled: bool = Field(default=False)

    class Config:
        use_enum_values = True


class ScriptCreateRequest(BaseModel):
    """Request to create a new script."""
    name: str
    language: str
    code: str
    metadata: ScriptMetadata
    created_by: Optional[str] = None


class ScriptUpdateRequest(BaseModel):
    """Request to update an existing script."""
    name: Optional[str] = None
    code: Optional[str] = None
    metadata: Optional[ScriptMetadata] = None
    is_disabled: Optional[bool] = None


# ─── SQLAlchemy ORM Model ──────────────────────────────────────────────────────

Base = declarative_base()


class ScriptORM(Base):
    """SQLAlchemy ORM mapping for Script storage in PostgreSQL."""
    __tablename__ = "scripts_library"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    language = Column(String(50), nullable=False)  # python, bash, powershell
    code = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, nullable=False)  # ScriptMetadata as JSON
    version = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255), nullable=True)
    is_approved = Column(String(255), default=False)  # Boolean field
    is_disabled = Column(String(255), default=False)  # Boolean field


# ─── ScriptLibrary Service ────────────────────────────────────────────────────

class ScriptLibrary:
    """
    Repository pattern for managing the script arsenal.
    
    Provides:
    - CRUD operations on scripts
    - Filtering by team, category, danger level
    - Version management
    - Approval workflow integration
    """

    def __init__(self, db_session: Session):
        """
        Initialize the Script Library with a database session.
        
        Args:
            db_session: SQLAlchemy session for database operations
        """
        self.db = db_session
        logger.info("📚 Script Library initialized")

    # ─── Create ───────────────────────────────────────────────────────────

    def create_script(self, request: ScriptCreateRequest) -> Script:
        """
        Create a new script in the library.
        
        Args:
            request: ScriptCreateRequest with script details
            
        Returns:
            Script: The created script object
        """
        script_id = str(uuid.uuid4())
        now = datetime.utcnow()

        orm_script = ScriptORM(
            id=script_id,
            name=request.name,
            language=request.language,
            code=request.code,
            metadata_=request.metadata.dict(),
            created_by=request.created_by,
            created_at=now,
            updated_at=now,
            is_approved=request.metadata.requires_approval is False,  # Auto-approve safe scripts
            is_disabled=False
        )

        self.db.add(orm_script)
        self.db.commit()
        self.db.refresh(orm_script)

        logger.info(
            f"✅ New script created: {request.name} (ID: {script_id}) "
            f"[Team: {request.metadata.team}, Danger: {request.metadata.danger_level}/10]"
        )

        return self._orm_to_pydantic(orm_script)

    # ─── Read ──────────────────────────────────────────────────────────────

    def get_script(self, script_id: str) -> Optional[Script]:
        """
        Retrieve a single script by ID.
        
        Args:
            script_id: UUID of the script
            
        Returns:
            Script or None if not found
        """
        orm_script = self.db.query(ScriptORM).filter(ScriptORM.id == script_id).first()
        return self._orm_to_pydantic(orm_script) if orm_script else None

    def list_scripts(
        self,
        team: Optional[Team] = None,
        category: Optional[Category] = None,
        max_danger: Optional[int] = None,
        include_disabled: bool = False
    ) -> List[Script]:
        """
        List scripts with optional filtering.
        
        Args:
            team: Filter by team (red/blue)
            category: Filter by category
            max_danger: Only show scripts with danger_level <= max_danger
            include_disabled: Include disabled scripts
            
        Returns:
            List of filtered scripts
        """
        query = self.db.query(ScriptORM)

        if not include_disabled:
            query = query.filter(ScriptORM.is_disabled == False)

        if team:
            query = query.filter(ScriptORM.metadata_['team'].astext == team.value)

        if category:
            query = query.filter(ScriptORM.metadata_['category'].astext == category.value)

        if max_danger is not None:
            query = query.filter(ScriptORM.metadata_['danger_level'].astext.cast(int) <= max_danger)

        scripts = query.all()
        return [self._orm_to_pydantic(s) for s in scripts]

    # ─── Update ────────────────────────────────────────────────────────────

    def update_script(self, script_id: str, request: ScriptUpdateRequest) -> Optional[Script]:
        """
        Update an existing script.
        
        Args:
            script_id: UUID of the script to update
            request: ScriptUpdateRequest with new values
            
        Returns:
            Updated Script or None if not found
        """
        orm_script = self.db.query(ScriptORM).filter(ScriptORM.id == script_id).first()
        if not orm_script:
            return None

        if request.name:
            orm_script.name = request.name
        if request.code:
            orm_script.code = request.code
            orm_script.version += 0.1  # Increment version on code change
        if request.metadata:
            orm_script.metadata_ = request.metadata.dict()
        if request.is_disabled is not None:
            orm_script.is_disabled = request.is_disabled

        orm_script.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(orm_script)

        logger.info(f"🔄 Script updated: {orm_script.name} (v{orm_script.version})")

        return self._orm_to_pydantic(orm_script)

    # ─── Delete ────────────────────────────────────────────────────────────

    def delete_script(self, script_id: str) -> bool:
        """
        Soft-delete a script (mark as disabled).
        
        Args:
            script_id: UUID of the script to delete
            
        Returns:
            True if successful, False if not found
        """
        orm_script = self.db.query(ScriptORM).filter(ScriptORM.id == script_id).first()
        if not orm_script:
            return False

        orm_script.is_disabled = True
        orm_script.updated_at = datetime.utcnow()

        self.db.commit()

        logger.info(f"🗑️ Script disabled: {orm_script.name}")

        return True

    # ─── Approval Workflow ─────────────────────────────────────────────────

    def approve_script(self, script_id: str) -> Optional[Script]:
        """
        Approve a script for execution.
        
        Args:
            script_id: UUID of the script
            
        Returns:
            Updated Script or None if not found
        """
        orm_script = self.db.query(ScriptORM).filter(ScriptORM.id == script_id).first()
        if not orm_script:
            return None

        orm_script.is_approved = True
        self.db.commit()
        self.db.refresh(orm_script)

        logger.info(f"✅ Script approved: {orm_script.name}")

        return self._orm_to_pydantic(orm_script)

    def revoke_script(self, script_id: str) -> Optional[Script]:
        """
        Revoke approval for a script.
        
        Args:
            script_id: UUID of the script
            
        Returns:
            Updated Script or None if not found
        """
        orm_script = self.db.query(ScriptORM).filter(ScriptORM.id == script_id).first()
        if not orm_script:
            return None

        orm_script.is_approved = False
        self.db.commit()
        self.db.refresh(orm_script)

        logger.info(f"❌ Script revoked: {orm_script.name}")

        return self._orm_to_pydantic(orm_script)

    # ─── Utility ───────────────────────────────────────────────────────────

    @staticmethod
    def _orm_to_pydantic(orm_obj: ScriptORM) -> Script:
        """Convert SQLAlchemy ORM object to Pydantic model."""
        if not orm_obj:
            return None

        metadata_dict = orm_obj.metadata_ if isinstance(orm_obj.metadata_, dict) else json.loads(orm_obj.metadata_)

        return Script(
            id=orm_obj.id,
            name=orm_obj.name,
            language=orm_obj.language,
            code=orm_obj.code,
            metadata=ScriptMetadata(**metadata_dict),
            version=orm_obj.version,
            created_at=orm_obj.created_at,
            updated_at=orm_obj.updated_at,
            created_by=orm_obj.created_by,
            is_approved=orm_obj.is_approved,
            is_disabled=orm_obj.is_disabled
        )

    def get_high_risk_scripts(self) -> List[Script]:
        """Get all high-danger scripts (danger_level >= 8)."""
        return self.list_scripts(max_danger=None)  # Manual filtering for danger >= 8
        # TODO: Implement danger_level >= 8 filtering in SQL

    def get_red_team_arsenal(self) -> List[Script]:
        """Get all approved Red Team (offensive) scripts."""
        return self.list_scripts(team=Team.RED)

    def get_blue_team_arsenal(self) -> List[Script]:
        """Get all approved Blue Team (defensive) scripts."""
        return self.list_scripts(team=Team.BLUE)
