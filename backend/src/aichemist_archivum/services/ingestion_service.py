"""Metadata extraction manager.

This module provides a central manager for coordinating metadata extraction
across different file types using appropriate extractors.
"""

import asyncio
import logging
import time
from collections.abc import Coroutine
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from aichemist_archivum.core.extraction.base_extractor import BaseMetadataExtractor
from aichemist_archivum.core.extraction.extractors import EXTRACTOR_REGISTRY
from aichemist_archivum.core.fs.file_metadata import FileMetadata
from aichemist_archivum.utils.cache.cache_manager import CacheManager
from aichemist_archivum.utils.concurrency.concurrency import TaskManager
from aichemist_archivum.utils.file_utils import get_mime_type

if TYPE_CHECKING:
    from typing import Self

ExtractorTuple = tuple[BaseMetadataExtractor, float, str | None]
logger = logging.getLogger(__name__)


class IngestionService:
    """Service for orchestrating metadata extraction from files.

    This class uses various extractors based on file type to populate FileMetadata.
    """

    def __init__(
        self: "Self",
        cache_manager: CacheManager | None = None,
        max_concurrent_batch: int = 5,
    ) -> None:
        """Initialize the ingestion service.

        Args:
            cache_manager: Optional cache manager for caching extraction results
            max_concurrent_batch: Max concurrent tasks for batch processing.
        """
        self.cache_manager = cache_manager
        self.task_manager = TaskManager(max_concurrent=max_concurrent_batch)

        logger.info(
            f"IngestionService initialized. Cache: {'Enabled' if cache_manager else 'Disabled'}. "
            f"Max concurrent batch: {max_concurrent_batch}"
        )

    async def extract_metadata(
        self: "Self",
        file_path: str | Path,
        content: str | bytes | None = None,
        mime_type_override: str | None = None,
        extractors_override: list[BaseMetadataExtractor] | None = None,
    ) -> FileMetadata:
        """
        Extract metadata from a file.

        Args:
            file_path: Path to the file
            content: Optional pre-loaded content (bytes or str)
            mime_type_override: Optionally override MIME type detection
            extractors_override: Optionally use a specific list of extractors

        Returns:
            Enhanced metadata with extracted information
        """
        path = (
            Path(file_path).resolve()
            if isinstance(file_path, str)
            else file_path.resolve()
        )
        overall_processing_start_time = time.monotonic()

        if not await asyncio.to_thread(path.exists):
            logger.error(f"File not found for metadata extraction: {path}")
            metadata = FileMetadata(
                path=path,
                mime_type="unknown",
                size=-1,
                extension=path.suffix.lower() or "",
                error="File not found",
            )
            return metadata

        metadata = await FileMetadata.from_path(path)

        try:
            if mime_type_override:
                metadata.mime_type = mime_type_override

            if (
                content is not None
                and (
                    metadata.mime_type is None
                    or metadata.mime_type == "unknown"
                    or metadata.mime_type == "application/octet-stream"
                    or metadata.mime_type == "error"
                )
                and not mime_type_override
            ):
                detected_content_mime = await get_mime_type(path, content)
                if detected_content_mime:
                    metadata.mime_type = detected_content_mime

            if (
                not metadata.mime_type
                or metadata.mime_type == "unknown"
                or metadata.mime_type == "error"
            ):
                logger.warning(
                    f"Could not reliably determine MIME type for {path}. Some extractors may not run."
                )

            active_extractors: list[ExtractorTuple]
            if extractors_override:
                active_extractors = [(ext, 1.0, None) for ext in extractors_override]
            elif metadata.mime_type and metadata.mime_type not in ["unknown", "error"]:
                active_extractors = self._get_extractors_for_mime_type(
                    metadata.mime_type
                )
            else:
                active_extractors = [
                    (ext_cls(), prio, sub_type)
                    for ext_cls, prio, sub_type in EXTRACTOR_REGISTRY.get("*/*", [])
                ]
                if active_extractors:
                    logger.debug(
                        f"Using fallback extractors for {path} due to undetermined MIME type."
                    )

            if not active_extractors:
                logger.info(
                    f"No suitable extractors found for {path} (MIME: {metadata.mime_type})."
                )
                metadata.extraction_complete = True
                return metadata

            logger.debug(
                f"Using extractors for {path}: {[e[0].__class__.__name__ for e in active_extractors]}"
            )

            extraction_tasks: list[
                Coroutine[Any, Any, tuple[str, dict[str, Any] | None, str | None]]
            ] = []

            for extractor_instance, priority, required_subtype in active_extractors:
                if (
                    required_subtype
                    and metadata.mime_type
                    and required_subtype not in metadata.mime_type
                ):
                    logger.debug(
                        f"Skipping extractor {extractor_instance.__class__.__name__} for {path} - subtype mismatch."
                    )
                    continue

                task = self._run_extractor(
                    extractor_instance, path, metadata, content, priority
                )
                extraction_tasks.append(task)

            results = await asyncio.gather(*extraction_tasks, return_exceptions=True)

            current_errors = []
            if metadata.error:
                current_errors.append(metadata.error)

            any_extractor_failed = False
            for result in results:
                if isinstance(result, Exception):
                    any_extractor_failed = True
                    error_str = f"Extractor task failed: {type(result).__name__}: {str(result)[:100]}"
                    current_errors.append(error_str)
                    logger.error(
                        f"Exception during batched extraction task for {path}: {result}",
                        exc_info=result,
                    )
                elif isinstance(result, tuple) and result[2]:
                    any_extractor_failed = True
                    current_errors.append(result[2])

            if current_errors:
                metadata.error = "; ".join(current_errors)

            if active_extractors:
                metadata.extraction_complete = (
                    not any_extractor_failed and not metadata.error
                )

        except Exception as e:
            logger.error(
                f"Critical error during metadata extraction process for {path}: {e}",
                exc_info=True,
            )
            metadata.error = f"Core extraction error: {e!s}"
            metadata.extraction_complete = False
        finally:
            final_processing_time = time.monotonic() - overall_processing_start_time
            logger.info(
                f"Finished metadata extraction for {path} in {final_processing_time:.2f}s. "
                f"Status: {'complete' if metadata.extraction_complete else 'incomplete'}. "
                f"Error: {metadata.error or 'None'}"
            )

        return metadata

    async def _run_extractor(
        self: "Self",
        extractor: BaseMetadataExtractor,
        path: Path,
        metadata_obj: FileMetadata,
        file_content: str | bytes | None,
        priority: float,
    ) -> tuple[str, dict[str, Any] | None, str | None]:
        extractor_name = extractor.__class__.__name__
        cache_key = ""

        file_mtime = 0
        file_size = 0
        try:
            if await asyncio.to_thread(path.exists):
                file_stat = await asyncio.to_thread(path.stat)
                file_mtime = file_stat.st_mtime
                file_size = file_stat.st_size
        except Exception as stat_exc:
            logger.warning(
                f"Could not stat file {path} for cache key generation: {stat_exc}"
            )

        if self.cache_manager:
            try:
                cache_key_parts = [
                    str(path),
                    str(file_mtime),
                    str(file_size),
                    extractor_name,
                    str(getattr(extractor, "VERSION", "1.0")),
                ]
                cache_key = "ext_meta::" + "|".join(cache_key_parts)

                cached_data_raw = await self.cache_manager.get(cache_key)
                cached_dict: dict[str, Any] | None = None
                if cached_data_raw and isinstance(cached_data_raw, dict):
                    cached_dict = cast(dict[str, Any], cached_data_raw)

                if cached_dict:
                    logger.debug(
                        f"Using cached metadata for {path} from {extractor_name}"
                    )
                    for key, value in cached_dict.items():
                        if hasattr(metadata_obj, key):
                            setattr(metadata_obj, key, value)
                        else:
                            if not isinstance(metadata_obj.parsed_data, dict):
                                metadata_obj.parsed_data = {}
                            if extractor_name not in metadata_obj.parsed_data:
                                metadata_obj.parsed_data[extractor_name] = {}
                            metadata_obj.parsed_data[extractor_name][key] = value

                    metadata_obj.extraction_time += cached_dict.get(
                        "_extraction_time_seconds", 0.01
                    )
                    return extractor_name, cached_dict, None
            except Exception as e:
                logger.warning(
                    f"Error accessing cache for {path} with {extractor_name}: {e}"
                )

        logger.debug(f"Running extractor {extractor_name} for {path}")
        error_msg_str: str | None = None
        extracted_data_dict: dict[str, Any] | None = None
        individual_extraction_start_time = time.monotonic()

        try:
            if hasattr(extractor, "extract_with_content") and file_content is not None:
                data_from_extractor = await extractor.extract_with_content(
                    path, file_content
                )
            else:
                data_from_extractor = await extractor.extract(path)

            if data_from_extractor and isinstance(data_from_extractor, dict):
                extracted_data_dict = data_from_extractor
                for key, value in extracted_data_dict.items():
                    if hasattr(metadata_obj, key):
                        setattr(metadata_obj, key, value)
                    else:
                        if not isinstance(metadata_obj.parsed_data, dict):
                            metadata_obj.parsed_data = {}
                        if extractor_name not in metadata_obj.parsed_data:
                            metadata_obj.parsed_data[extractor_name] = {}
                        metadata_obj.parsed_data[extractor_name][key] = value
            else:
                logger.warning(
                    f"Extractor {extractor_name} did not return a dict for {path}. Got: {type(data_from_extractor)}"
                )

        except (FileNotFoundError, PermissionError, IsADirectoryError, OSError) as e:
            error_msg_str = f"I/O or OS Error in {extractor_name} for {path}: {e}"
            logger.error(error_msg_str)
        except UnicodeDecodeError as e:
            error_msg_str = f"Unicode Decode Error in {extractor_name} for {path}: {e}"
            logger.error(error_msg_str)
        except (ValueError, TypeError) as e:
            error_msg_str = f"Data Error in {extractor_name} for {path}: {e}"
            logger.error(error_msg_str)
        except NotImplementedError:
            error_msg_str = (
                f"Extractor {extractor_name} method not implemented for {path}"
            )
            logger.warning(error_msg_str)
        except Exception as e:
            error_msg_str = f"Unexpected error in {extractor_name} for {path}: {e}"
            logger.error(error_msg_str, exc_info=True)

        individual_extraction_time = time.monotonic() - individual_extraction_start_time
        metadata_obj.extraction_time += individual_extraction_time

        if not error_msg_str and extracted_data_dict is not None:
            if self.cache_manager and cache_key:
                try:
                    data_to_cache = {
                        **extracted_data_dict,
                        "_extraction_time_seconds": individual_extraction_time,
                    }
                    await self.cache_manager.put(cache_key, data_to_cache)
                except Exception as e:
                    logger.warning(
                        f"Error putting data into cache for {path} with key {cache_key}: {e}"
                    )
        return extractor_name, extracted_data_dict, error_msg_str

    async def extract_batch(
        self: "Self", file_paths: list[str | Path]
    ) -> list[FileMetadata]:
        """
        Extract metadata from multiple files concurrently.

        Args:
            file_paths: List of file paths

        Returns:
            List of file metadata objects
        """
        coroutines = [self.extract_metadata(fp) for fp in file_paths]
        results = await self.task_manager.add_batch_coroutines(coroutines)

        final_results: list[FileMetadata] = []
        for i, res in enumerate(results):
            if isinstance(res, FileMetadata):
                final_results.append(res)
            elif isinstance(res, Exception):
                logger.error(
                    f"Error extracting metadata for {file_paths[i]} in batch: {res}",
                    exc_info=res,
                )
                final_results.append(
                    FileMetadata(
                        path=Path(file_paths[i]),
                        error=str(res),
                        extraction_complete=False,
                    )
                )
            else:
                logger.warning(
                    f"Unexpected result type for {file_paths[i]} in batch: {type(res)}"
                )
                final_results.append(
                    FileMetadata(
                        path=Path(file_paths[i]),
                        error=f"Unexpected result type: {type(res)}",
                        extraction_complete=False,
                    )
                )
        return final_results

    def _get_extractors_for_mime_type(
        self: "Self", mime_type: str
    ) -> list[ExtractorTuple]:
        """
        Get suitable extractors for a given MIME type from the registry.
        This considers primary type (e.g., 'image/jpeg' -> 'image/*') and full type.

        Args:
            mime_type: The MIME type string (e.g., "text/plain", "image/jpeg").

        Returns:
            A list of tuples: (extractor_instance, priority, specific_subtype_if_any).
            Sorted by priority (descending).
        """
        found_extractors: list[ExtractorTuple] = []
        primary_type = mime_type.split("/")[0] + "/*"

        for extractor_cls, priority, subtype_filter in EXTRACTOR_REGISTRY.get(
            mime_type, []
        ):
            found_extractors.append((extractor_cls(), priority, subtype_filter))

        if mime_type != primary_type:
            for extractor_cls, priority, subtype_filter in EXTRACTOR_REGISTRY.get(
                primary_type, []
            ):
                if not any(
                    isinstance(ext[0], extractor_cls) for ext in found_extractors
                ):
                    found_extractors.append((extractor_cls(), priority, subtype_filter))

        for extractor_cls, priority, subtype_filter in EXTRACTOR_REGISTRY.get(
            "*/*", []
        ):
            if not any(isinstance(ext[0], extractor_cls) for ext in found_extractors):
                found_extractors.append((extractor_cls(), priority, subtype_filter))

        found_extractors.sort(key=lambda x: x[1], reverse=True)
        if found_extractors:
            logger.debug(
                f"Extractors for MIME '{mime_type}': {[e[0].__class__.__name__ for e in found_extractors]}"
            )
        return found_extractors
