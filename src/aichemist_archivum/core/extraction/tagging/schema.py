"""
Database schema for tag management system.

This module provides the TagSchema class, which is responsible for
creating and managing the database schema for the tag management system.
"""

import logging
from pathlib import Path

from the_aichemist_codex.infrastructure.utils.io.sqlasync_io import AsyncSQL

logger = logging.getLogger(__name__)


class TagSchema:
    """
    Manages the database schema for the tag management system.

    This class is responsible for creating and initializing the database
    tables required for the tag management system.
    """

    def __init__(self, db_path: Path):
        """
        Initialize the schema manager with a database path.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.db = AsyncSQL(db_path)

    async def initialize(self) -> None:
        """
        Initialize the database schema.

        Creates the tables if they don't exist.
        """
        # Create tables
        await self._create_tags_table()
        await self._create_file_tags_table()

        logger.debug(f"Initialized database schema at {self.db_path}")

    async def _create_tags_table(self) -> None:
        """Create the tags table if it doesn't exist."""
        query = """
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        await self.db.execute(query, commit=True)

    async def _create_file_tags_table(self) -> None:
        """Create the file_tags table if it doesn't exist."""
        query = """
        CREATE TABLE IF NOT EXISTS file_tags (
            file_path TEXT NOT NULL,
            tag_id INTEGER NOT NULL,
            source TEXT DEFAULT 'manual',
            confidence REAL DEFAULT 1.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (file_path, tag_id),
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        )
        """
        await self.db.execute(query, commit=True)
