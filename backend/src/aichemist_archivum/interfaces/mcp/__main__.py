#!/usr/bin/env python3
"""
Launcher script for the AIchemist Archivum MCP server.

This can be run directly or invoked via the MCP configuration.
"""

if __name__ == "__main__":
    from aichemist_archivum.interfaces.mcp.server import main

    main()
