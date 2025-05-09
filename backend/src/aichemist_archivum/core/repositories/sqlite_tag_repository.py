"""
SQLite implementation of the Tag Repository interface.
Manages persistence for Tags and FileTagAssociations.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

# Import domain interfaces and entities
from the_aichemist_codex.domain.exceptions.repository_exception import RepositoryError
from the_aichemist_codex.domain.repositories.interfaces.tag_repository import (
    FileTagAssociation,
    Tag,
    TagRepositoryInterface,
)

# Import infrastructure utilities
from the_aichemist_codex.infrastructure.utils.io.sqlasync_io import AsyncSQL

logger = logging.getLogger(__name__)

# --- Schema Definitions (Moved from domain/tagging/schema.py) ---
CREATE_TAGS_TABLE = """
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE, -- Store lowercase, ensure unique case-insensitively
    description TEXT,
    created_at TEXT NOT NULL, -- Store as ISO format string
    modified_at TEXT NOT NULL -- Store as ISO format string
);
"""

CREATE_FILE_TAGS_TABLE = """
CREATE TABLE IF NOT EXISTS file_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    tag_id INTEGER NOT NULL,
    source TEXT NOT NULL, -- 'manual', 'auto', 'suggested'
    confidence REAL DEFAULT 1.0,
    added_at TEXT NOT NULL, -- Store as ISO format string
    FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE,
    UNIQUE (file_path, tag_id)
);
"""

CREATE_TAG_NAME_INDEX = "CREATE INDEX IF NOT EXISTS idx_tags_name ON tags (name);"
CREATE_FILE_TAGS_PATH_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_file_tags_path ON file_tags (file_path);"
)
CREATE_FILE_TAGS_TAG_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_file_tags_tag_id ON file_tags (tag_id);"
)

# Trigger to update modified_at timestamp
CREATE_TAGS_UPDATE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS update_tags_modified_at
AFTER UPDATE ON tags FOR EACH ROW
BEGIN
    UPDATE tags SET modified_at = STRFTIME('%Y-%m-%dT%H:%M:%f', 'NOW') WHERE id = NEW.id;
END;
"""
# --- End Schema Definitions ---


