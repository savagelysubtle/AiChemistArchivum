import asyncio
import datetime
import hashlib
import logging
from pathlib import Path

from the_aichemist_codex.infrastructure.config import config, rules_engine
from the_aichemist_codex.infrastructure.utils import (
    AsyncFileIO,
    SafeFileHandler,
    get_thread_pool,
)

from .directory import DirectoryManager
from .rollback import OperationType, rollback_manager

logger: logging.Logger = logging.getLogger(__name__)

# Initialize DirectoryManager using config
# This assumes DirectoryManager is refactored to accept config or uses it internally
# For now, let's assume DirectoryManager handles its own config access if needed.
# If DirectoryManager needs base_dir explicitly from config:
# data_dir_path = Path(config.get('data_dir', './data')) # Provide a default
directory_manager = (
    DirectoryManager()
)  # Assumes DirectoryManager uses config internally

# Instantiate AsyncFileIO for use in static methods
async_file_io = AsyncFileIO()
# Get shared thread pool
thread_pool = get_thread_pool()


class FileMover:
    def __init__(self) -> None:
        # Get base directory from config
        self.base_directory = Path(config.get("data_dir", "./data")).resolve()
        # Use the imported SafeFileHandler directly (assuming static methods or proper setup)
        self.safe_handler = (
            SafeFileHandler  # Instance might be needed if not static methods
        )
        self.copy_verify_threshold = config.get("fs.copy_verify_threshold", 10_000_000)
        self.chunked_copy_threshold = config.get(
            "fs.chunked_copy_threshold", 10_000_000
        )
        self.backup_base_dir = Path(
            config.get("fs.backup_dir", str(self.base_directory / "backup"))
        )
        self.auto_org_base = config.get("fs.auto_org_base", "organized")

    @staticmethod
    async def get_file_hash(file_path: Path) -> str:
        """Calculate SHA-256 hash of a file using async I/O.
        TODO: Consider moving this to a shared utility module in infrastructure.utils.io
        """
        try:
            hasher = hashlib.sha256()
            # Use AsyncFileIO for reading the file in chunks
            async for chunk in async_file_io.read_chunked(file_path, chunk_size=8192):
                # Run hash update in thread pool to avoid blocking
                hasher = await asyncio.get_event_loop().run_in_executor(
                    thread_pool, hasher.update, chunk
                )
            # Run hexdigest in thread pool as well
            return await asyncio.get_event_loop().run_in_executor(
                thread_pool, hasher.hexdigest
            )
        except FileNotFoundError:
            logger.warning(f"File not found for hashing: {file_path}")
            return ""
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return ""

    @staticmethod
    async def verify_file_copy(source: Path, destination: Path) -> bool:
        """Verify that the destination file exists and has the same size
        and hash as the source."""
        copy_verify_threshold = config.get("fs.copy_verify_threshold", 10_000_000)
        try:
            if not await async_file_io.exists(destination):
                logger.error(f"Destination file does not exist: {destination}")
                return False

            # Get file sizes concurrently
            source_size_task = asyncio.create_task(async_file_io.stat(source))
            dest_size_task = asyncio.create_task(async_file_io.stat(destination))
            source_stat, dest_stat = await asyncio.gather(
                source_size_task, dest_size_task, return_exceptions=True
            )

            if isinstance(source_stat, Exception) or isinstance(dest_stat, Exception):
                logger.error(
                    f"Could not determine file stats for {source} ({source_stat}) or {destination} ({dest_stat})"
                )
                return False

            source_size = source_stat.st_size
            dest_size = dest_stat.st_size

            if source_size != dest_size:
                logger.error(
                    f"File size mismatch: {source} ({source_size} bytes) -> "
                    f"{destination} ({dest_size} bytes)"
                )
                return False

            # For files below threshold, also verify contents with hash
            if source_size < copy_verify_threshold:
                source_hash_task = asyncio.create_task(FileMover.get_file_hash(source))
                dest_hash_task = asyncio.create_task(
                    FileMover.get_file_hash(destination)
                )
                source_hash, dest_hash = await asyncio.gather(
                    source_hash_task, dest_hash_task
                )

                if source_hash != dest_hash:
                    logger.error(
                        f"File hash mismatch: {source} ({source_hash}) -> {destination} ({dest_hash})"
                    )
                    return False

            return True
        except Exception as e:
            logger.error(f"Error verifying file copy {source} -> {destination}: {e}")
            return False

    @staticmethod
    async def safe_remove_file(file_path: Path) -> bool:
        """Safely remove a file using AsyncFileIO."""
        try:
            # Use AsyncFileIO.remove (assuming it exists and handles missing_ok)
            await async_file_io.remove(file_path)
            # If remove doesn't handle missing_ok, check existence first:
            # if await async_file_io.exists(file_path):
            #     await async_file_io.remove(file_path)
            logger.debug(f"Removed file: {file_path}")
            return True
        except FileNotFoundError:
            logger.debug(f"File already removed or never existed: {file_path}")
            return True  # Consider removal successful if not found
        except Exception as e:
            logger.error(f"Error removing file {file_path}: {e}")
            return False

    # Make move_file an instance method to access configured paths/thresholds
    async def move_file(self, source: Path, destination: Path) -> None:
        """Move a file from source to destination using AsyncFileIO operations."""
        # Use the instance's safe_handler
        if self.safe_handler.should_ignore(source):
            logger.info(f"Skipping ignored file: {source}")
            return

        # Create a backup BEFORE attempting any move
        backup_path = None  # Initialize backup_path
        try:
            # Use backup_base_dir from config
            backup_dir = self.backup_base_dir / "file_backups"
            # Ensure backup dir exists (use async mkdir)
            await async_file_io.mkdir(backup_dir, parents=True, exist_ok=True)

            # Create timestamped backup
            timestamp = int(datetime.datetime.now().timestamp())
            backup_path = backup_dir / f"{source.name}.{timestamp}.bak"

            # Perform backup
            await async_file_io.copy(source, backup_path)
            logger.info(f"Created backup of {source} at {backup_path}")
        except Exception as backup_error:
            logger.error(f"Failed to create backup of {source}: {backup_error}")
            # Continue with the move, but record that backup failed.

        move_success = False
        try:
            # Ensure destination directory exists asynchronously
            await directory_manager.ensure_directory(destination.parent)

            # Check if destination already exists
            if await async_file_io.exists(destination):
                logger.warning(f"Destination file already exists: {destination}")
                # Generate a unique name by adding a timestamp
                new_name = f"{destination.stem}_{int(datetime.datetime.now().timestamp())}{destination.suffix}"
                destination = destination.parent / new_name
                logger.info(f"Using alternative destination: {destination}")

            # Use configured chunked copy threshold
            file_size_stat = await async_file_io.stat(source)  # Get stat once
            file_size = file_size_stat.st_size
            if file_size > self.chunked_copy_threshold:
                logger.info(
                    f"Using chunked copy for large file: {source} ({file_size} bytes)"
                )
                copy_success = await async_file_io.copy_chunked(source, destination)
            else:
                # Use regular copy for smaller files
                copy_success = await async_file_io.copy(source, destination)

            if copy_success:
                # Verify the file was copied correctly
                verification = await self.verify_file_copy(source, destination)

                if verification:
                    logger.info(f"Verified copy successful: {source} -> {destination}")

                    # Remove original file only after successful copy and verification
                    removal_success = await self.safe_remove_file(source)

                    if removal_success:
                        logger.info(f"Moved {source} -> {destination}")
                        move_success = True  # Mark move as successful
                    else:
                        logger.error(
                            f"Failed to remove source file after copying: {source}"
                        )
                        # Decide on recovery strategy - potentially restore from backup?
                else:
                    logger.error(
                        f"File verification failed, cancelling move operation: "
                        f"{source} -> {destination}"
                    )
                    # Clean up the potentially corrupted destination file
                    await self.safe_remove_file(destination)
            else:
                logger.error(f"Failed to copy {source} to {destination}")
        except Exception as e:
            logger.exception(
                f"Error moving {source} to {destination}: {e}"
            )  # Log with stack trace

        # ALWAYS record the operation
        try:
            op_details = {
                "source": str(source),
                "destination": str(destination),
                "success": move_success,
                "backup_path": str(backup_path) if backup_path else None,
            }
            # Determine correct path for rollback based on success
            # If move succeeded, original path is 'destination', target for rollback is 'source'
            # If move failed, original path is 'source', target for rollback might be complex (cleanup?)
            # For simplicity, let's record based on the intended destination for potential manual review
            await rollback_manager.record_operation(
                OperationType.MOVE,
                target_path=destination
                if move_success
                else source,  # Path primarily affected
                details=op_details,
            )
        except Exception as rollback_error:
            logger.error(f"Error recording rollback operation: {rollback_error}")

    # Make apply_rules an instance method
    async def apply_rules(self, file_path: Path) -> bool:
        """
        Apply organization rules to a file.

        Args:
            file_path: Path to the file to be organized

        Returns:
            bool: True if a rule was applied, False otherwise
        """
        # Ensure we're using an absolute, resolved path
        file_path = file_path.resolve()
        logger.info(f"Applying rules to: {file_path}")

        # Skip if the file no longer exists
        if not await async_file_io.exists(file_path):
            logger.warning(f"File no longer exists: {file_path}")
            return False

        # Use rules_engine from config
        active_rules = rules_engine.get_active_rules()  # Assuming a method to get rules
        if not active_rules:
            logger.warning("No active rules found in the rules engine.")
            return False

        for rule in active_rules:  # Iterate through rules from engine
            # Assuming rule structure: {'extensions': [...], 'target_dir': '...'}
            # Match using the rules engine's matching capability if available
            # Or adapt the logic here based on the actual rules_engine structure
            if rules_engine.match(file_path, rule):  # Hypothetical match method
                # Or stick to manual matching if engine doesn't provide it:
                # if any(
                #     file_path.suffix.lower() == ext.lower()
                #     for ext in rule.get("extensions", [])
                # ):
                target_dir_str = rule.get("target_dir")
                if not target_dir_str:
                    logger.warning(
                        f"Rule matched for {file_path} but has no target_dir."
                    )
                    continue

                # Build target directory path
                target_dir = Path(target_dir_str)
                if not target_dir.is_absolute():
                    # Use the FileMover's base_directory
                    target_dir = self.base_directory / target_dir
                target_dir = target_dir.resolve()

                logger.info(
                    f"Rule matched for {file_path}. Target directory: {target_dir}"
                )

                # Ensure the target directory exists
                await directory_manager.ensure_directory(target_dir)

                # Move the file using the instance method
                target_file = target_dir / file_path.name
                logger.info(f"Moving file to {target_file}")
                await self.move_file(file_path, target_file)
                return True  # Rule applied, stop processing

        logger.info(f"No rules matched for {file_path}")
        return False

    # Make auto_folder_structure an instance method
    async def auto_folder_structure(self, file_path: Path) -> Path:
        """
        Create an automatic folder structure based on file type and date.

        Args:
            file_path: Path to the file to organize

        Returns:
            Path: Path to the target directory
        """
        # Ensure we're using an absolute, resolved path
        file_path = file_path.resolve()
        logger.info(f"Creating auto folder structure for: {file_path}")

        # Skip if the file no longer exists
        if not await async_file_io.exists(file_path):
            logger.warning(f"File no longer exists: {file_path}")
            # Use configured base directory and auto-org base
            return self.base_directory / self.auto_org_base / "unknown"

        # Organize by file extension and creation date (YYYY-MM)
        ext = file_path.suffix.lower().lstrip(".")
        if not ext:
            ext = "no_extension"

        # Get file creation time
        try:
            # Use AsyncFileIO.stat
            file_stats = await async_file_io.stat(file_path)
            # Try to use st_birthtime first (macOS/BSD),
            # fall back to st_mtime (modification time)
            creation_time = getattr(file_stats, "st_birthtime", file_stats.st_mtime)
            dt = datetime.datetime.fromtimestamp(creation_time)
            date_folder = dt.strftime("%Y-%m")
        except Exception as e:
            logger.warning(f"Error getting creation time for {file_path}: {e}")
            date_folder = "unknown_date"

        # Create path structure using configured base dir and auto-org base
        target_dir = (
            self.base_directory / self.auto_org_base / ext / date_folder
        ).resolve()
        logger.info(f"Auto-organization target directory: {target_dir}")

        # Ensure the directory exists
        await directory_manager.ensure_directory(target_dir)

        return target_dir
