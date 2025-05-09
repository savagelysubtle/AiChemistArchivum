"""Metadata extraction manager.

This module provides a central manager for coordinating metadata extraction
across different file types using appropriate extractors.
"""

import asyncio
import logging
import time
from pathlib import Path

from the_aichemist_codex.infrastructure.extraction.base_extractor import (
    BaseMetadataExtractor,
    MetadataExtractorRegistry,
)
from the_aichemist_codex.infrastructure.extraction.mime_detector import MimeTypeDetector
from the_aichemist_codex.infrastructure.fs.file_metadata import FileMetadata
from the_aichemist_codex.infrastructure.utils.cache.cache_manager import CacheManager

logger = logging.getLogger(__name__)


class MetadataManager:
    """Manager for coordinating metadata extraction.

    This class orchestrates the extraction of metadata from files using
    the appropriate extractors based on file type.
    """

    def __init__(
        self, cache_manager: CacheManager | None = None, max_concurrent_batch: int = 5
    ):
        """Initialize the metadata manager.

        Args:
            cache_manager: Optional cache manager for caching extraction results
            max_concurrent_batch: Max concurrent tasks for batch processing.
        """
        self.cache_manager = cache_manager
        self.mime_detector = MimeTypeDetector()
        self.max_concurrent_batch = max_concurrent_batch

        # Initialize all available extractors
        self.extractors: dict[str, BaseMetadataExtractor] = {}
        for extractor_class in MetadataExtractorRegistry.get_all_extractors():
            extractor = extractor_class(cache_manager)
            for mime_type in extractor.supported_mime_types:
                self.extractors[mime_type] = extractor

    async def extract_metadata(
        self,
        file_path: str | Path,
        content: str | None = None,
        mime_type: str | None = None,
        metadata: FileMetadata | None = None,
    ) -> FileMetadata:
        """
        Extract metadata from a file.

        Args:
            file_path: Path to the file
            content: Optional pre-loaded content
            mime_type: Optional pre-determined MIME type
            metadata: Optional existing metadata to enhance

        Returns:
            Enhanced metadata with extracted information

        Raises:
            FileNotFoundError: If the file does not exist and cannot be processed
            PermissionError: If the file cannot be accessed due to permission issues
            IOError: If there is a general I/O error with the file
        """
        path = Path(file_path) if isinstance(file_path, str) else file_path

        # If no metadata provided, create a basic one
        if metadata is None:
            try:
                if path.exists():
                    stats = path.stat()
                    size = stats.st_size
                    if mime_type is None:
                        mime_type, _ = self.mime_detector.get_mime_type(path)
                    extension = path.suffix.lower()
                else:
                    size = -1
                    if mime_type is None:
                        mime_type = "unknown"
                    extension = path.suffix.lower() if path.suffix else ""

                metadata = FileMetadata(
                    path=path,
                    mime_type=mime_type,
                    size=size,
                    extension=extension,
                    preview="",
                    error=None,
                    parsed_data=None,
                )
            except FileNotFoundError:
                error_msg = f"File not found: {path}"
                logger.error(error_msg)
                metadata = FileMetadata(
                    path=path,
                    mime_type="unknown",
                    size=-1,
                    extension=path.suffix.lower() if path.suffix else "",
                    preview="",
                    error=error_msg,
                    parsed_data=None,
                )
            except PermissionError as e:
                error_msg = f"Permission denied accessing file {path}: {e!s}"
                logger.error(error_msg)
                metadata = FileMetadata(
                    path=path,
                    mime_type="unknown",
                    size=-1,
                    extension=path.suffix.lower() if path.suffix else "",
                    preview="",
                    error=error_msg,
                    parsed_data=None,
                )
            except Exception as e:
                error_msg = f"Error creating metadata for {path}: {e!s}"
                logger.error(error_msg, exc_info=True)
                metadata = FileMetadata(
                    path=path,
                    mime_type="unknown",
                    size=-1,
                    extension=path.suffix.lower() if path.suffix else "",
                    preview="",
                    error=error_msg,
                    parsed_data=None,
                )

        # If MIME type not provided or in metadata, detect it
        if mime_type is None:
            mime_type = metadata.mime_type
            if mime_type is None or mime_type == "unknown":
                try:
                    if path.exists():
                        mime_type, _ = self.mime_detector.get_mime_type(path)
                        metadata.mime_type = mime_type
                except FileNotFoundError:
                    logger.warning(
                        f"File not found when detecting MIME type for {path}"
                    )
                    metadata.error = f"File not found: {path}"
                except PermissionError as e:
                    logger.warning(
                        f"Permission denied when detecting MIME type for {path}: {e}"
                    )
                    metadata.error = f"Permission denied: {path}"
                except Exception as e:
                    logger.warning(
                        f"Error detecting MIME type for {path}: {e}", exc_info=True
                    )
                    metadata.error = f"Error detecting file type: {e}"

        # Check if we have an extractor for this MIME type
        extractors = self._get_extractors_for_mime_type(mime_type)

        if not extractors:
            logger.debug(f"No extractors found for MIME type: {mime_type}")
            return metadata

        # Apply each extractor in sequence
        for extractor in extractors:
            cache_key = None
            cached_data = None
            if self.cache_manager:
                try:
                    mtime = path.stat().st_mtime if path.exists() else 0
                    cache_key = (
                        f"metadata:{path!s}:{mtime}:{extractor.__class__.__name__}"
                    )
                    cached_data = await self.cache_manager.get(cache_key)
                    if cached_data and isinstance(cached_data, dict):
                        logger.debug(
                            f"Using cached metadata for {path} from {extractor.__class__.__name__}"
                        )
                        for key, value in cached_data.items():
                            setattr(metadata, key, value)
                        metadata.extraction_complete = cached_data.get(
                            "extraction_complete", True
                        )
                        metadata.extraction_time = cached_data.get(
                            "extraction_time", 0.0
                        )
                        metadata.extraction_confidence = cached_data.get(
                            "extraction_confidence", 0.0
                        )
                        continue  # Cache hit, move to next extractor
                except (FileNotFoundError, PermissionError) as e:
                    # Errors during stat for cache key generation - log and proceed without cache
                    logger.warning(f"Error stating file {path} for cache key: {e}")
                    cached_data = None
                    cache_key = None
                except Exception as e:
                    logger.warning(
                        f"Error accessing cache for {path} with key {cache_key}: {e}"
                    )
                    cached_data = None  # Ensure proceed with extraction

            # If cache miss or no cache manager, proceed with extraction
            if cached_data is None:
                try:
                    start_time = time.time()
                    extracted_data = await extractor.extract(
                        file_path=path,
                        content=content,
                        mime_type=mime_type,
                        metadata=metadata,  # Pass metadata for potential enhancement
                    )
                    end_time = time.time()
                    extraction_time = end_time - start_time

                    # Update the metadata object directly
                    for key, value in extracted_data.items():
                        if hasattr(metadata, key):
                            setattr(metadata, key, value)
                        else:
                            setattr(metadata, key, value)

                    # Set extraction metadata
                    metadata.extraction_complete = extracted_data.get(
                        "extraction_complete", True
                    )
                    metadata.extraction_time = extracted_data.get(
                        "extraction_time", extraction_time
                    )
                    metadata.extraction_confidence = extracted_data.get(
                        "extraction_confidence", 0.7
                    )

                    # Cache the result
                    if (
                        self.cache_manager
                        and cache_key
                        and metadata.extraction_complete
                    ):
                        try:
                            await self.cache_manager.put(cache_key, extracted_data)
                        except Exception as e:
                            logger.warning(
                                f"Error putting data into cache for {path} with key {cache_key}: {e}"
                            )

                    logger.debug(
                        f"Metadata extraction completed in {metadata.extraction_time:.2f}s "
                        f"for {path} using {extractor.__class__.__name__}"
                    )

                # --- Refined Exception Handling for extractor.extract() ---
                except (OSError, FileNotFoundError, PermissionError, UnicodeDecodeError) as e:
                    # Specific errors expected from _get_content or file access within extractor
                    error_msg = f"I/O or Decode Error during extraction for {path} using {extractor.__class__.__name__}: {e}"
                    logger.error(error_msg)
                    metadata.error = error_msg
                    metadata.extraction_complete = False
                    metadata.extraction_confidence = 0.0
                except (ValueError, TypeError) as e:
                    # Errors related to content parsing or invalid data within extractor
                    error_msg = f"Data Error during extraction for {path} using {extractor.__class__.__name__}: {e}"
                    logger.error(error_msg)
                    metadata.error = error_msg
                    metadata.extraction_complete = False
                    metadata.extraction_confidence = 0.0
                except Exception as e:
                    # Catchall for unexpected errors within a specific extractor
                    error_msg = f"Unexpected error extracting metadata for {path} using {extractor.__class__.__name__}: {e}"
                    logger.error(
                        error_msg, exc_info=True
                    )  # Log traceback for unexpected errors
                    metadata.error = error_msg
                    metadata.extraction_complete = False
                    metadata.extraction_confidence = 0.0
                    # Continue to allow other extractors to run if desired, or add 'break'

        return metadata

    async def extract_batch(self, file_paths: list[str | Path]) -> list[FileMetadata]:
        """
        Extract metadata from multiple files concurrently.

        Args:
            file_paths: List of file paths

        Returns:
            List of file metadata objects
        """
        semaphore = asyncio.Semaphore(self.max_concurrent_batch)

        async def _extract_with_semaphore(file_path: str | Path) -> FileMetadata:
            async with semaphore:
                return await self.extract_metadata(file_path)

        tasks = [_extract_with_semaphore(path) for path in file_paths]
        return await asyncio.gather(*tasks)

    def _get_extractors_for_mime_type(
        self, mime_type: str
    ) -> list[BaseMetadataExtractor]:
        """
        Get all extractors that can handle the given MIME type.

        Args:
            mime_type: MIME type

        Returns:
            List of extractors for the MIME type
        """
        result = []

        # Check for exact MIME type match
        if mime_type in self.extractors:
            result.append(self.extractors[mime_type])

        # Check for MIME type prefix match (e.g., text/*)
        mime_prefix = mime_type.split("/")[0] + "/*"
        if (
            mime_prefix in self.extractors
            and self.extractors[mime_prefix] not in result
        ):
            result.append(self.extractors[mime_prefix])

        # Check for wildcard match
        if "*/*" in self.extractors and self.extractors["*/*"] not in result:
            result.append(self.extractors["*/*"])

        return result
