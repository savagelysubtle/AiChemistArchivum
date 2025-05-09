"""Rollback engine for The Aichemist Codex.

This module provides the core functionality for rolling back files to specific
versions managed by the `VersionManager`. It supports different rollback strategies,
including single-file rollback, backups, staging, and transactional bulk rollback.
"""

import datetime
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from the_aichemist_codex.infrastructure.config.settings import determine_project_root
from the_aichemist_codex.infrastructure.utils.io.async_io import AsyncFileIO

from ..metadata import RollbackResult
from ..version_manager import version_manager

logger = logging.getLogger(__name__)


class RollbackStrategy(Enum):
    """Strategies for performing rollbacks."""

    COPY = "copy"  # Direct copy of the version to the target
    BACKUP_AND_COPY = "backup_and_copy"  # Create a backup before replacing
    STAGED = "staged"  # Stage the rollback in a separate location
    TRANSACTION = "transaction"  # Only commit if all files succeed


@dataclass
class RollbackSpec:
    """Defines the parameters for rolling back a single file.

    Attributes:
        file_path: The absolute path to the file to be rolled back.
        version_id: The unique ID of the target version to restore.
        strategy: The strategy to use for the rollback operation.
        backup_path: If a backup is created, this holds the path to the backup file.
            This is typically set by the `RollbackEngine`.
    """

    file_path: Path
    version_id: str
    strategy: RollbackStrategy = RollbackStrategy.BACKUP_AND_COPY
    backup_path: Path | None = None


@dataclass
class BulkRollbackResult:
    """Holds the results of a bulk rollback operation.

    Attributes:
        success: True if the overall bulk operation (potentially transactional)
            was successful, False otherwise.
        results: A list of `RollbackResult` objects, one for each file processed.
        transaction_id: A unique identifier for the transaction, if applicable.
        error_message: An error message summarizing the failure, if `success` is False.
        rollback_timestamp: The timestamp when the bulk rollback operation was initiated.
    """

    success: bool
    results: list[RollbackResult]
    transaction_id: str = ""
    error_message: str = ""
    rollback_timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)


