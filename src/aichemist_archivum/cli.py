#!/usr/bin/env python
"""
Command-line interface for the AIchemist Codex.
This script provides direct access to the CLI functionality.
"""

import sys
from pathlib import Path

# Register parent directory in sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from the_aichemist_codex.interfaces.cli.cli import cli_app

if __name__ == "__main__":
    cli_app()
