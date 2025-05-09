from .file_code_artifact_repository import FileCodeArtifactRepository
from .sqlite_memory_repository import SQLiteMemoryRepository
from .sqlite_relationship_repository import SQLiteRelationshipRepository
from .sqlite_tag_hierarchy_repository import SQLiteTagHierarchyRepository
from .sqlite_tag_repository import SQLiteTagRepository

__all__ = [
    "FileCodeArtifactRepository",
    "SQLiteMemoryRepository",
    "SQLiteRelationshipRepository",
    "SQLiteTagHierarchyRepository",
    "SQLiteTagRepository",
]

"""Base repository interfaces for the infrastructure layer."""

from abc import ABC, abstractmethod
from typing import Generic, Optional, TypeVar
from uuid import UUID

T = TypeVar("T")  # Generic type for entity


class BaseRepository(ABC, Generic[T]):
    """Base repository interface defining common CRUD operations."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the repository."""
        pass

    @abstractmethod
    async def save(self, entity: T) -> UUID:
        """Save an entity."""
        pass

    @abstractmethod
    async def get(self, entity_id: UUID) -> T | None:
        """Get an entity by ID."""
        pass

    @abstractmethod
    async def update(self, entity: T) -> bool:
        """Update an entity."""
        pass

    @abstractmethod
    async def delete(self, entity_id: UUID) -> bool:
        """Delete an entity by ID."""
        pass


class BaseSQLiteRepository(BaseRepository[T]):
    """Base SQLite repository with common functionality."""

    def __init__(self, db_path: str):
        """Initialize the SQLite repository."""
        self.db_path = db_path

    async def _handle_repository_error(
        self, operation: str, entity_type: str, entity_id: str, error: Exception
    ) -> None:
        """Common error handling for repository operations."""
        from the_aichemist_codex.domain.exceptions.repository_exception import (
            RepositoryError,
        )

        raise RepositoryError(
            message=f"Failed to {operation} {entity_type}",
            entity_type=entity_type,
            operation=operation,
            entity_id=entity_id,
            cause=error,
        )
