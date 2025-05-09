"""
SQLite implementation of the Tag Hierarchy Repository interface.
Manages persistence for parent-child tag relationships.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

# Import domain interfaces and entities
from the_aichemist_codex.domain.exceptions.repository_exception import RepositoryError
from the_aichemist_codex.domain.repositories.interfaces.tag_hierarchy_repository import (
    TagHierarchyRepositoryInterface,
    TagInfo,
)

# Import infrastructure utilities
from the_aichemist_codex.infrastructure.utils.io.sqlasync_io import AsyncSQL

logger = logging.getLogger(__name__)

# --- Schema Definitions ---
CREATE_TAG_HIERARCHY_TABLE = """
CREATE TABLE IF NOT EXISTS tag_hierarchy (
    parent_id INTEGER NOT NULL,
    child_id INTEGER NOT NULL,
    created_at TEXT NOT NULL, -- Store as ISO format string
    PRIMARY KEY (parent_id, child_id),
    FOREIGN KEY (parent_id) REFERENCES tags (id) ON DELETE CASCADE,
    FOREIGN KEY (child_id) REFERENCES tags (id) ON DELETE CASCADE,
    CHECK (parent_id != child_id) -- Prevent self-referencing
);
"""
# Indexes are useful for hierarchy queries
CREATE_HIERARCHY_PARENT_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_th_parent ON tag_hierarchy(parent_id);"
)
CREATE_HIERARCHY_CHILD_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_th_child ON tag_hierarchy(child_id);"
)
# --- End Schema Definitions ---


class SQLiteTagHierarchyRepository(TagHierarchyRepositoryInterface):
    """SQLite implementation for storing and retrieving Tag Hierarchies."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.sql = AsyncSQL(db_path)
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the database table and indexes."""
        if self._initialized:
            return
        try:
            # Note: Assumes the 'tags' table is created by SQLiteTagRepository
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            await self.sql.execute(CREATE_TAG_HIERARCHY_TABLE, commit=True)
            await self.sql.execute(CREATE_HIERARCHY_PARENT_INDEX, commit=True)
            await self.sql.execute(CREATE_HIERARCHY_CHILD_INDEX, commit=True)
            self._initialized = True
            logger.info(
                f"Initialized SQLite Tag Hierarchy Repository at {self.db_path}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize tag hierarchy database: {e}")
            raise RepositoryError(
                "Failed to initialize tag hierarchy database", cause=e
            ) from e

    def _row_to_tag_info(self, row: tuple) -> TagInfo:
        """Convert a database row tuple to a TagInfo object."""
        (id_val, name, description) = row
        return TagInfo(id=id_val, name=name, description=description)

    async def add_relationship(self, parent_id: int, child_id: int) -> bool:
        """Add a parent-child relationship."""
        await self.initialize()
        if parent_id == child_id:
            logger.warning("Cannot create self-referential tag relationship.")
            return False

        # Check for potential cycles before inserting
        if await self.is_ancestor(child_id, parent_id):
            logger.warning(
                f"Adding relationship {parent_id}->{child_id} would create a cycle."
            )
            return False

        now_iso = datetime.now().isoformat()
        try:
            await self.sql.execute(
                "INSERT INTO tag_hierarchy (parent_id, child_id, created_at) VALUES (?, ?, ?)",
                (parent_id, child_id, now_iso),
                commit=True,
            )
            logger.debug(f"Added tag hierarchy relationship: {parent_id} -> {child_id}")
            return True
        except sqlite3.IntegrityError as e:
            # This usually means the relationship already exists or a foreign key constraint failed
            logger.warning(f"Could not add relationship {parent_id}->{child_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error adding relationship {parent_id}->{child_id}: {e}")
            raise RepositoryError("Failed to add tag relationship", cause=e) from e

    async def remove_relationship(self, parent_id: int, child_id: int) -> bool:
        """Remove a parent-child relationship."""
        await self.initialize()
        try:
            await self.sql.execute(
                "DELETE FROM tag_hierarchy WHERE parent_id = ? AND child_id = ?",
                (parent_id, child_id),
                commit=True,
            )
            # Check rowcount if needed
            logger.debug(
                f"Removed tag hierarchy relationship: {parent_id} -> {child_id}"
            )
            return True
        except Exception as e:
            logger.error(f"Error removing relationship {parent_id}->{child_id}: {e}")
            raise RepositoryError("Failed to remove tag relationship", cause=e) from e

    async def get_parents(self, tag_id: int) -> list[TagInfo]:
        """Get direct parent tags."""
        await self.initialize()
        rows = await self.sql.fetchall(
            """
            SELECT t.id, t.name, t.description
            FROM tag_hierarchy th JOIN tags t ON th.parent_id = t.id
            WHERE th.child_id = ? ORDER BY t.name
            """,
            (tag_id,),
        )
        return [self._row_to_tag_info(row) for row in rows]

    async def get_children(self, tag_id: int) -> list[TagInfo]:
        """Get direct child tags."""
        await self.initialize()
        rows = await self.sql.fetchall(
            """
            SELECT t.id, t.name, t.description
            FROM tag_hierarchy th JOIN tags t ON th.child_id = t.id
            WHERE th.parent_id = ? ORDER BY t.name
            """,
            (tag_id,),
        )
        return [self._row_to_tag_info(row) for row in rows]

    async def get_ancestors(self, tag_id: int) -> list[TagInfo]:
        """Get all ancestor tags (recursive parents)."""
        await self.initialize()
        # Recursive CTE query
        rows = await self.sql.fetchall(
            """
            WITH RECURSIVE tag_ancestors(id) AS (
                SELECT parent_id FROM tag_hierarchy WHERE child_id = ?
                UNION ALL
                SELECT th.parent_id FROM tag_hierarchy th JOIN tag_ancestors ta ON th.child_id = ta.id
            )
            SELECT DISTINCT t.id, t.name, t.description
            FROM tag_ancestors ta JOIN tags t ON ta.id = t.id
            ORDER BY t.name;
            """,
            (tag_id,),
        )
        return [self._row_to_tag_info(row) for row in rows]

    async def get_descendants(self, tag_id: int) -> list[TagInfo]:
        """Get all descendant tags (recursive children)."""
        await self.initialize()
        # Recursive CTE query
        rows = await self.sql.fetchall(
            """
            WITH RECURSIVE tag_descendants(id) AS (
                SELECT child_id FROM tag_hierarchy WHERE parent_id = ?
                UNION ALL
                SELECT th.child_id FROM tag_hierarchy th JOIN tag_descendants td ON th.parent_id = td.id
            )
            SELECT DISTINCT t.id, t.name, t.description
            FROM tag_descendants td JOIN tags t ON td.id = t.id
            ORDER BY t.name;
            """,
            (tag_id,),
        )
        return [self._row_to_tag_info(row) for row in rows]

    async def is_ancestor(self, ancestor_id: int, descendant_id: int) -> bool:
        """Check if ancestor_id is an ancestor of descendant_id."""
        await self.initialize()
        row = await self.sql.fetchone(
            """
            WITH RECURSIVE tag_ancestors(id) AS (
                SELECT parent_id FROM tag_hierarchy WHERE child_id = ?
                UNION ALL
                SELECT th.parent_id FROM tag_hierarchy th JOIN tag_ancestors ta ON th.child_id = ta.id
            )
            SELECT 1 FROM tag_ancestors WHERE id = ? LIMIT 1;
            """,
            (descendant_id, ancestor_id),
        )
        return row is not None

    async def remove_relationships_for_tag(self, tag_id: int) -> int:
        """Remove all hierarchy relationships involving a specific tag."""
        await self.initialize()
        try:
            # Count before deleting
            count_row = await self.sql.fetchone(
                "SELECT COUNT(*) FROM tag_hierarchy WHERE parent_id = ? OR child_id = ?",
                (tag_id, tag_id),
            )
            count = count_row[0] if count_row else 0

            if count > 0:
                await self.sql.execute(
                    "DELETE FROM tag_hierarchy WHERE parent_id = ? OR child_id = ?",
                    (tag_id, tag_id),
                    commit=True,
                )
                logger.debug(
                    f"Removed {count} hierarchy relationships for tag {tag_id}"
                )
            return count
        except Exception as e:
            logger.error(
                f"Error removing hierarchy relationships for tag {tag_id}: {e}"
            )
            raise RepositoryError(
                "Failed removing hierarchy relationships",
                entity_id=str(tag_id),
                cause=e,
            ) from e
