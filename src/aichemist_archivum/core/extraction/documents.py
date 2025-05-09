"""Document metadata extractor for extracting information from document files.

This module provides functionality for analyzing document content to extract
titles, authors, dates, and other metadata from document files.
"""

# mypy: disable-error-code="return-value"

import logging
import re
import time
from pathlib import Path
from typing import TypedDict

from the_aichemist_codex.infrastructure.fs.file_metadata import FileMetadata

from .base_extractor import BaseMetadataExtractor, MetadataExtractorRegistry

logger = logging.getLogger(__name__)


class DocumentStatisticsDict(TypedDict):
    word_count: int
    estimated_page_count: int
    character_count: int
    paragraph_count: int
    section_count: int


class DocumentMetadataDict(TypedDict):
    authors: list[str]
    title: str
    date: str
    version: str
    statistics: DocumentStatisticsDict
    keywords: list[str] | None
    extraction_complete: bool
    extraction_confidence: float
    extraction_time: float
    error: str | None


@MetadataExtractorRegistry.register
class DocumentMetadataExtractor(BaseMetadataExtractor):
    """Metadata extractor for document files.

    Analyzes document content to extract author information, titles, creation dates,
    page counts, and other document-specific metadata.
    """

    def __init__(self) -> None:
        """Initialize the document metadata extractor."""
        super().__init__()

        # Common patterns for extracting document metadata
        self.author_patterns = [
            r"Author:?\s*([^,\r\n]+)",
            r"by\s+([^,\r\n]+)",
            r"created\s+by\s+([^,\r\n]+)",
        ]

        self.title_patterns = [
            r"Title:?\s*([^\r\n]+)",
            r"Subject:?\s*([^\r\n]+)",
            r"Document\s+Name:?\s*([^\r\n]+)",
        ]

        self.date_patterns = [
            r"Date:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"Created:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"Modified:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"(\d{1,2}\s+\w+\s+\d{2,4})",  # 15 January 2023 format
        ]

        self.version_patterns = [
            r"Version:?\s*([\d.]+)",
            r"Rev(?:ision)?:?\s*([\d.]+)",
            r"v([\d.]+)",
        ]

    @property
    def supported_mime_types(self) -> list[str]:
        """List of MIME types supported by this extractor."""
        return [
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/epub+zip",
            "application/rtf",
            "text/markdown",
            "text/plain",
            "application/x-latex",
        ]

    async def extract(
        self,
        file_path: str | Path,
        content: str | None = None,
        mime_type: str | None = None,
        metadata: FileMetadata | None = None,
    ) -> DocumentMetadataDict:
        """Extract metadata from a document file.

        Args:
            file_path: Path to the file
            content: Optional pre-loaded file content
            mime_type: Optional MIME type of the file
            metadata: Optional existing metadata to enhance

        Returns:
            A DocumentMetadataDict containing extracted metadata
        """
        start_time = time.time()

        # Convert file_path to Path object
        if isinstance(file_path, str):
            file_path = Path(file_path)

        # If this is a binary document format, use specialized extraction if available
        # For this implementation, we'll focus on text-based documents

        # Get the content if not provided
        if content is None:
            content = await self._get_content(file_path)
            if not content:
                return {
                    "error": "Failed to read file content",
                    "extraction_complete": False,
                    "extraction_confidence": 0.0,
                    "extraction_time": time.time() - start_time,
                    "authors": [],
                    "title": "",
                    "date": "",
                    "version": "",
                    "statistics": {
                        "word_count": 0,
                        "estimated_page_count": 0,
                        "character_count": 0,
                        "paragraph_count": 0,
                        "section_count": 0,
                    },
                    "keywords": None,
                }

        # Extract document metadata
        extracted_data: DocumentMetadataDict = {
            "authors": [],
            "title": "",
            "date": "",
            "version": "",
            "statistics": {
                "word_count": 0,
                "estimated_page_count": 0,
                "character_count": 0,
                "paragraph_count": 0,
                "section_count": 0,
            },
            "keywords": None,
            "extraction_complete": False,
            "extraction_confidence": 0.0,
            "extraction_time": 0.0,
            "error": None,
        }

        # Try to extract basic document metadata using regular expressions
        authors = self._extract_authors(content)
        extracted_data["authors"] = authors

        title = self._extract_title(content, file_path)
        extracted_data["title"] = title

        date = self._extract_date(content)
        extracted_data["date"] = date

        version = self._extract_version(content)
        extracted_data["version"] = version

        # Calculate document statistics
        statistics = self._calculate_statistics(content)
        extracted_data["statistics"] = statistics

        # Extract keywords and topics if this is a text document
        if mime_type and mime_type.startswith("text/"):
            # For simplicity, we'll use a basic keyword extraction
            keywords = self._extract_keywords(content)
            extracted_data["keywords"] = keywords

        # Mark extraction as complete
        extracted_data["extraction_complete"] = True
        extracted_data["extraction_confidence"] = 0.7  # Reasonable default
        extracted_data["extraction_time"] = time.time() - start_time
        extracted_data["error"] = None  # Ensure error is None on success

        return extracted_data

    def _extract_authors(self, content: str) -> list[str]:
        """Extract author information from document content.

        Args:
            content: Document content

        Returns:
            A list of detected authors
        """
        authors = []
        for pattern in self.author_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            authors.extend([match.strip() for match in matches if match.strip()])

        # Remove duplicates and return
        return list(set(authors))

    def _extract_title(self, content: str, file_path: Path) -> str:
        """Extract title from document content.

        Args:
            content: Document content
            file_path: Path to the file (used as fallback)

        Returns:
            The extracted title or filename if no title found
        """
        # Try to find a title in the content
        for pattern in self.title_patterns:
            matches = re.search(pattern, content, re.IGNORECASE)
            if matches and matches.group(1).strip():
                return matches.group(1).strip()

        # For markdown files, try to extract the first heading
        if file_path.suffix.lower() in [".md", ".markdown"]:
            md_title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            if md_title_match:
                return md_title_match.group(1).strip()

        # If no title found, use the filename (without extension) as a fallback
        return file_path.stem

    def _extract_date(self, content: str) -> str:
        """Extract date from document content.

        Args:
            content: Document content

        Returns:
            The extracted date string or empty string if no date found
        """
        # Extract all dates from the content
        found_dates: list[str] = []
        try:
            # Look for dates in various formats
            date_patterns = [
                r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",  # MM/DD/YYYY or DD-MM-YYYY
                r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",  # YYYY-MM-DD
                r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b",  # Month DD, YYYY
            ]

            for pattern in date_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                found_dates.extend(matches)

            # Look for a creation date specifically
            creation_match = re.search(
                r"(created|date|published).*?(\d+[/-]\d+[/-]\d+|\d+\s+\w+\s+\d+)",
                content,
                re.IGNORECASE,
            )
            if creation_match:
                return creation_match.group(2).strip()
            elif found_dates:
                # Use the first date found as the creation date
                return found_dates[0]

        except Exception as e:
            logger.error(f"Error extracting date: {e}")

        return ""

    def _extract_version(self, content: str) -> str:
        """Extract version information from document content.

        Args:
            content: Document content

        Returns:
            The extracted version string or empty string if not found
        """
        for pattern in self.version_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return ""

    def _calculate_statistics(self, content: str) -> dict[str, int]:
        """Calculate document statistics.

        Args:
            content: Document content

        Returns:
            A dictionary of document statistics
        """
        stats = {}

        # Word count
        words = re.findall(r"\b\w+\b", content)
        stats["word_count"] = len(words)

        # Page count estimate (assuming ~500 words per page)
        stats["estimated_page_count"] = max(1, len(words) // 500)

        # Character count
        stats["character_count"] = len(content)

        # Paragraph count (estimated by double newlines)
        paragraphs = re.split(r"\n\s*\n", content)
        stats["paragraph_count"] = len(paragraphs)

        # Section count (estimated by headings in markdown or similar docs)
        headings = re.findall(r"^#+\s+", content, re.MULTILINE)
        stats["section_count"] = len(headings) if headings else 0

        return stats

    def _extract_keywords(self, content: str) -> list[str]:
        """Extract keywords from document content.

        Args:
            content: Document content

        Returns:
            A list of extracted keywords
        """
        # For simplicity, we'll use a basic keyword extraction
        words = re.findall(r"\b\w+\b", content)
        return [word.lower() for word in words if len(word) > 3]