class SQLiteTagRepository(TagRepositoryInterface):
    """SQLite implementation for storing and retrieving Tags and FileTags."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.sql = AsyncSQL(db_path)
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the database tables and indexes."""
        if self._initialized:
            return
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            await self.sql.execute(CREATE_TAGS_TABLE, commit=True)
            await self.sql.execute(CREATE_FILE_TAGS_TABLE, commit=True)
            await self.sql.execute(CREATE_TAG_NAME_INDEX, commit=True)
            await self.sql.execute(CREATE_FILE_TAGS_PATH_INDEX, commit=True)
            await self.sql.execute(CREATE_FILE_TAGS_TAG_INDEX, commit=True)
            await self.sql.execute(
                CREATE_TAGS_UPDATE_TRIGGER, commit=True
            )  # Add trigger execution
            self._initialized = True
            logger.info(f"Initialized SQLite Tag Repository at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize tag database: {e}")
            raise RepositoryError("Failed to initialize tag database", cause=e)

    def _row_to_tag(self, row: tuple) -> Tag:
        """Convert a database row tuple to a Tag object."""
        (id_val, name, description, created_at_str, modified_at_str) = row
        return Tag(
            id=id_val,
            name=name,
            description=description,
            created_at=datetime.fromisoformat(created_at_str),
            modified_at=datetime.fromisoformat(modified_at_str),
        )

    def _row_to_file_tag_association(self, row: tuple) -> FileTagAssociation:
        """Convert a database row tuple to a FileTagAssociation object."""
        (id_val, file_path_str, tag_id, source, confidence, added_at_str) = row
        return FileTagAssociation(
            file_path=Path(file_path_str),
            tag_id=tag_id,
            source=source,
            confidence=float(confidence),
            added_at=datetime.fromisoformat(added_at_str),
        )

    # --- Tag CRUD ---
    async def create_tag(self, name: str, description: str = "") -> Tag:
        """Create a new tag or return existing one."""
        await self.initialize()
        normalized_name = name.strip().lower()
        if not normalized_name:
            raise ValueError("Tag name cannot be empty.")

        try:
            # Check if tag already exists (case-insensitive)
            existing = await self.get_tag_by_name(normalized_name)
            if existing:
                return existing

            # Create new tag
            now_iso = datetime.now().isoformat()
            params = (normalized_name, description or "", now_iso, now_iso)
            await self.sql.execute(
                "INSERT INTO tags (name, description, created_at, modified_at) VALUES (?, ?, ?, ?)",
                params,
                commit=True,
            )

            # Retrieve the created tag to get its ID
            created_tag = await self.get_tag_by_name(normalized_name)
            if created_tag:
                logger.debug(f"Created tag: {normalized_name} (id: {created_tag.id})")
                return created_tag
            else:
                # This case should ideally not happen if insert succeeded
                raise RepositoryError(
                    f"Failed to retrieve newly created tag: {normalized_name}"
                )

        except Exception as e:
            # Check for UNIQUE constraint violation explicitly
            if isinstance(
                e, sqlite3.IntegrityError
            ) and "UNIQUE constraint failed: tags.name" in str(e):
                logger.warning(
                    f"Tag '{normalized_name}' already exists (concurrent creation?). Fetching existing."
                )
                existing = await self.get_tag_by_name(normalized_name)
                if existing:
                    return existing
                else:  # Should not happen if constraint failed
                    raise RepositoryError(
                        f"Constraint failed but cannot retrieve tag '{normalized_name}'",
                        cause=e,
                    )
            else:
                logger.error(f"Error creating tag '{normalized_name}': {e}")
                raise RepositoryError(
                    "Failed to create tag", details={"name": normalized_name}, cause=e
                )

    async def get_tag(self, tag_id: int) -> Tag | None:
        """Get a tag by ID."""
        await self.initialize()
        row = await self.sql.fetchone("SELECT * FROM tags WHERE id = ?", (tag_id,))
        return self._row_to_tag(row) if row else None

    async def get_tag_by_name(self, name: str) -> Tag | None:
        """Get a tag by name (case insensitive)."""
        await self.initialize()
        normalized_name = name.strip().lower()
        row = await self.sql.fetchone(
            "SELECT * FROM tags WHERE name = ?", (normalized_name,)
        )
        return self._row_to_tag(row) if row else None

    async def update_tag(
        self, tag_id: int, name: str | None = None, description: str | None = None
    ) -> bool:
        """Update a tag's name or description."""
        await self.initialize()
        if name is None and description is None:
            return False  # Nothing to update

        updates = {}
        if name is not None:
            normalized_name = name.strip().lower()
            if not normalized_name:
                raise ValueError("Tag name cannot be empty.")
            updates["name"] = normalized_name
        if description is not None:
            updates["description"] = description

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        params = list(updates.values()) + [tag_id]

        try:
            # Add modified_at update implicitly via trigger or explicitly
            # set_clause += ", modified_at = STRFTIME('%Y-%m-%dT%H:%M:%f', 'NOW')" # If trigger fails
            await self.sql.execute(
                f"UPDATE tags SET {set_clause} WHERE id = ?", tuple(params), commit=True
            )
            # Check if rows were affected (requires modification to AsyncSQL or fetch before/after)
            logger.debug(f"Updated tag {tag_id}")
            return (
                True  # Assume success if no error, rowcount check needed for certainty
            )
        except Exception as e:
            logger.error(f"Error updating tag {tag_id}: {e}")
            raise RepositoryError(
                "Failed to update tag", entity_id=str(tag_id), cause=e
            )

    async def delete_tag(self, tag_id: int) -> bool:
        """Delete a tag and its associations."""
        await self.initialize()
        try:
            await self.sql.execute(
                "DELETE FROM tags WHERE id = ?", (tag_id,), commit=True
            )
            logger.debug(f"Deleted tag {tag_id}")
            # Add check for rowcount if possible/needed
            return True  # Assume success
        except Exception as e:
            logger.error(f"Error deleting tag {tag_id}: {e}")
            raise RepositoryError(
                "Failed to delete tag", entity_id=str(tag_id), cause=e
            )

    async def get_all_tags(self) -> list[Tag]:
        """Get all tags."""
        await self.initialize()
        rows = await self.sql.fetchall("SELECT * FROM tags ORDER BY name")
        return [self._row_to_tag(row) for row in rows]

    # --- File Tag Association Management ---
    async def add_file_tag(
        self,
        file_path: Path,
        tag_id: int,
        source: str = "manual",
        confidence: float = 1.0,
    ) -> bool:
        """Add a tag association to a file."""
        await self.initialize()
        file_path_str = str(file_path.resolve())
        now_iso = datetime.now().isoformat()
        try:
            # Use INSERT OR IGNORE + UPDATE (upsert)
            await self.sql.execute(
                """
                INSERT INTO file_tags (file_path, tag_id, source, confidence, added_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(file_path, tag_id) DO UPDATE SET
                    source = excluded.source,
                    confidence = excluded.confidence,
                    added_at = excluded.added_at
                """,
                (file_path_str, tag_id, source, confidence, now_iso),
                commit=True,
            )
            # Cannot easily determine if insert or update happened without SELECT
            logger.debug(f"Associated tag {tag_id} with file '{file_path_str}'")
            return True  # Assume success
        except Exception as e:
            logger.error(f"Error adding tag {tag_id} to file '{file_path_str}': {e}")
            raise RepositoryError(
                "Failed to add file tag",
                details={"file": file_path_str, "tag_id": tag_id},
                cause=e,
            )

    async def add_file_tags_batch(self, file_tags: list[FileTagAssociation]) -> int:
        """Add multiple file-tag associations efficiently."""
        await self.initialize()
        if not file_tags:
            return 0

        now_iso = datetime.now().isoformat()
        params_list = [
            (
                str(ft.file_path.resolve()),
                ft.tag_id,
                ft.source,
                ft.confidence,
                ft.added_at.isoformat() if ft.added_at else now_iso,
            )
            for ft in file_tags
        ]

        try:
            # Use INSERT OR REPLACE or handle conflicts appropriately
            query = """
                INSERT INTO file_tags (file_path, tag_id, source, confidence, added_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(file_path, tag_id) DO UPDATE SET
                    source = excluded.source,
                    confidence = excluded.confidence,
                    added_at = excluded.added_at
            """
            await self.sql.executemany(query, params_list)
            logger.debug(f"Processed {len(params_list)} file tags in batch")
            return len(
                params_list
            )  # Returns number processed, not necessarily newly added
        except Exception as e:
            logger.error(f"Error in batch adding file tags: {e}")
            raise RepositoryError("Failed batch add file tags", cause=e)

    async def remove_file_tag(self, file_path: Path, tag_id: int) -> bool:
        """Remove a specific tag association from a file."""
        await self.initialize()
        file_path_str = str(file_path.resolve())
        try:
            await self.sql.execute(
                "DELETE FROM file_tags WHERE file_path = ? AND tag_id = ?",
                (file_path_str, tag_id),
                commit=True,
            )
            # Check rowcount if possible
            logger.debug(f"Removed tag {tag_id} from file '{file_path_str}'")
            return True
        except Exception as e:
            logger.error(
                f"Error removing tag {tag_id} from file '{file_path_str}': {e}"
            )
            raise RepositoryError("Failed to remove file tag", cause=e)

    async def remove_all_tags_for_file(self, file_path: Path) -> int:
        """Remove all tag associations for a specific file."""
        await self.initialize()
        file_path_str = str(file_path.resolve())
        try:
            # Get count before delete for accurate return value
            count_row = await self.sql.fetchone(
                "SELECT COUNT(*) FROM file_tags WHERE file_path = ?", (file_path_str,)
            )
            count = count_row[0] if count_row else 0

            if count > 0:
                await self.sql.execute(
                    "DELETE FROM file_tags WHERE file_path = ?",
                    (file_path_str,),
                    commit=True,
                )
                logger.debug(f"Removed {count} tags from file '{file_path_str}'")
            return count
        except Exception as e:
            logger.error(f"Error removing all tags for file '{file_path_str}': {e}")
            raise RepositoryError("Failed to remove all tags for file", cause=e)

    async def get_tags_for_file(self, file_path: Path) -> list[FileTagAssociation]:
        """Get all tag associations for a specific file."""
        await self.initialize()
        file_path_str = str(file_path.resolve())
        rows = await self.sql.fetchall(
            "SELECT * FROM file_tags WHERE file_path = ?", (file_path_str,)
        )
        return [self._row_to_file_tag_association(row) for row in rows]

    # --- Querying ---
    async def get_files_by_tag_id(self, tag_id: int) -> list[Path]:
        """Get all files associated with a specific tag ID."""
        await self.initialize()
        rows = await self.sql.fetchall(
            "SELECT file_path FROM file_tags WHERE tag_id = ?", (tag_id,)
        )
        return [Path(row[0]) for row in rows]

    async def get_files_by_tag_name(self, tag_name: str) -> list[Path]:
        """Get all files associated with a specific tag name."""
        await self.initialize()
        tag = await self.get_tag_by_name(tag_name)
        if not tag:
            return []
        return await self.get_files_by_tag_id(tag.id)

    async def get_files_by_tags(
        self, tag_ids: list[int], require_all: bool = False
    ) -> list[Path]:
        """Get files associated with multiple tags."""
        await self.initialize()
        if not tag_ids:
            return []

        try:
            placeholders = ",".join("?" * len(tag_ids))
            if require_all:
                query = f"""
                    SELECT file_path FROM file_tags
                    WHERE tag_id IN ({placeholders})
                    GROUP BY file_path
                    HAVING COUNT(DISTINCT tag_id) = ?
                """
                params = tuple(tag_ids) + (len(tag_ids),)
            else:
                query = f"""
                    SELECT DISTINCT file_path FROM file_tags
                    WHERE tag_id IN ({placeholders})
                """
                params = tuple(tag_ids)

            rows = await self.sql.fetchall(query, params)
            return [Path(row[0]) for row in rows]
        except Exception as e:
            logger.error(f"Error getting files by tags: {e}")
            raise RepositoryError("Failed to get files by tags", cause=e)

    async def get_tag_counts(self) -> list[dict[str, Any]]:
        """Get all tags with their usage counts."""
        await self.initialize()
        rows = await self.sql.fetchall(
            """
            SELECT t.id, t.name, t.description, COUNT(ft.file_path) as count
            FROM tags t
            LEFT JOIN file_tags ft ON t.id = ft.tag_id
            GROUP BY t.id, t.name, t.description
            ORDER BY count DESC, t.name
            """
        )
        return [
            {"id": row[0], "name": row[1], "description": row[2], "count": row[3]}
            for row in rows
        ]

    # --- Maintenance ---
    async def remove_tags_for_nonexistent_files(self) -> int:
        """Remove associations for files that no longer exist."""
        await self.initialize()
        try:
            all_paths_rows = await self.sql.fetchall(
                "SELECT DISTINCT file_path FROM file_tags"
            )
            all_paths = {Path(row[0]) for row in all_paths_rows}

            missing_paths = [p for p in all_paths if not p.exists()]

            if not missing_paths:
                return 0

            deleted_count = 0
            for path in missing_paths:
                await self.sql.execute(
                    "DELETE FROM file_tags WHERE file_path = ?",
                    (str(path),),
                    commit=True,
                )
                deleted_count += 1  # Approximation, better to get rowcount if possible

            logger.info(
                f"Removed tag associations for {len(missing_paths)} non-existent files."
            )
            return len(missing_paths)  # Return number of files cleaned
        except Exception as e:
            logger.error(f"Error cleaning tags for non-existent files: {e}")
            raise RepositoryError("Failed cleaning non-existent file tags", cause=e)

    async def remove_orphaned_tags(self) -> int:
        """Remove tags that are not associated with any files."""
        await self.initialize()
        try:
            # This query identifies tags that don't appear in file_tags
            # AND are not parents in the hierarchy (assuming hierarchy exists)
            # Note: Requires joining with tag_hierarchy table if that logic is added here
            # For now, just check file_tags:
            rows = await self.sql.fetchall(
                """
                SELECT id FROM tags
                WHERE id NOT IN (SELECT DISTINCT tag_id FROM file_tags)
                """
                # Add this condition if hierarchy table is managed here:
                # AND id NOT IN (SELECT DISTINCT parent_id FROM tag_hierarchy)
            )
            orphaned_ids = [row[0] for row in rows]

            if not orphaned_ids:
                return 0

            placeholders = ",".join("?" * len(orphaned_ids))
            await self.sql.execute(
                f"DELETE FROM tags WHERE id IN ({placeholders})",
                tuple(orphaned_ids),
                commit=True,
            )

            logger.info(f"Removed {len(orphaned_ids)} orphaned tags.")
            return len(orphaned_ids)
        except Exception as e:
            logger.error(f"Error removing orphaned tags: {e}")
            raise RepositoryError("Failed removing orphaned tags", cause=e)
