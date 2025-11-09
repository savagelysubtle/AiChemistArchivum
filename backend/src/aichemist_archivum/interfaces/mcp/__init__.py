"""
MCP (Model Context Protocol) interface for AIchemist Archivum.

This module provides an MCP server that exposes AIchemist Archivum's
functionality as tools and resources for AI agents to use.

Architecture:
- server/: Protocol handling (resources, tool routing, lifecycle)
- tools/: Tool definitions and implementations
"""

from .server import create_mcp_server, run_mcp_server
from .tools import execute_tool, get_tool_definitions

__all__ = [
    # Server
    "create_mcp_server",
    "run_mcp_server",
    # Tools
    "execute_tool",
    "get_tool_definitions",
]
