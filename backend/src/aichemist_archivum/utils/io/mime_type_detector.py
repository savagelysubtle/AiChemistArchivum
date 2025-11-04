"""MIME type detection utilities."""

import logging
import mimetypes
from pathlib import Path

logger = logging.getLogger(__name__)

# Initialize mimetypes
mimetypes.init()


class MimeTypeDetector:
    """Detects MIME types of files."""

    @staticmethod
    def get_mime_type(file_path: Path) -> tuple[str, float]:
        """
        Determine the MIME type of a file.

        Args:
            file_path: Path to the file

        Returns:
            Tuple of (mime_type, confidence)
        """
        try:
            # Try using the mimetypes library first
            mime_type, _ = mimetypes.guess_type(str(file_path))

            if mime_type:
                return mime_type, 1.0

            # Fall back to extension-based detection
            suffix = file_path.suffix.lower()

            if suffix == ".md":
                return "text/markdown", 1.0
            elif suffix == ".py":
                return "text/x-python", 1.0
            elif suffix == ".txt":
                return "text/plain", 1.0
            elif suffix == ".json":
                return "application/json", 1.0
            elif suffix == ".html" or suffix == ".htm":
                return "text/html", 1.0
            elif suffix == ".css":
                return "text/css", 1.0
            elif suffix == ".js":
                return "application/javascript", 1.0
            elif suffix == ".xml":
                return "application/xml", 1.0
            elif suffix == ".csv":
                return "text/csv", 1.0
            elif suffix == ".yaml" or suffix == ".yml":
                return "application/x-yaml", 1.0
            elif suffix == ".toml":
                return "application/toml", 1.0

            # Unknown type
            return "application/octet-stream", 0.5

        except Exception as e:
            logger.error(f"Error detecting MIME type for {file_path}: {e}")
            return "application/octet-stream", 0.1
