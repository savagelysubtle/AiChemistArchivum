"""File metadata module for The AIchemist Codex."""

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from the_aichemist_codex.infrastructure.utils import AsyncFileIO, get_thread_pool
from the_aichemist_codex.infrastructure.utils.io import MimeTypeDetector

logger = logging.getLogger(__name__)
async_file_io = AsyncFileIO()
mime_detector = MimeTypeDetector()
thread_pool = get_thread_pool()


@dataclass
class FileMetadata:
    """Class for storing file metadata.

    This class holds basic file information as well as rich metadata
    extracted from file content through content analysis.
    """

    path: Path
    mime_type: str
    size: int
    extension: str
    preview: str = ""
    error: str | None = None
    parsed_data: Any | None = None

    # Content-based metadata fields
    tags: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    topics: list[dict[str, float]] = field(default_factory=list)
    entities: dict[str, list[str]] = field(default_factory=dict)
    language: str | None = None
    content_type: str | None = None
    category: str | None = None
    summary: str | None = None

    # For code files
    programming_language: str | None = None
    imports: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    complexity_score: float | None = None

    # For document files
    title: str | None = None
    author: str | None = None
    creation_date: str | None = None
    modified_date: str | None = None

    # Extraction metadata
    extraction_complete: bool = False
    extraction_confidence: float = 0.0
    extraction_time: float = 0.0

    def __post_init__(self) -> None:
        """Ensure extension starts with a dot and is lowercase."""
        if self.extension and not self.extension.startswith("."):
            self.extension = f".{self.extension}"
        self.extension = self.extension.lower()

    @property
    def filename(self) -> str:
        """Get the filename from the path."""
        return self.path.name

    @classmethod
    async def from_path(cls, path: Path) -> "FileMetadata":
        """Create basic metadata from a file path asynchronously.

        Args:
            path: Path to the file

        Returns:
            FileMetadata object with basic information
        """
        size = -1
        mime_type = "unknown"
        error_str = None
        extension = path.suffix.lower()

        try:
            path = path.resolve()
            exists = await async_file_io.exists(path)

            if exists:
                try:
                    stat_task = asyncio.create_task(async_file_io.stat(path))
                    mime_task = asyncio.create_task(
                        asyncio.get_event_loop().run_in_executor(
                            thread_pool, mime_detector.get_mime_type, path
                        )
                    )

                    stat_result, mime_result = await asyncio.gather(
                        stat_task, mime_task, return_exceptions=True
                    )

                    if isinstance(stat_result, Exception):
                        logger.warning(f"Failed to get stat for {path}: {stat_result}")
                        error_str = f"Stat failed: {stat_result!s}"
                    else:
                        size = stat_result.st_size

                    if isinstance(mime_result, Exception):
                        logger.warning(
                            f"Failed to get MIME type for {path}: {mime_result}"
                        )
                        mime_type = "application/octet-stream"
                        error_str = (
                            f"{error_str}; MIME detection failed: {mime_result!s}"
                            if error_str
                            else f"MIME detection failed: {mime_result!s}"
                        )
                    else:
                        mime_type = mime_result

                except Exception as gather_exc:
                    logger.error(
                        f"Error during concurrent stat/mime fetch for {path}: {gather_exc}"
                    )
                    error_str = f"Concurrent fetch failed: {gather_exc!s}"
                    if mime_type == "unknown":
                        mime_type = "application/octet-stream"
            else:
                error_str = "File does not exist"
                logger.warning(f"File not found when creating metadata: {path}")

            return cls(
                path=path,
                mime_type=mime_type,
                size=size,
                extension=extension,
                preview="",
                error=error_str,
            )
        except Exception as e:
            logger.exception(f"Unexpected error creating FileMetadata for {path}: {e}")
            return cls(
                path=path,
                mime_type="error",
                size=-1,
                extension=extension,
                preview="",
                error=f"Unexpected error: {e!s}",
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary.

        Returns:
            Dictionary representation of metadata
        """
        result = {
            "path": str(self.path),
            "filename": self.filename,
            "mime_type": self.mime_type,
            "size": self.size,
            "extension": self.extension,
            "preview_length": len(self.preview) if self.preview else 0,
            "tags": self.tags,
            "keywords": self.keywords,
            "language": self.language,
            "content_type": self.content_type,
            "category": self.category,
            "extraction_complete": self.extraction_complete,
            "extraction_confidence": self.extraction_confidence,
        }

        if self.error:
            result["error"] = self.error
        if self.summary:
            result["summary"] = self.summary
        if self.programming_language:
            result["programming_language"] = self.programming_language
        if self.complexity_score is not None:
            result["complexity_score"] = self.complexity_score

        return result

    def __str__(self) -> str:
        """String representation of metadata."""
        return f"FileMetadata({self.path.name}, {self.mime_type}, {self.size} bytes)"
