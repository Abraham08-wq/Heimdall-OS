"""
Digital Twin Snapshots Engine (Phase 3C)

System state capture and recovery mechanism for safe execution of risky operations.
Creates point-in-time snapshots of database state, file system, and memory before
executing high-risk operations, enabling rollback if needed.

Key Features:
- Database snapshots (PostgreSQL point-in-time recovery)
- File system state versioning (copy-on-write snapshots)
- Memory dump capture for process state recovery
- Transactional execution with automatic rollback
- Snapshot comparison and diff analysis
- Recovery point management and cleanup
- Forensic replay of execution states
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import hashlib
import logging
import shutil
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================================
# TYPES & DATA MODELS
# ============================================================================

class SnapshotType(str, Enum):
    """Types of system snapshots"""
    DATABASE = "database"
    FILESYSTEM = "filesystem"
    MEMORY = "memory"
    APPLICATION = "application"
    FULL = "full"


class RecoveryStrategy(str, Enum):
    """How to handle recovery if execution fails"""
    AUTOMATIC_ROLLBACK = "automatic_rollback"
    MANUAL_REVIEW = "manual_review"
    SNAPSHOT_ONLY = "snapshot_only"
    POINT_IN_TIME = "point_in_time"


@dataclass
class SnapshotMetadata:
    """Metadata about a captured snapshot"""
    snapshot_id: str
    execution_id: str
    snapshot_type: SnapshotType
    created_at: datetime
    created_by: str
    description: str
    risk_level: int  # 1-10 (why snapshot was created)
    size_bytes: int
    checksum: str
    recovery_strategy: RecoveryStrategy
    is_compressed: bool = False
    retention_days: int = 7
    tags: Dict[str, str] = field(default_factory=dict)
    related_snapshots: List[str] = field(default_factory=list)


@dataclass
class SystemSnapshot:
    """A complete system state snapshot"""
    metadata: SnapshotMetadata
    database_state: Optional[Dict[str, Any]] = None
    filesystem_state: Optional[Dict[str, Any]] = None
    memory_state: Optional[Dict[str, Any]] = None
    application_state: Optional[Dict[str, Any]] = None
    storage_path: Optional[str] = None
    restore_commands: List[str] = field(default_factory=list)


@dataclass
class SnapshotDiff:
    """Differences between two snapshots"""
    before_snapshot_id: str
    after_snapshot_id: str
    timestamp: datetime
    database_changes: List[str] = field(default_factory=list)
    filesystem_changes: List[str] = field(default_factory=list)
    memory_changes: List[str] = field(default_factory=list)
    affected_tables: List[str] = field(default_factory=list)
    affected_files: List[str] = field(default_factory=list)
    summary: str = ""


@dataclass
class RecoveryPoint:
    """A point in time that can be recovered to"""
    point_id: str
    snapshot_id: str
    execution_id: str
    timestamp: datetime
    description: str
    is_valid: bool = True
    recovery_time_secs: Optional[float] = None


# ============================================================================
# DATABASE SNAPSHOT HANDLER
# ============================================================================

class DatabaseSnapshotHandler:
    """Handle PostgreSQL database snapshots and recovery"""

    def __init__(self, db_connection_string: str):
        """Initialize database snapshot handler"""
        self.connection_string = db_connection_string

    def create_snapshot(self, snapshot_id: str, backup_dir: str) -> Dict[str, Any]:
        """
        Create a PostgreSQL backup using pg_dump.
        
        Returns metadata about the backup:
        - Size
        - Number of tables
        - Backup format
        - Compressed size
        """
        import subprocess

        try:
            # Extract database name from connection string
            db_name = self._extract_db_name()

            # Create backup file
            backup_file = f"{backup_dir}/db_snapshot_{snapshot_id}.sql"

            # Run pg_dump
            cmd = f"pg_dump -d {db_name} -f {backup_file}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"Database backup failed: {result.stderr}")
                return {"success": False, "error": result.stderr}

            # Get file stats
            backup_path = Path(backup_file)
            size_bytes = backup_path.stat().st_size

            # Count tables in backup
            with open(backup_file, "r") as f:
                content = f.read()
                table_count = content.count("CREATE TABLE")

            return {
                "success": True,
                "backup_file": backup_file,
                "size_bytes": size_bytes,
                "table_count": table_count,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error creating database snapshot: {e}")
            return {"success": False, "error": str(e)}

    def restore_snapshot(self, backup_file: str, target_db: Optional[str] = None) -> bool:
        """
        Restore database from snapshot.
        
        Args:
            backup_file: Path to SQL backup file
            target_db: Target database (if different from original)
        
        Returns:
            Success status
        """
        import subprocess

        try:
            db_name = target_db or self._extract_db_name()

            # Drop existing database (optional, for full restore)
            # subprocess.run(f"dropdb {db_name}", shell=True, capture_output=True)

            # Restore from backup
            cmd = f"psql -d {db_name} -f {backup_file}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"Database restore failed: {result.stderr}")
                return False

            logger.info(f"Successfully restored database from {backup_file}")
            return True

        except Exception as e:
            logger.error(f"Error restoring database snapshot: {e}")
            return False

    def get_table_diff(self, before_backup: str, after_backup: str) -> List[str]:
        """Compare two database backups and identify changes"""
        changes = []

        try:
            # Parse both backups
            before_tables = self._parse_schema(before_backup)
            after_tables = self._parse_schema(after_backup)

            # Find new tables
            new_tables = set(after_tables.keys()) - set(before_tables.keys())
            if new_tables:
                changes.append(f"New tables: {', '.join(new_tables)}")

            # Find deleted tables
            deleted_tables = set(before_tables.keys()) - set(after_tables.keys())
            if deleted_tables:
                changes.append(f"Deleted tables: {', '.join(deleted_tables)}")

            # Find altered tables
            for table_name in before_tables:
                if table_name in after_tables:
                    if before_tables[table_name] != after_tables[table_name]:
                        changes.append(f"Altered table: {table_name}")

        except Exception as e:
            logger.error(f"Error comparing database backups: {e}")

        return changes

    def _extract_db_name(self) -> str:
        """Extract database name from connection string"""
        # Example: "postgresql://user:pass@localhost/dbname"
        parts = self.connection_string.split("/")
        return parts[-1] if parts else "projectxy"

    def _parse_schema(self, backup_file: str) -> Dict[str, Dict]:
        """Parse SQL dump and extract schema information"""
        tables = {}

        try:
            with open(backup_file, "r") as f:
                content = f.read()

                # Simple extraction of table definitions
                import re

                table_pattern = r"CREATE TABLE.*?(\w+)\s*\((.*?)\);"
                for match in re.finditer(table_pattern, content, re.DOTALL):
                    table_name = match.group(1)
                    table_def = match.group(2)
                    tables[table_name] = table_def

        except Exception as e:
            logger.error(f"Error parsing schema: {e}")

        return tables


# ============================================================================
# FILESYSTEM SNAPSHOT HANDLER
# ============================================================================

class FilesystemSnapshotHandler:
    """Handle file system snapshots and recovery"""

    def __init__(self, watch_paths: List[str]):
        """
        Initialize filesystem snapshot handler
        
        Args:
            watch_paths: List of directories to snapshot
        """
        self.watch_paths = watch_paths

    def create_snapshot(self, snapshot_id: str, snapshot_dir: str) -> Dict[str, Any]:
        """
        Create filesystem snapshot using copy-on-write or directory copy.
        
        Returns:
        - Number of files
        - Total size
        - File list with hashes
        """
        try:
            snapshot_path = Path(snapshot_dir) / f"fs_snapshot_{snapshot_id}"
            snapshot_path.mkdir(parents=True, exist_ok=True)

            file_list = {}
            total_size = 0

            for watch_path in self.watch_paths:
                watch_path_obj = Path(watch_path)
                if not watch_path_obj.exists():
                    continue

                # Copy directory tree
                dest = snapshot_path / watch_path_obj.name
                if dest.exists():
                    shutil.rmtree(dest)

                shutil.copytree(watch_path_obj, dest)

                # Generate file list with hashes
                for file_path in dest.rglob("*"):
                    if file_path.is_file():
                        rel_path = file_path.relative_to(snapshot_path)
                        file_hash = self._hash_file(file_path)
                        file_list[str(rel_path)] = {
                            "hash": file_hash,
                            "size": file_path.stat().st_size,
                        }
                        total_size += file_path.stat().st_size

            return {
                "success": True,
                "snapshot_path": str(snapshot_path),
                "file_count": len(file_list),
                "total_size": total_size,
                "file_list": file_list,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error creating filesystem snapshot: {e}")
            return {"success": False, "error": str(e)}

    def restore_snapshot(self, snapshot_path: str, target_paths: Dict[str, str]) -> bool:
        """
        Restore filesystem from snapshot.
        
        Args:
            snapshot_path: Path to snapshot directory
            target_paths: Mapping of snapshot paths to restore destinations
        
        Returns:
            Success status
        """
        try:
            snapshot_path_obj = Path(snapshot_path)

            for src_subdir, dest_path in target_paths.items():
                src = snapshot_path_obj / src_subdir
                dest = Path(dest_path)

                if src.exists():
                    # Back up current state before restore
                    if dest.exists():
                        backup_dest = Path(f"{dest}.backup")
                        if backup_dest.exists():
                            shutil.rmtree(backup_dest)
                        shutil.copytree(dest, backup_dest)

                    # Restore from snapshot
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(src, dest)

            logger.info(f"Successfully restored filesystem from snapshot")
            return True

        except Exception as e:
            logger.error(f"Error restoring filesystem snapshot: {e}")
            return False

    def get_filesystem_diff(self, before_snapshot: Dict, after_snapshot: Dict) -> List[str]:
        """Compare two filesystem snapshots"""
        changes = []

        before_files = before_snapshot.get("file_list", {})
        after_files = after_snapshot.get("file_list", {})

        # Find new files
        new_files = set(after_files.keys()) - set(before_files.keys())
        if new_files:
            changes.append(f"Created files: {len(new_files)}")

        # Find deleted files
        deleted_files = set(before_files.keys()) - set(after_files.keys())
        if deleted_files:
            changes.append(f"Deleted files: {len(deleted_files)}")

        # Find modified files (hash changed)
        modified_files = 0
        for file_path in before_files:
            if file_path in after_files:
                if (before_files[file_path]["hash"] != after_files[file_path]["hash"]):
                    modified_files += 1

        if modified_files:
            changes.append(f"Modified files: {modified_files}")

        return changes

    def _hash_file(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()


# ============================================================================
# DIGITAL TWIN SNAPSHOT MANAGER
# ============================================================================

class DigitalTwinEngine:
    """
    Main engine for managing system snapshots and recovery.
    
    Coordinates database, filesystem, and memory snapshots for safe
    execution of high-risk operations.
    """

    def __init__(
        self,
        db_connection: str,
        watch_paths: List[str],
        snapshot_root: str = "/var/snapshots",
    ):
        """Initialize Digital Twin engine"""
        self.db_handler = DatabaseSnapshotHandler(db_connection)
        self.fs_handler = FilesystemSnapshotHandler(watch_paths)
        self.snapshot_root = Path(snapshot_root)
        self.snapshot_root.mkdir(parents=True, exist_ok=True)

        self.snapshots: Dict[str, SystemSnapshot] = {}
        self.recovery_points: Dict[str, RecoveryPoint] = {}

    def create_pre_execution_snapshot(
        self,
        execution_id: str,
        risk_level: int,
        created_by: str,
        recovery_strategy: RecoveryStrategy = RecoveryStrategy.AUTOMATIC_ROLLBACK,
    ) -> SystemSnapshot:
        """
        Create a comprehensive snapshot before executing a risky operation.
        
        Captures:
        - Database state
        - File system state
        - Application state
        """
        snapshot_id = f"snap_{execution_id}_{int(datetime.utcnow().timestamp())}"

        logger.info(
            f"Creating pre-execution snapshot {snapshot_id} for execution {execution_id} "
            f"(risk_level={risk_level})"
        )

        # Create snapshots for each component
        db_snapshot = self.db_handler.create_snapshot(
            snapshot_id, str(self.snapshot_root)
        )
        fs_snapshot = self.fs_handler.create_snapshot(
            snapshot_id, str(self.snapshot_root)
        )

        # Create metadata
        total_size = db_snapshot.get("size_bytes", 0) + fs_snapshot.get(
            "total_size", 0
        )
        checksum = self._calculate_checksum(snapshot_id, [db_snapshot, fs_snapshot])

        metadata = SnapshotMetadata(
            snapshot_id=snapshot_id,
            execution_id=execution_id,
            snapshot_type=SnapshotType.FULL,
            created_at=datetime.utcnow(),
            created_by=created_by,
            description=f"Pre-execution snapshot for risk level {risk_level}",
            risk_level=risk_level,
            size_bytes=total_size,
            checksum=checksum,
            recovery_strategy=recovery_strategy,
        )

        # Create snapshot object
        snapshot = SystemSnapshot(
            metadata=metadata,
            database_state=db_snapshot,
            filesystem_state=fs_snapshot,
            storage_path=str(self.snapshot_root / snapshot_id),
        )

        self.snapshots[snapshot_id] = snapshot

        # Create recovery point
        recovery_point = RecoveryPoint(
            point_id=f"rp_{snapshot_id}",
            snapshot_id=snapshot_id,
            execution_id=execution_id,
            timestamp=datetime.utcnow(),
            description=f"Pre-execution recovery point",
        )

        self.recovery_points[recovery_point.point_id] = recovery_point

        logger.info(
            f"Created snapshot {snapshot_id}: {total_size / 1024 / 1024:.2f}MB"
        )

        return snapshot

    def create_post_execution_snapshot(
        self, execution_id: str, success: bool, created_by: str
    ) -> SystemSnapshot:
        """Create snapshot after execution for comparison"""
        snapshot_id = f"snap_post_{execution_id}_{int(datetime.utcnow().timestamp())}"

        db_snapshot = self.db_handler.create_snapshot(
            snapshot_id, str(self.snapshot_root)
        )
        fs_snapshot = self.fs_handler.create_snapshot(
            snapshot_id, str(self.snapshot_root)
        )

        metadata = SnapshotMetadata(
            snapshot_id=snapshot_id,
            execution_id=execution_id,
            snapshot_type=SnapshotType.FULL,
            created_at=datetime.utcnow(),
            created_by=created_by,
            description=f"Post-execution snapshot ({'success' if success else 'failed'})",
            risk_level=10,  # Always critical
            size_bytes=db_snapshot.get("size_bytes", 0) + fs_snapshot.get("total_size", 0),
            checksum=self._calculate_checksum(snapshot_id, [db_snapshot, fs_snapshot]),
            recovery_strategy=RecoveryStrategy.SNAPSHOT_ONLY,
        )

        snapshot = SystemSnapshot(
            metadata=metadata,
            database_state=db_snapshot,
            filesystem_state=fs_snapshot,
            storage_path=str(self.snapshot_root / snapshot_id),
        )

        self.snapshots[snapshot_id] = snapshot

        return snapshot

    def compare_snapshots(
        self, before_id: str, after_id: str
    ) -> Optional[SnapshotDiff]:
        """
        Compare two snapshots and generate a diff report.
        
        Returns:
        - Database changes
        - Filesystem changes
        - Summary of modifications
        """
        if before_id not in self.snapshots or after_id not in self.snapshots:
            logger.error(f"Snapshots not found: {before_id}, {after_id}")
            return None

        before = self.snapshots[before_id]
        after = self.snapshots[after_id]

        # Compare databases
        db_changes = []
        if before.database_state and after.database_state:
            db_changes = self.db_handler.get_table_diff(
                before.database_state.get("backup_file", ""),
                after.database_state.get("backup_file", ""),
            )

        # Compare filesystems
        fs_changes = []
        if before.filesystem_state and after.filesystem_state:
            fs_changes = self.fs_handler.get_filesystem_diff(
                before.filesystem_state, after.filesystem_state
            )

        diff = SnapshotDiff(
            before_snapshot_id=before_id,
            after_snapshot_id=after_id,
            timestamp=datetime.utcnow(),
            database_changes=db_changes,
            filesystem_changes=fs_changes,
            summary=self._generate_diff_summary(db_changes, fs_changes),
        )

        return diff

    def rollback_to_snapshot(self, snapshot_id: str) -> bool:
        """
        Perform full rollback to a previous snapshot.
        
        Restores:
        - Database state
        - File system state
        - Application state (if available)
        """
        if snapshot_id not in self.snapshots:
            logger.error(f"Snapshot not found: {snapshot_id}")
            return False

        snapshot = self.snapshots[snapshot_id]

        logger.warning(f"INITIATING ROLLBACK to snapshot {snapshot_id}")

        try:
            # Restore database
            if snapshot.database_state:
                backup_file = snapshot.database_state.get("backup_file")
                if backup_file:
                    if not self.db_handler.restore_snapshot(backup_file):
                        logger.error("Database restore failed")
                        return False

            # Restore filesystem
            if snapshot.filesystem_state:
                storage_path = snapshot.storage_path
                if storage_path:
                    if not self.fs_handler.restore_snapshot(
                        storage_path,
                        {path: path for path in self.fs_handler.watch_paths},
                    ):
                        logger.error("Filesystem restore failed")
                        return False

            logger.info(f"Successfully rolled back to snapshot {snapshot_id}")
            return True

        except Exception as e:
            logger.error(f"Error performing rollback: {e}")
            return False

    def get_recovery_points(
        self, execution_id: Optional[str] = None
    ) -> List[RecoveryPoint]:
        """Retrieve available recovery points"""
        if execution_id:
            return [
                rp
                for rp in self.recovery_points.values()
                if rp.execution_id == execution_id
            ]
        return list(self.recovery_points.values())

    def cleanup_old_snapshots(self, retention_days: int = 7) -> int:
        """Clean up snapshots older than retention period"""
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        removed_count = 0

        snapshots_to_remove = [
            snap_id
            for snap_id, snapshot in self.snapshots.items()
            if snapshot.metadata.created_at < cutoff_date
        ]

        for snap_id in snapshots_to_remove:
            snapshot = self.snapshots[snap_id]
            # Clean up files
            if snapshot.storage_path and Path(snapshot.storage_path).exists():
                shutil.rmtree(snapshot.storage_path)
            del self.snapshots[snap_id]
            removed_count += 1

        logger.info(f"Cleaned up {removed_count} snapshots older than {retention_days} days")
        return removed_count

    def _calculate_checksum(self, snapshot_id: str, components: List[Dict]) -> str:
        """Calculate checksum for snapshot integrity verification"""
        content = f"{snapshot_id}:{json.dumps(components, default=str)}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _generate_diff_summary(
        self, db_changes: List[str], fs_changes: List[str]
    ) -> str:
        """Generate a summary of changes"""
        summary_parts = []

        if db_changes:
            summary_parts.append(f"Database: {'; '.join(db_changes)}")
        if fs_changes:
            summary_parts.append(f"Filesystem: {'; '.join(fs_changes)}")

        return " | ".join(summary_parts) if summary_parts else "No changes detected"
