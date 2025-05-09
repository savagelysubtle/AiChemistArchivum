"""File-based implementation of the CodeArtifactRepository interface."""

import logging
from pathlib import Path
from typing import Any
from uuid import UUID

from the_aichemist_codex.domain.entities.code_artifact import CodeArtifact
from the_aichemist_codex.domain.exceptions.repository_exception import RepositoryError
from the_aichemist_codex.domain.repositories.code_artifact_repository import (
    CodeArtifactRepository,
)
from the_aichemist_codex.infrastructure.utils.io.async_io import AsyncFileIO

logger = logging.getLogger(__name__)


class FileCodeArtifactRepository(CodeArtifactRepository):
    """File-based implementation of the CodeArtifactRepository interface.

    This implementation stores code artifacts as JSON files in a local directory.
    Each artifact is stored in a file named with its UUID.
    """

    def __init__(self, storage_dir: Path) -> None:
        """Initialize the repository.

        Args:
            storage_dir: The directory where artifacts will be stored

        Raises:
            RepositoryError: If the storage directory cannot be created or accessed
        """
        self.storage_dir = storage_dir
        self.async_io = AsyncFileIO(storage_dir)

        # In-memory cache to speed up lookups
        self._cache: dict[str, CodeArtifact] = {}
        self._path_index: dict[str, str] = {}  # Maps path string to ID string
        self._name_index: dict[str, list[str]] = {}  # Maps name to list of ID strings

    async def _ensure_storage_dir_exists(self) -> None:
        """Ensure the storage directory exists.

        Raises:
            RepositoryError: If the directory cannot be created or accessed
        """
        try:
            await self.async_io.makedirs(self.storage_dir, exist_ok=True)
        except Exception as e:
            raise RepositoryError(
                message="Failed to create storage directory",
                entity_type="CodeArtifact",
                operation="initialize",
                details={"storage_dir": str(self.storage_dir)},
                cause=e,
            ) from e

    def _get_artifact_path(self, artifact_id: UUID) -> Path:
        """Get the file path for an artifact.

        Args:
            artifact_id: The ID of the artifact

        Returns:
            The path to the artifact file
        """
        return self.storage_dir / f"{artifact_id!s}.json"

    def _serialize_artifact(self, artifact: CodeArtifact) -> dict[str, Any]:
        """Serialize a code artifact to a dictionary.

        Args:
            artifact: The artifact to serialize

        Returns:
            A dictionary representation of the artifact
        """
        return {
            "id": str(artifact.id),
            "name": artifact.name,
            "path": str(artifact.path),
            "artifact_type": artifact.artifact_type,
            "content": artifact.content,
            "metadata": artifact.metadata,
            "is_valid": artifact.is_valid,
        }

    def _deserialize_artifact(self, data: dict[str, Any]) -> CodeArtifact:
        """Deserialize a code artifact from a dictionary.

        Args:
            data: The dictionary representation of the artifact

        Returns:
            The deserialized code artifact

        Raises:
            RepositoryError: If the artifact cannot be deserialized
        """
        try:
            return CodeArtifact(
                id=UUID(data["id"]),
                name=data["name"],
                path=Path(data["path"]),
                artifact_type=data["artifact_type"],
                content=data["content"],
                metadata=data["metadata"],
                is_valid=data["is_valid"],
            )
        except (KeyError, ValueError, TypeError) as e:
            raise RepositoryError(
                message="Failed to deserialize artifact",
                entity_type="CodeArtifact",
                operation="deserialize",
                details={"data": str(data)},
                cause=e,
            ) from e

    async def save(self, artifact: CodeArtifact) -> CodeArtifact:
        """Save a code artifact to the repository.

        Args:
            artifact: The code artifact to save

        Returns:
            The saved code artifact with any updates

        Raises:
            RepositoryError: If the artifact cannot be saved
        """
        try:
            await self._ensure_storage_dir_exists()

            # Serialize the artifact
            data = self._serialize_artifact(artifact)

            # Save to file
            artifact_path = self._get_artifact_path(artifact.id)
            await self.async_io.write_json(artifact_path, data)

            # Update cache and indexes
            artifact_id_str = str(artifact.id)
            self._cache[artifact_id_str] = artifact
            self._path_index[str(artifact.path)] = artifact_id_str

            if artifact.name not in self._name_index:
                self._name_index[artifact.name] = []
            if artifact_id_str not in self._name_index[artifact.name]:
                self._name_index[artifact.name].append(artifact_id_str)

            return artifact
        except Exception as e:
            raise RepositoryError(
                message="Failed to save artifact",
                entity_type="CodeArtifact",
                operation="save",
                entity_id=str(artifact.id),
                details={"path": str(artifact.path)},
                cause=e,
            ) from e

    async def get_by_id(self, artifact_id: UUID) -> CodeArtifact | None:
        """Get a code artifact by its ID.

        Args:
            artifact_id: The ID of the artifact to retrieve

        Returns:
            The code artifact if found, None otherwise

        Raises:
            RepositoryError: If an error occurs while retrieving the artifact
        """
        artifact_id_str = str(artifact_id)

        # Check the cache first
        if artifact_id_str in self._cache:
            return self._cache[artifact_id_str]

        # Load from file
        artifact_path = self._get_artifact_path(artifact_id)
        try:
            if not await self.async_io.exists(artifact_path):
                return None

            data = await self.async_io.read_json(artifact_path)
            artifact = self._deserialize_artifact(data)

            # Update cache and indexes
            self._cache[artifact_id_str] = artifact
            self._path_index[str(artifact.path)] = artifact_id_str

            if artifact.name not in self._name_index:
                self._name_index[artifact.name] = []
            if artifact_id_str not in self._name_index[artifact.name]:
                self._name_index[artifact.name].append(artifact_id_str)

            return artifact
        except Exception as e:
            raise RepositoryError(
                message="Failed to load artifact",
                entity_type="CodeArtifact",
                operation="get_by_id",
                entity_id=artifact_id_str,
                cause=e,
            ) from e

    async def get_by_path(self, path: Path) -> CodeArtifact | None:
        """Get a code artifact by its path.

        Args:
            path: The path of the artifact to retrieve

        Returns:
            The code artifact if found, None otherwise

        Raises:
            RepositoryError: If an error occurs while retrieving the artifact
        """
        path_str = str(path)

        # Check the path index
        if path_str in self._path_index:
            artifact_id_str = self._path_index[path_str]
            return await self.get_by_id(UUID(artifact_id_str))

        # If not in index, scan all artifacts
        try:
            artifact_ids = await self._list_artifact_ids()
            for artifact_id_str in artifact_ids:
                artifact = await self.get_by_id(UUID(artifact_id_str))
                if artifact and str(artifact.path) == path_str:
                    # Update path index for future lookups
                    self._path_index[path_str] = artifact_id_str
                    return artifact

            return None
        except Exception as e:
            raise RepositoryError(
                message="Failed to search artifacts by path",
                entity_type="CodeArtifact",
                operation="get_by_path",
                details={"path": path_str},
                cause=e,
            ) from e

    async def _list_artifact_ids(self) -> list[str]:
        """List all artifact IDs in the repository.

        Returns:
            A list of artifact ID strings
        """
        try:
            files = await self.async_io.glob("*.json")
            return [f.stem for f in files]
        except Exception as e:
            raise RepositoryError(
                message="Failed to list artifacts",
                entity_type="CodeArtifact",
                operation="list",
                cause=e,
            ) from e

    async def get_by_name(self, name: str) -> list[CodeArtifact]:
        """Retrieve code artifacts by name.

        Args:
            name: The name of the artifact(s) to retrieve

        Returns:
            A list of matching CodeArtifact objects

        Raises:
            RepositoryError: If an error occurs during retrieval
        """
        try:
            # Check the name index
            artifact_ids = self._name_index.get(name, [])

            # Build list of artifacts
            results = []
            for artifact_id in artifact_ids:
                artifact = await self.get_by_id(UUID(artifact_id))
                if artifact is not None:
                    results.append(artifact)

            return results
        except Exception as e:
            raise RepositoryError(
                message=f"Failed to retrieve artifacts with name '{name}'",
                entity_type="CodeArtifact",
                operation="get_by_name",
                details={"name": name, "error": str(e)},
                cause=e,
            ) from e

    async def find_all(self) -> list[CodeArtifact]:
        """Retrieve all code artifacts in the repository.

        Returns:
            A list of all CodeArtifact objects in the repository

        Raises:
            RepositoryError: If an error occurs during retrieval
        """
        try:
            # List all JSON files in the directory
            json_files = await self.async_io.glob("*.json")

            results = []
            for file_path in json_files:
                try:
                    artifact_id = UUID(file_path.stem)
                    artifact = await self.get_by_id(artifact_id)
                    if artifact is not None:
                        results.append(artifact)
                except ValueError:
                    # Not a valid UUID, skip this file
                    continue

            return results
        except Exception as e:
            raise RepositoryError(
                message="Failed to retrieve all artifacts",
                entity_type="CodeArtifact",
                operation="find_all",
                details={"error": str(e)},
                cause=e,
            ) from e

    async def find_by_criteria(self, criteria: dict) -> list[CodeArtifact]:
        """Find code artifacts matching the given criteria.

        Args:
            criteria: A dictionary of attribute name to expected value

        Returns:
            A list of matching CodeArtifact objects

        Raises:
            RepositoryError: If an error occurs during search
        """
        try:
            all_artifacts = await self.find_all()
            results = []

            for artifact in all_artifacts:
                match = True
                for key, value in criteria.items():
                    if not hasattr(artifact, key) or getattr(artifact, key) != value:
                        match = False
                        break

                if match:
                    results.append(artifact)

            return results
        except Exception as e:
            raise RepositoryError(
                message="Failed to find artifacts by criteria",
                entity_type="CodeArtifact",
                operation="find_by_criteria",
                details={"criteria": str(criteria), "error": str(e)},
                cause=e,
            ) from e

    async def delete(self, artifact_id: UUID) -> bool:
        """Delete a code artifact by its ID.

        Args:
            artifact_id: The ID of the artifact to delete

        Returns:
            True if the artifact was deleted, False otherwise

        Raises:
            RepositoryError: If an error occurs while deleting the artifact
        """
        artifact_id_str = str(artifact_id)

        # Get the artifact first to update indexes
        artifact = await self.get_by_id(artifact_id)
        if not artifact:
            return False

        try:
            # Remove from cache and indexes
            if artifact_id_str in self._cache:
                del self._cache[artifact_id_str]

            path_str = str(artifact.path)
            if path_str in self._path_index:
                del self._path_index[path_str]

            if (
                artifact.name in self._name_index
                and artifact_id_str in self._name_index[artifact.name]
            ):
                self._name_index[artifact.name].remove(artifact_id_str)
                if not self._name_index[artifact.name]:
                    del self._name_index[artifact.name]

            # Delete the file
            artifact_path = self._get_artifact_path(artifact_id)
            if await self.async_io.exists(artifact_path):
                await self.async_io.remove(artifact_path)

            return True
        except Exception as e:
            raise RepositoryError(
                message="Failed to delete artifact",
                entity_type="CodeArtifact",
                operation="delete",
                entity_id=artifact_id_str,
                cause=e,
            ) from e

    async def get_children(self, parent_id: UUID) -> list[CodeArtifact]:
        """Get child artifacts of a parent artifact.

        Args:
            parent_id: The ID of the parent artifact

        Returns:
            A list of child artifacts

        Raises:
            RepositoryError: If an error occurs while retrieving the children
        """
        try:
            # This implementation doesn't store parent-child relationships directly
            # We need to scan all artifacts and check their parent ID
            # In a real implementation, we would use a more efficient approach
            return []  # Placeholder implementation
        except Exception as e:
            raise RepositoryError(
                message="Failed to retrieve child artifacts",
                entity_type="CodeArtifact",
                operation="get_children",
                entity_id=str(parent_id),
                cause=e,
            ) from e

    async def get_dependencies(self, artifact_id: UUID) -> list[CodeArtifact]:
        """Get dependencies of an artifact.

        Args:
            artifact_id: The ID of the artifact

        Returns:
            A list of artifacts that the given artifact depends on

        Raises:
            RepositoryError: If an error occurs while retrieving the dependencies
        """
        try:
            # This implementation doesn't store dependency relationships directly
            # We would need to implement a separate DependencyRepository to handle this
            return []  # Placeholder implementation
        except Exception as e:
            raise RepositoryError(
                message="Failed to retrieve artifact dependencies",
                entity_type="CodeArtifact",
                operation="get_dependencies",
                entity_id=str(artifact_id),
                cause=e,
            ) from e

    async def get_dependents(self, artifact_id: UUID) -> list[CodeArtifact]:
        """Get artifacts that depend on an artifact.

        Args:
            artifact_id: The ID of the artifact

        Returns:
            A list of artifacts that depend on the given artifact

        Raises:
            RepositoryError: If an error occurs while retrieving the dependents
        """
        try:
            # This implementation doesn't store dependency relationships directly
            # We would need to implement a separate DependencyRepository to handle this
            return []  # Placeholder implementation
        except Exception as e:
            raise RepositoryError(
                message="Failed to retrieve artifact dependents",
                entity_type="CodeArtifact",
                operation="get_dependents",
                entity_id=str(artifact_id),
                cause=e,
            ) from e