class RollbackEngine:
    """Handles the logic for executing file rollback operations.

    Provides methods for rolling back individual files or multiple files
    atomically using different strategies. Interacts with the `VersionManager`
    to retrieve version data and `AsyncFileIO` for file operations.
    """

    def __init__(self):
        """Initialize the rollback engine."""
        self.file_io = AsyncFileIO()
        self.project_root = determine_project_root()
        self.backup_dir = self.project_root / "data" / "rollback_backups"
        self.staging_dir = self.project_root / "data" / "rollback_staging"

        # Ensure directories exist
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.staging_dir.mkdir(parents=True, exist_ok=True)

    async def rollback_file(
        self,
        file_path: Path,
        version_id: str,
        strategy: RollbackStrategy = RollbackStrategy.BACKUP_AND_COPY,
        dry_run: bool = False,
    ) -> RollbackResult:
        """Roll back a single file to a specified version asynchronously.

        Retrieves the specified version's content from the `VersionManager`
        and replaces the current file content based on the chosen strategy.
        Optionally creates a backup or stages the change.

        Args:
            file_path: The absolute path to the file to roll back.
            version_id: The ID of the target version to restore.
            strategy: The `RollbackStrategy` to use (e.g., COPY, BACKUP_AND_COPY).
            dry_run: If True, simulates the rollback without making changes
                and returns a success result.

        Returns:
            A `RollbackResult` object detailing the success or failure of the
            operation, including any backup path created.
        """
        file_path = file_path.resolve()

        try:
            # First, check if the file exists
            if (
                not await self.file_io.exists(file_path)
                and strategy != RollbackStrategy.COPY
            ):
                return RollbackResult(
                    success=False,
                    file_path=file_path,
                    target_version_id=version_id,
                    error_message=f"File does not exist: {file_path}",
                )

            # Get the version to roll back to
            version_file, version_metadata = await version_manager.get_version(
                file_path, version_id
            )

            if not version_file or not version_metadata:
                return RollbackResult(
                    success=False,
                    file_path=file_path,
                    target_version_id=version_id,
                    error_message=f"Version {version_id} not found for {file_path}",
                )

            # If this is a dry run, just return success
            if dry_run:
                return RollbackResult(
                    success=True,
                    file_path=file_path,
                    target_version_id=version_id,
                    current_version_id=version_id,
                    error_message="Dry run - no changes made",
                )

            # Perform the rollback according to the selected strategy
            if strategy == RollbackStrategy.COPY:
                # Direct copy
                await self.file_io.copy(version_file, file_path)

            elif strategy == RollbackStrategy.BACKUP_AND_COPY:
                # Create a backup before replacing
                backup_path = await self._create_backup(file_path)
                await self.file_io.copy(version_file, file_path)

                return RollbackResult(
                    success=True,
                    file_path=file_path,
                    target_version_id=version_id,
                    current_version_id=version_id,
                    created_backup=backup_path,
                )

            elif strategy == RollbackStrategy.STAGED:
                # Stage the rollback in a separate location
                staged_path = self._get_staged_path(file_path)
                await self.file_io.copy(version_file, staged_path)

                return RollbackResult(
                    success=True,
                    file_path=file_path,
                    target_version_id=version_id,
                    current_version_id=version_id,
                    error_message=f"Staged at {staged_path}",
                )

            # After rolling back, create a new version to record the rollback
            if strategy != RollbackStrategy.STAGED:
                await version_manager.create_version(
                    file_path,
                    manual=True,
                    annotation=f"Rolled back to version {version_id}",
                    tags=["rollback", f"from_{version_id}"],
                )

            return RollbackResult(
                success=True,
                file_path=file_path,
                target_version_id=version_id,
                current_version_id=version_id,
            )

        except Exception as e:
            logger.error(f"Error rolling back {file_path} to version {version_id}: {e}")
            return RollbackResult(
                success=False,
                file_path=file_path,
                target_version_id=version_id,
                error_message=str(e),
            )

    async def rollback_bulk(
        self, specs: list[RollbackSpec], transaction: bool = True, dry_run: bool = False
    ) -> BulkRollbackResult:
        """Roll back multiple files, optionally ensuring atomicity via staging.

        Processes a list of `RollbackSpec` objects. If `transaction` is True,
        it first stages all rollbacks. Only if all staging operations succeed
        does it commit the changes by copying staged files to their final
        destinations. If `transaction` is False or `dry_run` is True, it processes
        each spec individually using `rollback_file`.

        Args:
            specs: A list of `RollbackSpec` defining the files and versions.
            transaction: If True, perform an atomic rollback using staging.
                If False, roll back each file independently.
            dry_run: If True, simulates the operations without file changes.

        Returns:
            A `BulkRollbackResult` summarizing the outcome of the operation.
        """
        # Generate a transaction ID (even if not strictly transactional)
        transaction_id = f"rollback_{int(datetime.datetime.now().timestamp())}"
        results = []

        # If using transactions, we need to stage all rollbacks first
        if transaction and not dry_run:
            # Stage all rollbacks
            staged_specs = []
            for spec in specs:
                # Override the strategy to staged
                staged_spec = RollbackSpec(
                    file_path=spec.file_path,
                    version_id=spec.version_id,
                    strategy=RollbackStrategy.STAGED,
                )
                staged_specs.append(staged_spec)

            # Perform the staged rollbacks
            for spec in staged_specs:
                result = await self.rollback_file(
                    spec.file_path,
                    spec.version_id,
                    strategy=RollbackStrategy.STAGED,
                    dry_run=dry_run,
                )
                results.append(result)

            # Check if all staged rollbacks succeeded
            all_success = all(result.success for result in results)

            if all_success and not dry_run:
                # Commit all staged rollbacks
                for spec, result in zip(specs, results, strict=False):
                    staged_path = self._get_staged_path(spec.file_path)

                    # Create a backup if requested
                    backup_path = None
                    if spec.strategy == RollbackStrategy.BACKUP_AND_COPY:
                        backup_path = await self._create_backup(spec.file_path)
                        result.created_backup = backup_path

                    # Copy from staged to target
                    await self.file_io.copy(staged_path, spec.file_path)

                    # Create a new version to record the rollback
                    await version_manager.create_version(
                        spec.file_path,
                        manual=True,
                        annotation=f"Rolled back to version {spec.version_id} as part of transaction {transaction_id}",
                        tags=[
                            "rollback",
                            f"from_{spec.version_id}",
                            f"transaction_{transaction_id}",
                        ],
                    )

                # Clean up staged files
                for spec in specs:
                    staged_path = self._get_staged_path(spec.file_path)
                    try:
                        await self.file_io.remove(staged_path)
                    except Exception as e:
                        logger.warning(
                            f"Failed to clean up staged file {staged_path}: {e}"
                        )
            else:
                # Clean up staged files
                for spec in specs:
                    staged_path = self._get_staged_path(spec.file_path)
                    try:
                        if await self.file_io.exists(staged_path):
                            await self.file_io.remove(staged_path)
                    except Exception as e:
                        logger.warning(
                            f"Failed to clean up staged file {staged_path}: {e}"
                        )

                if not dry_run:
                    # Return failure
                    return BulkRollbackResult(
                        success=False,
                        results=results,
                        transaction_id=transaction_id,
                        error_message="One or more rollbacks failed",
                    )
        else:
            # Perform each rollback individually
            for spec in specs:
                result = await self.rollback_file(
                    spec.file_path,
                    spec.version_id,
                    strategy=spec.strategy,
                    dry_run=dry_run,
                )
                results.append(result)

        # Determine overall success
        success = all(result.success for result in results)

        return BulkRollbackResult(
            success=success,
            results=results,
            transaction_id=transaction_id,
            error_message="" if success else "One or more rollbacks failed",
        )

    async def _create_backup(self, file_path: Path) -> Path:
        """Create a timestamped backup of a file in the designated backup directory.

        Args:
            file_path: Path to the file to back up.

        Returns:
            The absolute path to the created backup file.
        """
        # Create a timestamped backup path
        timestamp = int(datetime.datetime.now().timestamp())
        backup_filename = f"{file_path.stem}_{timestamp}{file_path.suffix}.bak"
        backup_path = self.backup_dir / backup_filename

        # Copy the file to the backup location
        await self.file_io.copy(file_path, backup_path)

        logger.info(f"Created backup of {file_path} at {backup_path}")
        return backup_path

    def _get_staged_path(self, file_path: Path) -> Path:
        """Generate a unique path within the staging directory for a given file.

        This path is used temporarily during transactional rollbacks.
        The filename is derived from the original file path to avoid collisions.

        Args:
            file_path: The original absolute file path.

        Returns:
            The absolute path within the staging directory for this file.
        """
        # Create a unique filename based on the original path
        rel_path = str(file_path).replace(":", "_").replace("/", "_").replace("\\", "_")
        return self.staging_dir / f"{rel_path}.staged"


# Create a singleton instance for application-wide use
rollback_engine = RollbackEngine()
