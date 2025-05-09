"""Diff engine for The Aichemist Codex versioning system.

This module provides efficient diffing algorithms for various file types,
supporting storage optimization for the versioning system.
"""

import asyncio
import difflib
import hashlib
import logging
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from the_aichemist_codex.infrastructure.utils.io.async_io import AsyncFileIO

logger = logging.getLogger(__name__)


class DiffFormat(Enum):
    """Formats for storing diffs."""

    UNIFIED = "unified"  # Unified diff format
    CONTEXT = "context"  # Context diff format
    BINARY = "binary"  # Binary diff for non-text files
    JSON = "json"  # Special format for JSON files
    CUSTOM = "custom"  # Custom format for special files


@dataclass
class DiffResult:
    """Result of a diff operation.

    Attributes:
        is_different: True if the files differ, False otherwise.
        diff_content: The content of the diff (format depends on diff_format).
        diff_format: The format used for the diff content.
        original_hash: SHA-256 hash of the original file.
        new_hash: SHA-256 hash of the new file.
        change_percentage: Percentage of the file that changed (0-100).
        change_size_bytes: Size of the changes in bytes.
    """

    is_different: bool
    diff_content: str = ""
    diff_format: DiffFormat = DiffFormat.UNIFIED
    original_hash: str = ""
    new_hash: str = ""
    change_percentage: float = 0.0  # Percentage of file that changed
    change_size_bytes: int = 0  # Size of changes in bytes


