"""
SQLite Memory Repository

This module is part of the infrastructure layer of the AIchemist Codex.
Location: src/the_aichemist_codex/infrastructure/repositories/sqlite_memory_repository.py

Implements the MemoryRepository interface using SQLite for persistent storage.
This allows memory entities to be stored and retrieved from a local database.

Dependencies:
- domain.entities.memory
- domain.entities.memory_association
- domain.value_objects.recall_context
- infrastructure.utils.io.sqlasync_io
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from the_aichemist_codex.domain.entities.memory import (
    Memory,
    MemoryStrength,
    MemoryType,
)
from the_aichemist_codex.domain.entities.memory_association import (
    AssociationType,
    MemoryAssociation,
)
from the_aichemist_codex.domain.exceptions.repository_exception import RepositoryError
from the_aichemist_codex.domain.value_objects.recall_context import (
    RecallContext,
    RecallStrategy,
)
from the_aichemist_codex.infrastructure.utils.io.sqlasync_io import AsyncSQL

logger = logging.getLogger(__name__)


class SQLiteMemoryRepository:
    """SQLite implementation of the MemoryRepository interface."""

    def __init__(self: "SQLiteMemoryRepository", db_path: Path) -> None:
        """
        Initialize the repository with a database path.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.sql = AsyncSQL(db_path)

    async def initialize(self: "SQLiteMemoryRepository") -> None:
        """
        Initialize the repository by creating necessary tables.

        This should be called before using the repository.
        """
        # Create memories table
        await self.sql.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                type TEXT NOT NULL,
                source_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                tags TEXT NOT NULL,  -- Stored as JSON array
                metadata TEXT NOT NULL,  -- Stored as JSON object
                strength_initial REAL NOT NULL,
                strength_current REAL NOT NULL,
                strength_last_accessed TEXT NOT NULL,
                strength_access_count INTEGER NOT NULL
            )
            """,
            commit=True,
        )

        # Create associations table
        await self.sql.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_associations (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                association_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                strength REAL NOT NULL,
                bidirectional INTEGER NOT NULL,
                context TEXT,
                metadata TEXT NOT NULL,  -- Stored as JSON object
                FOREIGN KEY (source_id) REFERENCES memories (id),
                FOREIGN KEY (target_id) REFERENCES memories (id)
            )
            """,
            commit=True,
        )

        # Create indexes for efficient retrieval
        await self.sql.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_type ON memories (type)",
            commit=True,
        )
        await self.sql.execute(
            "CREATE INDEX IF NOT EXISTS idx_associations_source "
            "ON memory_associations (source_id)",
            commit=True,
        )
        await self.sql.execute(
            "CREATE INDEX IF NOT EXISTS idx_associations_target "
            "ON memory_associations (target_id)",
            commit=True,
        )

        logger.info("Initialized SQLite Memory Repository")

    async def save_memory(self: "SQLiteMemoryRepository", memory: Memory) -> UUID:
        """
        Save a memory to the repository.

        Args:
            memory: The memory to save

        Returns:
            The UUID of the saved memory

        Raises:
            RepositoryError: If the memory cannot be saved
        """
        try:
            # Convert sets and dicts to JSON for storage
            tags_json = json.dumps(list(memory.tags))
            metadata_json = json.dumps(memory.metadata)

            # Format datetime objects as ISO strings
            created_at = memory.created_at.isoformat()
            updated_at = memory.updated_at.isoformat() if memory.updated_at else None
            last_accessed = memory.strength.last_accessed.isoformat()

            # Convert UUID to string for storage
            source_id_str = str(memory.source_id) if memory.source_id else None

            await self.sql.execute(
                """
                INSERT OR REPLACE INTO memories (
                    id, content, type, source_id, created_at, updated_at,
                    tags, metadata, strength_initial, strength_current,
                    strength_last_accessed, strength_access_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(memory.id),
                    memory.content,
                    memory.type.name,
                    source_id_str,
                    created_at,
                    updated_at,
                    tags_json,
                    metadata_json,
                    memory.strength.initial_value,
                    memory.strength.current_value,
                    last_accessed,
                    memory.strength.access_count,
                ),
                commit=True,
            )

            return memory.id
        except Exception as e:
            logger.error(f"Error saving memory {memory.id}: {e}")
            raise RepositoryError(
                message="Failed to save memory",
                entity_type="Memory",
                operation="save",
                entity_id=str(memory.id),
                cause=e,
            ) from e

    async def get_memory(
        self: "SQLiteMemoryRepository", memory_id: UUID
    ) -> Memory | None:
        """
        Retrieve a memory by its ID.

        Args:
            memory_id: The UUID of the memory to retrieve

        Returns:
            The memory if found, None otherwise

        Raises:
            RepositoryError: If an error occurs during retrieval
        """
        try:
            row = await self.sql.fetchone(
                "SELECT * FROM memories WHERE id = ?", (str(memory_id),)
            )

            if not row:
                return None

            return self._row_to_memory(tuple(row))
        except Exception as e:
            logger.error(f"Error retrieving memory {memory_id}: {e}")
            raise RepositoryError(
                message="Failed to retrieve memory",
                entity_type="Memory",
                operation="get",
                entity_id=str(memory_id),
                cause=e,
            ) from e

    async def delete_memory(self: "SQLiteMemoryRepository", memory_id: UUID) -> bool:
        """
        Delete a memory by its ID.

        Args:
            memory_id: The UUID of the memory to delete

        Returns:
            True if successful, False otherwise

        Raises:
            RepositoryError: If an error occurs during deletion
        """
        try:
            # First, delete associated memory associations
            await self.sql.execute(
                """
                DELETE FROM memory_associations
                WHERE source_id = ? OR target_id = ?
                """,
                (str(memory_id), str(memory_id)),
                commit=True,
            )

            # Then delete the memory
            await self.sql.execute(
                "DELETE FROM memories WHERE id = ?",
                (str(memory_id),),
                commit=True,
            )

            # Check if the memory was actually deleted
            row = await self.sql.fetchone(
                "SELECT 1 FROM memories WHERE id = ?", (str(memory_id),)
            )

            return row is None
        except Exception as e:
            logger.error(f"Error deleting memory {memory_id}: {e}")
            raise RepositoryError(
                message="Failed to delete memory",
                entity_type="Memory",
                operation="delete",
                entity_id=str(memory_id),
                cause=e,
            ) from e

    async def update_memory(self: "SQLiteMemoryRepository", memory: Memory) -> bool:
        """
        Update an existing memory.

        Args:
            memory: The memory with updated fields

        Returns:
            True if successful, False otherwise

        Raises:
            RepositoryError: If an error occurs during update
        """
        # Implementation uses save_memory which handles upserts
        try:
            await self.save_memory(memory)
            return True
        except Exception as e:
            logger.error(f"Error updating memory {memory.id}: {e}")
            raise RepositoryError(
                message="Failed to update memory",
                entity_type="Memory",
                operation="update",
                entity_id=str(memory.id),
                cause=e,
            ) from e

    async def save_association(
        self: "SQLiteMemoryRepository", association: MemoryAssociation
    ) -> UUID:
        """
        Save a memory association.

        Args:
            association: The association to save

        Returns:
            The UUID of the saved association

        Raises:
            RepositoryError: If the association cannot be saved
        """
        try:
            # Convert metadata to JSON for storage
            metadata_json = json.dumps(association.metadata)

            # Format datetime objects as ISO strings
            created_at = association.created_at.isoformat()
            updated_at = (
                association.updated_at.isoformat() if association.updated_at else None
            )

            # Convert bidirectional boolean to integer for SQLite
            bidirectional_int = 1 if association.bidirectional else 0

            await self.sql.execute(
                """
                INSERT OR REPLACE INTO memory_associations (
                    id, source_id, target_id, association_type, created_at,
                    updated_at, strength, bidirectional, context, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(association.id),
                    str(association.source_id),
                    str(association.target_id),
                    association.association_type.name,
                    created_at,
                    updated_at,
                    association.strength,
                    bidirectional_int,
                    association.context,
                    metadata_json,
                ),
                commit=True,
            )

            return association.id
        except Exception as e:
            logger.error(f"Error saving association {association.id}: {e}")
            raise RepositoryError(
                message="Failed to save association",
                entity_type="MemoryAssociation",
                operation="save",
                entity_id=str(association.id),
                cause=e,
            ) from e

    async def get_association(
        self: "SQLiteMemoryRepository", association_id: UUID
    ) -> MemoryAssociation | None:
        """
        Retrieve an association by its ID.

        Args:
            association_id: The UUID of the association to retrieve

        Returns:
            The association if found, None otherwise

        Raises:
            RepositoryError: If an error occurs during retrieval
        """
        try:
            row = await self.sql.fetchone(
                "SELECT * FROM memory_associations WHERE id = ?", (str(association_id),)
            )

            if not row:
                return None

            return self._row_to_association(tuple(row))
        except Exception as e:
            logger.error(f"Error retrieving association {association_id}: {e}")
            raise RepositoryError(
                message="Failed to retrieve association",
                entity_type="MemoryAssociation",
                operation="get",
                entity_id=str(association_id),
                cause=e,
            ) from e

    async def find_associations(
        self: "SQLiteMemoryRepository", memory_id: UUID, bidirectional: bool = True
    ) -> list[MemoryAssociation]:
        """
        Find all associations for a given memory.

        Args:
            memory_id: The UUID of the memory
            bidirectional: Whether to include associations where this memory is the target

        Returns:
            List of associations connected to the memory

        Raises:
            RepositoryError: If an error occurs during retrieval
        """
        try:
            memory_id_str = str(memory_id)
            associations = []

            # Always get associations where this memory is the source
            source_rows = await self.sql.fetchall(
                "SELECT * FROM memory_associations WHERE source_id = ?",
                (memory_id_str,),
            )

            for row in source_rows:
                associations.append(self._row_to_association(tuple(row)))

            # Optionally get associations where this memory is the target
            if bidirectional:
                target_rows = await self.sql.fetchall(
                    """
                    SELECT * FROM memory_associations
                    WHERE target_id = ? AND bidirectional = 1
                    """,
                    (memory_id_str,),
                )

                for row in target_rows:
                    associations.append(self._row_to_association(tuple(row)))

            return associations
        except Exception as e:
            logger.error(f"Error finding associations for memory {memory_id}: {e}")
            raise RepositoryError(
                message="Failed to find associations",
                entity_type="MemoryAssociation",
                operation="find",
                details={"memory_id": str(memory_id)},
                cause=e,
            ) from e

    async def recall_memories(
        self: "SQLiteMemoryRepository", context: RecallContext
    ) -> list[Memory]:
        """
        Recall memories based on the provided context.

        Args:
            context: The recall context with query and filters

        Returns:
            List of memories matching the recall criteria

        Raises:
            RepositoryError: If an error occurs during recall
        """
        try:
            # Base query starts with content match
            query = "SELECT * FROM memories WHERE 1=1"
            params: list[Any] = []

            # Add content search if query is provided
            if context.query:
                query += " AND content LIKE ?"
                params.append(f"%{context.query}%")

            # Add type filter if provided
            if context.memory_types:
                types_list = list(context.memory_types)
                placeholders = ", ".join("?" for _ in types_list)
                query += f" AND type IN ({placeholders})"
                params.extend(types_list)

            # Add tag filter if provided
            if context.tags:
                # Since tags are stored as JSON arrays, we need to check each tag
                # This is simplified - in a real implementation, you might use JSON functions
                for tag in context.tags:
                    query += " AND tags LIKE ?"
                    params.append(f"%{tag}%")

            # Adjust order based on strategy
            if context.strategy == RecallStrategy.MOST_RECENT:
                query += " ORDER BY created_at DESC"
            elif context.strategy == RecallStrategy.STRONGEST:
                query += " ORDER BY strength_current DESC"
            else:
                # Default to most relevant which will be calculated later
                query += " ORDER BY created_at DESC"

            # Apply limit
            query += f" LIMIT {context.max_results}"

            rows = await self.sql.fetchall(query, tuple(params))
            memories = [self._row_to_memory(tuple(row)) for row in rows]

            # If using MOST_RELEVANT strategy, we need to calculate relevance scores
            if context.strategy == RecallStrategy.MOST_RELEVANT:
                # Calculate relevance scores
                memories_with_scores = [
                    (
                        memory,
                        memory.get_relevance_score(
                            context.query, set(context.tags) if context.tags else None
                        ),
                    )
                    for memory in memories
                ]

                # Filter by minimum relevance
                memories_with_scores = [
                    (memory, score)
                    for memory, score in memories_with_scores
                    if score >= context.min_relevance
                ]

                # Sort by relevance score
                memories_with_scores.sort(key=lambda x: x[1], reverse=True)

                # Extract memories from the sorted list
                memories = [memory for memory, _ in memories_with_scores]

            # If using ASSOCIATIVE strategy, we would need to implement network traversal
            # This is a placeholder for that functionality
            if context.strategy == RecallStrategy.ASSOCIATIVE and context.query:
                # First, find memories that match the query directly
                seed_memories = memories[:5]  # Use top 5 as seeds

                # Then find associated memories (simplified implementation)
                associated_memories = []
                for memory in seed_memories:
                    associations = await self.find_associations(memory.id)
                    for assoc in associations:
                        other_id = (
                            assoc.target_id
                            if assoc.source_id == memory.id
                            else assoc.source_id
                        )
                        other_memory = await self.get_memory(other_id)
                        if (
                            other_memory
                            and other_memory not in associated_memories
                            and other_memory not in memories
                        ):
                            associated_memories.append(other_memory)

                # Combine and trim to max results
                memories = memories + associated_memories
                memories = memories[: context.max_results]

            # Record access for retrieved memories
            for memory in memories:
                memory.access()
                await self.update_memory(memory)

            return memories
        except Exception as e:
            logger.error(f"Error recalling memories: {e}")
            raise RepositoryError(
                message="Failed to recall memories",
                entity_type="Memory",
                operation="recall",
                details={"query": context.query},
                cause=e,
            ) from e

    async def find_by_tags(
        self: "SQLiteMemoryRepository", tags: set[str], match_all: bool = False
    ) -> list[Memory]:
        """
        Find memories with the specified tags.

        Args:
            tags: Set of tags to match
            match_all: If True, all tags must match; if False, any tag can match

        Returns:
            List of memories with matching tags

        Raises:
            RepositoryError: If an error occurs during retrieval
        """
        try:
            if not tags:
                return []

            # Base query
            query = "SELECT * FROM memories WHERE 1=1"
            params: list[str] = []

            if match_all:
                # For match_all, every tag must be present
                for tag in tags:
                    query += " AND tags LIKE ?"
                    params.append(f"%{tag}%")
            else:
                # For match_any, at least one tag must be present
                tag_conditions = []
                for tag in tags:
                    tag_conditions.append("tags LIKE ?")
                    params.append(f"%{tag}%")

                if tag_conditions:
                    tag_query = " OR ".join(tag_conditions)
                    query += f" AND ({tag_query})"

            rows = await self.sql.fetchall(query, tuple(params))
            return [self._row_to_memory(tuple(row)) for row in rows]
        except Exception as e:
            logger.error(f"Error finding memories by tags: {e}")
            raise RepositoryError(
                message="Failed to find memories by tags",
                entity_type="Memory",
                operation="find_by_tags",
                details={"tags": str(tags)},
                cause=e,
            ) from e

    async def find_by_type(
        self: "SQLiteMemoryRepository", memory_type: MemoryType
    ) -> list[Memory]:
        """
        Find memories of a specific type.

        Args:
            memory_type: The type of memories to find

        Returns:
            List of memories of the specified type

        Raises:
            RepositoryError: If an error occurs during retrieval
        """
        try:
            rows = await self.sql.fetchall(
                "SELECT * FROM memories WHERE type = ?", (memory_type.name,)
            )

            return [self._row_to_memory(tuple(row)) for row in rows]
        except Exception as e:
            logger.error(f"Error finding memories by type {memory_type}: {e}")
            raise RepositoryError(
                message="Failed to find memories by type",
                entity_type="Memory",
                operation="find_by_type",
                details={"type": memory_type.name},
                cause=e,
            ) from e

    async def find_strongest_associations(
        self: "SQLiteMemoryRepository",
        memory_id: UUID,
        association_type: AssociationType | None = None,
        limit: int = 10,
    ) -> list[tuple[MemoryAssociation, Memory]]:
        """
        Find the strongest associations for a memory.

        Args:
            memory_id: The UUID of the memory
            association_type: Optional type to filter by
            limit: Maximum number of results

        Returns:
            List of tuples containing (association, related_memory)

        Raises:
            RepositoryError: If an error occurs during retrieval
        """
        try:
            memory_id_str = str(memory_id)

            # Base query
            query = """
                SELECT a.* FROM memory_associations a
                WHERE (a.source_id = ? OR (a.target_id = ? AND a.bidirectional = 1))
            """
            params = [memory_id_str, memory_id_str]

            # Add type filter if provided
            if association_type:
                query += " AND a.association_type = ?"
                params.append(association_type.name)

            # Add sorting and limit
            query += " ORDER BY a.strength DESC LIMIT ?"
            params.append(str(limit))

            association_rows = await self.sql.fetchall(query, tuple(params))

            result = []
            for row in association_rows:
                association = self._row_to_association(tuple(row))

                # Determine which memory to fetch (the one that isn't the input memory_id)
                other_id = (
                    association.target_id
                    if str(association.source_id) == memory_id_str
                    else association.source_id
                )

                other_memory = await self.get_memory(other_id)
                if other_memory:
                    result.append((association, other_memory))

            return result
        except Exception as e:
            logger.error(
                f"Error finding strongest associations for memory {memory_id}: {e}"
            )
            raise RepositoryError(
                message="Failed to find strongest associations",
                entity_type="MemoryAssociation",
                operation="find_strongest",
                details={"memory_id": str(memory_id)},
                cause=e,
            ) from e

    def _row_to_memory(self: "SQLiteMemoryRepository", row: tuple[Any, ...]) -> Memory:
        """Convert a database row to a Memory entity."""
        # Extract row data (adjust indices based on the query structure)
        (
            id_str,
            content,
            type_name,
            source_id_str,
            created_at_str,
            updated_at_str,
            tags_json,
            metadata_json,
            strength_initial,
            strength_current,
            strength_last_accessed_str,
            strength_access_count,
        ) = row

        # Parse JSON fields
        tags = set(json.loads(tags_json))
        metadata = json.loads(metadata_json)

        # Parse datetime strings
        created_at = datetime.fromisoformat(created_at_str)
        updated_at = datetime.fromisoformat(updated_at_str) if updated_at_str else None
        last_accessed = datetime.fromisoformat(strength_last_accessed_str)

        # Create the memory strength value object
        strength = MemoryStrength(
            initial_value=strength_initial,
            current_value=strength_current,
            last_accessed=last_accessed,
            access_count=strength_access_count,
        )

        # Create and return the memory entity
        return Memory(
            id=UUID(id_str),
            content=content,
            type=MemoryType[type_name],
            source_id=UUID(source_id_str) if source_id_str else None,
            created_at=created_at,
            updated_at=updated_at,
            tags=tags,
            metadata=metadata,
            strength=strength,
        )

    def _row_to_association(
        self: "SQLiteMemoryRepository", row: tuple[Any, ...]
    ) -> MemoryAssociation:
        """Convert a database row to a MemoryAssociation entity."""
        # Extract row data (adjust indices based on the query structure)
        (
            id_str,
            source_id_str,
            target_id_str,
            association_type_name,
            created_at_str,
            updated_at_str,
            strength,
            bidirectional_int,
            context,
            metadata_json,
        ) = row

        # Parse JSON fields
        metadata = json.loads(metadata_json)

        # Parse datetime strings
        created_at = datetime.fromisoformat(created_at_str)
        updated_at = datetime.fromisoformat(updated_at_str) if updated_at_str else None

        # Convert SQLite integer to boolean
        bidirectional = bidirectional_int == 1

        # Create and return the association entity
        return MemoryAssociation(
            id=UUID(id_str),
            source_id=UUID(source_id_str),
            target_id=UUID(target_id_str),
            association_type=AssociationType[association_type_name],
            created_at=created_at,
            updated_at=updated_at,
            strength=strength,
            bidirectional=bidirectional,
            context=context,
            metadata=metadata,
        )
