"""File utility functions."""

import asyncio
from pathlib import Path
from typing import Any

from aichemist_archivum.core.extraction.mime_detector import MimeTypeDetector


async def get_mime_type(
    file_path: Path, content: bytes | str | None = None
) -> str | None:
    """Placeholder: Asynchronously get MIME type.
    `content` is not used in this placeholder but kept for signature compatibility.
    """
    # In a real implementation, if content is provided and large,
    # it might be used directly with a library like `python-magic`
    # without reading the file again. For now, uses MimeTypeDetector.
    detector = MimeTypeDetector()
    try:
        # MimeTypeDetector.get_mime_type is synchronous
        mime, _ = await asyncio.to_thread(detector.get_mime_type, file_path)
        return mime
    except Exception:
        return None


async def get_file_info_basic(file_path: Path) -> dict[str, Any]:
    """Placeholder: Asynchronously get basic file info (size, timestamps)."""
    try:
        stat_result = await asyncio.to_thread(file_path.stat)
        return {
            "size": stat_result.st_size,
            "created_at": stat_result.st_ctime,  # Note: ctime is platform-dependent (creation or metadata change)
            "modified_at": stat_result.st_mtime,
            "accessed_at": stat_result.st_atime,
        }
    except FileNotFoundError:
        return {"size": -1, "error": "File not found"}
    except Exception as e:
        return {"size": -1, "error": str(e)}
