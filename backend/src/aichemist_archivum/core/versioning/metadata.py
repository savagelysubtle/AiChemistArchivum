"""Version metadata tracking for The Aichemist Codex.

This module defines the data structures (`Enum`, `dataclass`) used for tracking
version metadata, version history graphs, and rollback results within the
versioning system. It includes serialization/deserialization logic for persistence.
"""

import datetime
import hashlib
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class VersionType(Enum):
    """Enumerates the different origins or reasons for creating a file version."""

    AUTOMATIC = "automatic"  # Created automatically based on change detection
    MANUAL = "manual"  # Created manually by the user
    SCHEDULED = "scheduled"  # Created by scheduled job
    SYSTEM = "system"  # Created by system operations
    ROLLBACK = "rollback"  # Created during a rollback operation


@dataclass
class VersionMetadata:
    """Stores comprehensive metadata associated with a single file version.

    This dataclass holds information about the version's identity, creation
    details, relationship to other versions, content changes, and storage specifics.

    Attributes:
        version_id: Unique SHA-based identifier for this specific version.
        file_path: The absolute path to the original file this version corresponds to.
        timestamp: The date and time when this version was created.
        version_type: The `VersionType` indicating how this version was initiated.
        parent_version_id: The `version_id` of the preceding version in the history,
            if any. None for the initial version.
        author: Identifier for the user or process that triggered this version creation.
        change_description: A brief description or annotation of the changes in this version.
        change_size_bytes: The size of the change (e.g., diff size) in bytes.
        change_percentage: The percentage of the file content that changed compared
            to the parent version.
        tags: A list of arbitrary string tags for categorization or filtering.
        annotations: A dictionary for storing additional custom key-value metadata.
        storage_path: The absolute path to where the content of this version is stored
            (either a full snapshot or a diff file).
        is_full_snapshot: Boolean flag; True if `storage_path` points to a complete
            copy of the file, False if it points to a diff relative to the parent.
    """

    # Core identification
    version_id: str  # Unique identifier for this version
    file_path: Path  # Path to the original file
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)

    # Version details
    version_type: VersionType = VersionType.AUTOMATIC
    parent_version_id: str | None = None  # Previous version

    # Change information
    author: str = ""
    change_description: str = ""
    change_size_bytes: int = 0
    change_percentage: float = 0.0

    # Additional metadata
    tags: list[str] = field(default_factory=list)
    annotations: dict[str, Any] = field(default_factory=dict)

    # Storage details
    storage_path: Path | None = None  # Where this version is stored
    is_full_snapshot: bool = True  # If False, stored as diff from parent

    @classmethod
    def generate_version_id(
        cls, file_path: Path, timestamp: datetime.datetime | None = None
    ) -> str:
        """Generate a unique, content-agnostic version ID.

        Creates a short SHA-256 hash based on the file path, a precise timestamp,
        and a random component to ensure uniqueness even for rapid changes.

        Args:
            file_path: The absolute path of the file being versioned.
            timestamp: The timestamp for the version creation. Defaults to now().

        Returns:
            A 16-character hexadecimal string representing the version ID.
        """
        if timestamp is None:
            timestamp = datetime.datetime.now()

        # Combine file path, timestamp, and a random component
        timestamp_str = timestamp.isoformat()
        random_component = str(uuid.uuid4())[:8]

        # Create a hash from the combined data
        hash_input = f"{file_path}:{timestamp_str}:{random_component}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the metadata object to a dictionary for persistence (e.g., JSON).

        Converts complex types like `Path`, `datetime`, and `Enum` to string
        representations suitable for storage.

        Returns:
            A dictionary containing the serialized metadata.
        """
        result = asdict(self)

        # Convert Path objects to strings
        result["file_path"] = str(self.file_path)
        if self.storage_path:
            result["storage_path"] = str(self.storage_path)

        # Convert Enum to string
        result["version_type"] = self.version_type.value

        # Convert datetime to ISO format
        result["timestamp"] = self.timestamp.isoformat()

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VersionMetadata":
        """Deserialize a dictionary (e.g., from JSON) back into a VersionMetadata object.

        Handles the conversion of string representations back into their corresponding
        `Path`, `datetime`, and `Enum` types.

        Args:
            data: The dictionary containing the serialized metadata.

        Returns:
            A new `VersionMetadata` instance populated from the dictionary.

        Raises:
            ValueError: If the `version_type` string is not a valid `VersionType`.
            TypeError: If the `timestamp` string is not a valid ISO 8601 format.
        """
        # Copy the dictionary to avoid modifying the original
        data_copy = data.copy()

        # Convert string paths back to Path objects
        data_copy["file_path"] = Path(data_copy["file_path"])
        if data_copy.get("storage_path"):
            data_copy["storage_path"] = Path(data_copy["storage_path"])

        # Convert string version type back to enum
        data_copy["version_type"] = VersionType(data_copy["version_type"])

        # Convert ISO timestamp back to datetime
        data_copy["timestamp"] = datetime.datetime.fromisoformat(data_copy["timestamp"])

        return cls(**data_copy)

    def __str__(self) -> str:
        """Provide a concise, human-readable string representation.

        Example: "Version abc123def456 of config.py (2023-10-27 10:00:00, manual)"
        """
        time_str = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        return (
            f"Version {self.version_id} of {self.file_path.name} "
            f"({time_str}, {self.version_type.value})"
        )


@dataclass
class VersionGraph:
    """Represents the version history for a single file, including branches.

    Maintains a collection of all `VersionMetadata` objects for a file and
    organizes them into branches (currently only a single 'main' branch is implemented).

    Attributes:
        file_path: The absolute path of the file whose history this graph tracks.
        versions: A dictionary mapping version IDs (str) to `VersionMetadata` objects.
        branches: A dictionary mapping branch names (str) to lists of ordered version IDs.
    """

    file_path: Path
    versions: dict[str, VersionMetadata] = field(default_factory=dict)
    branches: dict[str, list[str]] = field(default_factory=dict)

    def add_version(self, metadata: VersionMetadata) -> None:
        """Add a new version's metadata to the graph.

        Stores the metadata in the `versions` dictionary and appends its ID to the
        appropriate branch list (currently defaults to 'main').

        Args:
            metadata: The `VersionMetadata` object for the version to add.
        """
        self.versions[metadata.version_id] = metadata

        # Update branch information
        branch_name = "main"  # Default branch
        if metadata.parent_version_id:
            # Find which branch the parent is on
            for br_name, version_ids in self.branches.items():
                if metadata.parent_version_id in version_ids:
                    branch_name = br_name
                    break

        # Add this version to the appropriate branch
        if branch_name not in self.branches:
            self.branches[branch_name] = []
        self.branches[branch_name].append(metadata.version_id)

    def get_latest_version(self, branch: str = "main") -> VersionMetadata | None:
        """Retrieve the metadata for the latest version on a specified branch.

        Args:
            branch: The name of the branch (defaults to 'main').

        Returns:
            The `VersionMetadata` of the latest version on the branch, or None
            if the branch is empty or does not exist.
        """
        if branch not in self.branches or not self.branches[branch]:
            return None

        latest_version_id = self.branches[branch][-1]
        return self.versions.get(latest_version_id)

    def get_version_chain(self, version_id: str) -> list[VersionMetadata]:
        """Retrieve the linear sequence of versions leading up to a specific version ID.

        Traverses the parent links from the specified version back to the initial
        version (where `parent_version_id` is None).

        Args:
            version_id: The ID of the target version.

        Returns:
            A list of `VersionMetadata` objects representing the history in
            chronological order (oldest first), or an empty list if the
            `version_id` is not found.
        """
        if version_id not in self.versions:
            return []

        result = []
        current_id = version_id

        # Follow the parent chain
        while current_id:
            if current_id not in self.versions:
                break

            current_version = self.versions[current_id]
            result.append(current_version)
            current_id = current_version.parent_version_id

        # Reverse to get chronological order
        return list(reversed(result))

    def to_dict(self) -> dict[str, Any]:
        """Serialize the version graph to a dictionary for persistence.

        Converts the `file_path` and all contained `VersionMetadata` objects
        into serializable formats.

        Returns:
            A dictionary representation of the version graph.
        """
        return {
            "file_path": str(self.file_path),
            "versions": {k: v.to_dict() for k, v in self.versions.items()},
            "branches": self.branches,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VersionGraph":
        """Deserialize a dictionary back into a `VersionGraph` object.

        Reconstructs the graph structure, converting serialized paths and
        version metadata back into their object forms.

        Args:
            data: The dictionary containing the serialized version graph.

        Returns:
            A new `VersionGraph` instance populated from the dictionary.
        """
        graph = cls(Path(data["file_path"]))
        graph.branches = data["branches"]

        for version_id, version_data in data["versions"].items():
            graph.versions[version_id] = VersionMetadata.from_dict(version_data)

        return graph


@dataclass
class RollbackResult:
    """Represents the outcome of a single file rollback operation.

    Used by `RollbackEngine` to report the success or failure of rolling
    back one file.

    Attributes:
        success: True if the rollback for this file was successful, False otherwise.
        file_path: The absolute path to the file that was targeted for rollback.
        target_version_id: The ID of the version that was attempted to be restored.
        current_version_id: The ID of the version the file is now at after the
            operation (might be the target_version_id or a new version ID if a
            new version was created post-rollback).
        error_message: A description of the error if `success` is False.
        affected_files: Typically just contains `file_path`, but available for future use.
        created_backup: If a backup was created during the rollback, this holds
            the absolute path to the backup file.
    """

    success: bool
    file_path: Path
    target_version_id: str
    current_version_id: str | None = None
    error_message: str = ""
    affected_files: list[Path] = field(default_factory=list)
    created_backup: Path | None = None
