"""
File metadata data class for AIchemist Archivum.

Represents metadata extracted from files including basic file properties
and extracted information.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class FileMetadata:
    """
    Data class representing file metadata.

    Contains both basic file properties (path, size, type) and
    extracted metadata (content, tags, entities, etc.).
    """

    # Basic file properties
    path: Path
    size: int = 0
    mime_type: str | None = None
    extension: str | None = None
    created_at: datetime | None = None
    modified_at: datetime | None = None

    # Content and extracted data
    preview: str | None = None
    content: str | None = None
    parsed_data: dict[str, Any] | None = None

    # Metadata extraction
    extraction_complete: bool = False
    extraction_time: float = 0.0
    error: str | None = None

    # Analysis results
    tags: list[str] = field(default_factory=list)
    topics: list[dict[str, float]] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    entities: dict[str, list[str]] = field(default_factory=dict)
    language: str | None = None
    content_type: str | None = None

    @classmethod
    async def from_path(cls, path: Path) -> "FileMetadata":
        """
        Create FileMetadata from a file path.

        Args:
            path: Path to the file.

        Returns:
            FileMetadata instance with basic file properties.
        """
        import asyncio

        try:
            stat = await asyncio.to_thread(path.stat)

            return cls(
                path=path.resolve(),
                size=stat.st_size,
                extension=path.suffix.lower() if path.suffix else None,
                created_at=datetime.fromtimestamp(stat.st_ctime),
                modified_at=datetime.fromtimestamp(stat.st_mtime),
            )
        except Exception as e:
            logger.error(f"Error creating FileMetadata from path {path}: {e}")
            return cls(
                path=path.resolve(),
                error=str(e),
            )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert metadata to dictionary.

        Returns:
            Dictionary representation of the metadata.
        """
        return {
            "path": str(self.path),
            "size": self.size,
            "mime_type": self.mime_type,
            "extension": self.extension,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
            "preview": self.preview,
            "extraction_complete": self.extraction_complete,
            "extraction_time": self.extraction_time,
            "error": self.error,
            "tags": self.tags,
            "topics": self.topics,
            "keywords": self.keywords,
            "entities": self.entities,
            "language": self.language,
            "content_type": self.content_type,
        }
