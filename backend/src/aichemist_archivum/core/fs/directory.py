import asyncio
import logging
import os
from pathlib import Path

from the_aichemist_codex.infrastructure.config import config
from the_aichemist_codex.infrastructure.fs.rollback import (
    OperationType,
    RollbackManager,
)
from the_aichemist_codex.infrastructure.utils import AsyncFileIO

logger: logging.Logger = logging.getLogger(__name__)
rollback_manager = RollbackManager()


class DirectoryManager:
    """
    Central manager for data directory access.

    This class provides standardized access to project data directories,
    handling creation, validation, and path resolution.
    """

    # Default standard directories if not in config
    _DEFAULT_STANDARD_DIRS = [
        "cache",
        "logs",
        "versions",
        "exports",
        "backup",
        "trash",
    ]

    def __init__(self, base_dir: Path | None = None) -> None:
        """
        Initialize with optional base directory override.

        Args:
            base_dir: Optional custom base directory path
        """
        self.base_dir = base_dir or self._get_default_data_dir()
        self.standard_dirs = config.get("fs.standard_dirs", self._DEFAULT_STANDARD_DIRS)
        self.async_file_io = AsyncFileIO()
        self._ensure_directories_exist()

    def _get_default_data_dir(self) -> Path:
        """
        Get the default data directory based on config, env vars, or system location.

        Returns:
            Path: The resolved data directory path
        """
        # 1. Check config first
        if config_dir := config.get("data_dir"):
            return Path(config_dir)

        # 2. Check for environment variable override
        if env_dir := os.environ.get("AICHEMIST_DATA_DIR"):
            return Path(env_dir)

        # 3. Use standard OS-specific data directories
        # Retrieve application name from config if available
        app_name = config.get("application.name", "AichemistCodex")
        if os.name == "nt":  # Windows
            appdata = os.environ.get("APPDATA")
            if appdata:
                return Path(appdata) / app_name
            else:
                # Fallback if APPDATA is not set
                return Path.home() / app_name
        else:  # Linux/Mac
            # Use . prefix for hidden directory
            return Path.home() / f".{app_name.lower()}"

    def _ensure_directories_exist(self) -> None:
        """Create all required directories if they don't exist (synchronous)."""
        try:
            for subdir in self.standard_dirs:
                dir_path = self.base_dir / subdir
                dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Ensured standard directories exist under {self.base_dir}")
        except OSError as e:
            logger.error(
                f"Failed to create standard directories under {self.base_dir}: {e}"
            )
            # Potentially raise an error or handle critical failure

    def get_dir(self, dir_type: str) -> Path:
        """
        Get a specific subdirectory path.

        Args:
            dir_type: Directory type (cache, logs, versions, etc.)

        Returns:
            Path: The resolved directory path

        Raises:
            ValueError: If the directory type is not recognized
        """
        if dir_type not in self.standard_dirs:
            raise ValueError(f"Unknown directory type: {dir_type}")
        return self.base_dir / dir_type

    def get_file_path(self, filename: str) -> Path:
        """
        Get path for a file in the base data directory.

        Args:
            filename: Name of the file

        Returns:
            Path: The resolved file path
        """
        return self.base_dir / filename

    async def ensure_directory(self, directory: Path) -> None:
        """
        Ensures that a directory exists asynchronously and records a rollback for creation.

        Args:
            directory: The directory path to ensure exists
        """
        directory = directory.resolve()

        # Use async existence check via AsyncFileIO
        dir_exists = await self.async_file_io.exists(directory)

        if not dir_exists:
            try:
                # Use AsyncFileIO.mkdir
                await self.async_file_io.mkdir(directory, parents=True, exist_ok=True)
                logger.info(f"Ensured directory exists: {directory}")
                # Record the creation so that an undo would delete this new directory
                await rollback_manager.record_operation(OperationType.CREATE, directory)
            except Exception as e:
                logger.error(f"Error ensuring directory {directory}: {e}")
        else:
            logger.debug(f"Directory already exists: {directory}")

    async def cleanup_empty_dirs(self, directory: Path) -> None:
        """
        Recursively removes empty directories asynchronously and records a rollback for each deletion.

        Args:
            directory: The base directory to clean up
        """
        directory = directory.resolve()

        async def remove_if_empty(subdir: Path) -> None:
            # Check if directory exists and is empty using AsyncFileIO
            is_dir = await self.async_file_io.is_dir(subdir)
            if not is_dir:
                return

            # Check if directory is empty using AsyncFileIO.iterdir
            # Need to materialize the async iterator to check if it's empty
            is_empty = True
            try:
                async for _ in self.async_file_io.iterdir(subdir):
                    is_empty = False
                    break  # Found an item, not empty
            except FileNotFoundError:
                # Directory might have been deleted between checks
                logger.warning(f"Directory {subdir} not found during emptiness check.")
                return
            except Exception as e:
                logger.error(f"Error checking emptiness of {subdir}: {e}")
                return  # Avoid deleting if we can't be sure it's empty

            if is_empty:
                try:
                    # Record deletion before removing the directory
                    await rollback_manager.record_operation(
                        OperationType.DELETE, subdir
                    )
                    # Use AsyncFileIO.rmdir
                    await self.async_file_io.rmdir(subdir)
                    logger.info(f"Removed empty directory: {subdir}")
                except Exception as e:
                    # Log error but continue trying other directories
                    logger.error(f"Failed to remove {subdir}: {e}")

        # Get all subdirectories recursively. AsyncFileIO doesn't have a direct glob.
        # We might need a more specific async walk implementation or stick to to_thread for glob.
        # For now, sticking with to_thread for glob, but operations inside loop are async.
        try:
            subdirs = await asyncio.to_thread(lambda: list(directory.glob("**/")))
        except Exception as e:
            logger.error(f"Error scanning directory {directory} for cleanup: {e}")
            return

        # Process each subdirectory
        # Use asyncio.gather for potentially better performance if many dirs
        tasks = [remove_if_empty(subdir) for subdir in sorted(subdirs, reverse=True)]
        await asyncio.gather(*tasks)
