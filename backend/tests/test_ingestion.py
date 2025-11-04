"""
Tests for the ingestion service.

Tests file metadata extraction, batch processing, and error handling.
"""

from pathlib import Path

import pytest
from aichemist_archivum.services.ingestion_service import IngestionService


@pytest.mark.asyncio
async def test_extract_metadata_text_file(
    ingestion_service: IngestionService, sample_text_file: Path
):
    """Test metadata extraction from a text file."""
    metadata = await ingestion_service.extract_metadata(sample_text_file)

    assert metadata.path == sample_text_file
    assert metadata.size > 0
    assert metadata.error is None
    assert metadata.extraction_complete


@pytest.mark.asyncio
async def test_extract_metadata_python_file(
    ingestion_service: IngestionService, sample_python_file: Path
):
    """Test metadata extraction from a Python file."""
    metadata = await ingestion_service.extract_metadata(sample_python_file)

    assert metadata.path == sample_python_file
    assert metadata.extension == ".py"
    assert metadata.error is None
    assert metadata.extraction_complete


@pytest.mark.asyncio
async def test_extract_metadata_markdown_file(
    ingestion_service: IngestionService, sample_markdown_file: Path
):
    """Test metadata extraction from a Markdown file."""
    metadata = await ingestion_service.extract_metadata(sample_markdown_file)

    assert metadata.path == sample_markdown_file
    assert metadata.extension == ".md"
    assert metadata.error is None
    assert metadata.extraction_complete


@pytest.mark.asyncio
async def test_extract_metadata_nonexistent_file(
    ingestion_service: IngestionService, temp_dir: Path
):
    """Test metadata extraction from a nonexistent file."""
    nonexistent_file = temp_dir / "nonexistent.txt"
    metadata = await ingestion_service.extract_metadata(nonexistent_file)

    # Should still return metadata with an error
    assert metadata.path == nonexistent_file
    assert metadata.error is not None


@pytest.mark.asyncio
async def test_batch_extraction(ingestion_service: IngestionService, temp_dir: Path):
    """Test batch extraction of multiple files."""
    # Create multiple test files
    files = []
    for i in range(5):
        file_path = temp_dir / f"file_{i}.txt"
        file_path.write_text(f"Content of file {i}")
        files.append(file_path)

    # Extract metadata for all files
    results = []
    for file_path in files:
        metadata = await ingestion_service.extract_metadata(file_path)
        results.append(metadata)

    # All files should be processed successfully
    assert len(results) == 5
    for metadata in results:
        assert metadata.error is None
        assert metadata.extraction_complete
