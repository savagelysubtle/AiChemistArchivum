"""Version management for The Aichemist Codex.

This module provides the main interface (`VersionManager`) for creating,
retrieving, and managing file versions. It handles version storage (as
full snapshots or diffs), metadata tracking (`VersionMetadata`, `VersionGraph`),
and automatic versioning based on configurable change thresholds.
"""

import logging
from pathlib import Path

from the_aichemist_codex.infrastructure.config.settings import determine_project_root
from the_aichemist_codex.infrastructure.utils.io.async_io import AsyncFileIO

from .diff_engine import DiffEngine
from .metadata import VersionGraph, VersionMetadata, VersionType

logger = logging.getLogger(__name__)


class VersionManager:
    """Manages file versioning operations and policies.

    Provides an interface to create new file versions, retrieve specific
    versions, list version history, and automatically version files based
    on change detection. It utilizes `DiffEngine` for comparing versions
    and `AsyncFileIO` for storage operations.
    """

    def __init__(self) -> None:
        """Initializes the VersionManager.

        Sets up dependencies (`DiffEngine`, `AsyncFileIO`), determines project paths,
        and initializes the version graph cache and auto-versioning settings.
        Note: Directory creation here is synchronous, typically acceptable during startup.
        For fully async initialization, consider an `async def setup()` method.
        """
        self.diff_engine = DiffEngine()
        self.file_io = AsyncFileIO()

        # Get project root and set up version storage
        self.project_root = determine_project_root()
        self.versions_dir = self.project_root / "data" / "versions"
        self.metadata_dir = self.versions_dir / "metadata"

        # Ensure directories exist
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

        # Cache of version graphs
        self._version_graphs: dict[str, VersionGraph] = {}

        # Auto-versioning settings
        self.auto_versioning_enabled = True
        self.version_on_change_threshold = 5.0  # Percentage change to trigger version

    async def create_version(
        self,
        file_path: Path,
        manual: bool = False,
        annotation: str = "",
        author: str = "",
        tags: list[str] | None = None,
    ) -> VersionMetadata | None:
        """Create a new version of the specified file asynchronously.

        Checks if the file exists, determines the parent version, generates
        metadata, decides whether to store a full snapshot or a diff based
        on changes from the parent, saves the version data and metadata, and
        updates the version graph.

        Args:
            file_path: Absolute path to the file to version.
            manual: If True, mark as `VersionType.MANUAL`.
            annotation: A description of the changes for this version.
            author: Identifier for the user/process creating the version.
            tags: Optional list of tags to associate with this version.

        Returns:
            The `VersionMetadata` for the newly created version, or None if
            creation failed (e.g., file not found, storage error).
        """
        file_path = file_path.resolve()

        try:
            # Check if the file exists
            if not await self.file_io.exists(file_path):
                logger.error(
                    f"Cannot create version for non-existent file: {file_path}"
                )
                return None

            # Get the version graph for this file
            version_graph = await self._get_version_graph(file_path)

            # Get the current latest version as the parent
            latest_version = version_graph.get_latest_version()

            # Determine the version type
            version_type = VersionType.MANUAL if manual else VersionType.AUTOMATIC

            # Generate a version ID
            version_id = VersionMetadata.generate_version_id(file_path)

            # Create metadata
            metadata = VersionMetadata(
                version_id=version_id,
                file_path=file_path,
                version_type=version_type,
                parent_version_id=latest_version.version_id if latest_version else None,
                author=author,
                change_description=annotation,
                tags=tags or [],
            )

            # Determine how to store this version
            if latest_version:
                # We have a previous version - check if we should store as a diff
                await self._store_as_diff(file_path, metadata, latest_version)
            else:
                # This is the first version - store full file
                await self._store_full_file(file_path, metadata)

            # Update the version graph
            version_graph.add_version(metadata)
            await self._save_version_graph(version_graph)

            logger.info(f"Created version {metadata.version_id} for {file_path}")
            return metadata

        except Exception as e:
            logger.error(f"Error creating version for {file_path}: {e}")
            return None

    async def get_version(
        self, file_path: Path, version_id: str | None = None
    ) -> tuple[Path | None, VersionMetadata | None]:
        """Retrieve a specific version of a file asynchronously.

        Fetches the version metadata from the graph. If the version exists,
        it reconstructs the file content (either by copying a snapshot or
        rebuilding from diffs) into a temporary file.

        Args:
            file_path: Absolute path to the file whose version is needed.
            version_id: The ID of the specific version to retrieve. If None,
                retrieves the latest version on the main branch.

        Returns:
            A tuple containing:
            - The absolute path to the temporary file holding the reconstructed
              version content (or None if retrieval failed).
            - The `VersionMetadata` of the retrieved version (or None).
        """
        file_path = file_path.resolve()

        try:
            # Get the version graph
            version_graph = await self._get_version_graph(file_path)

            # Get the requested version metadata
            version_metadata = None
            if version_id:
                if version_id in version_graph.versions:
                    version_metadata = version_graph.versions[version_id]
                else:
                    logger.error(f"Version {version_id} not found for {file_path}")
                    return None, None
            else:
                # Get the latest version
                version_metadata = version_graph.get_latest_version()

            if not version_metadata:
                logger.error(f"No versions found for {file_path}")
                return None, None

            # Create a temporary file to hold the version contents
            temp_dir = self.project_root / "data" / "temp"
            await self.file_io.mkdir(temp_dir, parents=True, exist_ok=True)

            temp_file = temp_dir / f"{file_path.name}.{version_metadata.version_id}"

            # Check if this is a full snapshot or a diff
            if version_metadata.is_full_snapshot:
                # Copy the full file
                if not version_metadata.storage_path:
                    logger.error(
                        f"Storage path not set for version {version_metadata.version_id}"
                    )
                    return None, None

                await self.file_io.copy(version_metadata.storage_path, temp_file)
            else:
                # This is a diff - need to rebuild from the chain of diffs
                success = await self._rebuild_from_diffs(version_metadata, temp_file)
                if not success:
                    logger.error(
                        f"Failed to rebuild version {version_metadata.version_id} from diffs"
                    )
                    return None, None

            return temp_file, version_metadata

        except Exception as e:
            logger.error(f"Error retrieving version {version_id} for {file_path}: {e}")
            return None, None

    async def list_versions(self, file_path: Path) -> list[VersionMetadata]:
        """List all available versions of a file, sorted newest first.

        Retrieves the version graph for the file and returns a list of its
        version metadata objects, ordered by timestamp descending.

        Args:
            file_path: Absolute path to the file.

        Returns:
            A list of `VersionMetadata` objects, or an empty list if the file
            has no versions or an error occurs.
        """
        file_path = file_path.resolve()

        try:
            # Get the version graph
            version_graph = await self._get_version_graph(file_path)

            # Get all versions, sorted by timestamp (newest first)
            versions = list(version_graph.versions.values())
            versions.sort(key=lambda v: v.timestamp, reverse=True)

            return versions

        except Exception as e:
            logger.error(f"Error listing versions for {file_path}: {e}")
            return []

    async def should_auto_version(self, file_path: Path) -> bool:
        """Determine if a file should be automatically versioned based on changes.

        Checks if auto-versioning is enabled. If so, compares the current file
        content against the latest stored version using `DiffEngine`.

        Args:
            file_path: Absolute path to the file to check.

        Returns:
            True if auto-versioning is enabled and the change percentage meets
            or exceeds the configured threshold, or if it's the first version.
            False otherwise.
        """
        if not self.auto_versioning_enabled:
            return False

        try:
            # Get the version graph
            version_graph = await self._get_version_graph(file_path)

            # Get the latest version
            latest_version = version_graph.get_latest_version()
            if not latest_version:
                # No previous version - always create one
                return True

            # Get the storage path
            if not latest_version.storage_path or not await self.file_io.exists(
                latest_version.storage_path
            ):
                # Can't find the previous version - create a new one
                return True

            # Calculate the diff to see how much has changed
            diff_result = await self.diff_engine.calculate_diff(
                latest_version.storage_path, file_path
            )

            # If the change percentage exceeds the threshold, create a new version
            return diff_result.change_percentage >= self.version_on_change_threshold

        except Exception as e:
            logger.error(f"Error checking if {file_path} should be auto-versioned: {e}")
            # If in doubt, create a version
            return True

    async def _store_as_diff(
        self,
        file_path: Path,
        metadata: VersionMetadata,
        parent_metadata: VersionMetadata,
    ) -> bool:
        """Store a new version as a diff relative to its parent version.

        Calculates the diff between the current file and the parent version's
        stored content. If changes exist and the change percentage is below a
        threshold (currently 50%), the diff content is saved. Otherwise, falls
        back to storing a full snapshot via `_store_full_file`.

        Args:
            file_path: Absolute path to the current state of the file.
            metadata: The `VersionMetadata` object for the new version being created.
            parent_metadata: The `VersionMetadata` of the parent version.

        Returns:
            True if the diff (or fallback snapshot) was stored successfully,
            False otherwise (e.g., parent not found, no changes, storage error).
        """
        try:
            # Make sure the parent storage path exists
            if not parent_metadata.storage_path or not await self.file_io.exists(
                parent_metadata.storage_path
            ):
                logger.error(
                    f"Parent storage path not found for {parent_metadata.version_id}"
                )
                return False

            # Calculate the diff
            diff_result = await self.diff_engine.calculate_diff(
                parent_metadata.storage_path, file_path
            )

            # If there's no difference, return False - no need for a new version
            if not diff_result.is_different:
                logger.info(
                    f"No changes detected for {file_path}, skipping version creation"
                )
                return False

            # Set the change metrics
            metadata.change_percentage = diff_result.change_percentage
            metadata.change_size_bytes = diff_result.change_size_bytes

            # Determine if we should store as a full snapshot or a diff
            # For simplicity, we'll use a simple heuristic based on change percentage
            # In a real system, we'd have more sophisticated logic
            if diff_result.change_percentage > 50.0:
                # If more than 50% changed, store a full snapshot
                return await self._store_full_file(file_path, metadata)

            # Store as a diff
            metadata.is_full_snapshot = False

            # Create the storage directory for this file
            file_hash = file_path.name.replace(".", "_")
            version_dir = self.versions_dir / file_hash
            await self.file_io.mkdir(version_dir, parents=True, exist_ok=True)

            # Create the diff storage path
            diff_path = version_dir / f"{metadata.version_id}.diff"
            metadata.storage_path = diff_path

            # Store the diff
            await self.file_io.write(diff_path, diff_result.diff_content)

            return True

        except Exception as e:
            logger.error(f"Error storing diff for {file_path}: {e}")
            return False

    async def _store_full_file(
        self, file_path: Path, metadata: VersionMetadata
    ) -> bool:
        """Store a new version as a full snapshot (copy) of the current file.

        Creates the necessary version storage directory and copies the current
        file content to a uniquely named snapshot file.

        Args:
            file_path: Absolute path to the current state of the file.
            metadata: The `VersionMetadata` for the new version being created.

        Returns:
            True if the file was copied and metadata updated successfully,
            False on storage error.
        """
        try:
            # Create the storage directory for this file
            file_hash = file_path.name.replace(".", "_")
            version_dir = self.versions_dir / file_hash
            await self.file_io.mkdir(version_dir, parents=True, exist_ok=True)

            # Create the storage path
            storage_path = version_dir / f"{metadata.version_id}.snapshot"
            metadata.storage_path = storage_path

            # Copy the file
            metadata.is_full_snapshot = True
            await self.file_io.copy(file_path, storage_path)

            return True

        except Exception as e:
            logger.error(f"Error storing full file for {file_path}: {e}")
            return False

    async def _rebuild_from_diffs(
        self, target_metadata: VersionMetadata, output_path: Path
    ) -> bool:
        """Reconstruct a specific file version by applying diffs from a base snapshot.

        Finds the version history chain leading to the `target_metadata`.
        Locates the nearest ancestor full snapshot, copies it to `output_path`,
        and then sequentially applies all subsequent diffs in the chain until
        the target version is reconstructed.

        Args:
            target_metadata: Metadata of the version to reconstruct.
            output_path: The file path where the reconstructed version content
                will be written.

        Returns:
            True if reconstruction was successful, False otherwise (e.g., missing
            snapshot/diff, diff application error).
        """
        try:
            # Get the version graph
            version_graph = await self._get_version_graph(target_metadata.file_path)

            # Get the version chain
            version_chain = version_graph.get_version_chain(target_metadata.version_id)
            if not version_chain:
                logger.error(
                    f"Could not find version chain for {target_metadata.version_id}"
                )
                return False

            # Find the most recent full snapshot in the chain
            snapshot_index = -1
            for i, version in enumerate(version_chain):
                if version.is_full_snapshot:
                    snapshot_index = i
                    break

            if snapshot_index == -1:
                logger.error(
                    f"No full snapshot found in version chain for {target_metadata.version_id}"
                )
                return False

            # Start with the snapshot
            snapshot = version_chain[snapshot_index]
            if not snapshot.storage_path or not await self.file_io.exists(
                snapshot.storage_path
            ):
                logger.error(
                    f"Snapshot storage path not found for {snapshot.version_id}"
                )
                return False

            # Copy the snapshot to the output path
            await self.file_io.copy(snapshot.storage_path, output_path)

            # Apply each diff in sequence
            for i in range(snapshot_index + 1, len(version_chain)):
                version = version_chain[i]
                if version.is_full_snapshot:
                    # If we hit another full snapshot, copy it directly
                    if version.storage_path:
                        await self.file_io.copy(version.storage_path, output_path)
                    else:
                        logger.error(
                            f"Storage path not found for snapshot {version.version_id}"
                        )
                        return False
                    continue

                if not version.storage_path or not await self.file_io.exists(
                    version.storage_path
                ):
                    logger.error(
                        f"Diff storage path not found for {version.version_id}"
                    )
                    return False

                # Create a temporary path for the intermediate result
                temp_path = output_path.parent / f"{output_path.name}.tmp"

                # Apply the diff
                success = await self.diff_engine.apply_diff(
                    output_path, version.storage_path, temp_path
                )

                if not success:
                    logger.error(f"Failed to apply diff {version.version_id}")
                    return False

                # Replace the output with the new version
                await self.file_io.copy(temp_path, output_path)

                # Clean up the temp file
                try:
                    await self.file_io.remove(temp_path)
                except (OSError, FileNotFoundError):
                    pass

            return True

        except Exception as e:
            logger.error(f"Error rebuilding from diffs: {e}")
            return False

    async def _get_version_graph(self, file_path: Path) -> VersionGraph:
        """Retrieve or load the version graph for a specific file.

        Checks an in-memory cache first. If not found, attempts to load the
        graph from its corresponding JSON file in the metadata directory.
        If the file doesn't exist or loading fails, creates a new empty graph.

        Args:
            file_path: Absolute path to the file whose graph is needed.

        Returns:
            The `VersionGraph` object for the file.
        """
        file_path = file_path.resolve()
        key = str(file_path)

        # Check if we have it in memory
        if key in self._version_graphs:
            return self._version_graphs[key]

        # Load it from disk or create a new one
        graph_path = self._get_graph_file_path(file_path)

        if await self.file_io.exists(graph_path):
            try:
                # Load from disk
                json_data = await self.file_io.read_json(graph_path)
                graph = VersionGraph.from_dict(json_data)
                self._version_graphs[key] = graph
                return graph
            except Exception as e:
                logger.error(f"Error loading version graph for {file_path}: {e}")
                # Fall through to create a new one

        # Create a new graph
        graph = VersionGraph(file_path)
        self._version_graphs[key] = graph
        return graph

    async def _save_version_graph(self, graph: VersionGraph) -> bool:
        """Save a version graph to disk.

        Args:
            graph: VersionGraph to save

        Returns:
            True if successful, False otherwise
        """
        try:
            graph_path = self._get_graph_file_path(graph.file_path)
            json_data = graph.to_dict()

            return await self.file_io.write_json(graph_path, json_data)

        except Exception as e:
            logger.error(f"Error saving version graph for {graph.file_path}: {e}")
            return False

    def _get_graph_file_path(self, file_path: Path) -> Path:
        """Construct the path to the metadata file for a given version graph.

        Creates a unique filename based on the hashed absolute path of the
        original file to store its version graph metadata.

        Args:
            file_path: Absolute path to the file.

        Returns:
            The absolute path to the corresponding metadata JSON file.
        """
        # Create a unique filename based on the full path
        file_path_str = str(file_path.resolve())
        file_hash = file_path_str.replace(":", "_").replace("/", "_").replace("\\", "_")

        return self.metadata_dir / f"{file_hash}.json"


# Create a singleton instance for application-wide use
version_manager = VersionManager()
