"""Search engine for The AIchemist Codex.

This module provides a comprehensive search engine with multiple search capabilities:
- Filename search
- Full-text search (using Whoosh)
- Fuzzy search
- Regex pattern search
- Semantic search (using embeddings)
- Metadata-based search
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, cast

import rapidfuzz
import whoosh.analysis
from whoosh.fields import ID, TEXT, Schema
from whoosh.index import create_in, open_dir
from whoosh.qparser import QueryParser

from aichemist_archivum.config.settings import (
    DATA_DIR,
    FEATURES,
    REGEX_MAX_RESULTS,
    SIMILARITY_MAX_RESULTS,
)
from aichemist_archivum.core.embeddings import TextEmbeddingModel
from aichemist_archivum.core.fs.file_metadata import FileMetadata
from aichemist_archivum.core.search.providers.regex_provider import RegexSearchProvider
from aichemist_archivum.core.search.providers.similarity_provider import (
    SimilarityProvider,
)
from aichemist_archivum.utils.cache.cache_manager import CacheManager
from aichemist_archivum.utils.concurrency.batch_processor import BatchProcessor
from aichemist_archivum.utils.io.async_io import AsyncFileIO
from aichemist_archivum.utils.io.sqlasync_io import AsyncSQL

# Import FAISS and SentenceTransformer for semantic search.
try:
    import faiss
except ImportError as err:
    raise ImportError("FAISS is not installed. Run `pip install faiss-cpu`.") from err
try:
    from sentence_transformers import SentenceTransformer
except ImportError as err:
    raise ImportError(
        "sentence-transformers is not installed. Run `pip install sentence-transformers`."
    ) from err

logger = logging.getLogger(__name__)
SEARCH_DB = "search_index.sqlite"


class SearchEngine:
    """Handles filename, full-text, metadata, fuzzy, and semantic search using asynchronous SQL operations.

    Semantic search is implemented using FAISS and sentence-transformers.
    """

    def __init__(
        self,
        index_dir: Path,
        db_path: Path | None = None,
        cache_manager: CacheManager | None = None,
    ) -> None:
        self.index_dir = index_dir
        self.db_path = db_path if db_path is not None else DATA_DIR / SEARCH_DB
        self.schema = Schema(
            path=ID(stored=True, unique=True),
            content=TEXT(stored=False, analyzer=whoosh.analysis.StemmingAnalyzer()),
        )
        self._initialize_index()
        self._initialize_database_sync()
        # Ensure db_path is not None before passing to AsyncSQL
        if self.db_path is None:
            raise ValueError("db_path cannot be None")
        self.async_db = AsyncSQL(self.db_path)  # Async SQL utility
        self.cache_manager = cache_manager

        # Initialize search providers
        self.regex_provider: RegexSearchProvider | None = None
        if FEATURES.get("enable_regex_search", False):
            self.regex_provider = RegexSearchProvider(cache_manager=cache_manager)

        # Initialize semantic search components.
        self.embedding_model = None
        self.semantic_index = None  # FAISS index instance.
        self.semantic_mapping: list[str] = []  # Maps vector IDs to file paths.

        # Only initialize embedding model if semantic search is enabled
        if FEATURES.get("enable_semantic_search", False):
            try:
                logger.info("Initializing embedding model for semantic search...")
                self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("Embedding model initialized successfully.")
            except Exception as e:
                logger.warning(f"Failed to initialize embedding model: {e}")
                logger.warning("Semantic search will be disabled.")

        # Initialize similarity provider if enabled
        self.similarity_provider: SimilarityProvider | None = None
        if (
            FEATURES.get("enable_similarity_search", False)
            and self.embedding_model is not None
        ):
            # Create a TextEmbeddingModel wrapper around SentenceTransformer
            model_wrapper = TextEmbeddingModel()
            model_wrapper.embedding_model = self.embedding_model  # type: ignore

            self.similarity_provider = SimilarityProvider(
                embedding_model=model_wrapper,
                vector_index=self.semantic_index,
                path_mapping=self.semantic_mapping,
                cache_manager=cache_manager,
            )

    def _initialize_index(self) -> None:
        """Ensure Whoosh full-text search index is initialized correctly."""
        try:
            if not self.index_dir.exists():
                self.index_dir.mkdir(parents=True, exist_ok=True)
                self.index = create_in(self.index_dir, self.schema)
            elif not any(self.index_dir.iterdir()):
                self.index = create_in(self.index_dir, self.schema)
            else:
                self.index = open_dir(self.index_dir)
        except Exception as e:
            logger.error(f"Whoosh index is missing or corrupted: {e}")
            self.index = create_in(self.index_dir, self.schema)

    def _initialize_database_sync(self) -> None:
        """Initialize SQLite database for metadata and fuzzy search synchronously."""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY,
                path TEXT UNIQUE,
                filename TEXT,
                extension TEXT,
                size INTEGER,
                created_at TEXT,
                updated_at TEXT,
                tags TEXT
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_filename ON files(filename);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags ON files(tags);")
        conn.commit()
        conn.close()

    async def add_to_index_async(self, file_metadata: FileMetadata) -> None | Path:
        """Asynchronously index a file in Whoosh, SQLite, and the semantic search index."""
        try:
            if not file_metadata.path.exists():
                logger.warning(f"Skipping non-existent file: {file_metadata.path}")
                return

            # Use AsyncFileIO to read file content if preview is empty.
            preview_content = file_metadata.preview
            if not preview_content and file_metadata.mime_type and file_metadata.mime_type.startswith("text/"):
                preview_content = await AsyncFileIO.read_text(file_metadata.path)
                if preview_content.startswith("# "):
                    logger.warning(
                        f"Error reading content for indexing: {preview_content}"
                    )
                    preview_content = f"[File content error: {file_metadata.path}]"

            # Ensure embedding_model is not None before using it
            if self.embedding_model is None:
                logger.warning("Cannot create document embedding - model not available")
                return file_metadata.path

            # Use asyncio.to_thread to run the encode operation without blocking
            import numpy as np

            def encode_func() -> Any:
                return (
                    self.embedding_model.encode(preview_content)
                    if self.embedding_model
                    else None
                )

            encoding_result = await asyncio.to_thread(encode_func)

            # Check if encoding was successful
            if encoding_result is None:
                logger.warning("Failed to encode document content")
                return file_metadata.path

            # Convert the encoding result to a NumPy array of the right shape
            embedding = np.array(encoding_result, dtype=np.float32).reshape(1, -1)
            dim = embedding.shape[1]

            if self.semantic_index is None:
                # Initialize the FAISS index with the correct dimension
                self.semantic_index = faiss.IndexFlatL2(dim)

            # Add the embedding to the FAISS index
            # Use type: ignore to silence mypy errors about FAISS API
            if self.semantic_index is not None:
                self.semantic_index.add(embedding)  # type: ignore

            # Whoosh indexing (run in a separate thread).
            def index_document() -> None:
                writer = self.index.writer()
                writer.add_document(
                    path=str(file_metadata.path), content=preview_content or ""
                )
                writer.commit(merge=False)

            await asyncio.to_thread(index_document)

            # Convert custom tags (if provided) into a comma-separated string.
            tags_str = ""
            if hasattr(file_metadata, "tags") and file_metadata.tags:
                tags_str = ",".join(file_metadata.tags)

            # Asynchronous SQLite insertion.
            sql = """
                    INSERT OR REPLACE INTO files (path, filename, extension, size, created_at, updated_at, tags)
                    VALUES (?, ?, ?, ?, datetime('now'), datetime('now'), ?)
                    """
            params = (
                str(file_metadata.path),
                file_metadata.path.name,
                file_metadata.extension,
                file_metadata.size,
                tags_str,
            )
            await self.async_db.execute(sql, params, commit=True)

            # Semantic indexing: compute embedding and add to FAISS index.
            if file_metadata.mime_type and file_metadata.mime_type.startswith("text") and preview_content:
                embedding = await asyncio.to_thread(
                    self.embedding_model.encode, preview_content
                )
                import numpy as np

                embedding = np.array(embedding, dtype="float32").reshape(1, -1)
                dim = embedding.shape[1]
                if self.semantic_index is None:
                    # Create a new FAISS index if one doesn't exist yet
                    try:
                        self.semantic_index = faiss.IndexFlatL2(dim)
                    except Exception as e:
                        logger.error(f"Error creating FAISS index: {e}")
                        # Ensure proper error handling
                        self.semantic_mapping.append(str(file_metadata.path))
                        return

                # Only add to index if it's not None
                if self.semantic_index is not None:
                    # The faiss add method expects x parameter which is embedding
                    # It's called without a named parameter in the FAISS API
                    try:
                        self.semantic_index.add(embedding)  # type: ignore
                        self.semantic_mapping.append(str(file_metadata.path))
                    except Exception as e:
                        logger.error(f"Error adding to FAISS index: {e}")
                else:
                    logger.warning("Cannot add to FAISS index: index is None")
        except Exception as e:
            logger.error(f"Error indexing file {file_metadata.path}: {e}")

    async def search_filename_async(self, query: str) -> list[str]:
        """Asynchronously search for files by exact or partial filename match."""
        sql = "SELECT path FROM files WHERE filename LIKE ?"
        rows = await self.async_db.fetchall(sql, (f"%{query}%",))
        return [Path(row[0]).as_posix() for row in rows]

    async def fuzzy_search_async(
        self, query: str, threshold: float = 80.0
    ) -> list[str]:
        """Asynchronously perform fuzzy search on filenames using RapidFuzz."""
        sql = "SELECT filename, path FROM files"
        all_files = await self.async_db.fetchall(sql)
        mapping = dict(all_files)
        matches = rapidfuzz.process.extract(query, mapping, score_cutoff=threshold)
        return [match[2] for match in matches]

    def full_text_search(self, query: str) -> list[str]:
        """Perform full-text search on file contents (synchronous)."""
        try:
            with self.index.searcher() as searcher:
                query_parser = QueryParser("content", schema=self.index.schema)
                search_query = query_parser.parse(query)
                results = searcher.search(search_query, limit=20)
                return [result["path"] for result in results]
        except Exception as e:
            logger.error(f"Error in full-text search: {e}")
            return []

    async def metadata_search_async(self, filters: dict | None = None) -> list[str]:
        """
        Asynchronously search by metadata filters (size, extension, timestamps, and custom tags).

        :param filters: Dictionary with keys: extension, size_min, size_max, date_after, date_before, tags.
        :return: List of matching file paths.
        """
        query_str = "SELECT path FROM files WHERE 1=1"
        params = []
        if filters:
            if "extension" in filters:
                query_str += (
                    " AND extension IN ("
                    + ",".join("?" for _ in filters["extension"])
                    + ")"
                )
                params.extend(filters["extension"])
            if "size_min" in filters:
                query_str += " AND size >= ?"
                params.append(filters["size_min"])
            if "size_max" in filters:
                query_str += " AND size <= ?"
                params.append(filters["size_max"])
            if "date_after" in filters:
                query_str += " AND updated_at >= ?"
                params.append(filters["date_after"])
            if "date_before" in filters:
                query_str += " AND updated_at <= ?"
                params.append(filters["date_before"])
            if "tags" in filters:
                tag_conditions = []
                for tag in filters["tags"]:
                    tag_conditions.append("tags LIKE ?")
                    params.append(f"%{tag}%")
                if tag_conditions:
                    query_str += " AND (" + " OR ".join(tag_conditions) + ")"
        rows = await self.async_db.fetchall(query_str, tuple(params))
        return [Path(row[0]).as_posix() for row in rows]

    async def semantic_search_async(self, query: str, top_k: int = 5) -> list[str]:
        """
        Perform semantic search using the embedding model.

        Args:
            query: The text query to search for
            top_k: Number of results to return

        Returns:
            List of file paths matching the query
        """
        if self.embedding_model is None:
            logger.warning(
                "Semantic search requested but embedding model is not available"
            )
            return []

        try:
            # Encode the query using a separate thread to not block

            def encode_func() -> Any:
                return (
                    self.embedding_model.encode(query) if self.embedding_model else None
                )

            query_embedding = await asyncio.to_thread(encode_func)

            if query_embedding is None:
                logger.warning("Failed to encode query")
                return []

            # Check if semantic index is initialized
            if self.semantic_index is None:
                logger.warning("Semantic index not initialized, cannot perform search")
                return []

            # The query_embedding must be a 2D numpy array for FAISS
            query_vector_reshaped = query_embedding.reshape(1, -1)

            if not hasattr(self.semantic_index, "search"):
                logger.warning("Semantic index doesn't have search method")
                return []

            # Call the FAISS search method
            # Use type: ignore to silence mypy errors about FAISS API
            _distances, indices = self.semantic_index.search(
                query_vector_reshaped, top_k
            )  # type: ignore

            # Map the results to file paths
            results = []
            for idx in indices[0]:
                if 0 <= idx < len(self.semantic_mapping):
                    results.append(self.semantic_mapping[idx])
            return results

        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []

    async def add_to_index_batch(
        self, file_metadata_list: list[FileMetadata], batch_size: int = 20
    ) -> list[Path]:
        """
        Add multiple files to the search index in batches.

        Args:
            file_metadata_list: List of file metadata objects to index
            batch_size: Number of files to process in each batch

        Returns:
            List of successfully indexed file paths
        """

        async def index_single_file(metadata: FileMetadata) -> Path | None:
            try:
                await self.add_to_index_async(metadata)
                return metadata.path
            except Exception as e:
                logger.error(f"Error indexing file {metadata.path}: {e}")
                return None

        processor = BatchProcessor()
        results = await processor.process_batch(
            items=file_metadata_list, operation=index_single_file, batch_size=batch_size
        )

        # Filter out None values from failed operations
        return [result for result in results if result is not None]

    async def regex_search_async(
        self,
        pattern: str,
        file_paths: list[Path] | None = None,
        case_sensitive: bool = False,
        whole_word: bool = False,
    ) -> list[str]:
        """
        Search for a regex pattern in file contents.

        Args:
            pattern: Regex pattern to search for
            file_paths: Optional list of file paths to search in
            case_sensitive: Whether to perform case-sensitive search
            whole_word: Whether to match whole words only

        Returns:
            List of file paths containing the pattern
        """
        if not self.regex_provider:
            logger.warning("Regex search requested but provider is not available")
            return []

        # Use the regex provider to search
        return await self.regex_provider.search(
            query=pattern,
            file_paths=file_paths if file_paths is not None else [],
            max_results=REGEX_MAX_RESULTS,
            case_sensitive=case_sensitive,
            whole_word=whole_word,
        )

    def search(
        self, query: str, method: str = "fulltext", case_sensitive: bool = False
    ) -> list[dict]:
        """
        Unified search method that dispatches to the appropriate search function based on method.

        Args:
            query: The search query
            method: The search method to use (filename, fulltext, fuzzy, regex)
            case_sensitive: Whether the search should be case sensitive (for fulltext)

        Returns:
            List of dictionaries containing search results with path and score
        """
        if not query:
            return []

        try:
            if method == "filename":
                # Run filename search asynchronously
                paths = asyncio.run(self.search_filename_async(query))
                return [{"path": path, "score": 1.0} for path in paths]

            elif method == "fuzzy":
                # Run fuzzy search asynchronously
                paths = asyncio.run(self.fuzzy_search_async(query))
                return [{"path": path, "score": 0.8} for path in paths]

            elif method == "fulltext":
                # Fulltext search is synchronous
                # TODO: Add case sensitivity support to fulltext search
                paths = self.full_text_search(query)
                return [{"path": path, "score": 0.9} for path in paths]

            else:
                logger.warning(f"Unsupported search method: {method}")
                return []

        except Exception as e:
            logger.error(f"Error in search ({method}): {e}")
            return []

    async def find_similar_files_async(
        self,
        file_path: Path,
        threshold: float | None = None,
        max_results: int = SIMILARITY_MAX_RESULTS,
    ) -> list[dict[str, str | float]]:
        """
        Find files similar to the given file.

        Args:
            file_path: Path to the reference file
            threshold: Similarity threshold (0.0 to 1.0)
            max_results: Maximum number of results to return

        Returns:
            List of dicts with file paths and similarity scores
        """
        if not self.similarity_provider:
            logger.warning("Similarity search requested but provider is not available")
            return []

        # Use the similarity provider to find similar files
        effective_threshold = 0.7 if threshold is None else threshold

        try:
            similarities = await self.similarity_provider.find_similar_files(
                file_path=file_path,
                threshold=effective_threshold,
                max_results=max_results,
            )

            # Format the results
            return [
                {"path": path, "score": float(score)} for path, score in similarities
            ]
        except Exception as e:
            logger.error(f"Error finding similar files: {e}")
            return []

    async def find_file_groups_async(
        self,
        file_paths: list[Path] | None = None,
        threshold: float | None = None,
        min_group_size: int | None = None,
    ) -> list[list[str]]:
        """
        Group files by similarity.

        Args:
            file_paths: Optional list of file paths to group
            threshold: Similarity threshold (0.0 to 1.0)
            min_group_size: Minimum number of files in a group

        Returns:
            List of file groups
        """
        if not self.similarity_provider:
            logger.warning(
                "File grouping requested but similarity provider is not available"
            )
            return []

        # Use default values if not provided
        effective_threshold = 0.7 if threshold is None else threshold
        effective_min_group_size = 2 if min_group_size is None else min_group_size

        # Convert Path objects to union of strings and Paths for compatibility
        converted_paths: list[str | Path] | None = None
        if file_paths is not None:
            # Convert to List[Union[str, Path]] since the provider accepts either type
            converted_paths = [str(p) if isinstance(p, Path) else p for p in file_paths]

        try:
            # Use the similarity provider to find file groups
            return await self.similarity_provider.find_file_groups(
                file_paths=converted_paths,
                threshold=effective_threshold,
                min_group_size=effective_min_group_size,
            )
        except Exception as e:
            logger.error(f"Error grouping files: {e}")
            return []


# Example Usage:
if __name__ == "__main__":

    async def main() -> None:
        search_engine = SearchEngine(index_dir=Path("search_index"))
        # Example file metadata with custom tags.
        file_metadata = FileMetadata(
            path=Path("/documents/example.txt"),
            mime_type="text/plain",
            size=1024,
            extension=".txt",
            preview="This is an example document containing searchable text.",
        )
        file_metadata.tags = ["important", "example"]
        await search_engine.add_to_index_async(file_metadata)
        filename_results = await search_engine.search_filename_async("example")
        fuzzy_results = await search_engine.fuzzy_search_async("exmple")
        full_text_results = search_engine.full_text_search("searchable")
        metadata_filters = {
            "extension": [".txt"],
            "size_min": 500,
            "size_max": 2000,
            "tags": ["important"],
        }
        metadata_results = await search_engine.metadata_search_async(metadata_filters)
        semantic_results = await search_engine.semantic_search_async("document text")
        print("Filename Search:", filename_results)
        print("Fuzzy Search:", fuzzy_results)
        print("Full-Text Search:", full_text_results)
        print("Metadata Search:", metadata_results)
        print("Semantic Search:", semantic_results)

    asyncio.run(main())
