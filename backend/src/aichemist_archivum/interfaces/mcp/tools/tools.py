"""
MCP Tools for AIchemist Archivum.

This module contains all tool definitions and implementations.
Tools can be easily added, modified, or removed without touching the server logic.
"""

import logging
from pathlib import Path
from typing import Any

import mcp.types as types

from aichemist_archivum.config import DATA_DIR
from aichemist_archivum.core.search.search_engine import SearchEngine
from aichemist_archivum.services.database_service import DatabaseService
from aichemist_archivum.services.ingestion_service import IngestionService
from aichemist_archivum.utils.cache.cache_manager import get_cache_manager

logger = logging.getLogger(__name__)

# ============================================================================
# SERVICE INSTANCES (Lazy-loaded singletons)
# ============================================================================

_search_engine: SearchEngine | None = None
_database_service: DatabaseService | None = None
_ingestion_service: IngestionService | None = None


def get_search_engine() -> SearchEngine:
    """Get or create search engine instance."""
    global _search_engine
    if _search_engine is None:
        index_dir = DATA_DIR / "search_index"
        index_dir.mkdir(parents=True, exist_ok=True)
        _search_engine = SearchEngine(index_dir=index_dir)
    return _search_engine


def get_database_service() -> DatabaseService:
    """Get or create database service instance."""
    global _database_service
    if _database_service is None:
        _database_service = DatabaseService()
    return _database_service


def get_ingestion_service() -> IngestionService:
    """Get or create ingestion service instance."""
    global _ingestion_service
    if _ingestion_service is None:
        cache_manager = get_cache_manager()
        _ingestion_service = IngestionService(cache_manager=cache_manager)
    return _ingestion_service


# ============================================================================
# TOOL DEFINITIONS
# ============================================================================


