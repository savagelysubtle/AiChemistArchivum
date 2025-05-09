"""Rollback manager for safe file operations.

Provides functionality to track file operations and roll them back
if needed, ensuring data integrity during file operations.
"""

import logging
import uuid
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any

from the_aichemist_codex.infrastructure.config import config
from the_aichemist_codex.infrastructure.utils import AsyncFileIO, get_thread_pool

logger: logging.Logger = logging.getLogger(__name__)

# Instantiate utilities
async_file_io = AsyncFileIO()
thread_pool = get_thread_pool()


class OperationType(Enum):
    """Type of file operation that can be tracked for rollback."""

    MOVE = auto()
    COPY = auto()
    RENAME = auto()
    DELETE = auto()
    CREATE = auto()
    MODIFY = auto()


class FileOperation:
    """Represents a single file operation that can be rolled back."""

    def __init__(
        self,
        operation_type: OperationType,
        affected_path: Path,
        original_state: Any = None,
        additional_info: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize a new file operation.

        Args:
            operation_type: Type of operation performed
            affected_path: Path to the file or directory affected
            original_state: Original state data (depends on operation type)
            additional_info: Any additional information needed for rollback
        """
        self.id = str(uuid.uuid4())
        self.operation_type = operation_type
        self.affected_path = affected_path
        self.timestamp = datetime.now()
        self.original_state = original_state
        self.additional_info = additional_info or {}
        self.rolled_back = False

    def __str__(self) -> str:
        """Return a string representation of the operation."""
        return (
            f"FileOperation(id={self.id}, type={self.operation_type.name}, "
            f"path='{self.affected_path!s}', timestamp={self.timestamp.isoformat()})"
        )


class RollbackManager:
    """
    Manages file operations and provides rollback functionality.

    This class tracks file operations in memory and provides the ability
    to roll back operations if needed. Operations can be grouped into
    transactions for atomicity.
    """

    _instance = None
    _initialized = False

    def __new__(cls, *args: object, **kwargs: object) -> "RollbackManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, backup_dir: Path | None = None) -> None:
        """
        Initialize the rollback manager.

        Args:
            backup_dir: Optional directory for storing backup files
        """
        # Only initialize once
        if RollbackManager._initialized:
            return

        # Set up backup directory
        if backup_dir is None:
            data_dir = Path(config.get("data_dir"))
            self.backup_dir = data_dir / ".backups"
        else:
            self.backup_dir = backup_dir

        # Create backup directory if it doesn't exist (use synchronous for init)
        # Note: Consider if __init__ should be async if it needs async setup.
        # For now, keeping sync init with sync mkdir.
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create backup directory {self.backup_dir}: {e}")
            # Decide how to handle this failure - maybe raise an exception?

        # Initialize operation tracking
        self.operations: list[FileOperation] = []
        self.current_transaction_id: str | None = None
        self.transactions: dict[str, list[FileOperation]] = {}

        RollbackManager._initialized = True
        logger.debug(f"Rollback manager initialized with backup dir: {self.backup_dir}")

    def start_transaction(self) -> str:
        """
        Start a new transaction for grouping operations.

        Returns:
            str: Transaction ID
        """
        # End any existing transaction first
        if self.current_transaction_id:
            self.end_transaction()

        # Create a new transaction
        self.current_transaction_id = str(uuid.uuid4())
        self.transactions[self.current_transaction_id] = []

        logger.debug(f"Started transaction: {self.current_transaction_id}")
        return self.current_transaction_id

    def end_transaction(self) -> None:
        """End the current transaction."""
        if self.current_transaction_id:
            logger.debug(f"Ended transaction: {self.current_transaction_id}")
            self.current_transaction_id = None

    # Make backup async
    async def _make_backup(self, file_path: Path) -> Path | None:
        """
        Create a backup of a file asynchronously.

        Args:
            file_path: Path to the file to back up

        Returns:
            Optional[Path]: Path to the backup file, or None if backup failed
        """
        if not await async_file_io.exists(file_path):
            logger.warning(f"Cannot back up non-existent file: {file_path}")
            return None

        # Create a unique backup filename
        timestamp_str = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )  # Added microseconds
        backup_name = f"{file_path.stem}_{timestamp_str}{file_path.suffix}"
        backup_path = self.backup_dir / backup_name

        try:
            # Create the backup using AsyncFileIO
            # Ensure backup directory exists first (though done in init, check again just in case)
            await async_file_io.mkdir(self.backup_dir, parents=True, exist_ok=True)
            success = await async_file_io.copy(file_path, backup_path)
            if success:
                logger.debug(f"Created backup of {file_path} at {backup_path}")
                return backup_path
            else:
                logger.error(f"Async copy failed to create backup of {file_path}")
                return None
        except Exception as e:
            logger.error(f"Failed to create backup of {file_path}: {e}")
            return None

    # Make record_operation async because it calls async _make_backup
    async def record_operation(
        self, operation_type: OperationType, target_path: Path, **kwargs: Any
    ) -> FileOperation | None:
        """
        Record a file operation asynchronously for potential rollback.

        Args:
            operation_type: Type of operation being performed
            target_path: Path primarily affected by the operation (e.g., destination for MOVE/COPY)
            **kwargs: Additional information needed for rollback (e.g., source, details)

        Returns:
            Optional[FileOperation]: The recorded operation, or None if recording failed
        """
        affected_path = target_path  # Use target_path as the main affected path
        original_state = None
        additional_info = kwargs.copy()  # Use a copy of kwargs

        # Determine path for backup based on operation type
        path_to_backup = None
        if operation_type == OperationType.DELETE:
            path_to_backup = affected_path  # Backup the file being deleted
        elif operation_type == OperationType.MODIFY:
            path_to_backup = affected_path  # Backup the file being modified
        elif operation_type in (OperationType.MOVE, OperationType.RENAME):
            # Backup the source file BEFORE it's moved/renamed
            source_path_str = additional_info.get("source")
            if isinstance(source_path_str, (str, Path)):
                path_to_backup = Path(source_path_str)
            else:
                logger.warning(
                    "Source path not provided or invalid for MOVE/RENAME backup."
                )

        # Create backup if a path was identified
        if (
            path_to_backup
            and await async_file_io.exists(path_to_backup)
            and await async_file_io.is_file(path_to_backup)
        ):
            backup_path = await self._make_backup(path_to_backup)
            if backup_path:
                original_state = {
                    "backup_path": str(backup_path)
                }  # Store backup path as string
            else:
                logger.warning(
                    f"Failed to backup {path_to_backup} for {operation_type.name} operation."
                )
                # Decide if failure to backup should prevent recording the operation

        # Validate required info for MOVE/RENAME
        if operation_type in (OperationType.MOVE, OperationType.RENAME):
            if "source" not in additional_info or "destination" not in additional_info:
                logger.error(
                    f"{operation_type.name} operation requires 'source' and 'destination' in details"
                )
                return None
            # Ensure paths are stored as strings for potential serialization
            additional_info["source"] = str(additional_info["source"])
            additional_info["destination"] = str(additional_info["destination"])

        # Create operation record
        operation = FileOperation(
            operation_type=operation_type,
            affected_path=affected_path,  # The path primarily affected (often destination)
            original_state=original_state,
            additional_info=additional_info,
        )

        # Add to current transaction if one is active
        if self.current_transaction_id:
            if self.current_transaction_id in self.transactions:
                self.transactions[self.current_transaction_id].append(operation)
            else:
                logger.error(
                    f"Transaction ID {self.current_transaction_id} not found in transactions dict."
                )
                # Handle error appropriately - maybe don't record?

        # Add to overall operations list
        self.operations.append(operation)

        logger.debug(f"Recorded operation: {operation}")
        return operation

    async def rollback_operation(self, operation: FileOperation) -> bool:
        """
        Roll back a single operation.

        Args:
            operation: The operation to roll back

        Returns:
            bool: True if successful
        """
        if operation.rolled_back:
            logger.warning(f"Operation already rolled back: {operation}")
            return True

        success = False

        try:
            # Rollback based on operation type
            if operation.operation_type == OperationType.DELETE:
                # Restore from backup
                if (
                    operation.original_state
                    and isinstance(operation.original_state, dict)
                    and "backup_path" in operation.original_state
                ):
                    backup_path = Path(operation.original_state["backup_path"])
                    if await async_file_io.exists(backup_path):
                        # Ensure parent directory exists
                        await async_file_io.mkdir(
                            operation.affected_path.parent, parents=True, exist_ok=True
                        )
                        # Restore file using async copy
                        success = await async_file_io.copy(
                            backup_path, operation.affected_path
                        )
                    else:
                        logger.warning(
                            f"Backup file not found for rollback: {backup_path}"
                        )
                else:
                    logger.warning(
                        f"No backup path found for DELETE rollback: {operation}"
                    )

            elif operation.operation_type == OperationType.MODIFY:
                # Restore from backup
                if (
                    operation.original_state
                    and isinstance(operation.original_state, dict)
                    and "backup_path" in operation.original_state
                ):
                    backup_path = Path(operation.original_state["backup_path"])
                    if await async_file_io.exists(backup_path):
                        # Restore file using async copy
                        success = await async_file_io.copy(
                            backup_path, operation.affected_path
                        )
                    else:
                        logger.warning(
                            f"Backup file not found for rollback: {backup_path}"
                        )
                else:
                    logger.warning(
                        f"No backup path found for MODIFY rollback: {operation}"
                    )

            elif (
                operation.operation_type == OperationType.MOVE
                or operation.operation_type == OperationType.RENAME
            ):
                # Move back to original location
                # Destination of the original operation becomes the source for rollback
                source_rb = Path(operation.additional_info.get("destination", ""))
                # Source of the original operation becomes the destination for rollback
                destination_rb = Path(operation.additional_info.get("source", ""))

                if not source_rb or not destination_rb:
                    logger.error(
                        f"Missing source or destination path in MOVE/RENAME rollback info: {operation}"
                    )
                    return False

                # Check if the file/dir to move back exists
                if await async_file_io.exists(source_rb):
                    # Ensure parent directory for the original location exists
                    await async_file_io.mkdir(
                        destination_rb.parent, parents=True, exist_ok=True
                    )
                    # Move back using async move
                    success = await async_file_io.move(source_rb, destination_rb)
                else:
                    logger.warning(
                        f"Source path for rollback does not exist: {source_rb}"
                    )
                    # Decide if this is success (already undone?) or failure
                    # Let's consider it a potential success if the destination *doesn't* exist either
                    success = not await async_file_io.exists(destination_rb)

            elif operation.operation_type == OperationType.CREATE:
                # Delete the created file/directory
                if await async_file_io.exists(operation.affected_path):
                    if await async_file_io.is_file(operation.affected_path):
                        await async_file_io.remove(operation.affected_path)
                        success = True
                    elif await async_file_io.is_dir(operation.affected_path):
                        await async_file_io.rmtree(operation.affected_path)
                        success = True
                    else:
                        logger.warning(
                            f"Cannot rollback CREATE for unknown file type: {operation.affected_path}"
                        )
                else:
                    logger.info(
                        f"Path to rollback CREATE for already gone: {operation.affected_path}"
                    )
                    success = True  # Already rolled back / deleted

            else:
                logger.warning(
                    f"Unsupported operation type for rollback: "
                    f"{operation.operation_type}"
                )
                return False

            # Mark as rolled back if successful
            if success:
                operation.rolled_back = True
                logger.info(f"Successfully rolled back operation: {operation}")

            return success

        except Exception as e:
            logger.error(f"Error rolling back operation {operation}: {e}")
            return False

    async def rollback_transaction(self, transaction_id: str) -> bool:
        """
        Roll back all operations in a transaction.

        Args:
            transaction_id: ID of the transaction to roll back

        Returns:
            bool: True if all operations were rolled back successfully
        """
        if transaction_id not in self.transactions:
            logger.error(f"Transaction not found: {transaction_id}")
            return False

        # Roll back operations in reverse order
        operations = self.transactions[transaction_id]
        success = True

        for operation in reversed(operations):
            op_success = await self.rollback_operation(operation)
            if not op_success:
                success = False
                logger.error(
                    f"Failed to roll back operation in transaction {transaction_id}: "
                    f"{operation}"
                )

        return success

    async def rollback_last_operations(self, count: int = 1) -> bool:
        """
        Roll back the last n operations.

        Args:
            count: Number of operations to roll back

        Returns:
            bool: True if all operations were rolled back successfully
        """
        if not self.operations:
            logger.warning("No operations to roll back")
            return True

        # Get the last n operations
        to_rollback = self.operations[-count:]
        if len(to_rollback) < count:
            logger.warning(
                f"Requested to roll back {count} operations, but only "
                f"{len(to_rollback)} available"
            )

        # Roll back in reverse order
        success = True
        for operation in reversed(to_rollback):
            op_success = await self.rollback_operation(operation)
            if not op_success:
                success = False

        return success

    def clear_history(self) -> None:
        """Clear operation history and transactions."""
        self.operations = []
        self.transactions = {}
        self.current_transaction_id = None
        logger.info("Cleared rollback history")


# Create a singleton instance
rollback_manager = RollbackManager()
