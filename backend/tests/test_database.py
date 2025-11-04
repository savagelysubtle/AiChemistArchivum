"""
Tests for the database service.

Tests database initialization, CRUD operations for files and tags.
"""

from pathlib import Path

import pytest
from aichemist_archivum.core.fs.file_metadata import FileMetadata
from aichemist_archivum.services.database_service import DatabaseService


@pytest.mark.asyncio
async def test_database_initialization(database_service: DatabaseService):
    """Test that database schema is initialized correctly."""
    stats = await database_service.get_statistics()

    assert "total_files" in stats
    assert "total_tags" in stats
    assert stats["total_files"] == 0
    assert stats["total_tags"] == 0


@pytest.mark.asyncio
async def test_save_file_metadata(
    database_service: DatabaseService, sample_text_file: Path
):
    """Test saving file metadata to database."""
    metadata = await FileMetadata.from_path(sample_text_file)

    file_id = await database_service.save_file_metadata(metadata)

    assert file_id > 0

    # Verify file was saved
    file_info = await database_service.get_file_by_path(sample_text_file)
    assert file_info is not None
    assert file_info["path"] == str(sample_text_file)


@pytest.mark.asyncio
async def test_add_tags_to_file(
    database_service: DatabaseService, sample_text_file: Path
):
    """Test adding tags to a file."""
    metadata = await FileMetadata.from_path(sample_text_file)
    await database_service.save_file_metadata(metadata)

    # Add tags
    tags = ["test", "important", "document"]
    await database_service.add_tags_to_file(sample_text_file, tags)

    # Verify tags were added
    file_tags = await database_service.get_file_tags(sample_text_file)
    tag_names = [tag["name"] for tag in file_tags]

    for tag in tags:
        assert tag in tag_names


@pytest.mark.asyncio
async def test_remove_tags_from_file(
    database_service: DatabaseService, sample_text_file: Path
):
    """Test removing tags from a file."""
    metadata = await FileMetadata.from_path(sample_text_file)
    await database_service.save_file_metadata(metadata)

    # Add tags
    tags = ["test", "important", "document"]
    await database_service.add_tags_to_file(sample_text_file, tags)

    # Remove one tag
    await database_service.remove_tags_from_file(sample_text_file, ["important"])

    # Verify tag was removed
    file_tags = await database_service.get_file_tags(sample_text_file)
    tag_names = [tag["name"] for tag in file_tags]

    assert "important" not in tag_names
    assert "test" in tag_names
    assert "document" in tag_names


@pytest.mark.asyncio
async def test_search_files_by_tags(database_service: DatabaseService, temp_dir: Path):
    """Test searching for files by tags."""
    # Create and save multiple files with different tags
    file1 = temp_dir / "file1.txt"
    file1.write_text("File 1")
    metadata1 = await FileMetadata.from_path(file1)
    await database_service.save_file_metadata(metadata1)
    await database_service.add_tags_to_file(file1, ["python", "code"])

    file2 = temp_dir / "file2.txt"
    file2.write_text("File 2")
    metadata2 = await FileMetadata.from_path(file2)
    await database_service.save_file_metadata(metadata2)
    await database_service.add_tags_to_file(file2, ["python", "tutorial"])

    file3 = temp_dir / "file3.txt"
    file3.write_text("File 3")
    metadata3 = await FileMetadata.from_path(file3)
    await database_service.save_file_metadata(metadata3)
    await database_service.add_tags_to_file(file3, ["document"])

    # Search for files with "python" tag
    results = await database_service.search_files_by_tags(["python"], match_all=False)
    assert len(results) == 2

    # Search for files with both "python" and "code" tags
    results = await database_service.search_files_by_tags(
        ["python", "code"], match_all=True
    )
    assert len(results) == 1


@pytest.mark.asyncio
async def test_get_all_tags(database_service: DatabaseService, temp_dir: Path):
    """Test getting all tags in the system."""
    # Create files with tags
    file1 = temp_dir / "file1.txt"
    file1.write_text("File 1")
    metadata1 = await FileMetadata.from_path(file1)
    await database_service.save_file_metadata(metadata1)
    await database_service.add_tags_to_file(file1, ["tag1", "tag2"])

    file2 = temp_dir / "file2.txt"
    file2.write_text("File 2")
    metadata2 = await FileMetadata.from_path(file2)
    await database_service.save_file_metadata(metadata2)
    await database_service.add_tags_to_file(file2, ["tag2", "tag3"])

    # Get all tags
    all_tags = await database_service.get_all_tags()

    assert len(all_tags) >= 3
    tag_names = [tag["name"] for tag in all_tags]
    assert "tag1" in tag_names
    assert "tag2" in tag_names
    assert "tag3" in tag_names

    # Check usage counts
    tag2 = [tag for tag in all_tags if tag["name"] == "tag2"][0]
    assert tag2["usage_count"] == 2


@pytest.mark.asyncio
async def test_create_tag(database_service: DatabaseService):
    """Test creating a tag."""
    tag_id = await database_service.create_tag(
        name="new_tag", description="A new test tag", category="test"
    )

    assert tag_id > 0

    # Verify tag was created
    all_tags = await database_service.get_all_tags()
    tag_names = [tag["name"] for tag in all_tags]
    assert "new_tag" in tag_names
