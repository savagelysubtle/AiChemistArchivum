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
                return mime_type, 0.8  # High confidence for built-in detection

            # Fall back to extension-based detection for common types
            extension = file_path.suffix.lower()
            ext_map = {
                ".txt": "text/plain",
                ".csv": "text/csv",
                ".md": "text/markdown",
                ".json": "application/json",
                ".yml": "application/x-yaml",
                ".yaml": "application/x-yaml",
                ".xml": "application/xml",
                ".html": "text/html",
                ".htm": "text/html",
                ".pdf": "application/pdf",
                ".doc": "application/msword",
                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".xls": "application/vnd.ms-excel",
                ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ".ppt": "application/vnd.ms-powerpoint",
                ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            }

            if extension in ext_map:
                return ext_map[extension], 0.7  # Good confidence for known extensions

            # Last resort: generic binary
            return "application/octet-stream", 0.2  # Low confidence fallback

        except Exception as e:
            logger.error(f"Error determining MIME type: {e}")
            return "application/octet-stream", 0.1  # Very low confidence due to error
