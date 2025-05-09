"""
Search Engine Module

This module provides search capabilities for The Aichemist Codex, including:
- Filename search (exact and partial matching)
- Full-text search using Whoosh indexing
- Fuzzy search using RapidFuzz
- Metadata-based filtering

Imports:
    - `SearchEngine`: Main search handler for indexing and querying files.
"""

from .search_engine import SearchEngine

__all__ = ["SearchEngine"]
