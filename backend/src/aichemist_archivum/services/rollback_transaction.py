"""Transaction support for rollback operations.

This module provides the `TransactionManager` class for coordinating atomic
rollback operations across multiple files, ensuring that either all specified
rollbacks succeed or none are permanently applied.
"""

import asyncio
import datetime
import logging
import os
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from the_aichemist_codex.infrastructure.config.settings import determine_project_root
from the_aichemist_codex.infrastructure.utils.io.async_io import AsyncFileIO

from ..version_manager import version_manager
from .engine import RollbackSpec, RollbackStrategy, rollback_engine

logger = logging.getLogger(__name__)


class TransactionState(Enum):
    """States of a rollback transaction."""

    CREATED = "created"  # Transaction created but not started
    PREPARING = "preparing"  # Preparing the rollback operations
    STAGING = "staging"  # Staging the rollback operations
    COMMITTING = "committing"  # Committing the rollback operations
    ROLLING_BACK = "rolling_back"  # Rolling back the transaction
    COMPLETED = "completed"  # Transaction completed successfully
    FAILED = "failed"  # Transaction failed
    ABORTED = "aborted"  # Transaction aborted manually


@dataclass
class TransactionMetadata:
    """Metadata associated with a single rollback transaction.

    Attributes:
        transaction_id: A unique identifier for the transaction.
        created_at: Timestamp when the transaction was created.
        completed_at: Timestamp when the transaction finished (successfully or not).
        state: The current `TransactionState` (e.g., CREATED, STAGING, COMPLETED).
        specs: A list of `RollbackSpec` objects defining the operations in this transaction.
        description: An optional user-provided description.
        initiator: An optional identifier for the user/process initiating the transaction.
        error_message: Stores any error message if the transaction fails.
    """

    transaction_id: str
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    completed_at: datetime.datetime | None = None
    state: TransactionState = TransactionState.CREATED
    specs: list[RollbackSpec] = field(default_factory=list)
    description: str = ""
    initiator: str = ""
    error_message: str = ""


