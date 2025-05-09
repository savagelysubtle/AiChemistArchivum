"""File parsers module for the AIchemist Codex.

This module provides functionality to select and use the appropriate parser
for different file types based on MIME type.
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

# Added imports
from the_aichemist_codex.infrastructure.utils import AsyncFileIO

logger: logging.Logger = logging.getLogger(__name__)

# Instantiate AsyncFileIO once for potential reuse
async_file_io = AsyncFileIO()


class BaseParser(ABC):
    """Abstract base class for file parsers."""

    @abstractmethod
    async def parse(self, file_path: Path) -> dict[str, Any]:
        """
        Parse a file asynchronously and return its structured data.

        Args:
            file_path: Path to the file to parse

        Returns:
            A dictionary containing parsed data (keys may differ by parser).
        """
        pass

    @abstractmethod
    def get_preview(self, parsed_data: dict[str, Any], max_length: int = 1000) -> str:
        """
        Generate a textual preview for the parsed data.

        Args:
            parsed_data: The dictionary returned by `parse()`
            max_length: Maximum length of the preview string

        Returns:
            A string preview of the data
        """
        pass


class TextParser(BaseParser):
    """Parser for basic text files (TXT, MD, etc.)."""

    async def parse(self, file_path: Path) -> dict[str, Any]:
        """Parse a text file asynchronously using AsyncFileIO."""
        content = ""
        encoding = ""
        line_count = 0
        error = None

        try:
            # Try reading with UTF-8 first
            content = await async_file_io.read_text(file_path, encoding="utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            logger.warning(f"UTF-8 decoding failed for {file_path}, trying latin-1.")
            try:
                # Fallback to Latin-1
                content = await async_file_io.read_text(file_path, encoding="latin-1")
                encoding = "latin-1"
            except Exception as e:
                error_msg = f"Error parsing {file_path} with fallback encoding: {e!s}"
                logger.error(error_msg)
                error = error_msg
        except Exception as e:
            error_msg = f"Error reading/parsing text file {file_path}: {e!s}"
            logger.error(error_msg)
            error = error_msg

        if content:
            line_count = content.count("\n") + 1

        return {
            "content": content,
            "encoding": encoding,
            "line_count": line_count,
            "error": error,
        }

    def get_preview(self, parsed_data: dict[str, Any], max_length: int = 1000) -> str:
        """Get a preview of the text content."""
        content = parsed_data.get("content", "")
        if not content:
            return "[No content]"

        return content[:max_length] + "..." if len(content) > max_length else content


# Try to use the more comprehensive parser system if available
try:
    # Simplified import, directly from the package
    from the_aichemist_codex.infrastructure.fs.parsers import (
        get_parser_for_mime_type as parsing_get_parser,
    )

    # Flag to indicate if we have access to the main parsing module
    HAS_PARSING_MODULE = True
except ImportError:
    HAS_PARSING_MODULE = False
    parsing_get_parser = None


def get_parser_for_mime_type(mime_type: str) -> BaseParser | None:
    """
    Get the appropriate parser for a given MIME type.

    This function tries to use the comprehensive parser system from the parsing module
    if available, otherwise falls back to a simple implementation.

    Args:
        mime_type: The MIME type of the file

    Returns:
        A parser instance appropriate for the given MIME type
        or None if no parser is available
    """
    # Try to use the comprehensive parser system first
    if HAS_PARSING_MODULE and parsing_get_parser:
        try:
            return parsing_get_parser(mime_type)
        except Exception as e:
            logger.warning(f"Error using main parser system for {mime_type}: {e!s}")
            # Fall back to simplified implementation

    # Fallback simplified implementation
    if mime_type.startswith("text/"):
        return TextParser()

    # Handle code file types that don't start with text/
    code_mime_types = [
        "application/javascript",
        "application/json",
        "application/xml",
        "application/toml",
        "application/x-yaml",
    ]
    if mime_type in code_mime_types:
        return TextParser()

    # For other types, we don't have a simple fallback
    logger.debug(f"No parser available for MIME type: {mime_type}")
    return None
