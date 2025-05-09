"""Regex-based search provider for pattern matching in file contents."""

import asyncio
import logging
import re
import time
from pathlib import Path
from typing import cast

from the_aichemist_codex.infrastructure.config.settings import (
    REGEX_MAX_COMPLEXITY,
    REGEX_TIMEOUT_MS,
)
from the_aichemist_codex.infrastructure.utils.batch_processor import BatchProcessor
from the_aichemist_codex.infrastructure.utils.cache_manager import CacheManager
from the_aichemist_codex.infrastructure.utils.io.async_io import AsyncFileIO

logger = logging.getLogger(__name__)


class RegexSearchProvider:
    """
    Provides regex-based search capabilities for file contents.

    Features:
    - Regex pattern validation to prevent catastrophic backtracking
    - Streaming file reading for memory efficiency
    - Caching of search results
    - Parallel processing of files
    """

    def __init__(self, cache_manager: CacheManager | None = None):
        """
        Initialize the regex search provider.

        Args:
            cache_manager: Optional cache manager for caching search results
        """
        self.cache_manager = cache_manager
        self.batch_processor = BatchProcessor()
        self._compiled_patterns: dict[str, re.Pattern] = {}

    async def search(
        self,
        query: str,
        file_paths: list[Path] | None = None,
        max_results: int = 100,
        case_sensitive: bool = False,
        whole_word: bool = False,
        **kwargs,
    ) -> list[str]:
        """
        Search for files matching the regex pattern.

        Args:
            query: The regex pattern to search for
            file_paths: List of file paths to search (empty list means no files)
            max_results: Maximum number of results to return
            case_sensitive: Whether to perform case-sensitive search
            whole_word: Whether to match whole words only
            **kwargs: Additional arguments for future extensions

        Returns:
            List of file paths containing matches
        """
        if not query:
            logger.warning("Empty query provided for regex search")
            return []

        # Ensure file_paths is a list, not None
        if file_paths is None:
            file_paths = []

        # Create a unique key for caching
        cache_key = f"regex_{query}_{case_sensitive}_{whole_word}"

        # Check cache first if cache manager is available
        if self.cache_manager and len(file_paths) > 0:
            cached_results = await self.cache_manager.get(cache_key)
            if cached_results:
                logger.info(f"Retrieved regex search results from cache for '{query}'")
                return cast(list[str], cached_results)

        # Validate and compile the regex pattern
        try:
            pattern = self._prepare_pattern(query, case_sensitive, whole_word)
            logger.info(f"Compiled regex pattern: {pattern.pattern}")
        except (re.error, ValueError) as e:
            logger.error(f"Invalid regex pattern '{query}': {e}")
            return []

        # Process files in batches
        start_time = time.time()
        logger.info(f"Starting regex search on {len(file_paths)} files")
        results = await self._search_files(pattern, file_paths, max_results)
        elapsed = time.time() - start_time
        logger.info(
            f"Regex search for '{query}' completed in {elapsed:.2f}s with {len(results)} results"
        )

        # Cache the results
        if self.cache_manager:
            # Create a safe cache key without characters that are invalid in file paths
            safe_query = query.replace("\\", "_").replace("/", "_").replace(":", "_")
            cache_key = f"regex_{safe_query}_{case_sensitive}_{whole_word}"
            await self.cache_manager.put(cache_key, results)

        return results[:max_results]

    def _prepare_pattern(
        self, query: str, case_sensitive: bool, whole_word: bool
    ) -> re.Pattern:
        """
        Prepare and validate the regex pattern.

        Args:
            query: The regex pattern string
            case_sensitive: Whether the pattern should be case sensitive
            whole_word: Whether to match whole words only

        Returns:
            Compiled regex pattern

        Raises:
            ValueError: If the pattern is too complex
            re.error: If the pattern is invalid
        """
        # Check if we've already compiled this pattern
        pattern_key = f"{query}:{case_sensitive}:{whole_word}"
        if pattern_key in self._compiled_patterns:
            return self._compiled_patterns[pattern_key]

        # Modify pattern for whole word matching if needed
        if whole_word and not (query.startswith(r"\b") and query.endswith(r"\b")):
            query = rf"\b{query}\b"

        # Validate pattern complexity to prevent catastrophic backtracking
        if self._estimate_complexity(query) > REGEX_MAX_COMPLEXITY:
            raise ValueError(f"Regex pattern too complex: '{query}'")

        # Compile the pattern
        flags = 0 if case_sensitive else re.IGNORECASE
        pattern = re.compile(query, flags)

        # Cache the compiled pattern
        self._compiled_patterns[pattern_key] = pattern
        return pattern

    def _estimate_complexity(self, pattern: str) -> int:
        """
        Estimate the complexity of a regex pattern.

        Args:
            pattern: The regex pattern string

        Returns:
            Complexity score (higher is more complex)
        """
        # Simple heuristic for pattern complexity
        complexity = len(pattern) * 2

        # Penalize potentially expensive operations
        complexity += pattern.count("*") * 10
        complexity += pattern.count("+") * 8
        complexity += pattern.count("{") * 10
        complexity += pattern.count("?") * 5
        complexity += pattern.count("|") * 15
        complexity += pattern.count("[") * 5
        complexity += pattern.count("(") * 8

        # Nested groups are particularly expensive
        depth = 0
        max_depth = 0
        for char in pattern:
            if char == "(":
                depth += 1
                max_depth = max(max_depth, depth)
            elif char == ")":
                depth = max(0, depth - 1)

        complexity += max_depth * 20

        return complexity

    async def _search_files(
        self, pattern: re.Pattern, file_paths: list[Path], max_results: int
    ) -> list[str]:
        """
        Search for the pattern in the given files.

        Args:
            pattern: Compiled regex pattern
            file_paths: List of file paths to search
            max_results: Maximum number of results to return

        Returns:
            List of file paths containing matches
        """
        # Use a set to avoid duplicates
        matching_files: set[str] = set()
        logger.info(f"Searching {len(file_paths)} files for pattern: {pattern.pattern}")

        # Check if the pattern is looking for file extensions
        is_extension_search = pattern.pattern.endswith("$") and "." in pattern.pattern

        # Process files in batches
        async def process_file(file_path: Path) -> str | None:
            if len(matching_files) >= max_results:
                return None

            try:
                # For extension searches, just check the filename
                if is_extension_search and pattern.search(file_path.name):
                    logger.debug(f"Found match in filename: {file_path}")
                    return str(file_path)

                # Skip binary files for content searches
                if not self._is_text_file(file_path):
                    return None

                # Log when processing a Markdown file
                if file_path.suffix.lower() == ".md":
                    logger.debug(f"Processing Markdown file: {file_path}")

                # Read file in chunks to handle large files
                async for chunk in AsyncFileIO.read_chunked(file_path):
                    chunk_str = chunk.decode("utf-8", errors="ignore")

                    # Use a timeout to prevent regex from hanging
                    match = await self._regex_search_with_timeout(pattern, chunk_str)
                    if match:
                        logger.debug(f"Found match in file content: {file_path}")
                        return str(file_path)

            except Exception as e:
                logger.error(f"Error searching file {file_path}: {e}")

            return None

        # Process files in parallel
        batch_results = await self.batch_processor.process_batch(
            items=file_paths,
            operation=process_file,
            batch_size=min(10, len(file_paths)),
            timeout=30,
        )

        # Collect results
        for result in batch_results:
            if result and len(matching_files) < max_results:
                matching_files.add(result)

        logger.info(f"Found {len(matching_files)} matching files")
        return list(matching_files)

    async def _regex_search_with_timeout(self, pattern: re.Pattern, text: str) -> bool:
        """
        Perform regex search with a timeout to prevent hanging.

        Args:
            pattern: Compiled regex pattern
            text: Text to search in

        Returns:
            True if a match was found, False otherwise
        """
        # Run the regex search in a separate thread with a timeout
        try:
            # Create a future for the regex search
            loop = asyncio.get_event_loop()
            future = loop.run_in_executor(None, pattern.search, text)

            # Wait for the result with a timeout
            result = await asyncio.wait_for(future, timeout=REGEX_TIMEOUT_MS / 1000)
            return bool(result)
        except TimeoutError:
            logger.warning(f"Regex search timed out after {REGEX_TIMEOUT_MS}ms")
            return False

    def _is_text_file(self, file_path: Path) -> bool:
        """
        Check if a file is likely to be a text file based on extension.

        Args:
            file_path: Path to the file

        Returns:
            True if the file is likely to be a text file, False otherwise
        """
        # Common text file extensions
        text_extensions = {
            ".txt",
            ".md",
            ".py",
            ".js",
            ".html",
            ".css",
            ".json",
            ".xml",
            ".yaml",
            ".yml",
            ".ini",
            ".cfg",
            ".conf",
            ".sh",
            ".bat",
            ".ps1",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".java",
            ".cs",
            ".go",
            ".rs",
            ".php",
            ".rb",
            ".pl",
            ".pm",
            ".t",
            ".sql",
            ".log",
            ".csv",
            ".tsv",
        }

        return file_path.suffix.lower() in text_extensions
