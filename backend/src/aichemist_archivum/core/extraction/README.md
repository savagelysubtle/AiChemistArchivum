# Infrastructure Extraction Module

This module provides the concrete implementations for extracting metadata from files and managing associated tags within The AIChemist Codex. It adheres to Clean Architecture principles, meaning higher layers (like `application`) should interact with this module primarily through interfaces defined in `domain` or `application`, or via coordinating application services.

## Core Components

1.  **`MetadataManager` (`extraction.manager.MetadataManager`)**:
    *   **Purpose**: The primary entry point for orchestrating file metadata extraction. It uses registered `BaseMetadataExtractor` implementations (`CodeMetadataExtractor`, `DocumentMetadataExtractor`, etc.) based on MIME types to analyze files.
    *   **Instantiation**: Requires an optional `CacheManager` instance (from `infrastructure.utils.cache`) and configuration values (like `max_concurrent_batch` from `infrastructure.config`) injected during setup.
    *   **Usage**:
        *   `extract_metadata(file_path, ...)`: Extracts metadata for a single file. Returns an enhanced `FileMetadata` object (`infrastructure.fs.file_metadata.FileMetadata`).
        *   `extract_batch(file_paths, ...)`: Extracts metadata for multiple files concurrently. Returns a list of `FileMetadata` objects.

    ```python
    # --- Example (within an Application Service or Interface Implementation) ---
    from pathlib import Path
    from the_aichemist_codex.infrastructure.extraction import MetadataManager
    from the_aichemist_codex.infrastructure.utils.cache import cache_manager # Singleton instance
    from the_aichemist_codex.infrastructure.config import config

    # Assuming config is loaded and cache_manager is initialized elsewhere

    # Instantiate MetadataManager (likely via Dependency Injection)
    extraction_config = config.get('extraction', {})
    metadata_manager = MetadataManager(
        cache_manager=cache_manager,
        max_concurrent_batch=extraction_config.get('metadata_manager_max_concurrent_batch', 5)
    )

    async def process_single_file(file_path_str: str):
        file_path = Path(file_path_str)
        try:
            # Get basic file info first (perhaps from a file system service)
            # ... basic_metadata = ...

            # Enhance metadata using the manager
            enhanced_metadata = await metadata_manager.extract_metadata(
                file_path=file_path,
                # metadata=basic_metadata # Optionally pass existing metadata
            )

            # Use the enhanced_metadata (e.g., save to DB, pass to tagging)
            print(f"Extracted for {file_path}: {enhanced_metadata.mime_type}")
            if hasattr(enhanced_metadata, 'code_language'):
                print(f"  Language: {enhanced_metadata.code_language}")
            if hasattr(enhanced_metadata, 'title'):
                print(f"  Title: {enhanced_metadata.title}")

        except FileNotFoundError:
            print(f"File not found: {file_path}")
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    async def process_multiple_files(file_paths_list: list[str]):
        file_paths = [Path(p) for p in file_paths_list]
        results = await metadata_manager.extract_batch(file_paths)
        for metadata in results:
            if metadata.error:
                print(f"Error extracting {metadata.path}: {metadata.error}")
            else:
                print(f"Extracted batch for {metadata.path}: {metadata.mime_type}")
                # ... process metadata ...

    # --- End Example ---
    ```

2.  **`TagManager` (`extraction.tagging.TagManager`)**:
    *   **Purpose**: Manages the persistent storage and retrieval of tags and their associations with file paths using an SQLite database (via `infrastructure.utils.io.sqlasync_io.AsyncSQL`).
    *   **Instantiation**: Requires the `db_path` (likely from configuration) for the SQLite database.
    *   **Usage**: Provides async methods like `create_tag`, `get_tag`, `add_file_tag`, `remove_file_tag`, `get_file_tags`, `get_files_by_tag`, `get_tag_counts`, etc.

3.  **`TagClassifier` (`extraction.tagging.TagClassifier`)**:
    *   **Purpose**: Implements the `TagClassifierInterface` (defined in `domain`). Uses machine learning (`sklearn`) to automatically classify files and suggest tags based on their `FileMetadata`.
    *   **Instantiation**: Requires `model_dir` (where the ML model is stored/loaded, likely from configuration) and the `default_confidence_threshold` (from configuration).
    *   **Usage**:
        *   `classify(file_metadata, ...)`: Takes a `FileMetadata` object (potentially enhanced by `MetadataManager`) and returns a list of suggested `(tag_name, confidence_score)` tuples.
        *   `train(...)`: Used for training the model (likely triggered by a separate process or admin action).
        *   `load_model()`, `save_model()`: Manage model persistence.

    ```python
    # --- Example (within an Application Service or Interface Implementation) ---
    from pathlib import Path
    from the_aichemist_codex.infrastructure.extraction.tagging import TagManager, TagClassifier
    from the_aichemist_codex.infrastructure.fs.file_metadata import FileMetadata # Assume we have this object
    from the_aichemist_codex.infrastructure.config import config

    # Assuming config is loaded

    # Instantiate TagManager and TagClassifier (likely via Dependency Injection)
    tag_db_path = Path(config.get('database', {}).get('tag_db_path', 'tags.db'))
    model_dir_path = Path(config.get('paths', {}).get('tag_model_dir', 'models/tags'))
    extraction_config = config.get('extraction', {})

    tag_manager = TagManager(db_path=tag_db_path)
    tag_classifier = TagClassifier(
        model_dir=model_dir_path,
        default_confidence_threshold=extraction_config.get('tag_classifier_default_confidence_threshold', 0.6)
    )

    async def tag_file_after_extraction(metadata: FileMetadata):
        if not metadata or metadata.error or not metadata.path:
            print("Cannot tag file with invalid metadata.")
            return

        await tag_manager.initialize() # Ensure DB is ready
        await tag_classifier.load_model() # Ensure model is loaded

        # 1. Get automatic tag suggestions
        suggested_tags = await tag_classifier.classify(metadata) # Use default threshold

        # 2. Add suggested tags via TagManager
        added_count = await tag_manager.add_file_tags(
            file_path=metadata.path,
            tags=suggested_tags,
            source="auto"
        )
        print(f"Added {added_count} automatic tags for {metadata.path}")

        # 3. Retrieve all tags for the file (including manual/existing)
        all_tags = await tag_manager.get_file_tags(metadata.path)
        print(f"All tags for {metadata.path}: {all_tags}")

        await tag_manager.close() # Close DB connection if managing manually

    # --- End Example ---
    ```

## Interaction Principles

*   **Dependency Inversion**: Infrastructure components like `MetadataManager`, `TagManager`, and `TagClassifier` should ideally be injected into application services or implementations of domain/application interfaces. Avoid direct instantiation from high-level application logic.
*   **Configuration**: Use the central `infrastructure.config` system to provide necessary paths (`db_path`, `model_dir`), thresholds, and settings (`max_concurrent_batch`) to these components.
*   **Orchestration**: Application-layer services are responsible for coordinating these infrastructure components. For example, an application service might:
    1.  Receive a file path.
    2.  Call `MetadataManager.extract_metadata`.
    3.  Pass the resulting `FileMetadata` to `TagClassifier.classify`.
    4.  Use `TagManager.add_file_tags` to store the suggested tags.
    5.  Use `TagManager` again to store any user-provided manual tags.
*   **Error Handling**: Infrastructure components will raise exceptions (specific ones like `FileNotFoundError`, `sqlite3.Error`, `ValueError`, or potentially `RuntimeError` for unexpected issues). Calling layers (application services) are responsible for catching and handling these appropriately (e.g., logging, returning errors to the user, retrying).
