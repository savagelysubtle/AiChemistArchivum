#!/usr/bin/env python
"""
Command-line interface for the AIchemist Archivum.
This script provides direct access to the CLI functionality.
"""

import sys
from pathlib import Path

# Register the project's src directory in sys.path
# This allows finding the aichemist_archivum package when running the script directly
# or when the environment is not fully set up for the installed package.
# Path to this file: backend/src/aichemist_archivum/interfaces/cli/commands.py
# We need to add 'backend/src' to sys.path.
_project_src_dir = Path(__file__).resolve().parent.parent.parent.parent
if str(_project_src_dir) not in sys.path:
    sys.path.insert(0, str(_project_src_dir))  # Prepend to path to prioritize

# This import should now be more reliable, assuming
# aichemist_archivum/interfaces/cli/cli.py defines cli_app.
from aichemist_archivum.interfaces.cli.cli import cli_app


def main() -> None:
    """
    Main entry point for the CLI application.
    This function invokes the Typer application.
    """
    cli_app()  # cli_app is expected to be the Typer application instance


if __name__ == "__main__":
    # This block executes when the script is run directly (e.g., python commands.py)
    main()