def get_tool_definitions() -> list[types.Tool]:
    """
    Return list of all available tool definitions.

    Add new tools here to make them available to AI agents.
    """
    return [
        types.Tool(
            name="search_semantic",
            description="Search ingested documents using semantic/AI search. Best for finding content by meaning rather than exact keywords.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query (natural language)",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 10)",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="search_fulltext",
            description="Search ingested documents using full-text keyword search. Good for finding exact terms or phrases.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query (keywords)",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 20)",
                        "default": 20,
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="search_files",
            description="Search for files by filename or pattern. Supports fuzzy matching.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Filename pattern to search for",
                    },
                    "fuzzy": {
                        "type": "boolean",
                        "description": "Use fuzzy matching (default: true)",
                        "default": True,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 50)",
                        "default": 50,
                    },
                },
                "required": ["pattern"],
            },
        ),
        types.Tool(
            name="search_by_tags",
            description="Search for files that have specific tags.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of tags to search for",
                    },
                    "match_all": {
                        "type": "boolean",
                        "description": "Require all tags (AND logic) vs any tag (OR logic). Default: false (OR)",
                        "default": False,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 50)",
                        "default": 50,
                    },
                },
                "required": ["tags"],
            },
        ),
        types.Tool(
            name="ingest_folder",
            description="Ingest files from a folder into the knowledge base. Extracts metadata, generates embeddings, and indexes content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the folder to ingest",
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Process subfolders recursively (default: true)",
                        "default": True,
                    },
                    "max_files": {
                        "type": "integer",
                        "description": "Maximum number of files to process (optional)",
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "File pattern to match (e.g., '*.py', '*.txt')",
                    },
                },
                "required": ["path"],
            },
        ),
        types.Tool(
            name="ingest_file",
            description="Ingest a single file into the knowledge base.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to ingest",
                    }
                },
                "required": ["path"],
            },
        ),
        types.Tool(
            name="add_tags",
            description="Add tags to a file for better organization and searchability.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of tags to add",
                    },
                },
                "required": ["file_path", "tags"],
            },
        ),
        types.Tool(
            name="list_tags",
            description="List all tags in the system with usage counts.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="get_statistics",
            description="Get database statistics (total files, tags, etc.).",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


# ============================================================================
# TOOL ROUTER
# ============================================================================


async def execute_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    """
    Route tool execution to the appropriate handler.

    Args:
        name: Name of the tool to execute
        arguments: Dictionary of arguments for the tool

    Returns:
        List of TextContent responses

    Raises:
        Exception: If tool execution fails
    """
    tool_handlers = {
        "search_semantic": tool_search_semantic,
        "search_fulltext": tool_search_fulltext,
        "search_files": tool_search_files,
        "search_by_tags": tool_search_by_tags,
        "ingest_folder": tool_ingest_folder,
        "ingest_file": tool_ingest_file,
        "add_tags": tool_add_tags,
        "list_tags": tool_list_tags,
        "get_statistics": tool_get_statistics,
    }

    handler = tool_handlers.get(name)
    if handler is None:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    try:
        return await handler(arguments)
    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: {e!s}")]


# ============================================================================
# TOOL IMPLEMENTATIONS
# ============================================================================


async def tool_search_semantic(args: dict) -> list[types.TextContent]:
    """Semantic search implementation."""
    query = args["query"]
    max_results = args.get("max_results", 10)

    search_engine = get_search_engine()
    results = await search_engine.semantic_search_async(query, top_k=max_results)

    if not results:
        return [
            types.TextContent(
                type="text",
                text=f"No results found for semantic search: '{query}'\n\nMake sure files have been ingested first.",
            )
        ]

    result_text = f"🔍 Semantic Search Results for: '{query}'\n\n"
    result_text += f"Found {len(results)} results:\n\n"

    for i, path in enumerate(results, 1):
        result_text += f"{i}. {path}\n"

    return [types.TextContent(type="text", text=result_text)]


async def tool_search_fulltext(args: dict) -> list[types.TextContent]:
    """Full-text search implementation."""
    query = args["query"]
    max_results = args.get("max_results", 20)

    search_engine = get_search_engine()
    results = search_engine.full_text_search(query)
    results = results[:max_results]

    if not results:
        return [
            types.TextContent(
                type="text", text=f"No results found for full-text search: '{query}'"
            )
        ]

    result_text = f"📝 Full-Text Search Results for: '{query}'\n\n"
    result_text += f"Found {len(results)} results:\n\n"

    for i, path in enumerate(results, 1):
        result_text += f"{i}. {path}\n"

    return [types.TextContent(type="text", text=result_text)]


async def tool_search_files(args: dict) -> list[types.TextContent]:
    """Filename search implementation."""
    pattern = args["pattern"]
    fuzzy = args.get("fuzzy", True)
    max_results = args.get("max_results", 50)

    search_engine = get_search_engine()

    if fuzzy:
        results = await search_engine.fuzzy_search_async(pattern, threshold=60.0)
    else:
        results = await search_engine.search_filename_async(pattern)

    results = results[:max_results]

    if not results:
        return [
            types.TextContent(
                type="text", text=f"No files found matching pattern: '{pattern}'"
            )
        ]

    result_text = f"📁 File Search Results for: '{pattern}'\n\n"
    result_text += f"Found {len(results)} files:\n\n"

    for i, path in enumerate(results, 1):
        result_text += f"{i}. {Path(path).name} - {path}\n"

    return [types.TextContent(type="text", text=result_text)]


async def tool_search_by_tags(args: dict) -> list[types.TextContent]:
    """Tag-based search implementation."""
    tags = args["tags"]
    match_all = args.get("match_all", False)
    max_results = args.get("max_results", 50)

    db_service = get_database_service()
    results = await db_service.search_files_by_tags(tags, match_all=match_all)
    results = results[:max_results]

    if not results:
        logic = "all" if match_all else "any"
        return [
            types.TextContent(
                type="text",
                text=f"No files found with {logic} of these tags: {', '.join(tags)}",
            )
        ]

    logic = "AND" if match_all else "OR"
    result_text = f"🏷️  Tag Search Results for: {', '.join(tags)} ({logic})\n\n"
    result_text += f"Found {len(results)} files:\n\n"

    for i, file_data in enumerate(results, 1):
        file_tags = (
            file_data.get("tags", "").split(",") if file_data.get("tags") else []
        )
        result_text += f"{i}. {file_data['filename']}\n"
        result_text += f"   Path: {file_data['path']}\n"
        result_text += f"   Tags: {', '.join(file_tags)}\n\n"

    return [types.TextContent(type="text", text=result_text)]


async def tool_ingest_folder(args: dict) -> list[types.TextContent]:
    """Folder ingestion implementation."""
    path = Path(args["path"])
    recursive = args.get("recursive", True)
    max_files = args.get("max_files")
    file_pattern = args.get("file_pattern", "*")

    if not path.exists():
        return [
            types.TextContent(type="text", text=f"❌ Error: Folder not found: {path}")
        ]

    if not path.is_dir():
        return [
            types.TextContent(
                type="text", text=f"❌ Error: Path is not a directory: {path}"
            )
        ]

    # Collect files
    if recursive:
        files_to_process = list(path.rglob(file_pattern))
    else:
        files_to_process = list(path.glob(file_pattern))

    files_to_process = [f for f in files_to_process if f.is_file()]

    if max_files:
        files_to_process = files_to_process[:max_files]

    if not files_to_process:
        return [
            types.TextContent(
                type="text",
                text=f"ℹ️ No files found in {path} matching pattern '{file_pattern}'",
            )
        ]

    # Process files
    ingestion_service = get_ingestion_service()
    db_service = get_database_service()
    search_engine = get_search_engine()

    await db_service.initialize_schema()

    processed = 0
    errors = 0

    for file_path in files_to_process:
        try:
            # Extract metadata
            metadata = await ingestion_service.extract_metadata(file_path)

            if metadata.error:
                errors += 1
            else:
                # Save to database
                await db_service.save_file_metadata(metadata)

                # Add to search index
                await search_engine.add_to_index_async(metadata)

                processed += 1
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            errors += 1

    result_text = "✅ Ingestion Complete\n\n"
    result_text += f"Folder: {path}\n"
    result_text += f"Files processed: {processed}\n"
    result_text += f"Errors: {errors}\n"
    result_text += f"Total files found: {len(files_to_process)}\n"

    return [types.TextContent(type="text", text=result_text)]


async def tool_ingest_file(args: dict) -> list[types.TextContent]:
    """Single file ingestion implementation."""
    path = Path(args["path"])

    if not path.exists():
        return [
            types.TextContent(type="text", text=f"❌ Error: File not found: {path}")
        ]

    if not path.is_file():
        return [
            types.TextContent(type="text", text=f"❌ Error: Path is not a file: {path}")
        ]

    # Process file
    ingestion_service = get_ingestion_service()
    db_service = get_database_service()
    search_engine = get_search_engine()

    await db_service.initialize_schema()

    try:
        # Extract metadata
        metadata = await ingestion_service.extract_metadata(path)

        if metadata.error:
            return [
                types.TextContent(
                    type="text", text=f"❌ Error processing file: {metadata.error}"
                )
            ]

        # Save to database
        await db_service.save_file_metadata(metadata)

        # Add to search index
        await search_engine.add_to_index_async(metadata)

        result_text = "✅ File Ingested Successfully\n\n"
        result_text += f"File: {path.name}\n"
        result_text += f"Path: {path}\n"
        result_text += f"Size: {metadata.size} bytes\n"
        result_text += f"Type: {metadata.mime_type}\n"
        result_text += f"Processing time: {metadata.extraction_time:.2f}s\n"

        return [types.TextContent(type="text", text=result_text)]

    except Exception as e:
        return [types.TextContent(type="text", text=f"❌ Error ingesting file: {e}")]


async def tool_add_tags(args: dict) -> list[types.TextContent]:
    """Add tags to file implementation."""
    file_path = Path(args["file_path"])
    tags = args["tags"]

    if not file_path.exists():
        return [
            types.TextContent(
                type="text", text=f"❌ Error: File not found: {file_path}"
            )
        ]

    db_service = get_database_service()

    try:
        await db_service.add_tags_to_file(file_path, tags)

        result_text = "✅ Tags Added Successfully\n\n"
        result_text += f"File: {file_path.name}\n"
        result_text += f"Tags: {', '.join(tags)}\n"

        return [types.TextContent(type="text", text=result_text)]

    except Exception as e:
        return [types.TextContent(type="text", text=f"❌ Error adding tags: {e}")]


async def tool_list_tags(args: dict) -> list[types.TextContent]:
    """List all tags implementation."""
    db_service = get_database_service()

    try:
        tags = await db_service.get_all_tags()

        if not tags:
            return [
                types.TextContent(type="text", text="ℹ️ No tags found in the system.")
            ]

        result_text = f"🏷️  All Tags ({len(tags)} total)\n\n"

        for tag in tags:
            result_text += f"• {tag['name']}"
            if tag.get("usage_count", 0) > 0:
                result_text += f" ({tag['usage_count']} files)"
            if tag.get("description"):
                result_text += f" - {tag['description']}"
            result_text += "\n"

        return [types.TextContent(type="text", text=result_text)]

    except Exception as e:
        return [types.TextContent(type="text", text=f"❌ Error listing tags: {e}")]


async def tool_get_statistics(args: dict) -> list[types.TextContent]:
    """Get database statistics implementation."""
    db_service = get_database_service()

    try:
        stats = await db_service.get_statistics()

        result_text = "📊 Database Statistics\n\n"
        result_text += f"Total Files: {stats.get('total_files', 0)}\n"
        result_text += f"Total Tags: {stats.get('total_tags', 0)}\n"
        result_text += (
            f"Total File-Tag Associations: {stats.get('total_file_tags', 0)}\n"
        )
        result_text += f"Total Versions: {stats.get('total_versions', 0)}\n"
        result_text += f"Average Tags per File: {stats.get('avg_tags_per_file', 0)}\n"

        return [types.TextContent(type="text", text=result_text)]

    except Exception as e:
        return [
            types.TextContent(type="text", text=f"❌ Error getting statistics: {e}")
        ]
