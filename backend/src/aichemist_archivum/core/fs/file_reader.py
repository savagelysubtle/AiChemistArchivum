"""
File reading and parsing module for The Aichemist Codex.
This module provides functionality for reading and parsing various file types,
including text files, documents, spreadsheets, code files, and more.
"""

import asyncio
import logging
from pathlib import Path

# Added imports for refactoring
from aichemist_archivum.config import config
from aichemist_archivum.utils.cache.cache_manager import get_cache_manager
from aichemist_archivum.utils.io.async_io import AsyncFileIO
from aichemist_archivum.utils.io.mime_type_detector import MimeTypeDetector
from aichemist_archivum.utils.threading.thread_pool import get_thread_pool

# Local module imports remain
from .file_metadata import FileMetadata
from .parsers import get_parser_for_mime_type

logger: logging.Logger = logging.getLogger(__name__)


class FileReader:
    """Main class for reading and parsing files with MIME type detection."""

    def __init__(self) -> None:
        """Initialize FileReader using central config and utilities."""
        # Get preview length from config
        self.preview_length = config.get("fs.preview_length", 100)
        self.logger = logging.getLogger(__name__)

        # Use shared utilities
        self.executor = get_thread_pool()
        self.cache_manager = get_cache_manager()
        self.mime_detector = MimeTypeDetector()
        self.async_file_io = AsyncFileIO()

    async def get_mime_type(self, file_path: str | Path) -> str:
        """
        Get the MIME type of a file asynchronously.

        Args:
            file_path: Path to the file

        Returns:
            str: MIME type of the file

        Raises:
            FileNotFoundError: If the file does not exist
        """
        path = Path(file_path).resolve()
        if not await self.async_file_io.exists(path):
            raise FileNotFoundError(f"{path} does not exist.")

        # Use the MimeTypeDetector. Needs to run in thread pool as it might block.
        try:
            # MimeTypeDetector.get_mime_type is synchronous
            mime_type = await asyncio.get_event_loop().run_in_executor(
                self.executor, self.mime_detector.get_mime_type, path
            )
            return mime_type
        except Exception as e:
            logger.warning(f"Error determining MIME type for {path}: {e}")
            # Fallback to octet-stream if detection fails
            return "application/octet-stream"

    async def get_mime_types(self, file_paths: list[str | Path]) -> dict[str, str]:
        """
        Get MIME types for multiple files concurrently.

        Args:
            file_paths: List of file paths to process

        Returns:
            Dict[str, str]: Dictionary mapping file paths to their MIME types
        """
        tasks = [self.get_mime_type(path) for path in file_paths]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        mime_dict = {}
        for path, result in zip(file_paths, results, strict=False):
            path_str = str(path)
            if isinstance(result, Exception):
                logger.error(f"Failed to get MIME type for {path_str}: {result}")
                mime_dict[path_str] = "unknown/error"  # Or handle differently
            else:
                mime_dict[path_str] = result
        return mime_dict

    async def process_file(self, file_path: Path) -> FileMetadata:
        """
        Process a single file to extract its metadata and preview asynchronously.

        Args:
            file_path: Path to the file to process

        Returns:
            FileMetadata: Metadata and preview information for the file
        """
        mime_type = "unknown"
        size = -1
        error_msg = None
        preview = ""
        parsed_data = None

        try:
            # Check if file exists asynchronously
            if not await self.async_file_io.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            # Get MIME type and size concurrently
            tasks = [
                asyncio.create_task(self.get_mime_type(file_path)),
                asyncio.create_task(self.async_file_io.stat(file_path)),
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            mime_result = results[0] if len(results) > 0 else Exception("No MIME result")
            stat_result = results[1] if len(results) > 1 else Exception("No stat result")

            if isinstance(mime_result, Exception):
                logger.warning(
                    f"Could not get MIME type for {file_path}: {mime_result}"
                )
                mime_type: str | None = "application/octet-stream"  # Fallback
                error_msg = f"MIME detection failed: {mime_result!s}"
            else:
                mime_type = str(mime_result) if mime_result else None

            if isinstance(stat_result, Exception):
                logger.error(f"Could not get file stats for {file_path}: {stat_result}")
                # Size remains -1, potentially add to error message
                error_msg = (
                    f"{error_msg}; Stat failed: {stat_result!s}"
                    if error_msg
                    else f"Stat failed: {stat_result!s}"
                )
            else:
                size = stat_result.st_size

            # Create initial metadata object
            metadata = FileMetadata(
                path=file_path,
                mime_type=mime_type,
                size=size,
                extension=file_path.suffix.lower(),
                preview=preview,  # Will be filled below
                error=error_msg,
                parsed_data=parsed_data,
            )

            # Only proceed with parsing if basic metadata retrieval was successful
            if not isinstance(stat_result, Exception):
                parser = get_parser_for_mime_type(mime_type)
                if parser:
                    try:
                        # Assuming parser.parse is now async and uses AsyncFileIO
                        parsed_data = await parser.parse(file_path)
                        # Assuming get_preview is synchronous
                        preview = parser.get_preview(parsed_data, self.preview_length)
                        metadata.preview = preview
                        metadata.parsed_data = parsed_data
                    except Exception as e:
                        parse_error = f"Parsing failed: {e!s}"
                        metadata.error = (
                            f"{metadata.error}; {parse_error}"
                            if metadata.error
                            else parse_error
                        )
                        metadata.preview = f"[Error: {e!s}]"
                        logger.warning(f"Failed to parse {file_path}: {e}")
                else:
                    metadata.preview = f"[No parser available for {mime_type}]"

            return metadata

        except FileNotFoundError as fnf:
            # Handle file not found specifically if exists check somehow passed or race condition
            error_msg = str(fnf)
            logger.error(error_msg)
        except Exception as e:
            # Catch any other unexpected errors during processing
            error_msg = f"Unexpected error processing file {file_path}: {e!s}"
            logger.exception(error_msg)  # Log with stack trace

        # Return error metadata if any exception occurred above
        final_mime_type: str | None = (
            "error" if mime_type == "unknown" else mime_type
        )
        return FileMetadata(
            path=file_path,
            mime_type=final_mime_type,
            size=size,
            extension=file_path.suffix.lower(),
            error=error_msg,
            preview=preview,
            parsed_data=parsed_data,
        )