class TransactionManager:
    """Manages the lifecycle of atomic rollback transactions.

    Provides methods to create, prepare (validate), commit, abort, and query
    the status of multi-file rollback transactions. It leverages the
    `RollbackEngine` for the actual file operations and ensures atomicity
    by using a prepare/commit pattern, typically involving staging.
    """

    def __init__(self):
        """Initializes the TransactionManager.

        Sets up `AsyncFileIO`, determines the directory for storing transaction
        metadata files, ensures the directory exists, and initializes an
        in-memory cache for active transactions.
        """
        self.file_io = AsyncFileIO()
        self.project_root = determine_project_root()
        self.transactions_dir = self.project_root / "data" / "transactions"

        # Ensure directories exist
        self.transactions_dir.mkdir(parents=True, exist_ok=True)

        # Active transactions
        self._active_transactions: dict[str, TransactionMetadata] = {}

    async def create_transaction(
        self, specs: list[RollbackSpec], description: str = "", initiator: str = ""
    ) -> TransactionMetadata:
        """Create a new rollback transaction and persist its initial metadata.

        Generates a unique transaction ID and creates the initial
        `TransactionMetadata` object in the `CREATED` state.

        Args:
            specs: A list of `RollbackSpec` detailing the files and target versions.
            description: Optional description for the transaction.
            initiator: Optional identifier of the entity initiating the transaction.

        Returns:
            The newly created `TransactionMetadata` object.
        """
        # Generate a transaction ID
        transaction_id = (
            f"tx_{uuid.uuid4().hex[:8]}_{int(datetime.datetime.now().timestamp())}"
        )

        # Create metadata
        metadata = TransactionMetadata(
            transaction_id=transaction_id,
            specs=specs,
            description=description,
            initiator=initiator,
        )

        # Store the metadata
        self._active_transactions[transaction_id] = metadata
        await self._save_transaction_metadata(metadata)

        logger.info(
            f"Created transaction {transaction_id} with {len(specs)} operations"
        )
        return metadata

    async def prepare_transaction(self, transaction_id: str) -> tuple[bool, str | None]:
        """Prepare a transaction by validating all included rollback operations.

        Checks if the transaction exists, updates its state to `PREPARING`,
        and then validates each `RollbackSpec`:
        - Ensures the target file exists (unless strategy is COPY).
        - Ensures the target version exists via `VersionManager`.
        Updates state to `STAGING` if all valid, `FAILED` otherwise.

        Args:
            transaction_id: The ID of the transaction to prepare.

        Returns:
            A tuple: (True, None) on successful preparation, or
            (False, error_message) if validation fails or an error occurs.
        """
        try:
            # Get the transaction metadata
            metadata = await self._get_transaction(transaction_id)
            if not metadata:
                return False, f"Transaction {transaction_id} not found"

            # Update state
            metadata.state = TransactionState.PREPARING
            await self._save_transaction_metadata(metadata)

            # Validate each operation
            all_valid = True
            errors = []

            for spec in metadata.specs:
                # Validate that the file exists
                if (
                    not await self.file_io.exists(spec.file_path)
                    and spec.strategy != RollbackStrategy.COPY
                ):
                    errors.append(f"File does not exist: {spec.file_path}")
                    all_valid = False
                    continue

                # Check if the version exists
                (
                    version_file,
                    version_metadata,
                ) = await version_manager.get_version(spec.file_path, spec.version_id)

                if not version_file or not version_metadata:
                    errors.append(
                        f"Version {spec.version_id} not found for {spec.file_path}"
                    )
                    all_valid = False

            # Update state based on validation
            if all_valid:
                metadata.state = TransactionState.STAGING
                await self._save_transaction_metadata(metadata)
                return True, None
            else:
                metadata.state = TransactionState.FAILED
                error_message = "Validation failed: " + "; ".join(errors)
                metadata.error_message = error_message
                await self._save_transaction_metadata(metadata)
                return False, error_message

        except Exception as e:
            logger.error(f"Error preparing transaction {transaction_id}: {e}")
            if metadata:
                metadata.state = TransactionState.FAILED
                metadata.error_message = str(e)
                await self._save_transaction_metadata(metadata)
            return False, str(e)

    async def commit_transaction(self, transaction_id: str) -> tuple[bool, str | None]:
        """Attempt to commit a prepared (staged) transaction.

        Checks if the transaction is in the `STAGING` state. Updates state to
        `COMMITTING` and then delegates the actual rollback execution to
        `RollbackEngine.rollback_bulk` with `transaction=True`.
        Updates the final state to `COMPLETED` or `FAILED` based on the result.

        Args:
            transaction_id: The ID of the transaction to commit.

        Returns:
            A tuple: (True, None) on successful commit, or
            (False, error_message) if the commit fails or an error occurs.
        """
        try:
            # Get the transaction metadata
            metadata = await self._get_transaction(transaction_id)
            if not metadata:
                return False, f"Transaction {transaction_id} not found"

            # Check if the transaction is in the right state
            if metadata.state != TransactionState.STAGING:
                return (
                    False,
                    f"Transaction {transaction_id} is not ready to commit (state: {metadata.state.value})",
                )

            # Update state
            metadata.state = TransactionState.COMMITTING
            await self._save_transaction_metadata(metadata)

            # Perform the rollback operations
            bulk_result = await rollback_engine.rollback_bulk(
                metadata.specs, transaction=True
            )

            if bulk_result.success:
                # Update state
                metadata.state = TransactionState.COMPLETED
                metadata.completed_at = datetime.datetime.now()
                await self._save_transaction_metadata(metadata)
                return True, None
            else:
                # Update state
                metadata.state = TransactionState.FAILED
                metadata.error_message = bulk_result.error_message
                await self._save_transaction_metadata(metadata)
                return False, bulk_result.error_message

        except Exception as e:
            logger.error(f"Error committing transaction {transaction_id}: {e}")
            if metadata:
                metadata.state = TransactionState.FAILED
                metadata.error_message = str(e)
                await self._save_transaction_metadata(metadata)
            return False, str(e)

    async def abort_transaction(
        self, transaction_id: str, reason: str = ""
    ) -> tuple[bool, str | None]:
        """Abort a transaction if it's in a state that allows abortion.

        Checks if the transaction exists and is not already completed or failed.
        Updates the state to `ABORTED`, records the reason, and sets the
        completion timestamp.
        Note: This typically prevents a commit but might not clean up staged files
              depending on when it's called relative to the `RollbackEngine` process.

        Args:
            transaction_id: The ID of the transaction to abort.
            reason: An optional reason for the abortion.

        Returns:
            A tuple: (True, None) if successfully aborted, or
            (False, error_message) if it cannot be aborted or an error occurs.
        """
        try:
            # Get the transaction metadata
            metadata = await self._get_transaction(transaction_id)
            if not metadata:
                return False, f"Transaction {transaction_id} not found"

            # Check if the transaction can be aborted
            if metadata.state in [TransactionState.COMPLETED, TransactionState.FAILED]:
                return (
                    False,
                    f"Cannot abort transaction {transaction_id} in state {metadata.state.value}",
                )

            # Update state
            metadata.state = TransactionState.ABORTED
            metadata.error_message = reason
            metadata.completed_at = datetime.datetime.now()
            await self._save_transaction_metadata(metadata)

            return True, None

        except Exception as e:
            logger.error(f"Error aborting transaction {transaction_id}: {e}")
            return False, str(e)

    async def get_transaction_status(
        self, transaction_id: str
    ) -> tuple[TransactionMetadata | None, str | None]:
        """Retrieve the current status and metadata of a transaction.

        Args:
            transaction_id: The ID of the transaction to query.

        Returns:
            A tuple: (`TransactionMetadata`, None) if found, or
            (None, error_message) if not found or an error occurs.
        """
        try:
            # Get the transaction metadata
            metadata = await self._get_transaction(transaction_id)
            if not metadata:
                return None, f"Transaction {transaction_id} not found"

            return metadata, None

        except Exception as e:
            logger.error(f"Error getting transaction status for {transaction_id}: {e}")
            return None, str(e)

    async def list_transactions(
        self, state: TransactionState | None = None, limit: int = 100
    ) -> list[TransactionMetadata]:
        """List recent transactions, optionally filtering by state.

        Scans the transaction metadata directory for JSON files, sorts them by
        modification time (newest first), loads the metadata, and returns a list.
        Uses `asyncio.to_thread` for potentially blocking file system operations
        like `glob` and `getmtime`.

        Args:
            state: If provided, only return transactions in this `TransactionState`.
            limit: The maximum number of transactions to retrieve.

        Returns:
            A list of `TransactionMetadata` objects matching the criteria.
        """
        try:
            transactions = []

            # List transaction files asynchronously
            try:
                # Use to_thread for potentially blocking glob
                tx_files_paths = await asyncio.to_thread(
                    list, self.transactions_dir.glob("*.json")
                )
                # Get modification times asynchronously
                tx_files_with_mtime = []
                for p in tx_files_paths:
                    mtime = await asyncio.to_thread(os.path.getmtime, p)
                    tx_files_with_mtime.append((p, mtime))

                # Sort by modification time (newest first)
                tx_files_with_mtime.sort(key=lambda item: item[1], reverse=True)
                tx_files = [p for p, mtime in tx_files_with_mtime]

            except Exception as e:
                logger.error(f"Error listing transaction files: {e}")
                return []

            # Limit the number of files to process
            tx_files = tx_files[:limit]

            # Load each transaction
            for tx_file in tx_files:
                try:
                    json_data = await self.file_io.read_json(tx_file)

                    # Convert the data to a TransactionMetadata object
                    metadata = await self._dict_to_metadata(json_data)

                    # Apply filter if provided
                    if state is None or metadata.state == state:
                        transactions.append(metadata)

                except Exception as e:
                    logger.error(f"Error loading transaction from {tx_file}: {e}")

            return transactions

        except Exception as e:
            logger.error(f"Error listing transactions: {e}")
            return []

    async def _get_transaction(self, transaction_id: str) -> TransactionMetadata | None:
        """Retrieve transaction metadata by ID, checking cache and then filesystem.

        Args:
            transaction_id: The unique ID of the transaction.

        Returns:
            The `TransactionMetadata` if found, otherwise None.
        """
        # Check active transactions first
        if transaction_id in self._active_transactions:
            return self._active_transactions[transaction_id]

        # Check the filesystem
        tx_path = self.transactions_dir / f"{transaction_id}.json"

        if not await self.file_io.exists(tx_path):
            return None

        try:
            json_data = await self.file_io.read_json(tx_path)
            return await self._dict_to_metadata(json_data)
        except Exception as e:
            logger.error(f"Error loading transaction {transaction_id}: {e}")
            return None

    async def _save_transaction_metadata(self, metadata: TransactionMetadata) -> bool:
        """Save transaction metadata to a JSON file asynchronously.

        Updates the in-memory cache and writes the serialized metadata
        to the appropriate file in the transactions directory.

        Args:
            metadata: The `TransactionMetadata` object to save.

        Returns:
            True if saving was successful, False otherwise.
        """
        try:
            # Update in-memory cache
            self._active_transactions[metadata.transaction_id] = metadata

            # Convert to dict
            data = await self._metadata_to_dict(metadata)

            # Write to disk
            tx_path = self.transactions_dir / f"{metadata.transaction_id}.json"
            return await self.file_io.write_json(tx_path, data)

        except Exception as e:
            logger.error(
                f"Error saving transaction metadata for {metadata.transaction_id}: {e}"
            )
            return False

    async def _metadata_to_dict(self, metadata: TransactionMetadata) -> dict[str, Any]:
        """Serialize `TransactionMetadata` to a dictionary for JSON storage.

        Converts `datetime`, `Enum`, and `Path` objects to JSON-serializable formats.

        Args:
            metadata: The `TransactionMetadata` object.

        Returns:
            A dictionary representation suitable for JSON serialization.
        """
        data = {
            "transaction_id": metadata.transaction_id,
            "created_at": metadata.created_at.isoformat(),
            "completed_at": metadata.completed_at.isoformat()
            if metadata.completed_at
            else None,
            "state": metadata.state.value,
            "description": metadata.description,
            "initiator": metadata.initiator,
            "error_message": metadata.error_message,
            "specs": [],
        }

        # Convert specs
        for spec in metadata.specs:
            spec_data = {
                "file_path": str(spec.file_path),
                "version_id": spec.version_id,
                "strategy": spec.strategy.value,
                "backup_path": str(spec.backup_path) if spec.backup_path else None,
            }
            data["specs"].append(spec_data)

        return data

    async def _dict_to_metadata(self, data: dict[str, Any]) -> TransactionMetadata:
        """Deserialize a dictionary (from JSON) back into `TransactionMetadata`.

        Converts ISO date strings, enum values, and path strings back into
        their respective object types.

        Args:
            data: The dictionary loaded from JSON.

        Returns:
            A reconstructed `TransactionMetadata` object.

        Raises:
            ValueError: If enum values are invalid.
            TypeError: If date strings are not in the correct format.
        """
        # Convert basic fields
        metadata = TransactionMetadata(
            transaction_id=data["transaction_id"],
            created_at=datetime.datetime.fromisoformat(data["created_at"]),
            completed_at=datetime.datetime.fromisoformat(data["completed_at"])
            if data["completed_at"]
            else None,
            state=TransactionState(data["state"]),
            description=data["description"],
            initiator=data["initiator"],
            error_message=data["error_message"],
        )

        # Convert specs
        for spec_data in data["specs"]:
            spec = RollbackSpec(
                file_path=Path(spec_data["file_path"]),
                version_id=spec_data["version_id"],
                strategy=RollbackStrategy(spec_data["strategy"]),
                backup_path=Path(spec_data["backup_path"])
                if spec_data["backup_path"]
                else None,
            )
            metadata.specs.append(spec)

        return metadata

    async def _apply_rollback(self, transaction: TransactionMetadata) -> bool:
        """Apply the rollback operation defined by the transaction specs.

        Iterates through the specs and calls the `RollbackEngine` for each.
        If all operations succeed and the transaction state indicates completion,
        it creates version records for the rolled-back files.

        Note: This method seems potentially redundant or misplaced, as the primary
              rollback logic is handled within `commit_transaction` via the
              `RollbackEngine`. It might be intended for a different workflow
              or could be refactored/removed if `commit_transaction` covers the
              required behavior.

        Args:
            transaction: The `TransactionMetadata` object containing rollback specs.

        Returns:
            True if all specified rollbacks were applied successfully, False otherwise.
        """
        try:
            for spec in transaction.specs:
                result = await rollback_engine.rollback_file(
                    spec.file_path, spec.version_id, strategy=spec.strategy
                )
                if not result.success:
                    transaction.error_message = (
                        f"Failed to rollback file: {spec.file_path}"
                    )
                    return False

            # Create version for the rollback if all successful
            if transaction.state == TransactionState.COMPLETED:
                # Create version for each file individually
                for spec in transaction.specs:
                    await version_manager.create_version(
                        spec.file_path,
                        manual=True,
                        annotation=f"Rollback: {transaction.description}",
                        tags=[
                            "rollback",
                            f"transaction-{transaction.transaction_id[:8]}",
                        ],
                    )
            return True
        except Exception as e:
            logger.error(f"Error during rollback application: {e!s}")
            return False


# Create a singleton instance for application-wide use
transaction_manager = TransactionManager()
