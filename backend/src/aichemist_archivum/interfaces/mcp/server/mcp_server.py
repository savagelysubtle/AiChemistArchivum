"""
Main MCP server for AIchemist Archivum.

This server handles MCP protocol communication and delegates tool execution
to the tools module. This separation allows independent evolution of protocol
handling and tool implementations.
"""

import asyncio
import logging
from pathlib import Path

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from ..tools import execute_tool, get_database_service, get_tool_definitions

logger = logging.getLogger(__name__)

# Initialize server
server = Server("aichemist-archivum")


# ============================================================================
# RESOURCES - Expose ingested files as readable resources
# ============================================================================


@server.list_resources()
async def list_resources() -> list[types.Resource]:
    """
    List all ingested files as MCP resources.

    Returns resources for all files in the database that can be read.
    """
    try:
        db_service = get_database_service()
        await db_service.initialize_schema()

        # Get statistics to check if there are files
        stats = await db_service.get_statistics()
        total_files = stats.get("total_files", 0)

        if total_files == 0:
            return []

        # For now, we'll list up to 100 most recent files
        # In production, you'd want pagination
        resources = []

        # Get all files (simplified - you'd want to use a proper query)
        # For now, return empty list with note in description
        return [
            types.Resource(
                uri="archivum://files/all",
                name="All Ingested Files",
                description=f"Database contains {total_files} ingested files. Use search tools to query them.",
                mimeType="application/json",
            )
        ]

    except Exception as e:
        logger.error(f"Error listing resources: {e}")
        return []


@server.read_resource()
async def read_resource(uri: str) -> str:
    """
    Read content of a resource by URI.

    Supports URIs like:
    - archivum://file/<path>  - Read specific file metadata
    - archivum://files/all    - Get list of all files
    """
    try:
        if uri == "archivum://files/all":
            db_service = get_database_service()
            stats = await db_service.get_statistics()
            return f"Database Statistics:\n{stats}"

        if uri.startswith("archivum://file/"):
            # Extract file path from URI
            file_path_str = uri.replace("archivum://file/", "")
            file_path = Path(file_path_str)

            # Get file metadata from database
            db_service = get_database_service()
            file_data = await db_service.get_file_by_path(file_path)

            if file_data:
                return f"File: {file_data['filename']}\nPath: {file_data['path']}\nSize: {file_data['size']} bytes\nType: {file_data['mime_type']}"
            else:
                return f"File not found in database: {file_path}"

        return f"Unknown resource URI: {uri}"

    except Exception as e:
        logger.error(f"Error reading resource {uri}: {e}")
        return f"Error reading resource: {e}"


# ============================================================================
# TOOLS - Expose functionality as callable tools
# ============================================================================


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """
    List all available tools.

    Delegates to tools module for tool definitions.
    """
    return get_tool_definitions()


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """
    Handle tool execution.

    Delegates to tools module for actual execution.
    """
    return await execute_tool(name, arguments)


# ============================================================================
# SERVER LIFECYCLE
# ============================================================================


def create_mcp_server() -> Server:
    """Create and return the MCP server instance."""
    return server


async def run_mcp_server() -> None:
    """Run the MCP server with stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


def main() -> None:
    """Main entry point for running the MCP server."""
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting AIchemist Archivum MCP server...")

    try:
        asyncio.run(run_mcp_server())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
