"""Base classes for metadata extraction.

This module provides the foundation for all metadata extractors, including
the base class and registry for dynamic extractor discovery and selection.
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, TypeVar

from the_aichemist_codex.infrastructure.fs.file_metadata import FileMetadata
from the_aichemist_codex.infrastructure.utils.io.async_io import AsyncFileIO

logger = logging.getLogger(__name__)

# Define a type variable for metadata dictionaries
T = TypeVar("T", bound=dict[str, Any])


class BaseMetadataExtractor(ABC):
    """Base class for all metadata extractors.

    Metadata extractors analyze file content to extract meaningful information
    such as keywords, topics, entities, and other content-based metadata.
    """

    def __init__(self) -> None:
        """Initialize the metadata extractor."""
        pass

    @abstractmethod
    async def extract(
        self,
        file_path: str | Path,
        content: str | None = None,
        mime_type: str | None = None,
        metadata: FileMetadata | None = None,
    ) -> T:
        """
        Extract metadata from the given file.

        Args:
            file_path: Path to the file
            content: Optional pre-loaded content
            mime_type: Optional pre-determined MIME type
            metadata: Optional existing metadata to enhance

        Returns:
            Dictionary of extracted metadata conforming to the implementing class's TypedDict

        Raises:
            FileNotFoundError: If the file does not exist
            UnicodeDecodeError: If the file content cannot be decoded
            IOError: If there is an error reading the file
        """
        pass

    @property
    @abstractmethod
    def supported_mime_types(self) -> list[str]:
        """
        Get the list of MIME types supported by this extractor.

        Returns:
            List of supported MIME types as strings
        """
        pass

    async def _get_content(self, file_path: str | Path) -> str:
        """
        Get the content of a file.

        Args:
            file_path: Path to the file

        Returns:
            Content of the file as a string

        Raises:
            FileNotFoundError: If the file does not exist
            UnicodeDecodeError: If the file content cannot be decoded as UTF-8
            IOError: If there is an error reading the file
            PermissionError: If the file cannot be accessed due to permission issues
        """
        path = Path(file_path) if isinstance(file_path, str) else file_path
        try:
            content = await AsyncFileIO.read_text(path)
            return content
        except UnicodeDecodeError:
            logger.warning(f"File {path} is not a text file or has non-UTF-8 encoding")
            raise
        except FileNotFoundError:
            logger.error(f"File not found: {path}")
            raise
        except PermissionError:
            logger.error(f"Permission denied accessing file {path}")
            raise
        except OSError as e:
            logger.error(f"I/O error reading file {path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error reading file {path}: {e}", exc_info=True)
            # Re-raise as IOError with original exception as context
            raise OSError(f"Error reading file {path}") from e


class MetadataExtractorRegistry:
    """Registry for metadata extractors.

    This class keeps track of all available extractors and helps select
    the appropriate extractor for a given file.
    """

    _extractors: dict[str, type[BaseMetadataExtractor]] = {}
    _mime_type_map: dict[str, type[BaseMetadataExtractor]] = {}

    @classmethod
    def register(
        cls, extractor_class: type[BaseMetadataExtractor]
    ) -> type[BaseMetadataExtractor]:
        """
        Register a metadata extractor.

        This method is typically used as a decorator on extractor classes.

        Args:
            extractor_class: The extractor class to register

        Returns:
            The registered extractor class (for decorator usage)
        """
        # Don't register abstract classes
        if extractor_class.__name__ == "BaseMetadataExtractor":
            return extractor_class

        # Register the extractor by name
        cls._extractors[extractor_class.__name__] = extractor_class

        # Create dummy instance to access properties
        try:
            # Map MIME types to this extractor
            dummy_instance = extractor_class()
            for mime_type in dummy_instance.supported_mime_types:
                if mime_type in cls._mime_type_map:
                    existing = cls._mime_type_map[mime_type].__name__
                    logger.warning(
                        f"MIME type {mime_type} already registered to {existing}, "
                        f"overriding with {extractor_class.__name__}"
                    )
                cls._mime_type_map[mime_type] = extractor_class
            logger.debug(f"Registered {extractor_class.__name__} metadata extractor")
        except Exception as e:
            logger.error(
                f"Error registering MIME types for {extractor_class.__name__}: {e}"
            )
            # Attempt to create instance without cache manager now
            try:
                dummy_instance = extractor_class()
                for mime_type in dummy_instance.supported_mime_types:
                    if mime_type in cls._mime_type_map:
                        existing = cls._mime_type_map[mime_type].__name__
                        logger.warning(
                            f"MIME type {mime_type} already registered to {existing}, "
                            f"overriding with {extractor_class.__name__}"
                        )
                    cls._mime_type_map[mime_type] = extractor_class
                logger.debug(
                    f"Registered {extractor_class.__name__} metadata extractor"
                )
            except Exception as inner_e:
                logger.error(
                    f"Error registering MIME types for {extractor_class.__name__} even without cache_manager: {inner_e}"
                )

        return extractor_class

    @classmethod
    def get_extractor_for_mime_type(
        cls, mime_type: str
    ) -> type[BaseMetadataExtractor] | None:
        """
        Get the appropriate extractor for a MIME type.

        Args:
            mime_type: The MIME type

        Returns:
            The extractor class for the MIME type, or None if no extractor is found
        """
        # Check for exact MIME type match
        if mime_type in cls._mime_type_map:
            return cls._mime_type_map[mime_type]

        # Check for MIME type prefix match (e.g., text/*)
        mime_prefix = mime_type.split("/")[0] + "/*"
        if mime_prefix in cls._mime_type_map:
            return cls._mime_type_map[mime_prefix]

        # Check for wildcard match
        if "*/*" in cls._mime_type_map:
            return cls._mime_type_map["*/*"]

        return None

    @classmethod
    def get_all_extractors(cls) -> list[type[BaseMetadataExtractor]]:
        """
        Get all registered extractors.

        Returns:
            List of all registered extractor classes
        """
        return list(cls._extractors.values())
