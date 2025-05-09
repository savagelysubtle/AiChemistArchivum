"""
Change detection and classification for The Aichemist Codex.

This module provides functionality to detect and classify different types of changes
in monitored files, with specific detection algorithms for various file types.
"""

import asyncio
import difflib
import hashlib
import logging
import time
from enum import Enum
from pathlib import Path

import aiofiles

from the_aichemist_codex.infrastructure.config import config
from the_aichemist_codex.infrastructure.utils import AsyncFileIO, SafeFileHandler

logger: logging.Logger = logging.getLogger(__name__)


class ChangeSeverity(Enum):
    """Classification of change severity levels."""

    MINOR = 1  # Small changes that don't significantly alter the file
    MODERATE = 2  # Notable changes that modify some important aspects
    MAJOR = 3  # Substantial changes that significantly alter the file
    CRITICAL = 4  # Fundamental changes that completely transform the file


class ChangeType(Enum):
    """Types of changes that can be detected."""

    CONTENT = 1  # Content changes within the file
    METADATA = 2  # Changes to file metadata like permissions or timestamps
    RENAME = 3  # File was renamed
    MOVE = 4  # File was moved to a new location
    CREATE = 5  # File was newly created
    DELETE = 6  # File was deleted


class ChangeInfo:
    """Stores information about a detected change."""

    def __init__(
        self,
        file_path: Path,
        change_type: ChangeType,
        severity: ChangeSeverity,
        timestamp: float | None = None,
        details: dict | None = None,
        old_path: Path | None = None,
    ) -> None:
        """
        Initialize change information.

        Args:
            file_path: Path to the changed file
            change_type: Type of change that occurred
            severity: Severity classification of the change
            timestamp: When the change occurred (defaults to now)
            details: Additional details about the change
            old_path: Previous path for renamed/moved files
        """
        self.file_path = file_path
        self.change_type = change_type
        self.severity = severity
        self.timestamp = timestamp or time.time()
        self.details = details or {}
        self.old_path = old_path

    def to_dict(self) -> dict:
        """Convert change info to a dictionary for serialization."""
        return {
            "file_path": str(self.file_path),
            "change_type": self.change_type.name,
            "severity": self.severity.name,
            "timestamp": self.timestamp,
            "details": self.details,
            "old_path": str(self.old_path) if self.old_path else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChangeInfo":
        """Create from a dictionary representation."""
        return cls(
            file_path=Path(data["file_path"]),
            change_type=ChangeType[data["change_type"]],
            severity=ChangeSeverity[data["severity"]],
            timestamp=data["timestamp"],
            details=data["details"],
            old_path=Path(data["old_path"]) if data["old_path"] else None,
        )

    def __str__(self) -> str:
        """String representation of the change."""
        return (
            f"Change[{self.change_type.name}] in {self.file_path} "
            f"(Severity: {self.severity.name})"
        )


class ChangeDetector:
    """
    Detects and classifies different types of changes in files.

    Features:
    - Content-based change detection for text files
    - Hash-based detection for binary files
    - Smart debounce for rapid sequential changes
    - Change severity classification
    """

    def __init__(self) -> None:
        """Initialize the change detector with debounce settings."""
        self.file_cache: dict[str, dict] = {}
        self.debounce_interval = config.get("change_debounce_interval", 2.0)
        self.debounce_buffer: dict[str, tuple[float, asyncio.Task]] = {}
        self.txt_extensions = {
            ".txt",
            ".md",
            ".py",
            ".js",
            ".html",
            ".css",
            ".json",
            ".xml",
            ".yml",
            ".yaml",
            ".csv",
        }
        self.max_text_size = config.get(
            "max_text_diff_size", 1024 * 1024
        )  # 1MB default

        # Thresholds for severity classification
        self.minor_threshold = config.get("minor_change_threshold", 0.05)  # 5% changed
        self.moderate_threshold = config.get(
            "moderate_change_threshold", 0.25
        )  # 25% changed
        self.major_threshold = config.get("major_change_threshold", 0.50)  # 50% changed
        # Above major_threshold is considered CRITICAL

        self.async_file_io = AsyncFileIO()

    async def detect_change(self, file_path: Path) -> ChangeInfo | None:
        """
        Detect changes in a file compared to its previously known state.
        For new files, establishes a baseline.

        Args:
            file_path: Path to the file to check

        Returns:
            ChangeInfo object if a change is detected, None otherwise
        """
        if not file_path.exists():
            # File was deleted or moved, handled by the event handler
            return None

        # Skip ignored files
        if SafeFileHandler.should_ignore(file_path):
            return None

        # Implement smart debounce
        path_str = str(file_path)
        current_time = time.time()

        # If there's an existing debounce task for this file
        if path_str in self.debounce_buffer:
            last_time, task = self.debounce_buffer[path_str]

            # If it's within the debounce interval, cancel the old task and schedule a new one
            if current_time - last_time < self.debounce_interval:
                if not task.done():
                    task.cancel()

                # Create a new task with the current file state
                new_task = asyncio.create_task(
                    self._delayed_process(file_path, self.debounce_interval)
                )
                self.debounce_buffer[path_str] = (current_time, new_task)
                return None

        # No active debounce, process immediately
        return await self._process_change(file_path)

    async def _delayed_process(
        self, file_path: Path, delay: float
    ) -> ChangeInfo | None:
        """
        Process a file change after a delay to handle rapid sequential changes.

        Args:
            file_path: Path to the file to check
            delay: Time to wait before processing

        Returns:
            ChangeInfo if a change is detected, None otherwise
        """
        await asyncio.sleep(delay)
        path_str = str(file_path)

        # Remove from debounce buffer when processing
        if path_str in self.debounce_buffer:
            del self.debounce_buffer[path_str]

        return await self._process_change(file_path)

    async def _process_change(self, file_path: Path) -> ChangeInfo | None:
        """
        Process a file to detect changes compared to cache.

        Args:
            file_path: Path to the file to check

        Returns:
            ChangeInfo if a change is detected, None otherwise
        """
        path_str = str(file_path)

        try:
            # Get current file stats using asyncio.to_thread as direct async stat may not exist
            stats = await asyncio.to_thread(file_path.stat)
            modified_time = stats.st_mtime
            file_size = stats.st_size

            # Check cache for previous state
            if path_str in self.file_cache:
                # File exists in cache, compare for changes
                cached = self.file_cache[path_str]

                # Check if modified time is different
                if modified_time == cached.get(
                    "modified_time"
                ) and file_size == cached.get("file_size"):
                    # No changes detected based on stats
                    return None

                # Determine file type and appropriate detection method
                is_text = await self._is_text_file(file_path)

                if is_text and file_size <= self.max_text_size:
                    # Use content-based detection for text files
                    return await self._detect_text_changes(file_path, cached)
                else:
                    # Use hash-based detection for binary or large files
                    return await self._detect_binary_changes(file_path, cached)
            else:
                # New file, add to cache
                file_hash = await self._calculate_file_hash(file_path)

                # Store in cache
                self.file_cache[path_str] = {
                    "modified_time": modified_time,
                    "file_size": file_size,
                    "hash": file_hash,
                    "content": None,  # Don't store content by default
                }

                # First time seeing this file, treat as creation
                return ChangeInfo(
                    file_path=file_path,
                    change_type=ChangeType.CREATE,
                    severity=ChangeSeverity.MODERATE,
                    details={"size": file_size},
                )
        except Exception as e:
            logger.error(f"Error detecting changes for {file_path}: {e}")
            return None

    async def _is_text_file(self, file_path: Path) -> bool:
        """
        Determine if a file is a text file based on extension and content sampling.

        Args:
            file_path: Path to check

        Returns:
            True if the file appears to be text, False otherwise
        """
        # Quick check based on extension
        if file_path.suffix.lower() in self.txt_extensions:
            return True

        if SafeFileHandler.is_binary_file(file_path):
            return False

        # Sample the first few KB to check for binary content
        try:
            sample_size = min(4096, (await asyncio.to_thread(file_path.stat)).st_size)
            if sample_size == 0:
                return True  # Empty file is considered text

            # Use AsyncFileIO to read a sample chunk asynchronously
            sample = await self.async_file_io.read_chunk(
                file_path, size=sample_size, mode="rb"
            )

            # Check for null bytes which indicate binary content
            return b"\0" not in sample
        except Exception as e:
            logger.warning(f"Error checking if file is text: {file_path}, {e}")
            return False

    async def _detect_text_changes(
        self, file_path: Path, cached: dict
    ) -> ChangeInfo | None:
        """
        Detect changes in text files using diff algorithms.

        Args:
            file_path: Path to the text file
            cached: Cached information about the file

        Returns:
            ChangeInfo with details about the changes
        """
        try:
            # Read current content using AsyncFileIO
            current_content = await self.async_file_io.read_text(
                file_path, encoding="utf-8"
            )

            # If we don't have cached content, read it now
            cached_content = cached.get("content")
            if cached_content is None:
                # No previous content to compare, update cache and return
                file_hash = await self._calculate_file_hash(file_path)
                stats = await asyncio.to_thread(file_path.stat)
                self.file_cache[str(file_path)].update(
                    {
                        "hash": file_hash,
                        "content": current_content,
                        "modified_time": stats.st_mtime,
                        "file_size": stats.st_size,
                    }
                )
                return None

            # Calculate diff between versions
            diff = list(
                difflib.unified_diff(
                    cached_content.splitlines(), current_content.splitlines()
                )
            )

            if not diff:
                # No actual content changes despite stat changes
                return None

            # Count added/removed lines
            added = sum(
                1
                for line in diff
                if line.startswith("+") and not line.startswith("+++")
            )
            removed = sum(
                1
                for line in diff
                if line.startswith("-") and not line.startswith("---")
            )
            total_lines = max(
                len(cached_content.splitlines()), len(current_content.splitlines())
            )

            # Calculate change percentage
            change_percentage = (
                (added + removed) / total_lines if total_lines > 0 else 0
            )

            # Determine severity based on percentage changed
            severity = self._classify_severity(change_percentage)

            # Update cache with new content
            stats = await asyncio.to_thread(file_path.stat)
            self.file_cache[str(file_path)].update(
                {
                    "content": current_content,
                    "modified_time": stats.st_mtime,
                    "file_size": stats.st_size,
                    "hash": await self._calculate_file_hash(file_path),
                }
            )

            return ChangeInfo(
                file_path=file_path,
                change_type=ChangeType.CONTENT,
                severity=severity,
                details={
                    "added_lines": added,
                    "removed_lines": removed,
                    "total_lines": total_lines,
                    "change_percentage": change_percentage,
                },
            )
        except UnicodeDecodeError:
            # File isn't valid text, use hash-based detection instead
            return await self._detect_binary_changes(file_path, cached)
        except Exception as e:
            logger.error(f"Error detecting text changes: {file_path}, {e}")
            return None

    async def _detect_binary_changes(
        self, file_path: Path, cached: dict
    ) -> ChangeInfo | None:
        """
        Detect changes in binary files using hash comparison.

        Args:
            file_path: Path to the binary file
            cached: Cached information about the file

        Returns:
            ChangeInfo with basic change details
        """
        try:
            # Calculate current file hash asynchronously
            current_hash = await self._calculate_file_hash(file_path)
            cached_hash = cached.get("hash")

            if current_hash == cached_hash:
                # No change detected based on hash
                return None

            # Hash differs, update cache
            stats = await asyncio.to_thread(file_path.stat)
            self.file_cache[str(file_path)].update(
                {
                    "hash": current_hash,
                    "modified_time": stats.st_mtime,
                    "file_size": stats.st_size,
                    "content": None,  # Invalidate potentially stale content
                }
            )

            # Determine severity based on size difference (simple heuristic)
            cached_size = cached.get("file_size", 0)
            current_size = stats.st_size
            size_diff_ratio = (
                abs(current_size - cached_size) / max(cached_size, 1)
                if cached_size > 0
                else 1.0
            )
            severity = self._classify_severity(size_diff_ratio)

            return ChangeInfo(
                file_path=file_path,
                change_type=ChangeType.CONTENT,
                severity=severity,
                details={
                    "old_size": cached_size,
                    "new_size": current_size,
                    "size_diff_ratio": size_diff_ratio,
                },
            )
        except Exception as e:
            logger.error(f"Error detecting binary changes: {file_path}, {e}")
            return None

    async def _calculate_file_hash(self, file_path: Path) -> str:
        """
        Calculate the SHA-256 hash of a file asynchronously.

        Args:
            file_path: Path to the file

        Returns:
            SHA-256 hash of the file content as a hex string
        """
        hasher = hashlib.sha256()
        try:
            # Use aiofiles for async reading
            async with aiofiles.open(file_path, "rb") as f:
                while True:
                    chunk = await f.read(8192)  # Read in 8KB chunks
                    if not chunk:
                        break
                    # Run the hashing update in a thread to avoid blocking event loop
                    # Although hashlib operations are often C-optimized and might release GIL,
                    # for large files or busy loops, this is safer.
                    hasher = await asyncio.to_thread(self._update_hasher, hasher, chunk)
            return await asyncio.to_thread(hasher.hexdigest)
        except FileNotFoundError:
            logger.warning(f"File not found during hash calculation: {file_path}")
            return ""
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return ""

    # Helper function to run hasher update in thread
    def _update_hasher(self, hasher, chunk):
        hasher.update(chunk)
        return hasher

    def _classify_severity(self, change_percentage: float) -> ChangeSeverity:
        """
        Classify the severity of a change based on a percentage metric.

        Args:
            change_percentage: Percentage of file that changed (0.0-1.0)

        Returns:
            ChangeSeverity classification
        """
        if change_percentage <= self.minor_threshold:
            return ChangeSeverity.MINOR
        elif change_percentage <= self.moderate_threshold:
            return ChangeSeverity.MODERATE
        elif change_percentage <= self.major_threshold:
            return ChangeSeverity.MAJOR
        else:
            return ChangeSeverity.CRITICAL