class DiffEngine:
    """Provides diffing capabilities for various file types.

    This engine calculates differences between file versions and can apply
    diffs to reconstruct specific versions. It supports different diff
    formats based on file types.
    """

    def __init__(self):
        """Initialize the diff engine."""
        self.file_io = AsyncFileIO()
        self._mime_type_handlers = {
            "text": self._diff_text,
            "application/json": self._diff_json,
            "application/xml": self._diff_text,
            "application/x-yaml": self._diff_text,
        }

    async def calculate_diff(
        self, original_path: Path, new_path: Path, mime_type: str | None = None
    ) -> DiffResult:
        """Calculate the difference between two files asynchronously.

        Determines the appropriate diffing strategy based on file type
        (text, binary, or specific MIME types like JSON) and returns the
        result including diff content and change metrics.

        Args:
            original_path: Path to the original file.
            new_path: Path to the new file.
            mime_type: Optional MIME type to override detection and use
                a specific diff strategy.

        Returns:
            A DiffResult object containing the diff information.

        Raises:
            FileNotFoundError: If either the original or new file does not exist.
        """
        # Check if the files exist
        if not await self.file_io.exists(original_path):
            raise FileNotFoundError(f"Original file not found: {original_path}")
        if not await self.file_io.exists(new_path):
            raise FileNotFoundError(f"New file not found: {new_path}")

        # Get file hashes
        original_hash = await self._calculate_file_hash(original_path)
        new_hash = await self._calculate_file_hash(new_path)

        # Quick check if they're identical
        if original_hash == new_hash:
            return DiffResult(
                is_different=False,
                original_hash=original_hash,
                new_hash=new_hash,
                change_percentage=0.0,
                change_size_bytes=0,
            )

        # Determine the appropriate diff method based on MIME type
        if not mime_type:
            # Simplified mime type detection - in a real implementation,
            # we would use a proper MIME type detector
            if await self._is_binary_file(original_path):
                mime_type = "binary"
            else:
                mime_type = "text"

        # Apply the appropriate diff method
        if mime_type.startswith("text/") or mime_type == "text":
            result = await self._diff_text(original_path, new_path)
        elif mime_type in self._mime_type_handlers:
            result = await self._mime_type_handlers[mime_type](original_path, new_path)
        else:
            # Default to binary diff for unsupported types
            result = await self._diff_binary(original_path, new_path)

        # Add hashes to result
        result.original_hash = original_hash
        result.new_hash = new_hash

        return result

    async def apply_diff(
        self,
        base_path: Path,
        diff_path: Path,
        output_path: Path,
        diff_format: DiffFormat = DiffFormat.UNIFIED,
    ) -> bool:
        """Apply a diff patch to a base file to reconstruct a target version.

        Selects the appropriate method to apply the patch based on the
        specified diff format.

        Args:
            base_path: Path to the base file.
            diff_path: Path to the file containing the diff information.
            output_path: Path where the reconstructed file should be written.
            diff_format: The format of the diff stored in diff_path.

        Returns:
            True if the diff was applied successfully, False otherwise.
        """
        try:
            if diff_format == DiffFormat.UNIFIED:
                return await self._apply_unified_diff(base_path, diff_path, output_path)
            elif diff_format == DiffFormat.BINARY:
                return await self._apply_binary_diff(base_path, diff_path, output_path)
            elif diff_format == DiffFormat.JSON:
                return await self._apply_json_diff(base_path, diff_path, output_path)
            else:
                logger.error(f"Unsupported diff format: {diff_format}")
                return False
        except Exception as e:
            logger.error(f"Error applying diff: {e}")
            return False

    async def _diff_text(self, original_path: Path, new_path: Path) -> DiffResult:
        """Calculate the diff for text files using the unified diff format.

        Reads both files, compares them line by line, and generates a
        standard unified diff.

        Args:
            original_path: Path to the original text file.
            new_path: Path to the new text file.

        Returns:
            A DiffResult object containing the unified diff and change metrics.
        """
        # Read file contents
        original_content = await self.file_io.read_text(original_path)
        new_content = await self.file_io.read_text(new_path)

        # Split into lines
        original_lines = original_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        # Calculate diff
        diff = difflib.unified_diff(
            original_lines,
            new_lines,
            fromfile=str(original_path),
            tofile=str(new_path),
        )
        diff_content = "".join(diff)

        # Calculate change metrics
        change_percentage = self._calculate_change_percentage(original_lines, new_lines)
        change_size_bytes = len(diff_content.encode("utf-8"))

        return DiffResult(
            is_different=bool(diff_content),
            diff_content=diff_content,
            diff_format=DiffFormat.UNIFIED,
            change_percentage=change_percentage,
            change_size_bytes=change_size_bytes,
        )

    async def _diff_binary(self, original_path: Path, new_path: Path) -> DiffResult:
        """Handle diff calculation for binary files.

        Note:
            This current implementation does not perform a true binary diff.
            It marks the files as different if their hashes don't match and
            calculates the size of the new file. A placeholder reference to the
            new file path is stored in `diff_content`. A more sophisticated
            implementation would use dedicated binary diffing tools (e.g., xdelta,
            bsdiff).

        Args:
            original_path: Path to the original binary file.
            new_path: Path to the new binary file.

        Returns:
            A DiffResult indicating a binary difference and the size of the new file.
        """
        # For binary files, we simply note they're different if hashes mismatch.
        # Calculate file sizes asynchronously.
        try:
            original_size = await asyncio.to_thread(os.path.getsize, original_path)
            new_size = await asyncio.to_thread(os.path.getsize, new_path)
        except OSError as e:
            logger.error(f"Error getting size for binary diff: {e}")
            original_size = 0
            new_size = 0

        # We don't actually generate a diff for binary files in this example.
        # Instead, we'll store a placeholder referencing the new file.
        return DiffResult(
            is_different=True,
            diff_content=f"BINARY_DIFF:{new_path}",  # Placeholder reference
            diff_format=DiffFormat.BINARY,
            change_percentage=100.0,  # Consider it a full change for binary files
            change_size_bytes=new_size,
        )

    async def _diff_json(self, original_path: Path, new_path: Path) -> DiffResult:
        """Calculate a structured diff for JSON files.

        Note:
            Currently falls back to standard text diff. A future enhancement
            could use a JSON-specific diff library (e.g., `jsonpatch`, `jsondiffpatch`)
            for more semantic comparisons.

        Args:
            original_path: Path to the original JSON file.
            new_path: Path to the new JSON file.

        Returns:
            A DiffResult object, currently using the unified text diff format.
        """
        # In a real implementation, we would use a JSON-specific diff algorithm.
        # For now, just use text diff.
        return await self._diff_text(original_path, new_path)

    async def _apply_unified_diff(
        self, base_path: Path, diff_path: Path, output_path: Path
    ) -> bool:
        """Apply a unified diff patch to a base text file.

        Note:
            Uses a mock patching implementation (`_mock_apply_patch`).
            A real implementation should use a robust patching library (e.g., the
            `patch` utility or a Python equivalent).

        Args:
            base_path: Path to the base text file.
            diff_path: Path to the unified diff file.
            output_path: Path where the reconstructed file will be written.

        Returns:
            True if the mock application was successful, False on error.
        """
        try:
            # Read the base file and diff
            base_content = await self.file_io.read_text(base_path)
            diff_content = await self.file_io.read_text(diff_path)

            # Parse the unified diff
            base_lines = base_content.splitlines(keepends=True)

            # Apply the diff using the patch module
            # In a real implementation, we would use a proper patch library
            # For simplicity, we're using a mock implementation here
            patched_content = self._mock_apply_patch(base_lines, diff_content)

            # Write the result
            return await self.file_io.write(output_path, patched_content)
        except Exception as e:
            logger.error(f"Error applying unified diff: {e}")
            return False

    async def _apply_binary_diff(
        self, base_path: Path, diff_path: Path, output_path: Path
    ) -> bool:
        """Apply a binary diff to recreate a file.

        Note:
            Based on the simplified `_diff_binary`, this assumes the `diff_path`
            contains a text file whose content is the placeholder
            `BINARY_DIFF:<path_to_new_file>`. It then copies the referenced new file.

        Args:
            base_path: Path to the base file (potentially unused in this strategy).
            diff_path: Path to the file containing the placeholder diff info.
            output_path: Path where the reconstructed (copied) file will be written.

        Returns:
            True if the file was copied successfully, False otherwise.
        """
        # In our simplified implementation, the diff is actually the full new file
        # So we just copy it to the output path
        try:
            # Read the diff placeholder
            diff_content = await self.file_io.read_text(diff_path)
            if diff_content.startswith("BINARY_DIFF:"):
                # Extract the reference to the new file
                new_file_path = Path(diff_content.split(":", 1)[1])
                # Copy the new file to the output
                return await self.file_io.copy(new_file_path, output_path)
            return False
        except Exception as e:
            logger.error(f"Error applying binary diff: {e}")
            return False

    async def _apply_json_diff(
        self, base_path: Path, diff_path: Path, output_path: Path
    ) -> bool:
        """Apply a JSON diff to recreate a file.

        Note:
            Currently falls back to applying a unified text diff.
            A future enhancement mirroring `_diff_json` would use a JSON-specific
            patch application method.

        Args:
            base_path: Path to the base JSON file.
            diff_path: Path to the diff file (assumed unified format for now).
            output_path: Path where the reconstructed file will be written.

        Returns:
            True if the unified diff application was successful, False otherwise.
        """
        # For now, this is the same as applying a unified diff
        return await self._apply_unified_diff(base_path, diff_path, output_path)

    def _calculate_change_percentage(
        self, original_lines: list[str], new_lines: list[str]
    ) -> float:
        """Calculate the percentage difference between two lists of lines.

        Uses `difflib.SequenceMatcher` to find the ratio of similarity and
        converts it to a percentage difference.

        Args:
            original_lines: A list of strings representing lines from the original file.
            new_lines: A list of strings representing lines from the new file.

        Returns:
            The percentage of lines that are different (0.0 to 100.0).
        """
        if not original_lines and not new_lines:
            return 0.0
        if not original_lines:
            return 100.0  # All new lines

        matcher = difflib.SequenceMatcher(None, original_lines, new_lines)
        similarity = matcher.ratio()
        return (1 - similarity) * 100

    def _mock_apply_patch(self, base_lines: list[str], diff_content: str) -> str:
        """Mock implementation of applying a unified diff patch.

        Warning:
            This is **not** a functional patch application. It simply returns the
            original content with a comment appended. Replace with a proper patch
            library for actual use.

        Args:
            base_lines: Lines from the base file.
            diff_content: Unified diff content (unused in this mock).

        Returns:
            The original base content concatenated with a comment.
        """
        # This is a simplified mock - in reality we would use a proper patch library
        # For now, just return the base content with a note
        return "".join(base_lines) + "\n# Patched with diff\n"

    async def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate the SHA-256 hash of a file asynchronously.

        Reads the file in chunks to handle potentially large files efficiently.

        Args:
            file_path: The path to the file.

        Returns:
            The hex digest of the SHA-256 hash, or an empty string if an error occurs.
        """
        try:
            hasher = hashlib.sha256()

            # Use chunked reading for efficiency
            async for chunk in self.file_io.read_chunked(file_path, chunk_size=8192):
                hasher.update(chunk)

            return hasher.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return ""

    async def _is_binary_file(self, file_path: Path) -> bool:
        """Attempt to detect if a file is binary by checking the first few bytes.

        Reads the beginning of the file and checks for null bytes or a high
        proportion of bytes outside the typical ASCII text range.

        Args:
            file_path: The path to the file.

        Returns:
            True if the file seems binary, False otherwise or if empty.
            Returns True if an error occurs during reading (e.g., permission denied).
        """
        try:
            # Read the first chunk of the file
            chunk = None
            async for data in self.file_io.read_chunked(
                file_path, chunk_size=8192, buffer_limit=1
            ):
                chunk = data
                break

            if not chunk:
                return False

            # Check for null bytes or high concentration of non-ASCII characters
            text_chars = set(bytes(range(32, 127)) + b"\n\r\t\f\b")
            return bool(any(byte not in text_chars for byte in chunk[:1024]))
        except Exception:
            # If we can't open the file, assume it's binary
            return True
