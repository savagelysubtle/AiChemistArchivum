"""Similarity-based search provider for finding related files.

This module provides classes and functions for finding similar files
using vector embeddings based on file content.
"""

import logging
import os
from pathlib import Path
from typing import cast

import numpy as np
from sklearn.cluster import AgglomerativeClustering  # type: ignore

from the_aichemist_codex.infrastructure.ai.embeddings import (
    TextEmbeddingModel,
    VectorIndex,
    compute_similarity_matrix,
)
from the_aichemist_codex.infrastructure.config.settings import get_settings
from the_aichemist_codex.infrastructure.utils.batch_processor import BatchProcessor
from the_aichemist_codex.infrastructure.utils.cache_manager import CacheManager
from the_aichemist_codex.infrastructure.utils.io.async_io import AsyncFileIO

logger = logging.getLogger(__name__)


class SimilarityProvider:
    """Provider for similarity-based search capabilities.

    This class enables finding files related to a query or another file
    by comparing their vector embeddings.

    Features:
    - Vector-based similarity search
    - File-to-file similarity comparison
    - Text-to-file search
    - File grouping based on similarity
    - Caching of results
    """

    def __init__(
        self,
        embedding_model: TextEmbeddingModel | None = None,
        vector_index: VectorIndex | None = None,
        path_mapping: list[str] | None = None,
        cache_manager: CacheManager | None = None,
    ):
        """Initialize the similarity provider.

        Args:
            embedding_model: Model for creating text embeddings
            vector_index: Index for storing and searching vectors
            path_mapping: List of file paths corresponding to vectors in the index
            cache_manager: Manager for caching search results
        """
        self.embedding_model = embedding_model
        self.vector_index = vector_index
        self.path_mapping = path_mapping or []
        self.cache_manager = cache_manager
        self.cache_ttl = get_settings().get(
            "SIMILARITY_CACHE_TTL", 300
        )  # Default 5 minutes
        self.batch_processor = BatchProcessor()

    async def search(
        self,
        query: str,
        file_paths: list[str | Path] | None = None,
        threshold: float = 0.7,
        max_results: int = 10,
    ) -> list[str]:
        """Search for files similar to the query text.

        Args:
            query: Text query to search for
            file_paths: Optional list of file paths to search in
            threshold: Minimum similarity score (0.0-1.0)
            max_results: Maximum number of results to return

        Returns:
            List of file paths matching the query
        """
        if not query or not self.embedding_model:
            return []

        # Check cache first
        cache_key = f"similarity_search_{query}_{threshold}_{max_results}"
        if self.cache_manager:
            cached_result = await self.cache_manager.get(cache_key)
            if cached_result:
                return cast(list[str], cached_result)

        try:
            # Calculate query embedding
            if self.embedding_model is None:
                return []

            query_vector = self.embedding_model.encode(query)

            # If we have a vector index, use it
            if self.vector_index is None or self.vector_index.vectors is None:
                return []

            distances, indices = self.vector_index.search(query_vector, max_results)
            # Convert indices to numpy array if they're not already
            np_indices = np.array(indices, dtype=np.int64)
            results = self.vector_index.get_paths(np_indices)

            # Filter by threshold
            filtered_results = []
            for i, path in enumerate(results):
                if i < len(distances) and distances[i] >= threshold:
                    filtered_results.append(path)

            # Cache results
            if self.cache_manager:
                await self.cache_manager.put(cache_key, filtered_results)

            return filtered_results

        except Exception as e:
            logger.error(f"Error in similarity search: {e}")
            return []

    async def find_similar_files(
        self, file_path: str | Path, threshold: float = 0.7, max_results: int = 10
    ) -> list[tuple[str, float]]:
        """Find files similar to the given file.

        Args:
            file_path: Path to the reference file
            threshold: Minimum similarity score (0.0-1.0)
            max_results: Maximum number of results to return

        Returns:
            List of (file_path, similarity_score) tuples
        """
        # Ensure file_path is a Path object
        path_obj = Path(file_path) if isinstance(file_path, str) else file_path

        if not path_obj.exists() or not self.embedding_model:
            return []

        # Check cache
        cache_key = f"similar_files_{path_obj!s}_{threshold}_{max_results}"
        if self.cache_manager:
            cached_result = await self.cache_manager.get(cache_key)
            if cached_result:
                return cast(list[tuple[str, float]], cached_result)

        try:
            # Read the file content
            content = ""
            async for chunk in AsyncFileIO.read_chunked(path_obj):
                content += chunk.decode("utf-8", errors="ignore")

            # Generate embedding for the file
            if self.embedding_model is None:
                return []

            file_vector = self.embedding_model.encode(content)

            # Search the vector index
            if self.vector_index is None:
                return []

            distances, indices = self.vector_index.search(
                file_vector, k=max_results + 1
            )  # +1 for the file itself

            # Filter by threshold and get paths with scores
            results = []
            for i, idx in enumerate(indices):
                if self.vector_index is None:
                    continue

                if idx < len(self.vector_index.path_mapping):
                    path = self.vector_index.path_mapping[idx]
                else:
                    path = ""

                score = float(distances[i])

                # Skip the file itself and ensure score meets threshold
                if path and path != str(path_obj) and score >= threshold:
                    results.append((path, score))

            # Limit to max_results
            results = results[:max_results]

            # Cache results
            if self.cache_manager:
                await self.cache_manager.put(cache_key, results)

            logger.debug(f"Found {len(results)} similar files for: {path_obj!s}")
            return results
        except Exception as e:
            logger.error(f"Error finding similar files for {path_obj!s}: {e}")
            return []

    async def find_file_groups(
        self,
        file_paths: list[str | Path] | None = None,
        threshold: float = 0.7,
        min_group_size: int = 2,
    ) -> list[list[str]]:
        """Find groups of similar files using hierarchical clustering.

        Args:
            file_paths: Optional list of file paths to search within
            threshold: Similarity threshold (0.0-1.0)
            min_group_size: Minimum number of files in a group

        Returns:
            List of file groups where each group is a list of file paths
        """
        if not self.embedding_model:
            logger.warning("Cannot find file groups without embedding model")
            return []

        # Check cache
        cache_key = f"file_groups_{threshold}_{min_group_size}"
        if file_paths:
            cache_key += f"_paths{len(file_paths)}"

        if self.cache_manager:
            cached_result = await self.cache_manager.get(cache_key)
            if cached_result:
                return cast(list[list[str]], cached_result)

        # Determine which files to process
        if file_paths is None:
            # Use all files in the vector index
            paths_to_process = self.path_mapping
        else:
            # Use specified file paths
            paths_to_process = [str(path) for path in file_paths]

        if not paths_to_process:
            logger.warning("No files to process for grouping")
            return []

        try:
            # Process files in manageable batches
            batch_size = 100  # Process 100 files at a time
            all_embeddings = []
            valid_paths = []

            # Process files in batches
            processor = BatchProcessor()
            for i in range(0, len(paths_to_process), batch_size):
                batch = paths_to_process[i : i + batch_size]

                # Process files to get their embeddings
                results = await processor.process_batch(
                    items=batch,
                    operation=self._process_file,
                    batch_size=10,
                    timeout=60,
                )

                # Filter out None results and collect embeddings and paths
                for result in results:
                    if result:
                        path, embedding = result
                        all_embeddings.append(embedding)
                        valid_paths.append(path)

            if not all_embeddings:
                logger.warning("No valid embeddings extracted from files")
                return []

            # Convert list of embeddings to a numpy array
            embeddings_array = np.array(all_embeddings)

            # Compute similarity matrix
            similarity_matrix = compute_similarity_matrix(embeddings_array)

            # Convert similarity to distance (1 - similarity)
            distance_matrix = 1 - similarity_matrix

            # Apply hierarchical clustering
            clustering = AgglomerativeClustering(
                n_clusters=None,
                distance_threshold=1
                - threshold,  # Convert similarity threshold to distance
                affinity="precomputed",
                linkage="average",
            )

            cluster_labels = clustering.fit_predict(distance_matrix)

            # Group files by cluster
            clusters: dict[int, list[str]] = {}
            for i, label in enumerate(cluster_labels):
                if label not in clusters:
                    clusters[label] = []
                clusters[label].append(valid_paths[i])

            # Filter clusters by minimum size
            file_groups = [
                group for group in clusters.values() if len(group) >= min_group_size
            ]

            # Cache results
            if self.cache_manager:
                await self.cache_manager.put(cache_key, file_groups)

            logger.info(f"Found {len(file_groups)} groups of similar files")
            return file_groups

        except Exception as e:
            logger.error(f"Error finding file groups: {e}")
            return []

    async def _process_file(
        self, file_path: str | Path
    ) -> tuple[str, np.ndarray] | None:
        """Process a file to extract its embedding.

        Args:
            file_path: Path to the file

        Returns:
            Tuple of (file_path, embedding) or None if processing failed
        """
        try:
            file_path_str = str(file_path)
            if not os.path.exists(file_path_str):
                return None

            # Skip large files and non-text files
            if os.path.getsize(file_path_str) > 1_000_000:  # 1MB limit
                logger.debug(f"Skipping large file: {file_path_str}")
                return None

            # Convert to Path for read_chunked
            path_obj = Path(file_path_str)
            content = ""
            async for chunk in AsyncFileIO.read_chunked(path_obj):
                content += chunk.decode("utf-8", errors="ignore")

            # Generate embedding for the file
            if self.embedding_model is None:
                return None

            file_vector = self.embedding_model.encode(content)
            return (file_path_str, file_vector)

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            return None
