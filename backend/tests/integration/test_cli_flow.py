"""
Integration tests for the CLI flow.

Tests end-to-end workflows: ingest → search → tag
"""

from pathlib import Path

import pytest
from aichemist_archivum.core.search.search_engine import SearchEngine
from aichemist_archivum.services.database_service import DatabaseService
from aichemist_archivum.services.ingestion_service import IngestionService


@pytest.mark.asyncio
async def test_ingest_search_flow(
    database_service: DatabaseService,
    ingestion_service: IngestionService,
    search_engine: SearchEngine,
    sample_text_file: Path,
):
    """Test the complete flow: ingest a file and search for it."""
    # Step 1: Ingest the file
    metadata = await ingestion_service.extract_metadata(sample_text_file)
    assert metadata.error is None

    # Step 2: Save to database
    file_id = await database_service.save_file_metadata(metadata)
    assert file_id > 0

    # Step 3: Add to search index (would be done in real flow)
    # For now, just verify database contains the file
    file_info = await database_service.get_file_by_path(sample_text_file)
    assert file_info is not None


@pytest.mark.asyncio
async def test_ingest_tag_search_flow(
    database_service: DatabaseService,
    ingestion_service: IngestionService,
    temp_dir: Path,
):
    """Test the complete flow: ingest → tag → search by tags."""
    # Create test file
    test_file = temp_dir / "test_document.txt"
    test_file.write_text("This is a test document for the integration test.")

    # Step 1: Ingest the file
    metadata = await ingestion_service.extract_metadata(test_file)
    assert metadata.error is None

    # Step 2: Save to database
    await database_service.save_file_metadata(metadata)

    # Step 3: Add tags
    tags = ["integration", "test", "document"]
    await database_service.add_tags_to_file(test_file, tags)

    # Step 4: Search by tags
    results = await database_service.search_files_by_tags(
        ["integration"], match_all=False
    )

    # Verify results
    assert len(results) > 0
    result_paths = [result["path"] for result in results]
    assert str(test_file) in result_paths


@pytest.mark.asyncio
async def test_batch_ingest_flow(
    database_service: DatabaseService,
    ingestion_service: IngestionService,
    temp_dir: Path,
):
    """Test batch ingestion of multiple files."""
    # Create multiple test files
    files = []
    for i in range(5):
        file_path = temp_dir / f"batch_file_{i}.txt"
        file_path.write_text(f"Content of batch file {i}")
        files.append(file_path)

    # Ingest all files
    for file_path in files:
        metadata = await ingestion_service.extract_metadata(file_path)
        assert metadata.error is None
        await database_service.save_file_metadata(metadata)

    # Verify all files are in database
    stats = await database_service.get_statistics()
    assert stats["total_files"] >= 5


@pytest.mark.asyncio
async def test_full_workflow(
    database_service: DatabaseService,
    ingestion_service: IngestionService,
    temp_dir: Path,
):
    """Test a complete realistic workflow."""
    # Create a set of related files
    python_file = temp_dir / "script.py"
    python_file.write_text("print('Hello, World!')")

    readme_file = temp_dir / "README.md"
    readme_file.write_text("# Project\n\nThis is a test project.")

    config_file = temp_dir / "config.yaml"
    config_file.write_text("key: value\n")

    # Step 1: Ingest all files
    for file_path in [python_file, readme_file, config_file]:
        metadata = await ingestion_service.extract_metadata(file_path)
        await database_service.save_file_metadata(metadata)

    # Step 2: Tag files appropriately
    await database_service.add_tags_to_file(python_file, ["code", "python", "script"])
    await database_service.add_tags_to_file(readme_file, ["documentation", "markdown"])
    await database_service.add_tags_to_file(config_file, ["configuration", "yaml"])

    # Step 3: Search by tags
    code_files = await database_service.search_files_by_tags(["code"], match_all=False)
    assert len(code_files) == 1

    doc_files = await database_service.search_files_by_tags(
        ["documentation"], match_all=False
    )
    assert len(doc_files) == 1

    # Step 4: Get statistics
    stats = await database_service.get_statistics()
    assert stats["total_files"] >= 3
    assert stats["total_tags"] >= 8
    assert stats["avg_tags_per_file"] > 0
