"""
Pytest configuration and fixtures for AIchemist Archivum tests.

This module provides common fixtures and configuration for all tests.
"""

import asyncio
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
import pytest_asyncio
from aichemist_archivum.core.search.search_engine import SearchEngine
from aichemist_archivum.services.database_service import DatabaseService
from aichemist_archivum.services.ingestion_service import IngestionService
from aichemist_archivum.utils.cache.cache_manager import CacheManager


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the entire test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_db_path(temp_dir: Path) -> Path:
    """Provide a temporary database path."""
    return temp_dir / "test_archivum.db"


@pytest_asyncio.fixture
async def database_service(temp_db_path: Path) -> DatabaseService:
    """Provide an initialized database service for tests."""
    service = DatabaseService(db_path=temp_db_path)
    await service.initialize_schema()
    return service


@pytest.fixture
def cache_manager(temp_dir: Path) -> CacheManager:
    """Provide a cache manager for tests."""
    cache_dir = temp_dir / "cache"
    cache_dir.mkdir(exist_ok=True)
    return CacheManager(cache_dir=cache_dir)


@pytest_asyncio.fixture
async def ingestion_service(cache_manager: CacheManager) -> IngestionService:
    """Provide an ingestion service for tests."""
    return IngestionService(cache_manager=cache_manager)


@pytest.fixture
def search_engine(temp_dir: Path) -> SearchEngine:
    """Provide a search engine for tests."""
    index_dir = temp_dir / "search_index"
    index_dir.mkdir(exist_ok=True)
    return SearchEngine(index_dir=index_dir)


@pytest.fixture
def sample_text_file(temp_dir: Path) -> Path:
    """Create a sample text file for testing."""
    file_path = temp_dir / "sample.txt"
    file_path.write_text("This is a sample text file for testing.")
    return file_path


@pytest.fixture
def sample_python_file(temp_dir: Path) -> Path:
    """Create a sample Python file for testing."""
    file_path = temp_dir / "sample.py"
    file_path.write_text(
        '"""Sample Python module."""\n\n'
        "def hello_world():\n"
        '    """Say hello."""\n'
        '    return "Hello, World!"\n'
    )
    return file_path


@pytest.fixture
def sample_markdown_file(temp_dir: Path) -> Path:
    """Create a sample Markdown file for testing."""
    file_path = temp_dir / "sample.md"
    file_path.write_text(
        "# Sample Document\n\n"
        "This is a sample markdown document.\n\n"
        "## Features\n\n"
        "- Item 1\n"
        "- Item 2\n"
    )
    return file_path
