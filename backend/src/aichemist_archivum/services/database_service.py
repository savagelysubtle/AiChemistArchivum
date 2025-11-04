"""
Database service for AIchemist Archivum.

Provides database initialization, schema management, and data persistence
for files, tags, versions, and relationships.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Any

import aiosqlite
from aichemist_archivum.core.fs.file_metadata import FileMetadata

logger = logging.getLogger(__name__)


class DatabaseService:
    """
    Service for managing SQLite database operations.

    Handles initialization, schema management, and CRUD operations
    for files, tags, versions, and relationships.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """
        Initialize the database service.

        Args:
            db_path: Path to the SQLite database file. If None, uses default location.
        """
        if db_path is None:
            from aichemist_archivum.config import DATA_DIR

            db_path = DATA_DIR / "archivum.db"

        self.db_path = Path(db_path)
        self._initialized = False
        logger.info(f"Database service initialized with path: {self.db_path}")

    async def initialize_schema(self) -> None:
        """Initialize the database schema if it doesn't exist."""
        if self._initialized:
            return

        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(self.db_path) as db:
            # Enable foreign keys
            await db.execute("PRAGMA foreign_keys = ON")

            # Create files table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT UNIQUE NOT NULL,
                    filename TEXT NOT NULL,
                    extension TEXT,
                    mime_type TEXT,
                    size INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_indexed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create tags table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    category TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create file_tags junction table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS file_tags (
                    file_id INTEGER NOT NULL,
                    tag_id INTEGER NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE,
                    PRIMARY KEY (file_id, tag_id)
                )
            """)

            # Create versions table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER NOT NULL,
                    version_hash TEXT NOT NULL,
                    version_number TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    author TEXT,
                    message TEXT,
                    type TEXT,
                    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
                )
            """)

            # Create indices for performance
            await db.execute("CREATE INDEX IF NOT EXISTS idx_files_path ON files(path)")
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_files_filename ON files(filename)"
            )
            await db.execute("CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name)")
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_file_tags_file_id ON file_tags(file_id)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_file_tags_tag_id ON file_tags(tag_id)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_versions_file_id ON versions(file_id)"
            )

            await db.commit()

        self._initialized = True
        logger.info("Database schema initialized successfully")

    async def save_file_metadata(self, metadata: FileMetadata) -> int:
        """
        Save or update file metadata in the database.

        Args:
            metadata: FileMetadata object containing file information.

        Returns:
            File ID from the database.
        """
        await self.initialize_schema()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON")

            # Check if file already exists
            cursor = await db.execute(
                "SELECT id FROM files WHERE path = ?", (str(metadata.path),)
            )
            existing = await cursor.fetchone()

            if existing:
                # Update existing file
                await db.execute(
                    """
                    UPDATE files
                    SET filename = ?, extension = ?, mime_type = ?, size = ?,
                        updated_at = CURRENT_TIMESTAMP, last_indexed = CURRENT_TIMESTAMP
                    WHERE path = ?
                """,
                    (
                        metadata.path.name,
                        metadata.extension,
                        metadata.mime_type,
                        metadata.size,
                        str(metadata.path),
                    ),
                )
                file_id = existing[0]
                logger.debug(f"Updated file metadata for {metadata.path}")
            else:
                # Insert new file
                cursor = await db.execute(
                    """
                    INSERT INTO files (path, filename, extension, mime_type, size)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        str(metadata.path),
                        metadata.path.name,
                        metadata.extension,
                        metadata.mime_type,
                        metadata.size,
                    ),
                )
                file_id = cursor.lastrowid
                logger.debug(f"Inserted new file metadata for {metadata.path}")

            await db.commit()
            return file_id

    async def get_file_by_path(self, path: Path) -> dict[str, Any] | None:
        """
        Get file information by path.

        Args:
            path: Path to the file.

        Returns:
            Dictionary with file information or None if not found.
        """
        await self.initialize_schema()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM files WHERE path = ?", (str(path),)
            )
            row = await cursor.fetchone()

            if row:
                return dict(row)
            return None

    async def add_tags_to_file(self, file_path: Path, tag_names: list[str]) -> None:
        """
        Add tags to a file.

        Args:
            file_path: Path to the file.
            tag_names: List of tag names to add.
        """
        await self.initialize_schema()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON")

            # Get file ID
            cursor = await db.execute(
                "SELECT id FROM files WHERE path = ?", (str(file_path),)
            )
            file_row = await cursor.fetchone()

            if not file_row:
                logger.warning(f"File not found in database: {file_path}")
                return

            file_id = file_row[0]

            # Add each tag
            for tag_name in tag_names:
                # Ensure tag exists
                cursor = await db.execute(
                    "SELECT id FROM tags WHERE name = ?", (tag_name,)
                )
                tag_row = await cursor.fetchone()

                if tag_row:
                    tag_id = tag_row[0]
                else:
                    # Create new tag
                    cursor = await db.execute(
                        "INSERT INTO tags (name) VALUES (?)", (tag_name,)
                    )
                    tag_id = cursor.lastrowid

                # Associate tag with file (ignore if already exists)
                try:
                    await db.execute(
                        "INSERT OR IGNORE INTO file_tags (file_id, tag_id) VALUES (?, ?)",
                        (file_id, tag_id),
                    )
                except sqlite3.IntegrityError:
                    pass  # Tag already associated

            await db.commit()
            logger.info(f"Added tags {tag_names} to file {file_path}")

    async def remove_tags_from_file(
        self, file_path: Path, tag_names: list[str]
    ) -> None:
        """
        Remove tags from a file.

        Args:
            file_path: Path to the file.
            tag_names: List of tag names to remove.
        """
        await self.initialize_schema()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON")

            # Get file ID
            cursor = await db.execute(
                "SELECT id FROM files WHERE path = ?", (str(file_path),)
            )
            file_row = await cursor.fetchone()

            if not file_row:
                return

            file_id = file_row[0]

            # Remove each tag
            for tag_name in tag_names:
                await db.execute(
                    """
                    DELETE FROM file_tags
                    WHERE file_id = ? AND tag_id = (
                        SELECT id FROM tags WHERE name = ?
                    )
                """,
                    (file_id, tag_name),
                )

            await db.commit()
            logger.info(f"Removed tags {tag_names} from file {file_path}")

    async def get_file_tags(self, file_path: Path) -> list[dict[str, Any]]:
        """
        Get all tags for a file.

        Args:
            file_path: Path to the file.

        Returns:
            List of tag dictionaries.
        """
        await self.initialize_schema()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute(
                """
                SELECT t.id, t.name, t.description, t.category, ft.added_at
                FROM tags t
                JOIN file_tags ft ON t.id = ft.tag_id
                JOIN files f ON ft.file_id = f.id
                WHERE f.path = ?
                ORDER BY t.name
            """,
                (str(file_path),),
            )

            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_all_tags(self) -> list[dict[str, Any]]:
        """
        Get all tags in the system with usage counts.

        Returns:
            List of tag dictionaries with usage counts.
        """
        await self.initialize_schema()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute("""
                SELECT t.id, t.name, t.description, t.category, t.created_at,
                       COUNT(ft.file_id) as usage_count
                FROM tags t
                LEFT JOIN file_tags ft ON t.id = ft.tag_id
                GROUP BY t.id
                ORDER BY t.name
            """)

            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def create_tag(
        self, name: str, description: str | None = None, category: str | None = None
    ) -> int:
        """
        Create a new tag.

        Args:
            name: Tag name.
            description: Optional tag description.
            category: Optional tag category.

        Returns:
            Tag ID.
        """
        await self.initialize_schema()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO tags (name, description, category) VALUES (?, ?, ?)",
                (name, description, category),
            )
            await db.commit()
            logger.info(f"Created tag: {name}")
            return cursor.lastrowid

    async def search_files_by_tags(
        self, tag_names: list[str], match_all: bool = False
    ) -> list[dict[str, Any]]:
        """
        Search for files by tags.

        Args:
            tag_names: List of tag names to search for.
            match_all: If True, files must have all tags. If False, any tag matches.

        Returns:
            List of file dictionaries.
        """
        await self.initialize_schema()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            if match_all:
                # Files must have ALL specified tags
                placeholders = ",".join("?" * len(tag_names))
                cursor = await db.execute(
                    f"""
                    SELECT f.*, GROUP_CONCAT(t.name) as tags
                    FROM files f
                    JOIN file_tags ft ON f.id = ft.file_id
                    JOIN tags t ON ft.tag_id = t.id
                    WHERE f.id IN (
                        SELECT ft2.file_id
                        FROM file_tags ft2
                        JOIN tags t2 ON ft2.tag_id = t2.id
                        WHERE t2.name IN ({placeholders})
                        GROUP BY ft2.file_id
                        HAVING COUNT(DISTINCT t2.name) = ?
                    )
                    GROUP BY f.id
                """,
                    (*tag_names, len(tag_names)),
                )
            else:
                # Files can have ANY of the specified tags
                placeholders = ",".join("?" * len(tag_names))
                cursor = await db.execute(
                    f"""
                    SELECT DISTINCT f.*, GROUP_CONCAT(t.name) as tags
                    FROM files f
                    JOIN file_tags ft ON f.id = ft.file_id
                    JOIN tags t ON ft.tag_id = t.id
                    WHERE t.name IN ({placeholders})
                    GROUP BY f.id
                """,
                    tag_names,
                )

            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_statistics(self) -> dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dictionary with database statistics.
        """
        await self.initialize_schema()

        async with aiosqlite.connect(self.db_path) as db:
            stats = {}

            # Count files
            cursor = await db.execute("SELECT COUNT(*) FROM files")
            stats["total_files"] = (await cursor.fetchone())[0]

            # Count tags
            cursor = await db.execute("SELECT COUNT(*) FROM tags")
            stats["total_tags"] = (await cursor.fetchone())[0]

            # Count file-tag associations
            cursor = await db.execute("SELECT COUNT(*) FROM file_tags")
            stats["total_file_tags"] = (await cursor.fetchone())[0]

            # Count versions
            cursor = await db.execute("SELECT COUNT(*) FROM versions")
            stats["total_versions"] = (await cursor.fetchone())[0]

            # Average tags per file
            if stats["total_files"] > 0:
                stats["avg_tags_per_file"] = round(
                    stats["total_file_tags"] / stats["total_files"], 2
                )
            else:
                stats["avg_tags_per_file"] = 0.0

            return stats
